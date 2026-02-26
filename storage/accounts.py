"""Account model and CRUD operations for multi-account support."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Float, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

import config
from storage.base import Base
from storage.encryption import decrypt, encrypt


class Account(Base):
    """Database model for a Meta Ad Account."""

    __tablename__ = "accounts"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    access_token = Column(String, nullable=False)  # stored encrypted
    ad_account_id = Column(String, nullable=False)  # plaintext
    app_id = Column(String, nullable=False)  # plaintext
    app_secret = Column(String, nullable=False)  # stored encrypted
    page_id = Column(String, nullable=False)  # plaintext
    max_daily_budget_usd = Column(Float, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True)


def _decrypt_account(account: Account, encryption_key: bytes) -> Account:
    """Decrypt sensitive fields on an Account object in-place and return it."""
    account.access_token = decrypt(account.access_token, encryption_key)
    account.app_secret = decrypt(account.app_secret, encryption_key)
    return account


def create_account(
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
        id=uuid.uuid4(),
        name=name,
        access_token=encrypt(access_token, encryption_key),
        ad_account_id=ad_account_id,
        app_id=app_id,
        app_secret=encrypt(app_secret, encryption_key),
        page_id=page_id,
        max_daily_budget_usd=max_daily_budget_usd,
    )

    with config.SessionLocal() as session:
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
    encryption_key: bytes,
    account_id: str,
) -> Optional[Account]:
    """Fetch a single account by ID with decrypted credentials.

    Args:
        encryption_key: Fernet key for decrypting credentials.
        account_id: The account UUID.

    Returns:
        Account with decrypted fields, or None if not found.
    """
    with config.SessionLocal() as session:
        account = session.get(Account, uuid.UUID(account_id) if isinstance(account_id, str) else account_id)
        if account is None:
            return None
        session.expunge(account)

    return _decrypt_account(account, encryption_key)


def list_accounts(
    encryption_key: bytes,
) -> list[Account]:
    """List all active accounts with decrypted credentials.

    Args:
        encryption_key: Fernet key for decrypting credentials.

    Returns:
        List of active Account objects with decrypted fields.
    """
    with config.SessionLocal() as session:
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
    encryption_key: bytes,
    account_id: str,
    **fields,
) -> Optional[Account]:
    """Update an account's fields. Sensitive fields are re-encrypted.

    Args:
        encryption_key: Fernet key for encrypting/decrypting credentials.
        account_id: The account UUID.
        **fields: Fields to update (e.g., name="New Name", access_token="new_token").

    Returns:
        Updated Account with decrypted fields, or None if not found.
    """
    with config.SessionLocal() as session:
        account = session.get(Account, uuid.UUID(account_id) if isinstance(account_id, str) else account_id)
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


def delete_account(account_id: str) -> None:
    """Soft-delete an account by setting is_active=False.

    Args:
        account_id: The account UUID.
    """
    with config.SessionLocal() as session:
        account = session.get(Account, uuid.UUID(account_id) if isinstance(account_id, str) else account_id)
        if account:
            account.is_active = False
            session.commit()
