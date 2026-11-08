#!/usr/bin/env python3
"""Fast regression tests for the TouchStation Finale source patcher."""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("touchstation_finale_suite.py")
SPEC = importlib.util.spec_from_file_location("touchstation_finale_suite", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
FINALE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FINALE)


class FinalePatchTests(unittest.TestCase):
    def test_version_promotion_is_exact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            app = Path(temporary)
            gradle = app / "build.gradle.kts"
            gradle.write_text(
                'defaultConfig {\n    versionCode = 1100\n    versionName = "11.0.0"\n}\n',
                encoding="utf-8",
            )
            FINALE.patch_version(app)
            result = gradle.read_text(encoding="utf-8")
            self.assertIn("versionCode = 1200", result)
            self.assertIn('versionName = "Finale"', result)
            self.assertNotIn("versionCode = 1100", result)

    def test_version_promotion_rejects_unexpected_input(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            app = Path(temporary)
            gradle = app / "build.gradle.kts"
            gradle.write_text(
                'defaultConfig {\n    versionCode = 1199\n    versionName = "RC"\n}\n',
                encoding="utf-8",
            )
            with self.assertRaises(SystemExit):
                FINALE.patch_version(app)

    def test_performance_tab_insertion_is_single_and_idempotency_guarded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            app = Path(temporary)
            source = app / "src/main/java/com/armsx2/ui/settings/PerformanceTab.kt"
            source.parent.mkdir(parents=True)
            source.write_text(
                """package com.armsx2.ui.settings
fun PerformanceTab() {
    Column {
        TouchStation11ReliabilitySuite(
            settings = s,
            onApply = { updated ->
                runCatching {
                    apply(updated)
                    InGameOverlay.reloadSettings()
                    true
                }.getOrDefault(false)
            },
        )
        SettingsDivider()

    }
}
""",
                encoding="utf-8",
            )
            FINALE.patch_performance_tab(app)
            result = source.read_text(encoding="utf-8")
            self.assertEqual(result.count("TouchStationFinaleSuite("), 1)
            self.assertIn("saved.ps3.spuXFloat == updated.ps3.spuXFloat", result)
            with self.assertRaises(SystemExit):
                FINALE.patch_performance_tab(app)

    def test_finale_source_has_exact_id_compatibility_and_safe_profile(self) -> None:
        source = FINALE.KOTLIN_SOURCE
        for marker in (
            "https://rpcs3.net/compatibility/?api=v1&export",
            "touchStationFinaleNormaliseId",
            "Full library compatibility index",
            "Apply GTA IV per-game profile",
            "settingsArePerGame",
            "spuXFloat = 0",
            "spuBlockSize = 0",
            "shaderMode = 1",
            "msaaMode = 0",
            "Export Finale diagnostic report",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)

    def test_native_metrics_are_not_fabricated(self) -> None:
        source = FINALE.KOTLIN_SOURCE
        self.assertIn("GPU utilization and exact Vulkan extensions remain N/A", source)
        self.assertIn("FPS and frametime are supplied only by the native in-game overlay", source)
        self.assertIn("Official status is a desktop RPCS3 reference", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
