"""Initial chat persistence schema.

Revision ID: 20260516_0001
Revises:
Create Date: 2026-05-16 23:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "20260516_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not inspector.has_table("conversations"):
        op.create_table(
            "conversations",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("title", sa.String(length=160), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

    if not inspector.has_table("messages"):
        op.create_table(
            "messages",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("conversation_id", sa.String(length=36), nullable=False),
            sa.Column("role", sa.String(length=20), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["conversation_id"],
                ["conversations.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    if not inspector.has_table("llm_invocations"):
        op.create_table(
            "llm_invocations",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("conversation_id", sa.String(length=36), nullable=False),
            sa.Column("assistant_message_id", sa.String(length=36), nullable=True),
            sa.Column("purpose", sa.String(length=40), nullable=False),
            sa.Column("model", sa.String(length=120), nullable=False),
            sa.Column("request_json", sa.JSON(), nullable=False),
            sa.Column("response_json", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["assistant_message_id"],
                ["messages.id"],
                ondelete="SET NULL",
            ),
            sa.ForeignKeyConstraint(
                ["conversation_id"],
                ["conversations.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    if not inspector.has_table("tool_runs"):
        op.create_table(
            "tool_runs",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("conversation_id", sa.String(length=36), nullable=False),
            sa.Column("assistant_message_id", sa.String(length=36), nullable=False),
            sa.Column("planner_invocation_id", sa.String(length=36), nullable=False),
            sa.Column("task_id", sa.String(length=80), nullable=False),
            sa.Column("tool", sa.String(length=120), nullable=False),
            sa.Column("parameters_json", sa.JSON(), nullable=False),
            sa.Column("result_json", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("record_count", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["assistant_message_id"],
                ["messages.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["conversation_id"],
                ["conversations.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["planner_invocation_id"],
                ["llm_invocations.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    _add_column_if_missing(
        "conversations",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    _create_index_if_missing("ix_messages_conversation_id", "messages", ["conversation_id"])
    _create_index_if_missing(
        "ix_llm_invocations_assistant_message_id",
        "llm_invocations",
        ["assistant_message_id"],
    )
    _create_index_if_missing(
        "ix_llm_invocations_conversation_id",
        "llm_invocations",
        ["conversation_id"],
    )
    _create_index_if_missing(
        "ix_tool_runs_assistant_message_id",
        "tool_runs",
        ["assistant_message_id"],
    )
    _create_index_if_missing(
        "ix_tool_runs_conversation_id",
        "tool_runs",
        ["conversation_id"],
    )
    _create_index_if_missing(
        "ix_tool_runs_planner_invocation_id",
        "tool_runs",
        ["planner_invocation_id"],
    )


def downgrade() -> None:
    # This baseline migration is intentionally non-destructive because it may
    # adopt production databases that already contain user conversation data.
    pass


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    bind = op.get_bind()
    columns = {column_info["name"] for column_info in inspect(bind).get_columns(table_name)}
    if column.name not in columns:
        op.add_column(table_name, column)


def _create_index_if_missing(
    index_name: str,
    table_name: str,
    columns: list[str],
) -> None:
    bind = op.get_bind()
    indexes = {index_info["name"] for index_info in inspect(bind).get_indexes(table_name)}
    if index_name not in indexes:
        op.create_index(index_name, table_name, columns)
