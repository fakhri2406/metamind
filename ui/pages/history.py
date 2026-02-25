"""Page 3: Run History — table of past runs with expandable details."""

from __future__ import annotations

import json

import streamlit as st

from models.campaign_config import CampaignConfig
from storage.logger import RunLogger
from ui.components.account_selector import render_account_selector
from ui.components.config_viewer import render_config_summary
from ui.state import init_state

init_state()

st.markdown('<div class="mm-page-title">Run History</div>', unsafe_allow_html=True)

# Account selector
account = render_account_selector()
if account is None:
    st.stop()

# Toggle to show all accounts
show_all = st.toggle("Show all accounts", value=False)

# Fetch runs and extract to plain dicts to avoid SQLAlchemy detached object issues
logger = RunLogger()
filter_account_id = None if show_all else account.id
raw_runs = logger.get_all_runs(account_id=filter_account_id)

runs: list[dict] = []
for r in raw_runs:
    runs.append({
        "run_id": r.run_id,
        "created_at": str(r.created_at) if r.created_at else "",
        "campaign_name": r.campaign_name or "—",
        "objective": r.objective or "—",
        "budget_daily_usd": r.budget_daily_usd,
        "approved": r.approved,
        "dry_run": r.dry_run,
        "reasoning": r.reasoning or "",
        "campaign_config_json": r.campaign_config_json or "",
        "strategy_error": r.strategy_error or "",
        "created_campaign_id": r.created_campaign_id or "",
        "created_ad_set_ids": r.created_ad_set_ids or "",
        "created_ad_ids": r.created_ad_ids or "",
        "execution_error": r.execution_error or "",
    })

if not runs:
    st.info("No runs found. Create a campaign to see history here.")
    st.stop()

# Summary table
table_data = []
for r in runs:
    status = "—"
    if r["approved"] is True:
        status = "Approved"
    elif r["approved"] is False:
        status = "Rejected"
    elif r["strategy_error"]:
        status = "Error"

    table_data.append({
        "Run ID": r["run_id"][:8],
        "Date": r["created_at"][:19] if r["created_at"] else "",
        "Campaign": r["campaign_name"],
        "Objective": r["objective"],
        "Budget": f"${r['budget_daily_usd']:.2f}" if r["budget_daily_usd"] else "—",
        "Status": status,
    })

st.dataframe(table_data, use_container_width=True, hide_index=True)

# Run selector for details
run_labels = [
    f"{r['run_id'][:8]} — {r['campaign_name']} ({r['created_at'][:10]})"
    for r in runs
]
selected_idx = st.selectbox(
    "Select a run to inspect",
    range(len(runs)),
    format_func=lambda i: run_labels[i],
)

if selected_idx is not None:
    run = runs[selected_idx]

    # Campaign config
    if run["campaign_config_json"]:
        with st.expander("Campaign Config", expanded=False):
            try:
                parsed = json.loads(run["campaign_config_json"])
                config_obj = CampaignConfig.model_validate(parsed)
                render_config_summary(config_obj)
            except Exception:
                st.json(json.loads(run["campaign_config_json"]))

    # Reasoning
    if run["reasoning"]:
        with st.expander("Claude's Reasoning", expanded=False):
            st.markdown(
                f'<div class="mm-card-mono">{run["reasoning"]}</div>',
                unsafe_allow_html=True,
            )

    # Execution log
    with st.expander("Execution Log", expanded=False):
        if run["created_campaign_id"]:
            st.markdown(f"**Campaign ID:** `{run['created_campaign_id']}`")
        if run["created_ad_set_ids"]:
            try:
                ids = json.loads(run["created_ad_set_ids"])
                st.markdown(f"**Ad Set IDs:** {', '.join(f'`{i}`' for i in ids)}")
            except (json.JSONDecodeError, TypeError):
                st.markdown(f"**Ad Set IDs:** `{run['created_ad_set_ids']}`")
        if run["created_ad_ids"]:
            try:
                ids = json.loads(run["created_ad_ids"])
                st.markdown(f"**Ad IDs:** {', '.join(f'`{i}`' for i in ids)}")
            except (json.JSONDecodeError, TypeError):
                st.markdown(f"**Ad IDs:** `{run['created_ad_ids']}`")
        if run["execution_error"]:
            st.error(f"Error: {run['execution_error']}")
        if run["strategy_error"]:
            st.error(f"Strategy Error: {run['strategy_error']}")
        if not any([
            run["created_campaign_id"],
            run["created_ad_set_ids"],
            run["created_ad_ids"],
            run["execution_error"],
            run["strategy_error"],
        ]):
            st.caption("No execution data recorded.")

    # Optimize button
    if run["campaign_config_json"]:
        if st.button("Optimize This Run", key=f"opt_{run['run_id']}"):
            st.session_state["mm_optimize_run_id"] = run["run_id"]
            st.switch_page("pages/optimize.py")
