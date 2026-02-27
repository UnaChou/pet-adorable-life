# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Run full stack (MySQL + Flask app) via Docker:**
```bash
docker-compose up -d
# App at http://localhost:5001
```

**Run locally (MySQL via Docker only, Flask directly):**
```bash
docker-compose up -d mysql   # start only the DB
python app.py                # runs on http://localhost:5001
```

**Dependency management (Poetry):**
```bash
poetry install       # Install dependencies
poetry add <pkg>     # Add a new dependency
```

Note: `pyproject.toml` requires Python >=3.14, but the `Dockerfile` uses Python 3.11-slim with `pip install` (not Poetry). There are **no automated tests** in this project.

## Environment Setup

When running locally, copy `.env.example` to `.env` and configure:
- `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE`

When using `docker-compose up`, env vars are injected automatically via the compose file.

The app requires an **Ollama** instance running externally. The endpoint is hardcoded in `model_connector.py` (`http://192.168.50.11:11434/api/generate`). To change it, edit the `url` variable at the top of that file. Ollama is **not** part of `docker-compose.yml`.

## Architecture

**Stack:** Python Flask + PyMySQL + Ollama AI + MySQL 8.0 (Docker)

The app is a pet care tool with two main domains:
1. **Product analysis** — upload a product photo, AI extracts `title` and `summary` (5-point format)
2. **Pet diary** — upload a pet photo, AI returns `title`, `describe`, and `main_emotion`

**Key files:**
- `app.py` — Flask routes and request handling
- `db.py` — All MySQL operations via raw PyMySQL (no ORM); creates tables on startup via `init_db()`, called lazily on first request via `@app.before_request`
- `model_connector.py` — Calls Ollama API with base64-encoded images; uses Tenacity (currently `stop_after_attempt(0)` = effectively no retries); parses JSON response with a regex fallback (`_extract_json_by_regex`)
- `pet_model_config.py` — Model name (`qwen3-vl:8b`) and prompts in Traditional Chinese; swap model or prompts here

**Two AI functions in `model_connector.py`:**
- `get_model_response_by_image(model, image_source)` — uses `product_prompt`, returns `{"title", "summary"}`
- `get_diary_response_by_image(model, image_source)` — uses `image_context_prompt`, returns `{"title", "describe", "main_emotion"}`

**Request flow for AI endpoints (`/api/product/analyze`, `/api/diary/analyze`):**
1. Frontend encodes image to base64 and POSTs it
2. `model_connector.py` sends to Ollama with the configured prompt
3. Response JSON is parsed and returned to the frontend
4. User confirms, then a second POST saves to MySQL

**Routes overview:**
- `/` — home/navigation
- `/product/analyze` — product image upload + AI analysis
- `/organize` — aggregated view of all products and diaries (both tables)
- `/organize/add|edit|update|remove` — product CRUD
- `/diary` — diary list and image upload
- `/diary/save` — save diary entry
- `/api/product/analyze`, `/api/diary/analyze` — JSON API endpoints for AI analysis

**Database:** Two tables — `products` and `pet_diaries`. Images are stored as base64 `LONGTEXT` in `pet_diaries`. Tables are auto-created by `db.py` on app startup, with `ALTER TABLE` guards for backward compatibility with existing databases.

**Templates:** Jinja2 in `templates/`; base layout in `base.html`. Frontend uses vanilla JS with camera API and drag-and-drop upload. No build step — static assets served directly.

**UI language:** Traditional Chinese (prompts and UI text).
