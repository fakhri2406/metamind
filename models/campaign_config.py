"""Pydantic models for Claude's JSON output — the source of truth for the JSON contract."""

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class CampaignObjective(str, Enum):
    CONVERSIONS = "CONVERSIONS"
    TRAFFIC = "TRAFFIC"
    AWARENESS = "AWARENESS"
    LEAD_GENERATION = "LEAD_GENERATION"
    ENGAGEMENT = "ENGAGEMENT"


class BudgetType(str, Enum):
    CBO = "CBO"
    ABO = "ABO"


class TargetingType(str, Enum):
    LOOKALIKE = "lookalike"
    INTEREST = "interest"
    RETARGETING = "retargeting"
    BROAD = "broad"


class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"
    ALL = "all"


class Placement(str, Enum):
    AUTOMATIC = "automatic"
    FACEBOOK_FEED = "facebook_feed"
    INSTAGRAM_FEED = "instagram_feed"
    STORIES = "stories"
    REELS = "reels"


class BidStrategy(str, Enum):
    LOWEST_COST = "LOWEST_COST"
    COST_CAP = "COST_CAP"
    BID_CAP = "BID_CAP"


class AdFormat(str, Enum):
    SINGLE_IMAGE = "single_image"
    CAROUSEL = "carousel"
    VIDEO = "video"
    COLLECTION = "collection"


class CTA(str, Enum):
    SHOP_NOW = "SHOP_NOW"
    LEARN_MORE = "LEARN_MORE"
    SIGN_UP = "SIGN_UP"
    GET_QUOTE = "GET_QUOTE"
    CONTACT_US = "CONTACT_US"
    BOOK_NOW = "BOOK_NOW"


class CampaignSpec(BaseModel):
    """Campaign-level configuration."""

    name: str = Field(..., min_length=1, max_length=200)
    objective: CampaignObjective
    budget_daily_usd: float = Field(..., gt=0)
    budget_type: BudgetType
    start_date: str
    end_date: Optional[str] = None

    @field_validator("start_date")
    @classmethod
    def start_date_not_in_past(cls, v: str) -> str:
        parsed = datetime.strptime(v, "%Y-%m-%d").date()
        if parsed < date.today():
            raise ValueError(f"start_date {v} is in the past")
        return v

    @field_validator("end_date")
    @classmethod
    def end_date_format(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            datetime.strptime(v, "%Y-%m-%d")
        return v

    @model_validator(mode="after")
    def end_after_start(self) -> "CampaignSpec":
        if self.end_date is not None:
            start = datetime.strptime(self.start_date, "%Y-%m-%d").date()
            end = datetime.strptime(self.end_date, "%Y-%m-%d").date()
            if end <= start:
                raise ValueError(
                    f"end_date ({self.end_date}) must be after start_date ({self.start_date})"
                )
        return self


class AdSetSpec(BaseModel):
    """Ad set configuration."""

    name: str = Field(..., min_length=1, max_length=200)
    targeting_type: TargetingType
    age_min: int = Field(default=18, ge=13, le=65)
    age_max: int = Field(default=65, ge=13, le=65)
    genders: list[Gender]
    interests: list[str] = Field(default_factory=list)
    lookalike_source: Optional[str] = None
    lookalike_ratio: float = Field(default=0.01, ge=0.01, le=0.20)
    placements: Placement = Placement.AUTOMATIC
    bid_strategy: BidStrategy = BidStrategy.LOWEST_COST
    bid_amount_usd: Optional[float] = None
    daily_budget_usd: Optional[float] = None

    @model_validator(mode="after")
    def validate_ad_set(self) -> "AdSetSpec":
        if self.age_max < self.age_min:
            raise ValueError(
                f"age_max ({self.age_max}) must be >= age_min ({self.age_min})"
            )
        if self.bid_strategy in (BidStrategy.COST_CAP, BidStrategy.BID_CAP):
            if self.bid_amount_usd is None:
                raise ValueError(
                    f"bid_amount_usd is required when bid_strategy is {self.bid_strategy}"
                )
        if self.targeting_type == TargetingType.LOOKALIKE:
            if not self.lookalike_source:
                raise ValueError(
                    "lookalike_source is required when targeting_type is 'lookalike'"
                )
        return self


class AdSpec(BaseModel):
    """Ad creative configuration."""

    name: str = Field(..., min_length=1, max_length=200)
    ad_set_name: str = Field(..., min_length=1)
    format: AdFormat
    headline: str = Field(..., max_length=40)
    primary_text: str = Field(..., max_length=125)
    description: Optional[str] = Field(default=None, max_length=30)
    cta: CTA
    destination_url: str
    creative_notes: str = ""

    @field_validator("destination_url")
    @classmethod
    def url_must_be_https(cls, v: str) -> str:
        if not v.startswith("https://"):
            raise ValueError(f"destination_url must start with https://, got: {v}")
        return v


class CampaignConfig(BaseModel):
    """Root model for Claude's complete campaign recommendation."""

    campaign: CampaignSpec
    ad_sets: list[AdSetSpec] = Field(..., min_length=1)
    ads: list[AdSpec] = Field(..., min_length=1)
    reasoning: str = Field(..., min_length=1)
    optimization_notes: str = ""

    @model_validator(mode="after")
    def ads_reference_valid_ad_sets(self) -> "CampaignConfig":
        ad_set_names = {ad_set.name for ad_set in self.ad_sets}
        for ad in self.ads:
            if ad.ad_set_name not in ad_set_names:
                raise ValueError(
                    f"Ad '{ad.name}' references ad_set_name '{ad.ad_set_name}' "
                    f"which does not match any ad set. Valid names: {ad_set_names}"
                )
        return self
