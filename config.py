"""Configuration and environment variable management."""

import base64
import os

from dotenv import load_dotenv
from rich.console import Console

from exceptions import SetupError

load_dotenv()

console = Console()

# Anthropic
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

# Safety Controls
REQUIRE_HUMAN_APPROVAL: bool = os.getenv("REQUIRE_HUMAN_APPROVAL", "true").lower() == "true"

# Encryption
_raw_encryption_key: str = os.getenv("METAMIND_ENCRYPTION_KEY", "")
ENCRYPTION_KEY: bytes = b""
if _raw_encryption_key:
    try:
        ENCRYPTION_KEY = base64.urlsafe_b64decode(_raw_encryption_key)
        # Re-encode to bytes for Fernet (it expects the base64 form)
        ENCRYPTION_KEY = _raw_encryption_key.encode()
    except Exception:
        ENCRYPTION_KEY = b""

# Constants
META_API_VERSION: str = "v21.0"
CLAUDE_MODEL: str = "claude-opus-4-6"
CLAUDE_MAX_TOKENS: int = 4096
CLAUDE_TEMPERATURE: float = 0

# Database
DB_PATH: str = os.path.join(os.path.dirname(__file__), "data", "campaign_runs.db")

_REQUIRED_VARS = {
    "ANTHROPIC_API_KEY": ANTHROPIC_API_KEY,
}


def check_setup() -> None:
    """Validate that all required environment variables are set.

    Raises:
        SetupError: If any required variables are missing or invalid.
    """
    missing = [name for name, value in _REQUIRED_VARS.items() if not value]
    if missing:
        raise SetupError(
            f"Missing required environment variables: {', '.join(missing)}. "
            f"Copy .env.example to .env and fill in all values."
        )

    if not _raw_encryption_key:
        raise SetupError(
            "Missing METAMIND_ENCRYPTION_KEY. "
            "Generate one with: python main.py generate-key"
        )

    # Validate Fernet key format (must be 32 url-safe base64-encoded bytes)
    try:
        decoded = base64.urlsafe_b64decode(_raw_encryption_key)
        if len(decoded) != 32:
            raise SetupError(
                f"METAMIND_ENCRYPTION_KEY must decode to 32 bytes, got {len(decoded)}. "
                "Generate a valid key with: python main.py generate-key"
            )
    except Exception as e:
        if isinstance(e, SetupError):
            raise
        raise SetupError(
            f"METAMIND_ENCRYPTION_KEY is not valid base64: {e}. "
            "Generate a valid key with: python main.py generate-key"
        ) from e
