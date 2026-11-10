#!/usr/bin/env python3
"""Regression checks for 20 additional TouchStation Extra reliability fixes."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/android.yml").read_text(encoding="utf-8")
LAB = (ROOT / "tools/templates/TouchStationExtraGameLab.kt").read_text(encoding="utf-8")
ADVANCED = (ROOT / "tools/templates/TouchStationExtraAdvancedSuite.kt").read_text(encoding="utf-8")
EXTRA100 = (ROOT / "tools/templates/TouchStationExtra100Suite.kt").read_text(encoding="utf-8")


class ExtraAdditionalBugfixTests(unittest.TestCase):
    def test_workflow_accepts_both_known_error_banner_thresholds(self):
        self.assertIn("GAME_ERROR_DISMISS_THRESHOLD_DP = 56|verticalDrag.value <= -72f", WORKFLOW)
        self.assertIn("detectVerticalDragGestures", WORKFLOW)
        self.assertIn("(200|220)", WORKFLOW)
        self.assertIn("Swipe this notice upward to dismiss it", WORKFLOW)

    def test_gamelab_title_id_uses_collision_resistant_hash(self):
        self.assertIn("private fun gameLabLegacyId", LAB)
        self.assertIn('MessageDigest.getInstance("SHA-256")', LAB)
        self.assertIn('return "$prefix-$digest"', LAB)

    def test_gamelab_device_identity_uses_full_fingerprint_hash(self):
        self.assertIn("private fun gameLabLegacyDeviceKey", LAB)
        self.assertIn("private fun gameLabDeviceKey(): String", LAB)
        self.assertIn('joinToString("|").lowercase(Locale.ROOT)', LAB)

    def test_gamelab_preference_migration_copies_then_removes_old_key(self):
        self.assertIn("private fun gameLabReadMigrated", LAB)
        self.assertIn("prefs.edit().putString(key, legacy).remove(legacyKey).apply()", LAB)

    def test_gamelab_history_uses_legacy_migration(self):
        self.assertIn("gameLabReadMigrated(context, gameLabHistoryKey(serial), gameLabLegacyHistoryKey(serial))", LAB)

    def test_gamelab_active_session_uses_legacy_migration(self):
        self.assertIn("gameLabReadMigrated(context, key, gameLabLegacyActiveKey(serial))", LAB)

    def test_gamelab_profile_uses_legacy_migration(self):
        self.assertIn("gameLabReadProfileRaw", LAB)
        self.assertIn("gameLabLegacyProfileKey(serial)", LAB)

    def test_active_session_must_parse_as_json_object(self):
        self.assertIn("runCatching { JSONObject(raw) }.getOrNull()", LAB)

    def test_active_session_requires_positive_start_time(self):
        self.assertIn('active.optLong("startedAt", 0L) <= 0L', LAB)

    def test_active_session_requires_event_array(self):
        self.assertIn('val events = active?.optJSONArray("events")', LAB)
        self.assertIn('val eventEntriesValid = events != null && events.length() in 1..40', LAB)
        self.assertIn('(0 until events.length()).all { events.optJSONObject(it) != null }', LAB)
        self.assertIn('!eventEntriesValid', LAB)

    def test_corrupt_active_key_is_removed_and_recovery_flag_saved(self):
        self.assertIn("prefs.edit().remove(key).putBoolean(gameLabRecoveryKey(serial), true).apply()", LAB)

    def test_corrupt_record_recovery_is_explained_to_user(self):
        self.assertIn("recoveredCorruptRecord", LAB)
        self.assertIn("An unreadable unfinished record was cleared.", LAB)

    def test_gamelab_profile_save_rejects_global_scope(self):
        self.assertIn('if (!gameScope) return "Select per-game settings scope before saving a game profile."', LAB)

    def test_gamelab_save_button_requires_per_game_scope(self):
        self.assertIn('enabled = canApply,\n                    modifier = Modifier.weight(1f),\n                ) { Text("Save current profile") }', LAB)

    def test_gamelab_profile_comparison_rejects_global_scope(self):
        self.assertIn('if (!gameScope) return "Select per-game settings scope before comparing a game profile."', LAB)

    def test_gamelab_compare_button_requires_per_game_scope(self):
        self.assertIn("enabled = canApply && savedProfile.value != null", LAB)

    def test_profile_diff_detects_removed_keys(self):
        self.assertIn("val savedKeys = saved.keys()", LAB)
        self.assertIn("val currentKeys = current.keys()", LAB)
        self.assertIn("saved.has(it) != current.has(it)", LAB)

    def test_settings_fingerprint_canonicalizes_nested_json(self):
        self.assertIn("private fun gameLabCanonicalJson(value: Any?): String", LAB)
        self.assertIn('keys.sorted().joinToString(prefix = "{", postfix = "}", separator = ",")', LAB)
        self.assertIn("gameLabCanonicalJson(settings.toJson())", LAB)

    def test_advanced_suite_uses_hashed_ids_and_migrates_legacy_data(self):
        self.assertIn("private fun extraAdvancedLegacyDeviceId", ADVANCED)
        self.assertIn("private fun extraAdvancedLegacyGameId", ADVANCED)
        self.assertIn("private fun extraAdvancedReadMigrated", ADVANCED)
        self.assertIn("extraAdvancedLegacyGameKey(serial)", ADVANCED)
        self.assertIn("extraAdvancedLegacyDeviceProfileKey(serial)", ADVANCED)
        self.assertIn("extraAdvancedLegacyProfileKey(serial, gameScope, slot)", ADVANCED)

    def test_advanced_settings_history_detects_removed_keys(self):
        self.assertIn("val oldKeys = oldJson.keys()", ADVANCED)
        self.assertIn("val newKeys = newJson.keys()", ADVANCED)
        self.assertIn("oldJson.has(it) != newJson.has(it)", ADVANCED)

    def test_save_picker_cancellation_keeps_previous_uri(self):
        save = EXTRA100.split("val saveFilePicker =", 1)[1].split("val backupDestinationPicker =", 1)[0]
        self.assertLess(save.index("if (uri != null)"), save.index("selectedSave.value = uri"))
        self.assertIn("the previous selection was kept", save)

    def test_restore_picker_cancellation_keeps_previous_uri(self):
        restore = EXTRA100.split("val restoreFilePicker =", 1)[1].split("val restoreDestinationPicker =", 1)[0]
        self.assertLess(restore.index("if (uri != null)"), restore.index("selectedRestore.value = uri"))
        self.assertIn("the previous selection was kept", restore)

    def test_controller_summary_ignores_virtual_input_devices(self):
        self.assertIn("if (device != null && !device.isVirtual)", EXTRA100)

    def test_report_share_actions_return_truthful_results(self):
        self.assertIn("private fun gameLabShare(context: Context, subject: String, report: String): Boolean", LAB)
        self.assertIn("private fun extra100Share(context: Context, report: String): Boolean", EXTRA100)
        self.assertIn("Could not open the Android share sheet", LAB)
        self.assertIn("Could not open the Android share sheet", EXTRA100)


if __name__ == "__main__":
    unittest.main(verbosity=2)
