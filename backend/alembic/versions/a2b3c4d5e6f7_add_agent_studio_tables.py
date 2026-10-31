"""add agent studio tables

Revision ID: a2b3c4d5e6f7
Revises: 9ea08dbb5816
Create Date: 2026-05-15 14:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic
revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, None] = '9ea08dbb5816'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types via raw SQL (IF NOT EXISTS avoids errors on re-run)
    op.execute("DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'agentstatus') THEN CREATE TYPE agentstatus AS ENUM ('draft', 'active', 'paused', 'archived'); END IF; END $$;")
    op.execute("DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'agentcategory') THEN CREATE TYPE agentcategory AS ENUM ('general', 'sales', 'support', 'hr', 'interview', 'education', 'healthcare', 'custom'); END IF; END $$;")

    # Use postgresql.ENUM with create_type=False so create_table doesn't re-create them
    agent_status = postgresql.ENUM('draft', 'active', 'paused', 'archived', name='agentstatus', create_type=False)
    agent_category = postgresql.ENUM('general', 'sales', 'support', 'hr', 'interview', 'education', 'healthcare', 'custom', name='agentcategory', create_type=False)

    # ── agents table ──
    op.create_table(
        'agents',
        sa.Column('id', sa.UUID(), nullable=False, default=sa.text('gen_random_uuid()')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),

        # Identity
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('slug', sa.String(128), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('avatar_url', sa.String(512), nullable=True),
        sa.Column('category', agent_category, nullable=False, server_default='general'),
        sa.Column('status', agent_status, nullable=False, server_default='draft'),

        # Prompt
        sa.Column('system_prompt', sa.Text(), nullable=False, server_default=''),
        sa.Column('welcome_message', sa.Text(), nullable=True,
                   server_default='Hello! How can I help you today?'),

        # Voice settings
        sa.Column('tts_voice', sa.String(128), nullable=False, server_default='en-US-AriaNeural'),
        sa.Column('tts_rate', sa.String(16), nullable=False, server_default='-5%'),
        sa.Column('tts_pitch', sa.String(16), nullable=False, server_default='+0Hz'),
        sa.Column('tts_volume', sa.String(16), nullable=False, server_default='+10%'),
        sa.Column('language', sa.String(16), nullable=False, server_default='en-US'),

        # LLM settings
        sa.Column('llm_model', sa.String(64), nullable=False, server_default='gpt-4o'),
        sa.Column('temperature', sa.Float(), nullable=False, server_default='0.3'),
        sa.Column('max_tokens', sa.Integer(), nullable=False, server_default='4096'),
        sa.Column('top_p', sa.Float(), nullable=False, server_default='1.0'),

        # JSONB configs
        sa.Column('tools_config', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('memory_config', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('workflow_config', postgresql.JSONB(astext_type=sa.Text()), nullable=True),

        # Analytics
        sa.Column('total_calls', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_duration_ms', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('avg_rating', sa.Float(), nullable=False, server_default='0.0'),

        # Ownership
        sa.Column('created_by', sa.UUID(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),

        # Version
        sa.Column('current_version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('is_template', sa.Boolean(), nullable=False, server_default='false'),

        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_agents_id'), 'agents', ['id'], unique=False)
    op.create_index(op.f('ix_agents_slug'), 'agents', ['slug'], unique=True)

    # ── agent_versions table ──
    op.create_table(
        'agent_versions',
        sa.Column('id', sa.UUID(), nullable=False, default=sa.text('gen_random_uuid()')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),

        sa.Column('agent_id', sa.UUID(), sa.ForeignKey('agents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('change_note', sa.Text(), nullable=True),
        sa.Column('config_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_by', sa.UUID(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),

        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_agent_versions_id'), 'agent_versions', ['id'], unique=False)

    # ── call_logs table ──
    op.create_table(
        'call_logs',
        sa.Column('id', sa.UUID(), nullable=False, default=sa.text('gen_random_uuid()')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),

        sa.Column('agent_id', sa.UUID(), sa.ForeignKey('agents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('session_id', sa.String(64), nullable=False),
        sa.Column('conversation_id', sa.UUID(),
                   sa.ForeignKey('conversations.id', ondelete='SET NULL'), nullable=True),

        # Metrics
        sa.Column('duration_ms', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('message_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_tokens', sa.Integer(), nullable=False, server_default='0'),

        # Latency
        sa.Column('avg_latency_ms', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('p95_latency_ms', sa.Integer(), nullable=False, server_default='0'),

        # Outcome
        sa.Column('status', sa.String(32), nullable=False, server_default='completed'),
        sa.Column('rating', sa.Float(), nullable=True),
        sa.Column('feedback', sa.Text(), nullable=True),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),

        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_call_logs_id'), 'call_logs', ['id'], unique=False)
    op.create_index(op.f('ix_call_logs_session_id'), 'call_logs', ['session_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_call_logs_session_id'), table_name='call_logs')
    op.drop_index(op.f('ix_call_logs_id'), table_name='call_logs')
    op.drop_table('call_logs')

    op.drop_index(op.f('ix_agent_versions_id'), table_name='agent_versions')
    op.drop_table('agent_versions')

    op.drop_index(op.f('ix_agents_slug'), table_name='agents')
    op.drop_index(op.f('ix_agents_id'), table_name='agents')
    op.drop_table('agents')

    sa.Enum(name='agentstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='agentcategory').drop(op.get_bind(), checkfirst=True)
