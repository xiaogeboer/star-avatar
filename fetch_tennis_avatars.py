#!/usr/bin/env python3
"""Download player avatars from TheSportsDB free API."""

from __future__ import annotations

import argparse
import json
import mimetypes
import re
import sys
import time
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


API_BASE = "https://www.thesportsdb.com/api/v1/json/123/searchplayers.php"
DEFAULT_PLAYERS = [
    "Novak Djokovic",
    "Rafael Nadal",
    "Roger Federer",
    "Carlos Alcaraz",
    "Jannik Sinner",
    "Iga Swiatek",
    "Aryna Sabalenka",
    "Coco Gauff",
    "Naomi Osaka",
    "Serena Williams",
]
IMAGE_FIELDS = ("strThumb", "strRender", "strCutout", "strFanart1")
USER_AGENT = "Mozilla/5.0 (compatible; tennis-avatar-fetcher/1.0)"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch player avatars from TheSportsDB free API."
    )
    parser.add_argument(
        "--players",
        nargs="+",
        help="Player names to fetch. Example: --players \"Novak Djokovic\" \"Iga Swiatek\"",
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Optional UTF-8 text file with one player name per line.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("avatars"),
        help="Directory for downloaded images and manifest.json",
    )
    parser.add_argument(
        "--size",
        choices=("original", "medium", "small", "tiny"),
        default="small",
        help="Append a preview size to image URLs when supported.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.2,
        help="Delay between API requests in seconds. Keep below 30 requests/minute.",
    )
    return parser.parse_args()


def load_players(args: argparse.Namespace) -> list[str]:
    # Merge names from CLI list and optional file, then de-duplicate.
    players: list[str] = []

    if args.players:
        players.extend(args.players)

    if args.input:
        lines = args.input.read_text(encoding="utf-8").splitlines()
        players.extend(line.strip() for line in lines if line.strip())

    if not players:
        players.extend(DEFAULT_PLAYERS)

    deduped: list[str] = []
    seen: set[str] = set()
    for player in players:
        key = player.casefold()
        if key not in seen:
            deduped.append(player)
            seen.add(key)
    return deduped


def build_preview_url(image_url: str, size: str) -> str:
    # TheSportsDB image CDN supports suffixes like /small /medium /tiny.
    if size == "original":
        return image_url
    return f"{image_url}/{size}"


def request_json(url: str) -> dict:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def request_bytes(url: str) -> tuple[bytes, str | None]:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=60) as response:
        content = response.read()
        content_type = response.headers.get_content_type()
        return content, content_type


def fetch_player_matches(player_name: str) -> list[dict]:
    # Free API search endpoint (key=123) by player name.
    query = urlencode({"p": player_name})
    payload = request_json(f"{API_BASE}?{query}")
    return payload.get("player") or []


def pick_exact_name_first(matches: Iterable[dict], requested_name: str) -> list[dict]:
    # Keep all matches; place exact-name matches first for predictable ordering.
    items = list(matches)
    if not items:
        return items
    exact_name = requested_name.casefold()
    exact = []
    others = []
    for item in items:
        candidate = (item.get("strPlayer") or "").casefold()
        if candidate == exact_name:
            exact.append(item)
        else:
            others.append(item)
    return [*exact, *others]


def dedupe_players(matches: Iterable[dict]) -> list[dict]:
    # Remove duplicate API rows using idPlayer as primary key.
    unique = []
    seen = set()
    for item in matches:
        key = item.get("idPlayer") or json.dumps(item, sort_keys=True, ensure_ascii=False)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def build_filename(player: dict, requested_name: str, extension: str) -> str:
    # Include sport and id to avoid collisions for same-name players.
    name_part = slugify(player.get("strPlayer") or requested_name)
    sport_part = slugify(player.get("strSport") or "sport")
    id_part = slugify(str(player.get("idPlayer") or "unknown"))
    return f"{name_part}_{sport_part}_{id_part}{extension}"


def _download_player_record(player: dict, requested_name: str, output_dir: Path, size: str) -> dict:
    image_url, image_field = pick_image(player, size)
    if not image_url:
        return {
            "requested_name": requested_name,
            "matched_name": player.get("strPlayer"),
            "idPlayer": player.get("idPlayer"),
            "sport": player.get("strSport"),
            "status": "missing_image",
            "reason": "Player found, but no avatar-like image fields were populated.",
        }

    image_bytes, content_type = request_bytes(image_url)
    extension = guess_extension(image_url, content_type)
    filename = build_filename(player, requested_name, extension)
    filepath = output_dir / filename
    filepath.write_bytes(image_bytes)

    return {
        "requested_name": requested_name,
        "matched_name": player.get("strPlayer"),
        "idPlayer": player.get("idPlayer"),
        "sport": player.get("strSport"),
        "gender": player.get("strGender"),
        "image_field": image_field,
        "image_url": image_url,
        "saved_to": str(filepath),
        "status": "downloaded",
    }


def download_avatars_for_name(player_name: str, output_dir: Path, size: str) -> list[dict]:
    # Download all matched players with the same searched name.
    matches = fetch_player_matches(player_name)
    if not matches:
        return None

    ordered = pick_exact_name_first(matches, player_name)
    unique = dedupe_players(ordered)
    return [_download_player_record(player, player_name, output_dir, size) for player in unique]


def pick_image(player: dict, size: str) -> tuple[str, str] | tuple[None, None]:
    # Fallback chain: thumb -> render -> cutout -> fanart.
    for field in IMAGE_FIELDS:
        image_url = player.get(field)
        if image_url:
            return build_preview_url(image_url, size), field
    return None, None


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip()).strip("_")
    return slug or "player"


def guess_extension(image_url: str, content_type: str | None) -> str:
    # Keep original extension when possible; fallback to MIME guessing.
    parsed = urlparse(image_url)
    suffix = Path(parsed.path).suffix
    if suffix:
        return suffix
    guessed = mimetypes.guess_extension(content_type or "")
    return guessed or ".jpg"


def download_avatar(player_name: str, output_dir: Path, size: str) -> dict:
    # Backward-compatible single-result wrapper (first downloaded or first status).
    results = download_avatars_for_name(player_name, output_dir, size)
    if not results:
        return {
            "requested_name": player_name,
            "status": "not_found",
            "reason": "No player match found in TheSportsDB.",
        }
    for item in results:
        if item.get("status") == "downloaded":
            return item
    return results[0]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        # Avoid Windows console encoding crashes for non-ASCII names.
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    args = parse_args()
    players = load_players(args)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    for index, player_name in enumerate(players):
        try:
            group = download_avatars_for_name(player_name, args.output_dir, args.size)
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
        except Exception as exc:  # pragma: no cover - defensive logging for API jobs
            group = [
                {
                    "requested_name": player_name,
                    "status": "error",
                    "reason": str(exc),
                }
            ]

        for result in group:
            results.append(result)
            print(json.dumps(result, ensure_ascii=False))

        if index < len(players) - 1:
            # Respect free tier rate limit by spacing requests.
            time.sleep(max(args.delay, 0))

    manifest_path = args.output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "source": "TheSportsDB Free Sports API",
                "api_base": API_BASE,
                "requested_players": players,
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    downloaded = sum(item.get("status") == "downloaded" for item in results)
    print(
        f"\nFinished. Downloaded {downloaded}/{len(results)} avatars. "
        f"Manifest: {manifest_path}"
    )
    return 0 if downloaded else 1


if __name__ == "__main__":
    sys.exit(main())
