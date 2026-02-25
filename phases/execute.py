"""Phase 3: Execute campaign creation via Meta API."""

from typing import Any

from rich.console import Console
from rich.table import Table

from exceptions import MetaAPIError
from models.campaign_config import (
    AdFormat,
    AdSetSpec,
    AdSpec,
    BidStrategy,
    CampaignConfig,
    CampaignObjective,
    CTA,
    Gender,
    Placement,
)
from storage.logger import RunLogger
from utils.meta_client import MetaClient

console = Console()

# TODO: Replace with real image upload via /act_{id}/adimages.
# This is a known limitation — creative assets need proper upload flow.
_PLACEHOLDER_IMAGE_HASH = "placeholder_image_hash_replace_me"

# Map our objectives to Meta's OUTCOME_* enum
_OBJECTIVE_MAP: dict[CampaignObjective, str] = {
    CampaignObjective.CONVERSIONS: "OUTCOME_SALES",
    CampaignObjective.TRAFFIC: "OUTCOME_TRAFFIC",
    CampaignObjective.AWARENESS: "OUTCOME_AWARENESS",
    CampaignObjective.LEAD_GENERATION: "OUTCOME_LEADS",
    CampaignObjective.ENGAGEMENT: "OUTCOME_ENGAGEMENT",
}

# Map CTA enum to Meta's call_to_action_type values
_CTA_MAP: dict[CTA, str] = {
    CTA.SHOP_NOW: "SHOP_NOW",
    CTA.LEARN_MORE: "LEARN_MORE",
    CTA.SIGN_UP: "SIGN_UP",
    CTA.GET_QUOTE: "GET_QUOTE",
    CTA.CONTACT_US: "CONTACT_US",
    CTA.BOOK_NOW: "BOOK_NOW",
}


def _usd_to_cents(usd: float) -> int:
    """Convert USD to cents for Meta API. This conversion happens HERE only."""
    return int(usd * 100)


