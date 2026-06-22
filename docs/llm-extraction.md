# LLM Extraction

## Overview

LLM extraction is an **optional** feature that uses an OpenAI-compatible Chat Completions API to transform unstructured text into structured knowledge cards. It is **disabled by default** and falls back to rule-based extraction if unavailable, misconfigured, or when requests fail.

## Current Status

- **Default**: Disabled
- **Fallback**: If the LLM is unavailable, misconfigured, times out, returns invalid JSON, or fails to authenticate, the system automatically falls back to the existing rule-based extractor without raising errors
- **Privacy**: When enabled, the full input text is sent to the configured LLM endpoint; users should understand the privacy implications before enabling this feature

## Configuration

### Environment Variables (Highest Priority)

```bash
# Enable/disable LLM extraction (overrides config.yaml)
LLM_EXTRACTION_ENABLED=false

# OpenAI-compatible API key (required when enabled; do not commit this)
LLM_API_KEY=sk-...

# API endpoint base URL
LLM_BASE_URL=https://api.openai.com/v1

# Model name
LLM_MODEL=gpt-4o-mini

# Request timeout in seconds
LLM_TIMEOUT_SECONDS=15.0
```

### config.yaml

```yaml
extraction:
  llm_enabled: false
  llm_provider: openai
  llm_model: gpt-4o-mini
  llm_base_url: https://api.openai.com/v1
  llm_timeout_seconds: 15.0
```

**Note**: Environment variables override config.yaml values.

`LLM_API_KEY` is read from the environment only. Do not put real API keys in committed config files, docs, tests, or shell history intended for sharing.

## How It Works

1. When `llm_enabled=true` and an API key is present, `ingest_memory` calls the LLM service
2. The service sends the input text and optional metadata to the configured endpoint
3. The LLM responds with structured JSON fields: title, problem, context, insight, solution, tags, domain, confidence
4. The system validates and normalizes the LLM output (clamps confidence to 0-1, validates tags as list[str], truncates long titles, etc.)
5. Metadata-provided values (tags, domain, confidence, source_agent) override LLM outputs
6. If the LLM call fails, times out, returns non-JSON, or is disabled, the system falls back to rule-based extraction

## Privacy Considerations

- **Default OFF**: LLM extraction is disabled by default to avoid unintended data transmission
- **Full text transmitted**: When enabled, the complete input text is sent to the configured LLM endpoint
- **Local fallback**: If LLM extraction is disabled or fails, all processing happens locally using rule-based extraction
- **No LLM in tests**: All automated tests mock LLM calls and never make real network requests

## Failure Modes & Fallback

The following conditions trigger automatic fallback to rule-based extraction:

- LLM extraction is disabled in config
- No API key is provided
- Network timeout (default 15 seconds)
- HTTP errors or connection failures
- Response body is not valid JSON
- Response does not contain expected `choices[0].message.content` structure
- LLM content is not valid JSON
- Any other exception during LLM call

Fallback is silent and does not raise errors; the system continues using rule-based extraction.

## OpenAI-Compatible API Requirement

The implementation uses standard OpenAI Chat Completions format:

```
POST {llm_base_url}/chat/completions
Authorization: Bearer {api_key}
Content-Type: application/json

{
  "model": "{llm_model}",
  "temperature": 0,
  "messages": [
    {"role": "system", "content": "...extraction instructions..."},
    {"role": "user", "content": "{input_text}"}
  ]
}
```

The configured service must expose an OpenAI-compatible Chat Completions endpoint at `{llm_base_url}/chat/completions`. Phase 7 does not include provider-specific adapters or claim support for non-compatible local LLM APIs.

## Testing

All LLM extraction tests use mocked network calls. No real API requests are made during test runs. Tests verify:

- Disabled state returns None
- Enabled state with API key calls the endpoint
- Successful responses are parsed and normalized
- Failures trigger fallback to rule-based extraction
- Metadata overrides take precedence
- Runtime selects the correct extractor based on config
- `ingest_memory` integration uses LLM when enabled

## Future Enhancements

Planned but not yet implemented:

- Retry logic with exponential backoff
- Prompt customization per domain
- Multiple LLM provider profiles
- Cost tracking and rate limiting
- LLM-based semantic deduplication
