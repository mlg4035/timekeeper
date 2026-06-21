from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

try:
    from pywinauto import Desktop
except Exception:  # pragma: no cover - optional import guard
    Desktop = None


BROWSER_NAMES = {"chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe", "opera_gx.exe"}


@dataclass
class BrowserContext:
    url: str | None
    domain: str | None


def get_browser_context(process_name: str, window_handle: int) -> BrowserContext:
    lower_name = (process_name or "").lower()
    if lower_name not in BROWSER_NAMES:
        return BrowserContext(url=None, domain=None)

    if Desktop is None:
        return BrowserContext(url=None, domain=None)

    url = None
    if lower_name in {"chrome.exe", "msedge.exe", "brave.exe", "opera.exe", "opera_gx.exe"}:
        url = _extract_chromium_url(window_handle)
    elif lower_name == "firefox.exe":
        url = _extract_firefox_url(window_handle)

    domain = _extract_domain(url) if url else None
    return BrowserContext(url=url, domain=domain)


def _extract_chromium_url(window_handle: int) -> str | None:
    try:
        window = Desktop(backend="uia").window(handle=window_handle)
        candidates = [
            window.child_window(title="Address and search bar", control_type="Edit"),
            window.child_window(auto_id="address and search bar", control_type="Edit"),
            window.child_window(title_re=".*address.*bar.*", control_type="Edit"),
        ]
        for control in candidates:
            if control.exists(timeout=0.2):
                value = control.get_value()
                if value:
                    return value.strip()
    except Exception:
        return None
    return None


def _extract_firefox_url(window_handle: int) -> str | None:
    try:
        window = Desktop(backend="uia").window(handle=window_handle)
        candidates = [
            window.child_window(title_re="Search with.*or enter address", control_type="Edit"),
            window.child_window(title_re=".*address.*", control_type="Edit"),
        ]
        for control in candidates:
            if control.exists(timeout=0.2):
                value = control.get_value()
                if value:
                    return value.strip()
    except Exception:
        return None
    return None


def _extract_domain(url: str) -> str | None:
    if not url:
        return None
    parsed = urlparse(url if "://" in url else f"https://{url}")
    return parsed.netloc or None
