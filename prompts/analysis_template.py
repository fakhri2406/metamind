"""Builds the dynamic user prompt from IngestedData and user inputs."""

from models.meta_data import IngestedData


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
    sections = []

    # Product info
    sections.append("## Product/Service Information")
    sections.append(f"- **Name:** {product_name}")
    sections.append(f"- **URL:** {product_url}")
    sections.append(f"- **Description:** {product_description}")
    sections.append(f"- **Target Customer:** {target_customer}")
    sections.append(f"- **Goal:** {goal}")
    sections.append(f"- **Daily Budget:** ${budget:.2f}")
    if aov:
        sections.append(f"- **Average Order Value:** ${aov:.2f}")
    if ads_per_ad_set is not None:
        sections.append(
            f"- **Ads Per Ad Set:** {ads_per_ad_set} (You MUST create exactly {ads_per_ad_set} ad(s) for each ad set.)")

    # Account info
    sections.append("\n## Account Information")
    sections.append(f"- **Account ID:** {data.account.account_id}")
    sections.append(f"- **Account Name:** {data.account.name}")
    sections.append(f"- **Currency:** {data.account.currency}")
    sections.append(f"- **Timezone:** {data.account.timezone}")
    if data.account.amount_spent is not None:
        sections.append(f"- **Total Amount Spent:** ${data.account.amount_spent:.2f}")

    # Date range
    sections.append(
        f"\n## Performance Data ({data.date_range_start} to {data.date_range_end})"
    )

    # Campaign performance
    if data.campaigns:
        sections.append("\n### Campaign Performance")
        for camp in data.campaigns:
            sections.append(f"\n**{camp.campaign_name}** (ID: {camp.campaign_id})")
            sections.append(f"  - Objective: {camp.objective}")
            sections.append(f"  - Spend: ${camp.spend:.2f}")
            sections.append(f"  - Impressions: {camp.impressions:,}")
            sections.append(f"  - Clicks: {camp.clicks:,}")
            sections.append(f"  - CTR: {camp.ctr:.2f}%")
            if camp.cpc is not None:
                sections.append(f"  - CPC: ${camp.cpc:.2f}")
            if camp.cpm is not None:
                sections.append(f"  - CPM: ${camp.cpm:.2f}")
            sections.append(f"  - Conversions: {camp.conversions}")
            if camp.conversion_value > 0:
                sections.append(f"  - Conversion Value: ${camp.conversion_value:.2f}")
            if camp.roas is not None:
                sections.append(f"  - ROAS: {camp.roas:.2f}x")
    else:
        sections.append("\n### Campaign Performance")
        sections.append(
            "No historical campaign data available. This is a new account or no campaigns have run in the last 60 days.")

    # Ad set performance
    if data.ad_sets:
        sections.append("\n### Ad Set Performance")
        for ad_set in data.ad_sets:
            sections.append(f"\n**{ad_set.ad_set_name}** (ID: {ad_set.ad_set_id})")
            sections.append(f"  - Campaign ID: {ad_set.campaign_id}")
            sections.append(f"  - Spend: ${ad_set.spend:.2f}")
            sections.append(f"  - Impressions: {ad_set.impressions:,}")
            sections.append(f"  - Clicks: {ad_set.clicks:,}")
            sections.append(f"  - CTR: {ad_set.ctr:.2f}%")
            sections.append(f"  - Conversions: {ad_set.conversions}")
            if ad_set.targeting_summary:
                sections.append(f"  - Targeting: {ad_set.targeting_summary}")

    # Custom audiences
    if data.custom_audiences:
        sections.append("\n### Available Custom Audiences")
        for aud in data.custom_audiences:
            line = f"- **{aud.name}** (type: {aud.subtype})"
            if aud.approximate_count:
                line += f" — ~{aud.approximate_count:,} people"
            sections.append(line)

    # Past AI runs
    if data.past_runs:
        sections.append("\n### Past AI Campaign Recommendations")
        for run in data.past_runs:
            sections.append(f"\n**{run.campaign_name}** (Run: {run.run_id})")
            sections.append(f"  - Date: {run.created_at}")
            sections.append(f"  - Objective: {run.objective}")
            sections.append(f"  - Budget: ${run.budget_daily_usd:.2f}/day")
            sections.append(f"  - Executed: {'Yes' if run.was_executed else 'No'}")
            if run.reasoning:
                sections.append(f"  - Reasoning: {run.reasoning[:200]}...")

    # Per-ad-set overrides
    if ad_set_overrides:
        sections.append("\n## Per-Ad-Set Configuration Overrides")
        sections.append(
            "The following overrides MUST take precedence over general campaign defaults. "
            "Apply these settings to the matching ad sets. "
            "Fields not listed should use campaign-level defaults."
        )
        for ad_set_name, overrides in ad_set_overrides.items():
            sections.append(f'\n### Ad Set: "{ad_set_name}"')
            for field, value in overrides.items():
                sections.append(f"- **{field}:** {value}")

    # Today's date for start_date validation
    from datetime import date

    sections.append(f"\n## Today's Date: {date.today().isoformat()}")
    sections.append(
        "Use this as the earliest possible start_date. Do not set start_date in the past."
    )

    return "\n".join(sections)
