# AGENTS.md

This repository is a small Flask + MySQL app with a vanilla HTML/CSS/JS frontend.
AI features call an external Ollama server (not managed by docker-compose).

Key entrypoints:
- `app.py` (Flask routes + auth gate)
- `db.py` (raw PyMySQL CRUD + schema init)
- `model_connector.py` (Ollama HTTP client + JSON parsing)
- `pet_model_config.py` (model name + prompts; Traditional Chinese)

Cursor/Copilot rules: none found (`.cursor/rules/`, `.cursorrules`, `.github/copilot-instructions.md`).


## Commands (Build / Run / Test / Lint)

Run full stack (recommended dev flow):
```bash
docker-compose up -d
# App: http://localhost:5001
```

Run locally (DB in Docker, Flask on host):
```bash
cp .env.example .env
docker-compose up -d mysql
poetry install
python app.py
```

Note: `pyproject.toml` requires Python >= 3.14 for local Poetry; `Dockerfile` uses Python 3.11 + pip.

Run unit/integration tests (inside the running web container):
```bash
docker exec pet-adorable-life-web python -m pytest tests/ -v
```

Run a single test (node id):
```bash
docker exec pet-adorable-life-web python -m pytest \
  tests/test_model_connector.py::test_get_model_response_by_image_regex_fallback -v
```

Run a single test file:
```bash
docker exec pet-adorable-life-web python -m pytest tests/test_api_pets.py -v
```

E2E tests (Playwright) require a live server:
```bash
pip install -r requirements-e2e.txt
playwright install chromium
pytest tests/e2e/ --base-url http://localhost:5001 -v
```

Run a single E2E test (node id):
```bash
pytest tests/e2e/test_page_navigation.py::TestHomePage::test_returns_200 \
  --base-url http://localhost:5001 -v
```

Lint/format/typecheck:
- No dedicated linter/formatter/typechecker is configured (no ruff/black/mypy configs).
- If you add lint tooling, keep it minimal and avoid mass reformatting in unrelated PRs.
- Optional sanity check:
```bash
python -m compileall .
```


## Code Style Guidelines

### General
- Prefer small, boring changes that fit existing patterns.
- UI and user-facing text is Traditional Chinese (`zh-Hant`) unless the file already uses English.
- Do not commit secrets; `.env` is local only.

### Python formatting
- 4-space indentation; keep lines readable (aim ~88-100 chars unless a long literal is clearer).
- Use trailing commas in multi-line literals.
- Prefer f-strings for interpolation.
- Avoid clever one-liners; be explicit.

### Imports
Use this order with blank lines between groups:
1) standard library
2) third-party
3) local modules

Within a file, keep import style consistent (don’t churn unrelated imports).

### Naming
- Functions/vars: `snake_case`
- Classes: `CapWords`
- Constants: `UPPER_SNAKE_CASE`
- “Private” helpers: prefix `_` (see `app.py`, `db.py`, `model_connector.py`).

### Types
- Add type hints for new/modified public functions where it improves clarity.
- Use `Optional[...]` and `Dict[str, Any]` pragmatically (see `model_connector.py`).
- Do not introduce heavy typing frameworks without a clear need.

### Error handling
- API routes: return structured JSON errors: `jsonify({"error": "..."}), <status>`.
- Validate inputs early; return 400 for client errors, 404 for missing resources, 401 for auth.
- Avoid blanket `except Exception` unless you also log and return a safe message.
- Prefer `logging` over `print` for non-test code.

### Flask conventions (`app.py`)
- Route handlers should be thin:
  - parse/validate request
  - call DB/model layer
  - normalize output
- Auth: most endpoints require a session `user_id` (see `current_user_id()` and `_require_login()`).
- Keep file upload validation centralized (`_validate_image_file`).

### DB layer (`db.py`)
- Use `get_connection()` context manager for commit/rollback handling.
- Always parameterize SQL (`%s` placeholders); never string-concatenate user input.
- Keep “filter semantics” consistent:
  - `pet_id is None` => all
  - `pet_id == 0` => `IS NULL`
  - `pet_id > 0` => exact match
- Return plain Python dicts/lists; API layer decides HTTP shape.

### Model/Ollama connector (`model_connector.py`)
- Network failures should return `None` (caller maps to a 5xx with a helpful message).
- Parsing failures should not crash the app; log at warning level and return `None`.
- Keep prompts in `pet_model_config.py`, not inline in route handlers.

### Frontend (Jinja templates + inline JS)
- No build step; keep JS small and embedded per page.
- Use `async/await` with `fetch`, handle `res.ok` and show a Traditional Chinese error.
- Escape user-provided strings before inserting into HTML (see `escapeHtml` pattern).
- Keep CSS design tokens in `static/css/style.css` (`:root` variables).


## Testing Guidelines

- Prefer fast unit tests with mocking.
- Use fixtures from `tests/conftest.py`:
  - `client` for anonymous requests
  - `authed_client` for authenticated requests (session `user_id`)
  - `mock_db` to patch `app.db` for route tests
- DB unit tests should mock `db.get_connection()` using helpers like `tests/helpers.py`.
- E2E tests under `tests/e2e/` require a live server and real DB.


## Repo Hygiene

- Avoid adding Windows `*:Zone.Identifier` artifacts; do not rely on them.
- Keep changes scoped; don’t reformat unrelated files.
- If you introduce new dependencies, update both `pyproject.toml` (Poetry) and the Docker image story.
