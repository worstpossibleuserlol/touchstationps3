#!/usr/bin/env python3
"""Regression tests for the TouchStation Extra Game Compatibility Lab."""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("touchstation_extra_game_lab.py")
SPEC = importlib.util.spec_from_file_location("touchstation_extra_game_lab", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
PATCHER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCHER)
TEMPLATE = Path(__file__).parent / "templates" / "TouchStationExtraGameLab.kt"
SOURCE = TEMPLATE.read_text(encoding="utf-8")


class ExtraGameLabTests(unittest.TestCase):
    def test_performance_tab_insertion_is_ordered_and_duplicate_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "src/main/java/com/armsx2/ui/settings/PerformanceTab.kt"
            path.parent.mkdir(parents=True)
            path.write_text(
                "fun tab() {\n"
                "        TouchStationExtra100Suite(settings = s)\n"
                "        SettingsDivider()\n\n"
                "    }\n",
                encoding="utf-8",
            )
            PATCHER.patch_performance_tab(Path(tmp))
            result = path.read_text(encoding="utf-8")
            self.assertEqual(result.count("TouchStationExtraGameLabSuite("), 1)
            self.assertLess(result.index("TouchStationExtra100Suite("),
                            result.index("TouchStationExtraGameLabSuite("))
            with self.assertRaises(SystemExit):
                PATCHER.patch_performance_tab(Path(tmp))

    def test_gta_iv_profile_is_exact_title_id_and_game_scope_guarded(self):
        self.assertIn('equals("BLES00229", ignoreCase = true)', SOURCE)
        self.assertIn("SettingsScope.Game", SOURCE)
        self.assertIn("Apply GTA IV conservative test profile", SOURCE)
        self.assertIn("has not been validated as playable", SOURCE)

    def test_repeatable_session_captures_configuration_and_device_evidence(self):
        for marker in (
            "settingsSha256", "availableRamMb", "appPssMb", "freeStorageMb",
            "thermal", "nativeRuntimeReady", "Repeatable launch test",
            "gameLabRecord", "gameLabFinish", "gameLabHistorySummary",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, SOURCE)

    def test_same_settings_regression_is_evidence_limited(self):
        self.assertIn("Possible same-settings regression", SOURCE)
        self.assertIn("exact current settings fingerprint", SOURCE)
        self.assertIn("not a compatibility percentage", SOURCE)

    def test_interrupted_session_is_not_mislabeled_as_a_crash(self):
        self.assertIn("cause is unknown and is not proof of a guest-game crash", SOURCE)
        self.assertIn("inconclusive / interrupted", SOURCE)

    def test_native_engine_boundaries_are_explicit(self):
        for marker in (
            "Native PPU/SPU/RSX counters",
            "guest crash callbacks remain unavailable",
            "does not launch or benchmark the game automatically",
            "not proof that a game is universally compatible",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, SOURCE)


if __name__ == "__main__":
    unittest.main(verbosity=2)
