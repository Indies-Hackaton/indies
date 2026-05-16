"""Async wrapper around the MiniMax LLM, used here as an intent router.

In this first iteration the LLM does not generate prose. Instead it acts as a
deterministic *intent classifier*: given a free-text user query it returns a
structured :class:`Intent` describing which Mercado Publico tool to call and
the parameters extracted from the query.
"""

import json
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator

from app.core.config import Settings


class MiniMaxError(RuntimeError):
    """Raised when MiniMax is unreachable or returns an unusable response."""


class IntentParameters(BaseModel):
    """Parameters extracted from the user's natural-language query."""

    # Code of the public organism, when the user mentions a specific entity.
    codigoorg: str | None = Field(
        default=None, description="Organism code (CodigoOrganismo), if mentioned."
    )
    # Date in ddmmyyyy format, as required by Mercado Publico.
    fecha: str | None = Field(
        default=None, description="Date in ddmmyyyy format, if mentioned."
    )
    # Tender code / Codigo de Licitacion (for example 1509-5-L114).
    codigo: str | None = Field(
        default=None, description="Tender code, if mentioned."
    )
    # Public tender status, either a Spanish name or Mercado Publico code.
    estado: str | None = Field(
        default=None, description="Tender status name/code, if mentioned."
    )
    # Supplier code / CodigoProveedor.
    codigo_proveedor: str | None = Field(
        default=None, description="Supplier code, if mentioned."
    )
    # Public organism code / CodigoOrganismo. Kept alongside legacy codigoorg.
    codigo_organismo: str | None = Field(
        default=None, description="Public organism code, if mentioned."
    )
    # Natural-language organism name that must be resolved via BuscarComprador.
    organism_name: str | None = Field(
        default=None, description="Public organism name, if mentioned."
    )
    # Product/service terms for semantic filtering.
    keywords: list[str] = Field(
        default_factory=list,
        description="Semantic product/service keywords extracted from the query.",
    )
    # Inclusive date range bounds in ddmmyyyy format.
    start_date: str | None = Field(
        default=None, description="Date range start in ddmmyyyy format."
    )
    end_date: str | None = Field(
        default=None, description="Date range end in ddmmyyyy format."
    )
    # Whether the user asked for purchase orders and/or tenders.
    include_orders: bool | None = Field(
        default=None, description="True when purchase orders should be queried."
    )
    include_tenders: bool | None = Field(
        default=None, description="True when tenders should be queried."
    )

    @field_validator("keywords", mode="before")
    @classmethod
    def _normalize_keywords(cls, value: Any) -> list[str]:
        """Treat LLM nulls as an empty keyword list for simple queries."""
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            return [str(item) for item in value if item not in (None, "")]
        return [str(value)]

    @field_validator(
        "codigoorg",
        "fecha",
        "codigo",
        "estado",
        "codigo_proveedor",
        "codigo_organismo",
        "organism_name",
        "start_date",
        "end_date",
        mode="before",
    )
    @classmethod
    def _normalize_optional_string(cls, value: Any) -> str | None:
        """Coerce simple scalar LLM values into the string fields we route with."""
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class Intent(BaseModel):
    """Structured routing decision returned by the LLM.

    ``tool`` is constrained to the set of queries supported by
    :class:`~app.services.mercado_publico.MercadoPublicoClient` and the route's
    higher-level semantic search workflow, plus ``"unknown"`` for requests that
    cannot be mapped to a tool.
    """

    tool: Literal[
        "orders_by_org_and_date",
        "orders_by_date",
        "public_organism_lookup",
        "tender_by_code",
        "tenders_current_day",
        "tenders_by_date",
        "tenders_by_status_and_date",
        "tenders_by_supplier_and_date",
        "tenders_by_org_and_date",
        "semantic_org_date_range_search",
        "unknown",
    ]
    parameters: IntentParameters = Field(default_factory=IntentParameters)
    reasoning: str | None = Field(
        default=None, description="Short rationale produced by the LLM."
    )


