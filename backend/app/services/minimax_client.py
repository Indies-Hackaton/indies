"""Async wrapper around the MiniMax LLM, used here as an intent router.

In this first iteration the LLM does not generate prose. Instead it acts as a
deterministic *intent classifier*: given a free-text user query it returns a
structured :class:`Intent` describing which Mercado Publico tool to call and
the parameters extracted from the query.
"""

import json
import re
import unicodedata
from calendar import monthrange
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator

from app.core.config import Settings
from app.core.text import detect_text_format


class MiniMaxError(RuntimeError):
    """Raised when MiniMax is unreachable or returns an unusable response."""


class IntentParameters(BaseModel):
    """Parameters extracted from the user's natural-language query."""

    # --- Mercado Publico fields ---
    codigoorg: str | None = Field(
        default=None, description="Organism code (CodigoOrganismo), if mentioned."
    )
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
You are an intent router for a Chilean government transparency and \
anti-corruption audit assistant.

You have access to two data sources:
1. Mercado Publico (public procurement API).
2. Senado de Chile (Senate support-staff salary transparency portal).

Your ONLY job is to read the user's request and reply with a SINGLE JSON \
object — no prose, no markdown fences — using exactly this shape:

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


# ---------------------------------------------------------------------------
# Planner prompt
# ---------------------------------------------------------------------------
_PLANNER_PROMPT = """\
You are the Planner agent for a Chilean government transparency and \
anti-corruption audit assistant.

Your ONLY job: read the user's question and reply with a SINGLE JSON object \
that lists every API call needed to answer it. No prose, no markdown.

=== OUTPUT SHAPE ===
{
  "tasks": [
    {
      "id": "t1",
      "tool": "<tool_name>",
      "description": "<one-line description>",
      "parameters": { <tool-specific keys> }
    }
  ],
  "reasoning": "<one sentence explaining the plan>"
}

=== AVAILABLE TOOLS ===

--- Senate (Senado de Chile) ---
senado_support_staff
  year        : int   (e.g. 2026)
  month_es    : str   UPPERCASE Spanish month (ENERO…DICIEMBRE)
  senator_name: str?  partial senator name (optional)
  staff_name  : str?  partial staff name (optional)

--- Mercado Público ---
mp_orders_by_org_and_date
  codigoorg: str? OR organism_name: str?, fecha: str (ddmmyyyy)
  Use for purchase orders on one date when the request includes either a public
  organism code or a named organism. If the user gives a name like
  "Municipalidad de Algarrobo", use organism_name; do not fall back to
  mp_orders_by_date.

mp_orders_by_date
  fecha: str (ddmmyyyy)

mp_tender_by_codigo
  codigo: str  (e.g. "1509-5-L114")

mp_tenders_today
  (no parameters)

mp_tenders_by_date
  fecha: str (ddmmyyyy)

mp_tenders_by_status
  fecha: str (ddmmyyyy), estado: str \
(Publicada|Cerrada|Desierta|Adjudicada|Revocada|Suspendida)

mp_tenders_by_supplier
  fecha: str (ddmmyyyy), CodigoProveedor: str

mp_tenders_by_org
  fecha: str (ddmmyyyy), codigo_organismo: str? OR organism_name: str?
  Use for tenders on one date when the request includes either a public
  organism code or a named organism.

mp_search_buyers
  (no parameters — returns the full organism directory)

mp_resolve_organism
  organism_name: str  (natural-language name; resolves to numeric code)

mp_semantic_range
  organism_name: str   (natural-language name, resolved automatically)
  start_date   : str   (ddmmyyyy)
  end_date     : str   (ddmmyyyy)
  keywords     : list  (product/service keywords for filtering; [] for a broad
                        organism/date search with no product category)
  include_tenders: bool (default true)
  include_orders : bool (default false)

--- Contraloría General de la República ---
contraloria_search
  entity_name        : str?  partial name of the institution (e.g. "ALGARROBO")
  year_min           : int?  earliest publication year (e.g. 2021)
  year_max           : int?  latest publication year  (e.g. 2023)
  region             : str?  Chilean region name (partial, e.g. "VALPARAISO")
  tipo_fiscalizacion : str?  audit type (AUDITORIA | INSPECCION_OBRA_PUBLICA | ...)
  complejidad        : str?  COMPLEJA | MEDIANAMENTE COMPLEJA | LEVEMENTE COMPLEJA
  keywords           : list  search terms across subject/objective/finding text
  source             : str   "municipalidades" | "no_municipales" | "both" (default "both")
  limit              : int   max rows to return (default 50, max 200)

=== RULES ===
- Emit as many tasks as needed; run independent ones in parallel.
- Use senado_support_staff for anything about senator staff, salaries, \
personal de apoyo.
- Use mp_semantic_range when the user asks for purchase orders and/or tenders \
for a named institution over a date range. Product/service keywords are \
optional; use keywords: [] for broad searches such as suspicious/doubtful \
purchase or tender reviews.
- Use contraloria_search when the user asks about Contraloría findings, \
audits, observaciones, fiscalizaciones, or irregularidades involving any \
public institution or municipality. Set source="municipalidades" for \
municipality questions, "no_municipales" for other public entities, "both" \
when unsure.
- Use mp_semantic_range when the user gives an institution name, a date \
range, and product/service keywords (Mercado Público procurement data).
- Use mp_orders_by_org_and_date when the user asks for purchase orders for a \
named public organism and a single date; pass the name as organism_name if no \
numeric code is provided.
- Use mp_tenders_by_org when the user asks for tenders for a named public \
organism and a single date; pass the name as organism_name if no numeric code \
is provided.
- Use mp_orders_by_date only when the request has a purchase-order date and no \
specific organism name/code.
- Use mp_tenders_by_date only when the request has a tender date and no \
specific organism name/code.
- Use mp_resolve_organism only when the user wants to find or verify a \
specific organism by name (returns code + candidates). Do not stop at \
mp_resolve_organism when the user also asks for purchases, purchase orders, \
compras, tenders, or licitaciones; plan the data retrieval too.
- Use mp_search_buyers only when the user explicitly wants to browse or list all public organisms.
- Dates must be ddmmyyyy (e.g. 5 Feb 2024 → "05022024").
- month_es must be full Spanish name in UPPERCASE.
- Reply with the JSON object and nothing else.
"""

