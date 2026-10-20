"""Distinguish login and signup rate-limit records."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20261020_0002"
down_revision = "20261020_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {item["name"] for item in sa.inspect(op.get_bind()).get_columns("login_attempts")}
    if "action" not in columns:
        op.add_column("login_attempts", sa.Column("action", sa.String(24), nullable=False, server_default="login"))


def downgrade() -> None:
    op.drop_column("login_attempts", "action")
