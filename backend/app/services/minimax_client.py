"""Async wrapper around the MiniMax LLM, used here as an intent router.

In this first iteration the LLM does not generate prose. Instead it acts as a
deterministic *intent classifier*: given a free-text user query it returns a
structured :class:`Intent` describing which Mercado Publico tool to call and
the parameters extracted from the query.
"""

import json
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field, ValidationError

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


class Intent(BaseModel):
    """Structured routing decision returned by the LLM.

    ``tool`` is constrained to the set of queries currently supported by
    :class:`~app.services.mercado_publico.MercadoPublicoClient`, plus
    ``"unknown"`` for requests that cannot be mapped to a tool.
    """

    tool: Literal["orders_by_org_and_date", "orders_by_date", "unknown"]
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
  "tool": "<orders_by_org_and_date | orders_by_date | unknown>",
  "parameters": {
    "codigoorg": "<organism code as string, or null>",
    "fecha": "<date as ddmmyyyy, or null>"
  },
  "reasoning": "<one short sentence explaining the choice>"
}

Rules:
- Use "orders_by_org_and_date" when the user names a specific organism/entity \
AND a date.
- Use "orders_by_date" when the user gives a date but no specific organism.
- Use "unknown" when there is no date or no clear purchase-order request.
- "fecha" MUST be formatted as ddmmyyyy (example: 2024-02-05 -> "05022024"). \
Use null when no date is given.
- "codigoorg" is the organism code as a string. Use null when not given.
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
