"""Contract tests for safe, approval-gated DocSend cookie refreshing."""

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from docsend_access import AccessProbeResult
from docsend_cookie_refresh import (
    BrowserAuthorizationResult,
    CookieRefreshRequest,
    PlaywrightBrowserAuthorizer,
    main,
    refresh_cookies,
)


class FakeLocator:
    """Small Playwright locator fake driven by the synthetic page state."""

    def __init__(self, page, kind):
        self.page = page
        self.kind = kind

    @property
    def first(self):
        """Mirror Playwright's first-locator property."""
        return self

    def count(self):
        """Return whether this locator is present in the current page state."""
        if self.kind in {"email", "passcode"}:
            return int(self.page.state == self.kind)
        if self.kind == "submit":
            return int(self.page.state in {"email", "passcode"})
        return 0

    def fill(self, value):
        """Record a filled authorization step without logging its value."""
        if self.count():
            self.page.filled_step = self.kind

    def click(self):
        """Advance only after the input for the current step was filled."""
        if self.page.state == self.page.filled_step == "email":
            self.page.state = "passcode"
            self.page.filled_step = None
        elif self.page.state == self.page.filled_step == "passcode":
            self.page.state = "viewer"
            self.page.filled_step = None

    def wait_for(self, **_kwargs):
        """Expose the synthetic viewer only after authorization completes."""
        if self.kind != "viewer" or self.page.state != "viewer":
            raise TimeoutError("synthetic locator unavailable")

    def inner_text(self, **_kwargs):
        """Return only a synthetic challenge marker for gate detection."""
        return "captcha" if self.page.state == "captcha" else ""


class FakePage:
    """Interactive page fake supporting sequential and human authorization."""

    def __init__(self, state):
        self.state = state
        self.filled_step = None
        self.browser = None

    def goto(self, *_args, **_kwargs):
        """Accept navigation to the already reviewed synthetic URL."""

    def get_by_label(self, pattern):
        """Resolve email and passcode labels against the current state."""
        kind = "email" if "email" in pattern.pattern.lower() else "passcode"
        return FakeLocator(self, kind)

    def locator(self, selector):
        """Resolve the production selectors needed by the authorization flow."""
        if selector == "body":
            return FakeLocator(self, "body")
        if "data-testid" in selector:
            return FakeLocator(self, "viewer")
        if "button[type='submit']" in selector:
            return FakeLocator(self, "submit")
        return FakeLocator(self, "missing")

    def wait_for_timeout(self, _timeout):
        """Simulate a human completing the visible CAPTCHA while Chrome stays open."""
        if self.browser.closed:
            raise AssertionError("browser closed before human interaction")
        if self.state == "captcha":
            self.state = "viewer"


class FakeBrowserContext:
    """Playwright browser-context fake with complete cookie records."""

    def __init__(self, page):
        self.page = page
        self.closed = False

    def new_page(self):
        """Return the configured synthetic page."""
        return self.page

    def cookies(self):
        """Return the full documented Playwright cookie shape."""
        return [
            {
                "name": "_v_",
                "value": "candidate-cookie",
                "domain": ".docsend.com",
                "path": "/",
                "expires": -1,
                "httpOnly": True,
                "secure": True,
                "sameSite": "Lax",
            }
        ]

    def close(self):
        """Record browser-context closure."""
        self.closed = True


class FakeBrowser:
    """Visible browser fake used without launching a live browser."""

    def __init__(self, page):
        self.closed = False
        self.context = FakeBrowserContext(page)
        page.browser = self

    def new_context(self):
        """Return the configured browser context."""
        return self.context

    def close(self):
        """Record final browser closure."""
        self.closed = True


class FakePlaywrightManager:
    """Context-manager fake for the Playwright entry point."""

    def __init__(self, page):
        self.browser = FakeBrowser(page)
        self.chromium = self

    def launch(self, **_kwargs):
        """Return a visible synthetic browser."""
        return self.browser

    def __enter__(self):
        """Return the synthetic Playwright object."""
        return self

    def __exit__(self, *_args):
        """Leave resource closure to the production finally block."""


class FakeAuthorizer:
    """Browser boundary fake that returns configured non-production cookies."""

    def __init__(self, result):
        self.result = result
        self.requests = []

    def authorize(self, request):
        """Record the request and return the configured authorization result."""
        self.requests.append(request)
        return self.result


