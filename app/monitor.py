from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass

import psutil
import win32gui
import win32process

from .browser import get_browser_context
from .explorer import get_explorer_context


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


user32 = ctypes.windll.user32

DESKTOP_SWITCHDESKTOP = 0x0100


@dataclass
class Snapshot:
    status: str
    source_type: str
    window_title: str
    process_name: str
    url: str
    domain: str


def get_idle_seconds() -> float:
    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if not user32.GetLastInputInfo(ctypes.byref(info)):
        return 0
    milliseconds_since_input = ctypes.windll.kernel32.GetTickCount() - info.dwTime
    return milliseconds_since_input / 1000.0


def is_workstation_locked() -> bool:
    desktop = user32.OpenInputDesktop(0, False, DESKTOP_SWITCHDESKTOP)
    if not desktop:
        return True
    try:
        return not bool(user32.SwitchDesktop(desktop))
    finally:
        user32.CloseDesktop(desktop)


def collect_snapshot(idle_threshold_minutes: int) -> Snapshot:
    if is_workstation_locked():
        return Snapshot(status="LOCKED", source_type="system", window_title="", process_name="", url="", domain="")

    idle_seconds = get_idle_seconds()
    if idle_seconds >= idle_threshold_minutes * 60:
        return Snapshot(status="IDLE", source_type="system", window_title="", process_name="", url="", domain="")

    window_handle = win32gui.GetForegroundWindow()
    if not window_handle:
        return Snapshot(status="ACTIVE", source_type="application", window_title="", process_name="", url="", domain="")

    title = win32gui.GetWindowText(window_handle) or ""
    process_name = _get_process_name(window_handle)
    browser_ctx = get_browser_context(process_name, window_handle)
    explorer_ctx = get_explorer_context(process_name, window_handle)
    resolved_url = browser_ctx.url or ""
    resolved_domain = browser_ctx.domain or ""
    source_type = "application"
    if browser_ctx.url:
        source_type = "browser"
    if explorer_ctx.path:
        resolved_url = explorer_ctx.path
        resolved_domain = explorer_ctx.network_host or ""
        source_type = "explorer"
    return Snapshot(
        status="ACTIVE",
        source_type=source_type,
        window_title=title,
        process_name=process_name,
        url=resolved_url,
        domain=resolved_domain,
    )


def _get_process_name(window_handle: int) -> str:
    try:
        _, pid = win32process.GetWindowThreadProcessId(window_handle)
        return psutil.Process(pid).name()
    except Exception:
        return ""
