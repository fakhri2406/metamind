# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Overview

MetaMind is an AI-powered Meta Ads automation agent. This repository (`metamind-engine`) is built in Python. It pulls campaign performance data from the Meta Marketing API, sends it to Claude (Anthropic API) for strategic analysis, and uses the resulting structured recommendations to automatically build and launch Meta ad campaigns via the API.

The system has three phases:
1. **Ingest** — Pull account data, campaign history, and audience insights from Meta API
2. **Strategize** — Send data to Claude, receive a validated JSON campaign config
3. **Execute** — Use that config to create campaigns, ad sets, and ads via Meta API

There is always a human approval gate between Phase 2 and Phase 3. Campaigns are always created with `status=PAUSED` and never auto-activated.

---

## Project Structure
```
metamind-engine/                   # This folder (project root)
├── main.py                        # Typer CLI — entry point for all commands
├── config.py                      # Env vars, constants, setup validation
├── exceptions.py                  # Custom exception classes
├── CLAUDE.md                      # This file
├── requirements.txt
├── Makefile
├── .env                           # Never commit this
├── .gitignore
│
├── phases/
│   ├── __init__.py
│   ├── ingest.py                  # Phase 1: MetaClient → IngestedData
│   ├── strategize.py              # Phase 2: IngestedData → Claude → CampaignConfig
│   └── execute.py                 # Phase 3: CampaignConfig → Meta API calls
│
├── models/
│   ├── __init__.py                # Re-exports all models and enums
│   ├── campaign_config.py         # Pydantic models for Claude's JSON output (source of truth)
│   └── meta_data.py               # Pydantic models for Meta API responses
│
├── prompts/
│   ├── __init__.py
│   ├── system_prompt.txt          # Claude's system prompt (loaded at runtime)
│   └── analysis_template.py       # Builds the dynamic user prompt from IngestedData
│
├── storage/
│   ├── __init__.py
│   └── logger.py                  # SQLAlchemy + SQLite logger for all runs
│
├── utils/
│   ├── __init__.py
│   └── meta_client.py             # Thin wrapper around facebook-business SDK
│
├── data/
│   └── campaign_runs.db           # SQLite database (auto-created, never committed)
│
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_models.py
    ├── test_strategize.py
    └── test_ingest.py
```

---

## Tech Stack

| Layer | Tool |
|---|---|
| Language | Python 3.10+ |
| CLI | Typer + Rich |
| Meta API | facebook-business (official SDK) |
| AI | Anthropic Python SDK |
| Data validation | Pydantic v2 |
| Storage | SQLAlchemy + SQLite |
| Testing | pytest |
| Linting | ruff |

---

## Environment Variables

All loaded in `config.py` via `python-dotenv`. See `.env` for the current values.

| Variable | Purpose |
|---|---|
| `META_ACCESS_TOKEN` | Meta System User long-lived access token |
| `META_AD_ACCOUNT_ID` | Format: `act_XXXXXXXXX` |
| `META_APP_ID` | Meta Developer App ID |
| `META_APP_SECRET` | Meta Developer App Secret |
| `META_PAGE_ID` | Meta Page ID (required for creative creation) |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `MAX_DAILY_BUDGET_USD` | Hard cap — Claude cannot exceed this regardless of recommendation |
| `REQUIRE_HUMAN_APPROVAL` | `true` / `false` — gates execution after strategy |

**Critical:** `MAX_DAILY_BUDGET_USD` is enforced in code in `phases/strategize.py`, not by prompt. Never remove this check.

---

## The JSON Contract (Most Important Thing)

Claude's output must always be a raw JSON object (no markdown, no code fences, no prose) that validates against `CampaignConfig` in `models/campaign_config.py`.

This is the schema Claude must return:
```json
{
  "campaign": {
    "name": "string",
    "objective": "CONVERSIONS | TRAFFIC | AWARENESS | LEAD_GENERATION | ENGAGEMENT",
    "budget_daily_usd": 0.0,
    "budget_type": "CBO | ABO",
    "start_date": "YYYY-MM-DD",
    "end_date": "YYYY-MM-DD or null"
  },
  "ad_sets": [
    {
      "name": "string",
      "targeting_type": "lookalike | interest | retargeting | broad",
      "age_min": 18,
      "age_max": 65,
      "genders": ["male | female | all"],
      "interests": ["string"],
      "lookalike_source": "string or null",
      "lookalike_ratio": 0.01,
      "placements": "automatic | facebook_feed | instagram_feed | stories | reels",
      "bid_strategy": "LOWEST_COST | COST_CAP | BID_CAP",
      "bid_amount_usd": null,
      "daily_budget_usd": null
    }
  ],
  "ads": [
    {
      "name": "string",
      "ad_set_name": "must match an ad_set.name exactly",
      "format": "single_image | carousel | video | collection",
      "headline": "max 40 chars",
      "primary_text": "max 125 chars",
      "description": "max 30 chars or null",
      "cta": "SHOP_NOW | LEARN_MORE | SIGN_UP | GET_QUOTE | CONTACT_US | BOOK_NOW",
      "destination_url": "string",
      "creative_notes": "string — why this approach for this audience"
    }
  ],
  "reasoning": "string — full explanation of all strategic decisions",
  "optimization_notes": "string — what to monitor and when to make changes"
}
```

