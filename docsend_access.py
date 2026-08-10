"""Safe, page-one access probing for DocSend documents.

The module deliberately returns only small classification codes so callers can
diagnose access without exposing credentials, signed URLs, or response bodies.
"""

from dataclasses import dataclass
from typing import Mapping

import requests


_BASE_URL = "https://docsend.com"
_REQUEST_TIMEOUT = (5, 15)


@dataclass(frozen=True)
class AccessProbeResult:
    """Outcome of a DocSend page-one availability probe.

    Attributes:
        status: Coarse, non-sensitive classification of document accessibility.
        page_count: Page count when safely available from the response, else None.
        detail_code: A bounded diagnostic code; never response or credential data.
    """

    status: str
    page_count: int | None
    detail_code: str

    def to_payload(self) -> dict[str, str | int | None]:
        """Return the stable public payload without request or response details."""
        return {
            "status": self.status,
            "page_count": self.page_count,
            "detail_code": self.detail_code,
        }


def probe_access(
    session: requests.Session,
    document_id: str,
    view_id: str,
    cookies: Mapping[str, str] | None = None,
) -> AccessProbeResult:
    """Classify whether page one is accessible using an injectable HTTP session.

    Args:
        session: Requests-compatible session used for the page-data request.
        document_id: DocSend document identifier.
        view_id: DocSend view identifier; an empty value selects the view-less URL.
        cookies: Optional cookie mapping applied to the provided session.

    Returns:
        A redacted ``AccessProbeResult`` that never includes URLs, bodies, or
        cookie values.
    """
    if cookies:
        session.cookies.update(cookies)

    url = _page_data_url(document_id, view_id)
    try:
        response = session.get(
            url,
            headers={"Accept": "application/json"},
            timeout=_REQUEST_TIMEOUT,
        )
    except requests.Timeout:
        return AccessProbeResult("unavailable", None, "request_timeout")
    except requests.RequestException:
        return AccessProbeResult("unavailable", None, "request_error")

    if response.status_code in (401, 403):
        return AccessProbeResult("authentication_required", None, f"http_{response.status_code}")
    if response.status_code == 404:
        return AccessProbeResult("not_found", None, "http_404")
    if response.status_code < 200 or response.status_code >= 300:
        return AccessProbeResult("unavailable", None, "http_error")

    try:
        payload = response.json()
    except (TypeError, ValueError):
        if _looks_like_html(response):
            return AccessProbeResult("authentication_required", None, "html_authorization_gate")
        return AccessProbeResult("unavailable", None, "invalid_response")

    if not isinstance(payload, Mapping) or not payload.get("imageUrl"):
        return AccessProbeResult("unavailable", None, "missing_image_url")

    return AccessProbeResult("authorized", _page_count(payload), "page_1_available")


def _page_data_url(document_id: str, view_id: str) -> str:
    """Build the page-one data endpoint for viewed and view-less documents."""
    if view_id:
        return f"{_BASE_URL}/view/{document_id}/d/{view_id}/page_data/1"
    return f"{_BASE_URL}/view/{document_id}/page_data/1"


def _looks_like_html(response: object) -> bool:
    """Recognize a non-JSON HTML gate without retaining its body."""
    response_text = getattr(response, "text", "")
    return isinstance(response_text, str) and "<html" in response_text.lower()


def _page_count(payload: Mapping[str, object]) -> int | None:
    """Return a positive declared count when a page-data response includes one."""
    for key in ("pageCount", "page_count", "numPages"):
        value = payload.get(key)
        if isinstance(value, int) and value > 0:
            return value
    return None
