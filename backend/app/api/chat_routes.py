"""Persistent conversational chat routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.chat_service import ChatNotFoundError, ChatService
from app.services.mercado_publico import MercadoPublicoClient
from app.services.minimax_client import MiniMaxClient
from app.services.models import (
    ChatMessageResponse,
    ConversationDetailResponse,
    ConversationListItem,
)
from app.services.senado_scraper import SenadoClient

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


class ChatMessageRequest(BaseModel):
    """Request body for a persistent chat turn."""

    conversation_id: str | None = Field(
        default=None,
        description="Existing conversation UUID. Omit/null to start a conversation.",
    )
    message: str = Field(
        ...,
        min_length=1,
        description="Natural-language user message.",
    )


def get_sessionmaker(request: Request) -> async_sessionmaker[AsyncSession]:
    return request.app.state.db_sessionmaker


def get_minimax_client(request: Request) -> MiniMaxClient:
    return request.app.state.minimax_client


def get_mercado_publico_client(request: Request) -> MercadoPublicoClient:
    return request.app.state.mercado_publico_client


def get_senado_client(request: Request) -> SenadoClient:
    return request.app.state.senado_client


SessionFactory = Annotated[
    async_sessionmaker[AsyncSession],
    Depends(get_sessionmaker),
]


@router.post(
    "/messages",
    response_model=ChatMessageResponse,
    summary="Send a persistent conversational audit message",
)
async def send_chat_message(
    payload: ChatMessageRequest,
    sessionmaker: SessionFactory,
    minimax: MiniMaxClient = Depends(get_minimax_client),
    mercado_publico: MercadoPublicoClient = Depends(get_mercado_publico_client),
    senado: SenadoClient = Depends(get_senado_client),
) -> ChatMessageResponse:
    """Create or continue a conversation and return the assistant response."""
    async with sessionmaker() as session:
        service = ChatService(
            session=session,
            minimax=minimax,
            mercado_publico=mercado_publico,
            senado=senado,
        )
        try:
            return await service.handle_message(
                conversation_id=payload.conversation_id,
                message=payload.message,
            )
        except ChatNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc


@router.get(
    "/conversations",
    response_model=list[ConversationListItem],
    summary="List persisted conversations",
)
async def list_conversations(
    sessionmaker: SessionFactory,
    minimax: MiniMaxClient = Depends(get_minimax_client),
    mercado_publico: MercadoPublicoClient = Depends(get_mercado_publico_client),
    senado: SenadoClient = Depends(get_senado_client),
) -> list[ConversationListItem]:
    """Return conversation metadata ordered by recent activity."""
    async with sessionmaker() as session:
        service = ChatService(
            session=session,
            minimax=minimax,
            mercado_publico=mercado_publico,
            senado=senado,
        )
        return await service.list_conversations()


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationDetailResponse,
    summary="Get a conversation with messages and execution traces",
)
async def get_conversation(
    conversation_id: str,
    sessionmaker: SessionFactory,
    minimax: MiniMaxClient = Depends(get_minimax_client),
    mercado_publico: MercadoPublicoClient = Depends(get_mercado_publico_client),
    senado: SenadoClient = Depends(get_senado_client),
) -> ConversationDetailResponse:
    """Return a full conversation, including linked LLM and API traces."""
    async with sessionmaker() as session:
        service = ChatService(
            session=session,
            minimax=minimax,
            mercado_publico=mercado_publico,
            senado=senado,
        )
        try:
            return await service.get_conversation(conversation_id)
        except ChatNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc
