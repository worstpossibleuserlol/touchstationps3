#!/usr/bin/env python3
"""Regression tests for the TouchStation Extra patcher."""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("touchstation_extra_suite.py")
SPEC = importlib.util.spec_from_file_location("touchstation_extra_suite", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
EXTRA = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EXTRA)


class ExtraPatchTests(unittest.TestCase):
    def test_version_promotion(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "build.gradle.kts"
            path.write_text('versionCode = 1200\nversionName = "TouchStation Finale"\n', encoding="utf-8")
            EXTRA.patch_version(Path(tmp))
            text = path.read_text(encoding="utf-8")
            self.assertIn("versionCode = 1300", text)
            self.assertIn('versionName = "TouchStation Extra"', text)

    def test_performance_tab_insertion(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "PerformanceTab.kt"
            path.write_text(
                "fun tab() {\n        TouchStationFinaleSuite(\n            settings = s,\n        )\n        SettingsDivider()\n\n    }\n",
                encoding="utf-8",
            )
            EXTRA.patch_performance_tab(Path(tmp))
            result = path.read_text(encoding="utf-8")
            self.assertEqual(result.count("TouchStationExtraDiagnostics("), 1)
            with self.assertRaises(SystemExit):
                EXTRA.patch_performance_tab(Path(tmp))

    def test_application_hook(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "src/main/java/com/armsx2/Pasx2Application.kt"
            path.parent.mkdir(parents=True)
            path.write_text(
                "package com.armsx2\nimport com.armsx2.reliability.TouchStationFinaleReliability\nfun boot() {\n    TouchStationFinaleReliability.install(this)\n}\n",
                encoding="utf-8",
            )
            EXTRA.patch_application(Path(tmp))
            result = path.read_text(encoding="utf-8")
            self.assertIn("TouchStationExtraCrashLoopGuard.install(this)", result)
            self.assertIn("import com.armsx2.reliability.TouchStationExtraCrashLoopGuard", result)
            with self.assertRaises(SystemExit):
                EXTRA.patch_application(Path(tmp))

    def test_feature_coverage_and_native_limits(self):
        for marker in (
            "PPU execution diagnostics", "PPU module validator", "PPU thread-state monitor",
            "PPU exception reporter", "PPU cache integrity", "SPU task diagnostics",
            "SPU workload monitor", "SPU timeout reporting", "SPU module validation",
            "Native engine self-test", "RSX command diagnostics", "FIFO queue health",
            "GPU synchronization", "Shader compilation tracker", "Shader cache recovery",
            "Vulkan capability checker", "Graphics driver report", "Frame pacing monitor",
            "Resolution scaling profiles", "Graphics settings rollback", "Game launch preflight",
            "Boot failure classifier", "Crash-loop protection", "Session recovery report",
            "Memory allocation diagnostics", "Cache cleanup manager", "Storage health warnings",
            "Android lifecycle protection", "Automated regression suite", "Per-game stability profiles",
            "N/A", "TouchStationExtraCrashLoopGuard",
        ):
            self.assertIn(marker, EXTRA.EXTRA_KOTLIN_SOURCE + EXTRA.EXTRA_CRASH_LOOP_KOTLIN_SOURCE)


if __name__ == "__main__":
    unittest.main(verbosity=2)
