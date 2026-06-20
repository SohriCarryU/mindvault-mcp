# Contributing

Thanks for helping improve `mindvault-mcp`.

## Local Setup

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
```

## Development Rules

- Keep Markdown as the card source of truth.
- Keep SQLite as an index and queue store, not the only card store.
- Do not commit `.env`, real tokens, generated databases, cache folders, or local card data.
- Do not add third-party dependencies without a clear reason.
- Prefer small, focused changes with tests.
- Do not present placeholder capabilities as implemented.

## Tests

Run the full suite before opening a pull request:

```powershell
pytest
```

For new behavior, add or update tests first when practical.
