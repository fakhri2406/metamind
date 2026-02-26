"""Thin wrapper around the facebook-business SDK with retry logic."""

import time
from typing import Any

from facebook_business.adobjects.ad import Ad
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.adset import AdSet
from facebook_business.adobjects.campaign import Campaign
from facebook_business.adobjects.targetingsearch import TargetingSearch
from facebook_business.api import FacebookAdsApi
from facebook_business.exceptions import FacebookRequestError
from rich.console import Console

import config
from exceptions import MetaAPIError

console = Console()

_MAX_RETRIES = 3
_RETRYABLE_ERROR_CODES = {17, 80004}


_CONVERSION_ACTION_TYPES = {
    "offsite_conversion.fb_pixel_purchase",
    "offsite_conversion.fb_pixel_lead",
    "lead",
    "purchase",
}
_CONVERSION_VALUE_ACTION_TYPES = {
    "offsite_conversion.fb_pixel_purchase",
    "purchase",
}


def _extract_conversions(row: dict[str, Any]) -> tuple[int, float]:
    """Extract conversion count and value from a Meta insights row.

    Returns:
        Tuple of (conversions, conversion_value).
    """
    conversions = 0
    for action in row.get("actions", []):
        if action.get("action_type") in _CONVERSION_ACTION_TYPES:
            conversions += int(action.get("value", 0))

    conversion_value = 0.0
    for av in row.get("action_values", []):
        if av.get("action_type") in _CONVERSION_VALUE_ACTION_TYPES:
            conversion_value += float(av.get("value", 0))

    return conversions, conversion_value


