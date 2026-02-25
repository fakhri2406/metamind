"""Page 4: Optimize — re-optimize an existing campaign from a past run."""

from __future__ import annotations

import json

import streamlit as st

from exceptions import BudgetCapError, CredentialDecryptionError, MetaAPIError, SetupError, StrategyError
from models.campaign_config import CampaignConfig, ClaudeModel
from phases.ingest import run_ingest
from phases.strategize import run_strategize
from storage.logger import RunLogger
from ui.components.account_selector import render_account_selector
from ui.state import init_state, reset_pipeline, set_config, set_error
from utils.meta_client import MetaClient

init_state()

st.markdown('<div class="mm-page-title">Optimize Existing Campaign</div>', unsafe_allow_html=True)

# Setup check
if not st.session_state["mm_setup_ok"]:
    msg = st.session_state.get("mm_setup_error") or "Environment not configured."
    st.error(f"Setup Error: {msg}")
    st.stop()

# Account selector
account = render_account_selector()
if account is None:
    st.stop()

# Fetch past runs
logger = RunLogger()
raw_runs = logger.get_all_runs(account_id=account.id)

# Filter to runs that have a campaign config
runs: list[dict] = []
for r in raw_runs:
    if r.campaign_config_json:
        runs.append({
            "run_id": r.run_id,
            "created_at": str(r.created_at) if r.created_at else "",
            "campaign_name": r.campaign_name or "Unnamed",
            "objective": r.objective or "—",
            "budget_daily_usd": r.budget_daily_usd,
            "reasoning": r.reasoning or "",
            "campaign_config_json": r.campaign_config_json,
        })

if not runs:
    st.info("No past runs with campaign configs found. Run a campaign first.")
    st.stop()

# Run selector
run_labels = [
    f"{r['campaign_name']} — {r['created_at'][:10]} ({r['run_id'][:8]})"
    for r in runs
]

# Pre-select if coming from history page
pre_selected = 0
optimize_run_id = st.session_state.get("mm_optimize_run_id")
if optimize_run_id:
    for i, r in enumerate(runs):
        if r["run_id"] == optimize_run_id:
            pre_selected = i
            break

selected_idx = st.selectbox(
    "Select a past run to optimize",
    range(len(runs)),
    index=pre_selected,
    format_func=lambda i: run_labels[i],
)

selected_run = runs[selected_idx]

# Past run summary
try:
    past_config = CampaignConfig.model_validate(json.loads(selected_run["campaign_config_json"]))
    past_campaign = past_config.campaign

    st.markdown(
        f"""<div class="mm-card">
        <div class="mm-stat"><span class="mm-stat-label">Campaign:</span> <span class="mm-stat-value">{past_campaign.name}</span></div>
        <div class="mm-stat"><span class="mm-stat-label">Objective:</span> <span class="mm-stat-value">{past_campaign.objective.value}</span></div>
        <div class="mm-stat"><span class="mm-stat-label">Daily Budget:</span> <span class="mm-stat-value">${past_campaign.budget_daily_usd:.2f}</span></div>
        <div class="mm-stat"><span class="mm-stat-label">Ad Sets:</span> <span class="mm-stat-value">{len(past_config.ad_sets)}</span></div>
        <div class="mm-stat"><span class="mm-stat-label">Ads:</span> <span class="mm-stat-value">{len(past_config.ads)}</span></div>
        </div>""",
        unsafe_allow_html=True,
    )
except Exception:
    st.warning("Could not parse past campaign config.")
    past_config = None