# System prompt that constrains the model to emit a single JSON object
# matching the :class:`Intent` schema.
_SYSTEM_PROMPT = """\
You are an intent router for an anti-corruption audit assistant that queries \
the Chilean public procurement API "Mercado Publico".

Your ONLY job is to read the user's request and reply with a SINGLE JSON \
object - no prose, no markdown fences - using exactly this shape:

{
  "tool": "<orders_by_org_and_date | orders_by_date | public_organism_lookup | tender_by_code | tenders_current_day | tenders_by_date | tenders_by_status_and_date | tenders_by_supplier_and_date | tenders_by_org_and_date | semantic_org_date_range_search | unknown>",
  "parameters": {
    "codigoorg": "<organism code as string, or null>",
    "fecha": "<single date as ddmmyyyy, or null>",
    "codigo": "<tender code/Codigo de Licitacion, or null>",
    "estado": "<Publicada | Cerrada | Desierta | Adjudicada | Revocada | Suspendida | Todos | code, or null>",
    "codigo_proveedor": "<supplier code/CodigoProveedor, or null>",
    "codigo_organismo": "<public organism code/CodigoOrganismo, or null>",
    "organism_name": "<public organism name to resolve, or null>",
    "keywords": ["<semantic keyword>", "..."],
    "start_date": "<date range start as ddmmyyyy, or null>",
    "end_date": "<date range end as ddmmyyyy, or null>",
    "include_orders": <true | false | null>,
    "include_tenders": <true | false | null>
  },
  "reasoning": "<one short sentence explaining the choice>"
}

Rules:
- Use "orders_by_org_and_date" when the user names a specific organism/entity \
code or organism name AND a single date for purchase orders.
- Use "orders_by_date" when the user gives a date but no specific organism.
- Use "public_organism_lookup" when the user asks to find, verify, resolve, or \
list a public buyer/organism by name.
- Use "tender_by_code" when a Codigo de Licitacion is provided (example: \
1509-5-L114).
- Use "tenders_current_day" when the user asks for today's/current-day tenders \
with no date.
- Use "tenders_by_date" when the user asks for all tenders on a single date.
- Use "tenders_by_status_and_date" when the user asks for tenders on a single \
date filtered by Estado.
- Use "tenders_by_supplier_and_date" when the user asks for tenders on a single \
date filtered by CodigoProveedor.
- Use "tenders_by_org_and_date" when the user asks for tenders on a single date \
filtered by CodigoOrganismo or a named public organism.
- Use "semantic_org_date_range_search" when the user gives a named institution, \
a date range, and product/service/category keywords that require filtering \
(for example "computational systems" / "sistemas computacionales"). This tool \
must include "organism_name", "keywords", "start_date", and "end_date". Set \
"include_orders" and "include_tenders" from the words in the user request; if \
the request says "purchase orders or tenders", set both to true.
- Use "unknown" only when the request cannot be mapped to any supported Mercado \
Publico lookup.
- "fecha" MUST be formatted as ddmmyyyy (example: 2024-02-05 -> "05022024"). \
Use null when no date is given.
- "start_date" and "end_date" MUST also use ddmmyyyy.
- "codigoorg" and "codigo_organismo" are organism codes as strings. Use null \
when not given.
- For named organisms such as "MUNICIPALIDAD DE ALGARROBO", do NOT invent a \
CodigoOrganismo. Put the name in "organism_name" so the backend can resolve it \
with BuscarComprador and handle municipality/corporation ambiguity.
- Preserve important Spanish institution names and keywords exactly when useful.
- Reply with the JSON object and nothing else.
"""


class MiniMaxClient:
    """Async client that turns user queries into structured :class:`Intent`s.

    Parameters
    ----------
    settings:
        Application settings holding the MiniMax credentials and model name.
    client:
        A shared :class:`httpx.AsyncClient` used for connection pooling.
    """

    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        self._client = client
        self._base_url = settings.MINIMAX_BASE_URL.rstrip("/")
        self._model = settings.MINIMAX_MODEL
        self._headers = {
            "Authorization": f"Bearer {settings.MINIMAX_API_KEY}",
            "Content-Type": "application/json",
        }

    async def classify_intent(self, message: str) -> Intent:
        """Classify a free-text query into a structured :class:`Intent`.

        Raises
        ------
        MiniMaxError
            If MiniMax is unreachable, replies with an error status, or returns
            content that does not match the expected JSON schema.
        """
        content = await self._chat(
            [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": message},
            ]
        )
        raw = self._extract_json(content)
        try:
            return Intent.model_validate(raw)
        except ValidationError as exc:
            raise MiniMaxError(
                f"LLM returned JSON that does not match the Intent schema: {exc}"
            ) from exc

    async def _chat(self, messages: list[dict[str, str]]) -> str:
        """Send a chat-completion request and return the assistant's content.

        Raises
        ------
        MiniMaxError
            On transport errors, error status codes, or malformed responses.
        """
        url = f"{self._base_url}/text/chatcompletion_v2"
        body: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            # Low temperature keeps the router deterministic.
            "temperature": 0.1,
        }

        try:
            response = await self._client.post(
                url, json=body, headers=self._headers
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise MiniMaxError(
                f"MiniMax returned HTTP {exc.response.status_code}."
            ) from exc
        except httpx.HTTPError as exc:
            raise MiniMaxError(f"Could not reach MiniMax: {exc}") from exc

        payload = response.json()
        try:
            # MiniMax exposes an OpenAI-compatible chat-completion response.
            return payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise MiniMaxError(
                f"Unexpected MiniMax response shape: {payload}"
            ) from exc

    @staticmethod
    def _extract_json(content: str) -> dict[str, Any]:
        """Extract the first JSON object from an LLM text response.

        The model is instructed to return raw JSON, but we defensively strip
        optional markdown code fences and isolate the outermost ``{...}`` block.

        Raises
        ------
        MiniMaxError
            If no valid JSON object can be recovered from ``content``.
        """
        text = content.strip()

        # Drop a leading ```json / ``` fence if the model added one.
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
            text = text.strip()

        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise MiniMaxError(
                f"No JSON object found in LLM output: {content!r}"
            )

        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise MiniMaxError(
                f"LLM output was not valid JSON: {exc}"
            ) from exc
