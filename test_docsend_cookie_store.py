"""Tests for the secret-safe DocSend cookie persistence boundary."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from docsend_cookie_store import (
    CookieStoreError,
    load_cookie_document,
    replace_cookie_document,
)


class CookieStoreTests(unittest.TestCase):
    """Exercise persistent cookie documents using only synthetic values."""

    def test_loads_cookies_and_metadata_from_top_level_envelope(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "cookies.json"
            path.write_text(
                json.dumps(
                    {
                        "cookies": {"_v_": "test-v"},
                        "metadata": {"source": "test"},
                    }
                ),
                encoding="utf-8",
            )

            document = load_cookie_document(path)

        self.assertEqual(document.cookies, {"_v_": "test-v"})
        self.assertEqual(document.metadata, {"source": "test"})

    def test_loads_legacy_flat_cookie_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "cookies.json"
            path.write_text(json.dumps({"_v_": "test-v"}), encoding="utf-8")

            document = load_cookie_document(path)

        self.assertEqual(document.cookies, {"_v_": "test-v"})
        self.assertEqual(document.metadata, {})

    def test_failed_replace_preserves_previous_cookie_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "cookies.json"
            path.write_text('{"cookies":{"_v_":"old"}}', encoding="utf-8")
            with patch("docsend_cookie_store.os.replace", side_effect=OSError("blocked")):
                with self.assertRaises(CookieStoreError):
                    replace_cookie_document(
                        path,
                        {"_v_": "new", "_dss_": "new"},
                        self._metadata(),
                    )
            self.assertIn('"old"', path.read_text(encoding="utf-8"))

    def test_replace_persists_only_parser_cookies_and_approved_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "cookies.json"

            replace_cookie_document(
                path,
                {"_v_": "test-v", "_dss_": "test-dss", "_us_": "test-us", "_ga": "ignore"},
                {**self._metadata(), "unapproved": "ignore"},
            )

            persisted = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(
            persisted["cookies"],
            {"_v_": "test-v", "_dss_": "test-dss", "_us_": "test-us"},
        )
        self.assertEqual(persisted["metadata"], self._metadata())

    def test_replace_uses_closed_sibling_temporary_file_on_windows(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "cookies.json"
            real_replace = os.replace

            def replace_after_asserting_temp_file_is_sibling(source, destination):
                self.assertEqual(Path(source).parent, path.parent)
                self.assertEqual(Path(destination), path)
                self.assertTrue(Path(source).exists())
                real_replace(source, destination)

            with patch("docsend_cookie_store.os.name", "nt"), patch(
                "docsend_cookie_store.os.replace",
                side_effect=replace_after_asserting_temp_file_is_sibling,
            ):
                replace_cookie_document(path, {"_v_": "test-v"}, self._metadata())

            self.assertEqual(load_cookie_document(path).cookies, {"_v_": "test-v"})

    @staticmethod
    def _metadata():
        return {
            "updated_at": "2026-08-10T21:30:00+03:00",
            "source": "test Playwright session",
            "docsend_host": "altitude.docsend.com",
            "document_id": "doc",
            "view_id": "view",
        }


if __name__ == "__main__":
    unittest.main()