If Claude returns anything other than this structure, `phases/strategize.py` retries once, then raises `StrategyError`. Never loosen validation to make a bad response pass.

---

## Data Flow
```
User runs: python main.py run [args]
              │
              ▼
      config.check_setup()
      Validate env vars
              │
              ▼
      Load --ad-set-overrides file (if provided)
              │
              ▼
    Phase 1: phases/ingest.py
    MetaClient pulls:
    - Account info
    - Last 60 days campaign performance
    - Custom audiences
    - (Past AI run history if exists)
    → Returns IngestedData
              │
              ▼
    Phase 2: phases/strategize.py
    - Builds prompt via analysis_template.py
      (includes --ads-per-ad-set and --ad-set-overrides if provided)
    - Calls Anthropic API (claude-opus-4-6, temp=0)
    - Parses and validates JSON → CampaignConfig
    - Checks budget cap
    - Logs to SQLite
    → Returns CampaignConfig
              │
              ▼
    HUMAN APPROVAL GATE
    - Prints full strategy summary (Rich)
    - Prints Claude's reasoning
    - User types y / N / edit
    - If edit: opens JSON in $EDITOR, re-validates on save
              │
              ▼ (only if approved)
    Phase 3: phases/execute.py
    - If --dry-run: prints what would be created, no API calls
    - If --no-dry-run:
        1. Create Campaign (status=PAUSED)
        2. Resolve interest names → Meta interest IDs via TargetingSearch
        3. Create Ad Sets (status=PAUSED)
        4. Create Ad Creatives
        5. Create Ads (status=PAUSED)
    - Logs all created IDs to SQLite
    - Prints Ads Manager link
```

---

## Critical Rules — Never Violate These

1. **Campaigns are always created as `status=PAUSED`.** Never set status to ACTIVE during creation under any circumstances.

2. **The budget cap is enforced in code, not by prompt.** `config.MAX_DAILY_BUDGET_USD` must be checked in `strategize.py` before execution proceeds. If the check is ever removed or bypassed, the system is broken.

3. **Default to `--dry-run=True`.** Phase 3 must default to dry-run. A user must explicitly pass `--no-dry-run` to make real API calls.

4. **Never store credentials.** `.env` is gitignored. Never hardcode tokens, app secrets, or API keys anywhere in source code.

5. **Log everything.** Every Claude response, every API call result, every run — logged to SQLite. Never skip logging even if execution fails.

6. **Pydantic validation is the contract.** If `CampaignConfig` validation fails, raise an error. Never manually patch or coerce bad data to make it fit.

7. **Retry logic is limited.** If Claude returns invalid JSON, retry exactly once with a correction prompt. If it fails twice, raise `StrategyError` and stop. Do not loop indefinitely.

8. **Interest names must be resolved to IDs before creating ad sets.** Meta's API does not accept plain string interest names in targeting specs. Always call `TargetingSearch` to get the correct `{id, name}` objects.

---

## Error Handling Conventions

All custom exceptions live in a top-level `exceptions.py` file:

| Exception | When to raise |
|---|---|
| `MetaAPIError` | Any Meta API call fails after retries |
| `StrategyError` | Claude returns invalid/unparseable JSON after retry |
| `BudgetCapError` | Claude's recommended budget exceeds `MAX_DAILY_BUDGET_USD` |
| `ValidationError` | Pydantic model validation fails (use Pydantic's built-in) |
| `SetupError` | Missing env vars at startup |

Never use bare `except:`. Always catch specific exceptions and log before re-raising.

---

## Claude API Usage

- **Model:** `claude-opus-4-6` for Phase 2 (strategize) — this is the critical reasoning step, use the best model
- **Temperature:** `0` — deterministic output, no creativity needed here
- **Max tokens:** `4096`
- **System prompt:** loaded from `prompts/system_prompt.txt` at runtime (not hardcoded)
- **Output format:** The system prompt explicitly instructs Claude to return only raw JSON with no surrounding text
```python
# Canonical API call pattern
client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
response = client.messages.create(
    model="claude-opus-4-6",
    max_tokens=4096,
    temperature=0,
    system=system_prompt,
    messages=[{"role": "user", "content": user_prompt}]
)
raw_text = response.content[0].text
```

---

## Meta API Usage

- **SDK:** `facebook_business` (official)
- **API Version:** pin to `v21.0` in all calls — do not use "latest"
- **Rate limits:** Retry on error codes `17` (rate limit) and `80004` with exponential backoff (3 attempts max)
- **Ad Account ID:** always in format `act_XXXXXXXXX` — stored in config, never hardcoded
- **Currency:** Meta's API accepts budget in **cents of the account's currency**. Always convert: `int(usd_amount * 100)`. This conversion must happen in `execute.py`, not in the models.

---

## Testing Philosophy

- **No real API calls in tests.** Everything is mocked. Use `pytest` + `unittest.mock`.
- Tests live in `/tests/`. Run with `make test`.
- `conftest.py` provides shared fixtures: `sample_ingested_data`, `sample_campaign_config`, `sample_campaign_config_dict`.
- Test the models thoroughly — they are the contract between Claude and the Meta API.
- Test error paths: invalid JSON from Claude, budget cap exceeded, Meta API failure.

---

## CLI Commands
```bash
# Full pipeline (dry-run by default)
python main.py run --product-name "X" --product-url "https://..." \
  --product-description "..." --target-customer "..." \
  --goal "maximize purchases" --budget 100 --aov 65

# Specify number of ads per ad set
python main.py run [args] --ads-per-ad-set 3

# Use per-ad-set overrides from a JSON file
python main.py run [args] --ad-set-overrides path/to/overrides.json

# Full pipeline, execute for real
python main.py run [args] --no-dry-run

# View run history
python main.py history

# Validate a campaign config JSON file
python main.py validate-config path/to/config.json

# Optimize an existing campaign from a past run
python main.py optimize --run-id <UUID>
python main.py optimize --run-id <UUID> --budget 150 --ads-per-ad-set 2
python main.py optimize --run-id <UUID> --ad-set-overrides path/to/overrides.json
```

---

## Per-Ad-Set Configuration Overrides

The `--ad-set-overrides` option accepts a path to a JSON file with per-ad-set instructions for Claude. This is an **optional escape hatch** for when individual ad sets need different settings within a single campaign.

**How it works:** The overrides are injected into the prompt as instructions to Claude. Claude reads them and incorporates them into its output. There is no post-processing or merge logic — this is purely prompt-level.

**Override file format** (freeform — keys are ad set names, values are dicts of arbitrary fields):
```json
{
  "Interest Targeting - Fitness": {
    "age_min": 25,
    "age_max": 45,
    "ads_per_ad_set": 3,
    "target_customer": "Fitness enthusiasts who do yoga",
    "creative_approach": "Use lifestyle imagery"
  },
  "Broad Targeting": {
    "ads_per_ad_set": 1
  }
}
```

**Validation:** Minimal — the file must be valid JSON, top-level must be a dict, and each value must be a dict. Field names are not validated because they are freeform instructions to Claude (e.g., `creative_approach` is not a schema field).

**Precedence:** Override values take precedence over campaign-level defaults. Fields not specified in an override use campaign defaults. This is communicated to Claude via rule 13 in `prompts/system_prompt.txt`.

Available on both `run` and `optimize` commands.

---

## Development Guidelines

**When adding a new feature:**
1. Define or update the Pydantic model first (`models/`)
2. Update the prompt template if Claude needs to return new data (`prompts/`)
3. Implement the logic (`phases/` or `utils/`)
4. Wire into CLI (`main.py`)
5. Write tests

**When changing the JSON schema:**
- Update `models/campaign_config.py` (source of truth)
- Update `prompts/system_prompt.txt` to reflect the new schema
- Update this CLAUDE.md file
- Run tests to confirm nothing breaks

**When the Meta API changes:**
- Update the pinned API version in `utils/meta_client.py`
- Test affected endpoints in isolation before running the full pipeline
- Update field mappings in `execute.py` if endpoint params changed

**Code style:**
- Ruff for linting (`make lint`)
- Type hints on all function signatures
- Docstrings on all public functions and classes
- Use `rich` for all terminal output — no bare `print()` statements in phases or CLI
- Enums use `(str, Enum)` pattern for Python 3.10 compatibility (not `StrEnum`)

---

## Known Limitations and TODOs

- **Creative assets:** Phase 3 currently uses a placeholder image hash for ad creatives. Real implementation needs image upload via `/act_{id}/adimages` before creative creation. This is the main gap in the current build.
- **Carousel and video formats:** AdConfig supports these format types but `execute.py` only fully implements `single_image`. Other formats are stubbed with warnings.
- **Feedback loop performance data:** `optimize` command pulls Claude's past configs from the logger, but live campaign performance (post-launch ROAS) must be manually fetched and passed in until automated polling is built.
- **Multi-account support:** Config currently handles one ad account at a time. Multi-account support requires refactoring `config.py` and `MetaClient` to accept account ID as a runtime parameter.

---

## Glossary

| Term | Meaning |
|---|---|
| CBO | Campaign Budget Optimization — budget set at campaign level, Meta distributes |
| ABO | Ad Set Budget Optimization — budget set per ad set manually |
| ROAS | Return on Ad Spend — revenue / spend |
| CPM | Cost per 1,000 impressions |
| CPC | Cost per click |
| CTR | Click-through rate |
| Lookalike | Audience Meta builds to match characteristics of a source audience |
| Custom Audience | Audience built from your own data (pixel, customer list, etc.) |
| TargetingSearch | Meta API endpoint to resolve interest names to targeting IDs |
| Dry Run | Phase 3 execution mode that prints actions without making API calls |
