"""
E2E — AI analyze endpoint input-validation tests.

These tests exercise only the validation layer (400-level responses) and
do NOT depend on Ollama being available. A request that would reach the AI
service is rejected before it gets that far, so the tests are always stable.

Endpoints covered:
  POST /api/product/analyze
  POST /api/diary/analyze

Requires a live server: pytest tests/e2e/ --base-url http://localhost:5001
"""

import io

import pytest
import requests


pytestmark = pytest.mark.e2e

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ALLOWED_EXTENSIONS = ("png", "jpg", "jpeg", "webp", "gif")
_DISALLOWED_EXTENSIONS = ("pdf", "txt", "docx", "exe", "svg", "mp4", "zip")

# Minimal valid PNG header (8 bytes) — sufficient for the extension check
_MINIMAL_IMAGE_BYTES = b"\x89PNG\r\n\x1a\n"


def _post_no_files(base_url: str, path: str) -> requests.Response:
    """POST to path with no files at all (missing 'image' key)."""
    return requests.post(f"{base_url}{path}")


def _post_file(
    base_url: str,
    path: str,
    filename: str,
    content: bytes = _MINIMAL_IMAGE_BYTES,
    field: str = "image",
) -> requests.Response:
    """POST a multipart file upload."""
    files = {field: (filename, io.BytesIO(content), "application/octet-stream")}
    return requests.post(f"{base_url}{path}", files=files)


def _post_empty_filename(base_url: str, path: str) -> requests.Response:
    """POST with the image field present but filename set to empty string."""
    files = {"image": ("", io.BytesIO(b"data"), "application/octet-stream")}
    return requests.post(f"{base_url}{path}", files=files)


# ---------------------------------------------------------------------------
# Product analyze — missing / invalid input
# ---------------------------------------------------------------------------

class TestProductAnalyzeValidation:
    """Validation tests for POST /api/product/analyze."""

    PATH = "/api/product/analyze"

    # --- Missing file ---

    def test_no_image_field_returns_400(self, base_url):
        resp = _post_no_files(base_url, self.PATH)
        assert resp.status_code == 400

    def test_no_image_response_has_error_key(self, base_url):
        resp = _post_no_files(base_url, self.PATH)
        assert "error" in resp.json()

    def test_no_image_error_is_string(self, base_url):
        resp = _post_no_files(base_url, self.PATH)
        assert isinstance(resp.json()["error"], str)

    # --- Empty filename ---

    def test_empty_filename_returns_400(self, base_url):
        resp = _post_empty_filename(base_url, self.PATH)
        assert resp.status_code == 400

    def test_empty_filename_response_has_error_key(self, base_url):
        resp = _post_empty_filename(base_url, self.PATH)
        assert "error" in resp.json()

    # --- Unsupported file types ---

    def test_pdf_returns_400(self, base_url):
        resp = _post_file(base_url, self.PATH, "document.pdf")
        assert resp.status_code == 400

    def test_txt_returns_400(self, base_url):
        resp = _post_file(base_url, self.PATH, "notes.txt")
        assert resp.status_code == 400

    def test_docx_returns_400(self, base_url):
        resp = _post_file(base_url, self.PATH, "report.docx")
        assert resp.status_code == 400

    def test_exe_returns_400(self, base_url):
        resp = _post_file(base_url, self.PATH, "malware.exe")
        assert resp.status_code == 400

    def test_mp4_returns_400(self, base_url):
        resp = _post_file(base_url, self.PATH, "video.mp4")
        assert resp.status_code == 400

    def test_zip_returns_400(self, base_url):
        resp = _post_file(base_url, self.PATH, "archive.zip")
        assert resp.status_code == 400

    def test_unsupported_format_error_mentions_supported_types(self, base_url):
        resp = _post_file(base_url, self.PATH, "file.pdf")
        body = resp.json()
        assert "error" in body
        # The app message says "不支援的格式，請使用: ..."
        assert "不支援" in body["error"] or any(
            ext in body["error"] for ext in _ALLOWED_EXTENSIONS
        )

    def test_no_extension_returns_400(self, base_url):
        resp = _post_file(base_url, self.PATH, "noextension")
        assert resp.status_code == 400

    # --- Wrong field name ---

    def test_wrong_field_name_returns_400(self, base_url):
        """Posting under 'file' instead of 'image' should be rejected."""
        resp = _post_file(base_url, self.PATH, "photo.jpg", field="file")
        assert resp.status_code == 400

    # --- Response structure sanity ---

    def test_400_response_is_json(self, base_url):
        resp = _post_no_files(base_url, self.PATH)
        # Should not raise
        _ = resp.json()

    def test_400_content_type_is_json(self, base_url):
        resp = _post_no_files(base_url, self.PATH)
        assert "application/json" in resp.headers.get("Content-Type", "")


