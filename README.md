# mindvault-mcp

`mindvault-mcp` is a privacy-first MCP server for agents that need to turn messy multi-turn conversations into structured, durable knowledge cards.

The project is aimed at Hermes, OpenClaw, and other non-programming agent workflows. It has no Web UI. Markdown files are the source of truth, while SQLite provides query indexes and the verification queue.

## Current Phase

This repository is in phase 3 stabilization around the phase 2 MVP:

- Python 3.11 package structure
- HTTP/SSE MCP server entrypoint using FastMCP
- YAML configuration plus `.env.example`
- Pydantic domain models for cards, agents, and verification queue items
- Markdown card storage with frontmatter
- SQLite index for card lookup, filtering, sorting, and verification queue persistence
- Dual libraries: `primary` and `staging`
- Token-to-agent permission checks with library and privacy-level enforcement
- Rule-based memory extraction with `conservative`, `balanced`, and `aggressive` modes
- Staging-to-primary review flow with approve/reject behavior
- Persistent verification queue placeholder with expiration status handling
- Basic duplicate detection using normalized title, tags, and domain similarity
- Eight MCP tools with runnable behavior
- Pytest coverage for core storage, tools, extraction, verification queue, search, and deduplication

Out of scope for the current release:

- Web UI
- External search APIs
- Networked verification
- LLM extraction
- Real embedding or vector search providers
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
- `extraction`: `conservative`, `balanced`, or `aggressive`
- `embedding`: `none`, `local`, or `api`; only `none` is implemented
- `defaults`: default ingest library and privacy level
- `verification`: verification backend mode placeholder
- `dedup`: duplicate detection similarity threshold
- `logging`: log level

`.env.example` only lists environment variable names. The current application reads `MINDVAULT_CONFIG`; token values are configured in the selected YAML file for this MVP.

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

SQLite stores query indexes and verification queue records:

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

Creates a card from raw text using the rule-based extractor. The default target is `staging`. If a similar staging card is found, `possible_duplicate_of` is set, but the new card is still retained for review.

### `search_cards`

Inputs: `token`, optional `query`, `tags`, `domain`, `library`, `status`, `verification_status`, `limit`, and `offset`.

Searches by keyword and filters. Results are grouped by library, with `primary` searched before `staging`. Ranking is deterministic: library priority, confidence, updated time, then card id. Results are permission-filtered.

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

Marks a card as `pending_verification` and persists a pending queue record in SQLite. No network verification is run in this release.

## Extraction, Deduplication, and Embeddings

Extraction is currently rule-based and replaceable:

- `conservative`: leaves uncertain fields blank and lowers confidence.
- `balanced`: fills reasonable fields from labels and sentence structure.
- `aggressive`: tries to fill all core fields.

Duplicate detection is basic and local. It compares normalized title, tags, and domain using token overlap. The threshold is configured with `dedup.similarity_threshold`.

Embedding providers are configured as:

- `none`: implemented default
- `local`: reserved interface
- `api`: reserved interface

The project does not run vector search in this release.

## Roadmap

- Rebuild SQLite index from Markdown
- Add real embedding providers behind the existing provider setting
- Add networked validation and verification backends
- Add richer candidate review lifecycle
- Improve deduplication with semantic similarity when embedding support exists
- Add import/export tooling for other agent memory systems
- Harden deployment authentication patterns without turning this into a full auth server