class MetaClient:
    """Wrapper around the Meta Marketing API with automatic retry on rate limits."""

    def __init__(
        self,
        access_token: str,
        app_id: str,
        app_secret: str,
        ad_account_id: str,
    ) -> None:
        """Initialize the Meta client with account credentials.

        Args:
            access_token: Meta System User long-lived access token.
            app_id: Meta Developer App ID.
            app_secret: Meta Developer App Secret.
            ad_account_id: Meta Ad Account ID (format: act_XXXXXXXXX).
        """
        FacebookAdsApi.init(
            app_id=app_id,
            app_secret=app_secret,
            access_token=access_token,
            api_version=config.META_API_VERSION,
        )
        self._ad_account_id = ad_account_id
        self._account = AdAccount(ad_account_id)

    @property
    def ad_account_id(self) -> str:
        """Return the ad account ID."""
        return self._ad_account_id

    def _retry_on_rate_limit(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        """Execute a function with exponential backoff retry on rate limit errors."""
        for attempt in range(_MAX_RETRIES):
            try:
                return func(*args, **kwargs)
            except FacebookRequestError as e:
                if e.api_error_code() in _RETRYABLE_ERROR_CODES and attempt < _MAX_RETRIES - 1:
                    wait_time = 2 ** (attempt + 1)
                    console.print(
                        f"[yellow]Rate limited (code {e.api_error_code()}). "
                        f"Retrying in {wait_time}s (attempt {attempt + 1}/{_MAX_RETRIES})...[/yellow]"
                    )
                    time.sleep(wait_time)
                else:
                    raise MetaAPIError(
                        f"Meta API error after {attempt + 1} attempts: {e.api_error_message()}"
                    ) from e
        raise MetaAPIError("Max retries exceeded")

    # --- Read methods ---

    def get_account_info(self) -> dict[str, Any]:
        """Fetch ad account information."""
        fields = [
            "name",
            "currency",
            "timezone_name",
            "spend_cap",
            "amount_spent",
            "account_id",
        ]
        result = self._retry_on_rate_limit(self._account.api_get, fields=fields)
        return {
            "account_id": result.get("account_id", self._ad_account_id),
            "name": result.get("name", ""),
            "currency": result.get("currency", "USD"),
            "timezone": result.get("timezone_name", ""),
            "spend_cap": (
                float(result["spend_cap"]) / 100 if result.get("spend_cap") else None
            ),
            "amount_spent": (
                float(result["amount_spent"]) / 100
                if result.get("amount_spent")
                else None
            ),
        }

    def get_campaigns(
            self, date_start: str, date_end: str
    ) -> list[dict[str, Any]]:
        """Fetch campaign performance data for a date range."""
        fields = [
            "campaign_name",
            "campaign_id",
            "objective",
            "spend",
            "impressions",
            "clicks",
            "ctr",
            "cpc",
            "cpm",
            "actions",
            "action_values",
        ]
        params = {
            "time_range": {"since": date_start, "until": date_end},
            "level": "campaign",
            "filtering": [],
        }
        insights = self._retry_on_rate_limit(
            self._account.get_insights, fields=fields, params=params
        )
        campaigns = []
        for row in insights:
            conversions, conversion_value = _extract_conversions(row)
            spend = float(row.get("spend", 0))
            roas = conversion_value / spend if spend > 0 else None

            campaigns.append({
                "campaign_id": row.get("campaign_id", ""),
                "campaign_name": row.get("campaign_name", ""),
                "status": "",
                "objective": row.get("objective", ""),
                "spend": spend,
                "impressions": int(row.get("impressions", 0)),
                "clicks": int(row.get("clicks", 0)),
                "ctr": float(row.get("ctr", 0)),
                "cpc": float(row["cpc"]) if row.get("cpc") else None,
                "cpm": float(row["cpm"]) if row.get("cpm") else None,
                "conversions": conversions,
                "conversion_value": conversion_value,
                "roas": roas,
            })
        return campaigns

    def get_ad_sets(
            self, date_start: str, date_end: str
    ) -> list[dict[str, Any]]:
        """Fetch ad set performance data for a date range."""
        fields = [
            "adset_name",
            "adset_id",
            "campaign_id",
            "spend",
            "impressions",
            "clicks",
            "ctr",
            "actions",
            "action_values",
        ]
        params = {
            "time_range": {"since": date_start, "until": date_end},
            "level": "adset",
        }
        insights = self._retry_on_rate_limit(
            self._account.get_insights, fields=fields, params=params
        )
        ad_sets = []
        for row in insights:
            conversions, conversion_value = _extract_conversions(row)
            ad_sets.append({
                "ad_set_id": row.get("adset_id", ""),
                "ad_set_name": row.get("adset_name", ""),
                "campaign_id": row.get("campaign_id", ""),
                "status": "",
                "spend": float(row.get("spend", 0)),
                "impressions": int(row.get("impressions", 0)),
                "clicks": int(row.get("clicks", 0)),
                "ctr": float(row.get("ctr", 0)),
                "conversions": conversions,
                "conversion_value": conversion_value,
            })
        return ad_sets

    def get_custom_audiences(self) -> list[dict[str, Any]]:
        """Fetch custom audiences for the ad account."""
        fields = ["name", "approximate_count", "subtype", "description"]
        audiences = self._retry_on_rate_limit(
            self._account.get_custom_audiences, fields=fields
        )
        return [
            {
                "audience_id": aud.get("id", ""),
                "name": aud.get("name", ""),
                "approximate_count": aud.get("approximate_count"),
                "subtype": aud.get("subtype", ""),
                "description": aud.get("description", ""),
            }
            for aud in audiences
        ]

    # --- Write methods ---

    def create_campaign(self, params: dict[str, Any]) -> str:
        """Create a campaign. Always sets status=PAUSED."""
        params["status"] = Campaign.Status.paused
        result = self._retry_on_rate_limit(
            self._account.create_campaign, fields=[], params=params
        )
        return result["id"]

    def create_ad_set(self, params: dict[str, Any]) -> str:
        """Create an ad set. Always sets status=PAUSED."""
        params["status"] = AdSet.Status.paused
        result = self._retry_on_rate_limit(
            self._account.create_ad_set, fields=[], params=params
        )
        return result["id"]

    def create_ad_creative(self, params: dict[str, Any]) -> str:
        """Create an ad creative."""
        result = self._retry_on_rate_limit(
            self._account.create_ad_creative, fields=[], params=params
        )
        return result["id"]

    def create_ad(self, params: dict[str, Any]) -> str:
        """Create an ad. Always sets status=PAUSED."""
        params["status"] = Ad.Status.paused
        result = self._retry_on_rate_limit(
            self._account.create_ad, fields=[], params=params
        )
        return result["id"]

    def search_interests(self, query: str) -> list[dict[str, Any]]:
        """Search for targeting interests by name. Returns list of {id, name} dicts."""
        params = {
            "q": query,
            "type": "adinterest",
        }
        results = self._retry_on_rate_limit(TargetingSearch.search, params=params)
        return [{"id": r["id"], "name": r["name"]} for r in results]
