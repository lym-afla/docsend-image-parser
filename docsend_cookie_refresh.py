"""Approval-gated, secret-safe DocSend browser cookie refresh workflow."""

import json
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, TextIO
from urllib.parse import urlparse

import requests
from docsend_access import AccessProbeResult, probe_access
from docsend_cookie_store import (
    PARSER_COOKIE_KEYS,
    CookieStoreError,
    load_cookie_document,
    replace_cookie_document,
)


@dataclass(frozen=True)
class CookieRefreshRequest:
    """Approved input required to refresh parser cookies for one DocSend URL."""

    url: str
    cookie_file: Path
    email: str | None
    passcode: str | None
    approved_at: str


@dataclass(frozen=True)
class BrowserAuthorizationResult:
    """Redacted outcome from the browser authorization boundary."""

    status: str
    cookies: Mapping[str, str]
    detail_code: str


@dataclass(frozen=True)
class CookieRefreshResult:
    """Public, bounded result of an attempted DocSend cookie refresh."""

    status: str
    probe_status: str
    cookie_file_updated: bool
    updated_at: str | None
    detail_code: str

    def to_payload(self) -> dict[str, str | bool | None]:
        """Return only the CLI contract fields, excluding authorization values."""
        return {
            "status": self.status,
            "probe_status": self.probe_status,
            "cookie_file_updated": self.cookie_file_updated,
            "updated_at": self.updated_at,
            "detail_code": self.detail_code,
        }


class BrowserAuthorizer(Protocol):
    """Boundary that obtains candidate parser cookies in an interactive browser."""

    def authorize(self, request: CookieRefreshRequest) -> BrowserAuthorizationResult:
        """Return a redacted authorization result for the approved request."""


Probe = Callable[[Mapping[str, str], str, str], AccessProbeResult]


