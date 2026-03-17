# Contributing Guide

<!-- AUTO-GENERATED: Prerequisites and setup sections generated from pyproject.toml, Dockerfile, docker-compose.yml -->

## Prerequisites

| Tool | Purpose | Version |
|------|---------|---------|
| Docker & Docker Compose | Run MySQL and the app container | Any recent |
| Python | Local development (optional) | ≥ 3.14 (local) / 3.11 (Docker) |
| Poetry | Dependency management (local only) | ≥ 2.0 |
| Ollama | External AI inference server | Any with `qwen3-vl:8b` model |

> **Note:** The Dockerfile uses Python 3.11-slim with plain `pip install`. `pyproject.toml` requires Python ≥ 3.14 for local Poetry-based development. These are different environments.

---

## Development Environment Setup

### Option A — Full Docker Stack (Recommended)

```bash
# Start MySQL + Flask app
docker-compose up -d

# App available at http://localhost:5001
```

### Option B — Local Flask, Docker MySQL

```bash
# 1. Copy env template
cp .env.example .env
# Edit .env with your Ollama URL and DB credentials

# 2. Start only MySQL
docker-compose up -d mysql

# 3. Install dependencies
poetry install

# 4. Run Flask dev server (auto-reloads on .py and .html changes)
python app.py
# App available at http://localhost:5001
```

---

## Available Commands

<!-- AUTO-GENERATED from pyproject.toml and CLAUDE.md -->

| Command | Description |
|---------|-------------|
| `docker-compose up -d` | Start full stack (MySQL + Flask app) |
| `docker-compose up -d mysql` | Start MySQL only |
| `docker-compose down` | Stop all containers |
| `docker-compose logs -f web` | Tail Flask app logs |
| `poetry install` | Install all dependencies |
| `poetry add <pkg>` | Add a new dependency |
| `python app.py` | Run Flask dev server locally (port 5001) |
| `docker exec pet-adorable-life-web python -m pytest tests/ -v` | Run full test suite |
| `docker exec pet-adorable-life-web python -m pytest tests/ --cov` | Run tests with coverage report |

---

## Environment Variables

<!-- AUTO-GENERATED from .env.example and docker-compose.yml -->

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MYSQL_HOST` | Yes | `localhost` (local) / `mysql` (Docker) | MySQL server hostname |
| `MYSQL_PORT` | No | `3306` | MySQL server port |
| `MYSQL_USER` | Yes | `pet_user` | MySQL username |
| `MYSQL_PASSWORD` | Yes | `pet_password` | MySQL password |
| `MYSQL_DATABASE` | Yes | `pet_adorable_life` | Database name |
| `OLLAMA_URL` | Yes | `http://192.168.50.11:11434/api/generate` | Ollama inference endpoint |
| `FLASK_SECRET_KEY` | Yes (production) | hardcoded ⚠️ | Flask session signing key — must be set in production |
| `FLASK_APP` | No | `app.py` | Flask entry point |
| `FLASK_DEBUG` | No | `0` | Enable Flask debug mode (`1` = on) |

> ⚠️ `FLASK_SECRET_KEY` is currently hardcoded in `app.py`. Before deploying to production, move it to an environment variable. Generate a secure key with: `python -c "import secrets; print(secrets.token_hex(32))"`

---

## Testing

### Run Tests

```bash
# Full test suite (requires Docker container running)
docker exec pet-adorable-life-web python -m pytest tests/ -v

# With coverage report
docker exec pet-adorable-life-web python -m pytest tests/ --cov --cov-report=term-missing
```

### Test Structure

| File | Coverage |
|------|----------|
| `tests/test_api_pets.py` | Pets REST API endpoints |
| `tests/test_api_products.py` | Products REST API endpoints |
| `tests/test_api_diaries.py` | Diaries REST API endpoints |
| `tests/test_app_pages.py` | Page routes (HTML rendering) |
| `tests/test_db_pets.py` | `db.py` — pet CRUD operations |
| `tests/test_db_products.py` | `db.py` — product CRUD operations |
| `tests/test_db_diaries.py` | `db.py` — diary CRUD operations |
| `tests/test_db_schema.py` | `db.py` — schema initialization |
| `tests/test_model_connector.py` | Ollama connector and JSON parsing |

### Writing New Tests

- Use `unittest.mock.patch` to mock `db.get_connection` and `model_connector` calls
- DB-layer tests mock `get_connection` directly — no live DB required
- API tests use the Flask test client from `conftest.py`
- Target: **≥ 80% coverage**

---

## Code Style

- **Python:** PEP 8, f-strings, context managers for resources
- **Immutability:** Create new objects rather than mutating in place
- **Functions:** < 50 lines; files < 800 lines
- **Error handling:** All errors handled explicitly; never silently swallowed
- **Logging:** Use `logging` module — no `print()` in production paths
- **UI language:** Traditional Chinese (prompts and all user-facing text)

---

## Project Layout

```
pet-adorable-life/
├── app.py                  # Flask routes and request handling
├── db.py                   # MySQL operations via PyMySQL (no ORM)
├── model_connector.py      # Ollama API client and JSON parsing
├── pet_model_config.py     # Model name and prompts (Traditional Chinese)
├── templates/              # Jinja2 HTML templates
│   └── base.html           # Shared layout
├── static/                 # CSS / JS / images (served directly)
├── tests/                  # pytest test suite
├── docs/                   # Architecture plans and docs
├── pyproject.toml          # Poetry project definition
├── docker-compose.yml      # MySQL + web container stack
├── Dockerfile              # Production container (Python 3.11-slim)
└── .env.example            # Environment variable template
```

---

## PR Checklist

- [ ] Tests pass: `docker exec pet-adorable-life-web python -m pytest tests/ -v`
- [ ] Coverage ≥ 80%
- [ ] No hardcoded credentials or secrets
- [ ] No `print()` in production code paths — use `logging`
- [ ] Error handling added for new endpoints
- [ ] UI text in Traditional Chinese
