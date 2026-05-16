# Indies — Project Overview

**What it is:** An anti-corruption audit chatbot for Chilean public procurement. Users ask natural-language questions; the system classifies the intent with an LLM and fetches real procurement data from the Chilean government's Mercado Público API.

---

## Architecture

```
[Next.js Frontend]
      |
      | POST /api/v1/audit/query  { message: "..." }
      v
[FastAPI Backend]
      |
      |-- (1) MiniMax LLM  →  classify intent + extract params
      |-- (2) Mercado Público API  →  fetch procurement data
      |
      v
{ intent, data, detail }
```

---

## Backend (`/backend`)

**Stack:** Python · FastAPI · httpx · Pydantic v2 · pydantic-settings · uvicorn

### Entry point
`backend/app/main.py`
- Creates the FastAPI app with a `lifespan` context that spins up a shared `httpx.AsyncClient` (connection pooling).
- Mounts `MiniMaxClient` and `MercadoPublicoClient` onto `app.state` for DI.
- Enables CORS for origins in `FRONTEND_ORIGINS` env var.

### Config
`backend/app/core/config.py` — `Settings` (pydantic-settings, reads `.env`)

| Variable | Default | Notes |
|---|---|---|
| `MINIMAX_API_KEY` | — | Required |
| `MINIMAX_BASE_URL` | — | Required; example in `backend/.env.example`: `https://api.minimax.io/v1` |
| `MINIMAX_MODEL` | — | Required; example in `backend/.env.example`: `MiniMax-Text-01` |
| `MERCADO_PUBLICO_TICKET` | — | Required |
| `MERCADO_PUBLICO_BASE_URL` | — | Required; example in `backend/.env.example`: `https://api.mercadopublico.cl/servicios/v1/publico` |
| `FRONTEND_ORIGINS` | — | Required; comma-separated frontend origins allowed by CORS. Set this in production, e.g. `https://indies-99li.vercel.app`. Values are normalized, so accidental trailing slashes or full URLs are reduced to `scheme://host[:port]`. |

### API Routes
`backend/app/api/routes.py` — prefix `/api/v1/audit`

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/audit/query` | Main endpoint — classify + fetch |
| `GET` | `/health` | Liveness probe |
| `GET` | `/api/hello` | Legacy connectivity check |

**Request body:**
```json
{ "message": "Show me purchase orders for organism 7239 on 2024-02-05" }
```

**Response:**
```json
{
  "intent": {
    "tool": "orders_by_org_and_date",
    "parameters": { "codigoorg": "7239", "fecha": "05022024" },
    "reasoning": "User specified both organism and date."
  },
  "data": { /* raw Mercado Público JSON */ },
  "detail": null
}
```

### Services

#### `MiniMaxClient` (`backend/app/services/minimax_client.py`)
- Sends user message to MiniMax with a strict system prompt.
- Model must reply with a single JSON object matching `Intent`:
  - `tool`: one of the supported query intents listed below.
  - `parameters.codigoorg` / `parameters.codigo_organismo`: organism code or `null`
  - `parameters.fecha`: single date in `ddmmyyyy` or `null`
  - `parameters.codigo`: tender code / Codigo de Licitacion or `null`
  - `parameters.estado`: tender status name/code or `null`
  - `parameters.codigo_proveedor`: supplier code or `null`
  - `parameters.organism_name`: public organism name to resolve or `null`
  - `parameters.keywords`: semantic product/service terms
  - `parameters.start_date` / `parameters.end_date`: inclusive range bounds in `ddmmyyyy`
  - `parameters.include_orders` / `parameters.include_tenders`: source flags for semantic range search
  - `reasoning`: one-sentence explanation
- Temperature `0.1` keeps routing deterministic.
- Defensively strips markdown fences from LLM output.

#### `MercadoPublicoClient` (`backend/app/services/mercado_publico.py`)
- Wraps `https://api.mercadopublico.cl/servicios/v1/publico`
- Endpoints used: `ordenesdecompra.json`, `licitaciones.json`, and `Empresas/BuscarComprador`
- Auth: `ticket` query param injected automatically.
- Retries retryable Mercado Publico failures (`429`, `500`, `502`, `503`, `504`) before surfacing a `502` from the API route.
- Resolves named public organisms via `BuscarComprador`; if several municipality/corporation entities match, the backend returns an ambiguity payload instead of guessing.

