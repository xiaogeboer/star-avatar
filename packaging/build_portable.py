#!/usr/bin/env python3
"""Build a portable desktop package for the sports avatar tool."""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
RELEASE_DIR = PROJECT_ROOT / "release"
APP_NAME = "sports-avatar-tool"


def data_separator() -> str:
    return ";" if os_name() == "windows" else ":"


def os_name() -> str:
    system = platform.system().lower()
    if "windows" in system:
        return "windows"
    if "darwin" in system:
        return "macos"
    return "linux"


def archive_ext() -> str:
    return "zip"


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, cwd=PROJECT_ROOT)


def ensure_pyinstaller() -> None:
    try:
        import PyInstaller  # noqa: F401
    except Exception as exc:  # pragma: no cover
        raise SystemExit(
            "PyInstaller is required. Install it with: python -m pip install pyinstaller"
        ) from exc


def build() -> Path:
    ensure_pyinstaller()

    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)

    web_dir = PROJECT_ROOT / "web"
    add_data_value = f"{web_dir}{data_separator()}web"
    run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--onedir",
            "--name",
            APP_NAME,
            "--add-data",
            add_data_value,
            "web_server.py",
        ]
    )

    output_dir = DIST_DIR / APP_NAME
    readme_path = output_dir / "README_PORTABLE.txt"
    readme_path.write_text(
        (
            "Sports Avatar Tool (Portable)\n"
            "=============================\n\n"
            "1) Start the app:\n"
            "   - Windows: run web_server.exe\n"
            "   - macOS/Linux: run ./web_server\n\n"
            "2) Open browser: http://127.0.0.1:8765\n\n"
            "3) Default output folder: ./avatars (next to executable)\n"
        ),
        encoding="utf-8",
    )

    artifact_base = f"{APP_NAME}-{os_name()}-{platform.machine().lower()}"
    archive_path = RELEASE_DIR / f"{artifact_base}.{archive_ext()}"
    if archive_path.exists():
        archive_path.unlink()
    shutil.make_archive(str(archive_path.with_suffix("")), "zip", DIST_DIR, APP_NAME)
    return archive_path


def main() -> None:
    archive = build()
    print(f"Portable archive ready: {archive}")


if __name__ == "__main__":
    main()
