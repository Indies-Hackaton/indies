"""Persistent conversational orchestration for the audit assistant."""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import (
    ConversationRecord,
    LlmInvocationRecord,
    MessageRecord,
    ToolRunRecord,
    utc_now,
)
from app.services.camara import CamaraService
from app.services.contraloria import ContraloriaService
from app.core.text import detect_text_format
from app.services.executor import Executor
from app.services.mercado_publico import MercadoPublicoClient
from app.services.minimax_client import MiniMaxClient, MiniMaxError
from app.services.models import (
    ChatMessageResponse,
    ChatPlannerOut,
    ConversationDetailResponse,
    ConversationListItem,
    ConversationOut,
    FeedbackRating,
    LlmInvocationOut,
    MessageOut,
    Plan,
    TaskResult,
    ToolRunOut,
)
from app.services.senado_scraper import SenadoClient


class ChatNotFoundError(RuntimeError):
    """Raised when a conversation UUID does not exist."""


class ChatService:
    """Coordinates persistent chat messages, LLM calls, and API tool runs."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        minimax: MiniMaxClient,
        mercado_publico: MercadoPublicoClient,
        senado: SenadoClient,
        contraloria: ContraloriaService,
        camara: CamaraService,
    ) -> None:
        self._session = session
        self._minimax = minimax
        self._mercado_publico = mercado_publico
        self._senado = senado
        self._contraloria = contraloria
        self._camara = camara

    async def handle_message(
        self,
        *,
        conversation_id: str | None,
        message: str,
    ) -> ChatMessageResponse:
        """Persist a user message, run the audit pipeline, and persist traces."""
        conversation = await self._get_or_create_conversation(
            conversation_id=conversation_id,
            first_message=message,
        )

        user_message = MessageRecord(
            id=_new_id(),
            conversation_id=conversation.id,
            role="user",
            content=message,
            status="completed",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        conversation.updated_at = utc_now()
        self._session.add(user_message)
        await self._session.commit()

        if conversation_id is None:
            await self._generate_and_store_title(conversation, message)

        assistant_message = MessageRecord(
            id=_new_id(),
            conversation_id=conversation.id,
            role="assistant",
            content="Procesando la consulta...",
            status="processing",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        conversation.updated_at = utc_now()
        self._session.add(assistant_message)
        await self._session.commit()

        history = await self._history_for_llm(
            conversation.id,
            exclude_message_id=user_message.id,
        )
        planner_invocation: LlmInvocationRecord | None = None
        plan: Plan | None = None
        results: list[TaskResult] = []
        tool_runs: list[ToolRunRecord] = []

        try:
            plan, request_json, response_json = await self._minimax.create_plan_with_trace(
                message,
                history=history,
            )
            planner_invocation = await self._store_llm_invocation(
                conversation_id=conversation.id,
                assistant_message_id=assistant_message.id,
                purpose="planner",
                model=self._minimax.planner_model,
                request_json=request_json,
                response_json=response_json,
                status="ok",
            )
        except MiniMaxError as exc:
            planner_invocation = await self._store_llm_invocation(
                conversation_id=conversation.id,
                assistant_message_id=assistant_message.id,
                purpose="planner",
                model=self._minimax.planner_model,
                request_json={
                    "model": self._minimax.planner_model,
                    "message": message,
                    "history": history,
                },
                response_json=None,
                status="error",
                error=str(exc),
            )
            await self._finish_assistant_message(
                assistant_message,
                (
                    "No pude planificar las llamadas necesarias para responder "
                    f"esta consulta. Detalle: {exc}"
                ),
                status="failed",
            )
            return await self._build_message_response(
                conversation,
                user_message,
                assistant_message,
                planner_invocation=planner_invocation,
                plan=None,
                tool_runs=[],
                total_records=0,
            )

        executor = Executor(mp=self._mercado_publico, senado=self._senado, contraloria=self._contraloria, camara=self._camara)
        results = await executor.run(plan)
        tool_runs = await self._store_tool_runs(
            conversation_id=conversation.id,
            assistant_message_id=assistant_message.id,
            planner_invocation_id=planner_invocation.id,
            plan=plan,
            results=results,
        )

        total_records = sum(result.record_count for result in results)
        try:
            answer, request_json, response_json = (
                await self._minimax.generate_chat_response_with_trace(
                    history=history,
                    user_message=message,
                    plan=plan,
                    results=results,
                )
            )
            await self._store_llm_invocation(
                conversation_id=conversation.id,
                assistant_message_id=assistant_message.id,
                purpose="chat_response",
                model=self._minimax.chat_model,
                request_json=request_json,
                response_json=response_json,
                status="ok",
            )
        except MiniMaxError as exc:
            answer = _fallback_answer(total_records, results, str(exc))
            await self._store_llm_invocation(
                conversation_id=conversation.id,
                assistant_message_id=assistant_message.id,
                purpose="chat_response",
                model=self._minimax.chat_model,
                request_json={
                    "model": self._minimax.chat_model,
                    "message": message,
                    "history": history,
                    "plan": plan.model_dump(),
                    "results": [result.model_dump() for result in results],
                },
                response_json=None,
                status="error",
                error=str(exc),
            )

        await self._finish_assistant_message(
            assistant_message,
            answer,
            status="completed",
        )
        return await self._build_message_response(
            conversation,
            user_message,
            assistant_message,
            planner_invocation=planner_invocation,
            plan=plan,
            tool_runs=tool_runs,
            total_records=total_records,
        )

    async def list_conversations(self) -> list[ConversationListItem]:
        """Return conversations ordered by recent activity."""
        rows = (
            await self._session.scalars(
                select(ConversationRecord)
                .where(ConversationRecord.deleted_at.is_(None))
                .order_by(ConversationRecord.updated_at.desc())
            )
        ).all()
        items: list[ConversationListItem] = []
        for conversation in rows:
            last_message = (
                await self._session.scalars(
                    select(MessageRecord)
                    .where(MessageRecord.conversation_id == conversation.id)
                    .order_by(MessageRecord.created_at.desc())
                    .limit(1)
                )
            ).first()
            message_count = await self._session.scalar(
                select(func.count(MessageRecord.id)).where(
                    MessageRecord.conversation_id == conversation.id
                )
            )
            items.append(
                ConversationListItem(
                    **_conversation_out(conversation).model_dump(),
                    last_message=(
                        _message_out(last_message) if last_message else None
                    ),
                    message_count=int(message_count or 0),
                )
            )
        return items

    async def get_conversation(self, conversation_id: str) -> ConversationDetailResponse:
        """Return a persisted conversation with messages and traces."""
        conversation = await self._get_active_conversation(conversation_id)

        messages = (
            await self._session.scalars(
                select(MessageRecord)
                .where(MessageRecord.conversation_id == conversation.id)
                .order_by(MessageRecord.created_at.asc())
            )
        ).all()
        invocations = (
            await self._session.scalars(
                select(LlmInvocationRecord)
                .where(LlmInvocationRecord.conversation_id == conversation.id)
                .order_by(LlmInvocationRecord.created_at.asc())
            )
        ).all()
        tool_runs = (
            await self._session.scalars(
                select(ToolRunRecord)
                .where(ToolRunRecord.conversation_id == conversation.id)
                .order_by(ToolRunRecord.created_at.asc())
            )
        ).all()

        invocation_links: dict[str, list[str]] = {}
        for invocation in invocations:
            if invocation.assistant_message_id:
                invocation_links.setdefault(invocation.assistant_message_id, []).append(
                    invocation.id
                )
        tool_links: dict[str, list[str]] = {}
        for tool_run in tool_runs:
            tool_links.setdefault(tool_run.assistant_message_id, []).append(
                tool_run.id
            )

        return ConversationDetailResponse(
            conversation=_conversation_out(conversation),
            messages=[
                _message_out(
                    message,
                    linked_invocation_ids=invocation_links.get(message.id, []),
                    linked_tool_run_ids=tool_links.get(message.id, []),
                )
                for message in messages
            ],
            llm_invocations=[_llm_invocation_out(row) for row in invocations],
            tool_runs=[_tool_run_out(row) for row in tool_runs],
        )

    async def rename_conversation(
        self,
        conversation_id: str,
        title: str,
    ) -> ConversationOut:
        """Rename an active conversation."""
        conversation = await self._get_active_conversation(conversation_id)
        conversation.title = title
        conversation.updated_at = utc_now()
        await self._session.commit()
        return _conversation_out(conversation)

    async def update_conversation_feedback(
        self,
        conversation_id: str,
        *,
        feedback_rating: FeedbackRating | None,
        feedback_text: str | None,
        update_rating: bool,
        update_text: bool,
    ) -> ConversationOut:
        """Set, update, or clear user feedback for an active conversation."""
        conversation = await self._get_active_conversation(conversation_id)
        if update_rating:
            conversation.feedback_rating = feedback_rating
        if update_text:
            conversation.feedback_text = feedback_text
        conversation.feedback_updated_at = utc_now()
        await self._session.commit()
        return _conversation_out(conversation)

    async def update_message_feedback(
        self,
        message_id: str,
        *,
        feedback_rating: FeedbackRating | None,
    ) -> MessageOut:
        """Set or clear like/dislike feedback for a message in an active conversation."""
        message = await self._get_active_message(message_id)
        message.feedback_rating = feedback_rating
        message.feedback_updated_at = utc_now()
        await self._session.commit()
        return _message_out(message)

    async def delete_conversation(self, conversation_id: str) -> None:
        """Soft-delete an active conversation while preserving its audit trail."""
        conversation = await self._get_active_conversation(conversation_id)
        conversation.deleted_at = utc_now()
        await self._session.commit()

    async def _get_or_create_conversation(
        self,
        *,
        conversation_id: str | None,
        first_message: str,
    ) -> ConversationRecord:
        if conversation_id:
            return await self._get_active_conversation(conversation_id)

        conversation = ConversationRecord(
            id=_new_id(),
            title=_fallback_title(first_message),
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self._session.add(conversation)
        await self._session.commit()
        return conversation

    async def _get_active_conversation(self, conversation_id: str) -> ConversationRecord:
        conversation = await self._session.scalar(
            select(ConversationRecord)
            .where(ConversationRecord.id == conversation_id)
            .where(ConversationRecord.deleted_at.is_(None))
        )
        if not conversation:
            raise ChatNotFoundError(f"Conversation {conversation_id!r} not found.")
        return conversation

    async def _get_active_message(self, message_id: str) -> MessageRecord:
        message = await self._session.scalar(
            select(MessageRecord)
            .join(
                ConversationRecord,
                MessageRecord.conversation_id == ConversationRecord.id,
            )
            .where(MessageRecord.id == message_id)
            .where(ConversationRecord.deleted_at.is_(None))
        )
        if not message:
            raise ChatNotFoundError(f"Message {message_id!r} not found.")
        return message

    async def _generate_and_store_title(
        self,
        conversation: ConversationRecord,
        first_message: str,
    ) -> None:
        try:
            title, request_json, response_json = (
                await self._minimax.generate_title_with_trace(first_message)
            )
            conversation.title = title or _fallback_title(first_message)
            conversation.updated_at = utc_now()
            await self._store_llm_invocation(
                conversation_id=conversation.id,
                assistant_message_id=None,
                purpose="title_generation",
                model=self._minimax.chat_model,
                request_json=request_json,
                response_json=response_json,
                status="ok",
            )
        except MiniMaxError as exc:
            await self._store_llm_invocation(
                conversation_id=conversation.id,
                assistant_message_id=None,
                purpose="title_generation",
                model=self._minimax.chat_model,
                request_json={
                    "model": self._minimax.chat_model,
                    "message": first_message,
                },
                response_json=None,
                status="error",
                error=str(exc),
            )
        await self._session.commit()

    async def _history_for_llm(
        self,
        conversation_id: str,
        *,
        exclude_message_id: str | None = None,
        limit: int = 12,
    ) -> list[dict[str, str]]:
        query = (
            select(MessageRecord)
            .where(MessageRecord.conversation_id == conversation_id)
            .where(MessageRecord.status == "completed")
        )
        if exclude_message_id:
            query = query.where(MessageRecord.id != exclude_message_id)

        rows = (
            await self._session.scalars(
                query.order_by(MessageRecord.created_at.desc()).limit(limit)
            )
        ).all()
        return [
            {"role": row.role, "content": row.content}
            for row in reversed(rows)
        ]

    async def _store_llm_invocation(
        self,
        *,
        conversation_id: str,
        assistant_message_id: str | None,
        purpose: str,
        model: str,
        request_json: dict[str, Any],
        response_json: dict[str, Any] | None,
        status: str,
        error: str | None = None,
    ) -> LlmInvocationRecord:
        record = LlmInvocationRecord(
            id=_new_id(),
            conversation_id=conversation_id,
            assistant_message_id=assistant_message_id,
            purpose=purpose,
            model=model,
            request_json=_json_safe(request_json),
            response_json=_json_safe(response_json) if response_json is not None else None,
            status=status,
            error=error,
            created_at=utc_now(),
        )
        self._session.add(record)
        await self._session.commit()
        return record

    async def _store_tool_runs(
        self,
        *,
        conversation_id: str,
        assistant_message_id: str,
        planner_invocation_id: str,
        plan: Plan,
        results: list[TaskResult],
    ) -> list[ToolRunRecord]:
        tasks_by_id = {task.id: task for task in plan.tasks}
        records: list[ToolRunRecord] = []
        for result in results:
            task = tasks_by_id.get(result.task_id)
            record = ToolRunRecord(
                id=_new_id(),
                conversation_id=conversation_id,
                assistant_message_id=assistant_message_id,
                planner_invocation_id=planner_invocation_id,
                task_id=result.task_id,
                tool=result.tool,
                parameters_json=_json_safe(task.parameters if task else {}),
                result_json=_json_safe(result.model_dump()),
                status=result.status,
                error=result.error,
                record_count=result.record_count,
                created_at=utc_now(),
            )
            self._session.add(record)
            records.append(record)
        await self._session.commit()
        return records

    async def _finish_assistant_message(
        self,
        assistant_message: MessageRecord,
        content: str,
        *,
        status: str,
    ) -> None:
        assistant_message.content = content
        assistant_message.status = status
        assistant_message.updated_at = utc_now()
        conversation = await self._session.scalar(
            select(ConversationRecord)
            .where(ConversationRecord.id == assistant_message.conversation_id)
            .where(ConversationRecord.deleted_at.is_(None))
        )
        if conversation:
            conversation.updated_at = utc_now()
        await self._session.commit()

    async def _build_message_response(
        self,
        conversation: ConversationRecord,
        user_message: MessageRecord,
        assistant_message: MessageRecord,
        *,
        planner_invocation: LlmInvocationRecord | None,
        plan: Plan | None,
        tool_runs: list[ToolRunRecord],
        total_records: int,
    ) -> ChatMessageResponse:
        invocation_rows = (
            await self._session.scalars(
                select(LlmInvocationRecord)
                .where(LlmInvocationRecord.assistant_message_id == assistant_message.id)
                .order_by(LlmInvocationRecord.created_at.asc())
            )
        ).all()
        linked_invocation_ids = [row.id for row in invocation_rows]
        linked_tool_run_ids = [row.id for row in tool_runs]

        return ChatMessageResponse(
            conversation=_conversation_out(conversation),
            user_message=_message_out(user_message),
            assistant_message=_message_out(
                assistant_message,
                linked_invocation_ids=linked_invocation_ids,
                linked_tool_run_ids=linked_tool_run_ids,
            ),
            planner=(
                ChatPlannerOut(
                    invocation_id=planner_invocation.id,
                    plan=plan,
                )
                if planner_invocation and plan
                else None
            ),
            tool_runs=[_tool_run_out(row) for row in tool_runs],
            total_records=total_records,
        )


def _conversation_out(row: ConversationRecord) -> ConversationOut:
    return ConversationOut(
        id=row.id,
        title=row.title,
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
        feedback_rating=row.feedback_rating,
        feedback_text=row.feedback_text,
        feedback_updated_at=row.feedback_updated_at,
    )


def _message_out(
    row: MessageRecord,
    *,
    linked_invocation_ids: list[str] | None = None,
    linked_tool_run_ids: list[str] | None = None,
) -> MessageOut:
    return MessageOut(
        id=row.id,
        conversation_id=row.conversation_id,
        role=row.role,
        content=row.content,
        content_format=detect_text_format(row.content),
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
        feedback_rating=row.feedback_rating,
        feedback_updated_at=row.feedback_updated_at,
        linked_invocation_ids=linked_invocation_ids or [],
        linked_tool_run_ids=linked_tool_run_ids or [],
    )


def _llm_invocation_out(row: LlmInvocationRecord) -> LlmInvocationOut:
    return LlmInvocationOut(
        id=row.id,
        conversation_id=row.conversation_id,
        assistant_message_id=row.assistant_message_id,
        purpose=row.purpose,
        model=row.model,
        request_json=_redact_llm_request_for_client(row.request_json),
        response_json=row.response_json,
        status=row.status,
        error=row.error,
        created_at=row.created_at,
    )


def _tool_run_out(row: ToolRunRecord) -> ToolRunOut:
    return ToolRunOut(
        id=row.id,
        conversation_id=row.conversation_id,
        assistant_message_id=row.assistant_message_id,
        planner_invocation_id=row.planner_invocation_id,
        task_id=row.task_id,
        tool=row.tool,
        parameters=row.parameters_json,
        result=TaskResult.model_validate(row.result_json),
        status=row.status,
        error=row.error,
        record_count=row.record_count,
        created_at=row.created_at,
    )


def _fallback_title(first_message: str) -> str:
    words = first_message.strip().split()
    title = " ".join(words[:8]).strip()
    if len(words) > 8:
        title = f"{title}..."
    return title or "Nueva conversación"


def _fallback_answer(
    total_records: int,
    results: list[TaskResult],
    error: str,
) -> str:
    failed = sum(1 for result in results if result.status == "error")
    if total_records:
        return (
            f"Ejecuté las consultas y encontré {total_records} registros, "
            "pero no pude generar la síntesis final en lenguaje natural. "
            f"Hubo {failed} tareas con error. Detalle del modelo: {error}"
        )
    return (
        "No pude generar la síntesis final en lenguaje natural. "
        f"Hubo {failed} tareas con error. Detalle del modelo: {error}"
    )


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _redact_llm_request_for_client(value: dict[str, Any]) -> dict[str, Any]:
    """Hide internal system prompts from public conversation-detail traces."""
    request_json = _json_safe(value)
    messages = request_json.get("messages")
    if not isinstance(messages, list):
        return request_json

    redacted_messages = []
    for message in messages:
        if not isinstance(message, dict):
            redacted_messages.append(message)
            continue
        if message.get("role") != "system":
            redacted_messages.append(message)
            continue
        redacted_messages.append(
            {
                **message,
                "content": "[redacted: internal system prompt]",
            }
        )
    request_json["messages"] = redacted_messages
    return request_json


def _new_id() -> str:
    return str(uuid4())
