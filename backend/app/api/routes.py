"""FastAPI routes for the multi-agent audit pipeline.

Flow per request:
  1. Planner  (LLM) → Plan  { tasks: [Task, ...] }
  2. Executor (sync) → [TaskResult, ...]  (tasks run in parallel)
  3. Synthesizer (LLM) → human-readable synthesis string

Adding a new data source requires only:
  - A new tool branch in :class:`~app.services.executor.Executor._dispatch`
  - A new tool description in the Planner prompt (_PLANNER_PROMPT in minimax_client.py)
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.services.contraloria import ContraloriaService
from app.core.text import detect_text_format
from app.services.executor import Executor
from app.services.mercado_publico import MercadoPublicoClient
from app.services.minimax_client import MiniMaxClient, MiniMaxError
from app.services.models import AuditResponse
from app.services.senado_scraper import SenadoClient

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


class QueryRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        description="Natural-language audit question from the user.",
        examples=["Analiza el personal de apoyo del senador Araya en marzo 2026"],
    )


# ---------------------------------------------------------------------------
# Dependency providers
# ---------------------------------------------------------------------------

def get_minimax_client(request: Request) -> MiniMaxClient:
    return request.app.state.minimax_client

def get_mercado_publico_client(request: Request) -> MercadoPublicoClient:
    return request.app.state.mercado_publico_client

def get_senado_client(request: Request) -> SenadoClient:
    return request.app.state.senado_client

def get_contraloria_service(request: Request) -> ContraloriaService:
    return request.app.state.contraloria


# ---------------------------------------------------------------------------
# Main endpoint
# ---------------------------------------------------------------------------

@router.post(
    "/query",
    response_model=AuditResponse,
    summary="Multi-agent audit query (plan → execute → synthesize)",
)
async def audit_query(
    payload: QueryRequest,
    minimax: MiniMaxClient = Depends(get_minimax_client),
    mercado_publico: MercadoPublicoClient = Depends(get_mercado_publico_client),
    senado: SenadoClient = Depends(get_senado_client),
    contraloria: ContraloriaService = Depends(get_contraloria_service),
) -> AuditResponse:
    """
    Three-step pipeline:
    1. **Planner** — LLM produces a list of API tasks from the user message.
    2. **Executor** — runs all tasks concurrently against the real APIs.
    3. **Synthesizer** — LLM merges the results into a human-readable answer.
    """

    # ── Step 1: Plan ──────────────────────────────────────────────────────────
    try:
        plan = await minimax.create_plan(payload.message)
    except MiniMaxError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Planner failed: {exc}",
        ) from exc

    if not plan.tasks:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The planner produced an empty task list. Try rephrasing your question.",
        )

    # ── Step 2: Execute ───────────────────────────────────────────────────────
    executor = Executor(mp=mercado_publico, senado=senado, contraloria=contraloria)
    results = await executor.run(plan)

    # ── Step 3: Synthesize ────────────────────────────────────────────────────
    try:
        synthesis = await minimax.synthesize(payload.message, results)
    except MiniMaxError as exc:
        # Non-fatal: return data even if synthesis fails.
        synthesis = f"(Synthesis unavailable: {exc})"

    total_records = sum(r.record_count for r in results)
    return AuditResponse(
        plan=plan,
        results=results,
        synthesis=synthesis,
        synthesis_format=detect_text_format(synthesis),
        total_records=total_records,
    )
