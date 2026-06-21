from __future__ import annotations

from pathlib import Path

from app.tray_app import TrayApplication


def main() -> None:
    app = TrayApplication(script_path=Path(__file__).resolve())
    app.run()


if __name__ == "__main__":
    main()
