"""Typer CLI entry point for MetaMind."""

import json
import os
import subprocess
import tempfile
from typing import Optional

import typer
from cryptography.fernet import Fernet
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

import config
from exceptions import (
    BudgetCapError,
    CredentialDecryptionError,
    MetaAPIError,
    SetupError,
    StrategyError,
)
from models.campaign_config import CampaignConfig, ClaudeModel
from phases.execute import run_execute
from phases.ingest import run_ingest
from phases.strategize import run_strategize
from storage.accounts import (
    create_account,
    delete_account,
    get_account,
    list_accounts,
)
from storage.logger import RunLogger
from storage.migrations import run_migrations
from utils.meta_client import MetaClient

app = typer.Typer(
    name="MetaMind",
    help="AI-powered Meta Ads automation agent",
    rich_markup_mode="rich",
)
accounts_app = typer.Typer(help="Manage Meta Ad Accounts")
app.add_typer(accounts_app, name="accounts")
console = Console()

MODEL_SHORT_NAMES: dict[str, ClaudeModel] = {
    "opus": ClaudeModel.OPUS,
    "sonnet": ClaudeModel.SONNET,
    "haiku": ClaudeModel.HAIKU,
}


def _resolve_model(name: str) -> ClaudeModel:
    """Resolve a short model name to a ClaudeModel enum.

    Raises typer.Exit if the name is invalid.
    """
    model = MODEL_SHORT_NAMES.get(name.lower())
    if model is None:
        console.print(
            f"[bold red]Unknown model:[/bold red] '{name}'. "
            f"Valid options: {', '.join(MODEL_SHORT_NAMES.keys())}"
        )
        raise typer.Exit(code=1)
    return model


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


def _load_account(account_id: str):
    """Load and return an Account from the database.

    Raises typer.Exit on failure.
    """
    try:
        account = get_account(config.ENCRYPTION_KEY, account_id)
    except CredentialDecryptionError as e:
        console.print(f"[bold red]Decryption Error:[/bold red] {e}")
        raise typer.Exit(code=1)

    if not account:
        console.print(f"[bold red]Account not found:[/bold red] {account_id}")
        raise typer.Exit(code=1)

    if not account.is_active:
        console.print(f"[bold red]Account is deleted:[/bold red] {account_id}")
        raise typer.Exit(code=1)

    return account


def _build_client(account) -> MetaClient:
    """Construct a MetaClient from an Account object."""
    return MetaClient(
        access_token=account.access_token,
        app_id=account.app_id,
        app_secret=account.app_secret,
        ad_account_id=account.ad_account_id,
    )


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
    except Exception as e:
        console.print(f"[red]Error processing edited config: {e}[/red]")
        return None
    finally:
        os.unlink(tmp_path)


@app.command()
def generate_key() -> None:
    """Generate a new Fernet encryption key for METAMIND_ENCRYPTION_KEY."""
    existing = os.getenv("METAMIND_ENCRYPTION_KEY", "")
    if existing:
        console.print(
            "[yellow]Warning: METAMIND_ENCRYPTION_KEY is already set in your environment. "
            "Changing it will make existing encrypted accounts unreadable.[/yellow]\n"
        )

    key = Fernet.generate_key().decode()
    console.print(f"[bold green]Generated encryption key:[/bold green]\n\n  {key}\n")
    console.print("Add this to your [bold].env[/bold] file as:")
    console.print(f"  [cyan]METAMIND_ENCRYPTION_KEY={key}[/cyan]")


@accounts_app.command("list")
def accounts_list(
    show_secrets: bool = typer.Option(False, "--show-secrets", help="Show full credentials"),
) -> None:
    """List all active accounts."""
    run_migrations()

    try:
        config.check_setup()
    except SetupError as e:
        console.print(f"[bold red]Setup Error:[/bold red] {e}")
        raise typer.Exit(code=1)

    try:
        accts = list_accounts(config.ENCRYPTION_KEY)
    except CredentialDecryptionError as e:
        console.print(f"[bold red]Decryption Error:[/bold red] {e}")
        raise typer.Exit(code=1)

    if not accts:
        console.print("[yellow]No accounts found. Create one with: python main.py accounts create[/yellow]")
        return

    table = Table(title="Meta Ad Accounts")
    table.add_column("ID", style="dim", max_width=36)
    table.add_column("Name", style="white")
    table.add_column("Ad Account ID", style="cyan")
    table.add_column("Budget Cap", style="yellow")
    table.add_column("Active", style="green")
    if show_secrets:
        table.add_column("Access Token", style="red")
        table.add_column("App Secret", style="red")

    for acct in accts:
        row = [
            str(acct.id),
            acct.name,
            acct.ad_account_id,
            f"${acct.max_daily_budget_usd:.2f}",
            "Yes" if acct.is_active else "No",
        ]
        if show_secrets:
            row.append(acct.access_token)
            row.append(acct.app_secret)
        table.add_row(*row)

    console.print(table)


