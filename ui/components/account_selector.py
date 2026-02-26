"""Reusable account selector component for Streamlit pages."""

from __future__ import annotations

from typing import Any, Optional

import streamlit as st

import config
from exceptions import CredentialDecryptionError
from storage.accounts import get_account, list_accounts


def render_account_selector() -> Optional[Any]:
    """Render an account selector and return the selected Account (with decrypted creds).

    Persists the selection in st.session_state["mm_active_account_id"].
    Returns None if no accounts exist (caller should st.stop()).
    """
    try:
        accounts = list_accounts(config.ENCRYPTION_KEY)
    except CredentialDecryptionError as e:
        st.error(f"Decryption Error: {e}")
        return None

    if not accounts:
        st.warning("No accounts configured. Go to the **Accounts** page to add one.")
        return None

    # Build label map
    labels = [f"{a.name} ({a.ad_account_id})" for a in accounts]
    id_map = {a.id: i for i, a in enumerate(accounts)}

    # Pre-select from session state
    current_id = st.session_state.get("mm_active_account_id")
    default_idx = id_map.get(current_id, 0) if current_id else 0

    selected_idx = st.selectbox(
        "Account",
        range(len(accounts)),
        index=default_idx,
        format_func=lambda i: labels[i],
        key="mm_account_selector",
    )

    selected = accounts[selected_idx]
    st.session_state["mm_active_account_id"] = selected.id

    # Return a fully decrypted Account object
    try:
        return get_account(config.ENCRYPTION_KEY, selected.id)
    except CredentialDecryptionError as e:
        st.error(f"Decryption Error: {e}")
        return None
