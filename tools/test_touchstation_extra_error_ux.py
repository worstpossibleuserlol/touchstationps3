#!/usr/bin/env python3
"""Regression tests for the TouchStation Extra game-error UX patcher."""
from __future__ import annotations
import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("touchstation_extra_error_ux.py")
SPEC = importlib.util.spec_from_file_location("touchstation_extra_error_ux", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
PATCHER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCHER)
TEMPLATE = Path(__file__).parent / "templates" / "TouchStationExtraErrorUX.kt"
SOURCE = TEMPLATE.read_text(encoding="utf-8")

class ExtraErrorUxTests(unittest.TestCase):
    def test_patch_replaces_only_a_recognised_upstream_error_banner(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "app" / PATCHER.TARGET
            target.parent.mkdir(parents=True)
            target.write_text(
                "object GameErrorNotice { fun show(error: String) {} }\n"
                "@Composable fun GameErrorBanner() { AnimatedVisibility(true) { slideOutVertically {} } }\n",
                encoding="utf-8",
            )
            PATCHER.patch(Path(tmp))
            result = target.read_text(encoding="utf-8")
            self.assertIn("detectVerticalDragGestures", result)
            self.assertIn("Swipe up or tap to dismiss", result)
            # Re-running against a complete installation must be idempotent.
            PATCHER.patch(Path(tmp))

    def test_partial_existing_swipe_handler_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "app" / PATCHER.TARGET
            target.parent.mkdir(parents=True)
            target.write_text(
                "object GameErrorNotice { fun show(error: String) {} }\\n"
                "fun GameErrorBanner() { detectVerticalDragGestures {} }\\n",
                encoding="utf-8",
            )
            with self.assertRaises(SystemExit):
                PATCHER.patch(Path(tmp))

    def test_missing_upstream_file_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                PATCHER.patch(Path(tmp))

    def test_swipe_up_has_a_real_threshold_and_only_upward_drag_dismisses(self):
        self.assertIn("GAME_ERROR_DISMISS_THRESHOLD_DP = 56", SOURCE)
        self.assertIn("totalVerticalDragPx <= -dismissThresholdPx", SOURCE)
        self.assertIn("onDragCancel = { totalVerticalDragPx = 0f }", SOURCE)
        self.assertIn("onDragStart = { totalVerticalDragPx = 0f }", SOURCE)

    def test_tap_and_accessibility_dismissal_are_preserved(self):
        self.assertIn("role = Role.Button", SOURCE)
        self.assertIn('onClickLabel = "Dismiss game error"', SOURCE)
        self.assertIn("Swipe up or tap to dismiss", SOURCE)
        self.assertIn("GameErrorNotice.clear()", SOURCE)

    def test_dismissal_animates_up_and_fades(self):
        self.assertIn("fadeOut(tween(160))", SOURCE)
        self.assertIn("slideOutVertically(tween(220)) { -it }", SOURCE)
        self.assertIn("slideInVertically(tween(240)) { -it }", SOURCE)

    def test_error_text_is_bounded_sanitised_and_deduplicated(self):
        for marker in (
            "error.lineSequence().firstOrNull { it.isNotBlank() }",
            "java.lang.Character.isISOControl",
            "GAME_ERROR_NOTICE_MAX_CHARS = 240",
            "if (cleaned.isBlank()) return",
            "if (previous == preview) return",
            "if (!wasVisible && !xmbActive)",
            "runCatching { MenuSfx.play(MenuSfx.Event.POPUP_OPEN) }",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, SOURCE)

    def test_xmb_route_and_exit_animation_content_are_safe(self):
        self.assertIn("xmbGameError(reason)", SOURCE)
        self.assertIn("LaunchedEffect(reason)", SOURCE)
        self.assertIn("if (!reason.isNullOrBlank()) shown.value = reason", SOURCE)
        self.assertIn("shown.value", SOURCE)
        self.assertIn("WindowInsets.safeDrawing.only(WindowInsetsSides.Top)", SOURCE)
        self.assertIn(".widthIn(max = 560.dp)", SOURCE)

    def test_twenty_error_handling_and_dismissal_regressions_are_documented(self):
        expected = (
            "first non-empty line", "trimmed preview", "control-character filtering",
            "240-character display cap", "blank-message rejection", "duplicate-message coalescing",
            "one sound per visible incident", "replacement without repeated sound",
            "XMB error-dialog routing", "safe XMB-state lookup", "safe notification sound",
            "nonblank-only visibility", "message-keyed gesture lifecycle", "vertical swipe recognition",
            "56 dp upward threshold", "downward-swipe preservation", "horizontal-gesture preservation",
            "cancelled-gesture reset", "accessible tap dismissal", "upward animated dismissal",
        )
        doc = (Path(__file__).parents[1] / "docs" / "EXTRA_ERROR_UX_20.md").read_text(encoding="utf-8")
        self.assertEqual(sum(1 for item in expected if item in doc), 20)

if __name__ == "__main__":
    unittest.main(verbosity=2)
