"""Tests for Phase 1: ingest module."""

from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from exceptions import MetaAPIError
from models.meta_data import IngestedData
from phases.ingest import run_ingest


class TestRunIngest:
    def _make_mock_client(self) -> MagicMock:
        """Create a mock MetaClient with standard responses."""
        client = MagicMock()
        client.get_account_info.return_value = {
            "account_id": "act_123456789",
            "name": "Test Account",
            "currency": "USD",
            "timezone": "America/Los_Angeles",
            "spend_cap": None,
            "amount_spent": 5000.0,
        }
        client.get_campaigns.return_value = [
            {
                "campaign_id": "camp_001",
                "campaign_name": "Test Campaign",
                "status": "ACTIVE",
                "objective": "CONVERSIONS",
                "spend": 500.0,
                "impressions": 50000,
                "clicks": 1000,
                "ctr": 2.0,
                "cpc": 0.50,
                "cpm": 10.0,
                "conversions": 20,
                "conversion_value": 1400.0,
                "roas": 2.8,
            }
        ]
        client.get_ad_sets.return_value = [
            {
                "ad_set_id": "adset_001",
                "ad_set_name": "Test Ad Set",
                "campaign_id": "camp_001",
                "status": "ACTIVE",
                "spend": 500.0,
                "impressions": 50000,
                "clicks": 1000,
                "ctr": 2.0,
                "conversions": 20,
                "conversion_value": 1400.0,
            }
        ]
        client.get_custom_audiences.return_value = [
            {
                "audience_id": "aud_001",
                "name": "Website Visitors",
                "approximate_count": 10000,
                "subtype": "WEBSITE",
                "description": "",
            }
        ]
        return client

    def test_successful_ingest(self):
        """Test successful data ingestion."""
        from storage.logger import RunLogger

        client = self._make_mock_client()
        logger = RunLogger()
        run_id = logger.create_run()

        # Mock past_run_summaries
        logger.get_past_run_summaries = MagicMock(return_value=[])

        result = run_ingest(client, logger, run_id)

        assert isinstance(result, IngestedData)
        assert result.account.account_id == "act_123456789"
        assert len(result.campaigns) == 1
        assert len(result.ad_sets) == 1
        assert len(result.custom_audiences) == 1
        assert result.date_range_end == date.today()
        assert result.date_range_start == date.today() - timedelta(days=60)

        client.get_account_info.assert_called_once()
        client.get_campaigns.assert_called_once()
        client.get_ad_sets.assert_called_once()
        client.get_custom_audiences.assert_called_once()

    def test_empty_data_handling(self):
        """Test ingestion when account has no historical data."""
        from storage.logger import RunLogger

        client = self._make_mock_client()
        client.get_campaigns.return_value = []
        client.get_ad_sets.return_value = []
        client.get_custom_audiences.return_value = []

        logger = RunLogger()
        run_id = logger.create_run()
        logger.get_past_run_summaries = MagicMock(return_value=[])

        result = run_ingest(client, logger, run_id)

        assert isinstance(result, IngestedData)
        assert len(result.campaigns) == 0
        assert len(result.ad_sets) == 0
        assert len(result.custom_audiences) == 0

    def test_meta_api_error_propagates(self):
        """Test that MetaAPIError from the client propagates."""
        from storage.logger import RunLogger

        client = MagicMock()
        client.get_account_info.side_effect = MetaAPIError("API failed")

        logger = RunLogger()
        run_id = logger.create_run()

        with pytest.raises(MetaAPIError, match="API failed"):
            run_ingest(client, logger, run_id)

    def test_ingested_data_logged(self):
        """Test that ingested data is logged to the database."""
        from storage.logger import RunLogger

        client = self._make_mock_client()
        logger = RunLogger()
        run_id = logger.create_run()
        logger.get_past_run_summaries = MagicMock(return_value=[])

        run_ingest(client, logger, run_id)

        run = logger.get_run(run_id)
        assert run is not None
        assert run.ingested_data_json is not None