@accounts_app.command("create")
def accounts_create() -> None:
    """Create a new Meta Ad Account (interactive)."""
    run_migrations()

    try:
        config.check_setup()
    except SetupError as e:
        console.print(f"[bold red]Setup Error:[/bold red] {e}")
        raise typer.Exit(code=1)

    name = typer.prompt("Account name")
    access_token = typer.prompt("Meta Access Token", hide_input=True)
    ad_account_id = typer.prompt("Ad Account ID (act_XXXXXXXXX)")
    app_id = typer.prompt("App ID")
    app_secret = typer.prompt("App Secret", hide_input=True)
    page_id = typer.prompt("Page ID")
    max_budget = typer.prompt("Max Daily Budget (USD)", type=float)

    if not ad_account_id.startswith("act_"):
        console.print("[bold red]Ad Account ID must start with 'act_'[/bold red]")
        raise typer.Exit(code=1)

    if max_budget <= 0:
        console.print("[bold red]Budget must be positive[/bold red]")
        raise typer.Exit(code=1)

    account = create_account(
        encryption_key=config.ENCRYPTION_KEY,
        name=name,
        access_token=access_token,
        ad_account_id=ad_account_id,
        app_id=app_id,
        app_secret=app_secret,
        page_id=page_id,
        max_daily_budget_usd=max_budget,
    )

    console.print(f"\n[bold green]Account created:[/bold green] {account.name}")
    console.print(f"[dim]ID: {account.id}[/dim]")


@accounts_app.command("delete")
def accounts_delete(
    account_id: str = typer.Option(..., "--account-id", help="Account UUID to delete"),
) -> None:
    """Soft-delete an account."""
    run_migrations()

    try:
        config.check_setup()
    except SetupError as e:
        console.print(f"[bold red]Setup Error:[/bold red] {e}")
        raise typer.Exit(code=1)

    account = _load_account(account_id)
    confirm = typer.confirm(f"Delete account '{account.name}' ({account.ad_account_id})?")
    if not confirm:
        console.print("[yellow]Cancelled.[/yellow]")
        raise typer.Exit(code=0)

    delete_account(account_id)
    console.print(f"[green]Account '{account.name}' deleted (soft).[/green]")


@app.command()
def run(
        account_id: str = typer.Option(..., "--account-id", help="Account UUID to use"),
        product_name: str = typer.Option(..., "--product-name", help="Name of the product/service"),
        product_url: str = typer.Option(..., "--product-url", help="Product landing page URL"),
        product_description: str = typer.Option(..., "--product-description", help="Product description"),
        target_customer: str = typer.Option(..., "--target-customer", help="Target customer profile"),
        goal: str = typer.Option(..., "--goal", help="Campaign goal (e.g., 'maximize purchases')"),
        budget: float = typer.Option(..., "--budget", help="Daily budget in USD"),
        aov: Optional[float] = typer.Option(None, "--aov", help="Average order value in USD"),
        ads_per_ad_set: Optional[int] = typer.Option(None, "--ads-per-ad-set",
                                                     help="Number of ads to create per ad set", min=1),
        ad_set_overrides: Optional[str] = typer.Option(None, "--ad-set-overrides",
                                                       help="Path to JSON file with per-ad-set config overrides"),
        model: str = typer.Option("opus", "--model", help="Claude model: opus, sonnet, or haiku"),
        dry_run: bool = typer.Option(True, "--dry-run/--no-dry-run", help="Dry run (default: True)"),
) -> None:
    """Run the full pipeline: ingest → strategize → approve → execute."""
    run_migrations()

    try:
        config.check_setup()
    except SetupError as e:
        console.print(f"[bold red]Setup Error:[/bold red] {e}")
        raise typer.Exit(code=1)

    claude_model = _resolve_model(model)
    account = _load_account(account_id)

    overrides_dict = None
    if ad_set_overrides:
        overrides_dict = _load_ad_set_overrides(ad_set_overrides)

    logger = RunLogger()
    run_id = logger.create_run(account_id=str(account.id))
    console.print(f"[dim]Run ID: {run_id}[/dim]")
    console.print(f"[dim]Account: {account.name} ({account.ad_account_id})[/dim]\n")

    try:
        # Phase 1: Ingest
        client = _build_client(account)
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
            max_daily_budget_usd=account.max_daily_budget_usd,
            aov=aov,
            ads_per_ad_set=ads_per_ad_set,
            ad_set_overrides=overrides_dict,
            model=claude_model,
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
        run_execute(
            client, campaign_config, logger, run_id,
            dry_run=dry_run, page_id=account.page_id,
        )

    except CredentialDecryptionError as e:
        console.print(f"[bold red]Decryption Error:[/bold red] {e}")
        raise typer.Exit(code=1)
    except (StrategyError, BudgetCapError, MetaAPIError) as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


