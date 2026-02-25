"""Session state management for MetaMind UI."""

from __future__ import annotations

import json
from typing import Any

import streamlit as st

_DEFAULTS: dict[str, Any] = {
    "mm_run_id": None,
    "mm_campaign_config": None,
    "mm_campaign_config_json": None,
    "mm_ingested_data": None,
    "mm_phase": "idle",
    "mm_approval_state": "idle",
    "mm_dry_run": True,
    "mm_error": None,
    "mm_optimize_run_id": None,
    "mm_model": "claude-opus-4-6",
    "mm_active_account_id": None,
    "mm_setup_ok": False,
    "mm_setup_error": None,
}


def init_state() -> None:
    """Initialize all session state keys with defaults if not already set."""
    for key, default in _DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = default


def reset_pipeline() -> None:
    """Reset pipeline state for a new run, preserving setup status."""
    keep = {"mm_setup_ok", "mm_setup_error", "mm_dry_run", "mm_active_account_id", "mm_model"}
    for key, default in _DEFAULTS.items():
        if key not in keep:
            st.session_state[key] = default


def set_config(config: Any) -> None:
    """Store a CampaignConfig and its JSON representation."""
    st.session_state["mm_campaign_config"] = config
    st.session_state["mm_campaign_config_json"] = json.dumps(
        config.model_dump(mode="json"), indent=2
    )


def get_config() -> Any | None:
    """Return the current CampaignConfig or None."""
    return st.session_state.get("mm_campaign_config")


def get_config_json() -> str | None:
    """Return the current config JSON string or None."""
    return st.session_state.get("mm_campaign_config_json")


def set_error(e: Exception) -> None:
    """Store an error message."""
    st.session_state["mm_error"] = str(e)
    st.session_state["mm_phase"] = "error"
