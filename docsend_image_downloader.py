"""Download DocSend page images with byte and sequence validation."""

import io
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests
from PIL import Image

_REQUEST_TIMEOUT = (5, 30)
_IMAGE_EXTENSIONS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}


class ImageFetchError(Exception):
    """Bounded signed-image request failure without URL or response details."""


@dataclass(frozen=True)
class PageDataResult:
    """Bounded result for one page-data request.

    ``status`` is ``available``, ``end``, or ``error``. Signed image URLs are
    kept internal and must never be serialized by callers.
    """

    status: str
    image_url: str | None
    expected_pages: int | None
    detail_code: str


@dataclass(frozen=True)
class DownloadResult:
    """Validated page-download outcome without sensitive request details."""

    status: str
    downloaded_pages: int
    expected_pages: int | None
    detail_code: str


def validate_image_bytes(content: bytes) -> str | None:
    """Return a safe extension for a verified JPEG, PNG, or WebP image.

    Validation requires both the format's binary signature and successful
    Pillow decoding. HTTP ``Content-Type`` is intentionally irrelevant.
    """
    if content.startswith(b"\xff\xd8\xff"):
        expected_format = "JPEG"
    elif content.startswith(b"\x89PNG\r\n\x1a\n"):
        expected_format = "PNG"
    elif len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        expected_format = "WEBP"
    else:
        return None

    try:
        with Image.open(io.BytesIO(content)) as image:
            image.verify()
            actual_format = image.format
        with Image.open(io.BytesIO(content)) as image:
            image.load()
    except OSError, SyntaxError, ValueError:
        return None

    if actual_format != expected_format:
        return None
    return _IMAGE_EXTENSIONS[expected_format]