# ---------------------------------------------------------------------------
# Synthesizer prompt
# ---------------------------------------------------------------------------
_SYNTHESIZER_PROMPT = """\
You are the Synthesis agent for a Chilean government transparency and \
anti-corruption audit assistant.

You receive the user's original question and the results of every API \
call that was made to answer it. Your job is to write a clear, concise \
response in the same language the user asked in.

Guidelines:
- Summarise the key findings from ALL results.
- Highlight relevant numbers (record counts, total amounts, names).
- If a task failed, acknowledge it briefly.
- Do NOT repeat raw JSON or full record lists.
- Be concise but informative; 3-8 sentences is usually right.
- Respond in the same language as the user's question.
"""

# ---------------------------------------------------------------------------
# Conversational chat prompts
# ---------------------------------------------------------------------------
_TITLE_PROMPT = """\
You generate short titles for audit conversations.

Rules:
- Use the same language as the user's first message.
- Describe the topic of the user's request, not the outcome or your response.
- If the request is unclear, use a generic descriptive title about the request.
- Never mention your limitations, missing data, errors, or inability to answer.
- Return plain text only — no markdown of any kind.
- Do NOT use #, ##, *, **, _, __, `, or any other markdown syntax anywhere.
- Maximum 8 words.
- No quotes or punctuation at the end.
- Output the title and nothing else.
"""

