"""Tests for Phase 2: strategize module."""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest
import typer

from exceptions import BudgetCapError, StrategyError
from main import _load_ad_set_overrides
from models.campaign_config import CampaignConfig
from phases.strategize import _enforce_budget_cap, _strip_markdown_fences, _try_parse
from prompts.analysis_template import build_user_prompt


class TestStripMarkdownFences:
    def test_no_fences(self):
        assert _strip_markdown_fences('{"key": "value"}') == '{"key": "value"}'

    def test_json_fences(self):
        text = '```json\n{"key": "value"}\n```'
        assert _strip_markdown_fences(text) == '{"key": "value"}'

    def test_plain_fences(self):
        text = '```\n{"key": "value"}\n```'
        assert _strip_markdown_fences(text) == '{"key": "value"}'

    def test_whitespace(self):
        text = '  \n```json\n{"key": "value"}\n```\n  '
        assert _strip_markdown_fences(text) == '{"key": "value"}'


class TestTryParse:
    def test_valid_json(self, sample_campaign_config):
        json_str = sample_campaign_config.model_dump_json()
        result = _try_parse(json_str)
        assert isinstance(result, CampaignConfig)
        assert result.campaign.name == sample_campaign_config.campaign.name

    def test_invalid_json_raises(self):
        with pytest.raises(StrategyError, match="Invalid JSON"):
            _try_parse("not json at all")

    def test_valid_json_invalid_schema_raises(self):
        with pytest.raises(StrategyError, match="Validation failed"):
            _try_parse('{"not": "a campaign config"}')

    def test_json_with_markdown_fences(self, sample_campaign_config):
        json_str = f"```json\n{sample_campaign_config.model_dump_json()}\n```"
        result = _try_parse(json_str)
        assert isinstance(result, CampaignConfig)


class TestEnforceBudgetCap:
    def test_within_cap(self, sample_campaign_config):
        _enforce_budget_cap(sample_campaign_config, 500.0)  # Should not raise

    def test_campaign_budget_exceeds_cap(self, sample_campaign_config):
        with pytest.raises(BudgetCapError, match="exceeds cap"):
            _enforce_budget_cap(sample_campaign_config, 50.0)

    def test_ad_set_budget_exceeds_cap(self):
        """Test ABO ad set budget exceeds cap."""
        start = (date.today() + timedelta(days=1)).isoformat()
        config_data = {
            "campaign": {
                "name": "Test",
                "objective": "CONVERSIONS",
                "budget_daily_usd": 10.0,
                "budget_type": "ABO",
                "start_date": start,
            },
            "ad_sets": [
                {
                    "name": "Expensive Set",
                    "targeting_type": "broad",
                    "genders": ["all"],
                    "daily_budget_usd": 600.0,
                }
            ],
            "ads": [
                {
                    "name": "Ad",
                    "ad_set_name": "Expensive Set",
                    "format": "single_image",
                    "headline": "Buy",
                    "primary_text": "Text",
                    "cta": "SHOP_NOW",
                    "destination_url": "https://example.com",
                }
            ],
            "reasoning": "Test",
        }
        campaign_config = CampaignConfig.model_validate(config_data)
        with pytest.raises(BudgetCapError, match="Expensive Set"):
            _enforce_budget_cap(campaign_config, 500.0)


