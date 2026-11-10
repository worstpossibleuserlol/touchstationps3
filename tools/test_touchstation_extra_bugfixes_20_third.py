#!/usr/bin/env python3
"""Regression checks for 20 more TouchStation Extra reliability fixes."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAB = (ROOT / "tools/templates/TouchStationExtraGameLab.kt").read_text(encoding="utf-8")
EXTRA100 = (ROOT / "tools/templates/TouchStationExtra100Suite.kt").read_text(encoding="utf-8")
ADVANCED = (ROOT / "tools/templates/TouchStationExtraAdvancedSuite.kt").read_text(encoding="utf-8")


class ExtraThirdBatchTests(unittest.TestCase):
    def test_provider_filename_control_characters_are_removed(self):
        self.assertIn("extra100CleanDisplayText(cursor.getString(nameIndex) ?: name)", EXTRA100)
        self.assertIn("!java.lang.Character.isISOControl(it)", EXTRA100)

    def test_provider_filename_length_is_bounded(self):
        self.assertIn("value.take(maxChars * 4)", EXTRA100)
        self.assertIn(".take(maxChars)", EXTRA100)
        self.assertIn("extra100CleanDisplayText(cursor.getString(nameIndex) ?: name)", EXTRA100)

    def test_negative_provider_size_is_unknown(self):
        self.assertIn("cursor.getLong(sizeIndex).takeIf { it >= 0L } ?: -1L", EXTRA100)

    def test_backup_uri_requires_persisted_read_grant(self):
        self.assertIn('extra100RestorePersistedReadUri(context, "selectedSaveUri")', EXTRA100)
        self.assertIn("it.uri == uri && it.isReadPermission", EXTRA100)

    def test_restore_uri_requires_persisted_read_grant(self):
        self.assertIn('extra100RestorePersistedReadUri(context, "selectedRestoreUri")', EXTRA100)
        self.assertIn("persistedUriPermissions.any", EXTRA100)

    def test_malformed_or_revoked_uri_preference_is_removed(self):
        self.assertIn("val uri = runCatching { Uri.parse(raw) }.getOrNull()", EXTRA100)
        self.assertIn("prefs.edit().remove(preferenceKey).apply()", EXTRA100)

    def test_same_saf_document_is_detected_across_uri_forms(self):
        self.assertIn("DocumentsContract.isDocumentUri(context, first)", EXTRA100)
        self.assertIn("DocumentsContract.getDocumentId(first) == DocumentsContract.getDocumentId(second)", EXTRA100)
        self.assertIn("extra100SameDocument(context, source, destination)", EXTRA100)

    def test_inspection_rethrows_cancellation(self):
        inspect = EXTRA100.split("private fun extra100InspectDocument", 1)[1].split("private fun extra100Digest", 1)[0]
        self.assertIn("catch (error: CancellationException)", inspect)
        self.assertIn("throw error", inspect)

    def test_backup_copy_rethrows_cancellation_after_cleanup(self):
        copy = EXTRA100.split("private fun extra100CopyAndVerify", 1)[1].split("private fun extra100TransferResult", 1)[0]
        self.assertIn("contentResolver.delete(destination, null, null)", copy)
        self.assertIn("if (error is CancellationException) throw error", copy)

    def test_restore_copy_rethrows_cancellation(self):
        transfer = EXTRA100.split("private fun extra100TransferResult", 1)[1].split("private fun extra100ControllerSummary", 1)[0]
        self.assertIn("catch (error: CancellationException)", transfer)
        self.assertIn("throw error", transfer)

    def test_controller_inventory_filters_physical_gamepad_joystick_and_dpad_devices(self):
        inventory = EXTRA100.split("private fun extra100ControllerSummary", 1)[1].split(
            "private fun extra100CaptureMetrics", 1
        )[0]
        self.assertIn("device != null && !device.isVirtual", inventory)
        self.assertIn("InputDevice.SOURCE_GAMEPAD", inventory)
        self.assertIn("InputDevice.SOURCE_JOYSTICK", inventory)
        self.assertIn("InputDevice.SOURCE_DPAD", inventory)
        # Compose KeyEvent has no supported native-device accessor in this pinned API.
        self.assertNotIn("event.nativeKeyEvent", EXTRA100)

    def test_diagnostic_key_probe_observes_but_does_not_consume_input(self):
        handler = EXTRA100.split(".onPreviewKeyEvent { event ->", 1)[1].split(
            "}.focusable()", 1
        )[0]
        self.assertIn("if (event.type == KeyEventType.KeyDown)", handler)
        self.assertIn('lastInput.value = "Digital key event: "', handler)
        self.assertTrue(handler.rstrip().endswith("false"))
        self.assertNotIn("isPhysicalController", handler)

    def test_controller_names_are_sanitized_and_bounded(self):
        self.assertIn("extra100CleanDisplayText(device.name, 80)", EXTRA100)

    def test_controller_summary_is_capped(self):
        self.assertIn("if (descriptions.size >= 16) break", EXTRA100)

    def test_safe_profile_obeys_ram_and_thermal_precompile_gate(self):
        self.assertIn("llvmPrecompile = TouchStationFinaleNativeDiagnostics.allowPpuPrecompile(context)", ADVANCED)
        self.assertNotIn("spuCache = true, llvmPrecompile = true", ADVANCED)

    def test_game_lab_uses_monotonic_session_start(self):
        self.assertIn("startedElapsedRealtime", LAB)
        self.assertIn("SystemClock.elapsedRealtime()", LAB)

    def test_game_lab_records_boot_count(self):
        self.assertIn("private fun gameLabBootCount(context: Context): Int", LAB)
        self.assertIn("Settings.Global.BOOT_COUNT", LAB)
        self.assertIn('.put("bootCount", gameLabBootCount(context))', LAB)

    def test_game_lab_duration_uses_monotonic_clock_and_fallback_label(self):
        self.assertIn("val monotonicDuration = if (sameBoot", LAB)
        self.assertIn('active.put("durationClock", if (monotonicDuration != null) "monotonic"', LAB)
        self.assertIn("wall-clock fallback (reboot or legacy session)", LAB)

    def test_active_session_game_identity_is_checked(self):
        self.assertIn("val gameIdentityValid = storedGameId == gameLabId(serial)", LAB)
        self.assertIn("storedGameId == gameLabLegacyId(serial)", LAB)

    def test_active_session_event_array_is_bounded_and_typed(self):
        self.assertIn("events.length() in 1..40", LAB)
        self.assertIn("events.optJSONObject(it) != null", LAB)
        self.assertIn("!eventEntriesValid || !gameIdentityValid", LAB)

    def test_game_lab_manual_stages_are_allowlisted(self):
        self.assertIn("val allowedStages = setOf(", LAB)
        self.assertIn('if (stage !in allowedStages) return "Unknown observation stage rejected."', LAB)

    def test_nested_profile_comparison_uses_canonical_json(self):
        self.assertIn("gameLabCanonicalJson(saved.opt(it)) != gameLabCanonicalJson(current.opt(it))", LAB)


if __name__ == "__main__":
    unittest.main(verbosity=2)
