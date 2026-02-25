"""Account model and CRUD operations for multi-account support."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Float, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from storage.encryption import decrypt, encrypt


class AccountBase(DeclarativeBase):
    pass


class Account(AccountBase):
    """Database model for a Meta Ad Account."""

    __tablename__ = "accounts"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    access_token = Column(String, nullable=False)  # stored encrypted
    ad_account_id = Column(String, nullable=False)  # plaintext
    app_id = Column(String, nullable=False)  # plaintext
    app_secret = Column(String, nullable=False)  # stored encrypted
    page_id = Column(String, nullable=False)  # plaintext
    max_daily_budget_usd = Column(Float, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True)


def _get_session(db_path: str) -> Session:
    """Create a session for the given database path."""
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    AccountBase.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    return factory()


def _decrypt_account(account: Account, encryption_key: bytes) -> Account:
    """Decrypt sensitive fields on an Account object in-place and return it."""
    account.access_token = decrypt(account.access_token, encryption_key)
    account.app_secret = decrypt(account.app_secret, encryption_key)
    return account


def create_account(
    db_path: str,
    encryption_key: bytes,
    name: str,
    access_token: str,
    ad_account_id: str,
    app_id: str,
    app_secret: str,
    page_id: str,
    max_daily_budget_usd: float,
) -> Account:
    """Create a new account with encrypted sensitive fields.

    Args:
        db_path: Path to the SQLite database.
        encryption_key: Fernet key for encrypting credentials.
        name: Human-readable account name.
        access_token: Meta access token (will be encrypted).
        ad_account_id: Meta ad account ID (format: act_XXXXXXXXX).
        app_id: Meta app ID.
        app_secret: Meta app secret (will be encrypted).
        page_id: Meta page ID.
        max_daily_budget_usd: Budget cap for this account.

    Returns:
        The created Account with sensitive fields decrypted.
    """
    account = Account(
        id=str(uuid.uuid4()),
        name=name,
        access_token=encrypt(access_token, encryption_key),
        ad_account_id=ad_account_id,
        app_id=app_id,
        app_secret=encrypt(app_secret, encryption_key),
        page_id=page_id,
        max_daily_budget_usd=max_daily_budget_usd,
    )

    with _get_session(db_path) as session:
        session.add(account)
        session.commit()
        session.refresh(account)
        # Detach before closing session
        session.expunge(account)

    # Return with decrypted fields
    account.access_token = access_token
    account.app_secret = app_secret
    return account


def get_account(
    db_path: str,
    encryption_key: bytes,
    account_id: str,
) -> Optional[Account]:
    """Fetch a single account by ID with decrypted credentials.

    Args:
        db_path: Path to the SQLite database.
        encryption_key: Fernet key for decrypting credentials.
        account_id: The account UUID.

    Returns:
        Account with decrypted fields, or None if not found.
    """
    with _get_session(db_path) as session:
        account = session.get(Account, account_id)
        if account is None:
            return None
        session.expunge(account)

    return _decrypt_account(account, encryption_key)


def list_accounts(
    db_path: str,
    encryption_key: bytes,
) -> list[Account]:
    """List all active accounts with decrypted credentials.

    Args:
        db_path: Path to the SQLite database.
        encryption_key: Fernet key for decrypting credentials.

    Returns:
        List of active Account objects with decrypted fields.
    """
    with _get_session(db_path) as session:
        accounts = (
            session.query(Account)
            .filter(Account.is_active.is_(True))
            .order_by(Account.created_at)
            .all()
        )
        for acct in accounts:
            session.expunge(acct)

    return [_decrypt_account(acct, encryption_key) for acct in accounts]


def update_account(
    db_path: str,
    encryption_key: bytes,
    account_id: str,
    **fields,
) -> Optional[Account]:
    """Update an account's fields. Sensitive fields are re-encrypted.

    Args:
        db_path: Path to the SQLite database.
        encryption_key: Fernet key for encrypting/decrypting credentials.
        account_id: The account UUID.
        **fields: Fields to update (e.g., name="New Name", access_token="new_token").

    Returns:
        Updated Account with decrypted fields, or None if not found.
    """
    with _get_session(db_path) as session:
        account = session.get(Account, account_id)
        if account is None:
            return None

        for field_name, value in fields.items():
            if field_name in ("access_token", "app_secret"):
                value = encrypt(value, encryption_key)
            setattr(account, field_name, value)

        session.commit()
        session.refresh(account)
        session.expunge(account)

    return _decrypt_account(account, encryption_key)


def delete_account(db_path: str, account_id: str) -> None:
    """Soft-delete an account by setting is_active=False.

    Args:
        db_path: Path to the SQLite database.
        account_id: The account UUID.
    """
    with _get_session(db_path) as session:
        account = session.get(Account, account_id)
        if account:
            account.is_active = False
            session.commit()
