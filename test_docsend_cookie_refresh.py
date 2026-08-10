"""Contract tests for safe, approval-gated DocSend cookie refreshing."""

import io
import json
import tempfile
import unittest
from pathlib import Path

from docsend_access import AccessProbeResult
from docsend_cookie_refresh import (
    BrowserAuthorizationResult,
    CookieRefreshRequest,
    main,
    refresh_cookies,
)


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
