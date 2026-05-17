# Indies — Project Overview

**What it is:** A conversational anti-corruption audit assistant for Chilean public data. Users ask natural-language questions; the backend plans the required API calls, executes them, stores the full conversation trace, and returns a human-readable answer.

---

## Architecture

```
[curl / API client]
      |
      | POST /api/v1/chat/messages  { conversation_id?, message }
      v
[FastAPI Backend]
      |
      |-- SQLite/Postgres           → conversations, messages, LLM traces, tool runs
      |-- MiniMax Planner model      → structured API task plan
      |-- Executor                   → Mercado Público + Senado + Contraloría/Cámara tool calls
      |-- MiniMax Chat model         → natural-language response
      |
      v
{ conversation, user_message, assistant_message, planner, tool_runs, total_records }
```

`POST /api/v1/audit/query` remains available as a stateless compatibility endpoint for the older plan → execute → synthesize flow.

---

## Backend (`/backend`)

**Stack:** Python · FastAPI · httpx · Pydantic v2 · pydantic-settings · SQLAlchemy async · Alembic · SQLite/aiosqlite · Postgres/asyncpg · uvicorn

### Entry point
`backend/app/main.py`
- Creates a shared `httpx.AsyncClient`.
- Creates the async database engine and runs Alembic migrations to `head` at startup.
- Mounts `MiniMaxClient`, `MercadoPublicoClient`, `SenadoClient`, `ContraloriaService`, and `db_sessionmaker` onto `app.state`.
- Uses `CONTRALORIA_DATABASE_URL` (or a PostgreSQL `DATABASE_URL`) for Contraloría/Cámara lookup tables; when no PostgreSQL DSN is configured, those executor tools are disabled so local development still starts.
- Enables CORS for origins in `FRONTEND_ORIGINS`.

### Config
`backend/app/core/config.py` — `Settings` (pydantic-settings, reads `.env`)

