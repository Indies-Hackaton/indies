# Indies

Proyecto base con FastAPI para el backend y Next.js para el frontend.

## Estructura

```text
backend/   API con FastAPI
frontend/  App web con Next.js
```

## Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

La API queda en `http://localhost:8000`.

Endpoints iniciales:

- `GET /health`
- `GET /api/hello`

## Frontend

```bash
cd frontend
npm install
npm run dev
```

La app queda en `http://localhost:3000`.

Para apuntar el frontend a otra API, crea `frontend/.env.local`:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```
