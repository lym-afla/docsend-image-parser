"""Regression tests for page-preserving PDF compilation fallbacks."""

import io
import tempfile
import unittest
from contextlib import chdir
from pathlib import Path
from unittest.mock import patch

from compile_to_pdf import (
    create_pdf_with_tesseract_default,
    create_pdf_with_tesseract_fallback,
)
from PIL import Image
from PyPDF2 import PdfReader
from reportlab.pdfgen import canvas


def _page_image_data(page) -> bytes:
    """Return the decoded bytes of the first image drawn on a PDF page."""
    resources = page["/Resources"].get_object()
    images = resources["/XObject"].get_object()
    return next(iter(images.values())).get_object().get_data()


def _single_image_pdf_bytes(image_path: Path) -> bytes:
    """Create an independent one-page PDF fixture containing one source image."""
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(12, 8))
    pdf.drawImage(str(image_path), 0, 0, width=12, height=8)
    pdf.save()
    return buffer.getvalue()


class TesseractFallbackTests(unittest.TestCase):
    """Ensure per-page OCR failures retain the matching source image."""

    def test_ocr_failure_on_second_page_preserves_second_image(self):
        compilers = (
            create_pdf_with_tesseract_default,
            create_pdf_with_tesseract_fallback,
        )
        for compiler in compilers:
            with self.subTest(compiler=compiler.__name__), tempfile.TemporaryDirectory(
                ignore_cleanup_errors=True
            ) as tmpdir:
                root = Path(tmpdir)
                image_dir = root / "images"
                image_dir.mkdir()
                Image.new("RGB", (12, 8), "red").save(image_dir / "page_001.png")
                Image.new("RGB", (12, 8), "blue").save(image_dir / "page_002.png")
                output_pdf = root / f"{compiler.__name__}.pdf"
                first_page_pdf = _single_image_pdf_bytes(image_dir / "page_001.png")

                with chdir(root), patch(
                    "compile_to_pdf.os.path.exists",
                    side_effect=lambda path: str(path).lower().endswith("tesseract.exe"),
                ), patch(
                    "pytesseract.image_to_pdf_or_hocr",
                    side_effect=(first_page_pdf, RuntimeError("synthetic OCR failure")),
                ), patch(
                    "builtins.print"
                ):
                    self.assertTrue(compiler(str(image_dir), str(output_pdf), "eng"))

                with output_pdf.open("rb") as handle:
                    pages = PdfReader(handle).pages
                    page_images = [_page_image_data(page)[:3] for page in pages]
                self.assertEqual(page_images, [b"\xff\x00\x00", b"\x00\x00\xff"])


if __name__ == "__main__":
    unittest.main()
