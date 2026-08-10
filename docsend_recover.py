"""Validated JSON command for recovering a DocSend document to PDF."""

import json
import sys
from collections.abc import Callable, Mapping
from contextlib import redirect_stdout
from pathlib import Path
from typing import TextIO

import requests
from compile_to_pdf import (
    create_pdf_with_ocrmypdf,
    create_pdf_with_tesseract_default,
    create_pdf_without_ocr,
)
from docsend_access import probe_access
from docsend_cookie_store import CookieStoreError, load_cookie_document
from docsend_image_downloader import DocSendImageDownloader
from PyPDF2 import PdfReader

PUBLIC_FIELDS = (
    "status",
    "probe_status",
    "downloaded_pages",
    "expected_pages",
    "pdf_created",
    "pdf_page_count",
    "ocr_mode",
    "detail_code",
)
_INPUT_FIELDS = (
    "url",
    "cookie_file",
    "image_directory",
    "target_pdf_path",
    "ocr_mode",
    "language",
)
_OCR_MODES = {"none", "tesseract", "ocrmypdf"}
_MAX_STDIN_BYTES = 64 * 1024


class _DiscardOutput:
    """Sink legacy compiler progress without retaining confidential paths."""

    def write(self, value):
        """Discard text and report its length to print-compatible callers."""
        return len(value)

    def flush(self):
        """Provide the file-like flush interface."""


def _result(
    status="failed",
    probe_status="not_run",
    downloaded_pages=0,
    expected_pages=None,
    pdf_created=False,
    pdf_page_count=None,
    ocr_mode="none",
    detail_code="invalid_input",
):
    """Construct the fixed, bounded public response object."""
    return {
        "status": status,
        "probe_status": probe_status,
        "downloaded_pages": downloaded_pages,
        "expected_pages": expected_pages,
        "pdf_created": pdf_created,
        "pdf_page_count": pdf_page_count,
        "ocr_mode": ocr_mode,
        "detail_code": detail_code,
    }


def recover_document(
    payload: Mapping[str, object],
    *,
    probe: Callable = probe_access,
    downloader_factory: Callable = DocSendImageDownloader,
    compiler: Callable | None = None,
) -> dict[str, object]:
    """Run probe-first recovery and return only the fixed public result.

    Args:
        payload: Command object containing URL, cookie/output paths, and OCR settings.
        probe: Injectable access probe for isolated tests.
        downloader_factory: Injectable downloader constructor for isolated tests.
        compiler: Optional PDF compiler accepting image/output paths and OCR settings.

    Returns:
        A bounded result with counts and classification codes; never credentials,
        signed URLs, response bodies, or document text.
    """
    normalized = _validate_payload(payload)
    if normalized is None:
        return _result()
    ocr_mode = normalized["ocr_mode"]
    document_id, view_id = _document_info(normalized["url"])
    if not document_id:
        return _result(ocr_mode=ocr_mode, detail_code="invalid_url")

    try:
        cookies = load_cookie_document(Path(normalized["cookie_file"])).cookies
    except CookieStoreError:
        return _result(ocr_mode=ocr_mode, detail_code="cookie_file_unavailable")

    session = requests.Session()
    try:
        probe_result = probe(session, document_id, view_id, cookies)
    except Exception:
        return _result(ocr_mode=ocr_mode, detail_code="probe_error")
    if probe_result.status != "authorized":
        status = (
            "authentication_required"
            if probe_result.status == "authentication_required"
            else "failed"
        )
        return _result(
            status=status,
            probe_status=probe_result.status,
            expected_pages=probe_result.page_count,
            ocr_mode=ocr_mode,
            detail_code=probe_result.detail_code,
        )

    try:
        downloader = downloader_factory(cookies=cookies, session=session)
        download = downloader.download_document_images_verified(
            document_id,
            view_id,
            Path(normalized["image_directory"]),
            expected_pages=probe_result.page_count,
        )
    except Exception:
        return _result(
            probe_status="authorized",
            expected_pages=probe_result.page_count,
            ocr_mode=ocr_mode,
            detail_code="download_error",
        )
    if download.status != "complete":
        return _result(
            status="incomplete",
            probe_status="authorized",
            downloaded_pages=download.downloaded_pages,
            expected_pages=download.expected_pages,
            ocr_mode=ocr_mode,
            detail_code=download.detail_code,
        )

    target_pdf = Path(normalized["target_pdf_path"])
    compile_function = compiler or _compile_pdf
    try:
        with redirect_stdout(_DiscardOutput()):
            created = bool(
                compile_function(
                    Path(normalized["image_directory"]),
                    target_pdf,
                    ocr_mode=ocr_mode,
                    language=normalized["language"],
                )
            )
    except Exception:
        created = False
    if not created:
        return _result(
            status="incomplete",
            probe_status="authorized",
            downloaded_pages=download.downloaded_pages,
            expected_pages=download.expected_pages,
            ocr_mode=ocr_mode,
            detail_code="pdf_creation_failed",
        )

    page_count, pdf_detail = _validate_pdf(target_pdf)
    if pdf_detail != "pdf_valid":
        return _result(
            status="incomplete",
            probe_status="authorized",
            downloaded_pages=download.downloaded_pages,
            expected_pages=download.expected_pages,
            pdf_created=target_pdf.is_file(),
            pdf_page_count=page_count,
            ocr_mode=ocr_mode,
            detail_code=pdf_detail,
        )
    if page_count != download.downloaded_pages:
        return _result(
            status="incomplete",
            probe_status="authorized",
            downloaded_pages=download.downloaded_pages,
            expected_pages=download.expected_pages,
            pdf_created=True,
            pdf_page_count=page_count,
            ocr_mode=ocr_mode,
            detail_code="pdf_page_count_mismatch",
        )
    return _result(
        status="success",
        probe_status="authorized",
        downloaded_pages=download.downloaded_pages,
        expected_pages=download.expected_pages,
        pdf_created=True,
        pdf_page_count=page_count,
        ocr_mode=ocr_mode,
        detail_code="recovery_complete",
    )


