from __future__ import annotations

import ctypes
import os
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import simpledialog

import pystray
from PIL import Image, ImageDraw

from .api_server import TaskApiServer
from .config import AppConfig, ensure_app_dirs, get_app_data_dir, get_database_path, get_reports_dir, load_config, save_config
from .db import ActivityStore
from .reporter import generate_today_report
from .service import TrackerService
from .startup import is_enabled as startup_is_enabled
from .startup import set_enabled as startup_set_enabled

MB_OK = 0x00000000
MB_ICONINFORMATION = 0x00000040
MB_ICONERROR = 0x00000010
MB_YESNOCANCEL = 0x00000003
MB_ICONQUESTION = 0x00000020
IDYES = 6
IDNO = 7
IDCANCEL = 2


class TrayApplication:
    def __init__(self, script_path: Path) -> None:
        self.script_path = script_path
        ensure_app_dirs()
        self.config = load_config()
        self.config.launch_at_startup = startup_is_enabled()
        save_config(self.config)

        self.store = ActivityStore(get_database_path())
        self.api_server = TaskApiServer(self.store)
        self.service = TrackerService(self.store)
        self.icon = pystray.Icon(
            "TimeKeeper",
            icon=self._create_icon(),
            title="TimeKeeper",
            menu=self._build_menu(),
        )
        self._lock = threading.Lock()

    def run(self) -> None:
        self.api_server.start()
        self.service.start()
        self.icon.run()

    def _build_menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem(self._tracking_label, self._toggle_tracking),
            pystray.MenuItem("Generate Today Report", self._generate_report),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Set Poll Interval...", self._set_poll_interval),
            pystray.MenuItem("Set Retention...", self._set_retention),
            pystray.MenuItem(
                "Start At Login",
                self._toggle_startup,
                checked=lambda _: self.config.launch_at_startup,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Open Data Folder", self._open_data_folder),
            pystray.MenuItem("Exit", self._exit_app),
        )

    def _tracking_label(self, _: pystray.MenuItem) -> str:
        return "Stop Tracking" if self.config.tracking_enabled else "Start Tracking"

    def _toggle_tracking(self, icon: pystray.Icon, _: pystray.MenuItem) -> None:
        with self._lock:
            self.config = load_config()
            self.config.tracking_enabled = not self.config.tracking_enabled
            save_config(self.config)
        self.service.notify_config_changed()
        icon.update_menu()

    def _toggle_startup(self, icon: pystray.Icon, _: pystray.MenuItem) -> None:
        with self._lock:
            self.config = load_config()
            target_state = not self.config.launch_at_startup
            startup_set_enabled(self.script_path, target_state)
            self.config.launch_at_startup = target_state
            save_config(self.config)
        icon.update_menu()

    def _set_poll_interval(self, icon: pystray.Icon, _: pystray.MenuItem) -> None:
        value = _ask_integer("Set Poll Interval", "Poll interval in minutes (>=1):", self.config.poll_interval_minutes)
        if value is None:
            return
        if value < 1:
            _show_error("Poll interval must be at least 1 minute.")
            return
        with self._lock:
            self.config = load_config()
            self.config.poll_interval_minutes = value
            save_config(self.config)
        self.service.notify_config_changed()
        icon.update_menu()

    def _set_retention(self, icon: pystray.Icon, _: pystray.MenuItem) -> None:
        days = _ask_integer("Set Retention", "Retention in days (>=1):", self.config.retention_days)
        if days is None:
            return
        if days < 1:
            _show_error("Retention must be at least 1 day.")
            return

        enabled = _ask_yes_no("Retention Cleanup", "Enable automatic retention cleanup?")
        if enabled is None:
            return

        with self._lock:
            self.config = load_config()
            self.config.retention_days = days
            self.config.retention_enabled = enabled
            save_config(self.config)
        self.service.notify_config_changed()
        icon.update_menu()

    def _generate_report(self, _: pystray.Icon, __: pystray.MenuItem) -> None:
        assignments = self.store.get_task_assignments()
        html_path = generate_today_report(
            self.store,
            get_reports_dir(),
            task_assignments=assignments,
            api_base_url=self.api_server.base_url,
        )
        self.icon.notify(
            f"Report generated:\n{html_path.name}",
            "TimeKeeper",
        )
        webbrowser.open(html_path.as_uri())

    def _open_data_folder(self, _: pystray.Icon, __: pystray.MenuItem) -> None:
        os.startfile(get_app_data_dir())  # type: ignore[attr-defined]

    def _exit_app(self, icon: pystray.Icon, _: pystray.MenuItem) -> None:
        self.service.stop()
        self.api_server.stop()
        icon.stop()

    def _create_icon(self) -> Image.Image:
        size = 64
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse((4, 4, size - 4, size - 4), fill=(36, 99, 235, 255))
        draw.ellipse((12, 12, size - 12, size - 12), fill=(255, 255, 255, 255))
        draw.line((size // 2, size // 2, size // 2, 20), fill=(36, 99, 235, 255), width=4)
        draw.line((size // 2, size // 2, 42, 36), fill=(36, 99, 235, 255), width=4)
        draw.ellipse((size // 2 - 4, size // 2 - 4, size // 2 + 4, size // 2 + 4), fill=(36, 99, 235, 255))
        return image


def _ask_integer(title: str, prompt: str, initial_value: int) -> int | None:
    root = tk.Tk()
    root.withdraw()
    try:
        value = simpledialog.askinteger(title, prompt, initialvalue=initial_value, minvalue=1)
        return value
    finally:
        root.destroy()


def _ask_yes_no(title: str, prompt: str) -> bool | None:
    response = _message_box(prompt, title, MB_YESNOCANCEL | MB_ICONQUESTION)
    if response == IDYES:
        return True
    if response == IDNO:
        return False
    return None


def _show_info(message: str) -> None:
    _message_box(message, "TimeKeeper", MB_OK | MB_ICONINFORMATION)


def _show_error(message: str) -> None:
    _message_box(message, "TimeKeeper", MB_OK | MB_ICONERROR)


def _message_box(message: str, title: str, flags: int) -> int:
    return ctypes.windll.user32.MessageBoxW(None, message, title, flags)
