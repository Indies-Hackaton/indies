"""Add conversation owner user id.

Revision ID: 20260518_0003
Revises: 20260517_0002
Create Date: 2026-05-18 01:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "20260518_0003"
down_revision: Union[str, None] = "20260517_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    _add_column_if_missing(
        "conversations",
        sa.Column("user_id", sa.String(length=255), nullable=True),
    )
    _create_index_if_missing(
        "ix_conversations_user_id",
        "conversations",
        ["user_id"],
    )


def downgrade() -> None:
    # Keep ownership metadata intact on downgrade, matching the project's
    # non-destructive migration style.
    pass


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    bind = op.get_bind()
    columns = {
        column_info["name"]
        for column_info in inspect(bind).get_columns(table_name)
    }
    if column.name not in columns:
        op.add_column(table_name, column)


def _create_index_if_missing(
    index_name: str,
    table_name: str,
    columns: list[str],
) -> None:
    bind = op.get_bind()
    indexes = {
        index_info["name"]
        for index_info in inspect(bind).get_indexes(table_name)
    }
    if index_name not in indexes:
        op.create_index(index_name, table_name, columns)
