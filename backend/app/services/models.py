"""Shared data models for the multi-agent audit pipeline.

These models flow through Planner → Executor → Synthesizer without any
service-layer import cycles. Add new tools here; the Executor and the
Planner prompt are the only files that need updating.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field


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
    total_records: int