class PlaywrightBrowserAuthorizer:
    """Interactive Chrome authorizer with bounded form and human-gate handling."""

    _MAX_AUTHORIZATION_STEPS = 6
    _HUMAN_INTERACTION_POLLS = 60
    _HUMAN_POLL_INTERVAL_MS = 1_000

    def authorize(self, request: CookieRefreshRequest) -> BrowserAuthorizationResult:
        """Navigate to one reviewed URL and collect only parser cookies on viewer success.

        The method never logs or returns credentials, input values, page text, or
        full browser cookie objects. CAPTCHA and OTP gates keep the visible
        browser open for a bounded human-completion window and are never bypassed.
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return BrowserAuthorizationResult("unavailable", {}, "playwright_unavailable")

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel="chrome", headless=False)
                context = browser.new_context()
                page = context.new_page()
                try:
                    page.goto(request.url, wait_until="domcontentloaded", timeout=30_000)
                    submitted_steps: set[str] = set()
                    for _ in range(self._MAX_AUTHORIZATION_STEPS):
                        if self._viewer_ready(page, timeout=2_000):
                            return self._authorized_cookies(context.cookies(), request.url)

                        marker = self._interaction_marker(page)
                        if marker:
                            if self._wait_for_human_completion(page):
                                return self._authorized_cookies(
                                    context.cookies(), request.url
                                )
                            remaining_marker = self._interaction_marker(page)
                            if remaining_marker:
                                return BrowserAuthorizationResult(
                                    "user_interaction_required", {}, remaining_marker
                                )
                            continue

                        filled_steps = self._fill_available_step(
                            page, request, submitted_steps
                        )
                        if filled_steps:
                            submit = page.locator(
                                "button[type='submit'], input[type='submit']"
                            ).first
                            if submit.count():
                                submit.click()
                                submitted_steps.update(filled_steps)
                        page.wait_for_timeout(500)

                    return BrowserAuthorizationResult(
                        "authentication_required", {}, "authorization_gate_not_completed"
                    )
                finally:
                    context.close()
                    browser.close()
        except Exception:
            return BrowserAuthorizationResult("unavailable", {}, "browser_error")

    @staticmethod
    def _first_input(page: object, label_pattern: str, selector: str) -> object | None:
        """Find an authorization input by its accessible label or stable attribute."""
        import re

        label_match = page.get_by_label(re.compile(label_pattern, re.IGNORECASE)).first
        if label_match.count():
            return label_match
        attribute_match = page.locator(selector).first
        return attribute_match if attribute_match.count() else None

    @staticmethod
    def _viewer_ready(page: object, timeout: int) -> bool:
        """Return whether a rendered viewer signal appears without reading document text."""
        try:
            page.locator(
                "[data-testid*='viewer' i], [data-testid*='page' i], "
                "[class*='page-viewer' i], [class*='page-container' i]"
            ).first.wait_for(state="visible", timeout=timeout)
            return True
        except Exception:
            return False

    def _fill_available_step(
        self,
        page: object,
        request: CookieRefreshRequest,
        submitted_steps: set[str],
    ) -> set[str]:
        """Fill each approved authorization value at most once per browser flow."""
        filled_steps: set[str] = set()
        if request.email and "email" not in submitted_steps:
            email_input = self._first_input(
                page,
                "email",
                "input[type='email'], input[name*='email' i], input[id*='email' i]",
            )
            if email_input is not None:
                email_input.fill(request.email)
                filled_steps.add("email")
        if request.passcode and "passcode" not in submitted_steps:
            passcode_input = self._first_input(
                page,
                "passcode|password",
                "input[type='password'], input[name*='passcode' i], "
                "input[id*='passcode' i], input[name*='password' i]",
            )
            if passcode_input is not None:
                passcode_input.fill(request.passcode)
                filled_steps.add("passcode")
        return filled_steps

    def _wait_for_human_completion(self, page: object) -> bool:
        """Keep Chrome open for a bounded CAPTCHA or OTP completion window."""
        for _ in range(self._HUMAN_INTERACTION_POLLS):
            page.wait_for_timeout(self._HUMAN_POLL_INTERVAL_MS)
            if self._viewer_ready(page, timeout=250):
                return True
            if self._interaction_marker(page, timeout=250) is None:
                return False
        return False

    @staticmethod
    def _interaction_marker(page: object, timeout: int = 2_000) -> str | None:
        """Identify a CAPTCHA or one-time-code gate without retaining page content."""
        try:
            page_text = page.locator("body").inner_text(timeout=timeout).lower()
        except Exception:
            return None
        if "captcha" in page_text or "recaptcha" in page_text:
            return "captcha_detected"
        if any(marker in page_text for marker in ("one-time", "otp", "verification code")):
            return "otp_detected"
        return None

    @staticmethod
    def _authorized_cookies(
        browser_cookies: object, url: str
    ) -> BrowserAuthorizationResult:
        """Filter browser cookie objects to non-empty parser values for the DocSend host."""
        host = urlparse(url).hostname or ""
        cookies = _filter_browser_cookies(browser_cookies, host)
        if not cookies:
            return BrowserAuthorizationResult("authentication_required", {}, "no_parser_cookies")
        return BrowserAuthorizationResult("authorized", cookies, "viewer_ready")


def refresh_cookies(
    request: CookieRefreshRequest,
    authorizer: BrowserAuthorizer,
    probe: Probe | None = None,
) -> CookieRefreshResult:
    """Refresh cookies only when the candidate succeeds at a second access probe.

    Args:
        request: Reviewed document, cookie-file, and optional authorization input.
        authorizer: Injectable interactive-browser boundary.
        probe: Injectable access probe accepting cookies, document ID, and view ID.

    Returns:
        A bounded refresh outcome. Existing cookie files are never replaced until
        candidate browser cookies have produced an authorized second probe.
    """
    try:
        document_id, view_id, host = _document_identity(request.url)
    except ValueError:
        return CookieRefreshResult("invalid_request", "not_run", False, None, "invalid_url")

    try:
        existing_cookies = _existing_cookies(request.cookie_file)
    except CookieStoreError:
        return CookieRefreshResult(
            "cookie_file_error", "not_run", False, None, "cookie_file_invalid"
        )

    access_probe = probe or _default_probe
    initial_probe = _run_probe(access_probe, existing_cookies, document_id, view_id)
    if initial_probe.status == "authorized":
        return CookieRefreshResult(
            "already_authorized", initial_probe.status, False, None, initial_probe.detail_code
        )
    if initial_probe.status != "authentication_required":
        return CookieRefreshResult(
            initial_probe.status, initial_probe.status, False, None, initial_probe.detail_code
        )

    authorization = _run_authorizer(authorizer, request)
    if authorization.status != "authorized":
        return CookieRefreshResult(
            authorization.status,
            initial_probe.status,
            False,
            None,
            authorization.detail_code,
        )

    candidate_cookies = _parser_cookies(authorization.cookies)
    if not candidate_cookies:
        return CookieRefreshResult(
            "authentication_required", initial_probe.status, False, None, "no_parser_cookies"
        )

    candidate_probe = _run_probe(access_probe, candidate_cookies, document_id, view_id)
    if candidate_probe.status != "authorized":
        return CookieRefreshResult(
            candidate_probe.status,
            candidate_probe.status,
            False,
            None,
            candidate_probe.detail_code,
        )

    updated_at = datetime.now(UTC).isoformat()
    metadata = {
        "updated_at": updated_at,
        "source": "playwright",
        "docsend_host": host,
        "document_id": document_id,
    }
    if view_id:
        metadata["view_id"] = view_id
    try:
        replace_cookie_document(request.cookie_file, candidate_cookies, metadata)
    except CookieStoreError:
        return CookieRefreshResult(
            "cookie_file_error", candidate_probe.status, False, None, "cookie_file_replace_failed"
        )
    return CookieRefreshResult(
        "refreshed", candidate_probe.status, True, updated_at, candidate_probe.detail_code
    )


def request_from_payload(payload: object) -> CookieRefreshRequest:
    """Validate the one JSON stdin object without exposing malformed values."""
    if not isinstance(payload, dict):
        raise ValueError("invalid payload")
    required = ("url", "cookie_file", "approved_at")
    if any(
        not isinstance(payload.get(name), str) or not payload[name].strip()
        for name in required
    ):
        raise ValueError("missing required field")
    for name in ("email", "passcode"):
        if name in payload and payload[name] is not None and not isinstance(payload[name], str):
            raise ValueError("invalid optional field")
    return CookieRefreshRequest(
        url=payload["url"],
        cookie_file=Path(payload["cookie_file"]),
        email=payload.get("email"),
        passcode=payload.get("passcode"),
        approved_at=payload["approved_at"],
    )


def main(
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    authorizer: BrowserAuthorizer | None = None,
    probe: Probe | None = None,
    argv: list[str] | None = None,
) -> int:
    """Read one refresh request from stdin and emit one redacted JSON result."""
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    if (sys.argv[1:] if argv is None else argv):
        _write_payload(stdout, _invalid_request_payload("invalid_arguments"))
        return 2
    try:
        request = request_from_payload(json.load(stdin))
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        _write_payload(stdout, _invalid_request_payload("invalid_input"))
        return 2
    result = refresh_cookies(request, authorizer or PlaywrightBrowserAuthorizer(), probe)
    _write_payload(stdout, result.to_payload())
    return 0


def _existing_cookies(cookie_file: Path) -> dict[str, str]:
    """Load any existing parser cookies while allowing a first-time cookie file."""
    if not cookie_file.exists():
        return {}
    return _parser_cookies(load_cookie_document(cookie_file).cookies)


def _default_probe(cookies: Mapping[str, str], document_id: str, view_id: str) -> AccessProbeResult:
    """Run the established HTTP probe with a short-lived session."""
    with requests.Session() as session:
        return probe_access(session, document_id, view_id, cookies)


def _run_probe(
    probe: Probe, cookies: Mapping[str, str], document_id: str, view_id: str
) -> AccessProbeResult:
    """Contain probe failures in a redacted availability outcome."""
    try:
        return probe(cookies, document_id, view_id)
    except Exception:
        return AccessProbeResult("unavailable", None, "probe_error")


def _run_authorizer(
    authorizer: BrowserAuthorizer, request: CookieRefreshRequest
) -> BrowserAuthorizationResult:
    """Contain browser-boundary failures without exposing exception details."""
    try:
        return authorizer.authorize(request)
    except Exception:
        return BrowserAuthorizationResult("unavailable", {}, "authorizer_error")


def _document_identity(url: str) -> tuple[str, str, str]:
    """Extract the safe document identity required by the existing access probe."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not (host == "docsend.com" or host.endswith(".docsend.com")):
        raise ValueError("unreviewed host")
    parts = [part for part in parsed.path.split("/") if part]
    try:
        view_index = parts.index("view")
        document_id = parts[view_index + 1]
    except (ValueError, IndexError):
        raise ValueError("missing document") from None
    view_id = ""
    if len(parts) > view_index + 3 and parts[view_index + 2] == "d":
        view_id = parts[view_index + 3]
    if not document_id or ("d" in parts[view_index + 2 :] and not view_id):
        raise ValueError("invalid document")
    return document_id, view_id, host


