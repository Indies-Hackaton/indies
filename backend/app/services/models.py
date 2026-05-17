"""Shared data models for the multi-agent audit pipeline.

These models flow through Planner → Executor → Synthesizer without any
service-layer import cycles. Add new tools here; the Executor and the
Planner prompt are the only files that need updating.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

TextFormat = Literal["plain_text", "markdown"]
FeedbackRating = Literal["like", "dislike"]


class Task(BaseModel):
    """A single API call in the execution plan."""

    id: str = Field(description="Short unique identifier, e.g. 't1'.")
    tool: str = Field(description="Tool name the executor will dispatch to.")
    description: str = Field(description="One-line human-readable description.")
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Tool-specific parameters (keys vary by tool).",
    )


class Plan(BaseModel):
    """The Planner agent's output: an ordered task list."""

    tasks: list[Task]
    reasoning: str = Field(description="Why these tasks were chosen.")


class TaskResult(BaseModel):
    """What the Executor returns for one Task."""

    task_id: str
    tool: str
    description: str
    status: Literal["ok", "error"]
    records: list[dict[str, Any]] = Field(default_factory=list)
    record_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class AuditResponse(BaseModel):
    """Full pipeline response returned to the API caller."""

    plan: Plan
    results: list[TaskResult]
    synthesis: str = Field(description="LLM-generated human-readable summary.")
    synthesis_format: TextFormat = Field(
        default="plain_text",
        description=(
            "Rendering hint for synthesis. Use 'markdown' to parse the text as "
            "Markdown, otherwise render it as plain text."
        ),
    )
    total_records: int


class ConversationOut(BaseModel):
    """Conversation metadata returned to API clients."""

    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    feedback_rating: FeedbackRating | None = None
    feedback_text: str | None = None
    feedback_updated_at: datetime | None = None


class MessageOut(BaseModel):
    """Chat message plus trace links."""

    id: str
    conversation_id: str
    role: Literal["user", "assistant"]
    content: str
    content_format: TextFormat = Field(
        default="plain_text",
        description=(
            "Rendering hint for content. Use 'markdown' to parse the text as "
            "Markdown, otherwise render it as plain text."
        ),
    )
    status: Literal["processing", "completed", "failed"]
    created_at: datetime
    updated_at: datetime
    feedback_rating: FeedbackRating | None = None
    feedback_updated_at: datetime | None = None
    linked_invocation_ids: list[str] = Field(default_factory=list)
    linked_tool_run_ids: list[str] = Field(default_factory=list)


class LlmInvocationOut(BaseModel):
    """Public trace record for a model invocation."""

    id: str
    conversation_id: str
    assistant_message_id: str | None = None
    purpose: Literal["title_generation", "planner", "chat_response"]
    model: str
    request_json: dict[str, Any]
    response_json: dict[str, Any] | None = None
    status: Literal["ok", "error"]
    error: str | None = None
    created_at: datetime


class ToolRunOut(BaseModel):
    """Public trace record for one API/tool execution."""

    id: str
    conversation_id: str
    assistant_message_id: str
    planner_invocation_id: str
    task_id: str
    tool: str
    parameters: dict[str, Any]
    result: TaskResult
    status: Literal["ok", "error"]
    error: str | None = None
    record_count: int
    created_at: datetime


class ChatPlannerOut(BaseModel):
    """Planner trace returned with a chat message response."""

    invocation_id: str
    plan: Plan


class ChatMessageResponse(BaseModel):
    """Response returned by POST /api/v1/chat/messages."""

    conversation: ConversationOut
    user_message: MessageOut
    assistant_message: MessageOut
    planner: ChatPlannerOut | None = None
    tool_runs: list[ToolRunOut] = Field(default_factory=list)
    total_records: int = 0


class ConversationListItem(ConversationOut):
    """Conversation list row with lightweight summary fields."""

    last_message: MessageOut | None = None
    message_count: int = 0


class ConversationDetailResponse(BaseModel):
    """Full persisted conversation with messages and trace links."""

    conversation: ConversationOut
    messages: list[MessageOut]
    llm_invocations: list[LlmInvocationOut]
    tool_runs: list[ToolRunOut]
