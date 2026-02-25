"""Pydantic models for Meta API response data and ingested data."""

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class AccountInfo(BaseModel):
    """Meta ad account information."""

    account_id: str
    name: str
    currency: str = "USD"
    timezone: str = "America/Los_Angeles"
    spend_cap: Optional[float] = None
    amount_spent: Optional[float] = None


class CampaignPerformance(BaseModel):
    """Performance metrics for a single campaign over a date range."""

    campaign_id: str
    campaign_name: str
    status: str
    objective: str
    daily_budget: Optional[float] = None
    lifetime_budget: Optional[float] = None
    spend: float = 0.0
    impressions: int = 0
    clicks: int = 0
    ctr: float = 0.0
    cpc: Optional[float] = None
    cpm: Optional[float] = None
    conversions: int = 0
    conversion_value: float = 0.0
    roas: Optional[float] = None


class AdSetPerformance(BaseModel):
    """Performance metrics for a single ad set."""

    ad_set_id: str
    ad_set_name: str
    campaign_id: str
    status: str
    targeting_summary: str = ""
    spend: float = 0.0
    impressions: int = 0
    clicks: int = 0
    ctr: float = 0.0
    conversions: int = 0
    conversion_value: float = 0.0


class CustomAudience(BaseModel):
    """A custom audience available in the ad account."""

    audience_id: str
    name: str
    approximate_count: Optional[int] = None
    subtype: str = ""
    description: str = ""


class PastRunSummary(BaseModel):
    """Summary of a past AI-generated campaign run."""

    run_id: str
    created_at: str
    campaign_name: str
    objective: str
    budget_daily_usd: float
    reasoning: str = ""
    was_executed: bool = False


class IngestedData(BaseModel):
    """Root model containing all data pulled from Meta API for analysis."""

    account: AccountInfo
    campaigns: list[CampaignPerformance] = Field(default_factory=list)
    ad_sets: list[AdSetPerformance] = Field(default_factory=list)
    custom_audiences: list[CustomAudience] = Field(default_factory=list)
    past_runs: list[PastRunSummary] = Field(default_factory=list)
    date_range_start: date
    date_range_end: date
