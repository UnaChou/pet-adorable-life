"""
E2E — Page navigation tests.

Verifies that all primary page routes render with HTTP 200 and include
expected structural elements in the DOM.

Requires a live server: pytest tests/e2e/ --base-url http://localhost:5001
"""

import pytest


pytestmark = pytest.mark.e2e


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _go(page, base_url: str, path: str):
    """Navigate and return the response status."""
    response = page.goto(f"{base_url}{path}", wait_until="domcontentloaded")
    return response


# ---------------------------------------------------------------------------
# Home page
# ---------------------------------------------------------------------------

class TestHomePage:
    def test_returns_200(self, page, base_url):
        response = _go(page, base_url, "/")
        assert response.status == 200

    def test_title_contains_pet_adorable_life(self, page, base_url):
        _go(page, base_url, "/")
        assert "Pet Adorable Life" in page.title()

    def test_nav_bar_present(self, page, base_url):
        _go(page, base_url, "/")
        nav = page.locator("nav.nav-bar")
        nav.wait_for(state="visible")
        assert nav.is_visible()

    def test_nav_links_include_all_sections(self, page, base_url):
        _go(page, base_url, "/")
        links = page.locator("nav.nav-bar a")
        hrefs = [links.nth(i).get_attribute("href") for i in range(links.count())]
        for expected in ["/", "/product/analyze", "/organize", "/diary", "/pets"]:
            assert expected in hrefs, f"Nav link '{expected}' not found in {hrefs}"

    def test_hero_heading_visible(self, page, base_url):
        _go(page, base_url, "/")
        heading = page.locator("section.hero h1")
        heading.wait_for(state="visible")
        assert heading.is_visible()

    def test_feature_cards_present(self, page, base_url):
        _go(page, base_url, "/")
        # Two feature card sections: AI and Life
        cards = page.locator("a.card")
        assert cards.count() >= 2

    def test_product_analyze_card_links_correctly(self, page, base_url):
        _go(page, base_url, "/")
        card = page.locator("a.card[href='/product/analyze']")
        assert card.count() == 1

    def test_diary_card_links_correctly(self, page, base_url):
        _go(page, base_url, "/")
        card = page.locator("a.card[href='/diary']")
        assert card.count() == 1


# ---------------------------------------------------------------------------
# Pets page
# ---------------------------------------------------------------------------

class TestPetsPage:
    def test_returns_200(self, page, base_url):
        response = _go(page, base_url, "/pets")
        assert response.status == 200

    def test_page_heading_visible(self, page, base_url):
        _go(page, base_url, "/pets")
        heading = page.locator("h1")
        heading.wait_for(state="visible")
        assert "寵物" in heading.inner_text()

    def test_add_pet_toggle_button_present(self, page, base_url):
        _go(page, base_url, "/pets")
        btn = page.locator("#btnToggleAdd")
        btn.wait_for(state="visible")
        assert btn.is_visible()

    def test_add_form_hidden_by_default(self, page, base_url):
        _go(page, base_url, "/pets")
        form_wrap = page.locator("#addFormWrap")
        form_wrap.wait_for(state="attached")
        assert not form_wrap.is_visible()

    def test_add_form_toggles_open(self, page, base_url):
        _go(page, base_url, "/pets")
        page.locator("#btnToggleAdd").click()
        form_wrap = page.locator("#addFormWrap")
        form_wrap.wait_for(state="visible")
        assert form_wrap.is_visible()

    def test_add_form_has_name_input(self, page, base_url):
        _go(page, base_url, "/pets")
        page.locator("#btnToggleAdd").click()
        page.locator("#addFormWrap").wait_for(state="visible")
        name_input = page.locator("#addName")
        assert name_input.is_visible()

    def test_pets_list_section_present(self, page, base_url):
        _go(page, base_url, "/pets")
        pets_list = page.locator("#petsList")
        pets_list.wait_for(state="attached")
        assert pets_list.count() == 1


# ---------------------------------------------------------------------------
# Organize page
# ---------------------------------------------------------------------------

