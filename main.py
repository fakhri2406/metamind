"""Typer CLI entry point for MetaMind."""

import json
import os
import subprocess
import tempfile
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

import config
from exceptions import BudgetCapError, MetaAPIError, SetupError, StrategyError
from models.campaign_config import CampaignConfig
from phases.execute import run_execute
from phases.ingest import run_ingest
from phases.strategize import run_strategize
from storage.logger import RunLogger
from utils.meta_client import MetaClient

app = typer.Typer(
    name="MetaMind",
    help="AI-powered Meta Ads automation agent",
    rich_markup_mode="rich",
)
console = Console()


def _load_ad_set_overrides(path: str) -> dict[str, dict]:
    """Load and validate a per-ad-set overrides JSON file.

    Args:
        path: Path to the JSON file.

    Returns:
        Dict mapping ad set names to override dicts.

    Raises:
        typer.BadParameter: If the file structure is invalid.
    """
    try:
        with open(path) as f:
            data = json.load(f)
    except FileNotFoundError:
        raise typer.BadParameter(f"Overrides file not found: {path}")
    except json.JSONDecodeError as e:
        raise typer.BadParameter(f"Overrides file is not valid JSON: {e}")

    if not isinstance(data, dict):
        raise typer.BadParameter("Ad set overrides must be a JSON object (dict)")
    for key, value in data.items():
        if not isinstance(value, dict):
            raise typer.BadParameter(
                f"Ad set override for '{key}' must be an object, got: {type(value).__name__}"
            )
    return data


def _human_approval_gate(campaign_config: CampaignConfig, logger: RunLogger, run_id: str) -> bool:
    """Present the strategy to the user and get approval.

    Returns True if approved, False if rejected.
    """
    # Print strategy summary
    console.print(Panel.fit(
        f"[bold]{campaign_config.campaign.name}[/bold]\n"
        f"Objective: {campaign_config.campaign.objective.value}\n"
        f"Budget: ${campaign_config.campaign.budget_daily_usd:.2f}/day "
        f"({campaign_config.campaign.budget_type.value})\n"
        f"Start: {campaign_config.campaign.start_date}\n"
        f"End: {campaign_config.campaign.end_date or 'No end date'}\n"
        f"Ad Sets: {len(campaign_config.ad_sets)}\n"
        f"Ads: {len(campaign_config.ads)}",
        title="Campaign Strategy",
        border_style="blue",
    ))

    # Print reasoning
    console.print(Panel.fit(
        campaign_config.reasoning,
        title="Claude's Reasoning",
        border_style="green",
    ))

    # Print optimization notes
    if campaign_config.optimization_notes:
        console.print(Panel.fit(
            campaign_config.optimization_notes,
            title="Optimization Notes",
            border_style="yellow",
        ))

    # Approval prompt
    while True:
        choice = typer.prompt(
            "\nApprove this strategy? [y]es / [N]o / [e]dit",
            default="N",
        ).strip().lower()

        if choice in ("y", "yes"):
            logger.log_approval(run_id, approved=True)
            return True
        elif choice in ("n", "no"):
            logger.log_approval(run_id, approved=False)
            return False
        elif choice in ("e", "edit"):
            edited_config = _edit_config(campaign_config)
            if edited_config is not None:
                # Re-display and re-prompt with edited config
                campaign_config.__dict__.update(edited_config.__dict__)
                console.print("[green]Config updated. Showing revised strategy...[/green]\n")
                return _human_approval_gate(campaign_config, logger, run_id)
            else:
                console.print("[red]Edit failed or was cancelled. Returning to approval prompt.[/red]")
        else:
            console.print("[red]Invalid choice. Enter y, N, or e.[/red]")


def _edit_config(campaign_config: CampaignConfig) -> Optional[CampaignConfig]:
    """Open the config JSON in $EDITOR and re-validate on save."""
    editor = os.environ.get("EDITOR", "vim")
    config_json = campaign_config.model_dump_json(indent=2)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, prefix="meta-ads-config-"
    ) as f:
        f.write(config_json)
        tmp_path = f.name

    try:
        subprocess.run([editor, tmp_path], check=True)
        with open(tmp_path) as f:
            edited_json = f.read()
        edited_data = json.loads(edited_json)
        return CampaignConfig.model_validate(edited_data)
    except (subprocess.CalledProcessError, json.JSONDecodeError, Exception) as e:
        console.print(f"[red]Error processing edited config: {e}[/red]")
        return None
    finally:
        os.unlink(tmp_path)


