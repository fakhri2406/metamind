"""Configuration and environment variable management."""

import os

from dotenv import load_dotenv
from rich.console import Console

from exceptions import SetupError

load_dotenv()

console = Console()

# Meta API
META_ACCESS_TOKEN: str = os.getenv("META_ACCESS_TOKEN", "")
META_AD_ACCOUNT_ID: str = os.getenv("META_AD_ACCOUNT_ID", "")
META_APP_ID: str = os.getenv("META_APP_ID", "")
META_APP_SECRET: str = os.getenv("META_APP_SECRET", "")
META_PAGE_ID: str = os.getenv("META_PAGE_ID", "")

# Anthropic
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

# Safety Controls
MAX_DAILY_BUDGET_USD: float = float(os.getenv("MAX_DAILY_BUDGET_USD", "500"))
REQUIRE_HUMAN_APPROVAL: bool = os.getenv("REQUIRE_HUMAN_APPROVAL", "true").lower() == "true"

# Constants
META_API_VERSION: str = "v21.0"
CLAUDE_MODEL: str = "claude-opus-4-6"
CLAUDE_MAX_TOKENS: int = 4096
CLAUDE_TEMPERATURE: float = 0

# Database
DB_PATH: str = os.path.join(os.path.dirname(__file__), "data", "campaign_runs.db")

_REQUIRED_VARS = {
    "META_ACCESS_TOKEN": META_ACCESS_TOKEN,
    "META_AD_ACCOUNT_ID": META_AD_ACCOUNT_ID,
    "META_APP_ID": META_APP_ID,
    "META_APP_SECRET": META_APP_SECRET,
    "META_PAGE_ID": META_PAGE_ID,
    "ANTHROPIC_API_KEY": ANTHROPIC_API_KEY,
}


def check_setup() -> None:
    """Validate that all required environment variables are set.

    Raises:
        SetupError: If any required variables are missing.
    """
    missing = [name for name, value in _REQUIRED_VARS.items() if not value]
    if missing:
        raise SetupError(
            f"Missing required environment variables: {', '.join(missing)}. "
            f"Copy .env.example to .env and fill in all values."
        )

    if not META_AD_ACCOUNT_ID.startswith("act_"):
        raise SetupError(
            f"META_AD_ACCOUNT_ID must start with 'act_', got: {META_AD_ACCOUNT_ID}"
        )

    if MAX_DAILY_BUDGET_USD <= 0:
        raise SetupError(
            f"MAX_DAILY_BUDGET_USD must be positive, got: {MAX_DAILY_BUDGET_USD}"
        )
