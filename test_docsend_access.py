"""Focused tests for the safe DocSend page-one access probe."""

import json
import unittest

import requests

from docsend_access import AccessProbeResult, probe_access


class FakeResponse:
    """Small response fake that models only probe-facing HTTP behavior."""

    def __init__(self, status_code, payload=None, text="", json_error=None):
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self._json_error = json_error

    def json(self):
        """Return configured JSON or raise the configured decoding error."""
        if self._json_error:
            raise self._json_error
        return self._payload


class FakeSession:
    """Session fake which records the requested endpoint without network access."""

    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.requests = []

    def get(self, url, **kwargs):
        """Record a request and return the configured result."""
        self.requests.append((url, kwargs))
        if self.error:
            raise self.error
        return self.response


class ProbeAccessTests(unittest.TestCase):
    """Contract tests for classifying page-one availability safely."""

    def test_probe_reports_authorized_without_emitting_signed_url(self):
        session = FakeSession(FakeResponse(200, {"imageUrl": "https://signed.example/secret"}))

        result = probe_access(session, document_id="doc", view_id="view")

        self.assertEqual(result, AccessProbeResult("authorized", None, "page_1_available"))
        self.assertNotIn("signed.example", json.dumps(result.to_payload()))
        self.assertEqual(
            session.requests[0][0],
            "https://docsend.com/view/doc/d/view/page_data/1",
        )

    def test_probe_uses_viewless_page_data_endpoint(self):
        session = FakeSession(FakeResponse(200, {"imageUrl": "https://signed.example/secret"}))

        result = probe_access(session, document_id="doc", view_id="")

        self.assertEqual(result, AccessProbeResult("authorized", None, "page_1_available"))
        self.assertEqual(session.requests[0][0], "https://docsend.com/view/doc/page_data/1")

    def test_probe_classifies_unauthorized_statuses(self):
        for status_code, detail_code in ((401, "http_401"), (403, "http_403")):
            with self.subTest(status_code=status_code):
                result = probe_access(FakeSession(FakeResponse(status_code)), "doc", "view")

                self.assertEqual(
                    result,
                    AccessProbeResult("authentication_required", None, detail_code),
                )

    def test_probe_classifies_html_authorization_gate(self):
        response = FakeResponse(
            200,
            text="<html><title>DocSend sign in</title></html>",
            json_error=ValueError("not json"),
        )

        result = probe_access(FakeSession(response), "doc", "view")

        self.assertEqual(
            result,
            AccessProbeResult("authentication_required", None, "html_authorization_gate"),
        )
        self.assertNotIn("DocSend sign in", json.dumps(result.to_payload()))

    def test_probe_classifies_missing_document(self):
        result = probe_access(FakeSession(FakeResponse(404)), "doc", "view")

        self.assertEqual(result, AccessProbeResult("not_found", None, "http_404"))

    def test_probe_classifies_timeouts_without_exception_details(self):
        timeout = requests.Timeout("request included a secret cookie value")

        result = probe_access(FakeSession(error=timeout), "doc", "view")

        self.assertEqual(result, AccessProbeResult("unavailable", None, "request_timeout"))
        self.assertNotIn("secret", json.dumps(result.to_payload()))

    def test_probe_classifies_json_without_image_url(self):
        result = probe_access(FakeSession(FakeResponse(200, {"page": 1})), "doc", "view")

        self.assertEqual(result, AccessProbeResult("unavailable", None, "missing_image_url"))

    def test_payload_only_contains_public_contract_fields(self):
        payload = AccessProbeResult("authorized", 12, "page_1_available").to_payload()

        self.assertEqual(payload, {"status": "authorized", "page_count": 12, "detail_code": "page_1_available"})


if __name__ == "__main__":
    unittest.main()
