# External Validation Protocol

Phase 6-A adds the protocol skeleton for future external validation. It does not call the network, fetch URLs, invoke LLMs, or verify facts against external sources.

## Current Scope

- Defines validation statuses and result records.
- Provides a service-layer entrypoint for creating validation jobs and validating one or more cards.
- Reuses the existing verification queue item shape for queued jobs.
- Keeps external validation disabled by default.
- Returns `skipped` when validation is disabled, when a source reference is missing, or when the future validator is not implemented yet.

No MCP tool is exposed for this protocol in Phase 6-A. Existing `queue_verification` behavior remains unchanged.

## Configuration

Committed defaults should stay disabled:

```yaml
verification:
  backend_mode: "none"
  external_validation_enabled: false
```

For local experiments, use an uncommitted environment override:

```powershell
$env:EXTERNAL_VALIDATION_ENABLED = "true"
```

Supported truthy values are `1`, `true`, `yes`, and `on`. Any unset value falls back to `config.yaml`.

## Status Model

- `pending`: a validation job is waiting to run.
- `passed`: validation succeeded.
- `failed`: validation found the card to be incorrect.
- `stale`: validation found the card may be outdated or needs review.
- `skipped`: validation did not run because it is disabled, lacks a source, or has no implemented backend.
- `error`: validation attempted to run and hit an operational error.

Phase 6-A only returns `pending` for queued jobs and `skipped` for validation attempts.

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
- The Phase 6-A service does not import HTTP clients and does not perform network requests.
- Enabling `EXTERNAL_VALIDATION_ENABLED=true` only reaches the no-op protocol entrypoint today.
- Future real validators may send `source_ref`, query text, or card text to external systems; that must remain explicit opt-in configuration.

## Future Phase 6-B Work

- Add a real link/source validator behind the same service interface.
- Persist validation result history if needed.
- Map real validation outcomes onto card `verification_status` conservatively.
- Decide whether to expose a dedicated MCP tool after the service behavior is stable.
