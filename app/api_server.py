from __future__ import annotations

import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from .db import ActivityRow, ActivityStore


class TaskApiServer:
    def __init__(self, store: ActivityStore, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.store = store
        self.host = host
        self.port = port
        self.bound_port: int | None = None
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        for candidate_port in range(port, port + 10):
            try:
                self._server = ThreadingHTTPServer((host, candidate_port), _build_handler(store))
                self.bound_port = candidate_port
                self._thread = threading.Thread(target=self._server.serve_forever, name="task-api-server", daemon=True)
                break
            except OSError:
                self._server = None
                self._thread = None
                self.bound_port = None

    def start(self) -> None:
        if self._thread is not None:
            self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=3)

    @property
    def base_url(self) -> str:
        if self.bound_port is None:
            return ""
        return f"http://{self.host}:{self.bound_port}"


def _build_handler(store: ActivityStore) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_OPTIONS(self) -> None:  # noqa: N802
            self._send_headers(HTTPStatus.NO_CONTENT)

        def do_GET(self) -> None:  # noqa: N802
            try:
                parsed = urlparse(self.path)

                if parsed.path == "/health":
                    self._send_json(HTTPStatus.OK, {"status": "ok"})
                    return
                if parsed.path == "/task-assignments":
                    assignments = store.get_task_assignments()
                    self._send_json(HTTPStatus.OK, {"assignments": assignments})
                    return
                if parsed.path == "/dates":
                    dates = store.get_available_dates()
                    self._send_json(HTTPStatus.OK, {"dates": dates})
                    return
                if parsed.path == "/activity":
                    query = parse_qs(parsed.query)
                    date_value = (query.get("date") or [""])[0]
                    if not date_value:
                        self._send_json(HTTPStatus.BAD_REQUEST, {"error": "date query parameter required"})
                        return
                    rows = store.get_entries_for_date(date_value)
                    self._send_json(HTTPStatus.OK, {"rows": [_row_to_dict(row) for row in rows]})
                    return
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

        def do_POST(self) -> None:  # noqa: N802
            try:
                parsed = urlparse(self.path)
                if parsed.path != "/task-assignments":
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
                    return

                payload = self._read_json()
                if not isinstance(payload, dict):
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid payload"})
                    return

                process_name = str(payload.get("process_name", ""))
                window_title = str(payload.get("window_title", ""))
                task_name = str(payload.get("task_name", ""))
                if not process_name and not window_title:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": "process_name/window_title required"})
                    return

                store.upsert_task_assignment(process_name, window_title, task_name)
                self._send_json(HTTPStatus.OK, {"ok": True})
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

        def log_message(self, _format: str, *_args: Any) -> None:
            return

        def _read_json(self) -> Any:
            content_length = int(self.headers.get("Content-Length", "0") or "0")
            if content_length <= 0:
                return None
            raw = self.rfile.read(content_length)
            try:
                return json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                return None

        def _send_headers(self, status: HTTPStatus) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
            self._send_headers(status)
            self.wfile.write(json.dumps(payload).encode("utf-8"))

    return Handler


def _row_to_dict(row: ActivityRow) -> dict[str, str | int]:
    return {
        "timestamp_local": row.timestamp_local,
        "date_local": row.date_local,
        "status": row.status,
        "source_type": row.source_type,
        "window_title": row.window_title,
        "process_name": row.process_name,
        "url": row.url,
        "domain": row.domain,
        "interval_minutes": row.interval_minutes,
    }
