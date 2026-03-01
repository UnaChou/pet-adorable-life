"""
E2E test configuration and fixtures for pytest-playwright.

Run against the live docker-compose stack:
    pytest tests/e2e/ --base-url http://localhost:5001

Playwright browser fixtures (page, browser, context) are provided
automatically by pytest-playwright once installed.
"""

import pytest
import requests


# ---------------------------------------------------------------------------
# Marks
# ---------------------------------------------------------------------------

def pytest_configure(config):
    """Register custom markers so -m e2e works without ini warnings."""
    config.addinivalue_line(
        "markers",
        "e2e: marks a test as an end-to-end test requiring a live server",
    )


# ---------------------------------------------------------------------------
# Base URL
# ---------------------------------------------------------------------------

def _default_base_url() -> str:
    return "http://localhost:5001"


@pytest.fixture(scope="session")
def base_url(request) -> str:
    """
    Returns the base URL for the running app.

    Override via the --base-url CLI flag (provided by pytest-playwright):
        pytest tests/e2e/ --base-url http://localhost:5001
    """
    # pytest-playwright injects --base-url into the standard fixture.
    # Fall back to our default when running without the flag.
    url = getattr(request.config, "option", None)
    if url:
        cli_url = getattr(url, "base_url", None)
        if cli_url:
            return cli_url.rstrip("/")
    return _default_base_url()


# ---------------------------------------------------------------------------
# Liveness check
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def require_live_server(base_url):
    """
    Session-scoped fixture that fails fast when the app is not reachable.
    All E2E tests are automatically skipped with a clear message rather
    than producing dozens of confusing connection errors.
    """
    try:
        resp = requests.get(base_url, timeout=5)
        assert resp.status_code == 200, f"App returned {resp.status_code}"
    except Exception as exc:
        pytest.skip(
            f"Live server not reachable at {base_url} — "
            f"start it with 'docker-compose up -d' before running E2E tests. "
            f"Error: {exc}"
        )


# ---------------------------------------------------------------------------
# Shared API helper
# ---------------------------------------------------------------------------

class ApiClient:
    """
    Thin wrapper around requests for the REST API.
    Used in pure-API tests (no browser needed).
    """

    def __init__(self, base_url: str):
        self.base = base_url
        self.session = requests.Session()

    def get(self, path: str, **kwargs):
        return self.session.get(f"{self.base}{path}", **kwargs)

    def post(self, path: str, **kwargs):
        return self.session.post(f"{self.base}{path}", **kwargs)

    def put(self, path: str, **kwargs):
        return self.session.put(f"{self.base}{path}", **kwargs)

    def delete(self, path: str, **kwargs):
        return self.session.delete(f"{self.base}{path}", **kwargs)


@pytest.fixture(scope="session")
def api(base_url) -> ApiClient:
    """Session-scoped API client shared across all API-level tests."""
    return ApiClient(base_url)


# ---------------------------------------------------------------------------
# Pet lifecycle helper
# ---------------------------------------------------------------------------

@pytest.fixture()
def transient_pet(api):
    """
    Creates a pet before a test and deletes it afterwards.
    Yields the full pet dict returned by the API.
    """
    resp = api.post("/api/pets", json={"name": "E2E測試寵物", "breed": "測試犬"})
    assert resp.status_code == 201, f"Failed to create transient pet: {resp.text}"
    pet = resp.json()
    yield pet
    # cleanup — ignore 404 if test already deleted it
    api.delete(f"/api/pets/{pet['id']}")
