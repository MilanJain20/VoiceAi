"""Add Agent OS tables: workflows, knowledge, marketplace, evaluations, call_replays

Revision ID: b3c4d5e6f7g8
Revises: a2b3c4d5e6f7
Create Date: 2025-01-20 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "b3c4d5e6f7g8"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Enum types ────────────────────────────────────────────────────
    workflow_status = postgresql.ENUM("draft", "active", "paused", "archived", name="workflowstatus", create_type=False)
    node_type = postgresql.ENUM("trigger", "llm", "tool", "condition", "action", "router", "delay", "human_handoff", "end", name="nodetype", create_type=False)
    execution_status = postgresql.ENUM("pending", "running", "completed", "failed", "cancelled", name="executionstatus", create_type=False)

    op.execute("DO $$ BEGIN CREATE TYPE workflowstatus AS ENUM ('draft', 'active', 'paused', 'archived'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;")
    op.execute("DO $$ BEGIN CREATE TYPE nodetype AS ENUM ('trigger', 'llm', 'tool', 'condition', 'action', 'router', 'delay', 'human_handoff', 'end'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;")
    op.execute("DO $$ BEGIN CREATE TYPE executionstatus AS ENUM ('pending', 'running', 'completed', 'failed', 'cancelled'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;")

    # ── Workflows ─────────────────────────────────────────────────────
    op.create_table(
        "workflows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="SET NULL")),
        sa.Column("status", workflow_status, server_default="draft"),
        sa.Column("graph_data", postgresql.JSONB, server_default="{}"),
        sa.Column("trigger_config", postgresql.JSONB, server_default="{}"),
        sa.Column("version", sa.Integer, server_default="1"),
        sa.Column("total_executions", sa.Integer, server_default="0"),
        sa.Column("success_rate", sa.Float, server_default="0.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "workflow_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.String(100)),
        sa.Column("status", execution_status, server_default="pending"),
        sa.Column("trigger_data", postgresql.JSONB, server_default="{}"),
        sa.Column("steps", postgresql.JSONB, server_default="[]"),
        sa.Column("duration_ms", sa.Integer),
        sa.Column("error", sa.Text),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )

    # ── Knowledge Bases ───────────────────────────────────────────────
    op.create_table(
        "knowledge_bases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="SET NULL")),
        sa.Column("total_documents", sa.Integer, server_default="0"),
        sa.Column("total_chunks", sa.Integer, server_default="0"),
        sa.Column("embedding_model", sa.String(100), server_default="'text-embedding-3-small'"),
        sa.Column("chunk_size", sa.Integer, server_default="512"),
        sa.Column("chunk_overlap", sa.Integer, server_default="50"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "knowledge_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("knowledge_base_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("file_type", sa.String(50)),
        sa.Column("file_size_bytes", sa.Integer, server_default="0"),
        sa.Column("source_url", sa.String(2000)),
        sa.Column("status", sa.String(20), server_default="'processing'"),
        sa.Column("chunk_count", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("chunk_index", sa.Integer, server_default="0"),
        sa.Column("token_count", sa.Integer, server_default="0"),
        sa.Column("embedding", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── Marketplace ───────────────────────────────────────────────────
    op.create_table(
        "marketplace_agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("publisher_id", postgresql.UUID(as_uuid=True)),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("tagline", sa.String(300)),
        sa.Column("description", sa.Text),
        sa.Column("icon", sa.String(10), server_default="'🤖'"),
        sa.Column("category", sa.String(50), server_default="'general'"),
        sa.Column("tags", postgresql.JSONB, server_default="[]"),
        sa.Column("status", sa.String(20), server_default="'pending'"),
        sa.Column("is_featured", sa.Boolean, server_default="false"),
        sa.Column("downloads", sa.Integer, server_default="0"),
        sa.Column("avg_rating", sa.Float, server_default="0.0"),
        sa.Column("total_ratings", sa.Integer, server_default="0"),
        sa.Column("config_snapshot", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "marketplace_ratings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("marketplace_agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("marketplace_agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("rating", sa.Integer, nullable=False),
        sa.Column("review", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── Evaluations ───────────────────────────────────────────────────
    op.create_table(
        "agent_evaluations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("call_log_id", postgresql.UUID(as_uuid=True)),
        sa.Column("overall_score", sa.Float, server_default="0.0"),
        sa.Column("conversation_quality", sa.Float, server_default="0.0"),
        sa.Column("task_completion", sa.Float, server_default="0.0"),
        sa.Column("hallucination_score", sa.Float, server_default="0.0"),
        sa.Column("latency_score", sa.Float, server_default="0.0"),
        sa.Column("tool_success_rate", sa.Float, server_default="0.0"),
        sa.Column("interruption_count", sa.Integer, server_default="0"),
        sa.Column("csat_score", sa.Float, server_default="0.0"),
        sa.Column("avg_latency_ms", sa.Integer, server_default="0"),
        sa.Column("p95_latency_ms", sa.Integer, server_default="0"),
        sa.Column("talk_ratio", sa.Float, server_default="0.5"),
        sa.Column("judge_model", sa.String(50), server_default="'gpt-4o'"),
        sa.Column("judge_reasoning", sa.Text),
        sa.Column("judge_suggestions", postgresql.JSONB, server_default="[]"),
        sa.Column("metrics_raw", postgresql.JSONB, server_default="{}"),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── Call Replays ──────────────────────────────────────────────────
    op.create_table(
        "call_replays",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.String(100), nullable=False),
        sa.Column("duration_ms", sa.Integer, server_default="0"),
        sa.Column("timeline", postgresql.JSONB, server_default="[]"),
        sa.Column("transcript", postgresql.JSONB, server_default="[]"),
        sa.Column("audio_segments", postgresql.JSONB, server_default="[]"),
        sa.Column("summary", sa.Text),
        sa.Column("tags", postgresql.JSONB, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── Indexes ───────────────────────────────────────────────────────
    op.create_index("ix_workflows_agent_id", "workflows", ["agent_id"])
    op.create_index("ix_workflows_status", "workflows", ["status"])
    op.create_index("ix_workflow_executions_workflow_id", "workflow_executions", ["workflow_id"])
    op.create_index("ix_knowledge_bases_agent_id", "knowledge_bases", ["agent_id"])
    op.create_index("ix_knowledge_documents_kb_id", "knowledge_documents", ["knowledge_base_id"])
    op.create_index("ix_knowledge_chunks_doc_id", "knowledge_chunks", ["document_id"])
    op.create_index("ix_marketplace_agents_category", "marketplace_agents", ["category"])
    op.create_index("ix_marketplace_agents_status", "marketplace_agents", ["status"])
    op.create_index("ix_agent_evaluations_agent_id", "agent_evaluations", ["agent_id"])
    op.create_index("ix_call_replays_agent_id", "call_replays", ["agent_id"])
    op.create_index("ix_call_replays_session_id", "call_replays", ["session_id"])


def downgrade() -> None:
    op.drop_table("call_replays")
    op.drop_table("agent_evaluations")
    op.drop_table("marketplace_ratings")
    op.drop_table("marketplace_agents")
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_documents")
    op.drop_table("knowledge_bases")
    op.drop_table("workflow_executions")
    op.drop_table("workflows")
    op.execute("DROP TYPE IF EXISTS workflowstatus")
    op.execute("DROP TYPE IF EXISTS nodetype")
    op.execute("DROP TYPE IF EXISTS executionstatus")
