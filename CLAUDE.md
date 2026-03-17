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

Note: `pyproject.toml` requires Python >=3.14, but the `Dockerfile` uses Python 3.11-slim with `pip install` (not Poetry).

**Run tests (requires Docker container running):**
```bash
docker exec pet-adorable-life-web python -m pytest tests/ -v
```

## Environment Setup

When running locally, copy `.env.example` to `.env` and configure:
- `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE`

When using `docker-compose up`, env vars are injected automatically via the compose file.

The app requires an **Ollama** instance running externally. The endpoint defaults to `http://192.168.50.11:11434/api/generate` and is configurable via the `OLLAMA_URL` env var (set in `.env` or `docker-compose.yml`). Ollama is **not** part of `docker-compose.yml`.

## Architecture

**Stack:** Python Flask + PyMySQL + Ollama AI + MySQL 8.0 (Docker)

The app is a pet care tool with three main domains:
1. **Pet management** — CRUD for pet profiles (name, breed, birthday, photo)
2. **Product analysis** — upload a product photo, AI extracts `title` and `summary` (5-point format); products can be attributed to a pet
3. **Pet diary** — upload a pet photo, AI returns `title`, `describe`, and `main_emotion`; diary entries can be attributed to a pet

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

**Routes overview (page routes — render templates):**
- `/` — home/navigation
- `/pets` — pet management page
- `/product/analyze` — product image upload + AI analysis
- `/organize` — products and diaries with pet filter tabs (all data loaded via fetch)
- `/organize/edit/<id>` — product edit page (loads data via fetch GET, saves via fetch PUT)
- `/diary` — diary image upload + AI analysis

**REST API routes:**
- `GET/POST /api/pets`, `GET/PUT/DELETE /api/pets/<id>`
- `GET/POST /api/products`, `GET/PUT/DELETE /api/products/<id>`, `DELETE /api/products` (batch)
- `GET/POST /api/diaries`, `DELETE /api/diaries/<id>`, `DELETE /api/diaries` (batch)
- `POST /api/product/analyze`, `POST /api/diary/analyze` — AI analysis endpoints

**pet_id filter pattern** (`?pet_id=N` on GET list endpoints): `None` = all records, `0` = IS NULL (unassigned), positive int = specific pet.

**Database:** Three tables — `pets`, `products`, `pet_diaries`. `products` and `pet_diaries` have nullable `pet_id` FK (logical, no DB-level constraint). Images stored as base64 `LONGTEXT`. Tables auto-created on startup via `init_db()` with `ALTER TABLE` guards for backward compatibility.

**Templates:** Jinja2 in `templates/`; base layout in `base.html`. Frontend uses vanilla JS with camera API and drag-and-drop upload. No build step — static assets served directly.

**UI language:** Traditional Chinese (prompts and UI text).
