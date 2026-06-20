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

Note: `pyproject.toml` requires Python >=3.13, but the `Dockerfile` uses Python 3.11-slim with `pip install` (not Poetry).

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

## Python Coding Guidelines

All Python code in this project must follow these standards.

### Formatting

- **Formatter:** `black` with line length **120** (not the default 88)
- **Indentation:** 4 spaces (no tabs)
- **Max line length:** 120 characters

`pyproject.toml` black config:
```toml
[tool.black]
line-length = 120
include = '\.pyi?$'
exclude = '''
/(
    \.git | \.hg | \.mypy_cache | \.tox | \.venv
  | _build | buck-out | build | dist
)/
'''
```

### Naming Conventions

| Kind | Style | Example |
|------|-------|---------|
| Class | UpperCamelCase (noun) | `ExampleClassGPT` |
| Function / method | `verb_noun` snake_case | `get_product_tags_dictionary` |
| Local variable | snake_case (noun) | `example_local_variable` |
| Global variable | UPPER_SNAKE_CASE | `EXAMPLE_GLOBAL_VARIABLE` |
| Environment variable | UPPER_SNAKE_CASE | `EXAMPLE_ENV_VARIABLE` |
| Protected method | leading underscore | `_update_df_to_db` |
| Protected attribute | leading underscore + `@property` getter | `self._cupid_id` |

### Imports

All imports must be at the **top of the file**, before any other code.

Use `from` for multi-level paths:
```python
# Bad
import src.tagging_service

# Good
from src import tagging_service
ser = tagging_service.ClassName()

# Also acceptable when module is large (avoids loading whole module)
from src.tagging_service import ClassName
```

### Docstrings

All public functions must have a docstring with Args and Return type:
```python
def get_product_info(cupid_id: str) -> pd.DataFrame:
    """
    商品分群資訊

    Args:
        cupid_id (str): 店家ID

    Returns:
        pd.DataFrame: columns — cupid_id, outer_id, title, language_id, tokenized_title
    """
```

### SQL Safety

- Never hard-code the database name in SQL strings
- Always use named parameters (`:param`) + `sqlalchemy.text()` to prevent SQL injection

```python
# Bad
sql = f"SELECT id FROM product WHERE id={id}"

# Good
from sqlalchemy import text
sql = "SELECT id FROM product WHERE id=:id"
conn.execute(text(sql), {"id": id})
```

### Large DB Queries

Use `chunksize` with `pd.read_sql` when processing large datasets to avoid connection timeouts:
```python
for chunk_df in pd.read_sql(text(sql), con=engine, params=params, chunksize=1000):
    # process chunk
```

### Pre-commit Hooks

The project uses pre-commit to enforce format before every commit: `check-ast`, `trailing-whitespace`, `end-of-file-fixer`, `isort`, and `black`.

## Skill routing

When the user's request matches an available skill, ALWAYS invoke it using the Skill
tool as your FIRST action. Do NOT answer directly, do NOT use other tools first.
The skill has specialized workflows that produce better results than ad-hoc answers.

Key routing rules:
- Product ideas, "is this worth building", brainstorming → invoke office-hours
- Bugs, errors, "why is this broken", 500 errors → invoke investigate
- Ship, deploy, push, create PR → invoke ship
- QA, test the site, find bugs → invoke qa
- Code review, check my diff → invoke review
- Update docs after shipping → invoke document-release
- Weekly retro → invoke retro
- Design system, brand → invoke design-consultation
- Visual audit, design polish → invoke design-review
- Architecture review → invoke plan-eng-review
