"""Page 2: Approval Gate — review, edit, approve, or reject campaign config."""

from __future__ import annotations

import json

import streamlit as st

from exceptions import CredentialDecryptionError, MetaAPIError
from models.campaign_config import CampaignConfig
from phases.execute import run_execute
from storage.logger import RunLogger
from ui.components.account_selector import render_account_selector
from ui.components.config_viewer import render_config_summary
from ui.components.json_editor import render_json_editor
from ui.state import get_config, init_state, reset_pipeline, set_config
from utils.meta_client import MetaClient

init_state()

st.markdown('<div class="mm-page-title">Review & Approve</div>', unsafe_allow_html=True)

approval_state = st.session_state["mm_approval_state"]

# --- State: idle ---
if approval_state == "idle":
    st.info("No campaign pending review. Start from **New Campaign** or **Optimize** page.")
    st.stop()

# --- State: rejected ---
if approval_state == "rejected":
    st.markdown(
        '<span class="mm-badge mm-badge-rejected">REJECTED</span>',
        unsafe_allow_html=True,
    )
    st.warning("This campaign was rejected and will not be executed.")
    if st.button("Start New Campaign"):
        reset_pipeline()
        st.switch_page("pages/new_campaign.py")
    st.stop()

# Account selector
account = render_account_selector()
if account is None:
    st.stop()

# --- State: approved ---
if approval_state == "approved":
    st.markdown(
        '<span class="mm-badge mm-badge-approved">APPROVED</span> '
        '<span class="mm-badge mm-badge-paused">PAUSED</span>',
        unsafe_allow_html=True,
    )

    config_obj = get_config()
    if config_obj:
        render_config_summary(config_obj)

    # Show execution results if available
    run_id = st.session_state.get("mm_run_id")
    if run_id:
        logger = RunLogger()
        run = logger.get_run(run_id)
        if run:
            with st.expander("Execution Log", expanded=True):
                if run.created_campaign_id:
                    st.markdown(f"**Campaign ID:** `{run.created_campaign_id}`")
                if run.created_ad_set_ids:
                    ids = json.loads(run.created_ad_set_ids) if isinstance(run.created_ad_set_ids, str) else run.created_ad_set_ids
                    st.markdown(f"**Ad Set IDs:** {', '.join(f'`{i}`' for i in ids)}")
                if run.created_ad_ids:
                    ids = json.loads(run.created_ad_ids) if isinstance(run.created_ad_ids, str) else run.created_ad_ids
                    st.markdown(f"**Ad IDs:** {', '.join(f'`{i}`' for i in ids)}")
                if run.execution_error:
                    st.error(f"Execution error: {run.execution_error}")
                if run.dry_run:
                    st.markdown('<span class="mm-badge mm-badge-dryrun">DRY RUN</span>', unsafe_allow_html=True)

    st.markdown('<div class="mm-divider"></div>', unsafe_allow_html=True)
    if st.button("Start New Campaign"):
        reset_pipeline()
        st.switch_page("pages/new_campaign.py")
    st.stop()

# --- State: generated — main approval interface ---
config_obj = get_config()
if not config_obj:
    st.error("No campaign config found. Please generate a strategy first.")
    st.stop()

# Header with badges
st.markdown(
    f"### {config_obj.campaign.name} "
    f'<span class="mm-badge mm-badge-paused">PAUSED</span>',
    unsafe_allow_html=True,
)

# Two-column layout: reasoning | config summary
col_left, col_right = st.columns([0.6, 0.4])

with col_left:
    st.markdown('<div class="mm-section-header">Reasoning</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="mm-card-mono">{config_obj.reasoning}</div>',
        unsafe_allow_html=True,
    )

    if config_obj.optimization_notes:
        st.markdown('<div class="mm-section-header">Optimization Notes</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="mm-card-mono">{config_obj.optimization_notes}</div>',
            unsafe_allow_html=True,
        )

with col_right:
    render_config_summary(config_obj)

st.markdown('<div class="mm-divider"></div>', unsafe_allow_html=True)

# JSON editor
render_json_editor()

st.markdown('<div class="mm-divider"></div>', unsafe_allow_html=True)

# Action bar
col_approve, col_edit, col_reject = st.columns(3)

with col_approve:
    approve_clicked = st.button("Approve", type="primary", use_container_width=True)

with col_edit:
    edit_clicked = st.button("Edit & Re-validate", use_container_width=True)

with col_reject:
    reject_clicked = st.button("Reject", use_container_width=True)

# --- Edit handler ---
if edit_clicked:
    edited_text = st.session_state.get("mm_json_editor_area", "")
    try:
        parsed = json.loads(edited_text)
        updated_config = CampaignConfig.model_validate(parsed)
        set_config(updated_config)
        st.success("Config updated and validated successfully.")
        st.rerun()
    except json.JSONDecodeError as e:
        st.error(f"Invalid JSON: {e}")
    except Exception as e:
        st.error(f"Validation error: {e}")

# --- Reject handler ---
if reject_clicked:
    run_id = st.session_state.get("mm_run_id")
    if run_id:
        logger = RunLogger()
        logger.log_approval(run_id, approved=False)
    st.session_state["mm_approval_state"] = "rejected"
    st.rerun()

# --- Approve handler ---
if approve_clicked:
    # Re-validate from editor content
    edited_text = st.session_state.get("mm_json_editor_area", "")
    try:
        parsed = json.loads(edited_text)
        final_config = CampaignConfig.model_validate(parsed)
        set_config(final_config)
    except (json.JSONDecodeError, Exception) as e:
        st.error(f"Cannot approve — JSON validation failed: {e}")
        st.stop()

    run_id = st.session_state.get("mm_run_id")
    logger = RunLogger()

    if run_id:
        logger.log_approval(run_id, approved=True)

    dry_run = st.session_state.get("mm_dry_run", True)

    if dry_run:
        # Execute dry run directly
        try:
            with st.status("Running dry-run execution...", expanded=True) as status:
                client = MetaClient(
                    access_token=account.access_token,
                    app_id=account.app_id,
                    app_secret=account.app_secret,
                    ad_account_id=account.ad_account_id,
                )
                run_execute(
                    client, final_config, logger, run_id,
                    dry_run=True, page_id=account.page_id,
                )
                status.update(label="Dry run complete", state="complete")
            st.session_state["mm_approval_state"] = "approved"
            st.rerun()
        except CredentialDecryptionError as e:
            st.error(f"Credential Error: {e}")
        except MetaAPIError as e:
            st.error(f"Execution error: {e}")
        except Exception as e:
            st.error(f"Unexpected error: {e}")
    else:
        # Real execution — show confirmation dialog
        @st.dialog("Confirm Live Execution")
        def _confirm_execute():
            st.warning(
                "This will make **real API calls** to Meta and create a campaign "
                "(status=PAUSED). This action cannot be easily undone."
            )
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Execute", type="primary", use_container_width=True):
                    try:
                        client = MetaClient(
                            access_token=account.access_token,
                            app_id=account.app_id,
                            app_secret=account.app_secret,
                            ad_account_id=account.ad_account_id,
                        )
                        run_execute(
                            client, final_config, logger, run_id,
                            dry_run=False, page_id=account.page_id,
                        )
                        st.session_state["mm_approval_state"] = "approved"
                        st.rerun()
                    except CredentialDecryptionError as e:
                        st.error(f"Credential Error: {e}")
                    except MetaAPIError as e:
                        st.error(f"Execution error: {e}")
                    except Exception as e:
                        st.error(f"Unexpected error: {e}")
            with col2:
                if st.button("Cancel", use_container_width=True):
                    st.rerun()

        _confirm_execute()
