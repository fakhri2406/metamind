"""Phase 2: Send ingested data to Claude for strategic analysis."""

import json
import os
import re

import anthropic
from rich.console import Console

import config
from exceptions import BudgetCapError, StrategyError
from models.campaign_config import CampaignConfig, ClaudeModel, DEFAULT_MODEL
from models.meta_data import IngestedData
from prompts.analysis_template import build_user_prompt
from storage.logger import RunLogger

console = Console()

_SYSTEM_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "prompts", "system_prompt.txt")

_CORRECTION_PROMPT = (
    "Your previous response was not valid JSON or did not match the required schema. "
    "Please respond with ONLY a raw JSON object matching the schema. "
    "No markdown, no code fences, no explanatory text. Just the JSON object. "
    "Error: {error}"
)


def _load_system_prompt() -> str:
    """Load the system prompt from file."""
    with open(_SYSTEM_PROMPT_PATH) as f:
        return f.read().strip()


def _strip_markdown_fences(text: str) -> str:
    """Remove markdown code fences if present."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def _try_parse(raw_text: str) -> CampaignConfig:
    """Attempt to parse Claude's response into a CampaignConfig.

    Args:
        raw_text: Raw text response from Claude.

    Returns:
        Validated CampaignConfig.

    Raises:
        StrategyError: If parsing or validation fails.
    """
    cleaned = _strip_markdown_fences(raw_text)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise StrategyError(f"Invalid JSON: {e}") from e

    try:
        return CampaignConfig.model_validate(data)
    except Exception as e:
        raise StrategyError(f"Validation failed: {e}") from e


def _enforce_budget_cap(campaign_config: CampaignConfig, budget_cap: float) -> None:
    """Enforce the budget cap.

    Checks both campaign-level budget and individual ad set budgets (for ABO).

    Args:
        campaign_config: The validated campaign config.
        budget_cap: Maximum allowed daily budget in USD.

    Raises:
        BudgetCapError: If any budget exceeds the cap.
    """
    cap = budget_cap

    if campaign_config.campaign.budget_daily_usd > cap:
        raise BudgetCapError(
            f"Campaign budget ${campaign_config.campaign.budget_daily_usd:.2f}/day "
            f"exceeds cap of ${cap:.2f}/day"
        )

    for ad_set in campaign_config.ad_sets:
        if ad_set.daily_budget_usd is not None and ad_set.daily_budget_usd > cap:
            raise BudgetCapError(
                f"Ad set '{ad_set.name}' budget ${ad_set.daily_budget_usd:.2f}/day "
                f"exceeds cap of ${cap:.2f}/day"
            )


def run_strategize(
        data: IngestedData,
        logger: RunLogger,
        run_id: str,
        product_name: str,
        product_url: str,
        product_description: str,
        target_customer: str,
        goal: str,
        budget: float,
        max_daily_budget_usd: float,
        aov: float | None = None,
        ads_per_ad_set: int | None = None,
        ad_set_overrides: dict[str, dict] | None = None,
        model: ClaudeModel = DEFAULT_MODEL,
) -> CampaignConfig:
    """Run Phase 2: Send data to Claude and get a validated campaign config.

    Args:
        data: Ingested data from Phase 1.
        logger: RunLogger for persisting results.
        run_id: Current run ID.
        product_name: Name of the product/service.
        product_url: URL for the product.
        product_description: Description of the product.
        target_customer: Target customer profile.
        goal: Campaign goal.
        budget: Daily budget in USD.
        max_daily_budget_usd: Budget cap for this account.
        aov: Average order value (optional).
        ads_per_ad_set: Number of ads to create per ad set (optional).
        ad_set_overrides: Per-ad-set configuration overrides (optional).
        model: Claude model to use for strategy generation.

    Returns:
        Validated CampaignConfig.

    Raises:
        StrategyError: If Claude fails to return valid JSON after retry.
        BudgetCapError: If budget exceeds the configured cap.
    """
    console.print(f"[bold blue]Phase 2: Generating strategy with Claude ({model.display_name})...[/bold blue]")

    system_prompt = _load_system_prompt()
    user_prompt = build_user_prompt(
        data=data,
        product_name=product_name,
        product_url=product_url,
        product_description=product_description,
        target_customer=target_customer,
        goal=goal,
        budget=budget,
        aov=aov,
        ads_per_ad_set=ads_per_ad_set,
        ad_set_overrides=ad_set_overrides,
    )

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    # First attempt
    console.print("  Calling Claude API...")
    response = client.messages.create(
        model=model.value,
        max_tokens=config.CLAUDE_MAX_TOKENS,
        temperature=config.CLAUDE_TEMPERATURE,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    raw_text = response.content[0].text

    # Log raw response immediately
    logger.log_strategy(run_id, raw_response=raw_text)

    # First parse attempt
    try:
        campaign_config = _try_parse(raw_text)
        console.print("  [green]Successfully parsed Claude's response.[/green]")
    except StrategyError as first_error:
        console.print(f"  [yellow]First parse failed: {first_error}[/yellow]")
        console.print("  [yellow]Retrying with correction prompt...[/yellow]")

        # Retry once with the conversation history + correction
        correction = _CORRECTION_PROMPT.format(error=str(first_error))
        retry_response = client.messages.create(
            model=model.value,
            max_tokens=config.CLAUDE_MAX_TOKENS,
            temperature=config.CLAUDE_TEMPERATURE,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt},
                {"role": "assistant", "content": raw_text},
                {"role": "user", "content": correction},
            ],
        )
        retry_text = retry_response.content[0].text

        # Log retry response
        logger.log_strategy(run_id, raw_response=retry_text)

        try:
            campaign_config = _try_parse(retry_text)
            console.print("  [green]Successfully parsed retry response.[/green]")
        except StrategyError as second_error:
            logger.log_strategy(
                run_id,
                raw_response=retry_text,
                error=str(second_error),
            )
            raise StrategyError(
                f"Claude failed to return valid JSON after retry. "
                f"First error: {first_error}. Second error: {second_error}"
            ) from second_error

    # Enforce budget cap (in code, not prompt)
    _enforce_budget_cap(campaign_config, max_daily_budget_usd)

    # Log successful strategy
    logger.log_strategy(
        run_id,
        raw_response=raw_text,
        config_json=campaign_config.model_dump_json(),
        campaign_name=campaign_config.campaign.name,
        objective=campaign_config.campaign.objective,
        budget_daily_usd=campaign_config.campaign.budget_daily_usd,
        reasoning=campaign_config.reasoning,
        model=model.value,
    )

    console.print("[bold green]  Phase 2 complete.[/bold green]\n")
    return campaign_config
