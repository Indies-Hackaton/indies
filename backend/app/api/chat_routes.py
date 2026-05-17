"""Persistent conversational chat routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.chat_service import ChatNotFoundError, ChatService
from app.services.camara import CamaraService
from app.services.contraloria import ContraloriaService
from app.services.mercado_publico import MercadoPublicoClient
from app.services.minimax_client import MiniMaxClient
from app.services.models import (
    ChatMessageResponse,
    ConversationDetailResponse,
    ConversationListItem,
    ConversationOut,
    FeedbackRating,
    MessageOut,
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


class ConversationUpdateRequest(BaseModel):
    """Request body for updating conversation metadata."""

    title: str = Field(
        ...,
        min_length=1,
        max_length=160,
        description="New conversation title.",
    )

    @field_validator("title")
    @classmethod
    def title_must_have_text(cls, value: str) -> str:
        title = value.strip()
        if not title:
            raise ValueError("Title must not be empty.")
        return title


class MessageFeedbackRequest(BaseModel):
    """Request body for updating like/dislike feedback on one message."""

    feedback_rating: FeedbackRating | None = Field(
        ...,
        description="Set to 'like' or 'dislike'; set null to clear the rating.",
    )


class ConversationFeedbackRequest(BaseModel):
    """Request body for updating overall conversation feedback."""

    feedback_rating: FeedbackRating | None = Field(
        default=None,
        description="Set to 'like' or 'dislike'; set null to clear the rating.",
    )
    feedback_text: str | None = Field(
        default=None,
        max_length=4000,
        description="Optional free-form user feedback; set null to clear it.",
    )

    @field_validator("feedback_text", mode="before")
    @classmethod
    def feedback_text_must_have_text(cls, value: object) -> object:
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        feedback_text = value.strip()
        return feedback_text or None


def get_sessionmaker(request: Request) -> async_sessionmaker[AsyncSession]:
    return request.app.state.db_sessionmaker


def get_minimax_client(request: Request) -> MiniMaxClient:
    return request.app.state.minimax_client


def get_mercado_publico_client(request: Request) -> MercadoPublicoClient:
    return request.app.state.mercado_publico_client


def get_senado_client(request: Request) -> SenadoClient:
    return request.app.state.senado_client


def get_contraloria_service(request: Request) -> ContraloriaService:
    return request.app.state.contraloria

def get_camara_service(request: Request) -> CamaraService:
    return request.app.state.camara


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
    contraloria: ContraloriaService = Depends(get_contraloria_service),
    camara: CamaraService = Depends(get_camara_service),
) -> ChatMessageResponse:
    """Create or continue a conversation and return the assistant response."""
    async with sessionmaker() as session:
        service = ChatService(
            session=session,
            minimax=minimax,
            mercado_publico=mercado_publico,
            senado=senado,
            contraloria=contraloria,
            camara=camara,
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


@router.patch(
    "/messages/{message_id}/feedback",
    response_model=MessageOut,
    summary="Set or clear like/dislike feedback for a chat message",
)
async def update_message_feedback(
    message_id: str,
    payload: MessageFeedbackRequest,
    sessionmaker: SessionFactory,
    minimax: MiniMaxClient = Depends(get_minimax_client),
    mercado_publico: MercadoPublicoClient = Depends(get_mercado_publico_client),
    senado: SenadoClient = Depends(get_senado_client),
    contraloria: ContraloriaService = Depends(get_contraloria_service),
) -> MessageOut:
    """Persist like/dislike feedback for any message in an active conversation."""
    async with sessionmaker() as session:
        service = ChatService(
            session=session,
            minimax=minimax,
            mercado_publico=mercado_publico,
            senado=senado,
            contraloria=contraloria,
        )
        try:
            return await service.update_message_feedback(
                message_id,
                feedback_rating=payload.feedback_rating,
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
    contraloria: ContraloriaService = Depends(get_contraloria_service),
    camara: CamaraService = Depends(get_camara_service),
) -> list[ConversationListItem]:
    """Return conversation metadata ordered by recent activity."""
    async with sessionmaker() as session:
        service = ChatService(
            session=session,
            minimax=minimax,
            mercado_publico=mercado_publico,
            senado=senado,
            contraloria=contraloria,
            camara=camara,
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
    contraloria: ContraloriaService = Depends(get_contraloria_service),
    camara: CamaraService = Depends(get_camara_service),
) -> ConversationDetailResponse:
    """Return a full conversation, including linked LLM and API traces."""
    async with sessionmaker() as session:
        service = ChatService(
            session=session,
            minimax=minimax,
            mercado_publico=mercado_publico,
            senado=senado,
            contraloria=contraloria,
            camara=camara,
        )
        try:
            return await service.get_conversation(conversation_id)
        except ChatNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc


@router.patch(
    "/conversations/{conversation_id}",
    response_model=ConversationOut,
    summary="Rename a conversation",
)
async def rename_conversation(
    conversation_id: str,
    payload: ConversationUpdateRequest,
    sessionmaker: SessionFactory,
    minimax: MiniMaxClient = Depends(get_minimax_client),
    mercado_publico: MercadoPublicoClient = Depends(get_mercado_publico_client),
    senado: SenadoClient = Depends(get_senado_client),
    contraloria: ContraloriaService = Depends(get_contraloria_service),
) -> ConversationOut:
    """Rename an active conversation."""
    async with sessionmaker() as session:
        service = ChatService(
            session=session,
            minimax=minimax,
            mercado_publico=mercado_publico,
            senado=senado,
            contraloria=contraloria,
        )
        try:
            return await service.rename_conversation(conversation_id, payload.title)
        except ChatNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc


@router.patch(
    "/conversations/{conversation_id}/feedback",
    response_model=ConversationOut,
    summary="Set or clear overall conversation feedback",
)
async def update_conversation_feedback(
    conversation_id: str,
    payload: ConversationFeedbackRequest,
    sessionmaker: SessionFactory,
    minimax: MiniMaxClient = Depends(get_minimax_client),
    mercado_publico: MercadoPublicoClient = Depends(get_mercado_publico_client),
    senado: SenadoClient = Depends(get_senado_client),
    contraloria: ContraloriaService = Depends(get_contraloria_service),
) -> ConversationOut:
    """Persist like/dislike and optional free-form feedback for a conversation."""
    fields_set = payload.model_fields_set
    if not fields_set:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one feedback field must be provided.",
        )

    async with sessionmaker() as session:
        service = ChatService(
            session=session,
            minimax=minimax,
            mercado_publico=mercado_publico,
            senado=senado,
            contraloria=contraloria,
        )
        try:
            return await service.update_conversation_feedback(
                conversation_id,
                feedback_rating=payload.feedback_rating,
                feedback_text=payload.feedback_text,
                update_rating="feedback_rating" in fields_set,
                update_text="feedback_text" in fields_set,
            )
        except ChatNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Soft-delete a conversation",
)
async def delete_conversation(
    conversation_id: str,
    sessionmaker: SessionFactory,
    minimax: MiniMaxClient = Depends(get_minimax_client),
    mercado_publico: MercadoPublicoClient = Depends(get_mercado_publico_client),
    senado: SenadoClient = Depends(get_senado_client),
    contraloria: ContraloriaService = Depends(get_contraloria_service),
) -> Response:
    """Soft-delete an active conversation while preserving messages and traces."""
    async with sessionmaker() as session:
        service = ChatService(
            session=session,
            minimax=minimax,
            mercado_publico=mercado_publico,
            senado=senado,
            contraloria=contraloria,
        )
        try:
            await service.delete_conversation(conversation_id)
        except ChatNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