| Method | Mercado Público params |
|---|---|
| `get_orders_by_org_and_date(codigoorg, fecha)` | `CodigoOrganismo` + `fecha` |
| `get_orders_by_date(fecha)` | `fecha` only |
| `lookup_public_organisms()` | `ticket` only against `Empresas/BuscarComprador` |
| `resolve_public_organism(name)` | Local resolution over `BuscarComprador` results |
| `get_tender_by_code(codigo)` | `codigo` |
| `get_tenders_current_day()` | `ticket` only against `licitaciones.json` |
| `get_tenders_by_date(fecha)` | `fecha` |
| `get_tenders_by_status_and_date(fecha, estado)` | `fecha` + normalized `estado` |
| `get_tenders_by_supplier_and_date(fecha, codigo_proveedor)` | `fecha` + `CodigoProveedor` |
| `get_tenders_by_org_and_date(codigo_organismo, fecha)` | `fecha` + `CodigoOrganismo` |

#### Semantic range workflow (`backend/app/api/routes.py`)
- `semantic_org_date_range_search` is implemented in the route layer because it orchestrates multiple Mercado Publico calls.
- Requires `start_date`, `end_date`, keywords, and either an organism code or `organism_name`.
- Expands the inclusive date range, capped at 366 days.
- Queries tenders by default. It also queries purchase orders when `include_orders` is `true`.
- Filters returned records with `pandas` across descriptive columns such as name, description, product, category, item, acquisition, tender and glossary fields.

---

## Frontend (`/frontend`)

**Stack:** Next.js (App Router) · TypeScript · vanilla CSS custom properties

- `NEXT_PUBLIC_API_URL` env var points to backend (default `http://localhost:8000`).
- Home page is a chat-style audit UI that sends questions to `POST /api/v1/audit/query`.
- Renders a receipt per query with the original question, model intent, Mercado Público query and returned data.
- Design tokens in `globals.css`: `--accent: #0f766e` (teal), `--background: #f7f7f2` (off-white).

---

## Running locally

```bash
# Backend
cd backend
cp .env.example .env   # fill in MINIMAX_API_KEY + MERCADO_PUBLICO_TICKET
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
```

---

## Supported query intents

| Intent tool | Required params | Example question |
|---|---|---|
| `orders_by_org_and_date` | `fecha` + `codigoorg`, `codigo_organismo`, or `organism_name` | "Show orders for organism 7239 on Feb 5 2024" |
| `orders_by_date` | `fecha` | "Show all orders from 05/02/2024" |
| `public_organism_lookup` | optional `organism_name` | "Verify the public organism for Municipalidad de Algarrobo" |
| `tender_by_code` | `codigo` | "Find tender 1509-5-L114" |
| `tenders_current_day` | — | "What tenders are available today?" |
| `tenders_by_date` | `fecha` | "Show tenders from 05/02/2024" |
| `tenders_by_status_and_date` | `fecha` + `estado` | "Show adjudicated tenders from 05/02/2024" |
| `tenders_by_supplier_and_date` | `fecha` + `codigo_proveedor` | "Show supplier 76543210 tenders from 05/02/2024" |
| `tenders_by_org_and_date` | `fecha` + `codigoorg`, `codigo_organismo`, or `organism_name` | "Show Municipalidad de Algarrobo tenders from 05/02/2024" |
| `semantic_org_date_range_search` | `start_date` + `end_date` + keywords + organism | "Find computer systems for Municipalidad de Algarrobo between January and March 2024" |
| `unknown` | — | Unrecognized / incomplete requests |

For detailed agent capabilities and full request/response examples, see `specs.md`.
