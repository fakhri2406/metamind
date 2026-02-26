"""Builds the dynamic user prompt from IngestedData and user inputs."""

from models.meta_data import IngestedData


def _build_product_section(
        product_name: str,
        product_url: str,
        product_description: str,
        target_customer: str,
        goal: str,
        budget: float,
        aov: float | None,
        ads_per_ad_set: int | None,
) -> list[str]:
    """Build the product/service information section."""
    lines = [
        "## Product/Service Information",
        f"- **Name:** {product_name}",
        f"- **URL:** {product_url}",
        f"- **Description:** {product_description}",
        f"- **Target Customer:** {target_customer}",
        f"- **Goal:** {goal}",
        f"- **Daily Budget:** ${budget:.2f}",
    ]
    if aov:
        lines.append(f"- **Average Order Value:** ${aov:.2f}")
    if ads_per_ad_set is not None:
        lines.append(
            f"- **Ads Per Ad Set:** {ads_per_ad_set} (You MUST create exactly {ads_per_ad_set} ad(s) for each ad set.)")
    return lines


def _build_account_section(data: IngestedData) -> list[str]:
    """Build the account information section."""
    lines = [
        "\n## Account Information",
        f"- **Account ID:** {data.account.account_id}",
        f"- **Account Name:** {data.account.name}",
        f"- **Currency:** {data.account.currency}",
        f"- **Timezone:** {data.account.timezone}",
    ]
    if data.account.amount_spent is not None:
        lines.append(f"- **Total Amount Spent:** ${data.account.amount_spent:.2f}")
    return lines


def _build_campaign_performance(data: IngestedData) -> list[str]:
    """Build the campaign performance section."""
    if not data.campaigns:
        return [
            "\n### Campaign Performance",
            "No historical campaign data available. This is a new account or no campaigns have run in the last 60 days.",
        ]

    lines = ["\n### Campaign Performance"]
    for camp in data.campaigns:
        lines.append(f"\n**{camp.campaign_name}** (ID: {camp.campaign_id})")
        lines.append(f"  - Objective: {camp.objective}")
        lines.append(f"  - Spend: ${camp.spend:.2f}")
        lines.append(f"  - Impressions: {camp.impressions:,}")
        lines.append(f"  - Clicks: {camp.clicks:,}")
        lines.append(f"  - CTR: {camp.ctr:.2f}%")
        if camp.cpc is not None:
            lines.append(f"  - CPC: ${camp.cpc:.2f}")
        if camp.cpm is not None:
            lines.append(f"  - CPM: ${camp.cpm:.2f}")
        lines.append(f"  - Conversions: {camp.conversions}")
        if camp.conversion_value > 0:
            lines.append(f"  - Conversion Value: ${camp.conversion_value:.2f}")
        if camp.roas is not None:
            lines.append(f"  - ROAS: {camp.roas:.2f}x")
    return lines


def _build_ad_set_performance(data: IngestedData) -> list[str]:
    """Build the ad set performance section."""
    if not data.ad_sets:
        return []

    lines = ["\n### Ad Set Performance"]
    for ad_set in data.ad_sets:
        lines.append(f"\n**{ad_set.ad_set_name}** (ID: {ad_set.ad_set_id})")
        lines.append(f"  - Campaign ID: {ad_set.campaign_id}")
        lines.append(f"  - Spend: ${ad_set.spend:.2f}")
        lines.append(f"  - Impressions: {ad_set.impressions:,}")
        lines.append(f"  - Clicks: {ad_set.clicks:,}")
        lines.append(f"  - CTR: {ad_set.ctr:.2f}%")
        lines.append(f"  - Conversions: {ad_set.conversions}")
        if ad_set.targeting_summary:
            lines.append(f"  - Targeting: {ad_set.targeting_summary}")
    return lines


def _build_audiences_section(data: IngestedData) -> list[str]:
    """Build the custom audiences section."""
    if not data.custom_audiences:
        return []

    lines = ["\n### Available Custom Audiences"]
    for aud in data.custom_audiences:
        line = f"- **{aud.name}** (type: {aud.subtype})"
        if aud.approximate_count:
            line += f" — ~{aud.approximate_count:,} people"
        lines.append(line)
    return lines


def _build_past_runs_section(data: IngestedData) -> list[str]:
    """Build the past AI runs section."""
    if not data.past_runs:
        return []

    lines = ["\n### Past AI Campaign Recommendations"]
    for run in data.past_runs:
        lines.append(f"\n**{run.campaign_name}** (Run: {run.run_id})")
        lines.append(f"  - Date: {run.created_at}")
        lines.append(f"  - Objective: {run.objective}")
        lines.append(f"  - Budget: ${run.budget_daily_usd:.2f}/day")
        lines.append(f"  - Executed: {'Yes' if run.was_executed else 'No'}")
        if run.reasoning:
            lines.append(f"  - Reasoning: {run.reasoning[:200]}...")
    return lines


def _build_overrides_section(ad_set_overrides: dict[str, dict] | None) -> list[str]:
    """Build the per-ad-set overrides section."""
    if not ad_set_overrides:
        return []

    lines = [
        "\n## Per-Ad-Set Configuration Overrides",
        "The following overrides MUST take precedence over general campaign defaults. "
        "Apply these settings to the matching ad sets. "
        "Fields not listed should use campaign-level defaults.",
    ]
    for ad_set_name, overrides in ad_set_overrides.items():
        lines.append(f'\n### Ad Set: "{ad_set_name}"')
        for field, value in overrides.items():
            lines.append(f"- **{field}:** {value}")
    return lines


def build_user_prompt(
        data: IngestedData,
        product_name: str,
        product_url: str,
        product_description: str,
        target_customer: str,
        goal: str,
        budget: float,
        aov: float | None = None,
        ads_per_ad_set: int | None = None,
        ad_set_overrides: dict[str, dict] | None = None,
) -> str:
    """Build the user prompt for Claude from ingested data and user inputs.

    Args:
        data: Ingested data from Meta API.
        product_name: Name of the product/service.
        product_url: URL for the product/service.
        product_description: Description of the product/service.
        target_customer: Description of the target customer.
        goal: Business goal for the campaign.
        budget: Daily budget in USD.
        aov: Average order value in USD (optional).
        ads_per_ad_set: Number of ads to create per ad set (optional).
        ad_set_overrides: Per-ad-set configuration overrides (optional).

    Returns:
        Formatted user prompt string.
    """
    sections: list[str] = []

    sections.extend(_build_product_section(
        product_name, product_url, product_description,
        target_customer, goal, budget, aov, ads_per_ad_set,
    ))
    sections.extend(_build_account_section(data))

    # Date range
    sections.append(
        f"\n## Performance Data ({data.date_range_start} to {data.date_range_end})"
    )

    sections.extend(_build_campaign_performance(data))
    sections.extend(_build_ad_set_performance(data))
    sections.extend(_build_audiences_section(data))
    sections.extend(_build_past_runs_section(data))
    sections.extend(_build_overrides_section(ad_set_overrides))

    # Today's date for start_date validation
    from datetime import date

    sections.append(f"\n## Today's Date: {date.today().isoformat()}")
    sections.append(
        "Use this as the earliest possible start_date. Do not set start_date in the past."
    )

    return "\n".join(sections)
