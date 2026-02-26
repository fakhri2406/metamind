"""Tests for Pydantic models — the contract between Claude and Meta API."""

import json
from datetime import date, timedelta

import pytest
from pydantic import ValidationError

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


class TestCampaignSpec:
    def test_valid_campaign(self):
        spec = CampaignSpec(
            name="Test",
            objective=CampaignObjective.CONVERSIONS,
            budget_daily_usd=50.0,
            budget_type=BudgetType.CBO,
            start_date=(date.today() + timedelta(days=1)).isoformat(),
        )
        assert spec.name == "Test"
        assert spec.objective == CampaignObjective.CONVERSIONS

    def test_start_date_in_past_raises(self):
        with pytest.raises(ValidationError, match="start_date.*past"):
            CampaignSpec(
                name="Test",
                objective=CampaignObjective.TRAFFIC,
                budget_daily_usd=50.0,
                budget_type=BudgetType.CBO,
                start_date="2020-01-01",
            )

    def test_end_date_before_start_raises(self):
        start = (date.today() + timedelta(days=5)).isoformat()
        end = (date.today() + timedelta(days=2)).isoformat()
        with pytest.raises(ValidationError, match="end_date.*must be after"):
            CampaignSpec(
                name="Test",
                objective=CampaignObjective.TRAFFIC,
                budget_daily_usd=50.0,
                budget_type=BudgetType.CBO,
                start_date=start,
                end_date=end,
            )

    def test_zero_budget_raises(self):
        with pytest.raises(ValidationError):
            CampaignSpec(
                name="Test",
                objective=CampaignObjective.TRAFFIC,
                budget_daily_usd=0,
                budget_type=BudgetType.CBO,
                start_date=(date.today() + timedelta(days=1)).isoformat(),
            )

    def test_null_end_date_is_valid(self):
        spec = CampaignSpec(
            name="Test",
            objective=CampaignObjective.AWARENESS,
            budget_daily_usd=25.0,
            budget_type=BudgetType.ABO,
            start_date=(date.today() + timedelta(days=1)).isoformat(),
            end_date=None,
        )
        assert spec.end_date is None


class TestAdSetSpec:
    def test_valid_ad_set(self):
        spec = AdSetSpec(
            name="Test Ad Set",
            targeting_type=TargetingType.INTEREST,
            age_min=25,
            age_max=45,
            genders=[Gender.ALL],
            interests=["yoga"],
        )
        assert spec.targeting_type == TargetingType.INTEREST

    def test_age_max_less_than_min_raises(self):
        with pytest.raises(ValidationError, match="age_max.*age_min"):
            AdSetSpec(
                name="Test",
                targeting_type=TargetingType.BROAD,
                age_min=45,
                age_max=25,
                genders=[Gender.ALL],
            )

    def test_cost_cap_requires_bid_amount(self):
        with pytest.raises(ValidationError, match="bid_amount_usd.*required"):
            AdSetSpec(
                name="Test",
                targeting_type=TargetingType.BROAD,
                genders=[Gender.ALL],
                bid_strategy=BidStrategy.COST_CAP,
            )

    def test_bid_cap_requires_bid_amount(self):
        with pytest.raises(ValidationError, match="bid_amount_usd.*required"):
            AdSetSpec(
                name="Test",
                targeting_type=TargetingType.BROAD,
                genders=[Gender.ALL],
                bid_strategy=BidStrategy.BID_CAP,
            )

    def test_cost_cap_with_bid_amount_valid(self):
        spec = AdSetSpec(
            name="Test",
            targeting_type=TargetingType.BROAD,
            genders=[Gender.ALL],
            bid_strategy=BidStrategy.COST_CAP,
            bid_amount_usd=5.0,
        )
        assert spec.bid_amount_usd == pytest.approx(5.0)

    def test_lookalike_requires_source(self):
        with pytest.raises(ValidationError, match="lookalike_source.*required"):
            AdSetSpec(
                name="Test",
                targeting_type=TargetingType.LOOKALIKE,
                genders=[Gender.ALL],
            )

    def test_lookalike_with_source_valid(self):
        spec = AdSetSpec(
            name="Test",
            targeting_type=TargetingType.LOOKALIKE,
            genders=[Gender.ALL],
            lookalike_source="Website Visitors 30d",
            lookalike_ratio=0.05,
        )
        assert spec.lookalike_source == "Website Visitors 30d"


