# MCP Endpoint

## Purpose

`mindvault-mcp` exposes MCP tools for agent memory workflows. It turns raw conversation text into structured Markdown-backed knowledge cards and keeps a SQLite index for lookup and verification queue records.

The service is intended for local or self-hosted agent integrations. It does not include a Web UI.

## Transport

The current server entrypoint uses FastMCP.

Default `config.yaml`:

```yaml
server:
  host: "127.0.0.1"
  port: 8000
  transport: "sse"
```

Supported transport values are delegated to FastMCP. The documented local default for this project is `sse`.

## Endpoint Convention

The server is created by `mindvault_mcp.server:create_app` and run by the `mindvault-mcp` console script.

With the default FastMCP SSE settings used by this project:

- SSE endpoint: `/sse`
- SSE message endpoint: `/messages`
- Streamable HTTP endpoint if using FastMCP HTTP transport directly: `/mcp`

The default local base URL is:

```text
http://127.0.0.1:8000
```

So the default SSE endpoint is:

```text
http://127.0.0.1:8000/sse
```

Do not assume these paths are custom application routes. They come from FastMCP defaults unless explicitly changed in code or FastMCP configuration.

## Authentication Model

Each MCP tool accepts a `token` argument. The server maps that token to an agent from `config.yaml`:

```yaml
auth:
  agents:
    - token: "dev-admin-token"
      agent_id: "admin-agent"
      trust_level: 10
      allowed_libraries: ["primary", "staging"]
```

The authenticated agent has:

- `agent_id`
- `trust_level`
- `allowed_libraries`

This is an MVP permission model, not a production authentication center.

## Data Access Boundaries

Cards live in one of two libraries:

- `staging`: candidate and rejected cards
- `primary`: approved active cards

Reads require:

- the agent has access to the card library
- `agent.trust_level >= card.privacy_level`

Writes require:

- staging writes: trust level `>= 3`
- primary writes and approve: trust level `>= 8`

Markdown files are the card source of truth. SQLite stores indexes and verification queue records.

## Local Development Connection

Install and run:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
mindvault-mcp
```

Use a custom config file:

```powershell
$env:MINDVAULT_CONFIG = "config.yaml"
mindvault-mcp
```

MCP clients should connect to the configured host, port, and transport. For the default local SSE setup, use:

```text
http://127.0.0.1:8000/sse
```

Tool calls must include a configured token.

## Not Implemented

The following are intentionally not implemented in this release:

- networked verification
- embedding-backed semantic retrieval
- LLM extraction
- production-grade authentication or OAuth
- Web UI
