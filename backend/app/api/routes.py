"""FastAPI routes for the anti-corruption audit chatbot.

The single endpoint exposed here orchestrates the full request flow:
1. Send the user's message to MiniMax for intent classification.
2. Dispatch to the matching Mercado Publico query or higher-level workflow.
3. Return the procurement data (lightly wrapped) to the caller.
"""

import asyncio
import json
import re
import unicodedata
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.services.mercado_publico import MercadoPublicoClient, MercadoPublicoError
from app.services.minimax_client import Intent, MiniMaxClient, MiniMaxError

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])

MAX_DATE_RANGE_DAYS = 366
MAX_MERCADO_RANGE_CONCURRENCY = 3


class QueryRequest(BaseModel):
    """Request body for the audit query endpoint."""

    message: str = Field(
        ...,
        min_length=1,
        description="Natural-language audit question from the user.",
        examples=["Show me purchase orders for organism 7239 on 2024-02-05"],
    )


class QueryResponse(BaseModel):
    """Response returned by the audit query endpoint."""

    # The structured routing decision produced by the LLM.
    intent: Intent
    # Raw/lightly-structured payload from Mercado Publico (None when unrouted).
    data: dict[str, Any] | None = None
    # Human-readable note, e.g. when the intent could not be mapped to a tool.
    detail: str | None = None


# --- Dependency providers --------------------------------------------------
# The service clients are created once at startup (see app.main.lifespan) and
# stored on ``app.state``. These helpers expose them to the route via FastAPI's
# dependency-injection system, which keeps the handler easy to test/mock.


def get_minimax_client(request: Request) -> MiniMaxClient:
    """Return the shared :class:`MiniMaxClient` from application state."""
    return request.app.state.minimax_client


def get_mercado_publico_client(request: Request) -> MercadoPublicoClient:
    """Return the shared :class:`MercadoPublicoClient` from application state."""
    return request.app.state.mercado_publico_client


