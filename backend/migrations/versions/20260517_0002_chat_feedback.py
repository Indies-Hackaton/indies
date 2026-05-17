"""Add chat feedback fields.

Revision ID: 20260517_0002
Revises: 20260516_0001
Create Date: 2026-05-17 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "20260517_0002"
down_revision: Union[str, None] = "20260516_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    _add_column_if_missing(
        "conversations",
        sa.Column("feedback_rating", sa.String(length=20), nullable=True),
    )
    _add_column_if_missing(
        "conversations",
        sa.Column("feedback_text", sa.Text(), nullable=True),
    )
    _add_column_if_missing(
        "conversations",
        sa.Column("feedback_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    _add_column_if_missing(
        "messages",
        sa.Column("feedback_rating", sa.String(length=20), nullable=True),
    )
    _add_column_if_missing(
        "messages",
        sa.Column("feedback_updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    # Keep feedback data intact on downgrade, matching the non-destructive
    # baseline migration style used by this hackathon project.
    pass


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    bind = op.get_bind()
    columns = {
        column_info["name"]
        for column_info in inspect(bind).get_columns(table_name)
    }
    if column.name not in columns:
        op.add_column(table_name, column)