| Variable | Default | Notes |
|---|---|---|
| `MINIMAX_API_KEY` | — | Required |
| `MINIMAX_BASE_URL` | — | Required; example: `https://api.minimax.io/v1` |
| `MINIMAX_MODEL` | — | Required planner/API-routing model |
| `MINIMAX_CHAT_MODEL` | `MINIMAX_MODEL` | Optional user-facing conversational model |
| `MERCADO_PUBLICO_TICKET` | — | Required Mercado Público ticket |
| `MERCADO_PUBLICO_BASE_URL` | — | Required; example: `https://api.mercadopublico.cl/servicios/v1/publico` |
| `FRONTEND_ORIGINS` | — | Required comma-separated CORS origins |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/indies.db` | Optional async SQLAlchemy URL for conversation persistence |
| `CONTRALORIA_DATABASE_URL` | — | Optional PostgreSQL/Neon URL for Contraloría and Cámara lookup tables; falls back to `DATABASE_URL` only when `DATABASE_URL` is PostgreSQL |

### API Routes

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | API index with docs/health/chat route pointers |
| `POST` | `/api/v1/chat/messages` | Create/continue a persistent conversation turn |
| `PATCH` | `/api/v1/chat/messages/{message_id}/feedback` | Set or clear like/dislike feedback for one chat message |
| `GET` | `/api/v1/chat/conversations` | List persisted conversations |
| `GET` | `/api/v1/chat/conversations/{conversation_id}` | Get messages, LLM invocations, and tool runs for one conversation |
| `PATCH` | `/api/v1/chat/conversations/{conversation_id}` | Rename a conversation |
| `PATCH` | `/api/v1/chat/conversations/{conversation_id}/feedback` | Set or clear overall conversation rating and text feedback |
| `DELETE` | `/api/v1/chat/conversations/{conversation_id}` | Soft-delete a conversation |
| `POST` | `/api/v1/audit/query` | Stateless compatibility endpoint: plan → execute → synthesize |
| `GET` | `/api/v1/senado/support-staff` | Direct Senate support-staff lookup |
| `GET` | `/health` | Liveness probe |
| `GET` | `/api/hello` | Legacy connectivity check |

### `GET /`

Returns a small API index for the backend base URL:

```json
{
  "name": "Indies Audit API",
  "version": "0.2.0",
  "status": "ok",
  "docs_url": "/docs",
  "health_url": "/health",
  "chat_messages_url": "/api/v1/chat/messages"
}
```

### `POST /api/v1/chat/messages`

Request:
```json
{
  "conversation_id": null,
  "message": "Busca sistemas computacionales para la Municipalidad de Algarrobo entre enero y marzo 2024"
}
```

Response:
```json
{
  "conversation": {
    "id": "uuid",
    "title": "Sistemas computacionales en Algarrobo",
    "created_at": "2026-05-16T00:00:00Z",
    "updated_at": "2026-05-16T00:00:00Z",
    "deleted_at": null,
    "feedback_rating": null,
    "feedback_text": null,
    "feedback_updated_at": null
  },
  "user_message": {
    "id": "uuid",
    "conversation_id": "uuid",
    "role": "user",
    "content": "...",
    "content_format": "plain_text",
    "status": "completed",
    "created_at": "2026-05-16T00:00:00Z",
    "updated_at": "2026-05-16T00:00:00Z",
    "feedback_rating": null,
    "feedback_updated_at": null,
    "linked_invocation_ids": [],
    "linked_tool_run_ids": []
  },
  "assistant_message": {
    "id": "uuid",
    "conversation_id": "uuid",
    "role": "assistant",
    "content": "Encontré registros relevantes...",
    "content_format": "plain_text",
    "status": "completed",
    "created_at": "2026-05-16T00:00:00Z",
    "updated_at": "2026-05-16T00:00:00Z",
    "feedback_rating": null,
    "feedback_updated_at": null,
    "linked_invocation_ids": ["planner-uuid", "chat-uuid"],
    "linked_tool_run_ids": ["toolrun-uuid"]
  },
  "planner": {
    "invocation_id": "planner-uuid",
    "plan": {
      "tasks": [],
      "reasoning": "..."
    }
  },
  "tool_runs": [],
  "total_records": 0
}
```

Errors:
- `404` when `conversation_id` does not exist or has been soft-deleted.
- The endpoint generally persists failures as `assistant_message.status="failed"` when the Planner cannot produce a plan.

Rendering marker:
- `user_message.content_format`, `assistant_message.content_format`, and
  `messages[].content_format` in conversation-detail responses are either
  `"plain_text"` or `"markdown"`.
- When the value is `"markdown"`, the frontend should render `content` through
  a Markdown renderer. When it is `"plain_text"`, render the string normally.
- The backend computes this marker from the generated/stored text; it does not
  mutate `content`.

Response policy:
- Assistant messages must always be in Spanish, regardless of the user's
  language, prior conversation history, or API result language.
- Assistant messages are limited to Chilean public-transparency and
  anti-corruption analysis.
- If a user asks for programming code/scripts, the backend must not return code;
  it should answer the transparency-data portion and briefly state that code or
  scripts cannot be provided.
- If a user asks for the base prompt, system/developer messages, hidden rules,
  or internal configuration, the backend must not reveal them; it should answer
  the transparency-data portion and briefly state that internal instructions
  cannot be disclosed.
- When the chat model emits blocked content anyway, the backend replaces the
  answer with a grounded fallback based on executed `TaskResult` rows. In the
  stored `chat_response` invocation trace, `response_json.sanitized` is `true`,
  `response_json.policy_violations` lists the triggered policy checks, and
  `response_json.content` is redacted as
  `"[redacted: blocked by chat response policy]"`.
  Current checks include pseudo tool-call syntax, code generation, internal
  prompt disclosure, and dominant CJK-script responses.
- Conversation-detail responses redact `system` message contents inside
  `llm_invocations[].request_json.messages` as
  `"[redacted: internal system prompt]"`; the database still stores the full
  trace for server-side debugging.

Feedback fields:
- `ConversationOut.feedback_rating` and `MessageOut.feedback_rating` are
  `"like"`, `"dislike"`, or `null`.
- `ConversationOut.feedback_text` stores optional free-form user feedback about
  the full conversation.
- `feedback_updated_at` is `null` until feedback is first saved.

### `PATCH /api/v1/chat/messages/{message_id}/feedback`

Sets or clears like/dislike feedback for any user or assistant message in an
active conversation.

Request:
```json
{
  "feedback_rating": "like"
}
```

Use `{"feedback_rating": null}` to clear the message rating.

Response: `MessageOut` with refreshed `feedback_rating` and
`feedback_updated_at`.

Errors:
- `404` when the message does not exist or belongs to a soft-deleted conversation.
- `422` when `feedback_rating` is not `"like"`, `"dislike"`, or `null`.

### `GET /api/v1/chat/conversations`

Returns active, non-deleted conversations ordered by `updated_at` descending.
Each item is a `ConversationListItem`:

```json
{
  "id": "uuid",
  "title": "Sistemas computacionales en Algarrobo",
  "created_at": "2026-05-16T00:00:00Z",
  "updated_at": "2026-05-16T00:00:00Z",
  "deleted_at": null,
  "feedback_rating": null,
  "feedback_text": null,
  "feedback_updated_at": null,
  "last_message": null,
  "message_count": 0
}
```

### `GET /api/v1/chat/conversations/{conversation_id}`

Returns a full active, non-deleted conversation with `conversation`, `messages`,
`llm_invocations`, and `tool_runs`. Returns `404` when the conversation does not
exist or has `deleted_at` set.

### `PATCH /api/v1/chat/conversations/{conversation_id}`

Request:
```json
{
  "title": "Nuevo título"
}
```

Response: `ConversationOut` with the updated `title`, refreshed `updated_at`,
and `deleted_at: null`.

Errors:
- `404` when the conversation does not exist or has been soft-deleted.
- `422` when `title` is empty or longer than 160 characters.

### `PATCH /api/v1/chat/conversations/{conversation_id}/feedback`

Sets, updates, or clears overall feedback for an active conversation. Fields are
patched independently: omitted fields keep their previous value, while explicit
`null` clears the stored value.

Request:
```json
{
  "feedback_rating": "dislike",
  "feedback_text": "La respuesta fue demasiado general."
}
```

Response: `ConversationOut` with refreshed `feedback_rating`, `feedback_text`,
and `feedback_updated_at`.

Errors:
- `404` when the conversation does not exist or has been soft-deleted.
- `422` when no feedback fields are provided, `feedback_rating` is not
  `"like"`, `"dislike"`, or `null`, or `feedback_text` is longer than 4000
  characters.

### `DELETE /api/v1/chat/conversations/{conversation_id}`

Soft-deletes the conversation by setting `conversations.deleted_at = utc_now()`.
Messages, LLM invocations, and tool runs are preserved for audit/recovery.

Response: `204 No Content`.

Errors:
- `404` when the conversation does not exist or has already been soft-deleted.

### `POST /api/v1/audit/query`

Request:
```json
{
  "message": "Analiza las compras de una municipalidad"
}
```

Response:
```json
{
  "plan": {
    "tasks": [],
    "reasoning": "..."
  },
  "results": [],
  "synthesis": "Encontré registros relevantes...",
  "synthesis_format": "plain_text",
  "total_records": 0
}
```

Rendering marker:
- `synthesis_format` is either `"plain_text"` or `"markdown"`.
- When `synthesis_format` is `"markdown"`, the frontend should render
  `synthesis` through a Markdown renderer. When it is `"plain_text"`, render it
  normally.

### Persistence
`backend/app/core/database.py`

Local SQLite paths are prepared at startup: the parent directory is created if
needed, and a local database file with missing user-write permission is made
writable for development.

Schema changes are versioned with Alembic:
- Config: `backend/alembic.ini`
- Environment: `backend/migrations/env.py`
- Revisions: `backend/migrations/versions/`

`init_db()` runs `alembic upgrade head` on the app's active async SQLAlchemy
connection before chat routes serve traffic. On Postgres it wraps the upgrade in
a transaction-scoped advisory lock so concurrent Vercel cold starts do not run
the same migration at the same time. The first revision is idempotent so it can
adopt existing SQLite/Postgres databases created before migrations; it creates
missing chat tables, indexes, and `conversations.deleted_at`. The second
revision adds persisted message and conversation feedback fields.

| Table | Purpose |
|---|---|
| `conversations` | UUID conversation shell with generated/renamable title, timestamps, nullable `deleted_at` for soft delete, overall `feedback_rating`, optional `feedback_text`, and `feedback_updated_at` |
| `messages` | User/assistant messages with status (`processing`, `completed`, `failed`), per-message `feedback_rating`, and `feedback_updated_at` |
| `llm_invocations` | Title generation, Planner, and chat-response model calls; stores request/response JSON and error status. Public API responses redact internal `system` prompt contents from `request_json.messages`. |
| `tool_runs` | One row per Planner task/API execution, linked to the assistant message and planner invocation |

There is no auth yet; the conversation UUID is the access handle.
Soft-deleted conversations are excluded from list/detail/continue/rename/delete
operations, but their messages and trace rows remain in the database.

### Services

#### `ChatService` (`backend/app/services/chat_service.py`)
- Creates/reuses conversations.
- Lists and fetches only active conversations (`deleted_at IS NULL`).
- Renames conversations by updating `title` and `updated_at`.
- Stores or clears message-level like/dislike feedback.
- Stores or clears conversation-level like/dislike feedback and optional text feedback.
- Soft-deletes conversations by setting `deleted_at`; it does not delete messages or traces.
- Generates a title from the first user message with `MINIMAX_CHAT_MODEL`; falls back to a short slice of the message if title generation fails.
- Persists user/assistant messages.
- Calls the Planner model with recent conversation history.
- Runs the existing `Executor` and stores every tool/API result as a `tool_run`.
- Calls the chat model to produce the final natural-language answer. The
  assistant response is expected to describe already executed results, not to
  emit `[TOOL_CALL]` blocks, future API-call instructions, programming code, or
  internal prompts/instructions, and must always be written in Spanish.
- Sends a compacted view of large `TaskResult.records` lists to the chat model
  for synthesis; full records remain persisted in `tool_runs` and returned to
  the frontend receipt/source tables. `mp_tender_by_codigo` uses a richer
  detail view for the chat model, preserving tender identity, buyer, dates,
  estimated amount, items, and item-level adjudication fields so single-tender
  analysis does not lose key fields during prompt compaction. Internal
  prompt-compaction markers are not exposed as record fields in the chat
  context. Mercado Público's `CantidadReclamos` tender field is labeled for the
  chat model as a buyer/organism period claim count, not as complaints filed
  against the specific tender.

#### `MiniMaxClient` (`backend/app/services/minimax_client.py`)
- `MINIMAX_MODEL`: structured Planner/API-routing and legacy synthesis.
- `MINIMAX_CHAT_MODEL`: title generation and final user-facing responses.
- Exposes trace-returning methods so chat persistence can store model requests/responses.
- Repairs common Planner degradations before execution. For example, if the
  Planner only resolves `Municipalidad de Maipú` but the user asked for compras
  or licitaciones over a date range, the backend rewrites the plan to
  `mp_semantic_range` with the extracted organism, range, and include flags.
- Cleans generated titles and falls back to a short local title from the first
  user message, or `Nueva conversación` when no Latin/Spanish title terms
  remain, when the chat model returns markdown, an assistant-style sentence, an
  inability/error response body, CJK-script text, or an overlong non-title.
- Sanitizes chat responses that contain pseudo tool-call syntax and replaces
  them with a grounded fallback based on the executed `TaskResult` objects.
- Sanitizes chat/synthesis responses containing dominant CJK-script output or
  English-language leakage. Known short prompt fragments, including `worth reviewing`,
  are repaired inline in Spanish; broader non-Spanish answers are replaced with
  a Spanish fallback based on the executed `TaskResult` objects.
- Sanitizes chat/synthesis responses that try to satisfy code-generation
  requests or disclose internal prompts/instructions. Mixed requests are
  handled by answering the transparency-data portion and refusing only the
  forbidden portion.
- Repairs Senate support-staff plans by moving cargo/rol/función/puesto terms
  such as `conductor` into the `senado_support_staff.role` parameter when the
  Planner omits that structured filter.

#### `Executor` (`backend/app/services/executor.py`)
Runs Planner tasks concurrently. Supported tools:

| Tool | Required params |
|---|---|
| `senado_support_staff` | `year`, `month_es`, optional `senator_name`, `staff_name`, `role` |
| `mp_orders_by_org_and_date` | `fecha` + `codigoorg` or `organism_name` |
| `mp_orders_by_date` | `fecha` |
| `mp_tender_by_codigo` | `codigo` |
| `mp_tenders_today` | — |
| `mp_tenders_by_date` | `fecha` |
| `mp_tenders_by_status` | `fecha`, `estado` |
| `mp_tenders_by_supplier` | `fecha`, `CodigoProveedor` |
| `mp_tenders_by_org` | `fecha` + `codigo_organismo` or `organism_name` |
| `mp_search_buyers` | — |
| `mp_resolve_organism` | `organism_name` |
| `mp_semantic_range` | `organism_name`, `start_date`, `end_date`, `keywords`, optional `include_tenders`, `include_orders` |
| `contraloria_search` | optional `entity_name`, `year_min`, `year_max`, `region`, `tipo_fiscalizacion`, `complejidad`, `keywords`, `source`, `limit` |
| `camara_resolve_diputado` | `name` |
| `camara_datos_diputado` | `categoria` plus `codigo` or `name` |

`mp_semantic_range` normalizes accents and expands computational keywords with
common Spanish singular/plural variants such as `sistemas informaticos` →
`sistema informatico`, so records like `SISTEMA INFORMÁTICO ...` are retained.
It also supports `keywords: []` for broad organism/date-range reviews, such as
questions asking for potentially suspicious purchases or tenders without a
specific product category.

Single-date organism tools also accept `organism_name`; the Executor resolves
the name through Mercado Público before calling `ordenesdecompra.json` or
`licitaciones.json`. This prevents named-organism requests from widening into
date-only searches.

#### `ContraloriaService` (`backend/app/services/contraloria.py`)
PostgreSQL client for Contraloría General de la República audit data. It is
enabled when `CONTRALORIA_DATABASE_URL` is set to a PostgreSQL/Neon DSN, or
when `DATABASE_URL` itself is PostgreSQL. If the app is using the default local
SQLite persistence URL and no Contraloría DSN is configured, FastAPI still
starts and `contraloria_search` tool runs return `status: "error"` with a
service-unavailable message.

**Database tables:**
- `municipalidades` — municipal audits, 2020–2024
- `no_municipalidades` — non-municipal entity audits, 2020–2025

**`contraloria_search` parameters:**

| Param | Type | Notes |
|---|---|---|
| `entity_name` | `str?` | Substring match on `Entidad` (accent-insensitive) |
| `year_min` / `year_max` | `int?` | Inclusive range on `Año informe publicado` |
| `region` | `str?` | Substring match on `Región` |
| `tipo_fiscalizacion` | `str?` | e.g. `AUDITORIA`, `INSPECCION_OBRA_PUBLICA` |
| `complejidad` | `str?` | `COMPLEJA` / `MEDIANAMENTE COMPLEJA` / `LEVEMENTE COMPLEJA` |
| `keywords` | `list[str]` | Searched across `Materia Fiscalizacion`, `Nombre Fiscalizacion`, `Objetivo Fiscalizacion`, `Titulo Observacion` |
| `source` | `str` | `"municipalidades"` / `"no_municipales"` / `"both"` (default `"both"`) |
| `limit` | `int` | Max rows returned (default 50, max 200) |

**Response metadata:** `total_before_limit`, `returned`, `limit`, `source`, `filters_applied`.

#### `CamaraService` (`backend/app/services/camara.py`)
Scrapes public Cámara de Diputados transparency pages and uses the same
PostgreSQL/Neon pool as Contraloría to resolve deputy names through the
`id_diputados` table. When no PostgreSQL DSN is configured, FastAPI still
starts and Cámara tool runs return `status: "error"` with a
service-unavailable message.

Supported `camara_datos_diputado.categoria` values:
- `gastos_operacionales`
- `asesoria_externa`
- `pasajes_aereos`
- `instancias_internacionales`
- `personal_apoyo`
- `audiencias`

#### External services
- Mercado Público API: authenticated with `ticket` query param.
- Senado de Chile transparency API: unauthenticated Strapi REST endpoint.
- MiniMax: OpenAI-compatible chat-completion endpoint.
- Contraloría/Cámara lookup data: PostgreSQL/Neon via `CONTRALORIA_DATABASE_URL`
  or PostgreSQL `DATABASE_URL`; optional for local startup.

---

## Frontend (`/frontend`)

**Stack:** Next.js (App Router) · TypeScript · CSS Modules · `react-markdown`

- `NEXT_PUBLIC_API_URL` points to the backend, defaulting to `http://localhost:8000`.
- The frontend uses `POST /api/v1/chat/messages` and the conversation endpoints exclusively. The old `/api/v1/audit/query` endpoint is not used by the UI.
- Browser tab/app icons are declared through Next metadata and served from `/favicon.png`.