def _build_targeting_spec(
        ad_set: AdSetSpec,
        resolved_interests: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Build Meta API targeting spec from an AdSetSpec."""
    targeting: dict[str, Any] = {
        "age_min": ad_set.age_min,
        "age_max": ad_set.age_max,
    }

    # Genders: Meta uses 1=male, 2=female; omit for all
    if Gender.ALL not in ad_set.genders:
        gender_map = {Gender.MALE: 1, Gender.FEMALE: 2}
        targeting["genders"] = [gender_map[g] for g in ad_set.genders]

    # Interests (resolved to IDs)
    if ad_set.interests:
        interest_objects = []
        for interest_name in ad_set.interests:
            if interest_name in resolved_interests and resolved_interests[interest_name]:
                interest_objects.append(resolved_interests[interest_name][0])
            else:
                console.print(
                    f"  [yellow]Warning: Could not resolve interest '{interest_name}', skipping[/yellow]"
                )
        if interest_objects:
            targeting["flexible_spec"] = [{"interests": interest_objects}]

    # Placements
    if ad_set.placements != Placement.AUTOMATIC:
        placement_map: dict[Placement, dict[str, Any]] = {
            Placement.FACEBOOK_FEED: {
                "facebook_positions": ["feed"],
                "publisher_platforms": ["facebook"],
            },
            Placement.INSTAGRAM_FEED: {
                "instagram_positions": ["stream"],
                "publisher_platforms": ["instagram"],
            },
            Placement.STORIES: {
                "facebook_positions": ["story"],
                "instagram_positions": ["story"],
                "publisher_platforms": ["facebook", "instagram"],
            },
            Placement.REELS: {
                "facebook_positions": ["reels"],
                "instagram_positions": ["reels"],
                "publisher_platforms": ["facebook", "instagram"],
            },
        }
        if ad_set.placements in placement_map:
            targeting.update(placement_map[ad_set.placements])

    return targeting


def _build_campaign_params(campaign_config: CampaignConfig) -> dict[str, Any]:
    """Build Meta API params for campaign creation."""
    campaign = campaign_config.campaign
    params: dict[str, Any] = {
        "name": campaign.name,
        "objective": _OBJECTIVE_MAP[campaign.objective],
        "special_ad_categories": [],
    }

    if campaign.budget_type.value == "CBO":
        params["daily_budget"] = _usd_to_cents(campaign.budget_daily_usd)

    return params


def _build_ad_set_params(
        ad_set: AdSetSpec,
        campaign_id: str,
        campaign_config: CampaignConfig,
        resolved_interests: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Build Meta API params for ad set creation."""
    params: dict[str, Any] = {
        "name": ad_set.name,
        "campaign_id": campaign_id,
        "targeting": _build_targeting_spec(ad_set, resolved_interests),
        "billing_event": "IMPRESSIONS",
        "optimization_goal": "OFFSITE_CONVERSIONS",
        "start_time": campaign_config.campaign.start_date,
    }

    if campaign_config.campaign.end_date:
        params["end_time"] = campaign_config.campaign.end_date

    # Budget (ABO)
    if ad_set.daily_budget_usd is not None:
        params["daily_budget"] = _usd_to_cents(ad_set.daily_budget_usd)

    # Bid strategy
    bid_map = {
        BidStrategy.LOWEST_COST: "LOWEST_COST_WITHOUT_CAP",
        BidStrategy.COST_CAP: "COST_CAP",
        BidStrategy.BID_CAP: "LOWEST_COST_WITH_BID_CAP",
    }
    params["bid_strategy"] = bid_map[ad_set.bid_strategy]

    if ad_set.bid_amount_usd is not None:
        params["bid_amount"] = _usd_to_cents(ad_set.bid_amount_usd)

    return params


def _build_creative_params(
        ad: AdSpec,
        page_id: str,
) -> dict[str, Any]:
    """Build Meta API params for ad creative creation."""
    if ad.format == AdFormat.SINGLE_IMAGE:
        object_story_spec = {
            "page_id": page_id,
            "link_data": {
                "image_hash": _PLACEHOLDER_IMAGE_HASH,
                "link": ad.destination_url,
                "message": ad.primary_text,
                "name": ad.headline,
                "call_to_action": {
                    "type": _CTA_MAP[ad.cta],
                    "value": {"link": ad.destination_url},
                },
            },
        }
        if ad.description:
            object_story_spec["link_data"]["description"] = ad.description
    elif ad.format == AdFormat.CAROUSEL:
        console.print(
            f"  [yellow]Warning: Carousel format for ad '{ad.name}' — using basic structure. "
            f"Full carousel support is not yet implemented.[/yellow]"
        )
        object_story_spec = {
            "page_id": page_id,
            "link_data": {
                "link": ad.destination_url,
                "message": ad.primary_text,
                "name": ad.headline,
                "child_attachments": [
                    {
                        "link": ad.destination_url,
                        "image_hash": _PLACEHOLDER_IMAGE_HASH,
                        "name": ad.headline,
                    }
                ],
                "call_to_action": {
                    "type": _CTA_MAP[ad.cta],
                    "value": {"link": ad.destination_url},
                },
            },
        }
    elif ad.format == AdFormat.VIDEO:
        console.print(
            f"  [yellow]Warning: Video format for ad '{ad.name}' — using placeholder. "
            f"Full video support is not yet implemented.[/yellow]"
        )
        object_story_spec = {
            "page_id": page_id,
            "link_data": {
                "image_hash": _PLACEHOLDER_IMAGE_HASH,
                "link": ad.destination_url,
                "message": ad.primary_text,
                "name": ad.headline,
                "call_to_action": {
                    "type": _CTA_MAP[ad.cta],
                    "value": {"link": ad.destination_url},
                },
            },
        }
    else:  # COLLECTION
        console.print(
            f"  [yellow]Warning: Collection format for ad '{ad.name}' — using basic structure. "
            f"Full collection support is not yet implemented.[/yellow]"
        )
        object_story_spec = {
            "page_id": page_id,
            "link_data": {
                "image_hash": _PLACEHOLDER_IMAGE_HASH,
                "link": ad.destination_url,
                "message": ad.primary_text,
                "name": ad.headline,
                "call_to_action": {
                    "type": _CTA_MAP[ad.cta],
                    "value": {"link": ad.destination_url},
                },
            },
        }

    return {
        "name": f"Creative - {ad.name}",
        "object_story_spec": object_story_spec,
    }


def _execute_dry_run(campaign_config: CampaignConfig) -> None:
    """Print what would be created without making API calls."""
    console.print("\n[bold yellow]DRY RUN — No API calls will be made[/bold yellow]\n")

    # Campaign table
    table = Table(title="Campaign to Create")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")
    c = campaign_config.campaign
    table.add_row("Name", c.name)
    table.add_row("Objective", c.objective.value)
    table.add_row("Budget", f"${c.budget_daily_usd:.2f}/day ({c.budget_type.value})")
    table.add_row("Start Date", c.start_date)
    table.add_row("End Date", c.end_date or "No end date")
    table.add_row("Status", "PAUSED")
    console.print(table)

    # Ad sets table
    for ad_set in campaign_config.ad_sets:
        table = Table(title=f"Ad Set: {ad_set.name}")
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="white")
        table.add_row("Targeting Type", ad_set.targeting_type.value)
        table.add_row("Age Range", f"{ad_set.age_min}-{ad_set.age_max}")
        table.add_row("Genders", ", ".join(g.value for g in ad_set.genders))
        if ad_set.interests:
            table.add_row("Interests", ", ".join(ad_set.interests))
        if ad_set.lookalike_source:
            table.add_row("Lookalike Source", ad_set.lookalike_source)
        table.add_row("Placements", ad_set.placements.value)
        table.add_row("Bid Strategy", ad_set.bid_strategy.value)
        if ad_set.bid_amount_usd is not None:
            table.add_row("Bid Amount", f"${ad_set.bid_amount_usd:.2f}")
        if ad_set.daily_budget_usd is not None:
            table.add_row("Daily Budget", f"${ad_set.daily_budget_usd:.2f}")
        table.add_row("Status", "PAUSED")
        console.print(table)

    # Ads table
    for ad in campaign_config.ads:
        table = Table(title=f"Ad: {ad.name}")
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="white")
        table.add_row("Ad Set", ad.ad_set_name)
        table.add_row("Format", ad.format.value)
        table.add_row("Headline", ad.headline)
        table.add_row("Primary Text", ad.primary_text)
        if ad.description:
            table.add_row("Description", ad.description)
        table.add_row("CTA", ad.cta.value)
        table.add_row("URL", ad.destination_url)
        table.add_row("Creative Notes", ad.creative_notes)
        table.add_row("Status", "PAUSED")
        console.print(table)


