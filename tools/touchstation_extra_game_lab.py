#!/usr/bin/env python3
"""Integrate the TouchStation Extra per-game compatibility lab."""
from __future__ import annotations

import argparse
from pathlib import Path

TEMPLATE = Path(__file__).parent / "templates" / "TouchStationExtraGameLab.kt"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Expected exactly one {label} marker; found {count}")
    return text.replace(old, new, 1)


def patch_performance_tab(app_dir: Path) -> None:
    path = app_dir / "src/main/java/com/armsx2/ui/settings/PerformanceTab.kt"
    text = path.read_text(encoding="utf-8")
    if "TouchStationExtraGameLabSuite(" in text:
        raise SystemExit("TouchStation Extra Game Compatibility Lab is already inserted")
    anchor = """        TouchStationExtra100Suite(settings = s)
        SettingsDivider()

"""
    insertion = anchor + """        TouchStationExtraGameLabSuite(
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
    text = replace_once(text, anchor, insertion, "Extra 100 / Game Lab placement")
    path.write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args()
    app_dir = args.source / "app"
    settings_dir = app_dir / "src/main/java/com/armsx2/ui/settings"
    performance = settings_dir / "PerformanceTab.kt"
    template_target = settings_dir / "TouchStationExtraGameLab.kt"
    if not performance.is_file():
        raise SystemExit("PerformanceTab.kt is missing")
    if not (settings_dir / "TouchStationExtra100Suite.kt").is_file():
        raise SystemExit("Run the Extra 100 patcher before the Game Lab patcher")
    if not TEMPLATE.is_file():
        raise SystemExit("Game Lab Kotlin template is missing: " + str(TEMPLATE))
    if template_target.exists():
        raise SystemExit("TouchStationExtraGameLab.kt already exists; refusing to overwrite")
    source = TEMPLATE.read_text(encoding="utf-8")
    for marker in (
        "fun TouchStationExtraGameLabSuite(",
        "BLES00229",
        "Apply GTA IV conservative test profile",
        "settingsSha256",
        "Repeatable launch test",
        "Mark interrupted",
        "Possible same-settings regression",
        "guest crash callbacks remain unavailable",
    ):
        if marker not in source:
            raise SystemExit("Game Lab template is missing required marker: " + marker)
    patch_performance_tab(app_dir)
    template_target.write_text(source, encoding="utf-8")
    print("Applied TouchStation Extra Game Compatibility Lab.")
    print("Added BLES00229 profile, device-aware guidance, per-game settings fingerprinting and repeatable observation records.")
    print("Native PPU/SPU/RSX internals remain unavailable unless exported by the pinned engine.")


if __name__ == "__main__":
    main()
