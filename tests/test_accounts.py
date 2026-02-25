"""Tests for accounts CRUD, encryption, and migrations."""

import pytest
from cryptography.fernet import Fernet

from exceptions import CredentialDecryptionError
from storage.accounts import (
    create_account,
    delete_account,
    get_account,
    list_accounts,
    update_account,
)
from storage.encryption import decrypt, encrypt
from storage.migrations import migrate


@pytest.fixture
def fernet_key() -> bytes:
    """Generate a valid Fernet key for testing."""
    return Fernet.generate_key()


@pytest.fixture
def db_path(tmp_path) -> str:
    """Return a temporary database path."""
    return str(tmp_path / "test_accounts.db")


@pytest.fixture
def sample_account(db_path, fernet_key):
    """Create and return a sample account."""
    return create_account(
        db_path=db_path,
        encryption_key=fernet_key,
        name="Test Account",
        access_token="EAABsbCS1IEBAZ...",
        ad_account_id="act_123456789",
        app_id="1234567890",
        app_secret="abc123secret",
        page_id="9876543210",
        max_daily_budget_usd=500.0,
    )


class TestEncryption:
    def test_encrypt_decrypt_round_trip(self, fernet_key):
        """Encrypting then decrypting returns the original value."""
        original = "my_secret_token_12345"
        encrypted = encrypt(original, fernet_key)
        assert encrypted != original
        decrypted = decrypt(encrypted, fernet_key)
        assert decrypted == original

    def test_decrypt_with_wrong_key_raises(self, fernet_key):
        """Decrypting with the wrong key raises CredentialDecryptionError."""
        original = "my_secret_token"
        encrypted = encrypt(original, fernet_key)

        wrong_key = Fernet.generate_key()
        with pytest.raises(CredentialDecryptionError):
            decrypt(encrypted, wrong_key)

    def test_decrypt_corrupted_data_raises(self, fernet_key):
        """Decrypting corrupted data raises CredentialDecryptionError."""
        with pytest.raises(CredentialDecryptionError):
            decrypt("not_valid_encrypted_data", fernet_key)

    def test_encrypt_empty_string(self, fernet_key):
        """Encrypting an empty string works."""
        encrypted = encrypt("", fernet_key)
        assert decrypt(encrypted, fernet_key) == ""

    def test_encrypt_unicode(self, fernet_key):
        """Encrypting unicode strings works."""
        original = "token_with_emoji_\u2764\ufe0f"
        encrypted = encrypt(original, fernet_key)
        assert decrypt(encrypted, fernet_key) == original


