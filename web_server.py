#!/usr/bin/env python3
"""Local web UI for downloading player avatars via TheSportsDB."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, unquote, urlparse

from fetch_tennis_avatars import download_avatars_for_name


ROOT_DIR = Path(__file__).resolve().parent
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", ROOT_DIR))
WEB_DIR = RESOURCE_DIR / "web"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8765
MAX_PLAYERS_PER_REQUEST = 50
DEFAULT_OUTPUT_DIR = ROOT_DIR / "avatars"

# Runtime settings are initialized in main().
SERVER_HOST = DEFAULT_HOST
SERVER_PORT = DEFAULT_PORT
BASE_OUTPUT_DIR = DEFAULT_OUTPUT_DIR


def parse_args() -> argparse.Namespace:
    """Support changing host/port/output directory without editing source."""
    parser = argparse.ArgumentParser(description="Run local web UI for sports avatar downloads.")
    parser.add_argument("--host", default=os.getenv("AVATAR_WEB_HOST", DEFAULT_HOST))
    parser.add_argument("--port", type=int, default=int(os.getenv("AVATAR_WEB_PORT", DEFAULT_PORT)))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(os.getenv("AVATAR_OUTPUT_DIR", str(DEFAULT_OUTPUT_DIR))),
        help="Default directory where avatar files are saved.",
    )
    return parser.parse_args()


def parse_player_text(text: str) -> list[str]:
    """Split multiline/comma-separated names, then deduplicate case-insensitively."""
    parts = []
    for line in text.splitlines():
        for chunk in line.split(","):
            name = chunk.strip()
            if name:
                parts.append(name)

    deduped: list[str] = []
    seen = set()
    for name in parts:
        key = name.casefold()
        if key not in seen:
            seen.add(key)
            deduped.append(name)
    return deduped


def resolve_output_dir(raw_value: str | None) -> Path:
    """Resolve a user-provided folder path; relative paths are rooted at project dir."""
    if not raw_value:
        return BASE_OUTPUT_DIR
    path = Path(raw_value.strip()).expanduser()
    if not path.is_absolute():
        path = (ROOT_DIR / path).resolve()
    return path


def pick_directory_dialog() -> str:
    """Open native folder picker and return selected absolute path (empty when canceled)."""
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    selected = filedialog.askdirectory(initialdir=str(BASE_OUTPUT_DIR))
    root.destroy()
    return selected or ""


class Handler(BaseHTTPRequestHandler):
    server_version = "SportsAvatarWeb/2.0"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path == "/" or path == "/index.html":
            self._serve_file(WEB_DIR / "index.html", "text/html; charset=utf-8")
            return
        if path == "/app.js":
            self._serve_file(WEB_DIR / "app.js", "application/javascript; charset=utf-8")
            return
        if path == "/styles.css":
            self._serve_file(WEB_DIR / "styles.css", "text/css; charset=utf-8")
            return
        if path == "/api/config":
            self._json_response(
                {
                    "default_output_dir": str(BASE_OUTPUT_DIR),
                    "max_players_per_request": MAX_PLAYERS_PER_REQUEST,
                }
            )
            return
        if path == "/api/preview":
            params = parse_qs(parsed.query)
            raw_file = (params.get("file") or [""])[0]
            file_path = Path(raw_file)
            if not file_path.is_absolute():
                self._json_response({"error": "Preview path must be absolute."}, status=HTTPStatus.BAD_REQUEST)
                return
            content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
            self._serve_file(file_path, content_type)
            return

        self._json_response({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/api/pick-directory":
            try:
                selected = pick_directory_dialog()
                self._json_response({"path": selected})
            except Exception as exc:
                self._json_response(
                    {"error": f"Failed to open directory picker: {exc}"},
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                )
            return

        if self.path == "/api/download":
            self._handle_download()
            return

        self._json_response({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def _handle_download(self) -> None:
        # The web page submits JSON here for batch downloading.
        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_length) if content_length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._json_response({"error": "Invalid JSON payload"}, status=HTTPStatus.BAD_REQUEST)
            return

        names_text = str(payload.get("players", ""))
        size = str(payload.get("size", "small"))
        delay = float(payload.get("delay", 1.0))
        output_dir = resolve_output_dir(payload.get("output_dir"))

        if size not in {"original", "medium", "small", "tiny"}:
            self._json_response({"error": "size must be original|medium|small|tiny"}, status=HTTPStatus.BAD_REQUEST)
            return

        players = parse_player_text(names_text)
        if not players:
            self._json_response({"error": "Please provide at least one player name."}, status=HTTPStatus.BAD_REQUEST)
            return
        if len(players) > MAX_PLAYERS_PER_REQUEST:
            self._json_response(
                {"error": f"Too many players. Max {MAX_PLAYERS_PER_REQUEST} names per request."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            self._json_response(
                {"error": f"Cannot create output directory: {output_dir}. {exc}"},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        results = []
        for index, player_name in enumerate(players):
            try:
                group = download_avatars_for_name(player_name, output_dir, size)
                if not group:
                    group = [
                        {
                            "requested_name": player_name,
                            "status": "not_found",
                            "reason": "No player match found in TheSportsDB.",
                        }
                    ]
            except HTTPError as exc:
                group = [
                    {
                        "requested_name": player_name,
                        "status": "http_error",
                        "reason": f"HTTP {exc.code}: {exc.reason}",
                    }
                ]
            except URLError as exc:
                group = [
                    {
                        "requested_name": player_name,
                        "status": "network_error",
                        "reason": str(exc.reason),
                    }
                ]
            except Exception as exc:
                group = [
                    {
                        "requested_name": player_name,
                        "status": "error",
                        "reason": str(exc),
                    }
                ]

            for result in group:
                saved_to = result.get("saved_to")
                if saved_to:
                    result["image_preview_url"] = f"/api/preview?file={saved_to}"
                results.append(result)
            if index < len(players) - 1:
                time.sleep(max(delay, 0.0))

        downloaded = sum(item.get("status") == "downloaded" for item in results)
        self._json_response(
            {
                "requested_count": len(players),
                "downloaded_count": downloaded,
                "output_dir": str(output_dir),
                "results": results,
            }
        )

    def _serve_file(self, file_path: Path, content_type: str) -> None:
        if not file_path.exists() or not file_path.is_file():
            self._json_response({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
            return
        data = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json_response(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt: str, *args) -> None:
        # Keep console output concise.
        return


def main() -> None:
    global SERVER_HOST, SERVER_PORT, BASE_OUTPUT_DIR

    # Read runtime configuration once at startup.
    if getattr(sys, "frozen", False):
        # In packaged executable mode, keep output beside the executable.
        executable_dir = Path(sys.executable).resolve().parent
        os.environ.setdefault("AVATAR_OUTPUT_DIR", str(executable_dir / "avatars"))

    args = parse_args()
    SERVER_HOST = args.host
    SERVER_PORT = args.port
    BASE_OUTPUT_DIR = args.output_dir.resolve()
    BASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    server = ThreadingHTTPServer((SERVER_HOST, SERVER_PORT), Handler)
    print(f"Web UI running at http://127.0.0.1:{SERVER_PORT}")
    print(f"Default output dir: {BASE_OUTPUT_DIR}")
    server.serve_forever()


if __name__ == "__main__":
    main()
