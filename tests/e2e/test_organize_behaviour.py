"""
E2E — Organize page browser behaviour tests.

Tests the /organize page's dynamic DOM behaviour driven by JS:
  - Tab switching
  - Pet filter bar rendering (including when pets exist)
  - Add product form toggle
  - Content sections rendered by the page JS

Requires a live server: pytest tests/e2e/ --base-url http://localhost:5001
"""

import pytest


pytestmark = pytest.mark.e2e

_ORGANIZE_PATH = "/organize"
_NAV_TIMEOUT = 10_000  # ms — generous for JS network calls


def _go(page, base_url: str):
    page.goto(f"{base_url}{_ORGANIZE_PATH}", wait_until="domcontentloaded")


# ---------------------------------------------------------------------------
# Initial page structure
# ---------------------------------------------------------------------------

class TestOrganisePageStructure:
    def test_page_title_set(self, page, base_url):
        _go(page, base_url)
        assert "Pet" in page.title()

    def test_nav_bar_visible(self, page, base_url):
        _go(page, base_url)
        nav = page.locator("nav.nav-bar")
        nav.wait_for(state="visible")
        assert nav.is_visible()

    def test_organize_nav_link_is_active(self, page, base_url):
        _go(page, base_url)
        active_link = page.locator("nav.nav-bar a.active")
        active_link.wait_for(state="visible")
        assert "/organize" in (active_link.get_attribute("href") or "")

    def test_hero_section_visible(self, page, base_url):
        _go(page, base_url)
        hero = page.locator("section.organize-hero")
        hero.wait_for(state="visible")
        assert hero.is_visible()

    def test_tabs_container_present(self, page, base_url):
        _go(page, base_url)
        container = page.locator("div.tabs-container")
        container.wait_for(state="visible")
        assert container.is_visible()

    def test_tabs_header_present(self, page, base_url):
        _go(page, base_url)
        header = page.locator("div.tabs-header")
        header.wait_for(state="visible")
        assert header.is_visible()


# ---------------------------------------------------------------------------
# Tab switching
# ---------------------------------------------------------------------------

class TestTabSwitching:
    def test_products_tab_active_on_load(self, page, base_url):
        _go(page, base_url)
        active = page.locator("button.tab-btn.active[data-tab='products-tab']")
        active.wait_for(state="visible")
        assert active.is_visible()

    def test_products_tab_content_visible_on_load(self, page, base_url):
        _go(page, base_url)
        content = page.locator("#products-tab")
        content.wait_for(state="visible")
        assert content.is_visible()

    def test_diaries_tab_content_hidden_on_load(self, page, base_url):
        _go(page, base_url)
        # Wait for page to settle
        page.locator("div.tabs-header").wait_for(state="visible")
        diaries_content = page.locator("#diaries-tab")
        # Should not be visible (CSS class 'active' absent)
        assert not diaries_content.is_visible()

    def test_clicking_diaries_tab_makes_content_visible(self, page, base_url):
        _go(page, base_url)
        page.locator("button.tab-btn[data-tab='diaries-tab']").click()
        page.locator("#diaries-tab").wait_for(state="visible", timeout=_NAV_TIMEOUT)
        assert page.locator("#diaries-tab").is_visible()

    def test_clicking_diaries_tab_hides_products_content(self, page, base_url):
        _go(page, base_url)
        page.locator("button.tab-btn[data-tab='diaries-tab']").click()
        page.locator("#diaries-tab").wait_for(state="visible", timeout=_NAV_TIMEOUT)
        assert not page.locator("#products-tab").is_visible()

    def test_clicking_products_tab_restores_products_content(self, page, base_url):
        _go(page, base_url)
        # Switch to diaries first
        page.locator("button.tab-btn[data-tab='diaries-tab']").click()
        page.locator("#diaries-tab").wait_for(state="visible", timeout=_NAV_TIMEOUT)
        # Switch back
        page.locator("button.tab-btn[data-tab='products-tab']").click()
        page.locator("#products-tab").wait_for(state="visible", timeout=_NAV_TIMEOUT)
        assert page.locator("#products-tab").is_visible()

    def test_active_class_moves_to_clicked_tab(self, page, base_url):
        _go(page, base_url)
        page.locator("button.tab-btn[data-tab='diaries-tab']").click()
        page.locator("#diaries-tab").wait_for(state="visible", timeout=_NAV_TIMEOUT)
        active_btn = page.locator(".tabs-header button.tab-btn.active")
        assert active_btn.get_attribute("data-tab") == "diaries-tab"