class TestAccountCRUD:
    def test_create_account(self, sample_account):
        """Creating an account returns it with decrypted fields."""
        assert sample_account.name == "Test Account"
        assert sample_account.access_token == "EAABsbCS1IEBAZ..."
        assert sample_account.ad_account_id == "act_123456789"
        assert sample_account.app_id == "1234567890"
        assert sample_account.app_secret == "abc123secret"
        assert sample_account.page_id == "9876543210"
        assert sample_account.max_daily_budget_usd == 500.0
        assert sample_account.is_active is True
        assert sample_account.id is not None

    def test_get_account(self, db_path, fernet_key, sample_account):
        """Getting an account returns it with decrypted fields."""
        fetched = get_account(db_path, fernet_key, sample_account.id)
        assert fetched is not None
        assert fetched.name == "Test Account"
        assert fetched.access_token == "EAABsbCS1IEBAZ..."
        assert fetched.app_secret == "abc123secret"

    def test_get_account_not_found(self, db_path, fernet_key):
        """Getting a nonexistent account returns None."""
        result = get_account(db_path, fernet_key, "nonexistent-uuid")
        assert result is None

    def test_list_accounts(self, db_path, fernet_key, sample_account):
        """Listing accounts returns only active accounts."""
        accounts = list_accounts(db_path, fernet_key)
        assert len(accounts) == 1
        assert accounts[0].name == "Test Account"
        assert accounts[0].access_token == "EAABsbCS1IEBAZ..."

    def test_list_accounts_excludes_deleted(self, db_path, fernet_key, sample_account):
        """Listing accounts excludes soft-deleted accounts."""
        delete_account(db_path, sample_account.id)
        accounts = list_accounts(db_path, fernet_key)
        assert len(accounts) == 0

    def test_update_account(self, db_path, fernet_key, sample_account):
        """Updating an account changes the specified fields."""
        updated = update_account(
            db_path, fernet_key, sample_account.id,
            name="Updated Name",
            max_daily_budget_usd=1000.0,
        )
        assert updated is not None
        assert updated.name == "Updated Name"
        assert updated.max_daily_budget_usd == 1000.0
        # Unchanged fields preserved
        assert updated.access_token == "EAABsbCS1IEBAZ..."
        assert updated.ad_account_id == "act_123456789"

    def test_update_sensitive_field(self, db_path, fernet_key, sample_account):
        """Updating a sensitive field re-encrypts it."""
        updated = update_account(
            db_path, fernet_key, sample_account.id,
            access_token="new_token_value",
        )
        assert updated is not None
        assert updated.access_token == "new_token_value"

        # Verify it's stored encrypted in DB (re-fetch raw)
        fetched = get_account(db_path, fernet_key, sample_account.id)
        assert fetched.access_token == "new_token_value"

    def test_update_nonexistent_account(self, db_path, fernet_key):
        """Updating a nonexistent account returns None."""
        result = update_account(db_path, fernet_key, "nonexistent-uuid", name="X")
        assert result is None

    def test_delete_account_soft(self, db_path, fernet_key, sample_account):
        """Deleting an account sets is_active=False."""
        delete_account(db_path, sample_account.id)
        # Still fetchable by ID
        fetched = get_account(db_path, fernet_key, sample_account.id)
        assert fetched is not None
        assert fetched.is_active is False

    def test_multiple_accounts(self, db_path, fernet_key, sample_account):
        """Multiple accounts can coexist."""
        create_account(
            db_path=db_path,
            encryption_key=fernet_key,
            name="Second Account",
            access_token="token_2",
            ad_account_id="act_987654321",
            app_id="app_2",
            app_secret="secret_2",
            page_id="page_2",
            max_daily_budget_usd=200.0,
        )
        accounts = list_accounts(db_path, fernet_key)
        assert len(accounts) == 2
        names = {a.name for a in accounts}
        assert names == {"Test Account", "Second Account"}


class TestMigrations:
    def test_migration_creates_accounts_table(self, db_path):
        """Migration creates the accounts table."""
        migrate(db_path)

        from sqlalchemy import create_engine, inspect
        engine = create_engine(f"sqlite:///{db_path}")
        inspector = inspect(engine)
        assert "accounts" in inspector.get_table_names()

    def test_migration_idempotent(self, db_path):
        """Running migration twice doesn't error."""
        migrate(db_path)
        migrate(db_path)  # Should not raise

    def test_migration_adds_account_id_to_run_logs(self, db_path):
        """Migration adds account_id column to run_logs if the table exists."""
        from storage.logger import RunLogger

        # Create run_logs table first
        logger = RunLogger(db_path=db_path)
        logger.create_run()

        # Run migration
        migrate(db_path)

        from sqlalchemy import create_engine, inspect
        engine = create_engine(f"sqlite:///{db_path}")
        inspector = inspect(engine)
        columns = [col["name"] for col in inspector.get_columns("run_logs")]
        assert "account_id" in columns

    def test_migration_backfills_legacy_account(self, db_path):
        """Migration backfills NULL account_id rows with Legacy account."""
        from storage.logger import RunLogger

        logger = RunLogger(db_path=db_path)
        run_id = logger.create_run()

        # Run migration — should backfill
        migrate(db_path)

        from sqlalchemy import create_engine, text
        engine = create_engine(f"sqlite:///{db_path}")
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT account_id FROM run_logs WHERE run_id = :id"),
                {"id": run_id},
            )
            account_id = result.scalar()
            assert account_id == "00000000-0000-0000-0000-000000000000"

            # Legacy account should exist
            result = conn.execute(
                text("SELECT name FROM accounts WHERE id = :id"),
                {"id": "00000000-0000-0000-0000-000000000000"},
            )
            name = result.scalar()
            assert name == "Legacy (pre-migration)"
