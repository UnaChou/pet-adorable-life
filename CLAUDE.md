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

## Environment Setup

When running locally, copy `.env.example` to `.env` and configure:
- `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE`

When using `docker-compose up`, env vars are injected automatically via the compose file.

The app also requires an **Ollama** instance running externally. The endpoint is hardcoded in `model_connector.py` (`http://192.168.50.11:11434/api/generate`). The active model is `qwen3-vl:8b` (vision-language).

## Architecture

**Stack:** Python Flask + PyMySQL + Ollama AI + MySQL 8.0 (Docker)

The app is a pet care tool with two main domains:
1. **Product analysis** — upload a product photo, AI extracts title and 5-point summary
2. **Pet diary** — upload a pet photo, AI classifies emotion and mental state

**Key files:**
- `app.py` — Flask routes and request handling
- `db.py` — All MySQL operations via raw PyMySQL (no ORM); creates tables on startup
- `model_connector.py` — Calls Ollama API with base64-encoded images; uses Tenacity for retry with exponential backoff; parses JSON response (with regex fallback)
- `pet_model_config.py` — Model name and prompts (Traditional Chinese); swap model here

**Request flow for AI endpoints (`/api/product/analyze`, `/api/diary/analyze`):**
1. Frontend encodes image to base64 and POSTs it
2. `model_connector.py` sends to Ollama with the configured prompt
3. Response JSON is parsed and returned to the frontend
4. User confirms, then a second POST saves to MySQL

**Database:** Two tables — `products` and `pet_diaries`. Images are stored as base64 `LONGTEXT` in `pet_diaries`. Tables are auto-created by `db.py` on app startup.

**Templates:** Jinja2 in `templates/`; base layout in `base.html`. Frontend uses vanilla JS with camera API and drag-and-drop upload. No build step — static assets served directly.

**UI language:** Traditional Chinese (prompts and UI text).
