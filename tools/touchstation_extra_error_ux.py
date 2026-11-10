#!/usr/bin/env python3
"""Install the swipe-to-dismiss, bounded and accessible game-error banner."""
from __future__ import annotations
import argparse
from pathlib import Path

TEMPLATE = Path(__file__).parent / "templates" / "TouchStationExtraErrorUX.kt"
TARGET = Path("src/main/java/com/armsx2/ui/emulation/GameErrorBanner.kt")
BASELINE_MARKERS = (
    "object GameErrorNotice", "fun show(error: String)",
    "fun GameErrorBanner()", "AnimatedVisibility(", "slideOutVertically",
)
NEW_MARKERS = (
    "detectVerticalDragGestures", "GAME_ERROR_DISMISS_THRESHOLD_DP",
    "GAME_ERROR_NOTICE_MAX_CHARS", "onDragCancel",
    'onClickLabel = "Dismiss game error"',
    "Swipe up or tap to dismiss", "slideOutVertically(tween(220)) { -it }",
    "java.lang.Character.isISOControl",
)

def patch(source_root: Path) -> None:
    target = source_root / "app" / TARGET
    if not target.is_file():
        raise SystemExit("Expected upstream GameErrorBanner.kt was not found: " + str(target))
    if not TEMPLATE.is_file():
        raise SystemExit("TouchStation Extra error UX template is missing: " + str(TEMPLATE))
    current = target.read_text(encoding="utf-8")
    if "detectVerticalDragGestures" in current:
        missing_existing = [marker for marker in NEW_MARKERS if marker not in current]
        if missing_existing:
            raise SystemExit(
                "Found a partial or incompatible swipe-to-dismiss implementation; missing: "
                + ", ".join(missing_existing)
            )
        print("Swipe-up error UX is already complete; leaving the upstream source unchanged.")
        return
    missing = [marker for marker in BASELINE_MARKERS if marker not in current]
    if missing:
        raise SystemExit("Unexpected upstream GameErrorBanner.kt; missing: " + ", ".join(missing))
    updated = TEMPLATE.read_text(encoding="utf-8")
    missing_new = [marker for marker in NEW_MARKERS if marker not in updated]
    if missing_new:
        raise SystemExit("Error UX template is incomplete; missing: " + ", ".join(missing_new))
    target.write_text(updated, encoding="utf-8")
    print("Installed swipe-up dismiss, upward exit animation, safe error text and accessibility label.")

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path, help="Pinned ARMSX3 Android source root")
    args = parser.parse_args()
    patch(args.source)

if __name__ == "__main__":
    main()