class TestOrganizePage:
    def test_returns_200(self, page, base_url):
        response = _go(page, base_url, "/organize")
        assert response.status == 200

    def test_page_heading_visible(self, page, base_url):
        _go(page, base_url, "/organize")
        heading = page.locator("h1")
        heading.wait_for(state="visible")
        assert "Pet Life" in heading.inner_text()

    def test_tab_switcher_present(self, page, base_url):
        _go(page, base_url, "/organize")
        tab_header = page.locator("div.tabs-header")
        tab_header.wait_for(state="visible")
        assert tab_header.is_visible()

    def test_products_tab_button_present(self, page, base_url):
        _go(page, base_url, "/organize")
        btn = page.locator("button.tab-btn[data-tab='products-tab']")
        btn.wait_for(state="visible")
        assert btn.is_visible()

    def test_diaries_tab_button_present(self, page, base_url):
        _go(page, base_url, "/organize")
        btn = page.locator("button.tab-btn[data-tab='diaries-tab']")
        btn.wait_for(state="visible")
        assert btn.is_visible()

    def test_products_tab_active_by_default(self, page, base_url):
        _go(page, base_url, "/organize")
        active_btn = page.locator("button.tab-btn.active[data-tab='products-tab']")
        active_btn.wait_for(state="visible")
        assert active_btn.is_visible()

    def test_tab_switch_to_diaries(self, page, base_url):
        _go(page, base_url, "/organize")
        page.locator("button.tab-btn[data-tab='diaries-tab']").click()
        diaries_tab = page.locator("#diaries-tab")
        diaries_tab.wait_for(state="visible")
        assert diaries_tab.is_visible()

    def test_pet_filter_bar_present(self, page, base_url):
        _go(page, base_url, "/organize")
        # The bar is always rendered (may be empty if no pets, but the
        # container element itself must exist)
        bar = page.locator("#petFilterBar")
        bar.wait_for(state="attached")
        assert bar.count() == 1

    def test_pet_filter_bar_has_all_button_after_load(self, page, base_url):
        _go(page, base_url, "/organize")
        # Wait for the JS to render the pet filter (network call to /api/pets)
        all_btn = page.locator("#petFilterBar button[data-pet='null']")
        all_btn.wait_for(state="visible", timeout=8000)
        assert "全部" in all_btn.inner_text()

    def test_add_product_toggle_button_present(self, page, base_url):
        _go(page, base_url, "/organize")
        btn = page.locator("#btnToggleAddProduct")
        btn.wait_for(state="visible")
        assert btn.is_visible()


# ---------------------------------------------------------------------------
# Product analyze page
# ---------------------------------------------------------------------------

class TestProductAnalyzePage:
    def test_returns_200(self, page, base_url):
        response = _go(page, base_url, "/product/analyze")
        assert response.status == 200

    def test_title_mentions_product_or_analyze(self, page, base_url):
        _go(page, base_url, "/product/analyze")
        title = page.title()
        assert "商品" in title or "分析" in title or "Pet" in title

    def test_nav_bar_present(self, page, base_url):
        _go(page, base_url, "/product/analyze")
        nav = page.locator("nav.nav-bar")
        nav.wait_for(state="visible")
        assert nav.is_visible()


# ---------------------------------------------------------------------------
# Diary page
# ---------------------------------------------------------------------------

class TestDiaryPage:
    def test_returns_200(self, page, base_url):
        response = _go(page, base_url, "/diary")
        assert response.status == 200

    def test_title_mentions_diary(self, page, base_url):
        _go(page, base_url, "/diary")
        title = page.title()
        assert "日記" in title or "Diary" in title or "Pet" in title

    def test_nav_bar_present(self, page, base_url):
        _go(page, base_url, "/diary")
        nav = page.locator("nav.nav-bar")
        nav.wait_for(state="visible")
        assert nav.is_visible()


# ---------------------------------------------------------------------------
# Organize edit page
# ---------------------------------------------------------------------------

class TestOrganizeEditPage:
    def test_returns_200_for_valid_id(self, page, base_url):
        # The page renders the shell regardless of whether the product
        # actually exists (data is loaded via JS fetch).
        response = _go(page, base_url, "/organize/edit/1")
        assert response.status == 200