@router.post(
    "/query",
    response_model=QueryResponse,
    summary="Route an audit question and fetch procurement data",
)
async def audit_query(
    payload: QueryRequest,
    minimax: MiniMaxClient = Depends(get_minimax_client),
    mercado_publico: MercadoPublicoClient = Depends(get_mercado_publico_client),
) -> QueryResponse:
    """Classify the user's message and return matching Mercado Publico data."""

    # 1. Ask the LLM which tool to use and extract its parameters.
    try:
        intent = await minimax.classify_intent(payload.message)
    except MiniMaxError as exc:
        # 502: an upstream dependency (the LLM) failed.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Intent analysis failed: {exc}",
        ) from exc

    # 2. Dispatch to the correct Mercado Publico query.
    params = intent.parameters
    detail: str | None = None
    try:
        if intent.tool == "orders_by_org_and_date":
            codigo_organismo, organism_resolution = await _resolve_organism_code(
                params=params,
                mercado_publico=mercado_publico,
            )
            if not codigo_organismo and organism_resolution:
                data = _organism_ambiguity_response(organism_resolution)
                detail = data.get("detail")
            elif not codigo_organismo or not params.fecha:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        "This query requires both an organism code/name and "
                        "'fecha'."
                    ),
                )
            else:
                payload_data = await mercado_publico.get_orders_by_org_and_date(
                    codigoorg=codigo_organismo, fecha=params.fecha
                )
                data = _wrap_resolved_payload(payload_data, organism_resolution)
                if organism_resolution:
                    detail = organism_resolution.get("detail")

        elif intent.tool == "orders_by_date":
            if not params.fecha:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="This query requires a 'fecha'.",
                )
            data = await mercado_publico.get_orders_by_date(fecha=params.fecha)

        elif intent.tool == "public_organism_lookup":
            if params.organism_name:
                data = await mercado_publico.resolve_public_organism(
                    params.organism_name
                )
                detail = data.get("detail")
            else:
                data = await mercado_publico.lookup_public_organisms()

        elif intent.tool == "tender_by_code":
            if not params.codigo:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="This query requires a tender 'codigo'.",
                )
            data = await mercado_publico.get_tender_by_code(codigo=params.codigo)

        elif intent.tool == "tenders_current_day":
            data = await mercado_publico.get_tenders_current_day()

        elif intent.tool == "tenders_by_date":
            if not params.fecha:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="This query requires a 'fecha'.",
                )
            data = await mercado_publico.get_tenders_by_date(fecha=params.fecha)

        elif intent.tool == "tenders_by_status_and_date":
            if not params.fecha or not params.estado:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="This query requires both 'fecha' and 'estado'.",
                )
            data = await mercado_publico.get_tenders_by_status_and_date(
                fecha=params.fecha, estado=params.estado
            )

        elif intent.tool == "tenders_by_supplier_and_date":
            if not params.fecha or not params.codigo_proveedor:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        "This query requires both 'fecha' and "
                        "'codigo_proveedor'."
                    ),
                )
            data = await mercado_publico.get_tenders_by_supplier_and_date(
                fecha=params.fecha, codigo_proveedor=params.codigo_proveedor
            )

        elif intent.tool == "tenders_by_org_and_date":
            codigo_organismo, organism_resolution = await _resolve_organism_code(
                params=params,
                mercado_publico=mercado_publico,
            )
            if not codigo_organismo and organism_resolution:
                data = _organism_ambiguity_response(organism_resolution)
                detail = data.get("detail")
            elif not params.fecha or not codigo_organismo:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        "This query requires both 'fecha' and an organism "
                        "code/name."
                    ),
                )
            else:
                payload_data = await mercado_publico.get_tenders_by_org_and_date(
                    codigo_organismo=codigo_organismo, fecha=params.fecha
                )
                data = _wrap_resolved_payload(payload_data, organism_resolution)
                if organism_resolution:
                    detail = organism_resolution.get("detail")

        elif intent.tool == "semantic_org_date_range_search":
            data = await _run_semantic_org_date_range_search(
                intent=intent,
                mercado_publico=mercado_publico,
            )
            detail = data.get("detail")

        else:
            # The LLM could not map the request to a supported tool.
            return QueryResponse(
                intent=intent,
                detail="Could not map the request to a known audit tool.",
            )
    except MercadoPublicoError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    # 3. Return the procurement payload alongside the routing decision.
    return QueryResponse(intent=intent, data=data, detail=detail)


