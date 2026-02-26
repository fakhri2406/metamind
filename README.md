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

Supports **multiple Meta Ad Accounts** with encrypted credential storage. Each pipeline run is scoped to a specific account.

## Tech Stack

| Layer | Tool |
|---|---|
| Language | Python 3.10+ |
| CLI | Typer + Rich |
| Web UI | Streamlit |
| Meta API | facebook-business SDK |
| AI | Anthropic Python SDK (Claude) |
| Validation | Pydantic v2 |
| Database | PostgreSQL + psycopg2 |
| ORM | SQLAlchemy 2.0+ |
| Migrations | Alembic |
| Encryption | cryptography (Fernet) |
| Testing | pytest |
| Linting | ruff |

## Quick Start

### Prerequisites

- Python 3.10+
- PostgreSQL 14+
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
ANTHROPIC_API_KEY=
DATABASE_URL=postgresql://user:password@localhost:5432/metamind-dev-db
REQUIRE_HUMAN_APPROVAL=true
METAMIND_ENCRYPTION_KEY=      # Generate with: python main.py generate-key
```

Meta credentials (access token, app ID, app secret, ad account ID, page ID) and budget caps are stored **per-account** in the database with sensitive fields encrypted. They are no longer environment variables.

### First-Time Setup

```bash
# 1. Create a PostgreSQL database
createdb metamind-dev-db

# 2. Generate an encryption key and add it to .env
python main.py generate-key

# 3. Create your first Meta Ad Account (runs migrations automatically)
python main.py accounts create
# (interactive prompts for name, access token, ad account ID, etc.)

# 4. List accounts to get the UUID
python main.py accounts list
```

### Run via CLI

```bash
# Generate a campaign strategy (dry-run by default)
python main.py run \
  --account-id <UUID> \
  --product-name "Premium Yoga Mat" \
  --product-url "https://example.com/yoga-mat" \
  --product-description "Eco-friendly non-slip yoga mat" \
  --target-customer "Health-conscious women 25-45" \
  --goal "maximize purchases" \
  --budget 100 \
  --aov 65

# Execute for real (creates PAUSED campaigns)
python main.py run --account-id <UUID> [args] --no-dry-run

# View past runs (all accounts or filtered)
python main.py history
python main.py history --account-id <UUID>

# Optimize a previous campaign
python main.py optimize --account-id <UUID> --run-id <UUID> --budget 150

# Validate a campaign config file
python main.py validate-config path/to/config.json
```

### Account Management

```bash
python main.py accounts create                       # Interactive prompts
python main.py accounts list                          # Masked credentials
python main.py accounts list --show-secrets           # Full credentials
python main.py accounts delete --account-id <UUID>    # Soft-delete
```

### Run via Web UI

```bash
bash ui/run.sh
```

Opens a Streamlit app at `http://localhost:8501` with five pages:

- **Accounts** - Create, edit, and delete Meta Ad Accounts
- **New Campaign** - Select an account, fill in campaign details, generate strategy
- **Review & Approve** - View Claude's strategy, edit JSON, approve or reject
- **Run History** - Browse past runs filtered by account, with expandable details
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
| `storage/` | SQLAlchemy + PostgreSQL: run logger, account CRUD, encryption |
| `alembic/` | Database migrations (Alembic) |
| `utils/` | Meta API client wrapper |
| `ui/` | Streamlit web interface |

## The JSON Contract

Claude returns a raw JSON object that must validate against `CampaignConfig` (defined in `models/campaign_config.py`). The schema includes campaign settings, ad sets with targeting, ads with creative, and Claude's reasoning. If validation fails, the system retries once, then raises `StrategyError`.

See [CLAUDE.md](CLAUDE.md) for the full schema and all implementation details.

## Safety Guarantees

- **Always PAUSED** -- Campaigns are never set to ACTIVE during creation
- **Budget cap** -- Per-account `max_daily_budget_usd` is enforced in code, not by prompt
- **Dry-run default** -- Real API calls require explicit `--no-dry-run`
- **Human approval** -- Strategy must be reviewed before execution
- **Strict validation** -- Pydantic enforces the JSON contract; bad data is never coerced
- **Full logging** -- Every run, Claude response, and API call is logged to PostgreSQL with account ID
- **Encrypted credentials** -- Account access tokens and app secrets are encrypted at rest with Fernet

## Development

```bash
# Create the test database
createdb metamind-test

# Run tests (requires PostgreSQL)
make test
# Or with a custom test DB:
TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/metamind-test make test

# Lint
make lint
```

All tests use mocks for external APIs -- no real Meta or Anthropic API calls. Tests require a PostgreSQL instance. See [CLAUDE.md](CLAUDE.md) for development guidelines, error handling conventions, and the full project reference.

## License

Proprietary. All rights reserved.
