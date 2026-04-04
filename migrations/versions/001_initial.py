"""Initial messaging module tables.

Revision ID: 001
Create Date: 2026-04-04
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- messaging_settings ---
    op.create_table(
        "messaging_settings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("hub_id", sa.Uuid(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        # WhatsApp
        sa.Column("whatsapp_enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("whatsapp_api_token", sa.String(500), server_default="", nullable=False),
        sa.Column("whatsapp_phone_id", sa.String(50), server_default="", nullable=False),
        sa.Column("whatsapp_business_id", sa.String(50), server_default="", nullable=False),
        # SMS
        sa.Column("sms_enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("sms_provider", sa.String(20), server_default="none", nullable=False),
        sa.Column("sms_api_key", sa.String(255), server_default="", nullable=False),
        sa.Column("sms_sender_name", sa.String(11), server_default="", nullable=False),
        # Email
        sa.Column("email_enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("email_from_name", sa.String(255), server_default="", nullable=False),
        sa.Column("email_from_address", sa.String(254), server_default="", nullable=False),
        sa.Column("email_smtp_host", sa.String(255), server_default="", nullable=False),
        sa.Column("email_smtp_port", sa.Integer(), server_default="587", nullable=False),
        sa.Column("email_smtp_username", sa.String(255), server_default="", nullable=False),
        sa.Column("email_smtp_password", sa.String(255), server_default="", nullable=False),
        sa.Column("email_smtp_use_tls", sa.Boolean(), server_default="true", nullable=False),
        # Automation
        sa.Column("appointment_reminder_enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("appointment_reminder_hours", sa.Integer(), server_default="24", nullable=False),
        sa.Column("booking_confirmation_enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hub_id", name="uq_messaging_settings_hub"),
    )

    # --- messaging_template ---
    op.create_table(
        "messaging_template",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("hub_id", sa.Uuid(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("channel", sa.String(20), server_default="all", nullable=False),
        sa.Column("category", sa.String(30), server_default="custom", nullable=False),
        sa.Column("subject", sa.String(255), server_default="", nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("is_system", sa.Boolean(), server_default="false", nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- messaging_message ---
    op.create_table(
        "messaging_message",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("hub_id", sa.Uuid(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("recipient_name", sa.String(255), server_default="", nullable=False),
        sa.Column("recipient_contact", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(255), server_default="", nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), server_default="queued", nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=True),
        sa.Column("customer_id", sa.Uuid(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), server_default="", nullable=False),
        sa.Column("external_id", sa.String(255), server_default="", nullable=False),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["template_id"], ["messaging_template.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers_customer.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_messaging_message_hub_channel_status",
        "messaging_message",
        ["hub_id", "channel", "status", "created_at"],
    )

    # --- messaging_campaign ---
    op.create_table(
        "messaging_campaign",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("hub_id", sa.Uuid(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(20), server_default="draft", nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_recipients", sa.Integer(), server_default="0", nullable=False),
        sa.Column("sent_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("delivered_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("target_filter", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["template_id"], ["messaging_template.id"], ondelete="SET NULL"),
    )

    # --- messaging_automation ---
    op.create_table(
        "messaging_automation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("hub_id", sa.Uuid(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("trigger", sa.String(30), nullable=False),
        sa.Column("channel", sa.String(20), server_default="email", nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=True),
        sa.Column("delay_hours", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("conditions", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("total_sent", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["template_id"], ["messaging_template.id"], ondelete="SET NULL"),
    )

    # --- messaging_automation_execution ---
    op.create_table(
        "messaging_automation_execution",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("hub_id", sa.Uuid(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("automation_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=True),
        sa.Column("message_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("trigger_data", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("error_message", sa.Text(), server_default="", nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["automation_id"], ["messaging_automation.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers_customer.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["message_id"], ["messaging_message.id"], ondelete="SET NULL"),
    )


def downgrade() -> None:
    op.drop_table("messaging_automation_execution")
    op.drop_table("messaging_automation")
    op.drop_table("messaging_campaign")
    op.drop_index("ix_messaging_message_hub_channel_status", table_name="messaging_message")
    op.drop_table("messaging_message")
    op.drop_table("messaging_template")
    op.drop_table("messaging_settings")
