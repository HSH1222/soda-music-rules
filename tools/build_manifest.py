from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = ROOT / "major_label_blocklist.json"
MANIFEST_PATH = ROOT / "manifest.json"


def build_manifest() -> dict:
    rules_bytes = RULES_PATH.read_bytes()
    rules = json.loads(rules_bytes.decode("utf-8"))
    return {
        "schema_version": 1,
        "database_version": str(rules["database_version"]),
        "updated_at": str(rules["updated_at"]),
        "rules": {
            "path": "major_label_blocklist.json",
            "sha256": hashlib.sha256(rules_bytes).hexdigest(),
            "size": len(rules_bytes),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = json.dumps(build_manifest(), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        actual = MANIFEST_PATH.read_text(encoding="utf-8") if MANIFEST_PATH.exists() else ""
        if actual != expected:
            raise SystemExit("manifest.json 与规则文件不一致，请重新生成")
        return 0
    MANIFEST_PATH.write_text(expected, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
