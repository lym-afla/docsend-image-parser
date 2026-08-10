"""Secret-safe, atomic persistence for DocSend parser cookies."""

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


PARSER_COOKIE_KEYS = ("_v_", "_dss_", "_us_")
METADATA_KEYS = ("updated_at", "source", "docsend_host", "document_id", "view_id")


class CookieStoreError(Exception):
    """Raised when a cookie document cannot be safely read or replaced."""


@dataclass(frozen=True)
class CookieDocument:
    """Cookies required by the parser and their non-secret provenance metadata."""

    cookies: dict[str, str]
    metadata: dict[str, str]


def load_cookie_document(path: Path) -> CookieDocument:
    """Load a cookie document, accepting the current envelope and legacy flat files.

    Args:
        path: JSON file containing a ``cookies`` object or a legacy flat mapping.

    Returns:
        The parser cookie mapping and non-secret metadata.

    Raises:
        CookieStoreError: If the file is unavailable or has an invalid structure.
    """
    try:
        with Path(path).open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        raise CookieStoreError("Could not read cookie document.") from error

    if not isinstance(payload, dict):
        raise CookieStoreError("Cookie document must contain a JSON object.")

    if "cookies" in payload:
        cookies = payload["cookies"]
        metadata = payload.get("metadata", {})
    else:
        cookies = payload
        metadata = {}

    if not _is_string_mapping(cookies) or not _is_string_mapping(metadata):
        raise CookieStoreError("Cookie document has an invalid structure.")

    return CookieDocument(cookies=dict(cookies), metadata=dict(metadata))


def replace_cookie_document(
    path: Path, cookies: Mapping[str, str], metadata: Mapping[str, str]
) -> None:
    """Atomically replace a cookie document with whitelisted parser data.

    Args:
        path: Destination JSON path.
        cookies: Browser cookies collected after the requested document is accessible.
        metadata: Non-secret provenance fields for the refreshed cookie document.

    Raises:
        CookieStoreError: If the new document cannot be safely persisted. The
            previous file remains untouched when replacement fails.
    """
    if not _is_string_mapping(cookies) or not _is_string_mapping(metadata):
        raise CookieStoreError("Cookies and metadata must be string mappings.")

    destination = Path(path)
    document = {
        "cookies": {key: cookies[key] for key in PARSER_COOKIE_KEYS if key in cookies},
        "metadata": {key: metadata[key] for key in METADATA_KEYS if key in metadata},
    }
    temporary_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            json.dump(document, handle, ensure_ascii=False, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())

        if os.name != "nt":
            os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, destination)
    except OSError as error:
        raise CookieStoreError("Could not atomically replace cookie document.") from error
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def _is_string_mapping(value: object) -> bool:
    """Return whether a value is a mapping with string keys and values."""
    return isinstance(value, Mapping) and all(
        isinstance(key, str) and isinstance(item, str) for key, item in value.items()
    )
