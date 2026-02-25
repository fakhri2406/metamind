"""Custom CSS styling for MetaMind Streamlit UI."""

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&family=JetBrains+Mono:wght@400;500&display=swap');

/* Global font override — targeted to avoid breaking Material Symbols icons.
   Never use blanket span/div selectors as they clobber icon fonts. */
html, body,
[class*="css"],
input, textarea, select, button, option,
label, p, li, th, td,
h1, h2, h3, h4, h5, h6,
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stSelectbox"] [data-baseweb="select"],
[data-testid="stMultiSelect"] [data-baseweb="select"],
[data-testid="stFileUploader"] section,
[data-testid="stWidgetLabel"],
[data-testid="stMarkdownContainer"],
[data-testid="stExpander"],
[data-testid="stForm"],
[data-testid="stDataFrame"],
[data-testid="stTable"],
[data-testid="stCaption"],
[data-testid="stToast"],
[data-baseweb="input"],
[data-baseweb="textarea"],
[data-baseweb="select"],
[data-baseweb="popover"] {
    font-family: 'DM Sans', sans-serif !important;
}

/* Hide Streamlit chrome */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header [data-testid="stStatusWidget"] {display: none;}
[data-testid="stDeployButton"] {display: none;}

/* Reduce main content top padding */
.stMainBlockContainer {
    padding-top: 2.5rem !important;
}

/* Card styles */
.mm-card {
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 1.25rem;
    margin-bottom: 1rem;
    background: rgba(255, 255, 255, 0.02);
}

.mm-card-mono {
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 1.25rem;
    margin-bottom: 1rem;
    background: rgba(255, 255, 255, 0.02);
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.85rem;
    line-height: 1.6;
    white-space: pre-wrap;
    word-wrap: break-word;
}

/* Badge styles */
.mm-badge {
    display: inline-block;
    padding: 0.2rem 0.75rem;
    border-radius: 999px;
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    vertical-align: middle;
    margin-left: 0.5rem;
}

.mm-badge-paused {
    background: rgba(245, 158, 11, 0.15);
    color: #f59e0b;
    border: 1px solid rgba(245, 158, 11, 0.3);
}

.mm-badge-approved {
    background: rgba(40, 69, 214, 0.15);
    color: #2845D6;
    border: 1px solid rgba(40, 69, 214, 0.3);
}

.mm-badge-rejected {
    background: rgba(239, 68, 68, 0.15);
    color: #ef4444;
    border: 1px solid rgba(239, 68, 68, 0.3);
}

.mm-badge-dryrun {
    background: rgba(99, 102, 241, 0.15);
    color: #818cf8;
    border: 1px solid rgba(99, 102, 241, 0.3);
}

/* Section header */
.mm-section-header {
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: rgba(255, 255, 255, 0.4);
    margin-bottom: 0.5rem;
}

/* Summary stat */
.mm-stat {
    font-size: 0.85rem;
    color: rgba(255, 255, 255, 0.7);
    margin-bottom: 0.25rem;
}

.mm-stat-label {
    color: rgba(255, 255, 255, 0.4);
    font-size: 0.75rem;
}

.mm-stat-value {
    color: rgba(255, 255, 255, 0.9);
    font-weight: 500;
}

/* Phase stepper */
.mm-step {
    text-align: center;
    padding: 0.5rem;
}

.mm-step-active {
    color: #2845D6;
    font-weight: 600;
}

.mm-step-complete {
    color: rgba(40, 69, 214, 0.6);
}

.mm-step-pending {
    color: rgba(255, 255, 255, 0.25);
}

.mm-step-icon {
    font-size: 1.2rem;
    margin-bottom: 0.25rem;
}

/* JSON editor text area — monospace */
[data-testid="stTextArea"] textarea {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.82rem !important;
    line-height: 1.5 !important;
}

/* Warning banner for dry-run off */
.mm-warning-banner {
    background: rgba(245, 158, 11, 0.1);
    border: 1px solid rgba(245, 158, 11, 0.3);
    border-radius: 8px;
    padding: 0.75rem 1rem;
    color: #f59e0b;
    font-size: 0.85rem;
    margin-bottom: 1rem;
}

/* Subtle divider */
.mm-divider {
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    margin: 1.5rem 0;
}

/* Ad set / ad nested card */
.mm-nested-card {
    border-left: 2px solid rgba(40, 69, 214, 0.3);
    padding-left: 1rem;
    margin-left: 0.5rem;
    margin-bottom: 0.75rem;
}

/* Page title styling */
.mm-page-title {
    font-size: 1.75rem;
    font-weight: 700;
    margin-bottom: 0.25rem;
}

/* Primary color overrides are handled by .streamlit/config.toml theme.
   Additional CSS overrides below for elements the theme may not reach. */
[data-testid="stBaseButton-primary"] {
    background-color: #2845D6 !important;
    border-color: #2845D6 !important;
}
[data-testid="stBaseButton-primary"]:hover {
    background-color: #1e3ab8 !important;
    border-color: #1e3ab8 !important;
}
</style>
"""
