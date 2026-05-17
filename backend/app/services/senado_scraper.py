"""REST API client for the Chilean Senate support-staff transparency data.

The Senate backend exposes a Strapi v4 REST API — no browser automation needed.

Example (April 2024):
  GET https://web-back.senado.cl/api/transparency/senator-assignments/support-staff
      ?filters[ano][$eq]=2024&filters[mes][$eq]=4&sort=appaterno

Adding a new Senate endpoint is a one-method addition to :class:`SenadoClient`,
mirroring the pattern in ``mercado_publico.py``.
"""

import time
from typing import Any

import httpx
import pandas as pd

from app.core.text import name_matches, normalize_text

_BASE_URL = "https://web-back.senado.cl"
_SUPPORT_STAFF_PATH = "/api/transparency/senator-assignments/support-staff"
_PAGE_SIZE = 200          # fetch in large pages to minimise round-trips
_TIMEOUT   = 30.0

_COLUMNS = ["senator", "staff_name", "role", "contract_type", "amount_clp"]

# Spanish month name → API integer (filters[mes][$eq]).
MONTH_TO_INT: dict[str, int] = {
    "ENERO": 1, "FEBRERO": 2, "MARZO": 3,     "ABRIL":     4,
    "MAYO":  5, "JUNIO":  6, "JULIO": 7,     "AGOSTO":    8,
    "SEPTIEMBRE": 9, "OCTUBRE": 10, "NOVIEMBRE": 11, "DICIEMBRE": 12,
}


class SenadoScraperError(RuntimeError):
    """Raised when the Senate API is unreachable or returns an unusable response."""


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def _join_name(*parts: str | None) -> str:
    """Concatenate non-empty name parts into an uppercase full name."""
    return " ".join(p.strip().upper() for p in parts if p and p.strip())


def _parse_item(item: dict[str, Any]) -> dict[str, Any] | None:
    """Map one Strapi v4 data item to a flat record dict.

    Observed API shape (April 2024):
      {
        "id": 17847098,
        "attributes": {
          "appaterno": "ABARCA",  "apmaterno": "VERA",  "nombre": "MARIA ELIZABETH",
          "cargo": "APOYO TERRITORIAL",
          "calidad_juridica": "INDEFINIDO",
          "monto": 926184,
          "unidad_laboral": "SEPULVEDA ORBENES ALEJANDRA"   ← senator name
        }
      }
    """
    attrs: dict[str, Any] = item.get("attributes") or item

    staff_name    = _join_name(attrs.get("nombre"), attrs.get("appaterno"), attrs.get("apmaterno"))
    senator_name  = (attrs.get("unidad_laboral") or "").strip().upper()
    role          = (attrs.get("cargo") or "").strip().upper()
    contract_type = (attrs.get("calidad_juridica") or attrs.get("fecha_termino") or "").strip().upper()
    raw_amount    = attrs.get("monto")

    if raw_amount is None:
        return None
    try:
        amount = int(raw_amount)
    except (ValueError, TypeError):
        return None

    return {
        "senator":       senator_name,
        "staff_name":    staff_name,
        "role":          role,
        "contract_type": contract_type,
        "amount_clp":    amount,
    }


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class SenadoClient:
    """Async REST client for the Senate transparency API.

    Parameters
    ----------
    client:
        Shared :class:`httpx.AsyncClient` from the application lifespan.
        Connection pooling is handled externally; this class never closes it.
    """

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        """Authenticated GET with error normalisation."""
        url = f"{_BASE_URL}{path}"
        try:
            resp = await self._client.get(url, params=params, timeout=_TIMEOUT)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise SenadoScraperError(
                f"Senate API returned HTTP {exc.response.status_code} for '{path}'."
            ) from exc
        except httpx.HTTPError as exc:
            raise SenadoScraperError(f"Could not reach Senate API: {exc}") from exc
        return resp.json()

    async def _fetch_all_pages(
        self, path: str, base_params: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Fetch every page and return the combined item list.

        The Senate API wraps the Strapi envelope in an extra ``data`` key:
          payload["data"]["data"]  → list of items
          payload["data"]["meta"]  → pagination info
        """
        all_items: list[dict[str, Any]] = []
        page = 1
        while True:
            params = {
                **base_params,
                "pagination[page]":     str(page),
                "pagination[pageSize]": str(_PAGE_SIZE),
                "t": str(int(time.time() * 1000)),
            }
            payload    = await self._get(path, params)
            inner      = payload.get("data") or {}            # outer wrapper
            items      = inner.get("data") or []              # actual item list
            all_items.extend(items)

            meta       = (inner.get("meta") or {}).get("pagination") or {}
            page_count = meta.get("pageCount") or 1
            if page >= page_count:
                break
            page += 1
        return all_items

    # ------------------------------------------------------------------
    # Public methods — one per Senate data endpoint
    # ------------------------------------------------------------------

    async def get_support_staff_raw(
        self, year: int, month_int: int
    ) -> list[dict[str, Any]]:
        """Raw Strapi items for support staff in a given year/month."""
        return await self._fetch_all_pages(
            _SUPPORT_STAFF_PATH,
            {
                "sort":     "appaterno",
                "populate": "contratos_transparencia.informes_contratos",
                "filters[ano][$eq]": str(year),
                "filters[mes][$eq]": str(month_int),
            },
        )

    async def scrape_support_staff(
        self,
        year: int,
        month: str,
        senator: str | None = None,
        support_staff: str | None = None,
        role: str | None = None,
    ) -> pd.DataFrame:
        """Fetch and return support-staff salary data as a clean DataFrame.

        Parameters
        ----------
        year:
            Fiscal year (e.g. ``2026``).
        month:
            Month in Spanish (e.g. ``"MARZO"``). Case-insensitive.
        senator:
            Optional accent-insensitive substring filter on senator name.
        support_staff:
            Optional accent-insensitive substring filter on staff name.
        role:
            Optional accent-insensitive word filter on the staff role/cargo.

        Returns
        -------
        pd.DataFrame
            Columns: senator, staff_name, role, contract_type, amount_clp.

        Raises
        ------
        SenadoScraperError
            On network errors, unknown month, or empty result set.
        """
        month_upper = month.strip().upper()
        month_int   = MONTH_TO_INT.get(month_upper)
        if month_int is None:
            raise SenadoScraperError(
                f"Unknown month {month!r}. Valid values: {', '.join(MONTH_TO_INT)}."
            )

        raw = await self.get_support_staff_raw(year, month_int)
        if not raw:
            raise SenadoScraperError(
                f"Senate API returned no records for {month_upper} {year}."
            )

        records = [r for item in raw if (r := _parse_item(item)) is not None]

        if senator:
            records = [r for r in records if name_matches(senator, r["senator"])]

        if support_staff:
            records = [r for r in records if name_matches(support_staff, r["staff_name"])]

        if role:
            records = [r for r in records if name_matches(role, r["role"])]

        df = pd.DataFrame(records, columns=_COLUMNS)
        print(df.to_string(index=False))
        return df


# Backwards-compatible alias used by existing route imports.
SenadoScraper = SenadoClient
