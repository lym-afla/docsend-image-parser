"""Tests for validated, secret-safe DocSend document recovery."""

import io
import json
import tempfile
import unittest
from contextlib import ExitStack, chdir
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import requests
from docsend_access import AccessProbeResult
from docsend_image_downloader import (
    DocSendImageDownloader,
    DownloadResult,
    ImageFetchError,
    PageDataResult,
    validate_image_bytes,
)
from docsend_recover import recover_document, write_command_response
from PIL import Image
from PyPDF2 import PdfWriter


def image_bytes(image_format: str) -> bytes:
    """Create a small, fully decodable in-memory image fixture."""
    buffer = io.BytesIO()
    Image.new("RGB", (12, 8), "white").save(buffer, format=image_format)
    return buffer.getvalue()


def write_pdf(path: Path, page_count: int) -> None:
    """Write a valid PDF fixture with the requested number of blank pages."""
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=72, height=72)
    with path.open("wb") as handle:
        writer.write(handle)


def pdf_bytes(page_count: int) -> bytes:
    """Return a valid in-memory PDF fixture with blank pages."""
    buffer = io.BytesIO()
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=72, height=72)
    writer.write(buffer)
    return buffer.getvalue()


class FixtureDownloader(DocSendImageDownloader):
    """Downloader fake retaining the production validation and sequence logic."""

    def __init__(self, pages):
        super().__init__()
        self.pages = pages

    def fetch_page_data(self, document_id, view_id, page_number):
        """Return configured page metadata without a live DocSend request."""
        value = self.pages.get(page_number)
        if value == "end":
            return PageDataResult("end", None, None, "end_of_document")
        if value is None:
            return PageDataResult("error", None, None, "page_unavailable")
        expected_pages, _ = value
        return PageDataResult(
            "available", f"fixture:{page_number}", expected_pages, "page_available"
        )

    def fetch_image_bytes(self, image_url):
        """Return configured bytes without exposing or requesting a signed URL."""
        page_number = int(image_url.rsplit(":", 1)[1])
        return self.pages[page_number][1]


class ImageValidationTests(unittest.TestCase):
    """Image validation accepts real images independent of HTTP media type."""

    def test_accepts_decodable_jpeg_png_and_webp_signatures(self):
        for image_format, extension in (("JPEG", ".jpg"), ("PNG", ".png"), ("WEBP", ".webp")):
            with self.subTest(image_format=image_format):
                self.assertEqual(validate_image_bytes(image_bytes(image_format)), extension)

    def test_rejects_invalid_bytes(self):
        self.assertIsNone(validate_image_bytes(b"binary/octet-stream but not an image"))

    def test_signed_image_request_exception_is_sanitized(self):
        signed_url = "https://signed.example/page?secret=credential"

        class FailingSession:
            def get(self, url, **kwargs):
                raise requests.ConnectionError(f"failed to fetch {url}")

        downloader = DocSendImageDownloader(session=FailingSession())

        with self.assertRaises(ImageFetchError) as caught:
            downloader.fetch_image_bytes(signed_url)

        self.assertEqual(str(caught.exception), "image_request_failed")
        self.assertNotIn(signed_url, repr(caught.exception))

    def test_signed_image_content_read_exception_is_sanitized(self):
        signed_url = "https://signed.example/page?secret=credential"

        class InterruptedResponse:
            def raise_for_status(self):
                return None

            @property
            def content(self):
                raise requests.exceptions.ChunkedEncodingError(f"interrupted {signed_url}")

        class InterruptedSession:
            def get(self, url, **kwargs):
                return InterruptedResponse()

        downloader = DocSendImageDownloader(session=InterruptedSession())

        with self.assertRaises(ImageFetchError) as caught:
            downloader.fetch_image_bytes(signed_url)

        self.assertEqual(str(caught.exception), "image_request_failed")
        self.assertNotIn(signed_url, repr(caught.exception))


