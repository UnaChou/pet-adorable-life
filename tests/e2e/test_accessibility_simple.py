"""
E2E — Accessibility tests (API-based).

Verifies skip-to-content link and .hidden utility class functionality
using HTTP requests and HTML parsing.

Requires a live server: pytest tests/e2e/ -v
"""

import pytest
from html.parser import HTMLParser


pytestmark = pytest.mark.e2e


class HTMLElementFinder(HTMLParser):
    """Simple HTML parser to find elements."""
    
    def __init__(self):
        super().__init__()
        self.skip_link_found = False
        self.main_content_found = False
        self.skip_link_href = None
        
    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == 'a' and attrs_dict.get('class') == 'skip-to-content':
            self.skip_link_found = True
            self.skip_link_href = attrs_dict.get('href')
        if tag == 'main' and attrs_dict.get('id') == 'main-content':
            self.main_content_found = True
        if tag == 'div' and attrs_dict.get('id') == 'main-content':
            self.main_content_found = True


# ---------------------------------------------------------------------------
# Skip-to-content link
# ---------------------------------------------------------------------------

class TestSkipToContentLink:
    def test_skip_link_present_in_login_page(self, api):
        """Skip-to-content link exists in login page HTML."""
        response = api.get("/login")
        assert response.status_code == 200
        
        parser = HTMLElementFinder()
        parser.feed(response.text)
        
        assert parser.skip_link_found, "Skip-to-content link not found in HTML"

    def test_skip_link_href_correct(self, api):
        """Skip-to-content link href points to #main-content."""
        response = api.get("/login")
        assert response.status_code == 200
        
        parser = HTMLElementFinder()
        parser.feed(response.text)
        
        assert parser.skip_link_href == "#main-content", \
            f"Expected href='#main-content', got '{parser.skip_link_href}'"

    def test_main_content_id_exists(self, api):
        """Main content area has id='main-content'."""
        response = api.get("/login")
        assert response.status_code == 200
        
        parser = HTMLElementFinder()
        parser.feed(response.text)
        
        assert parser.main_content_found, "Element with id='main-content' not found"

    def test_skip_link_present_in_register_page(self, api):
        """Skip-to-content link exists in register page HTML."""
        response = api.get("/register")
        assert response.status_code == 200
        
        parser = HTMLElementFinder()
        parser.feed(response.text)
        
        assert parser.skip_link_found, "Skip-to-content link not found in register page"


# ---------------------------------------------------------------------------
# .hidden utility class
# ---------------------------------------------------------------------------

class TestHiddenUtilityClass:
    def test_hidden_class_in_css(self, api):
        """The .hidden utility class is defined in CSS."""
        response = api.get("/static/css/style.css")
        assert response.status_code == 200
        
        # Check for .hidden class definition
        assert ".hidden" in response.text, ".hidden class not found in CSS"
        assert "display: none !important" in response.text, \
            ".hidden class doesn't use display: none !important"

    def test_skip_link_css_defined(self, api):
        """Skip-to-content link CSS is defined."""
        response = api.get("/static/css/style.css")
        assert response.status_code == 200
        
        # Check for skip-to-content CSS
        assert ".skip-to-content" in response.text, \
            ".skip-to-content CSS not found"
        assert "position: absolute" in response.text, \
            ".skip-to-content doesn't use absolute positioning"
        assert "top: -9999px" in response.text or "top: -9999" in response.text, \
            ".skip-to-content doesn't hide off-screen"

    def test_skip_link_focus_css_defined(self, api):
        """Skip-to-content link focus CSS is defined."""
        response = api.get("/static/css/style.css")
        assert response.status_code == 200
        
        # Check for skip-to-content:focus CSS
        assert ".skip-to-content:focus" in response.text, \
            ".skip-to-content:focus CSS not found"
        assert "top: 1rem" in response.text, \
            ".skip-to-content:focus doesn't position at top: 1rem"
