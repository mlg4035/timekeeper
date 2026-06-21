from __future__ import annotations

import threading
from datetime import datetime, timedelta
from typing import Callable

from .config import AppConfig, load_config
from .db import ActivityRow, ActivityStore, now_local
from .monitor import collect_snapshot

ConfigLoader = Callable[[], AppConfig]


class TrackerService:
    def __init__(self, store: ActivityStore, config_loader: ConfigLoader | None = None) -> None:
        self.store = store
        self.config_loader = config_loader or load_config
        self.stop_event = threading.Event()
        self.wake_event = threading.Event()
        self.thread = threading.Thread(target=self._run_loop, name="tracker-service", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        self.wake_event.set()
        self.thread.join(timeout=5)

    def notify_config_changed(self) -> None:
        self.wake_event.set()

    def _run_loop(self) -> None:
        while not self.stop_event.is_set():
            config = self.config_loader()
            if not config.tracking_enabled:
                self._wait_or_wake(1.0)
                continue

            next_poll = _next_clock_boundary(now_local(), config.poll_interval_minutes)
            sleep_seconds = max((next_poll - now_local()).total_seconds(), 0.0)
            woke_early = self._wait_or_wake(sleep_seconds)
            if woke_early or self.stop_event.is_set():
                continue

            fresh_config = self.config_loader()
            if not fresh_config.tracking_enabled:
                continue

            timestamp = now_local()
            snap = collect_snapshot(fresh_config.idle_threshold_minutes)
            row = ActivityRow(
                timestamp_local=timestamp.isoformat(),
                date_local=timestamp.date().isoformat(),
                status=snap.status,
                source_type=snap.source_type,
                window_title=snap.window_title,
                process_name=snap.process_name,
                url=snap.url,
                domain=snap.domain,
                interval_minutes=fresh_config.poll_interval_minutes,
            )
            self.store.insert_activity(row)
            if fresh_config.retention_enabled:
                self.store.cleanup_older_than_days(fresh_config.retention_days)

    def _wait_or_wake(self, timeout_seconds: float) -> bool:
        woke = self.wake_event.wait(timeout_seconds)
        self.wake_event.clear()
        return woke


def _next_clock_boundary(current: datetime, interval_minutes: int) -> datetime:
    interval_minutes = max(interval_minutes, 1)
    minute = current.minute
    remainder = minute % interval_minutes
    delta_minutes = interval_minutes if remainder == 0 else interval_minutes - remainder
    base = current.replace(second=0, microsecond=0)
    if current.second == 0 and current.microsecond == 0 and remainder == 0:
        return base + timedelta(minutes=interval_minutes)
    return base + timedelta(minutes=delta_minutes)
