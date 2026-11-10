#!/usr/bin/env python3
"""Integrate TouchStation Extra's 100-feature app-side companion suite."""
from __future__ import annotations

import argparse
from pathlib import Path

TEMPLATE = Path(__file__).parent / "templates" / "TouchStationExtra100Suite.kt"


def patch_performance_tab(app_dir: Path) -> None:
    path = app_dir / "src/main/java/com/armsx2/ui/settings/PerformanceTab.kt"
    text = path.read_text(encoding="utf-8")
    if "TouchStationExtra100Suite(" in text:
        raise SystemExit("TouchStation Extra 100-feature suite is already inserted")
    advanced = text.find("        TouchStationExtraAdvancedSuite(")
    if advanced < 0:
        raise SystemExit("TouchStation Extra advanced suite call not found")
    divider = text.find("        SettingsDivider()", advanced)
    if divider < 0:
        raise SystemExit("TouchStation Extra advanced suite divider not found")
    end = text.find("\n\n", divider)
    if end < 0:
        raise SystemExit("Could not locate end of advanced suite section")
    insertion = """        TouchStationExtra100Suite(settings = s)
        SettingsDivider()

"""
    text = text[:end + 2] + insertion + text[end + 2:]
    path.write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args()
    app_dir = args.source / "app"
    settings_dir = app_dir / "src/main/java/com/armsx2/ui/settings"
    performance = settings_dir / "PerformanceTab.kt"
    target = settings_dir / "TouchStationExtra100Suite.kt"
    if not performance.is_file():
        raise SystemExit("PerformanceTab.kt is missing")
    if not (settings_dir / "TouchStationExtraAdvancedSuite.kt").is_file():
        raise SystemExit("Run the Extra advanced patcher first")
    if not TEMPLATE.is_file():
        raise SystemExit("Extra 100-feature template is missing: " + str(TEMPLATE))
    if target.exists():
        raise SystemExit("TouchStation Extra 100-feature module already exists; refusing to overwrite")
    source = TEMPLATE.read_text(encoding="utf-8")
    for marker in (
        "fun TouchStationExtra100Suite(",
        "extra100CopyAndVerify",
        "extra100InspectDocument",
        "extra100CaptureMetrics",
        "extra100SelfChecks",
        "SHA-256 verified",
    ):
        if marker not in source:
            raise SystemExit("Extra 100-feature template is missing required marker: " + marker)
    patch_performance_tab(app_dir)
    target.write_text(source, encoding="utf-8")
    print("Applied TouchStation Extra 100-feature app-side companion suite.")


if __name__ == "__main__":
    main()
