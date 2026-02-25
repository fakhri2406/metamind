"""Custom exceptions for the MetaMind application."""


class MetaAPIError(Exception):
    """Raised when a Meta API call fails after retries."""


class StrategyError(Exception):
    """Raised when Claude returns invalid/unparseable JSON after retry."""


class BudgetCapError(Exception):
    """Raised when Claude's recommended budget exceeds MAX_DAILY_BUDGET_USD."""


class SetupError(Exception):
    """Raised when required environment variables are missing at startup."""