### Layout

Three-column layout (sidebar · chat · nothing) that collapses to a mobile drawer on small screens.

| Zone | Description |
|---|---|
| Sidebar | Conversation list grouped by time (Hoy / Ayer / 7 días / 30 días / Anterior). Collapsible. New conversation button, ⋯ hover menu per item for rename/delete. |
| Chat area | Message thread + sticky input at bottom. Conversation title bar with inline rename (pencil) and delete (trash) actions. |

### Evidence trail — "Show the receipts"

Every assistant message includes a collapsible **FUENTES** section below the bubble. Expanded by default. Each source row is its own accordion showing the exact API call parameters and the full data table. Citation markers `[N]` in the synthesis text are rendered as clickable superscript buttons that auto-expand and scroll to the corresponding source row.

### Markdown rendering

`assistant_message.content_format` drives rendering: `"markdown"` → `react-markdown` with custom `[N]` marker injection; `"plain_text"` → plain paragraph.

### Pending backend endpoints

The following endpoints are designed and the frontend is fully wired, but the backend has not implemented them yet:

| Method | Path | Notes |
|---|---|---|
| `PATCH` | `/api/v1/chat/conversations/{id}` | Rename — body: `{ "title": "..." }` |
| `DELETE` | `/api/v1/chat/conversations/{id}` | Soft delete — sets `deleted_at` |

