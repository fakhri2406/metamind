"""Startup migrations for MetaMind database schema changes.

Idempotent — safe to run on every startup.
"""

from sqlalchemy import create_engine, inspect, text

from storage.accounts import AccountBase

_LEGACY_ACCOUNT_ID = "00000000-0000-0000-0000-000000000000"


def migrate(db_path: str) -> None:
    """Run all pending migrations.

    1. Creates `accounts` table if not exists.
    2. Adds `account_id` column to `run_logs` if not exists.
    3. Backfills NULL `account_id` rows with a Legacy placeholder account.

    Args:
        db_path: Path to the SQLite database file.
    """
    engine = create_engine(f"sqlite:///{db_path}", echo=False)

    # 1. Create accounts table if not exists
    AccountBase.metadata.create_all(engine)

    inspector = inspect(engine)

    # 2. Add account_id column to run_logs if not exists
    if "run_logs" in inspector.get_table_names():
        columns = [col["name"] for col in inspector.get_columns("run_logs")]
        if "account_id" not in columns:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE run_logs ADD COLUMN account_id VARCHAR")
                )

        # 3. Backfill NULL account_id rows with Legacy account
        with engine.begin() as conn:
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

                # Backfill
                conn.execute(
                    text(
                        "UPDATE run_logs SET account_id = :id WHERE account_id IS NULL"
                    ),
                    {"id": _LEGACY_ACCOUNT_ID},
                )
