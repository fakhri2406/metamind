"""Page 1: New Campaign — form input, Phase 1 + Phase 2 execution."""

from __future__ import annotations

import json

import streamlit as st

from exceptions import BudgetCapError, CredentialDecryptionError, MetaAPIError, SetupError, StrategyError
from phases.ingest import run_ingest
from phases.strategize import run_strategize
from storage.logger import RunLogger
from ui.components.account_selector import render_account_selector
from ui.state import init_state, reset_pipeline, set_config, set_error
from utils.meta_client import MetaClient

init_state()

# Page header
st.markdown('<div class="mm-page-title">New Campaign</div>', unsafe_allow_html=True)

# Setup check
if not st.session_state["mm_setup_ok"]:
    msg = st.session_state.get("mm_setup_error") or "Environment not configured."
    st.error(f"Setup Error: {msg}")
    st.info("Check your `.env` file and ensure all required variables are set.")
    st.stop()

# Account selector
account = render_account_selector()
if account is None:
    st.stop()

# --- Form ---
with st.form("new_campaign_form"):
    col1, col2 = st.columns([0.55, 0.45])

    with col1:
        product_name = st.text_input("Product Name")
        product_url = st.text_input("Product URL")
        product_description = st.text_area("Product Description", height=100)
        target_customer = st.text_area("Target Customer", height=80)
        goal = st.text_input("Goal", placeholder="e.g. maximize purchases")

    with col2:
        budget = st.number_input(
            "Daily Budget (USD)", min_value=1.0, value=100.0, step=10.0
        )
        aov = st.number_input(
            "Average Order Value (USD, optional)", min_value=0.0, value=0.0, step=5.0
        )
        ads_per_ad_set = st.number_input(
            "Ads per Ad Set", min_value=1, max_value=10, value=2
        )

        st.markdown('<div class="mm-divider"></div>', unsafe_allow_html=True)

        dry_run = st.toggle("Dry Run", value=True)

    # Ad set overrides
    with st.expander("Ad Set Overrides (optional)"):
        overrides_file = st.file_uploader(
            "Upload JSON overrides file",
            type=["json"],
            help="Per-ad-set configuration overrides. See CLAUDE.md for format.",
        )
        st.caption(
            'Format: `{"Ad Set Name": {"age_min": 25, "creative_approach": "..."}, ...}`'
        )

    submitted = st.form_submit_button("Generate Strategy", type="primary", use_container_width=True)

# Dry-run warning (outside form so it updates reactively)
if not dry_run:
    st.markdown(
        '<div class="mm-warning-banner">'
        "Dry Run is OFF — executing will make real Meta API calls and create campaigns."
        "</div>",
        unsafe_allow_html=True,
    )

# --- Submission handler ---
if submitted:
    # Validate required fields
    missing = []
    if not product_name.strip():
        missing.append("Product Name")
    if not product_url.strip():
        missing.append("Product URL")
    if not product_description.strip():
        missing.append("Product Description")
    if not target_customer.strip():
        missing.append("Target Customer")
    if not goal.strip():
        missing.append("Goal")
    if missing:
        st.error(f"Required fields missing: {', '.join(missing)}")
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

    # Store dry-run preference
    st.session_state["mm_dry_run"] = dry_run

    # Reset pipeline state for new run
    reset_pipeline()
    st.session_state["mm_dry_run"] = dry_run

    # Run phases
    try:
        logger = RunLogger()
        run_id = logger.create_run(account_id=account.id)
        st.session_state["mm_run_id"] = run_id

        with st.status("Running pipeline...", expanded=True) as status:
            # Phase 1
            st.write("Ingesting account data...")
            st.session_state["mm_phase"] = "ingesting"
            client = MetaClient(
                access_token=account.access_token,
                app_id=account.app_id,
                app_secret=account.app_secret,
                ad_account_id=account.ad_account_id,
            )
            ingested_data = run_ingest(client, logger, run_id)
            st.session_state["mm_ingested_data"] = ingested_data

            # Phase 2
            st.write("Generating strategy with Claude...")
            st.session_state["mm_phase"] = "strategizing"
            campaign_config = run_strategize(
                data=ingested_data,
                logger=logger,
                run_id=run_id,
                product_name=product_name.strip(),
                product_url=product_url.strip(),
                product_description=product_description.strip(),
                target_customer=target_customer.strip(),
                goal=goal.strip(),
                budget=budget,
                max_daily_budget_usd=account.max_daily_budget_usd,
                aov=aov if aov > 0 else None,
                ads_per_ad_set=ads_per_ad_set,
                ad_set_overrides=ad_set_overrides,
            )

            set_config(campaign_config)
            st.session_state["mm_approval_state"] = "generated"
            st.session_state["mm_phase"] = "awaiting_approval"
            status.update(label="Strategy generated", state="complete")

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
