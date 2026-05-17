"""Cámara de Diputados transparency scraper.

Fetches deputy expense/activity data from the public ASP.NET pages at
https://www.camara.cl/diputados/detalle/{categoria}.aspx?prmId={codigo}

No authentication is required. The site serves server-rendered HTML; data is
extracted with BeautifulSoup. Deputy name → code resolution uses the
``id_diputados`` table in the shared Neon PostgreSQL database.

Supported categories:
  gastos_operacionales      — monthly operational expenses
  asesoria_externa          — external consulting fees
  pasajes_aereos            — air tickets
  instancias_internacionales — international trips/instances
  personal_apoyo            — support staff and salaries
  audiencias                — public audiences/meetings
"""

import re
from typing import Any

import asyncpg
from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession

from app.core.text import normalize_text

_BASE_URL = "https://www.camara.cl/diputados/detalle/{categoria}.aspx"

_CATEGORIAS: dict[str, str] = {
    "gastos_operacionales":       "gastosoperacionales",
    "asesoria_externa":           "asesoriaexterna",
    "pasajes_aereos":             "pasajesaereos",
    "instancias_internacionales": "instanciainternacionales",
    "personal_apoyo":             "personaldepoyo",
    "audiencias":                 "audiencia",
}

_TIMEOUT = 20.0

# Phrases the site uses when data is not yet published.
_NO_DATA_PATTERNS = [
    re.compile(r"no han sido publicados", re.I),
    re.compile(r"no existen datos", re.I),
    re.compile(r"sin información", re.I),
    re.compile(r"no se encontraron", re.I),
]


class CamaraError(RuntimeError):
    """Raised on network errors or unrecognised category names."""


class CamaraService:
    """Async client for Cámara de Diputados transparency pages.

    Uses ``curl-cffi`` with Chrome impersonation to bypass Cloudflare TLS
    fingerprint checks that block standard Python HTTP clients.

    Parameters
    ----------
    pool:
        Asyncpg connection pool pointing to the Neon database that contains
        the ``id_diputados`` table.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    async def resolve_diputado(self, name: str) -> list[dict[str, Any]]:
        """Return deputies whose name contains *name* (accent-insensitive).

        Queries the ``id_diputados`` table in Neon using ``unaccent`` + ILIKE.
        Returns a list of ``{"codigo": int, "nombre": str}`` dicts.
        """
        pattern = f"%{normalize_text(name)}%"
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT codigo, nombre FROM id_diputados "
                "WHERE UPPER(unaccent(nombre)) ILIKE UPPER(unaccent($1)) "
                "ORDER BY nombre",
                pattern,
            )
        return [{"codigo": r["codigo"], "nombre": r["nombre"]} for r in rows]

    async def fetch_categoria(
        self, codigo: int, categoria: str
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Scrape one transparency page for deputy *codigo*.

        Parameters
        ----------
        codigo:
            Numeric deputy ID (``prmId`` in the URL).
        categoria:
            One of the keys in :data:`_CATEGORIAS`.

        Returns
        -------
        (records, metadata)
            *records* is a list of row dicts (empty when no data is published).
            *metadata* always includes ``categoria``, ``codigo``, and
            ``no_data`` (bool). When ``no_data`` is True, ``no_data_reason``
            contains the site's explanation.
        """
        slug = _CATEGORIAS.get(categoria)
        if slug is None:
            raise CamaraError(
                f"Unknown category {categoria!r}. "
                f"Valid values: {', '.join(_CATEGORIAS)}"
            )

        url = _BASE_URL.format(categoria=slug)
        try:
            async with AsyncSession(impersonate="chrome") as session:
                resp = await session.get(
                    url,
                    params={"prmId": str(codigo)},
                    timeout=_TIMEOUT,
                )
            if resp.status_code != 200:
                raise CamaraError(
                    f"Cámara site returned HTTP {resp.status_code} "
                    f"for {categoria} / deputy {codigo}."
                )
        except CamaraError:
            raise
        except Exception as exc:
            raise CamaraError(
                f"Could not reach Cámara de Diputados: {exc}"
            ) from exc

        records, no_data_reason = _parse_page(resp.text, categoria)

        metadata: dict[str, Any] = {
            "categoria": categoria,
            "codigo": codigo,
            "no_data": no_data_reason is not None,
        }
        if no_data_reason:
            metadata["no_data_reason"] = no_data_reason
        else:
            metadata["record_count"] = len(records)

        return records, metadata


# ---------------------------------------------------------------------------
# HTML parsing helpers
# ---------------------------------------------------------------------------

def _parse_page(
    html: str, categoria: str
) -> tuple[list[dict[str, Any]], str | None]:
    """Parse the deputy transparency page HTML.

    Returns ``(records, no_data_reason)``.  When the site reports that data
    is not yet published, *records* is empty and *no_data_reason* is a string
    explaining why.  Otherwise *no_data_reason* is ``None``.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Check for "no data published" messages anywhere in the page text.
    page_text = soup.get_text(" ", strip=True)
    for pattern in _NO_DATA_PATTERNS:
        match = pattern.search(page_text)
        if match:
            reason = _extract_no_data_sentence(page_text, match.start())
            return [], reason

    # Try to find a data table.
    table = _find_data_table(soup)
    if table is None:
        return [], f"No data table found on the {categoria} page."

    headers = [th.get_text(" ", strip=True) for th in table.find_all("th")]
    if not headers:
        # Some pages use the first <tr> as a header row with <td> cells.
        first_row = table.find("tr")
        if first_row:
            headers = [td.get_text(" ", strip=True) for td in first_row.find_all("td")]

    records: list[dict[str, Any]] = []
    tbody = table.find("tbody") or table
    for tr in tbody.find_all("tr"):
        cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        if not cells or len(cells) != len(headers):
            continue
        records.append(dict(zip(headers, cells)))

    if not records:
        return [], "The page loaded but contained no data rows."

    return records, None


def _find_data_table(soup: BeautifulSoup):
    """Heuristically locate the main data table, ignoring nav/layout tables."""
    candidates = soup.find_all("table")
    for table in candidates:
        # Skip tiny tables (navigation, layout).
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue
        # Prefer tables with <th> header cells.
        if table.find("th"):
            return table
    # Fall back to the largest table by row count.
    if candidates:
        return max(candidates, key=lambda t: len(t.find_all("tr")))
    return None


def _extract_no_data_sentence(text: str, match_pos: int) -> str:
    """Return the sentence containing the no-data match for user display."""
    start = text.rfind(".", 0, match_pos)
    start = start + 1 if start != -1 else max(0, match_pos - 120)
    end = text.find(".", match_pos)
    end = end + 1 if end != -1 else match_pos + 120
    return text[start:end].strip()
