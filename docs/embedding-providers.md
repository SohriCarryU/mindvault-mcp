# Embedding Providers

MindVault keeps embedding support optional. The default configuration is privacy-first and does not require external services.

## Design Goals

- Privacy first: `none` must work without sending text outside the local process.
- Gradual enhancement: embedding support can be enabled later without changing the card model or Markdown source format.
- Interface first: providers share one small interface so local or API-backed implementations can be selected without changing search tool inputs.
- Conservative search behavior: vector ranking is used only when a provider returns usable non-zero vectors.

## Provider Modes

- `none`: the default no-op provider. It returns empty vectors and keeps search on the existing keyword/filter path.
- `local`: local `sentence-transformers` provider. It loads the configured model on this machine and never sends text to an embedding API.
- `api`: OpenAI-compatible embeddings API provider. It calls the configured endpoint only when provider, key, base URL, and model are explicitly configured.

## Current Implementation Status

- `none` is usable today and is the recommended default.
- `local` can load a `sentence-transformers` model such as `sentence-transformers/all-MiniLM-L6-v2`. First use may download the model into the normal Hugging Face cache.
- `api` can call OpenAI, Azure OpenAI, or compatible embeddings endpoints through standard-library `urllib`.
- Search can load the configured provider and call `embed_text(query)` when a query is provided.
- Phase 8-A adds a SQLite `card_embeddings` cache table for card vectors.
- Phase 8-C1 records a model fingerprint with each cached vector so provider, model, or dimension changes do not reuse stale vectors.
- When the query vector and cached/generated card vectors are usable non-zero vectors, `search_cards` can rank readable candidates by cosine similarity.
- If vectors are empty, zero, mismatched, or unavailable, search falls back to the existing SQLite keyword and filter logic.
- Automated tests use monkeypatches and do not make real network calls or download real models.

## Configuration

Use the public YAML config for committed defaults:

```yaml
embedding:
  provider: "none"
  local_model_path: "sentence-transformers/all-MiniLM-L6-v2"
  api_base_url: ""
  api_model: ""
  api_timeout: 10.0
```

For local runtime overrides, use an uncommitted environment file or shell environment:

```powershell
$env:EMBEDDING_PROVIDER = "none"
```

Valid values are `none`, `local`, and `api`. The default must remain `none`.

Local provider:

- Install the optional runtime dependency before using `local`: `pip install sentence-transformers`.
- Configure `EMBEDDING_LOCAL_MODEL_PATH` or `embedding.local_model_path`; the default is `sentence-transformers/all-MiniLM-L6-v2`.
- The default model produces 384-dimension vectors.
- Model files are managed by `sentence-transformers` and Hugging Face, typically under `~/.cache/huggingface/`.

API provider:

- `EMBEDDING_API_KEY`
- `EMBEDDING_API_BASE_URL`
- `EMBEDDING_API_MODEL`
- `EMBEDDING_API_TIMEOUT`

`EMBEDDING_API_BASE_URL` can be a version root such as `https://example.com/v1` or a full embeddings endpoint such as `https://example.com/v1/embeddings`. If it does not end in `/embeddings`, the provider appends that suffix. API keys must stay in environment variables or uncommitted local configuration.

## Cache Invalidation

Card vectors are cached in SQLite with the searchable text hash and a model fingerprint.

Fingerprint format:

```text
{provider}:{model_id}:dim{dimension}
```

Examples:

- `local:sentence-transformers/all-MiniLM-L6-v2:dim384`
- `api:text-embedding-3-small:dim1536`
- `none::dim0`

When the configured provider, model identifier, or actual vector dimension changes, MindVault treats the cached row as stale and re-embeds the card before ranking. Existing cache rows created before fingerprints are treated as stale because their fingerprint is empty. The cache remains SQLite-only index data; Markdown cards are not modified by vector cache refreshes.

## Privacy Boundary

- `none` does not create vectors and does not send text anywhere.
- `local` runs on the local machine. It may download model files on first use, but card text is embedded locally.
- `api` sends query text and readable card searchable text to the configured embeddings endpoint. Users must explicitly opt in and trust that endpoint.
- API keys are not stored in Markdown or SQLite and must not be committed.
- Markdown remains the source of truth and does not store vectors. SQLite stores vectors only as a cache/index.
- Semantic ranking embeds only cards the caller is allowed to read.

## Future Work

- Add production-grade semantic retrieval controls after real providers exist.
