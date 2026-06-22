# Embedding Providers

MindVault keeps embedding support optional. The default configuration is privacy-first and does not require external services.

## Design Goals

- Privacy first: `none` must work without sending text outside the local process.
- Gradual enhancement: embedding support can be enabled later without changing the card model or Markdown source format.
- Interface first: providers share one small interface so real local or API-backed implementations can replace placeholders later.
- Conservative search behavior: vector ranking is used only when a provider returns usable non-zero vectors.

## Provider Modes

- `none`: the default no-op provider. It returns empty vectors and keeps search on the existing keyword/filter path.
- `local`: local model placeholder. It returns fixed 384-dimension zero vectors and does not download, load, or run a real model.
- `api`: external API placeholder. It returns fixed 1536-dimension zero vectors and does not make network requests.

## Current Implementation Status

- `none` is usable today and is the recommended default.
- `local` is loadable today, but only verifies that the provider interface can be called.
- `api` is loadable today, but only verifies that the provider interface can be called.
- Search can load the configured provider and call `embed_text(query)` when a query is provided.
- Phase 8-A adds a SQLite `card_embeddings` cache table for card vectors.
- When the query vector and cached/generated card vectors are usable non-zero vectors, `search_cards` can rank readable candidates by cosine similarity.
- If vectors are empty, zero, mismatched, or unavailable, search falls back to the existing SQLite keyword and filter logic.
- The current `local` and `api` providers still return zero vectors by default, so real semantic ranking requires a future real provider or test monkeypatching.
- Automated tests use placeholders or monkeypatches and do not make network calls.

## Configuration

Use the public YAML config for committed defaults:

```yaml
embedding:
  provider: "none"
```

For local runtime overrides, use an uncommitted environment file or shell environment:

```powershell
$env:EMBEDDING_PROVIDER = "none"
```

Valid values are `none`, `local`, and `api`. The default must remain `none`.

API-related environment names are reserved for the future:

- `EMBEDDING_API_KEY`
- `EMBEDDING_API_URL`

The current `api` placeholder does not read card data over the network.

## Privacy Boundary

- `none` does not create vectors and does not send text anywhere.
- `local` currently does not load a real model and does not send text anywhere.
- `api` currently does not send text anywhere because it is only a placeholder.
- A future real `api` provider would send query or card text to an external service. Users must opt in explicitly and configure secrets outside the repository.
- Markdown remains the source of truth and does not store vectors. SQLite stores vectors only as a cache/index.
- Semantic ranking embeds only cards the caller is allowed to read.

## Future Work

- Add a real local embedding implementation without changing default behavior.
- Add a real API implementation with explicit opt-in configuration.
- Add vector cache invalidation policies beyond searchable text hashing.
- Add production-grade semantic retrieval controls after real providers exist.
