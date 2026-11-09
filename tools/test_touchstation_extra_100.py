#!/usr/bin/env python3
"""Regression tests for the TouchStation Extra 100-feature companion suite."""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("touchstation_extra_100.py")
SPEC = importlib.util.spec_from_file_location("touchstation_extra_100", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
PATCHER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCHER)
TEMPLATE = Path(__file__).parent / "templates" / "TouchStationExtra100Suite.kt"
SOURCE = TEMPLATE.read_text(encoding="utf-8")


class Extra100Tests(unittest.TestCase):
    def test_all_feature_groups_are_present(self):
        for marker in (
            "51–60 · Game library companion", "61–70 · Save-data and file safety",
            "71–80 · Controller and input checks", "81–90 · Personalization and session tracking",
            "91–100 · Diagnostics, performance evidence and recovery",
            "Save selected-game metadata", "Search saved game entries",
            "Inspect selected game file", "Create verified save-data backup",
            "Copy backup to a chosen destination", "Refresh Android controller list",
            "Start session", "Stop and save", "Capture Android performance snapshot",
            "Run app-side regression and readiness checks",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, SOURCE)

    def test_backup_is_streamed_and_verified(self):
        self.assertIn("ByteArray(64 * 1024)", SOURCE)
        self.assertIn('MessageDigest.getInstance("SHA-256")', SOURCE)
        self.assertIn("val actual = extra100Digest(context, destination)", SOURCE)
        self.assertIn("check(expected == actual)", SOURCE)

    def test_game_file_validation_does_not_claim_full_integrity(self):
        self.assertIn("metadata/readability check", SOURCE)
        self.assertIn("not a full PS3 image", SOURCE)

    def test_native_metrics_are_not_fabricated(self):
        for marker in ("not PS3 guest CPU/GPU counters", "Analog axis calibration",
                       "guest crash callbacks", "native core exports them"):
            self.assertIn(marker, SOURCE)

    def test_performance_tab_insertion(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "src/main/java/com/armsx2/ui/settings/PerformanceTab.kt"
            path.parent.mkdir(parents=True)
            path.write_text(
                "fun tab() {\n        TouchStationExtraAdvancedSuite(settings = s)\n"
                "        SettingsDivider()\n\n    }\n", encoding="utf-8")
            PATCHER.patch_performance_tab(Path(tmp))
            result = path.read_text(encoding="utf-8")
            self.assertEqual(result.count("TouchStationExtra100Suite("), 1)
            self.assertLess(result.index("TouchStationExtraAdvancedSuite("),
                            result.index("TouchStationExtra100Suite("))
            with self.assertRaises(SystemExit):
                PATCHER.patch_performance_tab(Path(tmp))

    def test_template_annotation_and_version_identity(self):
        self.assertIn("@Composable\nfun TouchStationExtra100Suite", SOURCE)
        self.assertIn('"TouchStation Extra · 100-feature companion suite"', SOURCE)


if __name__ == "__main__":
    unittest.main(verbosity=2)
