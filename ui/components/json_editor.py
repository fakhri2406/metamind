"""JSON editor component with Pydantic validation."""

from __future__ import annotations

import json

import streamlit as st

from models.campaign_config import CampaignConfig
from ui.state import set_config


def render_json_editor() -> None:
    """Render a JSON text editor with validation for CampaignConfig."""
    st.markdown('<div class="mm-section-header">Campaign Config JSON</div>', unsafe_allow_html=True)

    current_json = st.session_state.get("mm_campaign_config_json", "{}")

    edited_json = st.text_area(
        "Edit JSON",
        value=current_json,
        height=500,
        key="mm_json_editor_area",
        label_visibility="collapsed",
    )

    col1, _ = st.columns([1, 4])
    with col1:
        validate_clicked = st.button("Validate JSON", type="secondary")

    if validate_clicked:
        try:
            parsed = json.loads(edited_json)
            config = CampaignConfig.model_validate(parsed)
            set_config(config)
            st.success("Valid CampaignConfig")
        except json.JSONDecodeError as e:
            st.error(f"Invalid JSON: {e}")
        except Exception as e:
            st.error(f"Validation error: {e}")
