---
name: pet-adorable-life-patterns
description: This skill should be used when making changes in the pet-adorable-life repo, especially when adding Flask routes, modifying db.py CRUD/schema, changing Ollama model integration, editing Jinja templates/static CSS, or writing pytest/Playwright tests.
version: 1.0.0
source: local-git-analysis
analyzed_commits: 41
---

# Pet Adorable Life Patterns

This repository is a small Flask + MySQL app with a vanilla HTML/CSS/JS frontend and an external Ollama server.

Use these patterns to keep changes consistent with the existing codebase.

## Repo Map (Where Things Live)

- Flask routes + auth gate: `app.py`
- MySQL access + schema init + CRUD: `db.py`
- Ollama HTTP client + JSON parsing: `model_connector.py`
- Model name + prompts (Traditional Chinese): `pet_model_config.py`
- Templates (Jinja + inline JS): `templates/`
- CSS (design tokens live here): `static/css/style.css`
- Unit/integration tests (pytest): `tests/`
- E2E tests (pytest-playwright): `tests/e2e/`
- Dev + ops docs: `CLAUDE.md`, `AGENTS.md`, `docs/CONTRIBUTING.md`, `docs/RUNBOOK.md`

## Commit Conventions (Observed)

Observed prefixes in recent history:
- Common: `feat:`, `test:`, `docs:`, `refactor:`, `fix:`, `chore:`
- Also present: merge commits without a prefix.

Guidance:
- Prefer a short conventional prefix when possible (e.g., `feat:` / `fix:` / `test:` / `docs:` / `refactor:` / `chore:`).
- Keep the subject focused on intent (why) and user impact, not just a file list.
- If a change affects both backend and templates, it is normal here for them to move together (frequent co-changes include `app.py` + `templates/*.html`, and `static/css/style.css` + templates).

## Architecture & Boundaries

### Route layer stays thin (`app.py`)

Route handlers should:
- Parse/validate input early (e.g., `request.get_json() or {}`; required field checks).
- Enforce auth via the existing session gate.
- Call DB/model layer functions; do not embed SQL or prompts in handlers.
- Return structured JSON errors for API routes.

Key anchors:
- Login enforcement: `_require_login()` + `_EXEMPT_ENDPOINTS` + `current_user_id()` in `app.py`.
- File upload validation is centralized: `_validate_image_file()` + `_ALLOWED_IMAGE_EXTS` in `app.py`.

### DB layer owns SQL and schema (`db.py`)

Patterns:
- Use `get_connection()` context manager for commit/rollback/close.
- Always parameterize SQL using `%s` placeholders.
- Keep list filter semantics consistent for `pet_id`:
  - `pet_id is None` -> all
  - `pet_id == 0` -> `IS NULL` (unassigned)
  - `pet_id > 0` -> exact match
- Support user scoping via `user_id` parameters in read/write paths.

Schema patterns:
- `init_db()` creates tables and uses guarded `ALTER TABLE` (see `_guard_alter`) for backward-compatible evolution.

### Model/Ollama integration is isolated (`model_connector.py`)

Patterns:
- Network failures should not crash the app: return `None` and let the caller map to a 5xx with a helpful message.
- Parsing failures should not crash the app: log and return `None`.
- Image analysis endpoints use base64-encoded images and expect the model to return JSON (with a regex fallback for sloppy outputs).
- Prompts live in `pet_model_config.py` and should not be inlined into route handlers.

Key anchors:
- `_call_model_with_retry()` wraps `requests.post(...)` with Tenacity retries.
- `_parse_model_response()` parses the outer response and optionally JSON-decodes the inner `response` field.
- `_extract_json_by_regex()` provides a fallback extraction.

## Frontend Patterns (Templates + Inline JS)

Patterns:
- No frontend build step: keep JS small and embedded per page.
- Prefer `async/await` with `fetch`; check `res.ok` and show a Traditional Chinese error.
- Avoid XSS: escape user-provided strings before inserting into HTML. (The pets UI work in this repo introduces an `escapeHtml` pattern.)
- CSS design tokens live in `static/css/style.css` (`:root` variables); avoid scattering new hardcoded colors across templates.

## Auth & User Scoping

Patterns:
- Most endpoints require a session `user_id`; exemptions are limited to login/register/logout/static.
- In API handlers, obtain scope via `current_user_id()` and pass `user_id=` into DB functions.
- Tests commonly simulate auth by setting `session['user_id']`.

## Environment & Dev Workflow

### Docker compose (recommended)

From repo root:
```bash
docker-compose up -d
# App: http://localhost:5001
```

### Local Flask (DB in Docker)

```bash
cp .env.example .env
docker-compose up -d mysql
poetry install
python app.py
```

Notes:
- Docker image uses Python 3.11 + pip; local Poetry requires Python >= 3.13 (see `pyproject.toml` and `Dockerfile`).
- Ollama is external to compose; configure with `OLLAMA_URL`.
- Use `SECRET_KEY` in production; the repo includes a dev default.

## Testing Patterns

### Unit/integration (pytest)

Run inside the web container:
```bash
docker exec pet-adorable-life-web python -m pytest tests/ -v
```

Fixtures:
- `tests/conftest.py`:
  - `client`: Flask test client
  - `authed_client`: client with `user_id` set in session
  - `mock_db`: patches `app.db` so API tests do not hit a real DB

DB unit tests:
- Mock `db.get_connection()` using helpers in `tests/helpers.py`.

### E2E (pytest-playwright)

E2E requires a live server:
```bash
pip install -r requirements-e2e.txt
playwright install chromium
pytest tests/e2e/ --base-url http://localhost:5001 -v
```

## Change Playbooks

### Adding a new API endpoint

Checklist:
- Add route in `app.py` under an appropriate section.
- Validate inputs early; return `jsonify({'error': '...'}), 400` for client errors.
- Use `current_user_id()` and scope DB calls via `user_id=`.
- Add/extend DB functions in `db.py` (parameterized SQL only).
- Add pytest coverage under `tests/` using `authed_client` + `mock_db` (API tests) or db connection mocks (DB tests).

### Adding/changing schema

Checklist:
- Update `init_db()` in `db.py` and use guarded alters (`_guard_alter`) for compatibility.
- Add/extend schema tests in `tests/test_db_schema.py`.
- Verify docker-compose bring-up and basic page/API paths.

### Changing prompts or model behavior

Checklist:
- Update `pet_model_config.py` for prompts/model name.
- Keep parsing and retry logic in `model_connector.py`.
- Add/extend parsing tests in `tests/test_model_connector.py`.

## Repo Hygiene (Observed)

- Do not commit `.env` (it is gitignored).
- `.worktrees/` is ignored.
- Avoid adding Windows `*:Zone.Identifier` artifacts.
