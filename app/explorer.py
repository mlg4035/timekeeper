from __future__ import annotations

from dataclasses import dataclass

try:
    from pywinauto import Desktop
except Exception:  # pragma: no cover - optional import guard
    Desktop = None


@dataclass
class ExplorerContext:
    path: str | None
    network_host: str | None


def get_explorer_context(process_name: str, window_handle: int) -> ExplorerContext:
    if (process_name or "").lower() != "explorer.exe":
        return ExplorerContext(path=None, network_host=None)
    if Desktop is None:
        return ExplorerContext(path=None, network_host=None)

    path = _extract_explorer_path(window_handle)
    return ExplorerContext(path=path, network_host=_extract_network_host(path) if path else None)


def _extract_explorer_path(window_handle: int) -> str | None:
    try:
        window = Desktop(backend="uia").window(handle=window_handle)
        candidates = [
            window.child_window(title_re="Address.*", control_type="Edit"),
            window.child_window(auto_id="41477", control_type="Edit"),
        ]
        for control in candidates:
            if control.exists(timeout=0.2):
                value = control.get_value()
                if value:
                    cleaned = value.strip()
                    if cleaned:
                        return cleaned
    except Exception:
        return None
    return None


def _extract_network_host(path: str) -> str | None:
    # UNC path example: \\server\share\folder
    if not path.startswith("\\\\"):
        return None
    parts = path[2:].split("\\", 1)
    return parts[0] if parts and parts[0] else None