class DocSendImageDownloader:
    """Requests-based downloader that validates every saved page image."""

    def __init__(self, cookies: Mapping[str, str] | None = None, user_agent=None, session=None):
        """Initialize with optional cookies and an injectable HTTP session."""
        self.session = session or requests.Session()
        self.headers = {
            "User-Agent": user_agent
            or (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/120 Safari/537.36"
            ),
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://docsend.com/",
        }
        self.base_url = "https://docsend.com"
        if cookies:
            self.session.cookies.update(cookies)

    def extract_document_info_from_url(self, docsend_url):
        """Return document and optional view identifiers from a DocSend URL."""
        try:
            parts = urlparse(docsend_url).path.strip("/").split("/")
            if len(parts) >= 2 and parts[0] == "view" and parts[1]:
                view_id = parts[3] if len(parts) >= 4 and parts[2] == "d" else ""
                return parts[1], view_id
        except TypeError, ValueError:
            pass
        return None, None

    def fetch_page_data(self, document_id, view_id, page_number):
        """Fetch one page's metadata and classify its availability safely."""
        if view_id:
            url = f"{self.base_url}/view/{document_id}/d/{view_id}/page_data/{page_number}"
        else:
            url = f"{self.base_url}/view/{document_id}/page_data/{page_number}"
        try:
            response = self.session.get(
                url,
                headers=self.headers,
                params={"viewLoadTime": int(time.time()), "timezoneOffset": int(time.timezone)},
                timeout=_REQUEST_TIMEOUT,
            )
        except requests.Timeout:
            return PageDataResult("error", None, None, "request_timeout")
        except requests.RequestException:
            return PageDataResult("error", None, None, "request_error")

        if response.status_code == 404:
            return PageDataResult("end", None, None, "end_of_document")
        if response.status_code in (401, 403):
            return PageDataResult("error", None, None, "authentication_required")
        if response.status_code < 200 or response.status_code >= 300:
            return PageDataResult("error", None, None, "http_error")
        try:
            payload = response.json()
        except TypeError, ValueError:
            return PageDataResult("error", None, None, "invalid_page_data")
        if not isinstance(payload, Mapping) or not isinstance(payload.get("imageUrl"), str):
            return PageDataResult("error", None, _page_count(payload), "missing_image_url")
        return PageDataResult(
            "available", payload["imageUrl"], _page_count(payload), "page_available"
        )

    def get_page_data(self, document_id, view_id, page_number):
        """Return legacy page data shape for callers that predate validation."""
        result = self.fetch_page_data(document_id, view_id, page_number)
        if result.status != "available":
            return None
        return {"imageUrl": result.image_url, "pageCount": result.expected_pages}

    def fetch_image_bytes(self, image_url):
        """Fetch signed image bytes or raise a sanitized ``ImageFetchError``."""
        try:
            response = self.session.get(
                image_url, headers=self.headers, timeout=_REQUEST_TIMEOUT
            )
            response.raise_for_status()
        except requests.RequestException:
            raise ImageFetchError("image_request_failed") from None
        return response.content

    def download_image(self, image_url, output_dir, page_number):
        """Download and save one image only after byte-level validation."""
        try:
            content = self.fetch_image_bytes(image_url)
        except ImageFetchError:
            return None
        extension = validate_image_bytes(content)
        if extension is None:
            return None
        destination = Path(output_dir)
        destination.mkdir(parents=True, exist_ok=True)
        path = destination / f"page_{page_number:03d}{extension}"
        path.write_bytes(content)
        return str(path)

    def download_document_images_verified(
        self, document_id, view_id, output_dir, expected_pages=None
    ):
        """Download a continuous page sequence and return validated counts.

        A declared count is authoritative. Without one, only a page-data 404 is
        treated as the documented end of the document.
        """
        downloaded = 0
        page_number = 1
        known_count = (
            expected_pages if isinstance(expected_pages, int) and expected_pages > 0 else None
        )

        while known_count is None or page_number <= known_count:
            page = self.fetch_page_data(document_id, view_id, page_number)
            if page.expected_pages:
                if known_count is not None and known_count != page.expected_pages:
                    return DownloadResult(
                        "incomplete", downloaded, known_count, "page_count_changed"
                    )
                known_count = page.expected_pages

            if page.status == "end":
                if page_number == 1:
                    return DownloadResult("incomplete", 0, known_count, "page_1_unavailable")
                if known_count is not None and page_number <= known_count:
                    return DownloadResult("incomplete", downloaded, known_count, "missing_page")
                break
            if page.status != "available" or not page.image_url:
                code = "page_1_unavailable" if page_number == 1 else "missing_page"
                return DownloadResult("incomplete", downloaded, known_count, code)
            if self.download_image(page.image_url, output_dir, page_number) is None:
                code = "invalid_image_bytes" if page_number == 1 else "missing_page"
                return DownloadResult("incomplete", downloaded, known_count, code)
            downloaded += 1
            page_number += 1

        if downloaded == 0:
            return DownloadResult("incomplete", 0, known_count, "page_1_unavailable")
        if known_count is not None and downloaded != known_count:
            return DownloadResult("incomplete", downloaded, known_count, "page_count_mismatch")
        return DownloadResult(
            "complete", downloaded, known_count or downloaded, "download_complete"
        )

    def download_document_images(
        self, document_id, view_id, start_page=1, end_page=None, output_dir="downloaded_images"
    ):
        """Legacy count-only wrapper retained for the original converter."""
        if start_page != 1:
            return 0
        result = self.download_document_images_verified(
            document_id, view_id, output_dir, expected_pages=end_page
        )
        return result.downloaded_pages


def _page_count(payload):
    """Extract a positive page count from known DocSend response keys."""
    if not isinstance(payload, Mapping):
        return None
    for key in ("pageCount", "page_count", "numPages"):
        value = payload.get(key)
        if isinstance(value, int) and value > 0:
            return value
    return None


def get_cookies_from_browser():
    """Print non-sensitive directions for supplying browser cookies."""
    print("Provide authorized DocSend browser cookies through a cookie JSON file.")


def main():
    """Keep the historical module entry point informational and secret-safe."""
    get_cookies_from_browser()


if __name__ == "__main__":
    main()
