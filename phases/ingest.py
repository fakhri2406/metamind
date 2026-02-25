"""Phase 1: Pull account data from Meta Marketing API."""

from datetime import date, timedelta

from rich.console import Console

from models.meta_data import (
    AccountInfo,
    AdSetPerformance,
    CampaignPerformance,
    CustomAudience,
    IngestedData,
)
from storage.logger import RunLogger
from utils.meta_client import MetaClient

console = Console()

_LOOKBACK_DAYS = 60


def run_ingest(
    client: MetaClient,
    logger: RunLogger,
    run_id: str,
) -> IngestedData:
    """Pull all relevant data from the Meta Marketing API.

    Args:
        client: Initialized MetaClient instance.
        logger: RunLogger for persisting data.
        run_id: Current run ID for logging.

    Returns:
        IngestedData containing account info, performance data, and audiences.
    """
    console.print("[bold blue]Phase 1: Ingesting data from Meta API...[/bold blue]")

    date_end = date.today()
    date_start = date_end - timedelta(days=_LOOKBACK_DAYS)
    date_start_str = date_start.isoformat()
    date_end_str = date_end.isoformat()

    # Account info
    console.print("  Fetching account info...")
    account_raw = client.get_account_info()
    account = AccountInfo(**account_raw)

    # Campaign performance
    console.print(f"  Fetching campaign performance ({date_start_str} to {date_end_str})...")
    campaigns_raw = client.get_campaigns(date_start_str, date_end_str)
    campaigns = [CampaignPerformance(**c) for c in campaigns_raw]
    console.print(f"    Found {len(campaigns)} campaigns")

    # Ad set performance
    console.print("  Fetching ad set performance...")
    ad_sets_raw = client.get_ad_sets(date_start_str, date_end_str)
    ad_sets = [AdSetPerformance(**a) for a in ad_sets_raw]
    console.print(f"    Found {len(ad_sets)} ad sets")

    # Custom audiences
    console.print("  Fetching custom audiences...")
    audiences_raw = client.get_custom_audiences()
    audiences = [CustomAudience(**a) for a in audiences_raw]
    console.print(f"    Found {len(audiences)} custom audiences")

    # Past AI run summaries
    console.print("  Loading past AI run history...")
    past_runs = logger.get_past_run_summaries()
    console.print(f"    Found {len(past_runs)} past runs")

    data = IngestedData(
        account=account,
        campaigns=campaigns,
        ad_sets=ad_sets,
        custom_audiences=audiences,
        past_runs=past_runs,
        date_range_start=date_start,
        date_range_end=date_end,
    )

    # Log ingested data
    logger.log_ingested_data(run_id, data.model_dump_json())

    console.print("[bold green]  Phase 1 complete.[/bold green]\n")
    return data
