"""Task executor for the multi-agent audit pipeline.

The Executor is pure Python — no LLM. It maps tool names to service-client
calls and runs every task in the plan concurrently. Adding a new data source
is a matter of adding a branch to :meth:`Executor._dispatch`.

Tool catalogue (keep in sync with the Planner prompt):

  Mercado Público:
    mp_orders_by_org_and_date   codigoorg|organism_name, fecha
    mp_orders_by_date           fecha
    mp_tender_by_codigo         codigo
    mp_tenders_today            (no params)
    mp_tenders_by_date          fecha
    mp_tenders_by_status        fecha, estado
    mp_tenders_by_supplier      fecha, CodigoProveedor
    mp_tenders_by_org           fecha, codigo_organismo|organism_name
    mp_search_buyers            (no params) — dumps all organisms
    mp_resolve_organism         organism_name — resolves name → code
    mp_semantic_range           organism_name, start_date, end_date,
                                keywords, include_orders, include_tenders

  Senate:
    senado_support_staff        year, month_es, senator_name?, staff_name?

  Contraloría:
    contraloria_search          entity_name?, year_min?, year_max?, region?,
                                tipo_fiscalizacion?, complejidad?, keywords,
                                source (municipalidades|no_municipales|both), limit?

  Cámara de Diputados:
    camara_resolve_diputado     name → [{codigo, nombre}]
    camara_datos_diputado       name OR codigo, categoria (gastos_operacionales |
                                asesoria_externa | pasajes_aereos |
                                instancias_internacionales | personal_apoyo |
                                audiencias) — resolves name inline if codigo absent/0
"""

import asyncio
import json
import re
import unicodedata
from datetime import datetime, timedelta
from typing import Any

from app.core.text import normalize_text
from app.services.camara import CamaraError, CamaraService
from app.services.contraloria import ContraloriaError, ContraloriaService
from app.services.mercado_publico import MercadoPublicoClient, MercadoPublicoError
from app.services.models import Plan, Task, TaskResult
from app.services.senado_scraper import SenadoClient, SenadoScraperError

_MAX_DATE_RANGE_DAYS = 366
_MAX_CONCURRENCY = 5   # concurrent Mercado Público calls inside mp_semantic_range


class ExecutorError(RuntimeError):
    """Raised for configuration errors (missing required params, etc.)."""