class CookieRefreshTests(unittest.TestCase):
    """Exercise orchestration without launching a browser or making HTTP requests."""

    def test_refresh_persists_only_after_authorized_second_probe(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cookie_file = Path(tmpdir) / "cookies.json"
            cookie_file.write_text('{"cookies":{"_v_":"old"}}', encoding="utf-8")
            authorizer = FakeAuthorizer(
                BrowserAuthorizationResult(
                    "authorized", {"_v_": "new-v", "_dss_": "new-d"}, "viewer_ready"
                )
            )
            probes = []

            def probe(cookies, document_id, view_id):
                probes.append((dict(cookies), document_id, view_id))
                return (
                    AccessProbeResult("authentication_required", None, "http_403")
                    if len(probes) == 1
                    else AccessProbeResult("authorized", 7, "page_1_available")
                )

            result = refresh_cookies(self.request(cookie_file), authorizer=authorizer, probe=probe)

            self.assertEqual(result.status, "refreshed")
            self.assertTrue(result.cookie_file_updated)
            self.assertEqual(len(probes), 2)
            self.assertEqual(probes[0][0], {"_v_": "old"})
            self.assertEqual(probes[1][0], {"_v_": "new-v", "_dss_": "new-d"})
            persisted = json.loads(cookie_file.read_text(encoding="utf-8"))
            self.assertEqual(persisted["cookies"], {"_v_": "new-v", "_dss_": "new-d"})

    def test_wrong_passcode_preserves_previous_cookie_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cookie_file = Path(tmpdir) / "cookies.json"
            original = '{"cookies":{"_v_":"old-cookie"}}'
            cookie_file.write_text(original, encoding="utf-8")
            authorizer = FakeAuthorizer(
                BrowserAuthorizationResult("authorized", {"_v_": "bad-cookie"}, "viewer_ready")
            )

            result = refresh_cookies(
                self.request(cookie_file, passcode="wrong-passcode"),
                authorizer=authorizer,
                probe=lambda *_: AccessProbeResult("authentication_required", None, "http_403"),
            )

            self.assertEqual(result.status, "authentication_required")
            self.assertFalse(result.cookie_file_updated)
            self.assertEqual(cookie_file.read_text(encoding="utf-8"), original)

    def test_captcha_or_otp_requires_user_interaction(self):
        for marker in ("captcha_detected", "otp_detected"):
            with self.subTest(marker=marker), tempfile.TemporaryDirectory() as tmpdir:
                authorizer = FakeAuthorizer(
                    BrowserAuthorizationResult("user_interaction_required", {}, marker)
                )

                result = refresh_cookies(
                    self.request(Path(tmpdir) / "cookies.json"),
                    authorizer=authorizer,
                    probe=lambda *_: AccessProbeResult("authentication_required", None, "http_403"),
                )

                self.assertEqual(result.status, "user_interaction_required")
                self.assertFalse(result.cookie_file_updated)
                self.assertEqual(result.detail_code, marker)

    def test_browser_advances_sequential_email_then_passcode_steps(self):
        manager = FakePlaywrightManager(FakePage("email"))
        with patch("playwright.sync_api.sync_playwright", return_value=manager):
            result = PlaywrightBrowserAuthorizer().authorize(
                self.request(Path("unused-cookies.json"))
            )

        self.assertEqual(result.status, "authorized")
        self.assertEqual(result.cookies, {"_v_": "candidate-cookie"})
        self.assertEqual(result.detail_code, "viewer_ready")
        self.assertTrue(manager.browser.closed)

    def test_human_captcha_completion_is_reprobed_before_cookie_persistence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cookie_file = Path(tmpdir) / "cookies.json"
            original = '{"cookies":{"_v_":"old-cookie"}}'
            cookie_file.write_text(original, encoding="utf-8")
            manager = FakePlaywrightManager(FakePage("captcha"))
            probes = []

            def probe(cookies, _document_id, _view_id):
                probes.append(dict(cookies))
                if len(probes) == 1:
                    return AccessProbeResult("authentication_required", None, "http_403")
                return AccessProbeResult("authorized", 2, "page_1_available")

            with patch("playwright.sync_api.sync_playwright", return_value=manager):
                result = refresh_cookies(
                    self.request(cookie_file),
                    authorizer=PlaywrightBrowserAuthorizer(),
                    probe=probe,
                )

            self.assertEqual(result.status, "refreshed")
            self.assertEqual(probes, [{"_v_": "old-cookie"}, {"_v_": "candidate-cookie"}])
            self.assertEqual(
                json.loads(cookie_file.read_text(encoding="utf-8"))["cookies"],
                {"_v_": "candidate-cookie"},
            )
            self.assertTrue(manager.browser.closed)

    def test_result_payload_and_cli_output_never_include_authorization_values(self):
        email = "private@example.test"
        passcode = "private-passcode"
        with tempfile.TemporaryDirectory() as tmpdir:
            request_payload = {
                "url": "https://docsend.com/view/document/d/view",
                "cookie_file": str(Path(tmpdir) / "cookies.json"),
                "email": email,
                "passcode": passcode,
                "approved_at": "2026-08-10T21:30:00+03:00",
            }
            stdout = io.StringIO()
            exit_code = main(
                stdin=io.StringIO(json.dumps(request_payload)),
                stdout=stdout,
                authorizer=FakeAuthorizer(
                    BrowserAuthorizationResult("user_interaction_required", {}, "otp_detected")
                ),
                probe=lambda *_: AccessProbeResult("authentication_required", None, "http_403"),
                argv=[],
            )

        output = stdout.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(output)["status"], "user_interaction_required")
        self.assertNotIn(email, output)
        self.assertNotIn(passcode, output)

    def test_malformed_cli_json_returns_bounded_error(self):
        stdout = io.StringIO()

        exit_code = main(stdin=io.StringIO("not json"), stdout=stdout, argv=[])

        self.assertEqual(exit_code, 2)
        self.assertEqual(
            json.loads(stdout.getvalue()),
            {
                "status": "invalid_request",
                "probe_status": "not_run",
                "cookie_file_updated": False,
                "updated_at": None,
                "detail_code": "invalid_input",
            },
        )

    @staticmethod
    def request(cookie_file, passcode="test-passcode"):
        """Build a synthetic, approved refresh request."""
        return CookieRefreshRequest(
            url="https://docsend.com/view/document/d/view",
            cookie_file=Path(cookie_file),
            email="test@example.test",
            passcode=passcode,
            approved_at="2026-08-10T21:30:00+03:00",
        )


if __name__ == "__main__":
    unittest.main()
