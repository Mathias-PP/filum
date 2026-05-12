"""Initial schema

Revision ID: 001_initial
Revises:
Create Date: 2026-05-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('username', sa.String(100), unique=True, nullable=False, index=True),
        sa.Column('display_name', sa.String(255)),
        sa.Column('bio', sa.Text),
        sa.Column('avatar_url', sa.String(500)),
        sa.Column('public_key', sa.Text, nullable=False),
        sa.Column('encrypted_private_key', sa.Text, nullable=False),
        sa.Column('google_id', sa.String(255), unique=True),
        sa.Column('is_verified', sa.Boolean, default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        'biblio_cards',
        sa.Column('id', sa.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', sa.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('content_type', sa.String(50), nullable=False),
        sa.Column('content_url', sa.String(1000)),
        sa.Column('description', sa.Text),
        sa.Column('status', sa.String(20), default='draft', index=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('canonical_hash', sa.String(64), nullable=False, index=True),
        sa.Column('signature', sa.Text, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        'sources',
        sa.Column('id', sa.UUID(as_uuid=True), primary_key=True),
        sa.Column('biblio_card_id', sa.UUID(as_uuid=True), sa.ForeignKey('biblio_cards.id'), nullable=False, index=True),
        sa.Column('url', sa.String(2000), nullable=False, index=True),
        sa.Column('title', sa.String(500)),
        sa.Column('source_type', sa.String(50), nullable=False),
        sa.Column('authority_level', sa.String(20), nullable=False),
        sa.Column('annotation', sa.Text),
        sa.Column('archive_status', sa.String(20), default='pending', index=True),
        sa.Column('archive_url', sa.String(2000)),
        sa.Column('archive_timestamp', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    op.create_table(
        'audit_events',
        sa.Column('id', sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column('event_type', sa.String(100), nullable=False, index=True),
        sa.Column('user_id', sa.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('resource_type', sa.String(50), nullable=False),
        sa.Column('resource_id', sa.UUID(as_uuid=True), nullable=False),
        sa.Column('action', sa.String(20), nullable=False),
        sa.Column('metadata', sa.JSON),
        sa.Column('ip_address', sa.String(45)),
        sa.Column('user_agent', sa.String(500)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_index('ix_audit_events_resource', 'audit_events', ['resource_type', 'resource_id'])
    op.create_index('ix_audit_events_created', 'audit_events', ['created_at'])


def downgrade() -> None:
    op.drop_table('audit_events')
    op.drop_table('sources')
    op.drop_table('biblio_cards')
    op.drop_table('users')
