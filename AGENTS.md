# AGENTS.md

This repository is a small Flask + MySQL app with a vanilla HTML/CSS/JS frontend.
AI features call an external Ollama server; it is not managed by `docker-compose`.

## Project Map
- `app.py`, `db.py`, `model_connector.py`, `pet_model_config.py`
- `templates/` for Jinja pages, `static/css/` for styles, `tests/` for pytest + Playwright

## Rule Files
- Checked for Cursor rules in `.cursor/rules/` and `.cursorrules`.
- Checked for Copilot instructions in `.github/copilot-instructions.md`.
- In this checkout, none of those repo-level rule files are present.
- Follow this `AGENTS.md` as the authoritative repo guidance.

## Commands (Build / Run / Test / Lint)

### Recommended dev flow
```bash
docker-compose up -d
# App: http://localhost:5001
```

`docker-compose.yml` defines:
- `mysql` on port `3306`
- `web` on port `5001`

### Local Flask app with MySQL in Docker
```bash
cp .env.example .env
docker-compose up -d mysql
poetry install
python app.py
```

Notes:
- `pyproject.toml` requires Python `>=3.13` for local Poetry installs.
- `Dockerfile` uses Python 3.11, so local and container Python versions differ.
- The app requires `SECRET_KEY` outside debug mode.

### Unit/integration tests
```bash
docker exec pet-adorable-life-web python -m pytest tests/ -v
```

```bash
docker exec pet-adorable-life-web python -m pytest \
  tests/test_model_connector.py::test_get_model_response_by_image_regex_fallback -v
```

```bash
docker exec pet-adorable-life-web python -m pytest tests/test_api_pets.py -v
```

Pytest config notes:
- `testpaths = ["tests"]`
- E2E tests live under `tests/e2e/`
- Exclude E2E explicitly with:
```bash
docker exec pet-adorable-life-web python -m pytest tests/ --ignore=tests/e2e -v
```

### E2E tests (Playwright)
```bash
pip install -r requirements-e2e.txt
playwright install chromium
pytest tests/e2e/ --base-url http://localhost:5001 -v
```

```bash
pytest tests/e2e/test_page_navigation.py::TestHomePage::test_returns_200 \
  --base-url http://localhost:5001 -v
```

### Lint / format / type-check
There is no dedicated linter, formatter, or type-checker configured in this repo.
Do not introduce broad reformatting just because tooling is absent.

```bash
python -m compileall .
```

## Code Style Guidelines

### General
- Prefer small, boring changes that match existing patterns.
- Keep scope tight; do not refactor unrelated code.
- UI and user-facing copy is generally Traditional Chinese (`zh-Hant`).
- Do not commit secrets; `.env` is local-only.

### Python formatting
- Use 4-space indentation.
- Keep lines readable; avoid unnecessary cleverness.
- Use trailing commas in multi-line literals when already in that style.
- Prefer explicit code over dense one-liners.
- Prefer f-strings for interpolation.

### Imports
Use this order with a blank line between groups: standard library, third-party, local modules.
Examples are in `app.py` and `model_connector.py`.

### Naming
- Functions and variables: `snake_case`
- Classes: `CapWords`
- Constants: `UPPER_SNAKE_CASE`
- Private helpers/constants: leading underscore, e.g. `_validate_csrf_token`

### Types
- Add type hints on new or modified public functions when they improve clarity.
- This repo already uses pragmatic typing such as `Optional[...]`, `Dict[str, Any]`, and unions.
- Do not add heavy typing frameworks.

### Error handling
- API routes should return structured JSON errors: `jsonify({"error": "..."}), <status>`.
- Use `400` for invalid client input, `401` for auth issues, `404` for missing resources.
- Reserve `500` for actual server-side failures.
- Validate inputs early and return fast.
- Prefer `logging` over `print` in application code.
- Avoid broad `except Exception` unless you also log or convert it into a safe response.

## Flask Conventions (`app.py`)
- Keep route handlers thin: parse/validate input, call DB/model helpers, normalize response.
- Most routes require a logged-in session `user_id`; login enforcement is centralized in `@app.before_request`.
- API endpoints return JSON; page routes render templates or redirect.
- Keep `_no_cache_response(...)`, CSRF helpers, and `_validate_image_file` as centralized shared helpers.

## Database Conventions (`db.py`)
- Use `get_connection()` for commit/rollback/close behavior.
- Always parameterize SQL with `%s`; never string-concatenate user input.
- Return plain Python dicts/lists from the DB layer; let Flask routes shape HTTP responses.
- Keep schema setup logic in helper functions called by `init_db()`.
- Preserve pet filter semantics: `pet_id is None` => all, `pet_id == 0` => `IS NULL`, `pet_id > 0` => exact match.

## Ollama / Model Connector Conventions (`model_connector.py`)
- Keep prompts in `pet_model_config.py`, not inline in route handlers.
- Network/parsing failures should return `None`; callers map that to HTTP responses.
- Preserve retry-based requests, structured JSON parsing, and support for path/bytes/file-like image inputs.

## Frontend Conventions (`templates/` + `static/css/`)
- There is no frontend build step.
- Keep JavaScript small and page-local; inline script tags are normal here.
- Use `fetch` with `async/await`, always check `res.ok`, and show errors in Traditional Chinese.
- Escape user-provided strings before injecting HTML; follow the `escapeHtml` pattern in `templates/pets.html`.
- Base layout lives in `templates/base.html`; shared visual tokens live in `static/css/style.css` under `:root`.

## Testing Guidelines
- Prefer fast unit tests with mocks.
- Use fixtures from `tests/conftest.py`: `client`, `authed_client`, and `mock_db`.
- For route tests, patch DB/model dependencies instead of using a real database.
- For DB unit tests, mock `db.get_connection()` and cursor behavior.
- E2E tests require a live app and should stay separate from the normal fast suite.

## Change Scope / Hygiene
- Avoid mass formatting changes.
- Avoid renaming files or endpoints unless required.
- Keep new dependencies rare and justified.
- If you add a dependency, update the relevant install story (`pyproject.toml`, Docker setup, and docs if needed).
- Avoid committing generated junk such as Windows `*:Zone.Identifier` artifacts.

## Good Reference Files
- `app.py`, `db.py`, `model_connector.py`
- `templates/pets.html`, `templates/base.html`
- `tests/conftest.py`, `tests/test_api_pets.py`