async def _run_semantic_org_date_range_search(
    *,
    intent: Intent,
    mercado_publico: MercadoPublicoClient,
) -> dict[str, Any]:
    """Resolve an organism, query every date concurrently, and filter results."""
    params = intent.parameters
    if not params.start_date or not params.end_date:
        raise ValueError(
            "Semantic range search requires 'start_date' and 'end_date'."
        )

    dates = _expand_date_range(params.start_date, params.end_date)
    codigo_organismo = _organism_code(params)
    organism_resolution: dict[str, Any] | None = None

    if params.organism_name:
        organism_resolution = await mercado_publico.resolve_public_organism(
            params.organism_name
        )
        selected = organism_resolution.get("selected")
        if not selected:
            return {
                "detail": organism_resolution.get("detail"),
                "blocked_by_organism_ambiguity": True,
                "organism_resolution": organism_resolution,
                "dates": dates,
                "keywords": params.keywords,
                "records": [],
                "count": 0,
            }
        codigo_organismo = str(selected["code"])

    if not codigo_organismo:
        raise ValueError(
            "Semantic range search requires an organism name or CodigoOrganismo."
        )

    include_tenders = (
        params.include_tenders if params.include_tenders is not None else True
    )
    include_orders = (
        params.include_orders if params.include_orders is not None else False
    )
    if not include_tenders and not include_orders:
        include_tenders = True

    semaphore = asyncio.Semaphore(MAX_MERCADO_RANGE_CONCURRENCY)
    tasks = []
    for fecha in dates:
        if include_tenders:
            tasks.append(
                _fetch_records(
                    source="tenders",
                    fecha=fecha,
                    request=mercado_publico.get_tenders_by_org_and_date(
                        codigo_organismo=codigo_organismo,
                        fecha=fecha,
                    ),
                    semaphore=semaphore,
                )
            )
        if include_orders:
            tasks.append(
                _fetch_records(
                    source="purchase_orders",
                    fecha=fecha,
                    request=mercado_publico.get_orders_by_org_and_date(
                        codigoorg=codigo_organismo,
                        fecha=fecha,
                    ),
                    semaphore=semaphore,
                )
            )

    payloads = await asyncio.gather(*tasks)
    records = [
        record
        for payload in payloads
        for record in payload["records"]
    ]

    df, filtered_df, search_terms = _build_filtered_dataframe(
        records=records,
        keywords=params.keywords,
    )
    _print_filtered_dataframe(filtered_df)

    return {
        "detail": "Semantic date-range search completed.",
        "organism_resolution": organism_resolution,
        "codigo_organismo": codigo_organismo,
        "dates": dates,
        "queried_sources": {
            "tenders": include_tenders,
            "purchase_orders": include_orders,
        },
        "keywords": params.keywords,
        "search_terms": search_terms,
        "raw_record_count": int(len(df.index)),
        "count": int(len(filtered_df.index)),
        "columns": [str(column) for column in filtered_df.columns],
        "records": _dataframe_to_records(filtered_df),
    }


async def _fetch_records(
    *,
    source: str,
    fecha: str,
    request: Any,
    semaphore: asyncio.Semaphore,
) -> dict[str, Any]:
    async with semaphore:
        payload = await request
    records = []
    for record in _extract_records(payload):
        annotated = dict(record)
        annotated["_source"] = source
        annotated["_query_fecha"] = fecha
        records.append(annotated)
    return {"source": source, "fecha": fecha, "records": records}


def _organism_code(params: Any) -> str | None:
    return params.codigo_organismo or params.codigoorg


async def _resolve_organism_code(
    *,
    params: Any,
    mercado_publico: MercadoPublicoClient,
) -> tuple[str | None, dict[str, Any] | None]:
    codigo_organismo = _organism_code(params)
    if codigo_organismo or not params.organism_name:
        return codigo_organismo, None

    organism_resolution = await mercado_publico.resolve_public_organism(
        params.organism_name
    )
    selected = organism_resolution.get("selected")
    if selected:
        return str(selected["code"]), organism_resolution
    return None, organism_resolution


def _organism_ambiguity_response(
    organism_resolution: dict[str, Any],
) -> dict[str, Any]:
    return {
        "detail": organism_resolution.get("detail"),
        "blocked_by_organism_ambiguity": True,
        "organism_resolution": organism_resolution,
    }


def _wrap_resolved_payload(
    payload: dict[str, Any],
    organism_resolution: dict[str, Any] | None,
) -> dict[str, Any]:
    if not organism_resolution:
        return payload
    return {
        "organism_resolution": organism_resolution,
        "payload": payload,
    }


def _expand_date_range(start_date: str, end_date: str) -> list[str]:
    start = _parse_mercado_date(start_date, "start_date")
    end = _parse_mercado_date(end_date, "end_date")
    if end < start:
        raise ValueError("'end_date' must be greater than or equal to 'start_date'.")

    days = (end - start).days + 1
    if days > MAX_DATE_RANGE_DAYS:
        raise ValueError(
            f"Date ranges are limited to {MAX_DATE_RANGE_DAYS} days; got {days}."
        )

    return [
        (start + timedelta(days=offset)).strftime("%d%m%Y")
        for offset in range(days)
    ]