The `ConversationRecord` table also needs a `deleted_at` nullable datetime column and all existing queries need a `WHERE deleted_at IS NULL` filter.

### Environment

| Variable | Default | Notes |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend base URL |

---

## Running locally

```bash
# Backend
cd backend
cp .env.example .env
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## Database migrations

When ORM models in `backend/app/core/database.py` change, create a versioned
Alembic migration instead of adding one-off startup DDL:

```bash
cd backend
alembic revision --autogenerate -m "describe schema change"
alembic upgrade head
```

The FastAPI lifespan also runs `alembic upgrade head` on startup, so deployed
instances apply pending migrations before serving API traffic.

## Testing the chat API with curl

Create a conversation:

```bash
curl -sS http://localhost:8000/api/v1/chat/messages \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": null,
    "message": "Busca sistemas computacionales para la Municipalidad de Algarrobo entre enero y marzo 2024"
  }'
```

Continue the same conversation:

```bash
curl -sS http://localhost:8000/api/v1/chat/messages \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": "<uuid-devuelto>",
    "message": "Ahora incluye también órdenes de compra"
  }'
```

Fetch the full trace:

```bash
curl -sS http://localhost:8000/api/v1/chat/conversations/<uuid-devuelto>
```

Rename the conversation:

```bash
curl -sS -X PATCH http://localhost:8000/api/v1/chat/conversations/<uuid-devuelto> \
  -H "Content-Type: application/json" \
  -d '{ "title": "Nuevo título" }'
```

Soft-delete the conversation:

```bash
curl -sS -X DELETE -i http://localhost:8000/api/v1/chat/conversations/<uuid-devuelto>
```