def _parser_cookies(cookies: Mapping[str, str]) -> dict[str, str]:
    """Keep only required parser cookie names with non-empty string values."""
    return {
        key: value
        for key in PARSER_COOKIE_KEYS
        if isinstance(value := cookies.get(key), str) and value
    }


def _filter_browser_cookies(browser_cookies: object, document_host: str) -> dict[str, str]:
    """Select parser cookies scoped to the reviewed DocSend host."""
    if not isinstance(browser_cookies, list):
        return {}
    selected: dict[str, str] = {}
    for cookie in browser_cookies:
        if not isinstance(cookie, Mapping):
            continue
        name = cookie.get("name")
        value = cookie.get("value")
        domain = cookie.get("domain")
        normalized_domain = domain.lstrip(".").lower() if isinstance(domain, str) else ""
        if (
            isinstance(name, str)
            and name in PARSER_COOKIE_KEYS
            and isinstance(value, str)
            and value
            and normalized_domain
            and (
                document_host == normalized_domain
                or document_host.endswith(f".{normalized_domain}")
            )
        ):
            selected[name] = value
    return selected


def _invalid_request_payload(detail_code: str) -> dict[str, str | bool | None]:
    """Return a fixed-shape non-secret error for malformed CLI invocations."""
    return {
        "status": "invalid_request",
        "probe_status": "not_run",
        "cookie_file_updated": False,
        "updated_at": None,
        "detail_code": detail_code,
    }


def _write_payload(stdout: TextIO, payload: Mapping[str, str | bool | None]) -> None:
    """Write one compact JSON line to the designated standard output stream."""
    stdout.write(json.dumps(payload, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