class Executor:
    """Runs a :class:`~app.services.models.Plan` and returns one result per task.

    All tasks execute concurrently via :func:`asyncio.gather`. Individual task
    failures are captured as ``status="error"`` results so a single bad call
    does not abort the whole pipeline.
    """

    def __init__(
        self,
        mp: MercadoPublicoClient,
        senado: SenadoClient,
        contraloria: ContraloriaService,
        camara: CamaraService,
    ) -> None:
        self._mp = mp
        self._senado = senado
        self._contraloria = contraloria
        self._camara = camara

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    async def run(self, plan: Plan) -> list[TaskResult]:
        """Execute all tasks in *plan* concurrently and return results."""
        return list(
            await asyncio.gather(*[self._run_one(task) for task in plan.tasks])
        )

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    async def _run_one(self, task: Task) -> TaskResult:
        try:
            records, metadata = await self._dispatch(task)
            return TaskResult(
                task_id=task.id,
                tool=task.tool,
                description=task.description,
                status="ok",
                records=records,
                record_count=len(records),
                metadata=metadata,
            )
        except (ExecutorError, SenadoScraperError, MercadoPublicoError, ContraloriaError, CamaraError, ValueError) as exc:
            return TaskResult(
                task_id=task.id,
                tool=task.tool,
                description=task.description,
                status="error",
                error=str(exc),
            )

    async def _dispatch(
        self, task: Task
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Return (records, metadata) for one task."""
        p = task.parameters
        tool = task.tool

        # ── Senate ──────────────────────────────────────────────────────
        if tool == "senado_support_staff":
            df = await self._senado.scrape_support_staff(
                year=int(p["year"]),
                month=str(p["month_es"]),
                senator=p.get("senator_name"),
                support_staff=p.get("staff_name"),
            )
            return df.to_dict(orient="records"), {}

        # ── Mercado Público ─────────────────────────────────────────────
        if tool == "mp_orders_by_org_and_date":
            _require(p, "fecha")
            codigoorg, resolution = await self._resolve_organism_code(p)
            if not codigoorg:
                return [], {
                    "organism_resolution": resolution,
                    "blocked_by_organism_ambiguity": True,
                }
            data = await self._mp.get_orders_by_org_and_date(
                codigoorg=codigoorg, fecha=p["fecha"]
            )
            metadata: dict[str, Any] = {"codigo_organismo": codigoorg}
            if resolution:
                metadata["organism_resolution"] = resolution
            return _extract_records(data), metadata

        if tool == "mp_orders_by_date":
            _require(p, "fecha")
            data = await self._mp.get_orders_by_date(fecha=p["fecha"])
            return _extract_records(data), {}

        if tool == "mp_tender_by_codigo":
            _require(p, "codigo")
            data = await self._mp.get_tender_by_code(codigo=p["codigo"])
            return _extract_records(data), {}

        if tool == "mp_tenders_today":
            data = await self._mp.get_tenders_current_day()
            return _extract_records(data), {}

        if tool == "mp_tenders_by_date":
            _require(p, "fecha")
            data = await self._mp.get_tenders_by_date(fecha=p["fecha"])
            return _extract_records(data), {}

        if tool == "mp_tenders_by_status":
            _require(p, "fecha", "estado")
            data = await self._mp.get_tenders_by_status_and_date(
                fecha=p["fecha"], estado=p["estado"]
            )
            return _extract_records(data), {}

        if tool == "mp_tenders_by_supplier":
            _require(p, "fecha", "CodigoProveedor")
            data = await self._mp.get_tenders_by_supplier_and_date(
                fecha=p["fecha"], codigo_proveedor=p["CodigoProveedor"]
            )
            return _extract_records(data), {}

        if tool == "mp_tenders_by_org":
            _require(p, "fecha")
            codigo_organismo, resolution = await self._resolve_organism_code(p)
            if not codigo_organismo:
                return [], {
                    "organism_resolution": resolution,
                    "blocked_by_organism_ambiguity": True,
                }
            data = await self._mp.get_tenders_by_org_and_date(
                fecha=p["fecha"], codigo_organismo=codigo_organismo
            )
            metadata = {"codigo_organismo": codigo_organismo}
            if resolution:
                metadata["organism_resolution"] = resolution
            return _extract_records(data), metadata

        if tool == "mp_search_buyers":
            data = await self._mp.lookup_public_organisms()
            # Delegate to the authoritative extractor in MercadoPublicoClient
            # which knows all the response-envelope key names (listaEmpresas, etc.)
            records = MercadoPublicoClient._extract_records(data)
            return records, {"total_organisms": len(records)}

        if tool == "mp_resolve_organism":
            _require(p, "organism_name")
            resolution = await self._mp.resolve_public_organism(p["organism_name"])
            # Return candidates as records so synthesis can read them
            records = resolution.get("candidates") or []
            return records, {"resolution": resolution}

        if tool == "mp_semantic_range":
            return await self._run_semantic_range(p)

        # ── Contraloría ──────────────────────────────────────────────────
        if tool == "contraloria_search":
            records, metadata = await self._contraloria.search(
                entity_name=p.get("entity_name"),
                year_min=int(p["year_min"]) if p.get("year_min") is not None else None,
                year_max=int(p["year_max"]) if p.get("year_max") is not None else None,
                region=p.get("region"),
                tipo_fiscalizacion=p.get("tipo_fiscalizacion"),
                complejidad=p.get("complejidad"),
                keywords=p.get("keywords") or [],
                source=p.get("source") or "both",
                limit=int(p["limit"]) if p.get("limit") is not None else 50,
            )
            return records, metadata

        # ── Cámara de Diputados ──────────────────────────────────────────
        if tool == "camara_resolve_diputado":
            _require(p, "name")
            candidates = await self._camara.resolve_diputado(p["name"])
            return candidates, {"total_candidates": len(candidates)}

        if tool == "camara_datos_diputado":
            _require(p, "categoria")
            codigo = p.get("codigo")
            if not codigo or int(codigo) == 0:
                _require(p, "name")
                candidates = await self._camara.resolve_diputado(str(p["name"]))
                if not candidates:
                    raise CamaraError(f"No deputy found matching {p['name']!r}")
                if len(candidates) > 1:
                    # Ambiguous: return candidates so synthesizer can ask to clarify
                    return candidates, {
                        "ambiguous": True,
                        "candidates": candidates,
                        "categoria": p["categoria"],
                    }
                codigo = candidates[0]["codigo"]
            records, metadata = await self._camara.fetch_categoria(
                codigo=int(codigo),
                categoria=str(p["categoria"]),
            )
            return records, metadata

        raise ExecutorError(f"Unknown tool: {tool!r}")

    async def _run_semantic_range(
        self, p: dict[str, Any]
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Multi-date semantic search for one organism over a date range."""
        _require(p, "organism_name", "start_date", "end_date")

        # Resolve organism name → numeric code using the MP client.
        organism_name: str = p["organism_name"]
        resolution = await self._mp.resolve_public_organism(organism_name)
        if not resolution["selected"]:
            return [], {
                "organism_resolution": resolution,
                "blocked_by_ambiguity": True,
            }
        codigo_organismo = str(resolution["selected"]["code"])

        # Expand date range.
        dates = _expand_date_range(p["start_date"], p["end_date"])
        keywords: list[str] = p.get("keywords") or []
        include_tenders = bool(p.get("include_tenders", True))
        include_orders = bool(p.get("include_orders", False))

        # Fetch all dates concurrently.
        semaphore = asyncio.Semaphore(_MAX_CONCURRENCY)
        coros = []
        for fecha in dates:
            if include_tenders:
                coros.append(
                    _fetch_with_semaphore(
                        semaphore,
                        source="tender",
                        fecha=fecha,
                        coro=self._mp.get_tenders_by_org_and_date(
                            fecha=fecha, codigo_organismo=codigo_organismo
                        ),
                    )
                )
            if include_orders:
                coros.append(
                    _fetch_with_semaphore(
                        semaphore,
                        source="order",
                        fecha=fecha,
                        coro=self._mp.get_orders_by_org_and_date(
                            codigoorg=codigo_organismo, fecha=fecha
                        ),
                    )
                )

        pages = await asyncio.gather(*coros)

        all_records: list[dict[str, Any]] = []
        api_errors: list[str] = []
        for page in pages:
            if isinstance(page, str):        # error sentinel from _fetch_with_semaphore
                api_errors.append(page)
            else:
                all_records.extend(page)

        # Semantic keyword filter.
        filtered, search_terms = _semantic_filter(all_records, keywords)

        metadata = {
            "organism_resolution": resolution,
            "codigo_organismo": codigo_organismo,
            "dates_queried": len(dates),
            "api_calls": len(coros),
            "api_errors": len(api_errors),
            "raw_record_count": len(all_records),
            "search_terms": search_terms,
        }
        if api_errors:
            metadata["error_sample"] = api_errors[:3]  # first 3 to avoid flooding
        return filtered, metadata

    async def _resolve_organism_code(
        self,
        p: dict[str, Any],
    ) -> tuple[str | None, dict[str, Any] | None]:
        """Return a Mercado Público organism code from code or name params."""
        code = p.get("codigoorg") or p.get("codigo_organismo")
        if code:
            return str(code), None

        organism_name = p.get("organism_name")
        if not organism_name:
            raise ExecutorError(
                "Missing required parameters: codigoorg/codigo_organismo or organism_name"
            )

        resolution = await self._mp.resolve_public_organism(str(organism_name))
        selected = resolution.get("selected")
        if not selected:
            return None, resolution
        return str(selected["code"]), resolution


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require(params: dict[str, Any], *keys: str) -> None:
    missing = [k for k in keys if not params.get(k)]
    if missing:
        raise ExecutorError(
            f"Missing required parameters: {', '.join(missing)}"
        )


def _extract_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("Listado", "listado", "Ordenes", "ordenes", "data", "Data"):
        value = payload.get(key)
        if isinstance(value, list):
            return [r for r in value if isinstance(r, dict)]
    return []


def _resolve_organism(
    name: str, buyers: list[dict[str, Any]]
) -> dict[str, Any]:
    """Find organisms whose name contains *name* (accent-insensitive)."""
    key = normalize_text(name)
    matches = [
        b for b in buyers
        if key in normalize_text(
            str(b.get("Nombre") or b.get("nombre") or b.get("name") or "")
        )
    ]
    if len(matches) == 1:
        m = matches[0]
        code = m.get("CodigoOrganismo") or m.get("codigo") or m.get("id")
        return {
            "selected": {"code": code, "name": str(m.get("Nombre") or name)},
            "candidates": matches,
            "detail": None,
        }
    if len(matches) > 1:
        return {
            "selected": None,
            "candidates": matches[:10],
            "detail": (
                f"Found {len(matches)} organisms matching {name!r}. "
                "Provide a more specific name or a numeric code."
            ),
        }
    return {
        "selected": None,
        "candidates": [],
        "detail": f"No public organism matched {name!r}.",
    }


def _expand_date_range(start: str, end: str) -> list[str]:
    fmt = "%d%m%Y"
    try:
        s = datetime.strptime(start, fmt)
        e = datetime.strptime(end, fmt)
    except ValueError as exc:
        raise ExecutorError(f"Dates must be in ddmmyyyy format: {exc}") from exc
    if e < s:
        raise ExecutorError("end_date must be >= start_date.")
    days = (e - s).days + 1
    if days > _MAX_DATE_RANGE_DAYS:
        raise ExecutorError(
            f"Date range too large ({days} days, max {_MAX_DATE_RANGE_DAYS})."
        )
    return [(s + timedelta(i)).strftime(fmt) for i in range(days)]


async def _fetch_with_semaphore(
    semaphore: asyncio.Semaphore,
    source: str,
    fecha: str,
    coro: Any,
) -> list[dict[str, Any]] | str:
    async with semaphore:
        try:
            payload = await coro
        except MercadoPublicoError as exc:
            return f"{source}:{fecha}:{exc}"
    records = _extract_records(payload)
    for r in records:
        r["_source"] = source
        r["_fecha"] = fecha
    return records


def _normalize_search(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", text.lower())).strip()


def _semantic_filter(
    records: list[dict[str, Any]], keywords: list[str]
) -> tuple[list[dict[str, Any]], list[str]]:
    if not keywords or not records:
        return records, []
    terms = _expand_search_terms(keywords)
    searchable_keys = [
        k for k in records[0]
        if any(
            frag in _normalize_search(k)
            for frag in ("nombre", "descrip", "producto", "item", "rubro", "glosa")
        )
    ] or list(records[0].keys())

    def _matches(record: dict) -> bool:
        text = " ".join(
            _normalize_search(str(record.get(k, ""))) for k in searchable_keys
        )
        return any(t in text for t in terms if t)

    return [r for r in records if _matches(r)], terms


def _expand_search_terms(keywords: list[str]) -> list[str]:
    """Expand semantic keywords with common Spanish singular/plural variants."""
    terms: list[str] = []
    for keyword in keywords:
        normalized = _normalize_search(keyword)
        if not normalized:
            continue
        terms.append(normalized)
        terms.extend(
            part
            for part in re.split(r"[/,;]+|\s+(?:or|and|o|y)\s+", normalized)
            if part
        )

    for term in list(terms):
        singular = _singularize_phrase(term)
        if singular != term:
            terms.append(singular)

    normalized_terms = set(terms)
    if any(
        root in term
        for term in normalized_terms
        for root in (
            "comput",
            "informat",
            "sistema",
            "software",
            "hardware",
            "tecnolog",
        )
    ):
        terms.extend(
            [
                "sistema informatico",
                "sistemas informaticos",
                "sistema computacional",
                "sistemas computacionales",
                "computacional",
                "computacionales",
                "computacion",
                "informatica",
                "informaticas",
                "informatico",
                "informaticos",
                "software",
                "hardware",
                "tecnologia",
                "tecnologias",
            ]
        )

    seen: set[str] = set()
    unique_terms = []
    for term in terms:
        normalized = _normalize_search(term)
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique_terms.append(normalized)
    return unique_terms


def _singularize_phrase(term: str) -> str:
    words = [_singularize_word(word) for word in term.split()]
    return " ".join(words)


def _singularize_word(word: str) -> str:
    if len(word) <= 4:
        return word
    if word.endswith("ciones"):
        return f"{word[:-6]}cion"
    if word.endswith("ales"):
        return f"{word[:-4]}al"
    if word.endswith("icos") or word.endswith("icas"):
        return word[:-1]
    if word.endswith("es") and not word.endswith(("ces", "ses")):
        return word[:-2]
    if word.endswith("s") and not word.endswith(("is", "us")):
        return word[:-1]
    return word
