# TimeKeeper (Windows Tray Utility)

TimeKeeper is a local-only Windows tray app that records the active window at polling intervals.

<img width="244" height="143" alt="Screenshot 2026-06-21 BG" src="https://github.com/user-attachments/assets/cf759e54-4449-4146-84a3-7d176c193c75" />
<img width="244" height="200" alt="Screenshot 2026-06-21 195859" src="https://github.com/user-attachments/assets/dcb15c4d-3e64-4e28-b03c-3460290a2418" />

## Features

- Polls on clock boundaries (for example, `10:00`, `10:05`, `10:10`)
- Stores activity in SQLite under `%APPDATA%\TimeKeeper`
- Captures:
  - timestamp
  - active window title
  - process name
  - URL/domain for supported browsers (best effort via browser-specific extraction)
- Logs `LOCKED` or `IDLE` status (`IDLE` defaults to 5 minutes of no input)
- Tray controls:
  - Start/Stop tracking
  - Set poll interval
  - Set retention days and enable/disable cleanup
  - Enable/disable startup at login (HKCU Run key)
  - Generate today's report
  - Open data folder
  - Exit
- Generates timestamped report files:
  - HTML/JavaScript report powered directly by SQLite through local API
  - Date selector populated from available SQLite dates (when TimeKeeper is running)
  - Editable Task dropdowns in "Totals by App and Window"
  - Automatic Task assignment persistence for future reports
  - "Totals by Task" aggregation

## Install

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run

```powershell
python main.py
```

The app runs in the Windows notification area (system tray).

## One-Click EXE Packaging (PyInstaller)

Use the included one-click build script:

```powershell
.\build.bat
```

This will:

- create `.venv` if needed
- install build dependencies from `requirements-build.txt`
- clean previous build output
- produce `dist\TimeKeeper.exe`
- apply custom app icon from `assets\timekeeper.ico`

You can also run the PowerShell script directly:

```powershell
.\build.ps1 -Clean
```

To use a different EXE icon, replace `assets\timekeeper.ico` and rebuild.

## Data Location

`%APPDATA%\TimeKeeper`

- `config.json`
- `activity.sqlite3`
- `reports\`