def _format_history_row(r) -> list[str]:
    """Format a RunLog into a list of column values for the history table."""
    date_str = r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "-"
    budget_str = f"${r.budget_daily_usd:.2f}" if r.budget_daily_usd else "-"

    if r.approved:
        approved_str = "Yes"
    elif r.approved is False:
        approved_str = "No"
    else:
        approved_str = "-"

    if r.created_campaign_id:
        executed_str = "Yes"
    elif r.dry_run:
        executed_str = "Dry"
    else:
        executed_str = "-"

    return [
        str(r.run_id),
        date_str,
        r.campaign_name or "-",
        r.objective or "-",
        budget_str,
        approved_str,
        executed_str,
    ]


@app.command()
def history(
    account_id: Optional[str] = typer.Option(None, "--account-id", help="Filter by account UUID"),
) -> None:
    """View past run history."""
    run_migrations()

    logger = RunLogger()
    runs = logger.get_all_runs(account_id=account_id)

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
        table.add_row(*_format_history_row(r))

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
        account_id: str = typer.Option(..., "--account-id", help="Account UUID to use"),
        run_id: str = typer.Option(..., "--run-id", help="Run ID of a past campaign to optimize"),
        budget: Optional[float] = typer.Option(None, "--budget", help="New daily budget (optional)"),
        ads_per_ad_set: Optional[int] = typer.Option(None, "--ads-per-ad-set",
                                                     help="Number of ads to create per ad set", min=1),
        ad_set_overrides: Optional[str] = typer.Option(None, "--ad-set-overrides",
                                                       help="Path to JSON file with per-ad-set config overrides"),
        model: str = typer.Option("opus", "--model", help="Claude model: opus, sonnet, or haiku"),
        dry_run: bool = typer.Option(True, "--dry-run/--no-dry-run", help="Dry run (default: True)"),
) -> None:
    """Re-optimize an existing campaign from a past run.

    Re-ingests current data, passes past config + reasoning as additional context to Claude.
    """
    run_migrations()

    try:
        config.check_setup()
    except SetupError as e:
        console.print(f"[bold red]Setup Error:[/bold red] {e}")
        raise typer.Exit(code=1)

    claude_model = _resolve_model(model)
    account = _load_account(account_id)

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

    new_run_id = logger.create_run(account_id=str(account.id))
    console.print(f"[dim]Optimization Run ID: {new_run_id}[/dim]")
    console.print(f"[dim]Account: {account.name} ({account.ad_account_id})[/dim]")
    console.print(f"[dim]Based on past run: {run_id}[/dim]\n")

    try:
        client = _build_client(account)
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
            max_daily_budget_usd=account.max_daily_budget_usd,
            ads_per_ad_set=ads_per_ad_set,
            ad_set_overrides=overrides_dict,
            model=claude_model,
        )

        if config.REQUIRE_HUMAN_APPROVAL:
            approved = _human_approval_gate(campaign_config, logger, new_run_id)
            if not approved:
                console.print("[yellow]Optimization rejected. Exiting.[/yellow]")
                raise typer.Exit(code=0)
        else:
            logger.log_approval(new_run_id, approved=True)

        run_execute(
            client, campaign_config, logger, new_run_id,
            dry_run=dry_run, page_id=account.page_id,
        )

    except CredentialDecryptionError as e:
        console.print(f"[bold red]Decryption Error:[/bold red] {e}")
        raise typer.Exit(code=1)
    except (StrategyError, BudgetCapError, MetaAPIError) as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