class TestAdSpec:
    def test_valid_ad(self):
        spec = AdSpec(
            name="Test Ad",
            ad_set_name="Test Ad Set",
            format=AdFormat.SINGLE_IMAGE,
            headline="Buy Now",
            primary_text="Great product on sale",
            cta=CTA.SHOP_NOW,
            destination_url="https://example.com",
        )
        assert spec.format == AdFormat.SINGLE_IMAGE

    def test_http_url_raises(self):
        with pytest.raises(ValidationError, match="https://"):
            AdSpec(
                name="Test",
                ad_set_name="Test",
                format=AdFormat.SINGLE_IMAGE,
                headline="Buy",
                primary_text="Text",
                cta=CTA.SHOP_NOW,
                destination_url="http://example.com",
            )

    def test_headline_too_long_raises(self):
        with pytest.raises(ValidationError):
            AdSpec(
                name="Test",
                ad_set_name="Test",
                format=AdFormat.SINGLE_IMAGE,
                headline="A" * 41,
                primary_text="Text",
                cta=CTA.SHOP_NOW,
                destination_url="https://example.com",
            )

    def test_primary_text_too_long_raises(self):
        with pytest.raises(ValidationError):
            AdSpec(
                name="Test",
                ad_set_name="Test",
                format=AdFormat.SINGLE_IMAGE,
                headline="Headline",
                primary_text="A" * 126,
                cta=CTA.SHOP_NOW,
                destination_url="https://example.com",
            )


class TestCampaignConfig:
    def test_valid_config(self, sample_campaign_config):
        assert len(sample_campaign_config.ad_sets) == 2
        assert len(sample_campaign_config.ads) == 2

    def test_ad_references_invalid_ad_set_raises(self):
        with pytest.raises(ValidationError, match="does not match any ad set"):
            CampaignConfig(
                campaign=CampaignSpec(
                    name="Test",
                    objective=CampaignObjective.CONVERSIONS,
                    budget_daily_usd=50.0,
                    budget_type=BudgetType.CBO,
                    start_date=(date.today() + timedelta(days=1)).isoformat(),
                ),
                ad_sets=[
                    AdSetSpec(
                        name="Real Ad Set",
                        targeting_type=TargetingType.BROAD,
                        genders=[Gender.ALL],
                    )
                ],
                ads=[
                    AdSpec(
                        name="Test Ad",
                        ad_set_name="Nonexistent Ad Set",
                        format=AdFormat.SINGLE_IMAGE,
                        headline="Buy",
                        primary_text="Text",
                        cta=CTA.SHOP_NOW,
                        destination_url="https://example.com",
                    )
                ],
                reasoning="Test",
            )

    def test_json_round_trip(self, sample_campaign_config):
        json_str = sample_campaign_config.model_dump_json()
        parsed = json.loads(json_str)
        restored = CampaignConfig.model_validate(parsed)
        assert restored.campaign.name == sample_campaign_config.campaign.name
        assert len(restored.ad_sets) == len(sample_campaign_config.ad_sets)
        assert len(restored.ads) == len(sample_campaign_config.ads)

    def test_all_enum_values(self):
        """Verify all enum values are accessible."""
        assert len(CampaignObjective) == 5
        assert len(BudgetType) == 2
        assert len(TargetingType) == 4
        assert len(Gender) == 3
        assert len(Placement) == 5
        assert len(BidStrategy) == 3
        assert len(AdFormat) == 4
        assert len(CTA) == 6

    def test_empty_ad_sets_raises(self):
        with pytest.raises(ValidationError):
            CampaignConfig(
                campaign=CampaignSpec(
                    name="Test",
                    objective=CampaignObjective.CONVERSIONS,
                    budget_daily_usd=50.0,
                    budget_type=BudgetType.CBO,
                    start_date=(date.today() + timedelta(days=1)).isoformat(),
                ),
                ad_sets=[],
                ads=[
                    AdSpec(
                        name="Test Ad",
                        ad_set_name="Test",
                        format=AdFormat.SINGLE_IMAGE,
                        headline="Buy",
                        primary_text="Text",
                        cta=CTA.SHOP_NOW,
                        destination_url="https://example.com",
                    )
                ],
                reasoning="Test",
            )
