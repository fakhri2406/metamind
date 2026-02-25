"""Reusable CampaignConfig display component."""

from __future__ import annotations

import streamlit as st

from models.campaign_config import CampaignConfig


def render_config_summary(config: CampaignConfig) -> None:
    """Render campaign summary cards with expandable ad sets and ads."""
    campaign = config.campaign

    # Campaign overview card
    st.markdown('<div class="mm-section-header">Campaign Summary</div>', unsafe_allow_html=True)
    st.markdown(
        f"""<div class="mm-card">
        <div class="mm-stat"><span class="mm-stat-label">Name:</span> <span class="mm-stat-value">{campaign.name}</span></div>
        <div class="mm-stat"><span class="mm-stat-label">Objective:</span> <span class="mm-stat-value">{campaign.objective.value}</span></div>
        <div class="mm-stat"><span class="mm-stat-label">Daily Budget:</span> <span class="mm-stat-value">${campaign.budget_daily_usd:.2f}</span></div>
        <div class="mm-stat"><span class="mm-stat-label">Budget Type:</span> <span class="mm-stat-value">{campaign.budget_type.value}</span></div>
        <div class="mm-stat"><span class="mm-stat-label">Start Date:</span> <span class="mm-stat-value">{campaign.start_date}</span></div>
        <div class="mm-stat"><span class="mm-stat-label">End Date:</span> <span class="mm-stat-value">{campaign.end_date or "Open-ended"}</span></div>
        </div>""",
        unsafe_allow_html=True,
    )

    # Group ads by ad_set_name
    ads_by_set: dict[str, list] = {}
    for ad in config.ads:
        ads_by_set.setdefault(ad.ad_set_name, []).append(ad)

    # Ad sets with nested ads
    st.markdown('<div class="mm-section-header">Ad Sets & Ads</div>', unsafe_allow_html=True)
    for ad_set in config.ad_sets:
        with st.expander(f"Ad Set: {ad_set.name}", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Targeting:** {ad_set.targeting_type.value}")
                st.markdown(f"**Ages:** {ad_set.age_min}–{ad_set.age_max}")
                genders = ", ".join(g.value for g in ad_set.genders)
                st.markdown(f"**Genders:** {genders}")
                if ad_set.interests:
                    st.markdown(f"**Interests:** {', '.join(ad_set.interests)}")
            with col2:
                st.markdown(f"**Placements:** {ad_set.placements.value}")
                st.markdown(f"**Bid Strategy:** {ad_set.bid_strategy.value}")
                if ad_set.bid_amount_usd is not None:
                    st.markdown(f"**Bid Amount:** ${ad_set.bid_amount_usd:.2f}")
                if ad_set.daily_budget_usd is not None:
                    st.markdown(f"**Daily Budget:** ${ad_set.daily_budget_usd:.2f}")
                if ad_set.lookalike_source:
                    st.markdown(f"**Lookalike Source:** {ad_set.lookalike_source}")

            # Nested ads
            ads = ads_by_set.get(ad_set.name, [])
            for ad in ads:
                st.markdown('<div class="mm-nested-card">', unsafe_allow_html=True)
                st.markdown(f"**Ad: {ad.name}**")
                st.markdown(f"Format: `{ad.format.value}` | CTA: `{ad.cta.value}`")
                st.markdown(f"**Headline:** {ad.headline}")
                st.markdown(f"**Primary Text:** {ad.primary_text}")
                if ad.description:
                    st.markdown(f"**Description:** {ad.description}")
                st.markdown(f"**URL:** {ad.destination_url}")
                if ad.creative_notes:
                    st.caption(f"Creative notes: {ad.creative_notes}")
                st.markdown("</div>", unsafe_allow_html=True)
