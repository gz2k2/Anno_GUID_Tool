"""Build the Anno GUID Tool as a Windows one-file executable with PyInstaller.

Usage:
    python build_onefile.py
    python build_onefile.py --clean

Output: dist/Anno_GUID_Tool_v<version>.exe

The version is read from version.txt (e.g. "v1.23.45"). A leading "v" is
removed for the file name so it does not become "..._vv1.23.45.exe".
"""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

#: Base name of the executable (version is appended).
EXE_BASE_NAME = "Anno_GUID_Tool"

#: Optional program icon in the project root (next to main.py).
#: Used only if the file exists.
ICON_FILE = ROOT / "AnnoGUIDTool.ico"

#: Project modules. They are imported via main.py -> app.py and found by the
#: import scanner, but are listed explicitly to be safe.
HIDDEN_IMPORTS = (
    "core.collisions", "core.config_manager", "core.constants", "core.file_drop", "core.guid_database",
    "core.guid_reservations",
    "core.translations", "core.update_checker", "core.version", "core.xml_scanner",
    "dialogs.collision_dialog", "dialogs.collision_report", "dialogs.migrate_dialog", "dialogs.update_dialog", "dialogs.styled_dialogs",
    "tabs.database_tab", "tabs.reserve_tab", "tabs.replace_tab", "tabs.settings_tab",
)

#: Unused GUI bindings that may be installed in the build environment and
#: would only bloat the executable.
EXCLUDED_MODULES = ("PyQt5", "PyQt6", "PySide2", "PySide6")


def read_version() -> str:
    """Version from version.txt without leading "v" (fallback "0.0.0")."""
    version_file = ROOT / "version.txt"
    if not version_file.exists():
        return "0.0.0"
    version = version_file.read_text(encoding="utf-8-sig").strip()
    return version[1:] if version[:1].lower() == "v" else (version or "0.0.0")


def module_installed(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Anno GUID Tool as a PyInstaller one-file executable")
    parser.add_argument("--clean", action="store_true", help="Remove the PyInstaller work directory before building")
    args = parser.parse_args()

    if not module_installed("customtkinter"):
        print("ERROR: customtkinter is not installed. Install it with: pip install customtkinter")
        return 1

    version = read_version()
    name = f"{EXE_BASE_NAME}_v{version}"

    command = [
        sys.executable,
        "-m", "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name", name,
        # Project root on the search path so "app", "core", "tabs" and "dialogs" resolve.
        "--paths", str(ROOT),
        # version.txt is unpacked into the bundle and read from there at runtime.
        "--add-data", f"{ROOT / 'version.txt'};.",
        # CustomTkinter keeps its themes (*.json) and assets as package data.
        # PyInstaller ignores package data unless it is collected explicitly;
        # without it the app fails at startup when loading the color theme.
        "--collect-data", "customtkinter",
    ]

    if ICON_FILE.exists():
        command += ["--icon", str(ICON_FILE)]
    else:
        print(f"Note: no icon found at {ICON_FILE} - building without icon.")

    for module in HIDDEN_IMPORTS:
        command += ["--hidden-import", module]
    for module in EXCLUDED_MODULES:
        command += ["--exclude-module", module]

    if args.clean:
        command.append("--clean")

    command.append(str(ROOT / "main.py"))

    print("Building:")
    print(" ".join(f'"{part}"' if " " in part else part for part in command))

    result = subprocess.run(command, cwd=ROOT)
    if result.returncode == 0:
        print(f"\nBuild complete: {ROOT / 'dist' / (name + '.exe')}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