# Override form
with st.form("optimize_form"):
    default_budget = past_campaign.budget_daily_usd if past_config else 100.0

    new_budget = st.number_input(
        "New Daily Budget (USD)",
        min_value=1.0,
        value=default_budget,
        step=10.0,
    )
    ads_per_ad_set = st.number_input(
        "Ads per Ad Set (optional)",
        min_value=1,
        max_value=10,
        value=2,
    )

    overrides_file = st.file_uploader(
        "Ad Set Overrides (optional)",
        type=["json"],
    )

    _model_options = ["Opus 4.6 (Recommended)", "Sonnet 4.6", "Haiku 4.5"]
    _model_map = {
        "Opus 4.6 (Recommended)": ClaudeModel.OPUS,
        "Sonnet 4.6": ClaudeModel.SONNET,
        "Haiku 4.5": ClaudeModel.HAIKU,
    }
    selected_model_label = st.selectbox("Claude Model", _model_options)
    st.caption("Opus: best quality | Sonnet: balanced | Haiku: fastest & cheapest")

    dry_run = st.toggle("Dry Run", value=True)

    if not dry_run:
        st.markdown(
            '<div class="mm-warning-banner">'
            "Dry Run is OFF — executing will make real Meta API calls."
            "</div>",
            unsafe_allow_html=True,
        )

    submitted = st.form_submit_button(
        "Generate Optimized Strategy", type="primary", use_container_width=True
    )

if submitted:
    if not past_config:
        st.error("Cannot optimize — past config is invalid.")
        st.stop()

    # Parse overrides
    ad_set_overrides: dict[str, dict] | None = None
    if overrides_file is not None:
        try:
            raw = json.loads(overrides_file.read())
            if not isinstance(raw, dict) or not all(isinstance(v, dict) for v in raw.values()):
                st.error("Overrides must be a JSON object with dict values.")
                st.stop()
            ad_set_overrides = raw
        except json.JSONDecodeError as e:
            st.error(f"Invalid JSON in overrides file: {e}")
            st.stop()

    claude_model = _model_map[selected_model_label]

    st.session_state["mm_dry_run"] = dry_run
    reset_pipeline()
    st.session_state["mm_dry_run"] = dry_run
    st.session_state["mm_model"] = claude_model.value

    # Build optimization context (mirrors main.py optimize command)
    optimization_context = (
        f"This is an OPTIMIZATION of an existing campaign. "
        f"Previous campaign: '{past_campaign.name}'. "
        f"Previous reasoning: {past_config.reasoning}. "
        f"Previous optimization notes: {past_config.optimization_notes}. "
        f"Improve upon the previous strategy based on the current account data."
    )

    goal = f"Optimize the previous campaign '{past_campaign.name}'. {optimization_context}"

    try:
        opt_logger = RunLogger()
        run_id = opt_logger.create_run(account_id=account.id)
        st.session_state["mm_run_id"] = run_id

        with st.status("Running optimization pipeline...", expanded=True) as status:
            # Phase 1
            st.write("Ingesting current account data...")
            client = MetaClient(
                access_token=account.access_token,
                app_id=account.app_id,
                app_secret=account.app_secret,
                ad_account_id=account.ad_account_id,
            )
            ingested_data = run_ingest(client, opt_logger, run_id)
            st.session_state["mm_ingested_data"] = ingested_data

            # Phase 2
            st.write("Generating optimized strategy with Claude...")
            campaign_config = run_strategize(
                data=ingested_data,
                logger=opt_logger,
                run_id=run_id,
                product_name=past_campaign.name,
                product_url="",
                product_description="",
                target_customer="",
                goal=goal,
                budget=new_budget,
                max_daily_budget_usd=account.max_daily_budget_usd,
                ads_per_ad_set=ads_per_ad_set,
                ad_set_overrides=ad_set_overrides,
                model=claude_model,
            )

            set_config(campaign_config)
            st.session_state["mm_approval_state"] = "generated"
            st.session_state["mm_phase"] = "awaiting_approval"
            status.update(label="Optimized strategy generated", state="complete")

        st.switch_page("pages/approval.py")

    except SetupError as e:
        st.error(f"Setup Error: {e}")
        set_error(e)
    except CredentialDecryptionError as e:
        st.error(f"Credential Error: {e}")
        set_error(e)
    except MetaAPIError as e:
        st.error(f"Meta API Error: {e}")
        set_error(e)
    except StrategyError as e:
        st.error(f"Strategy Error: {e}")
        set_error(e)
    except BudgetCapError as e:
        st.error(f"Budget exceeds cap of ${account.max_daily_budget_usd:.2f}: {e}")
        set_error(e)
    except Exception as e:
        st.error(f"Unexpected error: {e}")
        set_error(e)
