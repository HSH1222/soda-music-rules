from __future__ import annotations

import argparse
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
import sys
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urlparse

from build_manifest import build_manifest


ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = ROOT / "major_label_blocklist.json"
SOURCES_PATH = ROOT / "sources.json"
SNAPSHOTS_PATH = ROOT / "source_snapshots.json"
REVIEW_PATH = ROOT / "review_queue.json"
MANIFEST_PATH = ROOT / "manifest.json"
ALLOWED_HOSTS = {
    "www.universalmusic.com",
    "www.sonymusic.com",
    "www.wmg.com",
}
SECTIONS = {"labels", "artists"}
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
IGNORED_NAMES = {"image", "back to top", "featured artists"}


def _clean(value: str) -> str:
    value = unicodedata.normalize("NFC", html.unescape(value))
    return re.sub(r"\s+", " ", value).strip(" \t\r\n:|-\u200b")


def _valid_name(value: str) -> bool:
    key = value.casefold()
    return 1 < len(value) <= 120 and key not in IGNORED_NAMES and not value.startswith("http")


class RosterParser(HTMLParser):
    def __init__(self, source: dict):
        super().__init__(convert_charrefs=True)
        self.source = source
        self.items: list[str] = []
        self.capture_depth = 0
        self.capture_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        parser = self.source["parser"]
        if parser == "attribute_prefix":
            value = values.get(self.source["attribute"], "")
            prefix = self.source["prefix"]
            if value.casefold().startswith(prefix.casefold()):
                self.items.append(_clean(value[len(prefix):]))
        should_capture = False
        if parser == "class_text":
            classes = values.get("class", "").split()
            should_capture = self.source["class_name"] in classes
        elif parser == "tag_text":
            should_capture = tag.casefold() == self.source["tag"].casefold()
        elif parser == "anchor_prefix":
            should_capture = tag.casefold() == "a"
        if should_capture and not self.capture_depth:
            self.capture_depth = 1
            self.capture_parts = []
        elif self.capture_depth:
            self.capture_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if not self.capture_depth:
            return
        self.capture_depth -= 1
        if self.capture_depth:
            return
        value = _clean("".join(self.capture_parts))
        if self.source["parser"] == "anchor_prefix":
            prefix = self.source["prefix"]
            if not value.casefold().startswith(prefix.casefold()):
                return
            value = _clean(value[len(prefix):])
        self.items.append(value)

    def handle_data(self, data: str) -> None:
        if self.capture_depth:
            self.capture_parts.append(data)


def parse_roster(page: str, source: dict) -> list[str]:
    parser = RosterParser(source)
    parser.feed(page)
    unique: dict[str, str] = {}
    for item in parser.items:
        item = _clean(item)
        if _valid_name(item):
            unique.setdefault(item.casefold(), item)
    return sorted(unique.values(), key=str.casefold)


def download(url: str) -> bytes:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError(f"source URL is not allowlisted: {url}")
    result = subprocess.run(
        [
            "curl", "--location", "--fail", "--silent", "--show-error",
            "--compressed", "--connect-timeout", "15", "--max-time", "45",
            "--user-agent", "SodaRulesMonitor/1.0 (+https://github.com/HSH1222/soda-music-rules)",
            url,
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if len(result.stdout) > MAX_RESPONSE_BYTES:
        raise ValueError(f"source response is too large: {url}")
    return result.stdout


def _read_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _next_version(current: str, date_text: str) -> str:
    prefix = date_text.replace("-", ".") + "."
    if current.startswith(prefix):
        try:
            return prefix + str(int(current[len(prefix):]) + 1)
        except ValueError:
            pass
    return prefix + "1"


def _append_unique(target: list, additions: list[str]) -> list[str]:
    known = {str(item).casefold() for item in target}
    added = []
    for value in additions:
        if value.casefold() not in known:
            target.append(value)
            known.add(value.casefold())
            added.append(value)
    target.sort(key=lambda item: str(item).casefold())
    return added


def collect(*, fetcher=download, today: str | None = None, dry_run: bool = False) -> dict:
    today = today or datetime.now(timezone.utc).date().isoformat()
    rules = _read_json(RULES_PATH, {})
    config = _read_json(SOURCES_PATH, {})
    snapshots = _read_json(SNAPSHOTS_PATH, {"schema_version": 1, "sources": {}})
    review = _read_json(REVIEW_PATH, {"schema_version": 1, "items": []})
    snapshot_sources = snapshots.setdefault("sources", {})
    review_items = review.setdefault("items", [])
    existing_review = {
        (str(item.get("source_id")), str(item.get("section")), str(item.get("value")).casefold())
        for item in review_items if isinstance(item, dict)
    }
    additions: dict[str, list[str]] = {}
    failures: list[str] = []
    summaries: list[str] = []

    for source in config.get("sources", []):
        source_id = str(source["id"])
        company = str(source["company"])
        section = str(source["section"])
        if section not in SECTIONS:
            raise ValueError(f"unsupported rules section: {section}")
        try:
            body = fetcher(str(source["url"]))
            page = body.decode("utf-8", "replace") if isinstance(body, bytes) else str(body)
            items = parse_roster(page, source)
            minimum = int(source["minimum_items"])
            if len(items) < minimum:
                raise ValueError(f"only {len(items)} items, expected at least {minimum}")
        except Exception as exc:
            failures.append(f"{source_id}: {exc}")
            continue

        previous = snapshot_sources.get(source_id, {})
        previous_items = [str(item) for item in previous.get("items", [])]
        previous_keys = {item.casefold() for item in previous_items}
        current_keys = {item.casefold() for item in items}
        removed = [item for item in previous_items if item.casefold() not in current_keys]
        new_since_snapshot = [item for item in items if item.casefold() not in previous_keys]
        target = rules.setdefault(section, {}).setdefault(company, [])
        added = _append_unique(target, items)
        if added:
            additions[f"{company}/{section}"] = added
        for value in removed:
            key = (source_id, section, value.casefold())
            if key not in existing_review:
                review_items.append({
                    "source_id": source_id,
                    "company": company,
                    "section": section,
                    "value": value,
                    "reason": "official_source_removed",
                    "detected_at": today,
                    "status": "pending",
                })
                existing_review.add(key)
        snapshot_sources[source_id] = {
            "company": company,
            "section": section,
            "url": source["url"],
            "content_sha256": hashlib.sha256(body if isinstance(body, bytes) else body.encode()).hexdigest(),
            "items": items,
        }
        summaries.append(
            f"{source_id}: {len(items)} items, {len(new_since_snapshot)} new on source, {len(removed)} removed"
        )

    if not summaries:
        raise RuntimeError("all official rule sources failed: " + " | ".join(failures))

    total_added = sum(len(values) for values in additions.values())
    if total_added:
        rules["database_version"] = _next_version(str(rules.get("database_version", "")), today)
        rules["updated_at"] = today
        entry = "官方名单自动更新：" + "；".join(
            f"{key} 新增 {len(values)} 项" for key, values in additions.items()
        )
        rules.setdefault("change_log", []).insert(0, entry)
    known_sources = list(rules.setdefault("sources", []))
    _append_unique(known_sources, [str(source["url"]) for source in config.get("sources", [])])
    rules["sources"] = known_sources

    result = {
        "added": total_added,
        "additions": additions,
        "failures": failures,
        "summaries": summaries,
    }
    if dry_run:
        return result
    _write_json(RULES_PATH, rules)
    _write_json(SNAPSHOTS_PATH, snapshots)
    _write_json(REVIEW_PATH, review)
    _write_json(MANIFEST_PATH, build_manifest())
    return result


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = collect(dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
