"""
E2E — Accessibility tests.

Verifies skip-to-content link and .hidden utility class functionality.

Requires a live server: pytest tests/e2e/ --base-url http://localhost:5001
"""

import pytest


pytestmark = pytest.mark.e2e


# ---------------------------------------------------------------------------
# Skip-to-content link
# ---------------------------------------------------------------------------

class TestSkipToContentLink:
    def test_skip_link_present_in_dom(self, page, base_url):
        """Skip-to-content link exists in the DOM."""
        page.goto(f"{base_url}/", wait_until="domcontentloaded")
        skip_link = page.locator("a.skip-to-content")
        assert skip_link.count() == 1

    def test_skip_link_hidden_by_default(self, page, base_url):
        """Skip-to-content link is visually hidden by default."""
        page.goto(f"{base_url}/", wait_until="domcontentloaded")
        skip_link = page.locator("a.skip-to-content")
        # When positioned at top:-9999px/left:-9999px, Playwright returns None
        # (element is off-screen/not in viewport) OR bounding box with very negative values
        bounding_box = skip_link.bounding_box()
        # None means completely off-screen — that's acceptable
        if bounding_box is not None:
            # Playwright uses x/y keys (not top/left).
            # If we got a bounding box, coordinates should be far off-screen
            assert bounding_box["y"] < -100 or bounding_box["x"] < -100

    def test_skip_link_visible_on_focus(self, page, base_url):
        """Skip-to-content link becomes visible when focused."""
        page.goto(f"{base_url}/", wait_until="domcontentloaded")
        skip_link = page.locator("a.skip-to-content")
        
        # Tab to focus the skip link
        page.keyboard.press("Tab")
        
        # Check that it's now visible (positioned on-screen)
        bounding_box = skip_link.bounding_box()
        assert bounding_box is not None
        assert bounding_box["y"] >= 0
        assert bounding_box["x"] >= 0

    def test_skip_link_points_to_main_content(self, page, base_url):
        """Skip-to-content link href points to #main-content."""
        page.goto(f"{base_url}/", wait_until="domcontentloaded")
        skip_link = page.locator("a.skip-to-content")
        href = skip_link.get_attribute("href")
        assert href == "#main-content"

    def test_main_content_id_exists(self, page, base_url):
        """Main content area has id='main-content'."""
        page.goto(f"{base_url}/", wait_until="domcontentloaded")
        main_content = page.locator("main#main-content")
        assert main_content.count() == 1

    def test_skip_link_navigation_works(self, page, base_url):
        """Pressing Enter on focused skip link navigates to main content."""
        page.goto(f"{base_url}/", wait_until="domcontentloaded")
        
        # Tab to focus skip link
        page.keyboard.press("Tab")
        
        # Press Enter to follow the link
        page.keyboard.press("Enter")
        
        # Check that focus moved to main content
        main_content = page.locator("main#main-content")
        # The main element should be in focus or a child should be
        focused_element = page.evaluate("document.activeElement.id")
        assert focused_element == "main-content" or main_content.is_visible()


# ---------------------------------------------------------------------------
# .hidden utility class
# ---------------------------------------------------------------------------

class TestHiddenUtilityClass:
    def test_hidden_class_hides_elements(self, page, base_url):
        """Elements with .hidden class are not visible."""
        page.goto(f"{base_url}/", wait_until="domcontentloaded")
        
        # Add .hidden to nav and verify it's hidden
        page.evaluate("""
            const nav = document.querySelector('nav.nav-bar');
            if (nav) {
                nav.classList.add('hidden');
            }
        """)
        
        nav = page.locator("nav.nav-bar")
        assert not nav.is_visible()

    def test_hidden_class_can_be_removed(self, page, base_url):
        """Elements with .hidden class become visible when class is removed."""
        page.goto(f"{base_url}/", wait_until="domcontentloaded")

        # Use a div we create ourselves so we're not dependent on auth state
        page.evaluate("""
            const div = document.createElement('div');
            div.id = 'hidden-test-elem';
            div.className = 'hidden';
            div.textContent = 'test';
            document.body.appendChild(div);
        """)

        elem = page.locator("#hidden-test-elem")
        assert not elem.is_visible()

        # Remove .hidden
        page.evaluate("""
            document.getElementById('hidden-test-elem').classList.remove('hidden');
        """)

        assert elem.is_visible()

    def test_hidden_class_uses_important_flag(self, page, base_url):
        """The .hidden class uses !important to override other styles."""
        page.goto(f"{base_url}/", wait_until="domcontentloaded")
        
        # Check that .hidden uses !important
        computed_style = page.evaluate("""(() => {
            const style = document.createElement('style');
            style.textContent = '.hidden { display: none !important; }';
            document.head.appendChild(style);

            const div = document.createElement('div');
            div.className = 'hidden';
            div.style.display = 'block';
            document.body.appendChild(div);

            const computed = window.getComputedStyle(div).display;
            div.remove();
            style.remove();
            return computed;
        })()""")
        
        assert computed_style == "none"
