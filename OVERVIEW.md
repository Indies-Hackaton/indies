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
      |-- SQLite                    → conversations, messages, LLM traces, tool runs
      |-- MiniMax Planner model      → structured API task plan
      |-- Executor                   → Mercado Público + Senado API calls
      |-- MiniMax Chat model         → natural-language response
      |
      v
{ conversation, user_message, assistant_message, planner, tool_runs, total_records }
```

`POST /api/v1/audit/query` remains available as a stateless compatibility endpoint for the older plan → execute → synthesize flow.

---

## Backend (`/backend`)

**Stack:** Python · FastAPI · httpx · Pydantic v2 · pydantic-settings · SQLAlchemy async · SQLite/aiosqlite · uvicorn

### Entry point
`backend/app/main.py`
- Creates a shared `httpx.AsyncClient`.
- Creates the async database engine and runs `CREATE TABLE IF NOT EXISTS` at startup.
- Mounts `MiniMaxClient`, `MercadoPublicoClient`, `SenadoClient`, `ContraloriaService`, and `db_sessionmaker` onto `app.state`.
- Loads both Contraloría CSV files (~120 MB total) into memory at startup.
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

### API Routes

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/chat/messages` | Create/continue a persistent conversation turn |
| `GET` | `/api/v1/chat/conversations` | List persisted conversations |
| `GET` | `/api/v1/chat/conversations/{conversation_id}` | Get messages, LLM invocations, and tool runs for one conversation |
| `POST` | `/api/v1/audit/query` | Stateless compatibility endpoint: plan → execute → synthesize |
| `GET` | `/api/v1/senado/support-staff` | Direct Senate support-staff lookup |
| `GET` | `/health` | Liveness probe |
| `GET` | `/api/hello` | Legacy connectivity check |

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
    "updated_at": "2026-05-16T00:00:00Z"
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
- `404` when `conversation_id` does not exist.
- The endpoint generally persists failures as `assistant_message.status="failed"` when the Planner cannot produce a plan.

Rendering marker:
- `user_message.content_format`, `assistant_message.content_format`, and
  `messages[].content_format` in conversation-detail responses are either
  `"plain_text"` or `"markdown"`.
- When the value is `"markdown"`, the frontend should render `content` through
  a Markdown renderer. When it is `"plain_text"`, render the string normally.
- The backend computes this marker from the generated/stored text; it does not
  mutate `content`.

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

| Table | Purpose |
|---|---|
| `conversations` | UUID conversation shell with generated title and timestamps |
| `messages` | User/assistant messages with status (`processing`, `completed`, `failed`) |
| `llm_invocations` | Title generation, Planner, and chat-response model calls; stores request/response JSON and error status |
| `tool_runs` | One row per Planner task/API execution, linked to the assistant message and planner invocation |

There is no auth yet; the conversation UUID is the access handle.

### Services

#### `ChatService` (`backend/app/services/chat_service.py`)
- Creates/reuses conversations.
- Generates a title from the first user message with `MINIMAX_CHAT_MODEL`; falls back to a short slice of the message if title generation fails.
- Persists user/assistant messages.
- Calls the Planner model with recent conversation history.
- Runs the existing `Executor` and stores every tool/API result as a `tool_run`.
- Calls the chat model to produce the final natural-language answer. The
  assistant response is expected to describe already executed results, not to
  emit `[TOOL_CALL]` blocks or future API-call instructions.

#### `MiniMaxClient` (`backend/app/services/minimax_client.py`)
- `MINIMAX_MODEL`: structured Planner/API-routing and legacy synthesis.
- `MINIMAX_CHAT_MODEL`: title generation and final user-facing responses.
- Exposes trace-returning methods so chat persistence can store model requests/responses.
- Repairs common Planner degradations before execution. For example, if the
  Planner only resolves `Municipalidad de Maipú` but the user asked for compras
  or licitaciones over a date range, the backend rewrites the plan to
  `mp_semantic_range` with the extracted organism, range, and include flags.
- Cleans generated titles and falls back to a short title from the first user
  message when the chat model returns an assistant-style sentence.
- Sanitizes chat responses that contain pseudo tool-call syntax and replaces
  them with a grounded fallback based on the executed `TaskResult` objects.

#### `Executor` (`backend/app/services/executor.py`)
Runs Planner tasks concurrently. Supported tools:

| Tool | Required params |
|---|---|
| `senado_support_staff` | `year`, `month_es`, optional `senator_name`, `staff_name` |
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
Local CSV store for Contraloría General de la República audit data. Loaded once at startup.

**Data files** (located in `data/` at the repo root):
- `Municipalidades_Contraloria.csv` — ~36 k rows, municipal audits 2020–2024
- `No_Municipales_Contraloria.csv` — ~35 k rows, non-municipal entity audits 2020–2025

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

**Startup cost:** ~1–2 s to load ~120 MB; no per-query I/O.

#### External services
- Mercado Público API: authenticated with `ticket` query param.
- Senado de Chile transparency API: unauthenticated Strapi REST endpoint.
- MiniMax: OpenAI-compatible chat-completion endpoint.
- Contraloría data: local CSV files (no external API call).

---

## Frontend (`/frontend`)

**Stack:** Next.js (App Router) · TypeScript · CSS Modules · `react-markdown`

- `NEXT_PUBLIC_API_URL` points to the backend, defaulting to `http://localhost:8000`.
- The frontend uses `POST /api/v1/chat/messages` and the conversation endpoints exclusively. The old `/api/v1/audit/query` endpoint is not used by the UI.

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
