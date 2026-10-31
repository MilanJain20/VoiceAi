"""Latency breakdown and tool audit log.

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7g8
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "c4d5e6f7a8b9"
down_revision = "b3c4d5e6f7g8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("latency_breakdown", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "call_logs",
        sa.Column("turn_latencies", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_table(
        "tool_audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", sa.String(64), nullable=False),
        sa.Column("agent_id", sa.String(64), nullable=True),
        sa.Column("turn_id", sa.String(64), nullable=False),
        sa.Column("tool_name", sa.String(128), nullable=False),
        sa.Column("arguments", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_tool_audit_logs_session_id", "tool_audit_logs", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_tool_audit_logs_session_id", table_name="tool_audit_logs")
    op.drop_table("tool_audit_logs")
    op.drop_column("call_logs", "turn_latencies")
    op.drop_column("messages", "latency_breakdown")
