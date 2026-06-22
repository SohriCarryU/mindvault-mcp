# mindvault-mcp

`mindvault-mcp` is a privacy-first MCP server for agents that need to turn messy multi-turn conversations into structured, durable knowledge cards.

The project is aimed at Hermes, OpenClaw, and other non-programming agent workflows. It has no Web UI. Markdown files are the source of truth, while SQLite provides query indexes and the verification queue.

## Current Phase

This repository includes Phase 8-A vector cache semantic ranking, Phase 7 optional LLM extraction, and Phase 6-C external validation persistence around the phase 2 MVP:

- Python 3.11 package structure
- HTTP/SSE MCP server entrypoint using FastMCP
- YAML configuration plus `.env.example`
- Pydantic domain models for cards, agents, and verification queue items
- Markdown card storage with frontmatter
- SQLite index for card lookup, filtering, sorting, verification queue persistence, validation result history, and cached card vectors
- Dual libraries: `primary` and `staging`
- Token-to-agent permission checks with library and privacy-level enforcement
- Rule-based memory extraction with `conservative`, `balanced`, and `aggressive` modes
- Optional LLM extraction through an OpenAI-compatible Chat Completions API, disabled by default with rule-based fallback
- Staging-to-primary review flow with approve/reject behavior
- Persistent verification queue placeholder with expiration status handling
- Minimal URL link validation behind an opt-in external validation flag, with persisted results and conservative card status mapping
- Basic duplicate detection using normalized title, tags, and domain similarity
- Embedding provider abstraction with no-op, local placeholder, API placeholder, and cached vector ranking when usable vectors are available
- Eight MCP tools with runnable behavior
- Pytest coverage for core storage, tools, extraction, verification queue, search, and deduplication

Out of scope for the current release:

- Web UI
- External search APIs
- Fact/content verification beyond URL reachability checks
- Provider-specific LLM adapters or local LLM APIs that are not OpenAI-compatible
- Real embedding model/API calls
- Complex schedulers
- Full review workflow UI
- Production authentication center
- Hardcoded secrets

## Quick Start

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
mindvault-mcp
```

By default the server reads `config.yaml` and runs on `127.0.0.1:8000` with SSE transport.

You can point at another config file:

```powershell
$env:MINDVAULT_CONFIG = "config.yaml"
mindvault-mcp
```

## Local Development

Requirements:

- Python 3.11 or newer
- `pip`
- Git

Install the package in editable mode with test dependencies:

```powershell
pip install -e ".[dev]"
```

Run the test suite:

```powershell
pytest -q
```

The project uses `src/` layout. The console entrypoint is declared in `pyproject.toml`:

```text
mindvault-mcp = mindvault_mcp.server:main
```

## Configuration

Public configuration lives in `config.yaml`.

Important sections:

- `server`: host, port, and transport
- `storage`: Markdown library paths and SQLite database path
- `auth`: token-to-agent mapping
- `extraction`: rule-based mode plus optional LLM extraction settings
- `embedding`: `none`, `local`, or `api`; default is `none`
- `defaults`: default ingest library and privacy level
- `verification`: verification backend mode placeholder, external validation enable flag, URL validation timeout, and persisted result history
- `dedup`: duplicate detection similarity threshold
- `logging`: log level

`.env.example` only lists environment variable names. The current application reads `MINDVAULT_CONFIG`, `EMBEDDING_PROVIDER`, and optional LLM extraction overrides such as `LLM_EXTRACTION_ENABLED`, `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`, and `LLM_TIMEOUT_SECONDS`; token values are configured in the selected YAML file for this MVP.

Keep committed `config.yaml` safe for public use. Do not commit real tokens or secrets. For local private credentials, use an uncommitted `.env` and point `MINDVAULT_CONFIG` at an uncommitted local config file.

The example config includes:

- `dev-admin-token`: high-trust admin with access to `primary` and `staging`
- `dev-trusted-token`: trusted agent with access to `staging`

## Running Locally

Start the MCP server:

```powershell
mindvault-mcp
```

Default local settings:

- host: `127.0.0.1`
- port: `8000`
- transport: `sse`
- SSE endpoint: `http://127.0.0.1:8000/sse`

See [MCP Endpoint](docs/mcp-endpoint.md) for transport, endpoint, and auth conventions.

## Testing

Run all tests:

```powershell
pytest -q
```

The test suite uses temporary directories for card storage and SQLite databases. It does not require `.env`, external services, or network access.

External validation is disabled by default. When explicitly enabled, the current validator only checks URL reachability with standard-library `urllib`; tests mock the HTTP layer and do not call the network. Phase 6-C persists validation results and maps outcomes conservatively to card `verification_status`.

LLM extraction tests mock the API layer and do not make real network requests.

Embedding tests use placeholder providers or monkeypatches and do not make real network requests.

## CI

GitHub Actions runs on `push` and `pull_request`.

The CI workflow installs the package with:

```text
pip install -e ".[dev]"
```

Then runs:

```text
pytest -q
```

The workflow targets Python 3.11 on Ubuntu and Windows.

## MCP Integration Notes

MCP clients should connect using the configured server host, port, and transport. With the default SSE configuration, use:

```text
http://127.0.0.1:8000/sse
```

Every tool call must include a configured `token`. The token maps to an agent identity with `trust_level` and `allowed_libraries`.

For a real local SSE smoke check, start `mindvault-mcp` in one terminal and run:

