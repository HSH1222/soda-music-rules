from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import unittest


TOOLS = Path(__file__).parent / "tools"
sys.path.insert(0, str(TOOLS))
spec = importlib.util.spec_from_file_location(
    "collect_official_rules", TOOLS / "collect_official_rules.py"
)
collector = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(collector)


class ParseRosterTests(unittest.TestCase):
    def test_attribute_prefix(self):
        source = {
            "parser": "attribute_prefix",
            "attribute": "alt",
            "prefix": "UMG Labels:",
        }
        page = '<img alt="UMG Labels: Def Jam Records"><img alt="unrelated">'
        self.assertEqual(collector.parse_roster(page, source), ["Def Jam Records"])

    def test_class_text_deduplicates(self):
        source = {"parser": "class_text", "class_name": "artist-name"}
        page = (
            '<div class="artist-name">Bruno <b>Mars</b></div>'
            '<div class="artist-name">Bruno Mars</div>'
        )
        self.assertEqual(collector.parse_roster(page, source), ["Bruno Mars"])

    def test_anchor_prefix(self):
        source = {"parser": "anchor_prefix", "prefix": "Visit "}
        page = '<a href="/x">Visit Atlantic Music Group</a><a>Home</a>'
        self.assertEqual(collector.parse_roster(page, source), ["Atlantic Music Group"])

    def test_version_increments_same_day(self):
        self.assertEqual(collector._next_version("2026.08.15.3", "2026-08-15"), "2026.08.15.4")

    def test_version_starts_new_day(self):
        self.assertEqual(collector._next_version("2026.08.14.7", "2026-08-15"), "2026.08.15.1")


if __name__ == "__main__":
    unittest.main()