_CHAT_RESPONSE_PROMPT = """\
You are the user-facing conversational agent for Indies, a Chilean government \
transparency and anti-corruption audit assistant.

You receive:
1. Recent conversation history.
2. The user's current message.
3. The Planner agent's API plan.
4. The tool/API results already executed by the backend.

Rules:
- Answer in natural language, in the same language as the user.
- Use the API results as evidence; do not invent data.
- Mention useful counts, names, totals, failed tool calls, and ambiguity.
- If there are no records, say that clearly and suggest a narrower follow-up.
- Do not expose raw JSON unless the user explicitly asks.
- Do not claim you can call APIs yourself; the backend has already done it.
- Never output tool-call syntax, pseudo-code, method names, or MCP/tool blocks.
- Never write [TOOL_CALL], [/TOOL_CALL], "tool =>", "method =>", or API
  command snippets.
- The response is final user-facing analysis of already executed results. Do
  not say "buscaré", "consultaré", or "voy a llamar"; explain what was
  retrieved or what was not retrieved.
- If the provided results only resolved an organism and did not retrieve the
  purchases/tenders the user asked for, say that the data was not retrieved
  yet instead of pretending to make more calls.
- For questions about suspicious, doubtful, or irregular purchases, do not
  assert wrongdoing from procurement listings alone. Identify records worth
  reviewing, explain the observable signals, and state the limitation.
- Keep the answer concise: 3-8 sentences unless the user asks for detail.

Citation rules:
- Each result in the data has a "citation_index" field (1, 2, 3...).
- When you mention a specific finding backed by data from a result, add [N] \
immediately after the claim, where N is that result's citation_index.
- Example: "Se encontraron 70 órdenes de compra [1] en el período analizado."
- If a claim draws from multiple results, use multiple markers: [1][2].
- If a result returned 0 records and you mention it, still cite it: \
"No se encontraron licitaciones [2] en ese período."
- Only add markers to claims directly backed by a specific result. \
Do not add [N] to general observations or conclusions.
- The markers must appear exactly as [N] — square brackets, number, nothing else.
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
        self._chat_model = settings.minimax_chat_model
        self._headers = {
            "Authorization": f"Bearer {settings.MINIMAX_API_KEY}",
            "Content-Type": "application/json",
        }

    @property
    def planner_model(self) -> str:
        """Model name used for planning/API-routing calls."""
        return self._model

    @property
    def chat_model(self) -> str:
        """Model name used for user-facing conversational calls."""
        return self._chat_model

    # ------------------------------------------------------------------
    # Multi-agent pipeline methods
    # ------------------------------------------------------------------

    async def create_plan(self, message: str) -> "Plan":
        """Ask the LLM to produce a structured task list for *message*."""
        plan, _request_json, _response_json = await self.create_plan_with_trace(
            message
        )
        return plan

    async def create_plan_with_trace(
        self,
        message: str,
        history: list[dict[str, str]] | None = None,
    ) -> tuple["Plan", dict[str, Any], dict[str, Any]]:
        """Produce a plan and return the serialisable LLM request/response."""
        from app.services.models import Plan  # local import avoids cycles

        messages = self._planner_messages(message, history)
        request_json = {
            "model": self._model,
            "temperature": 0.1,
            "messages": messages,
        }
        content = await self._chat(messages, model=self._model, temperature=0.1)
        raw = self._extract_json(content)
        try:
            plan = Plan.model_validate(raw)
        except ValidationError as exc:
            raise MiniMaxError(
                f"Planner returned JSON that does not match the Plan schema: {exc}"
            ) from exc
        repaired_plan = self._repair_plan_from_message(plan, message)
        response_json: dict[str, Any] = {
            "content": content,
            "parsed": repaired_plan.model_dump(),
        }
        if repaired_plan.model_dump() != plan.model_dump():
            response_json["raw_parsed"] = raw
            response_json["repaired"] = True
        return repaired_plan, request_json, response_json

    async def synthesize(self, message: str, results: list) -> str:
        """Ask the LLM to produce a human-readable summary of *results*."""
        results_text = json.dumps(
            [r.model_dump() for r in results],
            ensure_ascii=False,
            default=str,
            indent=2,
        )
        content = await self._chat(
            [
                {"role": "system", "content": _SYNTHESIZER_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"User question: {message}\n\nTask results:\n{results_text}"
                    ),
                },
            ],
            model=self._model,
            temperature=0.1,
        )
        return content.strip()

    async def generate_title_with_trace(
        self,
        first_message: str,
    ) -> tuple[str, dict[str, Any], dict[str, Any]]:
        """Generate a short conversation title with request/response trace."""
        messages = [
            {"role": "system", "content": _TITLE_PROMPT},
            {"role": "user", "content": first_message},
        ]
        request_json = {
            "model": self._chat_model,
            "temperature": 0.2,
            "messages": messages,
        }
        content = await self._chat(
            messages,
            model=self._chat_model,
            temperature=0.2,
        )
        title = self._clean_title(content)
        if self._title_needs_fallback(title, content):
            title = self._fallback_title_from_message(first_message)
        return title, request_json, {"content": content, "title": title}

    async def generate_title(self, first_message: str) -> str:
        """Generate a short conversation title."""
        title, _request_json, _response_json = await self.generate_title_with_trace(
            first_message
        )
        return title

    async def generate_chat_response_with_trace(
        self,
        *,
        history: list[dict[str, str]],
        user_message: str,
        plan: "Plan",
        results: list["TaskResult"],
    ) -> tuple[str, dict[str, Any], dict[str, Any]]:
        """Generate the final user-facing answer with request/response trace."""
        plan_text = plan.model_dump()
        results_text = [
            {"citation_index": i + 1, **result.model_dump()}
            for i, result in enumerate(results)
        ]
        messages = [
            {"role": "system", "content": _CHAT_RESPONSE_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "history": history,
                        "current_user_message": user_message,
                        "plan": plan_text,
                        "results": results_text,
                    },
                    ensure_ascii=False,
                    default=str,
                    indent=2,
                ),
            },
        ]
        request_json = {
            "model": self._chat_model,
            "temperature": 0.2,
            "messages": messages,
        }
        content = await self._chat(
            messages,
            model=self._chat_model,
            temperature=0.2,
        )
        answer = self._clean_chat_answer(content.strip(), results)
        response_json: dict[str, Any] = {
            "content": content,
            "answer": answer,
            "answer_format": detect_text_format(answer),
        }
        if answer != content.strip():
            response_json["sanitized"] = True
        return answer, request_json, response_json

    async def generate_chat_response(
        self,
        *,
        history: list[dict[str, str]],
        user_message: str,
        plan: "Plan",
        results: list["TaskResult"],
    ) -> str:
        """Generate the final user-facing answer."""
        answer, _request_json, _response_json = (
            await self.generate_chat_response_with_trace(
                history=history,
                user_message=user_message,
                plan=plan,
                results=results,
            )
        )
        return answer

    # ------------------------------------------------------------------
    # Original single-intent classifier (kept for backward compatibility)
    # ------------------------------------------------------------------

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
            ],
            model=self._model,
            temperature=0.1,
        )
        raw = self._extract_json(content)
        try:
            return Intent.model_validate(raw)
        except ValidationError as exc:
            raise MiniMaxError(
                f"LLM returned JSON that does not match the Intent schema: {exc}"
            ) from exc

    async def _chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float,
    ) -> str:
        """Send a chat-completion request and return the assistant's content.

        Raises
        ------
        MiniMaxError
            On transport errors, error status codes, or malformed responses.
        """
        url = f"{self._base_url}/text/chatcompletion_v2"
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
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

    @staticmethod
    def _planner_messages(
        message: str,
        history: list[dict[str, str]] | None,
    ) -> list[dict[str, str]]:
        if not history:
            user_content = message
        else:
            user_content = json.dumps(
                {
                    "conversation_history": history,
                    "current_user_message": message,
                },
                ensure_ascii=False,
                indent=2,
            )
        return [
            {"role": "system", "content": _PLANNER_PROMPT},
            {"role": "user", "content": user_content},
        ]

    @staticmethod
    def _clean_title(content: str) -> str:
        title = content.strip()
        # Strip leading markdown heading characters (# ## ### etc.)
        title = re.sub(r"^#+\s*", "", title)
        # Strip surrounding quotes and backticks
        title = title.strip("\"'`").strip()
        # Strip inline markdown: **bold**, *italic*, __bold__, _italic_, `code`
        title = re.sub(r"\*{1,2}(.+?)\*{1,2}", r"\1", title)
        title = re.sub(r"_{1,2}(.+?)_{1,2}", r"\1", title)
        title = re.sub(r"`(.+?)`", r"\1", title)
        # Normalize whitespace
        title = " ".join(title.split())
        # Strip trailing punctuation
        if title.endswith((".", ":", ";", ",")):
            title = title[:-1].strip()
        words = title.split()[:8]
        return " ".join(words)[:80] or "Nueva conversación"

    @staticmethod
    def _title_needs_fallback(title: str, raw_content: str | None = None) -> bool:
        normalized = _normalize_for_prompt_repair(title)
        raw_normalized = _normalize_for_prompt_repair(raw_content or title)
        raw_words = raw_normalized.split()
        bad_starts = (
            "voy ",
            "he ",
            "ahora ",
            "claro ",
            "permiteme",
            "buscare",
            "busca ",
            "buscar ",
            "limitacion ",
            "limitaciones ",
            "no puedo ",
            "no tengo ",
            "no dispongo ",
            "no cuento ",
            "lo siento ",
            "lamento ",
            "i cannot ",
            "i can't ",
            "i am unable ",
            "i'm unable ",
            "sorry ",
            "as an ai ",
        )
        answer_markers = (
            "no puedo realizar",
            "no puedo responder",
            "no tengo acceso",
            "no dispongo de acceso",
            "no cuento con acceso",
            "bases de datos en tiempo real",
            "como modelo",
            "mis capacidades",
            "i do not have access",
            "i don't have access",
            "cannot perform",
        )
        return (
            not title
            or title == "Nueva conversación"
            or normalized.startswith(bad_starts)
            or raw_normalized.startswith(bad_starts)
            or "permiteme" in normalized
            or "permiteme" in raw_normalized
            or "tool_call" in normalized
            or "tool_call" in raw_normalized
            or any(marker in raw_normalized for marker in answer_markers)
            or len(raw_words) > 16
            or len((raw_content or title).strip()) > 120
        )

    @staticmethod
    def _fallback_title_from_message(first_message: str) -> str:
        text = re.sub(r"[\r\n]+", " ", first_message).strip()
        text = re.sub(r"[^\w\sáéíóúÁÉÍÓÚñÑüÜ-]", " ", text)
        stopwords = {
            "a",
            "al",
            "con",
            "de",
            "del",
            "el",
            "en",
            "la",
            "las",
            "lo",
            "los",
            "o",
            "para",
            "por",
            "que",
            "quiero",
            "quisiera",
            "necesito",
            "saber",
            "indagar",
            "respecto",
            "caso",
            "ligadas",
            "ligados",
            "primeros",
            "primeras",
            "días",
            "dias",
        }
        words = [
            word
            for word in text.split()
            if _normalize_for_prompt_repair(word) not in stopwords
        ]
        if not words:
            words = text.split()
        title = " ".join(words[:8]).strip()
        return title.title()[:80] or "Nueva conversación"

    @staticmethod
    def _clean_chat_answer(answer: str, results: list[Any]) -> str:
        if not answer:
            return MiniMaxClient._fallback_chat_answer_from_results(results)
        if not MiniMaxClient._contains_tool_call_syntax(answer):
            return answer
        return MiniMaxClient._fallback_chat_answer_from_results(results)

    @staticmethod
    def _contains_tool_call_syntax(answer: str) -> bool:
        normalized = _normalize_for_prompt_repair(answer)
        markers = (
            "[tool_call]",
            "[/tool_call]",
            "tool =>",
            "method =>",
            "mcp_b ",
            "--buyer_code",
            "--date_from",
            "--date_to",
            "purchase_orders_list",
            "tenders_list",
        )
        return any(marker in normalized for marker in markers)

    @staticmethod
    def _fallback_chat_answer_from_results(results: list[Any]) -> str:
        data_results = [
            result
            for result in results
            if getattr(result, "tool", "") != "mp_resolve_organism"
        ]
        failed = sum(1 for result in results if getattr(result, "status", "") == "error")

        if data_results:
            total = sum(int(getattr(result, "record_count", 0) or 0) for result in data_results)
            if total == 0:
                suffix = f" Hubo {failed} tareas con error." if failed else ""
                return (
                    "Ejecuté las consultas disponibles, pero no encontré registros "
                    f"para los filtros solicitados.{suffix}"
                )

            samples = []
            for result in data_results:
                for record in getattr(result, "records", [])[:3]:
                    code = record.get("Codigo") or record.get("codigo") or record.get("code")
                    name = record.get("Nombre") or record.get("nombre") or record.get("name")
                    if code and name:
                        samples.append(f"{code} - {name}")
                    elif name:
                        samples.append(str(name))
                    if len(samples) >= 3:
                        break
                if len(samples) >= 3:
                    break
            sample_text = f" Algunos ejemplos: {'; '.join(samples)}." if samples else ""
            suffix = f" Hubo {failed} tareas con error." if failed else ""
            return (
                f"Ejecuté las consultas y encontré {total} registros en los "
                f"resultados de datos.{sample_text}{suffix}"
            )

        resolved = []
        for result in results:
            for record in getattr(result, "records", [])[:2]:
                code = record.get("code") or record.get("CodigoEmpresa")
                name = record.get("name") or record.get("NombreEmpresa")
                if code and name:
                    resolved.append(f"{name} ({code})")
        if resolved:
            return (
                "Resolví el organismo solicitado como "
                f"{'; '.join(resolved)}, pero esta respuesta no recibió resultados "
                "de compras o licitaciones para analizar."
            )
        return (
            "No obtuve datos suficientes para responder con resultados. "
            "La traza de la conversación conserva las llamadas ejecutadas y sus errores."
        )

    @staticmethod
    def _repair_plan_from_message(plan: Any, message: str) -> Any:
        """Patch common planner degradations that would widen API searches."""
        organism_name = MiniMaxClient._extract_named_organism(message)
        if not organism_name:
            return plan

        message_norm = _normalize_for_prompt_repair(message)
        date_range = MiniMaxClient._extract_date_range_from_message(message)
        if (
            date_range
            and MiniMaxClient._plan_only_resolves_organisms(plan)
            and (
                MiniMaxClient._message_requests_orders(message_norm)
                or MiniMaxClient._message_requests_tenders(message_norm)
            )
        ):
            from app.services.models import Task

            include_orders = MiniMaxClient._message_requests_orders(message_norm)
            include_tenders = MiniMaxClient._message_requests_tenders(message_norm)
            if not include_orders and not include_tenders:
                include_tenders = True
            start_date, end_date = date_range
            task = Task(
                id="t1",
                tool="mp_semantic_range",
                description=(
                    "Search Mercado Publico purchases/tenders for "
                    f"{organism_name} between {start_date} and {end_date}"
                ),
                parameters={
                    "organism_name": organism_name,
                    "start_date": start_date,
                    "end_date": end_date,
                    "keywords": MiniMaxClient._extract_semantic_keywords(message_norm),
                    "include_orders": include_orders,
                    "include_tenders": include_tenders,
                },
            )
            return plan.model_copy(
                update={
                    "tasks": [task],
                    "reasoning": (
                        "Repaired resolve-only plan into a date-range Mercado "
                        "Publico data search for the named organism."
                    ),
                }
            )

        repaired_tasks = []
        changed = False
        for task in plan.tasks:
            if (
                task.tool == "mp_orders_by_date"
                and ("orden" in message_norm or "purchase order" in message_norm)
            ):
                parameters = {
                    **task.parameters,
                    "organism_name": organism_name,
                }
                repaired_tasks.append(
                    task.model_copy(
                        update={
                            "tool": "mp_orders_by_org_and_date",
                            "parameters": parameters,
                            "description": (
                                f"{task.description} for {organism_name}"
                            ),
                        }
                    )
                )
                changed = True
            elif (
                task.tool == "mp_tenders_by_date"
                and ("licit" in message_norm or "tender" in message_norm)
            ):
                parameters = {
                    **task.parameters,
                    "organism_name": organism_name,
                }
                repaired_tasks.append(
                    task.model_copy(
                        update={
                            "tool": "mp_tenders_by_org",
                            "parameters": parameters,
                            "description": (
                                f"{task.description} for {organism_name}"
                            ),
                        }
                    )
                )
                changed = True
            else:
                repaired_tasks.append(task)

        if not changed:
            return plan
        return plan.model_copy(update={"tasks": repaired_tasks})

    @staticmethod
    def _extract_named_organism(message: str) -> str | None:
        match = re.search(
            r"\b((?:(?:i\.?|ilustre)\s+)?municipalidad\s+de\s+.+?)"
            r"(?=[\.,;:\n]|\s+(?:para|por|entre|between|from|on|"
            r"el\s+\d|la\s+\d|necesito|necesita|quiero|quisiera|"
            r"busca|buscar|dame|muestrame|mu[eé]strame)\b|$)",
            message,
            flags=re.IGNORECASE,
        )
        if not match:
            return None
        return " ".join(match.group(1).strip(" .,;:").split())

    @staticmethod
    def _plan_only_resolves_organisms(plan: Any) -> bool:
        tasks = getattr(plan, "tasks", [])
        return bool(tasks) and all(
            getattr(task, "tool", "") == "mp_resolve_organism"
            for task in tasks
        )

    @staticmethod
    def _message_requests_orders(message_norm: str) -> bool:
        return any(
            term in message_norm
            for term in ("orden", "ordenes", "compra", "compras", "purchase order")
        )

    @staticmethod
    def _message_requests_tenders(message_norm: str) -> bool:
        return any(term in message_norm for term in ("licit", "tender"))

    @staticmethod
    def _extract_date_range_from_message(message: str) -> tuple[str, str] | None:
        text = _normalize_for_prompt_repair(message)

        match = re.search(
            r"\b(?:entre|between)\s+(\d{8})\s+(?:y|and|hasta|to|-)\s+(\d{8})\b",
            text,
        )
        if match:
            return match.group(1), match.group(2)

        match = re.search(
            r"\b(?:entre|between)\s+(\d{4})-(\d{2})-(\d{2})\s+"
            r"(?:y|and|hasta|to|-)\s+(\d{4})-(\d{2})-(\d{2})\b",
            text,
        )
        if match:
            y1, m1, d1, y2, m2, d2 = match.groups()
            return f"{d1}{m1}{y1}", f"{d2}{m2}{y2}"

        match = re.search(
            r"\b(?:entre|between)\s+(?:el\s+)?(\d{1,2})\s+"
            r"(?:y|al|hasta|and|to|-)\s+(?:el\s+)?(\d{1,2})\s+"
            r"de\s+([a-z]+)\s+(?:de|del)\s+(\d{4})\b",
            text,
        )
        if match:
            start_day = int(match.group(1))
            end_day = int(match.group(2))
            month = _SPANISH_MONTHS.get(match.group(3))
            year = int(match.group(4))
            if month:
                return (
                    f"{start_day:02d}{month:02d}{year}",
                    f"{end_day:02d}{month:02d}{year}",
                )

        match = re.search(
            r"\bprimer(?:os|as)?\s+(\d{1,2}|un|uno|una|dos|tres|cuatro|"
            r"cinco|seis|siete|ocho|nueve|diez)\s+dias?\s+de\s+"
            r"([a-z]+)\s+(?:de|del)\s+(\d{4})\b",
            text,
        )
        if match:
            days = _parse_small_number(match.group(1))
            month = _SPANISH_MONTHS.get(match.group(2))
            year = int(match.group(3))
            if days and month:
                max_day = monthrange(year, month)[1]
                end_day = min(days, max_day)
                return f"01{month:02d}{year}", f"{end_day:02d}{month:02d}{year}"

        match = re.search(
            r"\bentre\s+([a-z]+)\s+y\s+([a-z]+)\s+(?:de|del)?\s*(\d{4})\b",
            text,
        )
        if match:
            start_month = _SPANISH_MONTHS.get(match.group(1))
            end_month = _SPANISH_MONTHS.get(match.group(2))
            year = int(match.group(3))
            if start_month and end_month:
                end_day = monthrange(year, end_month)[1]
                return f"01{start_month:02d}{year}", f"{end_day:02d}{end_month:02d}{year}"

        return None

    @staticmethod
    def _extract_semantic_keywords(message_norm: str) -> list[str]:
        keyword_patterns = [
            (r"sistemas?\s+computacionales?", "sistemas computacionales"),
            (r"sistemas?\s+informaticos?", "sistemas informaticos"),
            (r"computadores?", "computadores"),
            (r"notebooks?", "notebooks"),
            (r"software", "software"),
            (r"hardware", "hardware"),
            (r"plataformas?\s+web", "plataforma web"),
            (r"tecnologia", "tecnologia"),
            (r"informatica", "informatica"),
        ]
        keywords = [
            keyword
            for pattern, keyword in keyword_patterns
            if re.search(pattern, message_norm)
        ]
        return list(dict.fromkeys(keywords))


_SPANISH_MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}

_SMALL_NUMBER_WORDS = {
    "un": 1,
    "uno": 1,
    "una": 1,
    "dos": 2,
    "tres": 3,
    "cuatro": 4,
    "cinco": 5,
    "seis": 6,
    "siete": 7,
    "ocho": 8,
    "nueve": 9,
    "diez": 10,
}


def _parse_small_number(value: str) -> int | None:
    if value.isdigit():
        return int(value)
    return _SMALL_NUMBER_WORDS.get(value)


def _normalize_for_prompt_repair(value: str) -> str:
    text = unicodedata.normalize("NFKD", value)
    text = "".join(char for char in text if not unicodedata.combining(char))
    return text.lower()