class TestRunStrategize:
    @patch("phases.strategize.anthropic")
    def test_successful_strategize(
            self, mock_anthropic, sample_campaign_config, sample_ingested_data
    ):
        """Test successful strategy generation with mocked Claude API."""
        from storage.logger import RunLogger

        # Mock the Anthropic client
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text=sample_campaign_config.model_dump_json())
        ]
        mock_client.messages.create.return_value = mock_response

        logger = RunLogger()
        run_id = logger.create_run()

        from phases.strategize import run_strategize

        result = run_strategize(
            data=sample_ingested_data,
            logger=logger,
            run_id=run_id,
            product_name="Test Product",
            product_url="https://example.com",
            product_description="A test product",
            target_customer="Adults 25-55",
            goal="maximize purchases",
            budget=100.0,
            max_daily_budget_usd=500.0,
        )

        assert isinstance(result, CampaignConfig)
        assert result.campaign.name == sample_campaign_config.campaign.name
        mock_client.messages.create.assert_called_once()

    @patch("phases.strategize.anthropic")
    def test_retry_on_first_failure(
            self, mock_anthropic, sample_campaign_config, sample_ingested_data
    ):
        """Test that strategy retries once on parse failure."""
        from storage.logger import RunLogger

        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client

        # First call returns invalid JSON, second returns valid
        bad_response = MagicMock()
        bad_response.content = [MagicMock(text="not valid json")]
        good_response = MagicMock()
        good_response.content = [
            MagicMock(text=sample_campaign_config.model_dump_json())
        ]
        mock_client.messages.create.side_effect = [bad_response, good_response]

        logger = RunLogger()
        run_id = logger.create_run()

        from phases.strategize import run_strategize

        result = run_strategize(
            data=sample_ingested_data,
            logger=logger,
            run_id=run_id,
            product_name="Test Product",
            product_url="https://example.com",
            product_description="A test",
            target_customer="Adults",
            goal="purchases",
            budget=100.0,
            max_daily_budget_usd=500.0,
        )

        assert isinstance(result, CampaignConfig)
        assert mock_client.messages.create.call_count == 2

    @patch("phases.strategize.anthropic")
    def test_strategy_error_after_two_failures(
            self, mock_anthropic, sample_ingested_data
    ):
        """Test that StrategyError is raised after two parse failures."""
        from storage.logger import RunLogger

        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client

        bad_response = MagicMock()
        bad_response.content = [MagicMock(text="not valid json")]
        mock_client.messages.create.return_value = bad_response

        logger = RunLogger()
        run_id = logger.create_run()

        from phases.strategize import run_strategize

        with pytest.raises(StrategyError, match="failed to return valid JSON after retry"):
            run_strategize(
                data=sample_ingested_data,
                logger=logger,
                run_id=run_id,
                product_name="Test",
                product_url="https://example.com",
                product_description="Test",
                target_customer="Adults",
                goal="purchases",
                budget=100.0,
                max_daily_budget_usd=500.0,
            )

        assert mock_client.messages.create.call_count == 2


