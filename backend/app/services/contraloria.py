"""PostgreSQL client for Contraloría General de la República de Chile data.

Connects to a Neon PostgreSQL database containing two tables loaded from the
Contraloría CSV exports:

  municipalidades     — municipal audits, 2020–2024
  no_municipalidades  — non-municipal entity audits, 2020–2025

Both tables share an identical schema (23 snake_case columns). Filtering is
done with parameterised SQL — no raw user input is interpolated.

Accent-insensitive matching is handled by normalising the search term in
Python (via :func:`~app.core.text.normalize_text`) and using PostgreSQL
``ILIKE`` against the stored values, which are already uppercase in the source
data.
"""

from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import asyncpg

from app.core.text import normalize_text

_DEFAULT_LIMIT = 50
_MAX_LIMIT = 200

_KEYWORD_COLS = [
    "materia_fiscalizacion",
    "nombre_fiscalizacion",
    "objetivo_fiscalizacion",
    "titulo_observacion",
]


class ContraloriaError(RuntimeError):
    """Raised when a DB call fails or a parameter is invalid."""


class ContraloriaService:
    """Async PostgreSQL client for Contraloría audit data.

    Instantiate via :meth:`create`; the constructor is internal.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    @classmethod
    async def create(cls, database_url: str) -> "ContraloriaService":
        """Open a connection pool and return a ready service instance."""
        database_url = normalize_asyncpg_dsn(database_url)
        pool = await asyncpg.create_pool(
            database_url,
            min_size=1,
            max_size=5,
            ssl="require",
        )
        return cls(pool)

    async def close(self) -> None:
        """Close the connection pool (called during app shutdown)."""
        await self._pool.close()

    async def search(
        self,
        *,
        entity_name: str | None = None,
        year_min: int | None = None,
        year_max: int | None = None,
        region: str | None = None,
        tipo_fiscalizacion: str | None = None,
        complejidad: str | None = None,
        keywords: list[str] | None = None,
        source: str = "both",
        limit: int = _DEFAULT_LIMIT,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Query Contraloría records with structured filters.

        Returns ``(records, metadata)`` where *records* is a list of dicts and
        *metadata* contains ``total_before_limit``, ``returned``, ``limit``,
        ``source``, and ``filters_applied``.
        """
        tables = _resolve_tables(source)
        effective_limit = min(int(limit) if limit else _DEFAULT_LIMIT, _MAX_LIMIT)

        all_records: list[dict[str, Any]] = []
        total_before_limit = 0

        async with self._pool.acquire() as conn:
            for table in tables:
                where, params = _build_where(
                    entity_name=entity_name,
                    year_min=year_min,
                    year_max=year_max,
                    region=region,
                    tipo_fiscalizacion=tipo_fiscalizacion,
                    complejidad=complejidad,
                    keywords=keywords or [],
                )

                count_sql = f"SELECT COUNT(*) FROM {table}"
                if where:
                    count_sql += f" WHERE {where}"
                count_row = await conn.fetchrow(count_sql, *params)
                total_before_limit += count_row[0]

                fetch_sql = f"SELECT * FROM {table}"
                if where:
                    fetch_sql += f" WHERE {where}"
                fetch_sql += f" LIMIT ${len(params) + 1}"
                rows = await conn.fetch(fetch_sql, *params, effective_limit)
                all_records.extend(dict(row) for row in rows)

        # When querying both tables honour the overall limit across both.
        records = all_records[:effective_limit]

        metadata: dict[str, Any] = {
            "total_before_limit": total_before_limit,
            "returned": len(records),
            "limit": effective_limit,
            "source": source,
            "filters_applied": {
                k: v for k, v in {
                    "entity_name": entity_name,
                    "year_min": year_min,
                    "year_max": year_max,
                    "region": region,
                    "tipo_fiscalizacion": tipo_fiscalizacion,
                    "complejidad": complejidad,
                    "keywords": keywords or [],
                }.items() if v not in (None, [], "")
            },
        }
        return records, metadata


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_tables(source: str) -> list[str]:
    if source == "municipalidades":
        return ["municipalidades"]
    if source == "no_municipales":
        return ["no_municipalidades"]
    if source == "both":
        return ["municipalidades", "no_municipalidades"]
    raise ContraloriaError(
        f"Invalid source {source!r}. Must be 'municipalidades', 'no_municipales', or 'both'."
    )


def _build_where(
    *,
    entity_name: str | None,
    year_min: int | None,
    year_max: int | None,
    region: str | None,
    tipo_fiscalizacion: str | None,
    complejidad: str | None,
    keywords: list[str],
) -> tuple[str, list[Any]]:
    """Return a SQL WHERE clause (no leading WHERE) and its parameter list."""
    clauses: list[str] = []
    params: list[Any] = []

    def _add(col: str, value: str) -> None:
        params.append(f"%{normalize_text(value)}%")
        clauses.append(f"UPPER(unaccent({col})) ILIKE UPPER(unaccent(${len(params)}))")

    if entity_name:
        _add("entidad", entity_name)
    if region:
        _add("region", region)
    if tipo_fiscalizacion:
        _add("tipo_fiscalizacion", tipo_fiscalizacion)
    if complejidad:
        _add("complejidad_observacion", complejidad)

    if year_min is not None:
        params.append(year_min)
        clauses.append(f"anio_informe >= ${len(params)}")
    if year_max is not None:
        params.append(year_max)
        clauses.append(f"anio_informe <= ${len(params)}")

    if keywords:
        terms = [normalize_text(k) for k in keywords if k]
        for term in terms:
            keyword_parts = []
            for col in _KEYWORD_COLS:
                params.append(f"%{term}%")
                keyword_parts.append(f"UPPER(unaccent({col})) ILIKE UPPER(unaccent(${len(params)}))")
            clauses.append(f"({' OR '.join(keyword_parts)})")

    return (" AND ".join(clauses), params)


class UnavailableContraloriaService:
    """Contraloria placeholder used when local dev has no Postgres data URL."""

    def __init__(self, reason: str) -> None:
        self.reason = reason

    async def close(self) -> None:
        """Match the real service shutdown API."""
        return None

    async def search(self, **_: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Report that the backed data source is not configured."""
        raise ContraloriaError(f"Contraloria service unavailable: {self.reason}")


def normalize_asyncpg_dsn(database_url: str) -> str:
    """Normalize PostgreSQL URLs before passing them directly to asyncpg."""
    if database_url.startswith("postgresql+asyncpg://"):
        database_url = database_url.replace("postgresql+asyncpg://", "postgresql://", 1)

    if not database_url.startswith(("postgresql://", "postgres://")):
        raise ContraloriaError(
            "Contraloria requires a PostgreSQL DSN; set CONTRALORIA_DATABASE_URL "
            "or use a PostgreSQL DATABASE_URL."
        )

    parts = urlsplit(database_url)
    query_params = dict(parse_qsl(parts.query, keep_blank_values=True))
    query_params.pop("channel_binding", None)
    query_params.pop("ssl", None)
    query_params.pop("sslmode", None)

    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query_params),
            parts.fragment,
        )
    )
