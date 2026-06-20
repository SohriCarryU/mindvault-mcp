# Hermes / OpenClaw MCP Client Configuration

This document shows how to point an external agent client at a local `mindvault-mcp` server.

The exact config keys vary by client. Treat the examples below as shape guidance and adapt the field names to the client you use.

## Server Endpoints

Start the server locally:

```powershell
mindvault-mcp
```

This project uses FastMCP. The relevant default paths are:

- StreamableHTTP endpoint: `http://127.0.0.1:8000/mcp`
- SSE endpoint: `http://127.0.0.1:8000/sse`
- SSE message endpoint: `http://127.0.0.1:8000/messages`

Hermes native `mcp_servers` uses HTTP/StreamableHTTP-style MCP transport. For Hermes, prefer the `/mcp` endpoint.

The repository's `docs/sse-smoke-client.py` is different: it uses FastMCP's SSE client path and should point at `/sse`.

## Hermes Native MCP Example

Hermes configuration lives in `~/.hermes/config.yaml` under the top-level `mcp_servers` key.

Remote HTTP-style MCP servers use `url`. Do not add `transport` or manually list `tools`; Hermes connects at startup, discovers tools automatically, and registers them as `mcp_<server_name>_<tool_name>`.

```yaml
mcp_servers:
  mindvault:
    url: http://127.0.0.1:8000/mcp
    # Optional transport-level headers only. mindvault-mcp does not read
    # Authorization headers for tool permissions in the current release.
    # headers:
    #   Authorization: Bearer local-dev-token
    # Optional timeouts, in seconds.
    # timeout: 30
    # connect_timeout: 10
```

With the server name above, Hermes-discovered tools are expected to appear with names like:

```text
mcp_mindvault_list_candidates
mcp_mindvault_search_cards
mcp_mindvault_ingest_memory
```

## OpenClaw-Style Clients

OpenClaw-compatible clients vary in their MCP configuration schema. Do not assume the Hermes YAML above is accepted unchanged.

Use the client documentation for its HTTP or StreamableHTTP MCP server configuration and adapt these facts:

- StreamableHTTP endpoint: `http://127.0.0.1:8000/mcp`
- SSE endpoint: `http://127.0.0.1:8000/sse`
- SSE message endpoint: `http://127.0.0.1:8000/messages`
- Tool permissions require a `token` tool argument.

If a client only supports SSE, use `/sse`. If it supports StreamableHTTP, prefer `/mcp`.

## Token Passing

`mindvault-mcp` does not currently use HTTP Authorization headers or OAuth.

Every tool call must pass `token` as a tool argument:

```json
{
  "token": "dev-trusted-token"
}
```

For example, a `list_candidates` tool call uses:

```json
{
  "token": "dev-trusted-token",
  "limit": 20,
  "offset": 0
}
```

Hermes native `mcp_servers` does not provide default tool-argument injection. That means the caller must include `token` in each tool call or use a client-side wrapper that adds it.

Transport `headers` can be useful for clients or proxies that require HTTP-layer auth, but this service's current permission model does not read HTTP `Authorization` headers.

## Permission Notes

The default development config includes:

- `dev-admin-token`: high-trust admin, allowed `primary` and `staging`
- `dev-trusted-token`: trusted staging agent, allowed `staging`

Approval and primary writes require higher trust. Staging reads and writes are suitable for the trusted development token.

Do not commit real tokens. Use an uncommitted local config for private deployments.
