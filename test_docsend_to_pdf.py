import json
import tempfile
import unittest
from pathlib import Path

from docsend_to_pdf import load_cookies_from_file


class LoadCookiesFromFileTests(unittest.TestCase):
    def test_loads_cookies_from_top_level_cookies_object(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cookies_path = Path(tmpdir) / "cookies.json"
            cookies_path.write_text(
                json.dumps(
                    {
                        "cookies": {
                            "_v_": "session-cookie",
                            "_dss_": "docsend-session",
                            "_us_": "user-session",
                        }
                    }
                ),
                encoding="utf-8",
            )

            cookies = load_cookies_from_file(cookies_path)

        self.assertEqual(
            cookies,
            {
                "_v_": "session-cookie",
                "_dss_": "docsend-session",
                "_us_": "user-session",
            },
        )


if __name__ == "__main__":
    unittest.main()
