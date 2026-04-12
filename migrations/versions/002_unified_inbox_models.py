"""Unified inbox models for messaging hub.

Adds Conversation, InboxMessage, and MessagingAccount tables so the messaging
module can store cross-channel conversations independently from the legacy
whatsapp_inbox and communications modules.

Design decisions:
- Tables are prefixed with messaging_ to stay in messaging module scope.
- All columns nullable or have server_default → safe to deploy before code reads them.
- Fully reversible downgrade.

Revision ID: 002
Depends on: 001
Create Date: 2026-04-12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── messaging_account ──────────────────────────────────────────────────
    # Stores per-channel account credentials (phone number, email, etc.)
    op.create_table(
        "messaging_account",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("hub_id", sa.Uuid(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        # Identity
        sa.Column("channel_id", sa.String(30), nullable=False),       # 'whatsapp', 'email_smtp', etc.
        sa.Column("name", sa.String(255), server_default="", nullable=False),
        sa.Column("display_identifier", sa.String(255), server_default="", nullable=False),
        # Encrypted credentials JSON (Fernet via HUB_SECRETS_KEY)
        sa.Column("credentials_encrypted", sa.Text(), server_default="", nullable=False),
        # State
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("config", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_messaging_account_hub_channel", "messaging_account", ["hub_id", "channel_id"])
    op.create_index("ix_messaging_account_hub_active", "messaging_account", ["hub_id", "is_active"])

    # ── messaging_conversation ─────────────────────────────────────────────
    # Unified conversation (one per contact per account)
    op.create_table(
        "messaging_conversation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("hub_id", sa.Uuid(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        # Source
        sa.Column("account_id", sa.Uuid(), nullable=True),            # FK to messaging_account
        sa.Column("channel_id", sa.String(30), nullable=False),
        # Thread identity
        sa.Column("external_thread_id", sa.String(255), nullable=False),  # wa_id, email thread root, etc.
        # Contact
        sa.Column("customer_id", sa.Uuid(), nullable=True),           # optional FK to customers_customer
        sa.Column("assigned_user_id", sa.Uuid(), nullable=True),
        sa.Column("contact_name", sa.String(255), server_default="", nullable=False),
        sa.Column("contact_identifier", sa.String(255), server_default="", nullable=False),
        # State
        sa.Column("status", sa.String(20), server_default="open", nullable=False),
        sa.Column("subject", sa.String(500), server_default="", nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unread_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("message_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["account_id"], ["messaging_account.id"], ondelete="SET NULL", name="fk_messaging_conv_account"
        ),
    )
    op.create_index("ix_messaging_conv_hub_channel", "messaging_conversation", ["hub_id", "channel_id"])
    op.create_index("ix_messaging_conv_hub_status", "messaging_conversation", ["hub_id", "status"])
    op.create_index("ix_messaging_conv_hub_last", "messaging_conversation", ["hub_id", "last_message_at"])
    op.create_index(
        "ix_messaging_conv_account_thread",
        "messaging_conversation",
        ["hub_id", "account_id", "external_thread_id"],
        unique=True,
    )

    # ── messaging_inbound_message ──────────────────────────────────────────
    # Individual inbound/outbound message record (cross-channel)
    op.create_table(
        "messaging_inbound_message",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("hub_id", sa.Uuid(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        # Parent
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        # Channel info
        sa.Column("channel_id", sa.String(30), nullable=False),
        sa.Column("direction", sa.String(10), server_default="inbound", nullable=False),
        # External identity (idempotency key)
        sa.Column("external_message_id", sa.String(500), server_default="", nullable=False),
        # Content
        sa.Column("body", sa.Text(), server_default="", nullable=False),
        sa.Column("attachments", postgresql.JSONB(), server_default="[]", nullable=False),
        # Status tracking
        sa.Column("status", sa.String(20), server_default="received", nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["messaging_conversation.id"],
            ondelete="CASCADE", name="fk_messaging_inmsg_conv"
        ),
    )
    op.create_index("ix_messaging_inmsg_conv", "messaging_inbound_message", ["conversation_id"])
    op.create_index("ix_messaging_inmsg_hub_ext", "messaging_inbound_message", ["hub_id", "external_message_id"])
    op.create_index("ix_messaging_inmsg_hub_dir", "messaging_inbound_message", ["hub_id", "direction"])


def downgrade() -> None:
    op.drop_index("ix_messaging_inmsg_hub_dir", table_name="messaging_inbound_message")
    op.drop_index("ix_messaging_inmsg_hub_ext", table_name="messaging_inbound_message")
    op.drop_index("ix_messaging_inmsg_conv", table_name="messaging_inbound_message")
    op.drop_table("messaging_inbound_message")

    op.drop_index("ix_messaging_conv_account_thread", table_name="messaging_conversation")
    op.drop_index("ix_messaging_conv_hub_last", table_name="messaging_conversation")
    op.drop_index("ix_messaging_conv_hub_status", table_name="messaging_conversation")
    op.drop_index("ix_messaging_conv_hub_channel", table_name="messaging_conversation")
    op.drop_table("messaging_conversation")

    op.drop_index("ix_messaging_account_hub_active", table_name="messaging_account")
    op.drop_index("ix_messaging_account_hub_channel", table_name="messaging_account")
    op.drop_table("messaging_account")
