"""Shared test fixtures for MetaMind."""

import os
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import config
from models.campaign_config import (
    AdFormat,
    AdSetSpec,
    AdSpec,
    BidStrategy,
    BudgetType,
    CampaignConfig,
    CampaignObjective,
    CampaignSpec,
    CTA,
    Gender,
    Placement,
    TargetingType,
)
from models.meta_data import (
    AccountInfo,
    CampaignPerformance,
    CustomAudience,
    IngestedData,
)
from storage.base import Base


@pytest.fixture(autouse=True)
def test_db():
    """Set up a test PostgreSQL database and override config.engine/SessionLocal.

    Reads TEST_DATABASE_URL from the environment (defaults to a local test DB).
    Creates all tables before tests, drops them after.
    """
    test_url = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql://localhost:5432/metamind-test",
    )
    test_engine = create_engine(test_url, echo=False)
    test_session_factory = sessionmaker(
        autocommit=False, autoflush=False, bind=test_engine,
    )

    # Override config globals
    config.DATABASE_URL = test_url
    config.engine = test_engine
    config.SessionLocal = test_session_factory

    # Create all tables
    Base.metadata.create_all(test_engine)

    yield test_engine

    # Drop all tables after test
    Base.metadata.drop_all(test_engine)
    test_engine.dispose()


@pytest.fixture
def sample_campaign_config() -> CampaignConfig:
    """A valid CampaignConfig for testing."""
    return CampaignConfig(
        campaign=CampaignSpec(
            name="Test Campaign",
            objective=CampaignObjective.CONVERSIONS,
            budget_daily_usd=100.0,
            budget_type=BudgetType.CBO,
            start_date=(date.today() + timedelta(days=1)).isoformat(),
            end_date=(date.today() + timedelta(days=30)).isoformat(),
        ),
        ad_sets=[
            AdSetSpec(
                name="Interest Targeting",
                targeting_type=TargetingType.INTEREST,
                age_min=25,
                age_max=55,
                genders=[Gender.ALL],
                interests=["fitness", "yoga"],
                placements=Placement.AUTOMATIC,
                bid_strategy=BidStrategy.LOWEST_COST,
            ),
            AdSetSpec(
                name="Broad Targeting",
                targeting_type=TargetingType.BROAD,
                age_min=18,
                age_max=65,
                genders=[Gender.ALL],
                placements=Placement.AUTOMATIC,
                bid_strategy=BidStrategy.LOWEST_COST,
            ),
        ],
        ads=[
            AdSpec(
                name="Ad 1 - Interest",
                ad_set_name="Interest Targeting",
                format=AdFormat.SINGLE_IMAGE,
                headline="Get Fit Today",
                primary_text="Transform your body in 30 days",
                cta=CTA.SHOP_NOW,
                destination_url="https://example.com/product",
                creative_notes="Testing interest-based approach",
            ),
            AdSpec(
                name="Ad 2 - Broad",
                ad_set_name="Broad Targeting",
                format=AdFormat.SINGLE_IMAGE,
                headline="Limited Offer",
                primary_text="50% off for new customers",
                cta=CTA.LEARN_MORE,
                destination_url="https://example.com/product",
                creative_notes="Testing broad reach",
            ),
        ],
        reasoning="Testing strategy with interest and broad targeting for A/B comparison.",
        optimization_notes="Monitor CTR and CPA after 3 days.",
    )


@pytest.fixture
def sample_campaign_config_dict(sample_campaign_config: CampaignConfig) -> dict:
    """The sample config as a dict (for JSON testing)."""
    return sample_campaign_config.model_dump()


@pytest.fixture
def sample_ingested_data() -> IngestedData:
    """Sample ingested data for testing."""
    return IngestedData(
        account=AccountInfo(
            account_id="act_123456789",
            name="Test Ad Account",
            currency="USD",
            timezone="America/Los_Angeles",
            amount_spent=5000.0,
        ),
        campaigns=[
            CampaignPerformance(
                campaign_id="camp_001",
                campaign_name="Past Campaign 1",
                status="ACTIVE",
                objective="CONVERSIONS",
                spend=1200.0,
                impressions=150000,
                clicks=3000,
                ctr=2.0,
                cpc=0.40,
                cpm=8.0,
                conversions=50,
                conversion_value=3500.0,
                roas=2.92,
            ),
        ],
        custom_audiences=[
            CustomAudience(
                audience_id="aud_001",
                name="Website Visitors 30d",
                approximate_count=15000,
                subtype="WEBSITE",
            ),
        ],
        date_range_start=date.today() - timedelta(days=60),
        date_range_end=date.today(),
    )
