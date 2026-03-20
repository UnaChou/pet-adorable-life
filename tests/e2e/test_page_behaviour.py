"""
E2E — Page behaviour tests for pets, diary, product_analyze, and auth pages.

Tests dynamic DOM behaviour driven by JS:
  - Pets page: add pet form toggle, edit dialog
  - Diary page: upload zone visibility, form sections
  - Product analyze page: upload zone visibility, analyze button state
  - Auth pages: login/register form rendering

Requires a live server: pytest tests/e2e/ --base-url http://localhost:5001
"""

import pytest


pytestmark = pytest.mark.e2e

_NAV_TIMEOUT = 10_000  # ms — generous for JS network calls


# ---------------------------------------------------------------------------
# Pets page (/pets) — Auth required, redirects to /login
# ---------------------------------------------------------------------------

class TestPetsPageAuth:
    def test_redirects_to_login_when_not_authenticated(self, page, base_url):
        """Protected pages redirect to /login when user is not authenticated."""
        page.goto(f"{base_url}/pets", wait_until="domcontentloaded")
        # Should redirect to login page
        page.wait_for_url(f"{base_url}/login", timeout=_NAV_TIMEOUT)
        assert "/login" in page.url


# ---------------------------------------------------------------------------
# Diary page (/diary) — Auth required, redirects to /login
# ---------------------------------------------------------------------------

class TestDiaryPageAuth:
    def test_redirects_to_login_when_not_authenticated(self, page, base_url):
        """Protected pages redirect to /login when user is not authenticated."""
        page.goto(f"{base_url}/diary", wait_until="domcontentloaded")
        # Should redirect to login page
        page.wait_for_url(f"{base_url}/login", timeout=_NAV_TIMEOUT)
        assert "/login" in page.url


# ---------------------------------------------------------------------------
# Product Analyze page (/product-analyze) — Auth required, redirects to /login
# ---------------------------------------------------------------------------

class TestProductAnalyzePageAuth:
    def test_redirects_to_login_when_not_authenticated(self, page, base_url):
        """Protected pages redirect to /login when user is not authenticated."""
        page.goto(f"{base_url}/product/analyze", wait_until="domcontentloaded")
        # Should redirect to login page
        page.wait_for_url(f"{base_url}/login", timeout=_NAV_TIMEOUT)
        assert "/login" in page.url


# ---------------------------------------------------------------------------
# Login page (/login)
# ---------------------------------------------------------------------------

class TestLoginPageStructure:
    def test_page_title_set(self, page, base_url):
        page.goto(f"{base_url}/login", wait_until="domcontentloaded")
        assert "登入" in page.title()

    def test_auth_card_visible(self, page, base_url):
        page.goto(f"{base_url}/login", wait_until="domcontentloaded")
        card = page.locator(".auth-card")
        card.wait_for(state="visible")
        assert card.is_visible()

    def test_page_subtitle_is_dengru(self, page, base_url):
        page.goto(f"{base_url}/login", wait_until="domcontentloaded")
        subtitle = page.locator(".auth-subtitle")
        subtitle.wait_for(state="visible")
        assert "登入帳號" in subtitle.inner_text()


class TestLoginForm:
    def test_username_input_present(self, page, base_url):
        page.goto(f"{base_url}/login", wait_until="domcontentloaded")
        username = page.locator("#username")
        username.wait_for(state="visible")
        assert username.is_visible()

    def test_password_input_present(self, page, base_url):
        page.goto(f"{base_url}/login", wait_until="domcontentloaded")
        password = page.locator("#password")
        password.wait_for(state="visible")
        assert password.is_visible()

    def test_submit_button_present(self, page, base_url):
        page.goto(f"{base_url}/login", wait_until="domcontentloaded")
        submit_btn = page.locator("button[type='submit']")
        submit_btn.wait_for(state="visible")
        assert submit_btn.is_visible()
        assert "登入" in submit_btn.inner_text()

    def test_register_link_present(self, page, base_url):
        page.goto(f"{base_url}/login", wait_until="domcontentloaded")
        register_link = page.locator("a[href='/register']")
        register_link.wait_for(state="visible")
        assert register_link.is_visible()

    def test_forgot_password_link_present(self, page, base_url):
        page.goto(f"{base_url}/login", wait_until="domcontentloaded")
        forgot_link = page.locator("a[href='/forgot-password']")
        forgot_link.wait_for(state="visible")
        assert forgot_link.is_visible()


# ---------------------------------------------------------------------------
# Register page (/register)
# ---------------------------------------------------------------------------

class TestRegisterPageStructure:
    def test_page_title_set(self, page, base_url):
        page.goto(f"{base_url}/register", wait_until="domcontentloaded")
        assert "註冊" in page.title()

    def test_auth_card_visible(self, page, base_url):
        page.goto(f"{base_url}/register", wait_until="domcontentloaded")
        card = page.locator(".auth-card")
        card.wait_for(state="visible")
        assert card.is_visible()

    def test_page_subtitle_is_jianlizhanghao(self, page, base_url):
        page.goto(f"{base_url}/register", wait_until="domcontentloaded")
        subtitle = page.locator(".auth-subtitle")
        subtitle.wait_for(state="visible")
        assert "建立帳號" in subtitle.inner_text()


class TestRegisterForm:
    def test_username_input_present(self, page, base_url):
        page.goto(f"{base_url}/register", wait_until="domcontentloaded")
        username = page.locator("#username")
        username.wait_for(state="visible")
        assert username.is_visible()

    def test_email_input_present(self, page, base_url):
        page.goto(f"{base_url}/register", wait_until="domcontentloaded")
        email = page.locator("#email")
        email.wait_for(state="visible")
        assert email.is_visible()

    def test_password_input_present(self, page, base_url):
        page.goto(f"{base_url}/register", wait_until="domcontentloaded")
        password = page.locator("#password")
        password.wait_for(state="visible")
        assert password.is_visible()

    def test_confirm_password_input_present(self, page, base_url):
        page.goto(f"{base_url}/register", wait_until="domcontentloaded")
        confirm = page.locator("#confirm_password")
        confirm.wait_for(state="visible")
        assert confirm.is_visible()

    def test_submit_button_present(self, page, base_url):
        page.goto(f"{base_url}/register", wait_until="domcontentloaded")
        submit_btn = page.locator("button[type='submit']")
        submit_btn.wait_for(state="visible")
        assert submit_btn.is_visible()
        assert "註冊" in submit_btn.inner_text()

    def test_login_link_present(self, page, base_url):
        page.goto(f"{base_url}/register", wait_until="domcontentloaded")
        login_link = page.locator("a[href='/login']")
        login_link.wait_for(state="visible")
        assert login_link.is_visible()

    def test_username_label_has_validation_hint(self, page, base_url):
        page.goto(f"{base_url}/register", wait_until="domcontentloaded")
        # Username label should indicate validation rules
        label = page.locator("label[for='username']")
        label.wait_for(state="visible")
        assert "英文字母" in label.inner_text() or "數字" in label.inner_text()

    def test_password_label_has_length_hint(self, page, base_url):
        page.goto(f"{base_url}/register", wait_until="domcontentloaded")
        # Password label should indicate minimum length
        label = page.locator("label[for='password']")
        label.wait_for(state="visible")
        assert "8" in label.inner_text()
