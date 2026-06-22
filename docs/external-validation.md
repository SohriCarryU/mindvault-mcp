# External Validation Protocol

Phase 6-B adds a minimal URL link validator behind the external validation protocol. It is disabled by default and does not invoke LLMs, inspect page content, or verify factual correctness.

## Current Scope

- Defines validation statuses and result records.
- Provides a service-layer entrypoint for creating validation jobs and validating one or more cards.
- Reuses the existing verification queue item shape for queued jobs.
- Keeps external validation disabled by default.
- Validates only `http://` and `https://` URL sources when explicitly enabled.
- Returns `skipped` when validation is disabled, when a source reference is missing, or when the source is not a supported URL.

No MCP tool is exposed for this protocol in Phase 6-B. Existing `queue_verification` behavior remains unchanged.

## Configuration

Committed defaults should stay disabled:

```yaml
verification:
  backend_mode: "none"
  external_validation_enabled: false
  external_validation_timeout_seconds: 5.0
```

For local experiments, use an uncommitted environment override:

```powershell
$env:EXTERNAL_VALIDATION_ENABLED = "true"
$env:EXTERNAL_VALIDATION_TIMEOUT_SECONDS = "5.0"
```

Supported truthy values are `1`, `true`, `yes`, and `on`. Any unset value falls back to `config.yaml`. Invalid timeout overrides are ignored and fall back to the configured value.

## Status Model

- `pending`: a validation job is waiting to run.
- `passed`: validation succeeded.
- `failed`: validation found the card to be incorrect.
- `stale`: validation found the card may be outdated or needs review.
- `skipped`: validation did not run because it is disabled, lacks a source, or has no implemented backend.
- `error`: validation attempted to run and hit an operational error.

With URL validation enabled, Phase 6-B maps HTTP results as follows:

- `200` through `399`: `passed`
- `410`: `stale`
- other `400` through `499`: `failed`
- `500` through `599`, timeout, `URLError`, or other network exceptions: `error`

When validation is disabled, queued jobs are marked `skipped` instead of `pending`.

## Result Shape

Each validation result contains:

- `card_id`
- `status`
- `checked_at`
- `source_type`
- `source_ref`
- `message`
- `evidence`, optional
- `error`, optional

## Privacy Boundary

- Default configuration does not validate externally.
- Phase 6-B uses only Python standard library `urllib.request`.
- Enabling `EXTERNAL_VALIDATION_ENABLED=true` may send an HTTP `HEAD` request to `source_ref` when it is an `http://` or `https://` URL.
- If `HEAD` returns `405` or `501`, the validator falls back to `GET` but does not read or store the response body.
- Evidence stores only low-sensitivity metadata: method, status code, and final URL.
- The validator does not send card text to the URL endpoint.
- Future validators that send query text or card text to external systems must remain explicit opt-in configuration.

## Future Work

- Persist validation result history if needed.
- Map real validation outcomes onto card `verification_status` conservatively.
- Decide whether to expose a dedicated MCP tool after the service behavior is stable.
- Add source-specific validators beyond simple URL reachability.
