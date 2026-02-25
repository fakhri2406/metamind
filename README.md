# MetaMind

AI-powered Meta Ads automation. Pulls campaign performance data from the Meta Marketing API, sends it to Claude for strategic analysis, and uses the resulting recommendations to build and launch Meta ad campaigns.

## How It Works

```
Ingest ──► Strategize ──► Approve ──► Execute
  │            │               │             │
  │  Pull account data,        │  Human      │  Create campaigns,
  │  campaigns, audiences      │  reviews    │  ad sets, ads
  │  from Meta API             │  strategy   │  via Meta API
  │                            │             │
  │            │               │             │
  │  Claude analyzes data      │  Edit JSON  │  Always PAUSED
  │  and returns a campaign    │  if needed  │  Always dry-run
  │  config as validated JSON  │             │  by default
```

Campaigns are always created with `status=PAUSED` and never auto-activated. A human approval gate sits between strategy generation and execution.

## Tech Stack

| Layer | Tool |
|---|---|
| Language | Python 3.10+ |
| CLI | Typer + Rich |
| Web UI | Streamlit |
| Meta API | facebook-business SDK |
| AI | Anthropic Python SDK (Claude) |
| Validation | Pydantic v2 |
| Storage | SQLAlchemy + SQLite |
| Testing | pytest |
| Linting | ruff |

## Quick Start

### Prerequisites

- Python 3.10+
- A [Meta Developer](https://developers.facebook.com/) app with Marketing API access
- An [Anthropic API](https://console.anthropic.com/) key

### Setup

```bash
git clone <repo-url> && cd metamind
pip install -r requirements.txt
cp .env.example .env  # Fill in your credentials
```

Required environment variables in `.env`:

```
META_ACCESS_TOKEN=        # System User long-lived token
META_AD_ACCOUNT_ID=       # Format: act_XXXXXXXXX
META_APP_ID=
META_APP_SECRET=
META_PAGE_ID=
ANTHROPIC_API_KEY=
MAX_DAILY_BUDGET_USD=500  # Hard cap enforced in code
REQUIRE_HUMAN_APPROVAL=true
```

### Run via CLI

```bash
# Generate a campaign strategy (dry-run by default)
python main.py run \
  --product-name "Premium Yoga Mat" \
  --product-url "https://example.com/yoga-mat" \
  --product-description "Eco-friendly non-slip yoga mat" \
  --target-customer "Health-conscious women 25-45" \
  --goal "maximize purchases" \
  --budget 100 \
  --aov 65

# Execute for real (creates PAUSED campaigns)
python main.py run [args] --no-dry-run

# View past runs
python main.py history

# Optimize a previous campaign
python main.py optimize --run-id <UUID> --budget 150

# Validate a campaign config file
python main.py validate-config path/to/config.json
```

### Run via Web UI

```bash
bash ui/run.sh
```

Opens a Streamlit app at `http://localhost:8501` with four pages:

- **New Campaign** - Form-based campaign creation
- **Review & Approve** - View Claude's strategy, edit JSON, approve or reject
- **Run History** - Browse past runs with expandable details
- **Optimize** - Re-optimize a previous campaign with new parameters

## Architecture

```
main.py (CLI)   ─┐
                 ├──► phases/ingest.py ──► phases/strategize.py ──► phases/execute.py
ui/app.py (Web) ─┘         │                      │                       │
                     Meta Marketing API      Anthropic API          Meta Marketing API
                     (read account data)     (Claude analysis)      (create campaigns)
```

Both interfaces call the same phase functions. The UI is a separate entry point, not a wrapper around the CLI.

### Key Components

| Directory | Purpose |
|---|---|
| `phases/` | Core pipeline: ingest, strategize, execute |
| `models/` | Pydantic v2 models -- the contract between Claude and Meta API |
| `prompts/` | System prompt and dynamic prompt builder |
| `storage/` | SQLAlchemy + SQLite run logger |
| `utils/` | Meta API client wrapper |
| `ui/` | Streamlit web interface |

## The JSON Contract

Claude returns a raw JSON object that must validate against `CampaignConfig` (defined in `models/campaign_config.py`). The schema includes campaign settings, ad sets with targeting, ads with creative, and Claude's reasoning. If validation fails, the system retries once, then raises `StrategyError`.

See [CLAUDE.md](CLAUDE.md) for the full schema and all implementation details.

## Safety Guarantees

- **Always PAUSED** -- Campaigns are never set to ACTIVE during creation
- **Budget cap** -- `MAX_DAILY_BUDGET_USD` is enforced in code, not by prompt
- **Dry-run default** -- Real API calls require explicit `--no-dry-run`
- **Human approval** -- Strategy must be reviewed before execution
- **Strict validation** -- Pydantic enforces the JSON contract; bad data is never coerced
- **Full logging** -- Every run, Claude response, and API call is logged to SQLite

## Development

```bash
# Run tests
make test

# Lint
make lint
```

All tests use mocks -- no real API calls. See [CLAUDE.md](CLAUDE.md) for development guidelines, error handling conventions, and the full project reference.

## License

Proprietary. All rights reserved.
