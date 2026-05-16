"""FastAPI routes for the anti-corruption audit chatbot.

The single endpoint exposed here orchestrates the full request flow:
1. Send the user's message to MiniMax for intent classification.
2. Dispatch to the matching Mercado Publico query.
3. Return the procurement data (lightly wrapped) to the caller.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.services.mercado_publico import MercadoPublicoClient, MercadoPublicoError
from app.services.minimax_client import Intent, MiniMaxClient, MiniMaxError

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


class QueryRequest(BaseModel):
    """Request body for the audit query endpoint."""

    message: str = Field(
        ...,
        min_length=1,
        description="Natural-language audit question from the user.",
        examples=["Show me purchase orders for organism 7239 on 2024-02-05"],
    )


class QueryResponse(BaseModel):
    """Response returned by the audit query endpoint."""

    # The structured routing decision produced by the LLM.
    intent: Intent
    # Raw/lightly-structured payload from Mercado Publico (None when unrouted).
    data: dict[str, Any] | None = None
    # Human-readable note, e.g. when the intent could not be mapped to a tool.
    detail: str | None = None


# --- Dependency providers --------------------------------------------------
# The service clients are created once at startup (see app.main.lifespan) and
# stored on ``app.state``. These helpers expose them to the route via FastAPI's
# dependency-injection system, which keeps the handler easy to test/mock.


def get_minimax_client(request: Request) -> MiniMaxClient:
    """Return the shared :class:`MiniMaxClient` from application state."""
    return request.app.state.minimax_client


def get_mercado_publico_client(request: Request) -> MercadoPublicoClient:
    """Return the shared :class:`MercadoPublicoClient` from application state."""
    return request.app.state.mercado_publico_client


@router.post(
    "/query",
    response_model=QueryResponse,
    summary="Route an audit question and fetch procurement data",
)
async def audit_query(
    payload: QueryRequest,
    minimax: MiniMaxClient = Depends(get_minimax_client),
    mercado_publico: MercadoPublicoClient = Depends(get_mercado_publico_client),
) -> QueryResponse:
    """Classify the user's message and return matching Mercado Publico data."""

    # 1. Ask the LLM which tool to use and extract its parameters.
    try:
        intent = await minimax.classify_intent(payload.message)
    except MiniMaxError as exc:
        # 502: an upstream dependency (the LLM) failed.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Intent analysis failed: {exc}",
        ) from exc

    # 2. Dispatch to the correct Mercado Publico query.
    params = intent.parameters
    try:
        if intent.tool == "orders_by_org_and_date":
            if not params.codigoorg or not params.fecha:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="This query requires both 'codigoorg' and 'fecha'.",
                )
            data = await mercado_publico.get_orders_by_org_and_date(
                codigoorg=params.codigoorg, fecha=params.fecha
            )

        elif intent.tool == "orders_by_date":
            if not params.fecha:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="This query requires a 'fecha'.",
                )
            data = await mercado_publico.get_orders_by_date(fecha=params.fecha)

        else:
            # The LLM could not map the request to a supported tool.
            return QueryResponse(
                intent=intent,
                detail="Could not map the request to a known audit tool.",
            )
    except MercadoPublicoError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    # 3. Return the procurement payload alongside the routing decision.
    return QueryResponse(intent=intent, data=data)
