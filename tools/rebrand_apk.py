#!/usr/bin/env python3
"""Rebrand the pinned ARMSX3 Android APK as TouchStation PS3.

This script changes presentation metadata only. It does not alter, stub, or
replace the RPCS3-derived native emulator engine.
"""
from __future__ import annotations

import argparse
import base64
import io
import re
from pathlib import Path

from PIL import Image, ImageOps

DENSITIES = {
    "mipmap-mdpi": 48,
    "mipmap-hdpi": 72,
    "mipmap-xhdpi": 96,
    "mipmap-xxhdpi": 144,
    "mipmap-xxxhdpi": 192,
}


def replace_app_strings(decoded: Path) -> None:
    for strings in (decoded / "res").glob("values*/strings.xml"):
        try:
            text = strings.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        text = re.sub(
            r'(<string\s+[^>]*name="app_name"[^>]*>).*?(</string>)',
            r"\1TouchStation PS3\2",
            text,
            flags=re.DOTALL,
        )
        text = text.replace("ARMSX3", "TouchStation PS3")
        text = text.replace("1.6.4", "3.0.0")
        strings.write_text(text, encoding="utf-8")


def patch_manifest(decoded: Path) -> None:
    manifest = decoded / "AndroidManifest.xml"
    if not manifest.exists():
        raise SystemExit("APKTool did not produce AndroidManifest.xml")
    text = manifest.read_text(encoding="utf-8")
    text, code_count = re.subn(
        r'android:versionCode="[^"]+"',
        'android:versionCode="300"',
        text,
        count=1,
    )
    text, name_count = re.subn(
        r'android:versionName="[^"]+"',
        'android:versionName="3.0.0"',
        text,
        count=1,
    )
    text = text.replace("ARMSX3", "TouchStation PS3")
    manifest.write_text(text, encoding="utf-8")

    # APKTool 3 keeps package version information in apktool.yml when the
    # original binary manifest had its version metadata in the APK resources.
    # Patch that metadata too; the rebuilt package manifest is generated from it.
    if not code_count or not name_count:
        metadata = decoded / "apktool.yml"
        if not metadata.exists():
            raise SystemExit("APKTool did not produce apktool.yml version metadata")
        yaml_text = metadata.read_text(encoding="utf-8")
        yaml_text, yaml_code_count = re.subn(
            r"(?m)^(\\s*versionCode:\\s*).+$",
            r"\\g<1>'300'",
            yaml_text,
            count=1,
        )
        yaml_text, yaml_name_count = re.subn(
            r"(?m)^(\\s*versionName:\\s*).+$",
            r"\\g<1>'3.0.0'",
            yaml_text,
            count=1,
        )
        if not yaml_code_count or not yaml_name_count:
            raise SystemExit("Could not find versionInfo versionCode/versionName in apktool.yml")
        metadata.write_text(yaml_text, encoding="utf-8")


def patch_smali(decoded: Path) -> int:
    changed = 0
    for smali_root in decoded.glob("smali*"):
        if not smali_root.is_dir():
            continue
        for file in smali_root.rglob("*.smali"):
            try:
                original = file.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            updated = original.replace("ARMSX3", "TouchStation PS3")
            updated = updated.replace("1.6.4", "3.0.0")
            if updated != original:
                file.write_text(updated, encoding="utf-8")
                changed += 1
    return changed


def write_icon_assets(decoded: Path, logo_b64: Path) -> None:
    encoded = "".join(logo_b64.read_text(encoding="ascii").split())
    try:
        raw = base64.b64decode(encoded, validate=True)
        source = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception as exc:
        raise SystemExit(f"Could not decode TouchStation logo asset: {exc}") from exc

    full_logo = ImageOps.fit(source, (512, 512), method=Image.Resampling.LANCZOS)
    splash = decoded / "res" / "drawable" / "ic_armsx3_mark.png"
    splash.parent.mkdir(parents=True, exist_ok=True)
    full_logo.save(splash, format="PNG", optimize=True)

    foreground = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    mark = ImageOps.contain(
        full_logo.convert("RGBA"),
        (338, 338),
        method=Image.Resampling.LANCZOS,
    )
    foreground.alpha_composite(
        mark,
        ((512 - mark.width) // 2, (512 - mark.height) // 2),
    )
    background = Image.new("RGBA", (512, 512), (0, 0, 0, 255))

    res = decoded / "res"
    for folder, size in DENSITIES.items():
        target = res / folder
        target.mkdir(parents=True, exist_ok=True)

        legacy = full_logo.resize((size, size), Image.Resampling.LANCZOS)
        fg = foreground.resize((size, size), Image.Resampling.LANCZOS)
        bg = background.resize((size, size), Image.Resampling.LANCZOS)

        legacy.save(target / "ic_launcher.png", format="PNG", optimize=True)
        legacy.save(target / "ic_launcher_round.png", format="PNG", optimize=True)
        bg.save(target / "ic_launcher_background.png", format="PNG", optimize=True)
        fg.save(target / "ic_launcher_foreground.png", format="PNG", optimize=True)

    adaptive = '<?xml version="1.0" encoding="utf-8"?>\n' + \
        '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n' + \
        '    <background android:drawable="@mipmap/ic_launcher_background" />\n' + \
        '    <foreground android:drawable="@mipmap/ic_launcher_foreground" />\n' + \
        '</adaptive-icon>\n'
    mipmap_v26 = res / "mipmap-anydpi-v26"
    mipmap_v26.mkdir(parents=True, exist_ok=True)
    (mipmap_v26 / "ic_launcher.xml").write_text(adaptive, encoding="utf-8")
    (mipmap_v26 / "ic_launcher_round.xml").write_text(adaptive, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decoded", required=True, type=Path)
    parser.add_argument("--logo-b64", required=True, type=Path)
    args = parser.parse_args()

    if not args.decoded.is_dir():
        raise SystemExit(f"Decoded APK directory does not exist: {args.decoded}")

    patch_manifest(args.decoded)
    replace_app_strings(args.decoded)
    smali_files = patch_smali(args.decoded)
    write_icon_assets(args.decoded, args.logo_b64)

    print("TouchStation branding applied.")
    print("Application label: TouchStation PS3")
    print("Package version: 3.0.0 (versionCode 300)")
    print("Launcher icon: supplied TouchStation logo")
    print(f"Smali files with visible branding/version updates: {smali_files}")
    print("Native PPU/SPU/RSX engine: preserved unchanged from pinned upstream APK.")


if __name__ == "__main__":
    main()
