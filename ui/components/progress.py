"""Phase progress stepper component."""

from __future__ import annotations

import streamlit as st

_PHASES = [
    ("Ingest", "ingest"),
    ("Strategize", "strategize"),
    ("Execute", "execute"),
]


def render_progress(current_phase: str) -> None:
    """Render a horizontal three-step phase indicator.

    Args:
        current_phase: One of "idle", "ingest", "strategize", "execute", "complete", "error".
    """
    phase_order = ["ingest", "strategize", "execute"]
    current_idx = phase_order.index(current_phase) if current_phase in phase_order else -1
    is_complete = current_phase == "complete"

    cols = st.columns(3)
    for i, (label, phase_key) in enumerate(_PHASES):
        with cols[i]:
            if is_complete or i < current_idx:
                icon = "&#10003;"
                css_class = "mm-step-complete"
            elif i == current_idx:
                icon = "&#9679;"
                css_class = "mm-step-active"
            else:
                icon = "&#9675;"
                css_class = "mm-step-pending"

            st.markdown(
                f'<div class="mm-step {css_class}">'
                f'<div class="mm-step-icon">{icon}</div>'
                f"{label}</div>",
                unsafe_allow_html=True,
            )
