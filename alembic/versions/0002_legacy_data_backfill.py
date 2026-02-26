"""legacy_data_backfill

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-26

Backfills NULL account_id and model columns in run_logs with legacy defaults.
This is a no-op on fresh PostgreSQL installs.
"""
from typing import Sequence, Union

from sqlalchemy import text

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_LEGACY_ACCOUNT_ID = "00000000-0000-0000-0000-000000000000"


def upgrade() -> None:
    conn = op.get_bind()

    # Check if there are any run_logs with NULL account_id
    result = conn.execute(
        text("SELECT COUNT(*) FROM run_logs WHERE account_id IS NULL")
    )
    null_count = result.scalar()

    if null_count and null_count > 0:
        # Create Legacy placeholder account if it doesn't exist
        existing = conn.execute(
            text("SELECT id FROM accounts WHERE id = :id"),
            {"id": _LEGACY_ACCOUNT_ID},
        )
        if existing.fetchone() is None:
            conn.execute(
                text(
                    "INSERT INTO accounts "
                    "(id, name, access_token, ad_account_id, app_id, "
                    "app_secret, page_id, max_daily_budget_usd, is_active) "
                    "VALUES (:id, :name, :token, :ad_id, :app_id, "
                    ":secret, :page_id, :budget, :active)"
                ),
                {
                    "id": _LEGACY_ACCOUNT_ID,
                    "name": "Legacy (pre-migration)",
                    "token": "legacy",
                    "ad_id": "act_000000000",
                    "app_id": "legacy",
                    "secret": "legacy",
                    "page_id": "legacy",
                    "budget": 500.0,
                    "active": False,
                },
            )

        # Backfill NULL account_id
        conn.execute(
            text(
                "UPDATE run_logs SET account_id = :id WHERE account_id IS NULL"
            ),
            {"id": _LEGACY_ACCOUNT_ID},
        )

    # Backfill NULL model column — all previous runs used Opus
    conn.execute(
        text(
            "UPDATE run_logs SET model = :model WHERE model IS NULL"
        ),
        {"model": "claude-opus-4-6"},
    )


def downgrade() -> None:
    # Data migrations are not reversible — no-op
    pass
