"""FastAPI application initialisation for the Indies audit API.

This module wires together configuration, the shared async HTTP client, the
service clients (MiniMax + Mercado Publico) and the API router.
"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.api.chat_routes import router as chat_router
from app.api.routes import router as audit_router
from app.api.senado_routes import router as senado_router
from app.core.config import get_settings
from app.core.database import init_db, make_engine, make_sessionmaker
from app.services.contraloria import ContraloriaService
from app.services.mercado_publico import MercadoPublicoClient
from app.services.minimax_client import MiniMaxClient
from app.services.senado_scraper import SenadoClient


class HelloResponse(BaseModel):
    """Response model for the legacy connectivity-check endpoint."""

    message: str


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage resources tied to the application lifecycle.

    A single :class:`httpx.AsyncClient` is created at startup and shared by all
    service clients, enabling connection pooling/keep-alive. It is closed
    cleanly on shutdown to avoid leaking sockets.
    """
    settings = get_settings()

    http_client = httpx.AsyncClient(timeout=httpx.Timeout(30.0))
    db_engine = make_engine(settings.DATABASE_URL)
    await init_db(db_engine)

    # Expose shared resources on app.state so routes can resolve them via DI.
    app.state.http_client = http_client
    app.state.db_engine = db_engine
    app.state.db_sessionmaker = make_sessionmaker(db_engine)
    app.state.minimax_client = MiniMaxClient(settings, http_client)
    app.state.mercado_publico_client = MercadoPublicoClient(settings, http_client)
    app.state.senado_client = SenadoClient(http_client)
    _data_dir = Path(__file__).parent.parent.parent / "data"  # indies/data/
    app.state.contraloria = ContraloriaService(
        municipalidades_path=str(_data_dir / "Municipalidades_Contraloria.csv"),
        no_municipales_path=str(_data_dir / "No_Municipales_Contraloria.csv"),
    )

    try:
        yield
    finally:
        await http_client.aclose()
        await db_engine.dispose()


app = FastAPI(title="Indies Audit API", version="0.2.0", lifespan=lifespan)

# CORS must be configured before the app starts serving requests.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the audit chatbot router (POST /api/v1/audit/query).
app.include_router(audit_router)
# Mount persistent chat routes (POST /api/v1/chat/messages).
app.include_router(chat_router)
# Mount the Senate transparency scraper router (GET /api/v1/senado/support-staff).
app.include_router(senado_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Lightweight liveness probe."""
    return {"status": "ok"}


@app.get("/api/hello", response_model=HelloResponse)
async def hello() -> HelloResponse:
    """Connectivity check consumed by the Next.js frontend."""
    return HelloResponse(message="Hola desde FastAPI")
