#!/usr/bin/env python3
"""Install the TouchStation Extra universal and GTA IV compatibility center."""
from __future__ import annotations

import argparse
from pathlib import Path

TEMPLATE = Path(__file__).parent / "templates" / "TouchStationExtraCompatibility.kt"
GAME_LAB_BLOCK = """        TouchStationExtraGameLabSuite(
            settings = s,
            onApply = { updated ->
                runCatching {
                    apply(updated)
                    InGameOverlay.reloadSettings()
                    val saved = InGameOverlay.settingsState.value
                    saved.toJson().toString() == updated.toJson().toString()
                }.getOrDefault(false)
            },
        )
        SettingsDivider()

"""


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"Expected exactly one {label} marker; found {count}")
    return source.replace(old, new, 1)


def patch_performance_tab(app_dir: Path) -> None:
    path = app_dir / "src/main/java/com/armsx2/ui/settings/PerformanceTab.kt"
    source = path.read_text(encoding="utf-8")
    if "TouchStationExtraCompatibilitySuite(" in source:
        raise SystemExit("TouchStation Extra Compatibility Center is already inserted")
    callback = """onApply = { updated ->
                runCatching {
                    apply(updated)
                    InGameOverlay.reloadSettings()
                    InGameOverlay.settingsState.value.toJson().toString() == updated.toJson().toString()
                }.getOrDefault(false)
            }"""
    insertion = GAME_LAB_BLOCK + """        TouchStationExtraCompatibilitySuite(
            settings = s,
            """ + callback + """,
        )
        SettingsDivider()

"""
    source = replace_once(source, GAME_LAB_BLOCK, insertion, "Game Lab placement")
    path.write_text(source, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args()
    app_dir = args.source / "app"
    settings_dir = app_dir / "src/main/java/com/armsx2/ui/settings"
    performance = settings_dir / "PerformanceTab.kt"
    target = settings_dir / "TouchStationExtraCompatibility.kt"
    if not performance.is_file():
        raise SystemExit("PerformanceTab.kt is missing")
    if not (settings_dir / "TouchStationExtraGameLab.kt").is_file():
        raise SystemExit("Run the Game Compatibility Lab patcher first")
    if not TEMPLATE.is_file():
        raise SystemExit("Compatibility Kotlin template is missing: " + str(TEMPLATE))
    if target.exists():
        raise SystemExit("Compatibility module already exists; refusing to overwrite")
    source = TEMPLATE.read_text(encoding="utf-8")
    required = (
        "TouchStationExtraCompatibilitySuite(",
        "BLES00229",
        "extraCompatibilityCandidate",
        "extraCompatibilityReadinessReport",
        "FEATURE_VULKAN_HARDWARE_LEVEL",
        "SettingsScope.Game",
        "full settings read-back verified",
        "Native core/JNI",
        "guest crash callbacks",
    )
    missing = [marker for marker in required if marker not in source]
    if missing:
        raise SystemExit("Compatibility template is missing: " + ", ".join(missing))
    patch_performance_tab(app_dir)
    target.write_text(source, encoding="utf-8")
    print("Installed TouchStation Extra - Compatibility Center.")
    print("Added universal and low-memory profiles, exact BLES00229 profile, local per-game records, Android preflight and report sharing.")
    print("Native PPU/SPU/RSX changes remain explicitly marked as requiring a rebuilt native core.")


if __name__ == "__main__":
    main()