class TestAdSetOverrides:
    """Tests for per-ad-set configuration overrides in the prompt."""

    def test_overrides_present_in_prompt(self, sample_ingested_data):
        """Override section appears in prompt when overrides are provided."""
        overrides = {
            "Interest Targeting - Fitness": {
                "age_min": 25,
                "age_max": 45,
                "target_customer": "Yoga enthusiasts",
            }
        }
        prompt = build_user_prompt(
            data=sample_ingested_data,
            product_name="Test",
            product_url="https://example.com",
            product_description="Test product",
            target_customer="Everyone",
            goal="sales",
            budget=100.0,
            ad_set_overrides=overrides,
        )
        assert "Per-Ad-Set Configuration Overrides" in prompt
        assert "Interest Targeting - Fitness" in prompt
        assert "**age_min:** 25" in prompt
        assert "**age_max:** 45" in prompt
        assert "Yoga enthusiasts" in prompt

    def test_overrides_absent_no_section(self, sample_ingested_data):
        """No override section when overrides are None."""
        prompt = build_user_prompt(
            data=sample_ingested_data,
            product_name="Test",
            product_url="https://example.com",
            product_description="Test product",
            target_customer="Everyone",
            goal="sales",
            budget=100.0,
            ad_set_overrides=None,
        )
        assert "Per-Ad-Set Configuration Overrides" not in prompt

    def test_overrides_empty_dict_no_section(self, sample_ingested_data):
        """No override section when overrides is an empty dict."""
        prompt = build_user_prompt(
            data=sample_ingested_data,
            product_name="Test",
            product_url="https://example.com",
            product_description="Test product",
            target_customer="Everyone",
            goal="sales",
            budget=100.0,
            ad_set_overrides={},
        )
        assert "Per-Ad-Set Configuration Overrides" not in prompt

    def test_partial_override_only_specified_fields(self, sample_ingested_data):
        """Only the fields in the override appear for that ad set."""
        overrides = {
            "Broad Targeting": {"age_min": 21},
        }
        prompt = build_user_prompt(
            data=sample_ingested_data,
            product_name="Test",
            product_url="https://example.com",
            product_description="Test product",
            target_customer="Everyone",
            goal="sales",
            budget=100.0,
            ad_set_overrides=overrides,
        )
        # The override section for "Broad Targeting" should contain age_min
        assert "**age_min:** 21" in prompt
        # Extract the Broad Targeting subsection and check age_max is NOT there
        broad_section = prompt.split('"Broad Targeting"')[1].split("##")[0]
        assert "age_max" not in broad_section

    def test_multiple_ad_sets_all_rendered(self, sample_ingested_data):
        """Multiple ad set overrides all appear in the prompt."""
        overrides = {
            "Set A": {"age_min": 25},
            "Set B": {"creative_approach": "Use video"},
            "Set C": {"ads_per_ad_set": 4},
        }
        prompt = build_user_prompt(
            data=sample_ingested_data,
            product_name="Test",
            product_url="https://example.com",
            product_description="Test product",
            target_customer="Everyone",
            goal="sales",
            budget=100.0,
            ad_set_overrides=overrides,
        )
        assert '"Set A"' in prompt
        assert '"Set B"' in prompt
        assert '"Set C"' in prompt

    @patch("phases.strategize.anthropic")
    def test_run_strategize_passes_overrides_through(
            self, mock_anthropic, sample_campaign_config, sample_ingested_data
    ):
        """Overrides flow from run_strategize through to build_user_prompt."""
        from storage.logger import RunLogger
        from phases.strategize import run_strategize

        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text=sample_campaign_config.model_dump_json())
        ]
        mock_client.messages.create.return_value = mock_response

        logger = RunLogger()
        run_id = logger.create_run()

        overrides = {"Interest Targeting": {"age_min": 30}}

        with patch("phases.strategize.build_user_prompt") as mock_build:
            mock_build.return_value = "mocked prompt"
            run_strategize(
                data=sample_ingested_data,
                logger=logger,
                run_id=run_id,
                product_name="Test",
                product_url="https://example.com",
                product_description="Test",
                target_customer="Adults",
                goal="sales",
                budget=100.0,
                max_daily_budget_usd=500.0,
                ad_set_overrides=overrides,
            )
            mock_build.assert_called_once()
            _, kwargs = mock_build.call_args
            assert kwargs["ad_set_overrides"] == overrides


class TestLoadAdSetOverrides:
    """Tests for the JSON file loading helper."""

    def test_valid_file(self, tmp_path):
        path = tmp_path / "overrides.json"
        path.write_text('{"Set A": {"age_min": 25}}')
        result = _load_ad_set_overrides(str(path))
        assert result == {"Set A": {"age_min": 25}}

    def test_invalid_json(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("not json")
        with pytest.raises(typer.BadParameter, match="not valid JSON"):
            _load_ad_set_overrides(str(path))

    def test_file_not_found(self):
        with pytest.raises(typer.BadParameter, match="not found"):
            _load_ad_set_overrides("/nonexistent/path.json")

    def test_top_level_not_dict(self, tmp_path):
        path = tmp_path / "array.json"
        path.write_text("[1, 2, 3]")
        with pytest.raises(typer.BadParameter, match="must be a JSON object"):
            _load_ad_set_overrides(str(path))

    def test_value_not_dict(self, tmp_path):
        path = tmp_path / "flat.json"
        path.write_text('{"Set A": "not a dict"}')
        with pytest.raises(typer.BadParameter, match="must be an object"):
            _load_ad_set_overrides(str(path))
