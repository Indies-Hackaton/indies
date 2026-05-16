"""Small text utilities shared across services.

Spanish institution and product names are full of accents and inconsistent
casing. Comparing them reliably requires a normalisation step, centralised here
so the organism resolver and the audit pipeline behave identically.
"""

import unicodedata


def normalize_text(value: str) -> str:
    """Return an upper-cased, accent-stripped, whitespace-collapsed string.

    Example: ``"Municipalidad de Ñuñoa "`` -> ``"MUNICIPALIDAD DE NUNOA"``.
    """
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    return " ".join(without_accents.upper().split())


def name_matches(query: str, full_name: str) -> bool:
    """Return True when every word in *query* appears in *full_name*.

    Order-insensitive and accent/case-insensitive. Designed for names stored
    in ``APELLIDO MATERNO APELLIDO PATERNO NOMBRE`` order where a query like
    ``"Pedro Araya"`` must match ``"ARAYA GUERRERO PEDRO"``.

    Examples::

        name_matches("Pedro Araya", "ARAYA GUERRERO PEDRO")  # True
        name_matches("Pedro Araya", "CELIS ARAYA RICARDO")   # False (no PEDRO)
        name_matches("Araya",       "ARAYA GUERRERO PEDRO")  # True
        name_matches("Araya",       "CELIS ARAYA RICARDO")   # True
    """
    query_words = set(normalize_text(query).split())
    name_words  = set(normalize_text(full_name).split())
    return query_words.issubset(name_words)
