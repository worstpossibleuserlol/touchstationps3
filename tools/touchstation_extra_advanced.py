#!/usr/bin/env python3
"""Patch the Extra Android app with advanced diagnostics, profiles and settings history."""
from __future__ import annotations

import argparse
from pathlib import Path

TEMPLATE = Path(__file__).parent / "templates" / "TouchStationExtraAdvancedSuite.kt"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Expected exactly one {label} marker; found {count}")
    return text.replace(old, new, 1)


def patch_performance_tab(app_dir: Path) -> None:
    path = app_dir / "src/main/java/com/armsx2/ui/settings/PerformanceTab.kt"
    text = path.read_text(encoding="utf-8")
    if "TouchStationExtraAdvancedSuite(" in text:
        raise SystemExit("TouchStation Extra advanced suite is already inserted")
    start = text.find("        TouchStationExtraDiagnostics(")
    if start < 0:
        raise SystemExit("TouchStation Extra diagnostics call not found")
    divider = text.find("        SettingsDivider()", start)
    if divider < 0:
        raise SystemExit("TouchStation Extra diagnostics divider not found")
    end = text.find("\n\n", divider)
    if end < 0:
        raise SystemExit("Could not locate end of TouchStation Extra diagnostics section")
    insertion = '''
        TouchStationExtraAdvancedSuite(
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

'''
    text = text[:end + 2] + insertion + text[end + 2:]
    path.write_text(text, encoding="utf-8")


def patch_settings_history(app_dir: Path) -> None:
    path = app_dir / "src/main/java/com/armsx2/ui/InGameOverlay.kt"
    text = path.read_text(encoding="utf-8")
    if "TouchStationExtraSettingsHistory" in text:
        raise SystemExit("TouchStation Extra settings history hook is already installed")
    import_anchor = "import com.armsx2.runtime.MainActivityRuntime\n"
    text = replace_once(
        text,
        import_anchor,
        import_anchor + "import com.armsx2.ui.settings.TouchStationExtraSettingsHistory\n",
        "settings history import",
    )
    save_anchor = "        ConfigStore.save(settingsScope.value, currentSerial.value, updated, previous)"
    history_call = """        TouchStationExtraSettingsHistory.record(
            com.armsx2.Pasx2Application.appContext,
            settingsScope.value,
            currentSerial.value,
            previous,
            updated,
        )
"""
    text = replace_once(text, save_anchor, save_anchor + "\n" + history_call.rstrip("\n"), "settings history record call")
    path.write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args()
    app_dir = args.source / "app"
    settings_dir = app_dir / "src/main/java/com/armsx2/ui/settings"
    advanced = settings_dir / "TouchStationExtraAdvancedSuite.kt"
    performance = settings_dir / "PerformanceTab.kt"
    overlay = app_dir / "src/main/java/com/armsx2/ui/InGameOverlay.kt"
    if not performance.is_file() or not overlay.is_file():
        raise SystemExit("PerformanceTab.kt or InGameOverlay.kt is missing")
    if not (settings_dir / "TouchStationExtraDiagnostics.kt").is_file():
        raise SystemExit("Run the TouchStation Extra base patcher before the advanced patcher")
    if not TEMPLATE.is_file():
        raise SystemExit("Advanced Kotlin source template is missing: " + str(TEMPLATE))
    if advanced.exists():
        raise SystemExit("TouchStation Extra advanced module already exists; refusing to overwrite")
    kotlin = TEMPLATE.read_text(encoding="utf-8")
    if "fun TouchStationExtraAdvancedSuite(" not in kotlin or "TouchStationExtraSettingsHistory" not in kotlin:
        raise SystemExit("Advanced Kotlin source template failed its required marker checks")
    patch_performance_tab(app_dir)
    patch_settings_history(app_dir)
    advanced.write_text(kotlin, encoding="utf-8")
    print("Applied TouchStation Extra advanced compatibility, diagnostics, settings profiles and history.")


if __name__ == "__main__":
    main()