def _resolve_all_interests(
        client: MetaClient,
        campaign_config: CampaignConfig,
) -> dict[str, list[dict[str, Any]]]:
    """Resolve all unique interest names to Meta targeting IDs."""
    unique_interests: set[str] = set()
    for ad_set in campaign_config.ad_sets:
        for interest in ad_set.interests:
            unique_interests.add(interest)

    resolved: dict[str, list[dict[str, Any]]] = {}
    for interest_name in unique_interests:
        console.print(f"  Resolving interest: '{interest_name}'...")
        results = client.search_interests(interest_name)
        resolved[interest_name] = results
        if results:
            console.print(f"    → {results[0]['name']} (ID: {results[0]['id']})")
        else:
            console.print("    [yellow]→ No results found[/yellow]")

    return resolved


def _execute_real(
        client: MetaClient,
        campaign_config: CampaignConfig,
        logger: RunLogger,
        run_id: str,
        page_id: str,
) -> None:
    """Execute real API calls to create the campaign."""
    console.print("\n[bold red]LIVE EXECUTION — Creating real campaigns[/bold red]\n")

    try:
        # Step 1: Create campaign
        console.print("  Creating campaign...")
        campaign_params = _build_campaign_params(campaign_config)
        campaign_id = client.create_campaign(campaign_params)
        console.print(f"  [green]Campaign created: {campaign_id}[/green]")

        # Step 2: Resolve interests
        console.print("  Resolving interest targeting IDs...")
        resolved_interests = _resolve_all_interests(client, campaign_config)

        # Step 3: Create ad sets
        ad_set_ids: dict[str, str] = {}  # name → id
        for ad_set in campaign_config.ad_sets:
            console.print(f"  Creating ad set: {ad_set.name}...")
            ad_set_params = _build_ad_set_params(
                ad_set, campaign_id, campaign_config, resolved_interests
            )
            ad_set_id = client.create_ad_set(ad_set_params)
            ad_set_ids[ad_set.name] = ad_set_id
            console.print(f"  [green]Ad set created: {ad_set_id}[/green]")

        # Step 4: Create creatives and ads
        ad_ids: list[str] = []
        for ad in campaign_config.ads:
            console.print(f"  Creating creative for ad: {ad.name}...")
            creative_params = _build_creative_params(ad, page_id)
            creative_id = client.create_ad_creative(creative_params)
            console.print(f"  [green]Creative created: {creative_id}[/green]")

            console.print(f"  Creating ad: {ad.name}...")
            ad_params = {
                "name": ad.name,
                "adset_id": ad_set_ids[ad.ad_set_name],
                "creative": {"creative_id": creative_id},
            }
            ad_id = client.create_ad(ad_params)
            ad_ids.append(ad_id)
            console.print(f"  [green]Ad created: {ad_id}[/green]")

        # Log success
        logger.log_execution(
            run_id,
            dry_run=False,
            campaign_id=campaign_id,
            ad_set_ids=list(ad_set_ids.values()),
            ad_ids=ad_ids,
        )

        # Print Ads Manager link
        account_id = client.ad_account_id.replace("act_", "")
        console.print(
            "\n[bold green]All entities created successfully (status=PAUSED).[/bold green]"
        )
        console.print(
            f"[bold]View in Ads Manager: "
            f"https://www.facebook.com/adsmanager/manage/campaigns"
            f"?act={account_id}&campaign_id={campaign_id}[/bold]"
        )

    except MetaAPIError as e:
        logger.log_execution(run_id, dry_run=False, error=str(e))
        raise


def run_execute(
        client: MetaClient,
        campaign_config: CampaignConfig,
        logger: RunLogger,
        run_id: str,
        dry_run: bool = True,
        page_id: str = "",
) -> None:
    """Run Phase 3: Create campaign entities via Meta API.

    Args:
        client: Initialized MetaClient instance.
        campaign_config: Validated campaign config from Phase 2.
        logger: RunLogger for persisting results.
        run_id: Current run ID.
        dry_run: If True (default), only print what would be created.
        page_id: Meta Page ID for creative creation.
    """
    console.print("[bold blue]Phase 3: Executing campaign creation...[/bold blue]")

    if dry_run:
        _execute_dry_run(campaign_config)
        logger.log_execution(run_id, dry_run=True)
        console.print(
            "\n[bold yellow]Dry run complete. Use --no-dry-run to create real campaigns.[/bold yellow]"
        )
    else:
        _execute_real(client, campaign_config, logger, run_id, page_id=page_id)

    console.print("[bold green]  Phase 3 complete.[/bold green]\n")
