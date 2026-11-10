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
        self.assertIn('return "Copied and re-read $bytes bytes. SHA-256 verified: $actual"', SOURCE)
        self.assertNotIn("nativeKeyEvent", SOURCE)
        self.assertIn("import androidx.compose.ui.input.key.key", SOURCE)
        self.assertIn("val deviceIds: IntArray = InputDevice.getDeviceIds()", SOURCE)
        self.assertNotIn("InputDevice.getDeviceIds().mapNotNull", SOURCE)

    def test_game_file_validation_does_not_claim_full_integrity(self):
        self.assertIn("Bounded read-only signature inspection", SOURCE)
        self.assertIn("not a full PS3 image", SOURCE)
        self.assertIn("7F504B47", SOURCE)
        self.assertIn("ISO9660 volume descriptor", SOURCE)
        self.assertIn("UDF volume recognition descriptor", SOURCE)
        self.assertIn("bounded read-only header signature checks", SOURCE)

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


    def test_game_ids_are_collision_resistant_and_legacy_metadata_is_migrated(self):
        self.assertIn("extra100LegacyGameId", SOURCE)
        self.assertIn('MessageDigest.getInstance("SHA-256")', SOURCE)
        self.assertIn("prefs.getString(currentKey, null) ?: prefs.getString(legacyKey", SOURCE)
        self.assertIn("editor.remove(legacyKey).remove(legacyHistoryKey)", SOURCE)
        self.assertIn("migrateLegacyHistory", SOURCE)
        self.assertIn("if (migrateLegacyHistory) editor.putString(historyKey, history.toString())", SOURCE)
        self.assertIn('.put("serial", serial.trim().take(80))', SOURCE)

    def test_metadata_is_bounded_and_history_is_written_together(self):
        for marker in ('title.trim().take(120)', 'category.trim().take(60)',
                       'tags.trim().take(240)', 'status.trim().take(80)',
                       'knownIssues.trim().take(1200)', 'firmwareNote.trim().take(500)',
                       'updateNote.trim().take(500)', 'notes.trim().take(2000)',
                       'editor.putString(historyKey, updated.toString())'):
            with self.subTest(marker=marker):
                self.assertIn(marker, SOURCE)

    def test_stream_readers_handle_zero_length_reads(self):
        self.assertGreaterEqual(SOURCE.count('if (count == 0) {'), 3)
        self.assertIn('digest.update(one.toByte())', SOURCE)
        self.assertIn('prefix[prefixCount++] = one.toByte()', SOURCE)
        self.assertIn('marker[markerCount++] = one.toByte()', SOURCE)

    def test_copy_refuses_same_uri_and_cleans_partial_destination(self):
        self.assertIn('require(source != destination)', SOURCE)
        self.assertIn('contentResolver.delete(destination, null, null)', SOURCE)
        self.assertIn('Destination checksum differs from source', SOURCE)

    def test_copy_size_counter_is_overflow_safe(self):
        self.assertIn('bytes > Long.MAX_VALUE - count.toLong()', SOURCE)
        self.assertIn('bytes == Long.MAX_VALUE', SOURCE)

    def test_document_permissions_and_playtime_lifecycle_are_hardened(self):
        self.assertIn('takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION)', SOURCE)
        self.assertGreaterEqual(SOURCE.count('extra100PersistReadPermission(context, uri)'), 3)
        self.assertIn('prefs.getString("selectedSaveUri", null)', SOURCE)
        self.assertIn('prefs.getString("selectedRestoreUri", null)', SOURCE)
        self.assertIn('putString("selectedSaveUri", uri.toString())', SOURCE)
        self.assertIn('putString("selectedRestoreUri", uri.toString())', SOURCE)
        self.assertIn('LaunchedEffect(serial, sessionStart.value)', SOURCE)
        self.assertIn('extra100SaturatingAdd(totalPlaytime.value, liveElapsed.value)', SOURCE)
        self.assertIn('totalPlaytime.value = extra100SaturatingAdd(totalPlaytime.value, elapsed)', SOURCE)
        self.assertIn('liveElapsed.value = 0L', SOURCE)

    def test_template_annotation_and_version_identity(self):
        self.assertIn("@Composable\nfun TouchStationExtra100Suite", SOURCE)
        self.assertIn('"TouchStation Extra · 100-feature companion suite"', SOURCE)


if __name__ == "__main__":
    unittest.main(verbosity=2)