class ContinuousDownloadTests(unittest.TestCase):
    """Downloader results distinguish complete documents from page gaps."""

    def test_zero_pages_fails_with_bounded_code(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = FixtureDownloader({1: "end"}).download_document_images_verified(
                "doc", "view", Path(tmpdir), expected_pages=None
            )

        self.assertEqual(result, DownloadResult("incomplete", 0, None, "page_1_unavailable"))

    def test_missing_middle_page_fails_and_preserves_downloaded_page(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            result = FixtureDownloader(
                {1: (3, image_bytes("JPEG")), 2: None, 3: (3, image_bytes("PNG"))}
            ).download_document_images_verified("doc", "view", output_dir, expected_pages=3)

            self.assertTrue((output_dir / "page_001.jpg").is_file())

        self.assertEqual(result, DownloadResult("incomplete", 1, 3, "missing_page"))


class RecoveryTests(unittest.TestCase):
    """Recovery orchestration probes, downloads, compiles, and validates."""

    def payload(self, root: Path) -> dict[str, object]:
        """Return a complete command payload using only temporary paths."""
        return {
            "url": "https://docsend.com/view/doc/d/view",
            "cookie_file": str(root / "cookies.json"),
            "image_directory": str(root / "images"),
            "target_pdf_path": str(root / "document.pdf"),
            "ocr_mode": "none",
            "language": "eng",
        }

    def test_authentication_required_does_not_construct_downloader(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            payload = self.payload(root)
            (root / "cookies.json").write_text('{"cookies": {}}', encoding="utf-8")

            def forbidden_factory(*args, **kwargs):
                raise AssertionError("downloads must not start")

            result = recover_document(
                payload,
                probe=lambda *args, **kwargs: AccessProbeResult(
                    "authentication_required", None, "http_403"
                ),
                downloader_factory=forbidden_factory,
            )

        self.assertEqual(result["status"], "authentication_required")
        self.assertEqual(result["detail_code"], "http_403")

    def test_pdf_page_count_mismatch_is_incomplete(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            payload = self.payload(root)
            (root / "cookies.json").write_text('{"cookies": {}}', encoding="utf-8")

            result = recover_document(
                payload,
                probe=lambda *args, **kwargs: AccessProbeResult(
                    "authorized", 3, "page_1_available"
                ),
                downloader_factory=lambda **kwargs: FixtureDownloader(
                    {
                        1: (3, image_bytes("JPEG")),
                        2: (3, image_bytes("PNG")),
                        3: (3, image_bytes("WEBP")),
                    }
                ),
                compiler=lambda image_dir, output_pdf, **kwargs: (
                    write_pdf(Path(output_pdf), 2) or True
                ),
            )

            self.assertEqual(result["detail_code"], "pdf_page_count_mismatch")
            self.assertEqual(result["pdf_page_count"], 2)
            self.assertTrue((root / "images" / "page_003.webp").is_file())

    def test_stale_target_is_not_validated_when_compiler_writes_elsewhere(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            payload = self.payload(root)
            target_pdf = Path(payload["target_pdf_path"])
            (root / "cookies.json").write_text('{"cookies": {}}', encoding="utf-8")
            write_pdf(target_pdf, 3)

            def redirected_compiler(image_dir, output_pdf, **kwargs):
                write_pdf(Path(output_pdf).with_stem("document_alternative"), 3)
                return True

            result = recover_document(
                payload,
                probe=lambda *args, **kwargs: AccessProbeResult(
                    "authorized", 3, "page_1_available"
                ),
                downloader_factory=lambda **kwargs: FixtureDownloader(
                    {
                        1: (3, image_bytes("JPEG")),
                        2: (3, image_bytes("PNG")),
                        3: (3, image_bytes("WEBP")),
                    }
                ),
                compiler=redirected_compiler,
            )

        self.assertEqual(result["status"], "incomplete")
        self.assertFalse(result["pdf_created"])
        self.assertEqual(result["detail_code"], "invalid_pdf")

    def test_successful_three_page_ocr_free_recovery(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            payload = self.payload(root)
            (root / "cookies.json").write_text('{"cookies": {}}', encoding="utf-8")

            result = recover_document(
                payload,
                probe=lambda *args, **kwargs: AccessProbeResult(
                    "authorized", 3, "page_1_available"
                ),
                downloader_factory=lambda **kwargs: FixtureDownloader(
                    {
                        1: (3, image_bytes("JPEG")),
                        2: (3, image_bytes("PNG")),
                        3: (3, image_bytes("WEBP")),
                    }
                ),
            )

        self.assertEqual(
            result,
            {
                "status": "success",
                "probe_status": "authorized",
                "downloaded_pages": 3,
                "expected_pages": 3,
                "pdf_created": True,
                "pdf_page_count": 3,
                "ocr_mode": "none",
                "detail_code": "recovery_complete",
            },
        )

    def test_tesseract_recovery_supports_bare_output_filename(self):
        self._assert_bare_output_filename_recovery("tesseract")

    def test_ocrmypdf_tesseract_fallback_supports_bare_output_filename(self):
        self._assert_bare_output_filename_recovery("ocrmypdf")

    def _assert_bare_output_filename_recovery(self, ocr_mode):
        """Recover one page through mocked OCR boundaries into the current directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            payload = self.payload(root)
            payload["target_pdf_path"] = "recovered-document.pdf"
            payload["ocr_mode"] = ocr_mode
            (root / "cookies.json").write_text('{"cookies": {}}', encoding="utf-8")

            patches = [
                patch(
                    "compile_to_pdf.os.path.exists",
                    side_effect=lambda path: str(path).lower().endswith("tesseract.exe"),
                ),
                patch("pytesseract.image_to_pdf_or_hocr", return_value=pdf_bytes(1)),
            ]
            if ocr_mode == "ocrmypdf":
                patches.extend(
                    [
                        patch("compile_to_pdf.shutil.which", return_value="ocrmypdf"),
                        patch(
                            "compile_to_pdf.subprocess.run",
                            return_value=SimpleNamespace(
                                returncode=1, stderr="synthetic OCR failure"
                            ),
                        ),
                    ]
                )

            with chdir(root), ExitStack() as stack:
                for active_patch in patches:
                    stack.enter_context(active_patch)
                result = recover_document(
                    payload,
                    probe=lambda *_args, **_kwargs: AccessProbeResult(
                        "authorized", 1, "page_1_available"
                    ),
                    downloader_factory=lambda **_kwargs: FixtureDownloader(
                        {1: (1, image_bytes("PNG"))}
                    ),
                )

            self.assertEqual(result["status"], "success")
            self.assertEqual(result["pdf_page_count"], 1)
            self.assertTrue((root / "recovered-document.pdf").is_file())

    def test_command_output_is_one_bounded_json_object(self):
        output = io.StringIO()
        write_command_response(
            {
                "status": "failed",
                "probe_status": "unavailable",
                "downloaded_pages": 0,
                "expected_pages": None,
                "pdf_created": False,
                "pdf_page_count": None,
                "ocr_mode": "none",
                "detail_code": "invalid_input",
                "secret": "must not appear",
            },
            output,
        )

        decoded = json.loads(output.getvalue())
        self.assertNotIn("secret", decoded)
        self.assertEqual(output.getvalue().count("\n"), 1)


if __name__ == "__main__":
    unittest.main()
