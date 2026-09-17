# Repository Guidelines

## Project Structure & Module Organization
- `chat_client.py` and `oral_cavity_client.py` hold HTTP clients for chat completion API demos using `requests`.
- `chat_request.py` exposes a one-off request helper for local manual testing.
- `extract_docx.py` contains DOCX parsing utilities; update hard-coded doc path before reuse.
- `venv/` stores an optional virtual environment; recreate locally rather than committing changes.

## Build, Test, and Development Commands
- `python -m venv venv` creates a fresh environment; activate with `source venv/bin/activate`.
- `pip install -r requirements.txt` once available; for now install `requests` and `python-docx` manually.
- `python chat_client.py` runs the default chat demo against `http://127.0.0.1:8000`.
- `python chat_request.py` triggers a minimal mouth-cavity request flow.
- `python oral_cavity_client.py` exercises the alternate API key scenario.

## Coding Style & Naming Conventions
- Follow PEP 8 with 4-space indentation, snake_case functions, and CapWords classes (`ChatClient`, `CavityClient`).
- Keep modules single-purpose scripts; extract shared helpers into new modules under `clients/` if the codebase grows.
- Prefer explicit type hints on public functions; use module-level constants for API URLs and keys.
- Include docstrings for modules and public callables; keep inline comments for non-obvious behavior only.

## Testing Guidelines
- Add Python tests under `tests/` mirroring module hierarchy (e.g., `tests/test_chat_client.py`).
- Use `pytest` for new coverage; call `pytest` locally before pushing.
- Stub HTTP calls with `responses` or `requests-mock` to avoid hitting real endpoints.
- Target at least smoke coverage of each request helper and any parsing utilities.

## Commit & Pull Request Guidelines
- Write imperative, present-tense commit subjects ≤50 chars (e.g., `Add streaming support toggle`); include body wrapping at 72 chars when context helps.
- Group logical changes per commit; avoid bundling environment files.
- PRs should describe motivation, summarize testing, and reference issue IDs when relevant.
- Attach terminal output snippets or screenshots if behavior changes; flag new secrets for rotation.
