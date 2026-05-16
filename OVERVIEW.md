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
| `MINIMAX_BASE_URL` | `https://api.minimax.io/v1` | |
| `MINIMAX_MODEL` | `MiniMax-Text-01` | |
| `MERCADO_PUBLICO_TICKET` | — | Required |
| `MERCADO_PUBLICO_BASE_URL` | `https://api.mercadopublico.cl/servicios/v1/publico` | |
| `FRONTEND_ORIGINS` | `http://localhost:3000,...` | Comma-separated |

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
  - `tool`: `"orders_by_org_and_date"` | `"orders_by_date"` | `"unknown"`
  - `parameters.codigoorg`: organism code or `null`
  - `parameters.fecha`: date in `ddmmyyyy` or `null`
  - `reasoning`: one-sentence explanation
- Temperature `0.1` keeps routing deterministic.
- Defensively strips markdown fences from LLM output.

#### `MercadoPublicoClient` (`backend/app/services/mercado_publico.py`)
- Wraps `https://api.mercadopublico.cl/servicios/v1/publico`
- Endpoint used: `ordenesdecompra.json`
- Auth: `ticket` query param injected automatically.

| Method | Mercado Público params |
|---|---|
| `get_orders_by_org_and_date(codigoorg, fecha)` | `CodigoOrganismo` + `fecha` |
| `get_orders_by_date(fecha)` | `fecha` only |

---

## Frontend (`/frontend`)

**Stack:** Next.js (App Router) · TypeScript · vanilla CSS custom properties

- `NEXT_PUBLIC_API_URL` env var points to backend (default `http://localhost:8000`).
- Currently a starter status page — **needs to be replaced with the chat UI**.
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
| `orders_by_org_and_date` | `codigoorg` + `fecha` | "Show orders for organism 7239 on Feb 5 2024" |
| `orders_by_date` | `fecha` | "Show all orders from 05/02/2024" |
| `unknown` | — | Unrecognized / incomplete requests |