def _validate_payload(payload):
    """Return a normalized command payload when all required fields are safe strings."""
    if not isinstance(payload, Mapping):
        return None
    if any(not isinstance(payload.get(field), str) for field in _INPUT_FIELDS):
        return None
    normalized = {field: payload[field] for field in _INPUT_FIELDS}
    if any(not normalized[field] for field in _INPUT_FIELDS):
        return None
    if normalized["ocr_mode"] not in _OCR_MODES:
        return None
    return normalized


def _document_info(url):
    """Parse DocSend document and optional view identifiers without logging input."""
    return DocSendImageDownloader().extract_document_info_from_url(url)


def _compile_pdf(image_dir, output_pdf, *, ocr_mode, language):
    """Dispatch to the selected existing compiler implementation."""
    if ocr_mode == "none":
        return create_pdf_without_ocr(str(image_dir), str(output_pdf))
    if ocr_mode == "tesseract":
        return create_pdf_with_tesseract_default(str(image_dir), str(output_pdf), language)
    return create_pdf_with_ocrmypdf(str(image_dir), str(output_pdf), language)


def _validate_pdf(path):
    """Return page count and a bounded validation code for a generated PDF."""
    try:
        with Path(path).open("rb") as handle:
            if handle.read(5) != b"%PDF-":
                return None, "invalid_pdf_signature"
            handle.seek(0)
            return len(PdfReader(handle).pages), "pdf_valid"
    except OSError, ValueError:
        return None, "invalid_pdf"
    except Exception:
        return None, "invalid_pdf"


def write_command_response(result: Mapping[str, object], output: TextIO = sys.stdout) -> None:
    """Write exactly one filtered JSON object and one trailing newline."""
    public = {field: result.get(field) for field in PUBLIC_FIELDS}
    output.write(json.dumps(public, separators=(",", ":")) + "\n")


def main(input_stream: TextIO = sys.stdin, output_stream: TextIO = sys.stdout) -> int:
    """Read one bounded JSON object from stdin and emit one bounded JSON object."""
    try:
        raw = input_stream.read(_MAX_STDIN_BYTES + 1)
        if len(raw) > _MAX_STDIN_BYTES:
            result = _result(detail_code="input_too_large")
        else:
            payload = json.loads(raw)
            result = recover_document(payload)
    except json.JSONDecodeError, UnicodeError:
        result = _result(detail_code="invalid_json")
    except Exception:
        result = _result(detail_code="command_error")
    write_command_response(result, output_stream)
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