# ---------------------------------------------------------------------------
# Pet filter bar
# ---------------------------------------------------------------------------

class TestPetFilterBar:
    def test_filter_bar_container_present(self, page, base_url):
        _go(page, base_url)
        bar = page.locator("#petFilterBar")
        bar.wait_for(state="attached")
        assert bar.count() == 1

    def test_all_button_rendered_after_js_loads(self, page, base_url):
        _go(page, base_url)
        all_btn = page.locator("#petFilterBar button[data-pet='null']")
        all_btn.wait_for(state="visible", timeout=_NAV_TIMEOUT)
        assert all_btn.is_visible()

    def test_all_button_text_is_quanbu(self, page, base_url):
        _go(page, base_url)
        all_btn = page.locator("#petFilterBar button[data-pet='null']")
        all_btn.wait_for(state="visible", timeout=_NAV_TIMEOUT)
        assert "全部" in all_btn.inner_text()

    def test_unassigned_button_rendered(self, page, base_url):
        _go(page, base_url)
        # Wait for JS to finish rendering the bar (at least the '全部' btn)
        page.locator("#petFilterBar button[data-pet='null']").wait_for(
            state="visible", timeout=_NAV_TIMEOUT
        )
        unassigned_btn = page.locator("#petFilterBar button[data-pet='0']")
        unassigned_btn.wait_for(state="visible", timeout=_NAV_TIMEOUT)
        assert "未指定" in unassigned_btn.inner_text()

    def test_all_button_active_by_default(self, page, base_url):
        _go(page, base_url)
        all_btn = page.locator("#petFilterBar button[data-pet='null']")
        all_btn.wait_for(state="visible", timeout=_NAV_TIMEOUT)
        assert "active" in (all_btn.get_attribute("class") or "")

    def test_filter_bar_with_existing_pet(self, page, base_url, transient_pet, api):
        """
        When at least one pet exists in the database the filter bar should
        show that pet's name as a dedicated filter button.
        """
        _go(page, base_url)
        pet_name = transient_pet["name"]
        pet_id = transient_pet["id"]
        # Wait for the JS to render the filter including our pet
        pet_btn = page.locator(f"#petFilterBar button[data-pet='{pet_id}']")
        pet_btn.wait_for(state="visible", timeout=_NAV_TIMEOUT)
        assert pet_name in pet_btn.inner_text()

    def test_clicking_filter_button_updates_active_state(self, page, base_url, transient_pet):
        _go(page, base_url)
        pet_id = transient_pet["id"]
        btn = page.locator(f"#petFilterBar button[data-pet='{pet_id}']")
        btn.wait_for(state="visible", timeout=_NAV_TIMEOUT)
        btn.click()
        # After click the button should become active
        assert "active" in (btn.get_attribute("class") or "")

    def test_clicking_all_button_resets_filter(self, page, base_url, transient_pet):
        _go(page, base_url)
        pet_id = transient_pet["id"]
        pet_btn = page.locator(f"#petFilterBar button[data-pet='{pet_id}']")
        pet_btn.wait_for(state="visible", timeout=_NAV_TIMEOUT)
        pet_btn.click()
        all_btn = page.locator("#petFilterBar button[data-pet='null']")
        all_btn.click()
        assert "active" in (all_btn.get_attribute("class") or "")


# ---------------------------------------------------------------------------
# Add product form toggle
# ---------------------------------------------------------------------------