```powershell
python docs/sse-smoke-client.py --url http://127.0.0.1:8000/sse --token dev-trusted-token
```

Hermes/OpenClaw-style config examples are in [docs/hermes-openclaw-config.md](docs/hermes-openclaw-config.md).

## Data Layout

Markdown is the durable source of truth for cards:

```text
data/
  primary/
    *.md
  staging/
    *.md
```

Each card is saved as a Markdown file with YAML frontmatter. The body renders the same card as readable sections: problem, context, insight, and solution.

SQLite stores query indexes, verification queue records, validation result history, and vector cache rows:

```text
data/mindvault.sqlite
```

The code writes Markdown and SQLite together. Rebuilding SQLite from Markdown is still a roadmap item.

## Card Model

Cards include:

- `card_id`
- `title`
- `problem`
- `context`
- `insight`
- `solution`
- `tags`
- `domain`
- `confidence`
- `status`: `candidate`, `active`, `archived`, or `rejected`
- `source_agent`
- `privacy_level`
- `verification_status`: `verified`, `no_verification_needed`, `pending_verification`, `expired`, or `contested`
- `valid_until`
- `possible_duplicate_of`
- `created_at`
- `updated_at`
- `library`: `primary` or `staging`

## Permission Model

The MVP permission model is intentionally small:

- Each tool receives a token.
- The token maps to an agent identity.
- Agents have `trust_level` and `allowed_libraries`.
- Cards have `privacy_level`.
- Reads require library access and `trust_level >= privacy_level`.
- Staging writes require trust level `>= 3`.
- Primary writes and approval require trust level `>= 8`.

Rules are centralized in `src/mindvault_mcp/auth.py`.

## MCP Tools

### `ingest_memory`

Inputs: `token`, `text`, optional `metadata`.

Creates a card from raw text using the configured extractor. By default this is the local rule-based extractor; optional LLM extraction can be enabled and falls back to rule-based extraction on configuration or request failures. The default target is `staging`. If a similar staging card is found, `possible_duplicate_of` is set, but the new card is still retained for review.

### `search_cards`

Inputs: `token`, optional `query`, `tags`, `domain`, `library`, `status`, `verification_status`, `limit`, and `offset`.

Searches by keyword and filters. Results are grouped by library, with `primary` searched before `staging`. Ranking is deterministic: library priority, confidence, updated time, then card id. Results are permission-filtered.

If `EMBEDDING_PROVIDER` is set to `local` or `api` and the provider returns usable non-zero vectors, readable candidate cards can be ranked by cosine similarity using vectors cached in SQLite. If vectors are unavailable, empty, zero, or mismatched, search falls back to the existing keyword/filter logic.

### `list_candidates`

Inputs: `token`, optional `domain`, `tags`, `min_confidence`, `limit`, and `offset`.

Lists `staging` cards with `status=candidate`.

### `approve_card`

Inputs: `token`, `card_id`.

Promotes a card from `staging` to `primary`, marks it `active`, preserves `created_at` and `source_agent`, and updates Markdown plus SQLite.

### `reject_card`

Inputs: `token`, `card_id`, `reason`.

Marks a staging candidate as `rejected`, records the reason in the card context, and retains the Markdown record.

### `get_card`

Inputs: `token`, `card_id`.

Returns one card after library and privacy checks. If `valid_until` is in the past and the card is not `no_verification_needed`, the returned card can be marked `expired`.

### `update_card`

Inputs: `token`, `card_id`, `fields`.

Updates editable fields, then writes both Markdown and SQLite index state.

### `queue_verification`

Inputs: `token`, `card_id`, optional `reason`.

Marks a card as `pending_verification` and persists a pending queue record in SQLite. No network verification is run by this tool.

See [External Validation Protocol](docs/external-validation.md) for the Phase 6-C URL validator, persisted result history, status mapping, timeout setting, and privacy boundary.

## Extraction, Deduplication, and Embeddings

Extraction is rule-based by default and replaceable:

- `conservative`: leaves uncertain fields blank and lowers confidence.
- `balanced`: fills reasonable fields from labels and sentence structure.
- `aggressive`: tries to fill all core fields.

Optional LLM extraction can be enabled with an OpenAI-compatible Chat Completions endpoint. It is disabled by default, requires `LLM_API_KEY` when enabled, sends the full input text to the configured endpoint, and falls back to the rule-based extractor when disabled, missing credentials, timing out, failing, or receiving invalid JSON. See [LLM Extraction](docs/llm-extraction.md) for setup, privacy notes, and mocked-test boundaries.

Duplicate detection is basic and local. It compares normalized title, tags, and domain using token overlap. The threshold is configured with `dedup.similarity_threshold`.

Embedding providers are configured as:

- `none`: implemented default; no vectors and no external calls
- `local`: placeholder interface; returns fixed zero vectors and does not load a model
- `api`: placeholder interface; returns fixed zero vectors and does not make network requests

Phase 8-A stores card vectors in SQLite as cache/index data, never in Markdown. The current placeholder providers return zero vectors by default, so normal local behavior still falls back to keyword search unless tests or future real providers supply usable vectors. See [Embedding Providers](docs/embedding-providers.md) for privacy boundaries and cache behavior.

## Roadmap

- Rebuild SQLite index from Markdown
- Replace placeholder embedding providers with real local/API implementations
- Add richer candidate review lifecycle
- Improve deduplication with semantic similarity when embedding support exists
- Add import/export tooling for other agent memory systems
- Harden deployment authentication patterns without turning this into a full auth server
