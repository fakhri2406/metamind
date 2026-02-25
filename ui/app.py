"""MetaMind Streamlit UI — entry point."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path so we can import config, phases, models, etc.
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import streamlit as st  # noqa: E402

from exceptions import SetupError  # noqa: E402
from ui.state import init_state  # noqa: E402
from ui.styles import CUSTOM_CSS  # noqa: E402

# Page config — must be first Streamlit call
st.set_page_config(
    page_title="MetaMind",
    page_icon=":material/psychology:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inject custom CSS
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# Initialize session state
init_state()

# Run migration on startup
if not st.session_state.get("mm_migration_done"):
    try:
        import config
        from storage.migrations import migrate

        migrate(config.DB_PATH)
        st.session_state["mm_migration_done"] = True
    except Exception:
        st.session_state["mm_migration_done"] = True  # Don't block on migration failure

# Run setup check once
if not st.session_state.get("mm_setup_checked"):
    try:
        import config

        config.check_setup()
        st.session_state["mm_setup_ok"] = True
        st.session_state["mm_setup_error"] = None
    except SetupError as e:
        st.session_state["mm_setup_ok"] = False
        st.session_state["mm_setup_error"] = str(e)
    except Exception as e:
        st.session_state["mm_setup_ok"] = False
        st.session_state["mm_setup_error"] = f"Unexpected setup error: {e}"
    st.session_state["mm_setup_checked"] = True

# Sidebar logo — use st.logo() so it renders above navigation
st.logo(
    image="https://placehold.co/200x40/2845D6/white?text=MetaMind&font=roboto",
    icon_image="https://placehold.co/40x40/2845D6/white?text=M&font=roboto",
)

# Navigation
pages = [
    st.Page("pages/accounts.py", title="Accounts", icon=":material/manage_accounts:"),
    st.Page("pages/new_campaign.py", title="New Campaign", icon=":material/add_circle:"),
    st.Page("pages/approval.py", title="Review & Approve", icon=":material/check_circle:"),
    st.Page("pages/history.py", title="Run History", icon=":material/history:"),
    st.Page("pages/optimize.py", title="Optimize", icon=":material/trending_up:"),
]

nav = st.navigation(pages)
nav.run()
