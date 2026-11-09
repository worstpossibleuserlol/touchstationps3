#!/usr/bin/env python3
"""Regression tests for TouchStation Extra advanced feature integration."""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("touchstation_extra_advanced.py")
SPEC = importlib.util.spec_from_file_location("touchstation_extra_advanced", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
ADV = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ADV)
TEMPLATE = Path(__file__).parent / "templates" / "TouchStationExtraAdvancedSuite.kt"
SOURCE = TEMPLATE.read_text(encoding="utf-8")


class ExtraAdvancedTests(unittest.TestCase):
    def test_performance_tab_inserts_advanced_suite_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "src/main/java/com/armsx2/ui/settings/PerformanceTab.kt"
            path.parent.mkdir(parents=True)
            path.write_text(
                "fun tab() {\n        TouchStationExtraDiagnostics(\n            settings = s,\n        )\n        SettingsDivider()\n\n    }\n",
                encoding="utf-8",
            )
            ADV.patch_performance_tab(Path(tmp))
            result = path.read_text(encoding="utf-8")
            self.assertEqual(result.count("TouchStationExtraAdvancedSuite("), 1)
            with self.assertRaises(SystemExit):
                ADV.patch_performance_tab(Path(tmp))

    def test_settings_history_hook_records_all_saved_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "src/main/java/com/armsx2/ui/InGameOverlay.kt"
            path.parent.mkdir(parents=True)
            path.write_text(
                "package com.armsx2.ui\nimport com.armsx2.runtime.MainActivityRuntime\n"
                "fun saveSettings(updated: Settings) {\n    val previous = settingsState.value\n"
                "        ConfigStore.save(settingsScope.value, currentSerial.value, updated, previous)\n}\n",
                encoding="utf-8",
            )
            ADV.patch_settings_history(Path(tmp))
            result = path.read_text(encoding="utf-8")
            self.assertIn("TouchStationExtraSettingsHistory.record(", result)
            self.assertIn("previous,", result)
            self.assertIn("updated,", result)
            self.assertLess(result.index("ConfigStore.save("), result.index("TouchStationExtraSettingsHistory.record("))
            with self.assertRaises(SystemExit):
                ADV.patch_settings_history(Path(tmp))

    def test_all_50_feature_areas_are_present(self):
        markers = (
            "Pre-launch crash predictor", "Automatic crash detection", "Crash reason analyzer",
            "Safe game boot", "Automatic configuration recovery", "Game session watchdog",
            "Memory pressure protection", "Thermal protection", "Crash history per game",
            "Stability score", "Expanded compatibility database", "Compatibility confidence",
            "Device-specific compatibility profile", "Compatibility regression detector",
            "Game boot stage tracker", "Known issue matching", "Per-game configuration recommendations",
            "Compatibility report generator", "Controller compatibility database",
            "Firmware / game update warnings", "PPU execution profiler", "PPU LLVM compilation monitor",
            "PPU interpreter fallback", "PPU thread configuration advisor", "PPU module loading diagnostics",
            "PPU compilation cache validation", "SPU workload distribution", "SPU decoder comparison",
            "SPU thread starvation detector", "SPU compilation failure recovery", "SPU cache management",
            "SPU performance advisor", "RSX command-stream diagnostics", "FIFO deadlock diagnostics",
            "RSX synchronization monitor", "Shader compilation failure recovery", "Shader cache version manager",
            "GPU driver compatibility profiles", "Dynamic resolution recommendations", "Frame pacing optimizer",
            "Complete settings search", "Settings profiles", "One-tap settings reset", "Settings change history",
            "Advanced setting descriptions", "Automatic device detection", "Battery and performance modes",
            "Background activity controls", "Storage manager", "Diagnostics dashboard",
        )
        for marker in markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, SOURCE)

    def test_compose_row_helper_is_annotated(self):
        self.assertIn("@Composable\nprivate fun extraAdvancedRow", SOURCE)

    def test_settings_search_covers_serialized_settings_and_storage_scan_is_bounded_off_ui(self):
        self.assertIn("extraAdvancedSettingGuide(settings)", SOURCE)
        self.assertIn("settings.toJson()", SOURCE)
        self.assertIn("withContext(Dispatchers.IO)", SOURCE)
        self.assertNotIn("size(context.filesDir)", SOURCE)
        self.assertIn("object TouchStationExtraSettingsHistory", SOURCE)

    def test_native_telemetry_limits_are_explicit(self):
        for marker in (
            "native instruction counters=N/A", "native worker distribution=N/A",
            "GPU fence and RSX synchronization counters=N/A",
            "physical GPU utilization", "not a compatibility rating",
            "not a prediction", "guest-game crashes",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, SOURCE)


if __name__ == "__main__":
    unittest.main(verbosity=2)
