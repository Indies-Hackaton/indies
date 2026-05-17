"""In-process CSV store for Contraloría General de la República de Chile data.

Loads two semicolon-delimited, Latin-1 encoded CSV files at startup and
exposes a synchronous ``search`` method that applies structured filters using
pandas boolean masks. Accent-insensitive matching reuses ``normalize_text``
from :mod:`app.core.text`.

Files expected at the paths passed to :class:`ContraloriaService.__init__`:
  - Municipalidades_Contraloria.csv  (municipal audits, 2020–2024, ~36 k rows)
  - No_Municipales_Contraloria.csv   (non-municipal entities, 2020–2025, ~35 k rows)

Both files share an identical 23-column schema; key columns used for filtering:

  Entidad                   — institution name
  Región                    — Chilean region
  Año informe publicado     — integer publication year
  Tipo Fiscalizacion        — e.g. AUDITORIA, INSPECCION_OBRA_PUBLICA
  Materia Fiscalizacion     — subject matter (text)
  Nombre Fiscalizacion      — audit title (text)
  Objetivo Fiscalizacion    — audit scope/objective (long text)
  Titulo Observacion        — finding title (text)
  Complejidad Observacion   — COMPLEJA | MEDIANAMENTE COMPLEJA | LEVEMENTE COMPLEJA
  Link informe publicado    — URL to the published report
  Sector                    — MUNICIPALIDADES | SERVICIOS PUBLICOS | …
"""

from typing import Any

import pandas as pd

from app.core.text import normalize_text

# Columns searched when keyword filtering is applied.
_KEYWORD_COLS = [
    "Materia Fiscalizacion",
    "Nombre Fiscalizacion",
    "Objetivo Fiscalizacion",
    "Titulo Observacion",
]

_DEFAULT_LIMIT = 50
_MAX_LIMIT = 200


class ContraloriaError(RuntimeError):
    """Raised when data files are missing or a filter parameter is invalid."""


class ContraloriaService:
    """Loads Contraloría CSV data at init and serves filtered search results.

    Parameters
    ----------
    municipalidades_path:
        Absolute or relative path to ``Municipalidades_Contraloria.csv``.
    no_municipales_path:
        Absolute or relative path to ``No_Municipales_Contraloria.csv``.
    """

    def __init__(self, municipalidades_path: str, no_municipales_path: str) -> None:
        self._muni = self._load(municipalidades_path)
        self._no_muni = self._load(no_municipales_path)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def search(
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
        """Filter Contraloría records and return (records, metadata).

        All string comparisons are accent- and case-insensitive via
        :func:`~app.core.text.normalize_text`.

        Parameters
        ----------
        entity_name:
            Substring to match against the ``Entidad`` column.
        year_min / year_max:
            Inclusive bounds on ``Año informe publicado``.
        region:
            Substring to match against ``Región``.
        tipo_fiscalizacion:
            Substring to match against ``Tipo Fiscalizacion``.
        complejidad:
            Substring to match against ``Complejidad Observacion``.
        keywords:
            Terms searched across subject/objective/finding text columns.
        source:
            ``"municipalidades"`` | ``"no_municipales"`` | ``"both"``.
        limit:
            Maximum rows returned (capped at ``_MAX_LIMIT``).
        """
        df = self._select_source(source)

        if entity_name:
            key = normalize_text(entity_name)
            mask = df["_entidad_norm"].str.contains(key, regex=False, na=False)
            df = df[mask]

        if year_min is not None:
            df = df[df["Año informe publicado"] >= year_min]

        if year_max is not None:
            df = df[df["Año informe publicado"] <= year_max]

        if region:
            key = normalize_text(region)
            mask = df["_region_norm"].str.contains(key, regex=False, na=False)
            df = df[mask]

        if tipo_fiscalizacion:
            key = normalize_text(tipo_fiscalizacion)
            mask = df["_tipo_norm"].str.contains(key, regex=False, na=False)
            df = df[mask]

        if complejidad:
            key = normalize_text(complejidad)
            mask = df["_complejidad_norm"].str.contains(key, regex=False, na=False)
            df = df[mask]

        if keywords:
            terms = [normalize_text(k) for k in keywords if k]
            if terms:
                combined = df[[c for c in _KEYWORD_COLS if c in df.columns]].fillna("").agg(
                    lambda row: " ".join(normalize_text(str(v)) for v in row), axis=1
                )
                keyword_mask = combined.apply(
                    lambda text: any(t in text for t in terms)
                )
                df = df[keyword_mask]

        total_before_limit = len(df)
        effective_limit = min(int(limit) if limit else _DEFAULT_LIMIT, _MAX_LIMIT)
        df = df.head(effective_limit)

        # Drop internal normalisation columns before returning.
        output_cols = [c for c in df.columns if not c.startswith("_")]
        records = df[output_cols].to_dict(orient="records")

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

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load(path: str) -> pd.DataFrame:
        try:
            df = pd.read_csv(
                path,
                sep=";",
                encoding="latin-1",
                dtype=str,
                low_memory=False,
            )
        except FileNotFoundError:
            raise ContraloriaError(f"Contraloría data file not found: {path!r}")

        # Coerce year column to nullable integer.
        year_col = "Año informe publicado"
        if year_col in df.columns:
            df[year_col] = pd.to_numeric(df[year_col], errors="coerce")

        # Pre-compute normalised columns for fast filtering.
        for raw_col, norm_col in (
            ("Entidad", "_entidad_norm"),
            ("Región", "_region_norm"),
            ("Tipo Fiscalizacion", "_tipo_norm"),
            ("Complejidad Observacion", "_complejidad_norm"),
        ):
            if raw_col in df.columns:
                df[norm_col] = df[raw_col].fillna("").apply(normalize_text)

        return df

    def _select_source(self, source: str) -> pd.DataFrame:
        if source == "municipalidades":
            return self._muni.copy()
        if source == "no_municipales":
            return self._no_muni.copy()
        if source == "both":
            return pd.concat([self._muni, self._no_muni], ignore_index=True)
        raise ContraloriaError(
            f"Invalid source {source!r}. Must be 'municipalidades', 'no_municipales', or 'both'."
        )
