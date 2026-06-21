from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

APP_DIR_NAME = "TimeKeeper"
CONFIG_FILENAME = "config.json"
DB_FILENAME = "activity.sqlite3"
REPORTS_DIRNAME = "reports"


@dataclass
class AppConfig:
    poll_interval_minutes: int = 5
    idle_threshold_minutes: int = 5
    retention_days: int = 30
    retention_enabled: bool = True
    tracking_enabled: bool = True
    launch_at_startup: bool = False


def get_app_data_dir() -> Path:
    appdata_env = os.getenv("APPDATA")
    appdata = Path(appdata_env) if appdata_env else (Path.home() / "AppData" / "Roaming")
    return appdata / APP_DIR_NAME


def get_config_path() -> Path:
    return get_app_data_dir() / CONFIG_FILENAME


def get_database_path() -> Path:
    return get_app_data_dir() / DB_FILENAME


def get_reports_dir() -> Path:
    return get_app_data_dir() / REPORTS_DIRNAME


def ensure_app_dirs() -> None:
    app_dir = get_app_data_dir()
    reports_dir = get_reports_dir()
    app_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)


def load_config() -> AppConfig:
    ensure_app_dirs()
    path = get_config_path()
    if not path.exists():
        cfg = AppConfig()
        save_config(cfg)
        return cfg

    with path.open("r", encoding="utf-8") as file:
        raw = json.load(file)

    defaults = asdict(AppConfig())
    defaults.update(raw or {})
    return AppConfig(**defaults)


def save_config(config: AppConfig) -> None:
    ensure_app_dirs()
    path = get_config_path()
    with path.open("w", encoding="utf-8") as file:
        json.dump(asdict(config), file, indent=2)