@app.command()
def run(
    product_name: str = typer.Option(..., "--product-name", help="Name of the product/service"),
    product_url: str = typer.Option(..., "--product-url", help="Product landing page URL"),
    product_description: str = typer.Option(..., "--product-description", help="Product description"),
    target_customer: str = typer.Option(..., "--target-customer", help="Target customer profile"),
    goal: str = typer.Option(..., "--goal", help="Campaign goal (e.g., 'maximize purchases')"),
    budget: float = typer.Option(..., "--budget", help="Daily budget in USD"),
    aov: Optional[float] = typer.Option(None, "--aov", help="Average order value in USD"),
    ads_per_ad_set: Optional[int] = typer.Option(None, "--ads-per-ad-set", help="Number of ads to create per ad set", min=1),
    ad_set_overrides: Optional[str] = typer.Option(None, "--ad-set-overrides", help="Path to JSON file with per-ad-set config overrides"),
    dry_run: bool = typer.Option(True, "--dry-run/--no-dry-run", help="Dry run (default: True)"),
) -> None:
    """Run the full pipeline: ingest → strategize → approve → execute."""
    try:
        config.check_setup()
    except SetupError as e:
        console.print(f"[bold red]Setup Error:[/bold red] {e}")
        raise typer.Exit(code=1)

    overrides_dict = None
    if ad_set_overrides:
        overrides_dict = _load_ad_set_overrides(ad_set_overrides)

    logger = RunLogger()
    run_id = logger.create_run()
    console.print(f"[dim]Run ID: {run_id}[/dim]\n")

    try:
        # Phase 1: Ingest
        client = MetaClient()
        data = run_ingest(client, logger, run_id)

        # Phase 2: Strategize
        campaign_config = run_strategize(
            data=data,
            logger=logger,
            run_id=run_id,
            product_name=product_name,
            product_url=product_url,
            product_description=product_description,
            target_customer=target_customer,
            goal=goal,
            budget=budget,
            aov=aov,
            ads_per_ad_set=ads_per_ad_set,
            ad_set_overrides=overrides_dict,
        )

        # Human approval gate
        if config.REQUIRE_HUMAN_APPROVAL:
            approved = _human_approval_gate(campaign_config, logger, run_id)
            if not approved:
                console.print("[yellow]Strategy rejected. Exiting.[/yellow]")
                raise typer.Exit(code=0)
        else:
            logger.log_approval(run_id, approved=True)

        # Phase 3: Execute
        run_execute(client, campaign_config, logger, run_id, dry_run=dry_run)

    except (StrategyError, BudgetCapError, MetaAPIError) as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command()
def history() -> None:
    """View past run history."""
    logger = RunLogger()
    runs = logger.get_all_runs()

    if not runs:
        console.print("[yellow]No runs found.[/yellow]")
        return

    table = Table(title="Run History")
    table.add_column("Run ID", style="dim", max_width=36)
    table.add_column("Date", style="cyan")
    table.add_column("Campaign", style="white")
    table.add_column("Objective", style="green")
    table.add_column("Budget", style="yellow")
    table.add_column("Approved", style="blue")
    table.add_column("Executed", style="red")

    for r in runs:
        table.add_row(
            r.run_id,
            r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "-",
            r.campaign_name or "-",
            r.objective or "-",
            f"${r.budget_daily_usd:.2f}" if r.budget_daily_usd else "-",
            "Yes" if r.approved else ("No" if r.approved is False else "-"),
            "Yes" if r.created_campaign_id else ("Dry" if r.dry_run else "-"),
        )

    console.print(table)