def _parse_mercado_date(value: str, field_name: str) -> datetime:
    if not re.fullmatch(r"\d{8}", value):
        raise ValueError(f"'{field_name}' must use ddmmyyyy format.")
    try:
        return datetime.strptime(value, "%d%m%Y")
    except ValueError as exc:
        raise ValueError(
            f"'{field_name}' must be a valid ddmmyyyy date."
        ) from exc


def _extract_records(payload: dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [record for record in payload if isinstance(record, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("Listado", "listado", "Ordenes", "ordenes", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            return [record for record in value if isinstance(record, dict)]
    return []


def _build_filtered_dataframe(
    *,
    records: list[dict[str, Any]],
    keywords: list[str],
) -> tuple[Any, Any, list[str]]:
    pd = _load_pandas()
    df = pd.DataFrame(records)
    search_terms = _expand_search_terms(keywords)

    if df.empty or not search_terms:
        return df, df, search_terms

    columns = _searchable_columns(df)
    searchable_text = df[columns].apply(
        lambda row: " ".join(_stringify_cell(value) for value in row),
        axis=1,
    )
    normalized_terms = [_normalize_for_search(term) for term in search_terms]
    mask = searchable_text.map(
        lambda value: any(
            term in _normalize_for_search(value)
            for term in normalized_terms
            if term
        )
    )
    return df, df.loc[mask].copy(), search_terms


def _load_pandas() -> Any:
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError(
            "Pandas is required for semantic filtering. Install backend "
            "dependencies with 'pip install -r backend/requirements.txt'."
        ) from exc
    return pd


def _searchable_columns(df: Any) -> list[str]:
    preferred_fragments = (
        "nombre",
        "descripcion",
        "descrip",
        "producto",
        "item",
        "rubro",
        "categoria",
        "adquisicion",
        "licitacion",
        "glosa",
    )
    preferred = [
        column
        for column in df.columns
        if any(
            fragment in _normalize_for_search(str(column))
            for fragment in preferred_fragments
        )
    ]
    if preferred:
        return preferred
    return list(df.columns)


def _expand_search_terms(keywords: list[str]) -> list[str]:
    terms: list[str] = []
    for keyword in keywords:
        terms.extend(_split_keyword(keyword))

    normalized = {_normalize_for_search(term) for term in terms if term}
    if any(
        root in term
        for term in normalized
        for root in ("comput", "sistema", "software", "hardware")
    ):
        terms.extend(
            [
                "computacional",
                "computacionales",
                "computacion",
                "computación",
                "informatica",
                "informática",
                "sistema",
                "sistemas",
                "software",
                "hardware",
                "tecnologia",
                "tecnología",
            ]
        )

    seen: set[str] = set()
    unique_terms = []
    for term in terms:
        normalized_term = _normalize_for_search(term)
        if normalized_term and normalized_term not in seen:
            seen.add(normalized_term)
            unique_terms.append(term)
    return unique_terms


def _split_keyword(keyword: str) -> list[str]:
    pieces = [keyword]
    pieces.extend(re.split(r"[/,;]+|\s+(?:or|and|o|y)\s+", keyword, flags=re.I))
    return [piece.strip() for piece in pieces if piece.strip()]


def _normalize_for_search(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text.strip().lower())


def _stringify_cell(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return "" if value is None else str(value)


def _print_filtered_dataframe(df: Any) -> None:
    pd = _load_pandas()
    print("\n=== Mercado Publico filtered dataset ===")
    with pd.option_context(
        "display.max_rows",
        200,
        "display.max_columns",
        None,
        "display.width",
        240,
        "display.max_colwidth",
        120,
    ):
        if df.empty:
            print(df)
        else:
            print(df.to_string(index=False))


def _dataframe_to_records(df: Any) -> list[dict[str, Any]]:
    if df.empty:
        return []
    return json.loads(
        df.to_json(
            orient="records",
            force_ascii=False,
            default_handler=str,
        )
    )
