"""Async client wrapper for the Chilean government 'Mercado Publico' API.

The :class:`MercadoPublicoClient` is intentionally minimal and extensible:
every public method models exactly *one* business query and delegates all
networking to the private :meth:`MercadoPublicoClient._make_request` helper.
Adding a new endpoint/query is therefore a one-method change.
"""

import re
import unicodedata
import asyncio
from typing import Any

import httpx

from app.core.config import Settings


class MercadoPublicoError(RuntimeError):
    """Raised when Mercado Publico is unreachable or returns an HTTP error."""


class MercadoPublicoClient:
    """Thin async wrapper around the Mercado Publico REST API.

    Parameters
    ----------
    settings:
        Application settings holding the API ticket and base URL.
    client:
        A shared :class:`httpx.AsyncClient`. Sharing a single client across the
        app enables connection pooling and keep-alive.
    """

    # Every purchase-order query targets the same JSON resource; only the
    # query-string parameters differ between methods.
    ORDERS_ENDPOINT = "ordenesdecompra.json"
    TENDERS_ENDPOINT = "licitaciones.json"
    BUYERS_ENDPOINT = "Empresas/BuscarComprador"

    TENDER_STATUS_CODES = {
        "publicada": "5",
        "5": "5",
        "cerrada": "6",
        "6": "6",
        "desierta": "7",
        "7": "7",
        "adjudicada": "8",
        "8": "8",
        "revocada": "18",
        "18": "18",
        "suspendida": "19",
        "19": "19",
        "todos": None,
        "todas": None,
        "all": None,
    }

    _ORGANISM_CODE_FIELDS = (
        "CodigoOrganismo",
        "CodigoEmpresa",
        "CodigoUnidad",
        "Codigo",
        "CodigoComprador",
        "codigoOrganismo",
        "codigoEmpresa",
    )
    _ORGANISM_NAME_FIELDS = (
        "NombreOrganismo",
        "NombreEmpresa",
        "RazonSocial",
        "Nombre",
        "NombreUnidad",
        "Comprador",
        "nombreOrganismo",
        "nombreEmpresa",
    )
    RETRYABLE_HTTP_STATUSES = {429, 500, 502, 503, 504}
    MAX_RETRY_ATTEMPTS = 3

    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        self._client = client
        self._base_url = settings.MERCADO_PUBLICO_BASE_URL.rstrip("/")
        self._public_lookup_base_url = self._derive_public_lookup_base_url(
            self._base_url
        )
        self._ticket = settings.MERCADO_PUBLICO_TICKET

    async def _make_request(
        self,
        endpoint: str,
        params: dict[str, Any],
        *,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        """Perform an authenticated GET request and return the parsed JSON.

        The ``ticket`` is injected automatically, so callers only ever pass the
        parameters specific to their query. This keeps every public method free
        of authentication and error-handling boilerplate.

        Raises
        ------
        MercadoPublicoError
            If the API responds with an error status or cannot be reached.
        """
        root_url = (base_url or self._base_url).rstrip("/")
        url = f"{root_url}/{endpoint.lstrip('/')}"
        # The ticket is always required; merge it with the caller's params.
        clean_params = {
            key: value for key, value in params.items() if value is not None
        }
        query: dict[str, Any] = {"ticket": self._ticket, **clean_params}

        for attempt in range(self.MAX_RETRY_ATTEMPTS + 1):
            try:
                response = await self._client.get(url, params=query)
                if response.status_code in self.RETRYABLE_HTTP_STATUSES:
                    if attempt < self.MAX_RETRY_ATTEMPTS:
                        await asyncio.sleep(
                            self._retry_delay(response, attempt)
                        )
                        continue
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as exc:
                raise MercadoPublicoError(
                    f"Mercado Publico returned HTTP {exc.response.status_code} "
                    f"for '{endpoint}'."
                ) from exc
            except httpx.HTTPError as exc:
                # Covers timeouts, connection errors, DNS failures, etc.
                if attempt < self.MAX_RETRY_ATTEMPTS:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                raise MercadoPublicoError(
                    f"Could not reach Mercado Publico for '{endpoint}': {exc}"
                ) from exc

        raise MercadoPublicoError(f"Could not reach Mercado Publico for '{endpoint}'.")

    # ------------------------------------------------------------------
    # Public business queries. To add a new query, simply define another
    # async method here that builds its ``params`` and calls ``_make_request``.
    # ------------------------------------------------------------------

    async def get_orders_by_org_and_date(
        self, codigoorg: str, fecha: str
    ) -> dict[str, Any]:
        """Method A - purchase orders for one organism on a specific date.

        Parameters
        ----------
        codigoorg:
            Code identifying the public organism (``CodigoOrganismo``).
        fecha:
            Date in ``ddmmyyyy`` format, as expected by Mercado Publico.
        """
        return await self._make_request(
            self.ORDERS_ENDPOINT,
            {"CodigoOrganismo": codigoorg, "fecha": fecha},
        )

    async def get_orders_by_date(self, fecha: str) -> dict[str, Any]:
        """Method B - every purchase order issued on a specific date.

        Parameters
        ----------
        fecha:
            Date in ``ddmmyyyy`` format, as expected by Mercado Publico.
        """
        return await self._make_request(self.ORDERS_ENDPOINT, {"fecha": fecha})

    async def lookup_public_organisms(self) -> dict[str, Any]:
        """Return public buyer organisms from the BuscarComprador endpoint."""
        return await self._make_request(
            self.BUYERS_ENDPOINT,
            {},
            base_url=self._public_lookup_base_url,
        )

    async def resolve_public_organism(self, name: str) -> dict[str, Any]:
        """Resolve an organism name and surface ambiguity instead of guessing.

        Mercado Publico has several independent entities per commune, especially
        municipalities and their education, health, and cultural corporations.
        This resolver selects one unique exact normalized match when available;
        otherwise it returns the plausible candidates and marks the result as
        ambiguous so the caller can ask for verification or stop the query.
        """
        payload = await self.lookup_public_organisms()
        organisms = self._extract_records(payload)
        query_norm = self._normalize_organism_name(name)

        candidates: list[dict[str, Any]] = []
        for organism in organisms:
            organism_name = self._first_present(
                organism, self._ORGANISM_NAME_FIELDS
            )
            organism_code = self._first_present(
                organism, self._ORGANISM_CODE_FIELDS
            )
            if not organism_name or not organism_code:
                continue

            name_norm = self._normalize_organism_name(str(organism_name))
            match_type = self._match_organism_name(query_norm, name_norm)
            if not match_type:
                continue

            candidates.append(
                {
                    "code": str(organism_code),
                    "name": str(organism_name),
                    "match_type": match_type,
                    "raw": organism,
                }
            )

        exact_matches = [
            candidate
            for candidate in candidates
            if candidate["match_type"] == "exact"
        ]
        selected: dict[str, Any] | None = None
        ambiguous = False

        if len(exact_matches) == 1:
            selected = exact_matches[0]
        elif len(exact_matches) > 1:
            ambiguous = True
        elif len(candidates) == 1:
            selected = candidates[0]
        elif len(candidates) > 1:
            ambiguous = True

        return {
            "query": name,
            "selected": selected,
            "ambiguous": ambiguous,
            "candidates": candidates,
            "candidate_count": len(candidates),
            "verification_required": ambiguous or selected is None,
            "detail": self._resolution_detail(name, selected, candidates, ambiguous),
            "source_payload_count": len(organisms),
        }

    async def get_tender_by_code(self, codigo: str) -> dict[str, Any]:
        """Tender details by Codigo de Licitacion."""
        return await self._make_request(
            self.TENDERS_ENDPOINT,
            {"codigo": codigo},
        )

    async def get_tenders_current_day(self) -> dict[str, Any]:
        """All tenders for the API's current day."""
        return await self._make_request(self.TENDERS_ENDPOINT, {})

    async def get_tenders_by_date(self, fecha: str) -> dict[str, Any]:
        """All tenders for a specific date in ddmmyyyy format."""
        return await self._make_request(self.TENDERS_ENDPOINT, {"fecha": fecha})

    async def get_tenders_by_status_and_date(
        self, fecha: str, estado: str
    ) -> dict[str, Any]:
        """Tenders for a date and Mercado Publico status.

        ``estado`` may be a public Spanish name (for example ``Publicada``) or
        an internal API code. ``Todos`` omits the filter.
        """
        estado_code = self.normalize_tender_status(estado)
        return await self._make_request(
            self.TENDERS_ENDPOINT,
            {"fecha": fecha, "estado": estado_code},
        )

    async def get_tenders_by_supplier_and_date(
        self, fecha: str, codigo_proveedor: str
    ) -> dict[str, Any]:
        """Tenders for a supplier code on a specific date."""
        return await self._make_request(
            self.TENDERS_ENDPOINT,
            {"fecha": fecha, "CodigoProveedor": codigo_proveedor},
        )

    async def get_tenders_by_org_and_date(
        self, codigo_organismo: str, fecha: str
    ) -> dict[str, Any]:
        """Tenders for a public organism code on a specific date."""
        return await self._make_request(
            self.TENDERS_ENDPOINT,
            {"fecha": fecha, "CodigoOrganismo": codigo_organismo},
        )

    @classmethod
    def normalize_tender_status(cls, estado: str | None) -> str | None:
        """Return the Mercado Publico status code for a public status label."""
        if estado is None:
            return None

        key = cls._normalize_text(str(estado))
        if key not in cls.TENDER_STATUS_CODES:
            allowed = ", ".join(
                sorted(k for k in cls.TENDER_STATUS_CODES if not k.isdigit())
            )
            raise MercadoPublicoError(
                f"Unknown tender status '{estado}'. Expected one of: {allowed}."
            )
        return cls.TENDER_STATUS_CODES[key]

    @staticmethod
    def _derive_public_lookup_base_url(base_url: str) -> str:
        """Build the exact Publico root used by BuscarComprador."""
        marker = "/publico"
        lower_base = base_url.lower()
        if lower_base.endswith(marker):
            services_v1 = base_url[: -len(marker)]
            return f"{services_v1}/Publico"
        if lower_base.endswith("/servicios/v1"):
            return f"{base_url.rstrip('/')}/Publico"
        return base_url.rstrip("/")

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return min(float(retry_after), 10.0)
            except ValueError:
                pass
        return min(0.75 * (2**attempt), 6.0)

    @classmethod
    def _normalize_text(cls, value: str) -> str:
        text = unicodedata.normalize("NFKD", value)
        text = "".join(char for char in text if not unicodedata.combining(char))
        return re.sub(r"\s+", " ", text.strip().lower())

    @classmethod
    def _normalize_organism_name(cls, value: str) -> str:
        text = cls._normalize_text(value).upper()
        text = re.sub(r"[^A-Z0-9]+", " ", text)
        text = re.sub(r"\bI\s+MUNICIPALIDAD\b", "MUNICIPALIDAD", text)
        text = re.sub(r"\bILUSTRE\s+MUNICIPALIDAD\b", "MUNICIPALIDAD", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @classmethod
    def _match_organism_name(
        cls, query_norm: str, organism_norm: str
    ) -> str | None:
        if not query_norm:
            return None
        if organism_norm == query_norm:
            return "exact"
        if query_norm in organism_norm:
            return "contains"

        query_tokens = cls._meaningful_tokens(query_norm)
        organism_tokens = cls._meaningful_tokens(organism_norm)
        if query_tokens and query_tokens.issubset(organism_tokens):
            return "token_subset"
        return None

    @staticmethod
    def _meaningful_tokens(value: str) -> set[str]:
        stopwords = {"DE", "DEL", "LA", "LAS", "LOS", "EL", "Y"}
        return {
            token
            for token in value.split()
            if token not in stopwords and len(token) > 1
        }

    @staticmethod
    def _extract_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [record for record in payload if isinstance(record, dict)]
        for key in (
            "Listado",
            "listado",
            "listaEmpresas",
            "Empresas",
            "empresas",
            "data",
        ):
            value = payload.get(key)
            if isinstance(value, list):
                return [
                    record for record in value if isinstance(record, dict)
                ]
        for value in payload.values():
            if isinstance(value, list) and all(
                isinstance(record, dict) for record in value
            ):
                return value
        return []

    @staticmethod
    def _first_present(record: dict[str, Any], fields: tuple[str, ...]) -> Any:
        for field in fields:
            value = record.get(field)
            if value not in (None, ""):
                return value
        return None

    @staticmethod
    def _resolution_detail(
        name: str,
        selected: dict[str, Any] | None,
        candidates: list[dict[str, Any]],
        ambiguous: bool,
    ) -> str:
        if selected and not ambiguous:
            if len(candidates) > 1:
                return (
                    "Resolved to a unique exact organism; similar buyer "
                    "entities were retained for verification."
                )
            return "Resolved to a unique public organism."
        if ambiguous:
            return (
                f"Multiple public buyer organisms match '{name}'. Verify the "
                "specific municipality or corporation before querying."
            )
        return f"No public buyer organism matched '{name}'."