class TestAddProductFormToggle:
    def test_add_product_button_present(self, page, base_url):
        _go(page, base_url)
        btn = page.locator("#btnToggleAddProduct")
        btn.wait_for(state="visible")
        assert btn.is_visible()

    def test_add_product_section_hidden_by_default(self, page, base_url):
        _go(page, base_url)
        section = page.locator("#addProductSection")
        section.wait_for(state="attached")
        assert not section.is_visible()

    def test_clicking_toggle_shows_add_section(self, page, base_url):
        _go(page, base_url)
        page.locator("#btnToggleAddProduct").click()
        section = page.locator("#addProductSection")
        section.wait_for(state="visible")
        assert section.is_visible()

    def test_clicking_toggle_twice_hides_section(self, page, base_url):
        _go(page, base_url)
        btn = page.locator("#btnToggleAddProduct")
        btn.click()
        page.locator("#addProductSection").wait_for(state="visible")
        btn.click()
        page.locator("#addProductSection").wait_for(state="hidden")
        assert not page.locator("#addProductSection").is_visible()

    def test_add_form_has_title_input(self, page, base_url):
        _go(page, base_url)
        page.locator("#btnToggleAddProduct").click()
        page.locator("#addProductSection").wait_for(state="visible")
        assert page.locator("#addTitle").is_visible()

    def test_add_form_has_summary_textarea(self, page, base_url):
        _go(page, base_url)
        page.locator("#btnToggleAddProduct").click()
        page.locator("#addProductSection").wait_for(state="visible")
        assert page.locator("#addSummary").is_visible()

    def test_add_form_has_pet_select(self, page, base_url):
        _go(page, base_url)
        page.locator("#btnToggleAddProduct").click()
        page.locator("#addProductSection").wait_for(state="visible")
        assert page.locator("#addPetId").is_visible()

    def test_add_form_has_submit_button(self, page, base_url):
        _go(page, base_url)
        page.locator("#btnToggleAddProduct").click()
        page.locator("#addProductSection").wait_for(state="visible")
        assert page.locator("#btnAddProduct").is_visible()

    def test_button_label_changes_when_open(self, page, base_url):
        _go(page, base_url)
        btn = page.locator("#btnToggleAddProduct")
        btn.click()
        page.locator("#addProductSection").wait_for(state="visible")
        assert "隱藏" in btn.inner_text()

    def test_button_label_resets_when_closed(self, page, base_url):
        _go(page, base_url)
        btn = page.locator("#btnToggleAddProduct")
        btn.click()
        page.locator("#addProductSection").wait_for(state="visible")
        btn.click()
        page.locator("#addProductSection").wait_for(state="hidden")
        assert "新增商品" in btn.inner_text()


# ---------------------------------------------------------------------------
# Products loaded into the DOM
# ---------------------------------------------------------------------------

class TestProductListRendering:
    def test_product_list_section_present(self, page, base_url):
        _go(page, base_url)
        section = page.locator("#productList")
        section.wait_for(state="attached")
        assert section.count() == 1

    def test_products_loading_spinner_disappears(self, page, base_url):
        _go(page, base_url)
        # The spinner should be hidden once the API call completes
        spinner = page.locator("#productsLoading")
        spinner.wait_for(state="hidden", timeout=_NAV_TIMEOUT)
        assert not spinner.is_visible()

    def test_add_product_flow(self, page, base_url, api):
        """
        Full add-product flow through the UI:
        1. Toggle the form open
        2. Fill in title and summary
        3. Click the add button
        4. The new product appears in the list
        """
        _go(page, base_url)
        # Open form
        page.locator("#btnToggleAddProduct").click()
        page.locator("#addProductSection").wait_for(state="visible")

        test_title = "E2E測試商品"
        page.locator("#addTitle").fill(test_title)
        page.locator("#addSummary").fill("E2E摘要")

        # Submit
        page.locator("#btnAddProduct").click()

        # Form should close and product appear
        page.locator("#addProductSection").wait_for(state="hidden", timeout=_NAV_TIMEOUT)

        # Product list should contain our new title
        page.locator("#productList").wait_for(state="visible")
        # Wait for list re-render
        product_title = page.locator("#productList", has_text=test_title)
        product_title.wait_for(state="visible", timeout=_NAV_TIMEOUT)
        assert product_title.is_visible()

        # Cleanup: find and delete the product we just created via API
        products_resp = api.get("/api/products")
        for p in products_resp.json().get("products", []):
            if p.get("title") == test_title:
                api.delete(f"/api/products/{p['id']}")
                break
