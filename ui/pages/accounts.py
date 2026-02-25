"""Page: Accounts — manage Meta Ad Accounts."""

from __future__ import annotations

import streamlit as st

import config
from exceptions import CredentialDecryptionError
from storage.accounts import (
    create_account,
    delete_account,
    get_account,
    list_accounts,
    update_account,
)
from ui.state import init_state

init_state()

st.markdown('<div class="mm-page-title">Accounts</div>', unsafe_allow_html=True)

# Setup check
if not st.session_state["mm_setup_ok"]:
    msg = st.session_state.get("mm_setup_error") or "Environment not configured."
    st.error(f"Setup Error: {msg}")
    st.info("Check your `.env` file and ensure `ANTHROPIC_API_KEY` and `METAMIND_ENCRYPTION_KEY` are set.")
    st.stop()

# --- Load accounts ---
try:
    accounts = list_accounts(config.DB_PATH, config.ENCRYPTION_KEY)
except CredentialDecryptionError as e:
    st.error(f"Decryption Error: {e}")
    st.stop()

# --- Layout: left=list, right=form ---
col_list, col_form = st.columns([0.4, 0.6])

# Track selected account for editing
if "mm_edit_account_id" not in st.session_state:
    st.session_state["mm_edit_account_id"] = None
if "mm_account_mode" not in st.session_state:
    st.session_state["mm_account_mode"] = "list"  # "list", "create", "edit"

with col_list:
    if st.button("Add Account", type="primary", use_container_width=True):
        st.session_state["mm_account_mode"] = "create"
        st.session_state["mm_edit_account_id"] = None
        st.rerun()

    if not accounts:
        st.info("No accounts yet. Click **Add Account** to get started.")
    else:
        for acct in accounts:
            is_selected = st.session_state.get("mm_edit_account_id") == acct.id
            border_style = "border-left: 3px solid #2845D6;" if is_selected else ""

            st.markdown(
                f'<div style="padding: 0.75rem; margin-bottom: 0.5rem; '
                f'border-radius: 0.375rem; background: rgba(255,255,255,0.03); {border_style}">'
                f'<strong>{acct.name}</strong><br/>'
                f'<span style="color: #888; font-size: 0.85rem;">{acct.ad_account_id}</span><br/>'
                f'<span style="color: #888; font-size: 0.85rem;">Budget cap: ${acct.max_daily_budget_usd:.2f}</span>'
                f"</div>",
                unsafe_allow_html=True,
            )
            if st.button("Edit", key=f"edit_{acct.id}", use_container_width=True):
                st.session_state["mm_account_mode"] = "edit"
                st.session_state["mm_edit_account_id"] = acct.id
                st.rerun()

with col_form:
    mode = st.session_state["mm_account_mode"]

    # --- Create mode ---
    if mode == "create":
        st.markdown("### New Account")
        with st.form("create_account_form"):
            name = st.text_input("Account Name")
            access_token = st.text_input("Access Token", type="password")
            ad_account_id = st.text_input("Ad Account ID", placeholder="act_XXXXXXXXX")
            app_id = st.text_input("App ID")
            app_secret = st.text_input("App Secret", type="password")
            page_id = st.text_input("Page ID")
            max_budget = st.number_input("Max Daily Budget (USD)", min_value=1.0, value=500.0, step=50.0)

            submitted = st.form_submit_button("Save Account", type="primary", use_container_width=True)

        if submitted:
            errors = []
            if not name.strip():
                errors.append("Account Name is required")
            if not access_token.strip():
                errors.append("Access Token is required")
            if not ad_account_id.strip():
                errors.append("Ad Account ID is required")
            elif not ad_account_id.startswith("act_"):
                errors.append("Ad Account ID must start with 'act_'")
            if not app_id.strip():
                errors.append("App ID is required")
            if not app_secret.strip():
                errors.append("App Secret is required")
            if not page_id.strip():
                errors.append("Page ID is required")
            if max_budget <= 0:
                errors.append("Budget must be positive")

            if errors:
                for err in errors:
                    st.error(err)
            else:
                try:
                    create_account(
                        db_path=config.DB_PATH,
                        encryption_key=config.ENCRYPTION_KEY,
                        name=name.strip(),
                        access_token=access_token.strip(),
                        ad_account_id=ad_account_id.strip(),
                        app_id=app_id.strip(),
                        app_secret=app_secret.strip(),
                        page_id=page_id.strip(),
                        max_daily_budget_usd=max_budget,
                    )
                    st.success(f"Account '{name.strip()}' created.")
                    st.session_state["mm_account_mode"] = "list"
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to create account: {e}")

    # --- Edit mode ---
    elif mode == "edit" and st.session_state.get("mm_edit_account_id"):
        edit_id = st.session_state["mm_edit_account_id"]
        try:
            acct = get_account(config.DB_PATH, config.ENCRYPTION_KEY, edit_id)
        except CredentialDecryptionError as e:
            st.error(f"Decryption Error: {e}")
            st.stop()

        if not acct:
            st.error("Account not found.")
            st.session_state["mm_account_mode"] = "list"
            st.stop()

        st.markdown(f"### Edit: {acct.name}")

        with st.form("edit_account_form"):
            name = st.text_input("Account Name", value=acct.name)
            ad_account_id = st.text_input("Ad Account ID", value=acct.ad_account_id)
            app_id = st.text_input("App ID", value=acct.app_id)
            page_id = st.text_input("Page ID", value=acct.page_id)
            max_budget = st.number_input(
                "Max Daily Budget (USD)", min_value=1.0, value=acct.max_daily_budget_usd, step=50.0
            )

            st.markdown("---")
            st.caption("Leave blank to keep existing values.")
            new_access_token = st.text_input("New Access Token", type="password", placeholder="********")
            new_app_secret = st.text_input("New App Secret", type="password", placeholder="********")

            col_save, col_delete = st.columns(2)
            with col_save:
                save_clicked = st.form_submit_button("Save Changes", type="primary", use_container_width=True)
            with col_delete:
                delete_clicked = st.form_submit_button("Delete Account", use_container_width=True)

        if save_clicked:
            updates = {}
            if name.strip() and name.strip() != acct.name:
                updates["name"] = name.strip()
            if ad_account_id.strip() and ad_account_id.strip() != acct.ad_account_id:
                if not ad_account_id.startswith("act_"):
                    st.error("Ad Account ID must start with 'act_'")
                    st.stop()
                updates["ad_account_id"] = ad_account_id.strip()
            if app_id.strip() and app_id.strip() != acct.app_id:
                updates["app_id"] = app_id.strip()
            if page_id.strip() and page_id.strip() != acct.page_id:
                updates["page_id"] = page_id.strip()
            if max_budget != acct.max_daily_budget_usd:
                updates["max_daily_budget_usd"] = max_budget
            if new_access_token.strip():
                updates["access_token"] = new_access_token.strip()
            if new_app_secret.strip():
                updates["app_secret"] = new_app_secret.strip()

            if updates:
                try:
                    update_account(config.DB_PATH, config.ENCRYPTION_KEY, edit_id, **updates)
                    st.success("Account updated.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to update: {e}")
            else:
                st.info("No changes detected.")

        if delete_clicked:
            delete_account(config.DB_PATH, edit_id)
            st.success(f"Account '{acct.name}' deleted.")
            st.session_state["mm_account_mode"] = "list"
            st.session_state["mm_edit_account_id"] = None
            st.rerun()

    # --- Default: no selection ---
    else:
        st.info("Select an account to edit, or click **Add Account** to create one.")