# ---------------------------------------------------------------------------
# Diary analyze — missing / invalid input
# ---------------------------------------------------------------------------

class TestDiaryAnalyzeValidation:
    """Validation tests for POST /api/diary/analyze."""

    PATH = "/api/diary/analyze"

    # --- Missing file ---

    def test_no_image_field_returns_400(self, base_url):
        resp = _post_no_files(base_url, self.PATH)
        assert resp.status_code == 400

    def test_no_image_response_has_error_key(self, base_url):
        resp = _post_no_files(base_url, self.PATH)
        assert "error" in resp.json()

    def test_no_image_error_is_string(self, base_url):
        resp = _post_no_files(base_url, self.PATH)
        assert isinstance(resp.json()["error"], str)

    # --- Empty filename ---

    def test_empty_filename_returns_400(self, base_url):
        resp = _post_empty_filename(base_url, self.PATH)
        assert resp.status_code == 400

    def test_empty_filename_response_has_error_key(self, base_url):
        resp = _post_empty_filename(base_url, self.PATH)
        assert "error" in resp.json()

    # --- Unsupported file types ---

    def test_pdf_returns_400(self, base_url):
        resp = _post_file(base_url, self.PATH, "document.pdf")
        assert resp.status_code == 400

    def test_txt_returns_400(self, base_url):
        resp = _post_file(base_url, self.PATH, "notes.txt")
        assert resp.status_code == 400

    def test_docx_returns_400(self, base_url):
        resp = _post_file(base_url, self.PATH, "report.docx")
        assert resp.status_code == 400

    def test_exe_returns_400(self, base_url):
        resp = _post_file(base_url, self.PATH, "malware.exe")
        assert resp.status_code == 400

    def test_mp4_returns_400(self, base_url):
        resp = _post_file(base_url, self.PATH, "video.mp4")
        assert resp.status_code == 400

    def test_zip_returns_400(self, base_url):
        resp = _post_file(base_url, self.PATH, "archive.zip")
        assert resp.status_code == 400

    def test_unsupported_format_error_mentions_supported_types(self, base_url):
        resp = _post_file(base_url, self.PATH, "file.pdf")
        body = resp.json()
        assert "error" in body
        assert "不支援" in body["error"] or any(
            ext in body["error"] for ext in _ALLOWED_EXTENSIONS
        )

    def test_no_extension_returns_400(self, base_url):
        resp = _post_file(base_url, self.PATH, "noextension")
        assert resp.status_code == 400

    # --- Wrong field name ---

    def test_wrong_field_name_returns_400(self, base_url):
        resp = _post_file(base_url, self.PATH, "photo.jpg", field="file")
        assert resp.status_code == 400

    # --- Response structure sanity ---

    def test_400_response_is_json(self, base_url):
        resp = _post_no_files(base_url, self.PATH)
        _ = resp.json()

    def test_400_content_type_is_json(self, base_url):
        resp = _post_no_files(base_url, self.PATH)
        assert "application/json" in resp.headers.get("Content-Type", "")


# ---------------------------------------------------------------------------
# Parametrized extension coverage (both endpoints)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename", [f"file.{ext}" for ext in _DISALLOWED_EXTENSIONS])
@pytest.mark.parametrize("path", ["/api/product/analyze", "/api/diary/analyze"])
def test_disallowed_extension_rejected(base_url, path, filename):
    """All disallowed extensions must return 400 on both analyze endpoints."""
    resp = _post_file(base_url, path, filename)
    assert resp.status_code == 400, (
        f"Expected 400 for '{filename}' on {path}, got {resp.status_code}"
    )
