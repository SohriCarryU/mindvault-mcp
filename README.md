# mindvault-mcp

`mindvault-mcp` is a privacy-first MCP server for agents that need to turn messy multi-turn conversations into structured, durable knowledge cards.

The project is aimed at Hermes, OpenClaw, and other non-programming agent workflows. It has no Web UI. Markdown files are the source of truth, while SQLite provides a small query index.

## Current Phase

This repository currently implements the phase 1 MVP skeleton:

- Python 3.11 package structure
- HTTP/SSE MCP server entrypoint using FastMCP
- YAML configuration plus `.env.example`
- Pydantic domain models for cards and agents
- Markdown card storage with frontmatter
- SQLite index for basic card lookup and filtering
- Dual libraries: `primary` and `staging`
- Minimal token-to-agent permission checks
- Eight MCP tools with runnable basic behavior
- Basic pytest coverage

Out of scope for this phase:

- Web UI
- External search APIs
- Real embedding models
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

## Configuration

Public configuration lives in `config.yaml`.

Important sections:

- `server`: host, port, and transport
- `storage`: Markdown library paths and SQLite database path
- `auth`: token-to-agent mapping
- `extraction`: `conservative`, `balanced`, or `aggressive`
- `embedding`: `none`, `local`, or `api`
- `defaults`: default ingest library and privacy level
- `verification`: placeholder backend mode
- `logging`: log level

`.env.example` only lists environment variable names. Do not commit real tokens or secrets.

The example config includes:

- `dev-admin-token`: high-trust admin with access to `primary` and `staging`
- `dev-trusted-token`: trusted agent with access to `staging`

## Data Layout

Markdown is the durable source of truth:

```text
data/
  primary/
    *.md
  staging/
    *.md
```

Each card is saved as a Markdown file with YAML frontmatter. The body renders the same card as readable sections: problem, context, insight, and solution.

SQLite is an index only:

```text
data/mindvault.sqlite
```

If the index is deleted, future versions should be able to rebuild it from Markdown. Phase 1 focuses on write-through synchronization.

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

Creates a candidate card from raw text and metadata. The default target is `staging`.

### `search_cards`

Searches by keyword, tags, domain, library, status, and verification status. Results are grouped by library, with `primary` searched first.

### `list_candidates`

Lists pending candidate cards in `staging`.

### `approve_card`

Promotes a card from `staging` to `primary` and marks it `active`.

### `reject_card`

Marks a staging candidate as `rejected` and retains the Markdown record.

### `get_card`

Returns one card after library and privacy checks.

### `update_card`

Updates editable fields, then writes both Markdown and SQLite index state.

### `queue_verification`

Marks a card as `pending_verification` and returns a queue placeholder. No network verification is run in phase 1.

## Extraction and Embeddings

Phase 1 extraction is a replaceable rule-based implementation:

- Title comes from the first sentence.
- Card fields are filled conservatively from the input text.
- `extraction.mode` changes how much text is copied into fields.

Embedding providers are configured as:

- `none`: implemented default
- `local`: reserved interface
- `api`: reserved interface

The project does not pretend to run vector search in this phase.

## Roadmap

- Rebuild SQLite index from Markdown
- Add real embedding providers behind the existing provider setting
- Add validation and verification backends
- Add richer candidate review lifecycle
- Add deduplication beyond the current placeholder
- Add import/export tooling for other agent memory systems
- Harden deployment authentication patterns without turning this into a full auth server