@app.command()
def validate_config(
    path: str = typer.Argument(..., help="Path to a campaign config JSON file"),
) -> None:
    """Validate a campaign config JSON file against the schema."""
    try:
        with open(path) as f:
            data = json.load(f)
        campaign_config = CampaignConfig.model_validate(data)
        console.print(f"[bold green]Valid![/bold green] Campaign: {campaign_config.campaign.name}")
        console.print(f"  Objective: {campaign_config.campaign.objective.value}")
        console.print(f"  Budget: ${campaign_config.campaign.budget_daily_usd:.2f}/day")
        console.print(f"  Ad Sets: {len(campaign_config.ad_sets)}")
        console.print(f"  Ads: {len(campaign_config.ads)}")
    except FileNotFoundError:
        console.print(f"[bold red]File not found:[/bold red] {path}")
        raise typer.Exit(code=1)
    except json.JSONDecodeError as e:
        console.print(f"[bold red]Invalid JSON:[/bold red] {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Validation failed:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command()
def optimize(
    run_id: str = typer.Option(..., "--run-id", help="Run ID of a past campaign to optimize"),
    budget: Optional[float] = typer.Option(None, "--budget", help="New daily budget (optional)"),
    ads_per_ad_set: Optional[int] = typer.Option(None, "--ads-per-ad-set", help="Number of ads to create per ad set", min=1),
    ad_set_overrides: Optional[str] = typer.Option(None, "--ad-set-overrides", help="Path to JSON file with per-ad-set config overrides"),
    dry_run: bool = typer.Option(True, "--dry-run/--no-dry-run", help="Dry run (default: True)"),
) -> None:
    """Re-optimize an existing campaign from a past run.

    Re-ingests current data, passes past config + reasoning as additional context to Claude.
    """
    try:
        config.check_setup()
    except SetupError as e:
        console.print(f"[bold red]Setup Error:[/bold red] {e}")
        raise typer.Exit(code=1)

    overrides_dict = None
    if ad_set_overrides:
        overrides_dict = _load_ad_set_overrides(ad_set_overrides)

    logger = RunLogger()
    past_run = logger.get_run(run_id)

    if not past_run:
        console.print(f"[bold red]Run not found:[/bold red] {run_id}")
        raise typer.Exit(code=1)

    if not past_run.campaign_config_json:
        console.print(f"[bold red]No campaign config found for run:[/bold red] {run_id}")
        raise typer.Exit(code=1)

    # Parse past config to extract product info
    past_config = CampaignConfig.model_validate_json(past_run.campaign_config_json)

    new_run_id = logger.create_run()
    console.print(f"[dim]Optimization Run ID: {new_run_id}[/dim]")
    console.print(f"[dim]Based on past run: {run_id}[/dim]\n")

    try:
        client = MetaClient()
        data = run_ingest(client, logger, new_run_id)

        # Use budget from past run or override
        effective_budget = budget if budget is not None else past_config.campaign.budget_daily_usd

        # Append past context to the goal
        past_context = (
            f"This is an optimization of a previous campaign: '{past_config.campaign.name}'. "
            f"Previous reasoning: {past_config.reasoning}. "
            f"Previous optimization notes: {past_config.optimization_notes}. "
            f"Please improve upon the previous strategy based on current performance data."
        )

        campaign_config = run_strategize(
            data=data,
            logger=logger,
            run_id=new_run_id,
            product_name=past_config.campaign.name,
            product_url=past_config.ads[0].destination_url if past_config.ads else "",
            product_description=past_context,
            target_customer="See past campaign data for targeting insights",
            goal=f"Optimize and improve upon previous campaign. {past_config.optimization_notes}",
            budget=effective_budget,
            ads_per_ad_set=ads_per_ad_set,
            ad_set_overrides=overrides_dict,
        )

        if config.REQUIRE_HUMAN_APPROVAL:
            approved = _human_approval_gate(campaign_config, logger, new_run_id)
            if not approved:
                console.print("[yellow]Optimization rejected. Exiting.[/yellow]")
                raise typer.Exit(code=0)
        else:
            logger.log_approval(new_run_id, approved=True)

        run_execute(client, campaign_config, logger, new_run_id, dry_run=dry_run)

    except (StrategyError, BudgetCapError, MetaAPIError) as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
