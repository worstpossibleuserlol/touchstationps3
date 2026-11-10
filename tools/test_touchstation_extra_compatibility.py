#!/usr/bin/env python3
"""Regression tests for TouchStation Extra - Compatibility."""
from __future__ import annotations

import importlib.util
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = Path(__file__).with_name("touchstation_extra_compatibility.py")
SPEC = importlib.util.spec_from_file_location("touchstation_extra_compatibility", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
PATCHER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCHER)
TEMPLATE = (ROOT / "tools/templates/TouchStationExtraCompatibility.kt").read_text(encoding="utf-8")
DOC = (ROOT / "docs/EXTRA_COMPATIBILITY_50.md").read_text(encoding="utf-8")


class ExtraCompatibilityTests(unittest.TestCase):
    def test_performance_tab_insertion_follows_game_lab_and_is_duplicate_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "src/main/java/com/armsx2/ui/settings/PerformanceTab.kt"
            path.parent.mkdir(parents=True)
            path.write_text("fun tab() {\n" + PATCHER.GAME_LAB_BLOCK + "    }\n", encoding="utf-8")
            PATCHER.patch_performance_tab(Path(tmp))
            result = path.read_text(encoding="utf-8")
            self.assertEqual(result.count("TouchStationExtraCompatibilitySuite("), 1)
            self.assertLess(result.index("TouchStationExtraGameLabSuite("), result.index("TouchStationExtraCompatibilitySuite("))
            with self.assertRaises(SystemExit):
                PATCHER.patch_performance_tab(Path(tmp))

    def test_universal_profiles_are_per_game_and_use_existing_validated_settings(self):
        self.assertIn("Apply Universal Compatibility Profile", TEMPLATE)
        self.assertIn("Apply Low-Memory Compatibility Profile", TEMPLATE)
        self.assertIn("SettingsScope.Game", TEMPLATE)
        self.assertIn("TouchStationFinaleReliability.validateSettings(candidate)", TEMPLATE)
        self.assertIn("spuDecoder = 3", TEMPLATE)
        self.assertIn("msaaMode = 0", TEMPLATE)
        self.assertIn("full settings read-back verified", TEMPLATE)

    def test_gta_iv_profile_requires_exact_bles00229_serial(self):
        self.assertIn('game?.serial?.equals("BLES00229", ignoreCase = true) == true', TEMPLATE)
        self.assertIn("Apply GTA IV BLES00229 Profile", TEMPLATE)
        self.assertIn("extraCompatibilityCandidate(settings, snapshot.value, true, true)", TEMPLATE)
        self.assertIn("Hidden for other games", TEMPLATE)

    def test_android_preflight_reports_device_evidence_without_claiming_guest_telemetry(self):
        for marker in (
            "FEATURE_VULKAN_HARDWARE_LEVEL",
            "libarmsx3-core.so",
            "libarmsx3-jni.so",
            "App PSS",
            "Thermal status",
            "does not launch or certify the selected game",
            "live Vulkan device/extension query",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, TEMPLATE)

    def test_report_and_game_record_are_scoped_by_hashed_title_id(self):
        self.assertIn('return "game.$digest"', TEMPLATE)
        self.assertIn("extraCompatibilitySaveRecord", TEMPLATE)
        self.assertIn("putString(extraCompatibilityGameKey(serial), record.toString())", TEMPLATE)
        self.assertIn("Share compatibility preflight", TEMPLATE)

    def test_requested_feature_map_has_exactly_fifty_features(self):
        first, second = DOC.split("## 21–50 · Expanded game compatibility", 1)
        first = first.split("## 1–20 · PPU / SPU / RSX / GTA IV foundations", 1)[1]
        first_count = len(re.findall(r"(?m)^\d+\. \*\*", first))
        second_count = len(re.findall(r"(?m)^\d+\. \*\*", second.split("## Native-core boundary", 1)[0]))
        self.assertEqual(first_count, 20)
        self.assertEqual(second_count, 30)
        self.assertIn("EXTRA_COMPATIBILITY_FEATURES", TEMPLATE)
        self.assertIn("Show 50-feature implementation map", TEMPLATE)
        self.assertIn("extraCompatibilityFeatureAudit", TEMPLATE)
        self.assertEqual(len(re.findall(r"(?m)^\d+\. \*\*", DOC)), 50)

    def test_gta_iv_diagnostic_snapshot_captures_settings_and_failure_stage(self):
        for marker in (
            "failureStage",
            "extraCompatibilitySettingsFingerprint",
            "Settings SHA-256:",
            "Capture GTA IV diagnostic snapshot",
            "PPU instruction/module trace: NOT EXPOSED BY PINNED NATIVE CORE",
            "SPU worker queue, scheduling and starvation counters: NOT EXPOSED BY PINNED NATIVE CORE",
            "RSX command queue and GPU-fence trace: NOT EXPOSED BY PINNED NATIVE CORE",
            "Guest save-state schema/checksum validation: NOT EXPOSED BY PINNED NATIVE CORE",
            "50-feature compatibility map",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, TEMPLATE)

    def test_native_core_boundaries_are_explicit(self):
        for marker in ("NATIVE CORE REQUIRED", "prebuilt ARM64", "not claimed as fixed", "device testing", "PPU", "SPU", "RSX"):
            with self.subTest(marker=marker):
                self.assertIn(marker, DOC)


if __name__ == "__main__":
    unittest.main(verbosity=2)
