#!/usr/bin/env python3
"""Prepare a pinned ARMSX3 Android source tree for the TouchStation 4.0.0 build.

This preserves the upstream emulator core and Android application, adds a
small chipset-profile section to its existing Performance settings, and applies
the TouchStation app name and launcher artwork.
"""
from __future__ import annotations

import argparse
import base64
import io
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


DENSITIES = {
    "mipmap-mdpi": 48,
    "mipmap-hdpi": 72,
    "mipmap-xhdpi": 96,
    "mipmap-xxhdpi": 144,
    "mipmap-xxxhdpi": 192,
}

PERFORMANCE_HELPER = r'''
/**
 * 0 = not one of the supported families; 1 = Dimensity; 2 = Snapdragon;
 * 3 = Exynos. Unknown manufacturers retain the emulator's normal settings.
 */
private fun detectTouchStationChipset(): Int {
    val manufacturer = android.os.Build.SOC_MANUFACTURER.orEmpty().lowercase()
    val model = android.os.Build.SOC_MODEL.orEmpty().lowercase()
    val hardware = android.os.Build.HARDWARE.orEmpty().lowercase()
    val board = android.os.Build.BOARD.orEmpty().lowercase()
    val all = "$manufacturer $model $hardware $board"

    return when {
        manufacturer.contains("mediatek") ||
            model.contains("dimensity") ||
            Regex("""(^|[^a-z])mtk?\d{4,}""").containsMatchIn(all) -> 1

        manufacturer.contains("qualcomm") ||
            all.contains("snapdragon") ||
            all.contains("qcom") -> 2

        all.contains("exynos") ||
            Regex("""s5e\d{3,}""").containsMatchIn(all) -> 3

        else -> 0
    }
}
'''

PERFORMANCE_STATE = r'''    val detectedChipset = remember { detectTouchStationChipset() }
    val selectedChipset = remember {
        mutableStateOf(
            MainActivityRuntime.prefs.getInt("ui.touchstationChipsetProfile", 0).coerceIn(0, 3)
        )
    }
    val activeChipset = if (selectedChipset.value == 0) detectedChipset else selectedChipset.value
    val selectedTuning = remember {
        mutableStateOf(
            MainActivityRuntime.prefs.getInt("ui.touchstationTuningMode", 0).coerceIn(0, 2)
        )
    }

    // Auto applies the detected family on first entry; manual profile changes
    // run this same effect. Only supported RPCS3 settings are modified.
    LaunchedEffect(activeChipset, selectedTuning.value) {
        if (activeChipset in 1..3) {
            val current = state.value
            val outputScale = when (selectedTuning.value) {
                1 -> 540
                2 -> 720
                else -> if (activeChipset == 2) 0 else 720
            }
            val preset = current.copy(
                hwScaler = outputScale,
                affinityMode = 0,
                ps3 = current.ps3.copy(
                    ppuDecoder = 1,
                    spuDecoder = if (selectedTuning.value == 2) 2 else 3,
                    spuBlockSize = 0,
                    preferredSpuThreads = 0,
                    llvmThreads = 0,
                    maxSpursThreads = 6,
                    clocksScale = 100,
                    spuLoopDetection = selectedTuning.value == 2,
                    spuCache = true,
                    llvmPrecompile = true,
                    accurateSpuDma = selectedTuning.value == 2,
                ),
            )
            if (preset != current) {
                apply(preset)
                MainActivityRuntime.surface.value?.applyOutputScale()
            }
        }
    }
'''

PERFORMANCE_SECTION = r'''        CollapsibleSection("TouchStation chipset profiles", initiallyExpanded = true) {
            val profileDescription = when (activeChipset) {
                1 -> "Dimensity profile: ARM64 LLVM PPU/SPU, safe SPU block size, automatic thread allocation and a 720p output scaler."
                2 -> "Snapdragon profile: ARM64 LLVM PPU/SPU, safe SPU block size, automatic thread allocation and the device's normal output resolution."
                3 -> "Exynos profile: ARM64 LLVM PPU/SPU, safe SPU block size, automatic thread allocation and a 720p output scaler."
                else -> "No supported chipset family was detected. Choose Dimensity, Snapdragon or Exynos manually, or keep your current settings."
            }
            SegmentedGridRow(
                label = "Processor family",
                options = listOf("Auto detect", "Dimensity", "Snapdragon", "Exynos"),
                selectedIndex = selectedChipset.value,
                columns = 2,
                description = profileDescription,
                onChange = { choice ->
                    selectedChipset.value = choice
                    selectedTuning.value = 0
                    MainActivityRuntime.prefs.edit {
                        putInt("ui.touchstationChipsetProfile", choice)
                        putInt("ui.touchstationTuningMode", 0)
                    }
                },
                notDefault = selectedChipset.value != 0,
            )
            SettingsDivider()
            SegmentedGridRow(
                label = "Optimization target",
                options = listOf("Balanced", "Performance", "Compatibility"),
                selectedIndex = selectedTuning.value,
                columns = 3,
                description = when (selectedTuning.value) {
                    1 -> "Performance: lowers the output surface to 540p and keeps LLVM compilation and SPU caching enabled to reduce GPU load."
                    2 -> "Compatibility: uses the safe SPU block size, conservative 720p output, and accurate SPU DMA/loop handling where supported."
                    else -> "Balanced: uses automatic PPU/SPU thread allocation, safe SPU blocks, and a chipset-aware output scale."
                },
                onChange = { choice ->
                    if (activeChipset in 1..3) {
                        selectedTuning.value = choice
                        MainActivityRuntime.prefs.edit {
                            putInt("ui.touchstationTuningMode", choice)
                        }
                        val current = state.value
                    val scale = when (choice) {
                        1 -> 540
                        2 -> 720
                        else -> if (activeChipset == 2) 0 else 720
                    }
                    val tuned = when (choice) {
                        2 -> current.copy(
                            hwScaler = scale,
                            affinityMode = 0,
                            ps3 = current.ps3.copy(
                                ppuDecoder = 1,
                                spuDecoder = 2,
                                spuBlockSize = 0,
                                preferredSpuThreads = 0,
                                llvmThreads = 0,
                                maxSpursThreads = 6,
                                clocksScale = 100,
                                spuCache = true,
                                llvmPrecompile = true,
                                spuLoopDetection = true,
                                accurateSpuDma = true,
                            ),
                        )
                        else -> current.copy(
                            hwScaler = scale,
                            affinityMode = 0,
                            ps3 = current.ps3.copy(
                                ppuDecoder = 1,
                                spuDecoder = 3,
                                spuBlockSize = 0,
                                preferredSpuThreads = 0,
                                llvmThreads = 0,
                                maxSpursThreads = 6,
                                clocksScale = 100,
                                spuCache = true,
                                llvmPrecompile = true,
                                spuLoopDetection = false,
                                accurateSpuDma = false,
                            ),
                        )
                    }
                        apply(tuned)
                        MainActivityRuntime.surface.value?.applyOutputScale()
                    }
                },
                notDefault = selectedTuning.value != 0,
            )
            HelpText(
                "Profiles only change existing emulator settings. They do not overclock, alter voltage, " +
                    "or force CPU/GPU frequencies. Snapdragon keeps its normal output size in Balanced; " +
                    "Dimensity and Exynos start at 720p. Performance lowers output to 540p. Compatibility " +
                    "uses conservative SPU settings. You can still fine-tune PPU/SPU threads, renderer " +
                    "scale, ADPF, sustained performance and optional Adreno-only GPU Turbo below."
            )
        }
        SettingsDivider()
'''


def replace_once(text: str, old: str, new: str, description: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Expected exactly one {description} marker; found {count}")
    return text.replace(old, new, 1)


def remove_gradle_block(text: str, start: str, closing_indent: str, description: str) -> str:
    pattern = re.compile(
        rf"(?m)^{re.escape(start)}\n.*?^{re.escape(closing_indent)}\}}\n",
        re.DOTALL,
    )
    updated, count = pattern.subn("", text, count=1)
    if count != 1:
        raise SystemExit(f"Could not remove the {description} block from app/build.gradle.kts")
    return updated


def patch_gradle(app_dir: Path) -> None:
    path = app_dir / "build.gradle.kts"
    text = path.read_text(encoding="utf-8")

    text, code_count = re.subn(
        r"(?m)^(\s*)versionCode\s*=\s*\d+\s*$",
        r"\g<1>versionCode = 400",
        text,
        count=1,
    )
    text, name_count = re.subn(
        r'(?m)^(\s*)versionName\s*=\s*"[^"]+"\s*$',
        r'\g<1>versionName = "4.0.0"',
        text,
        count=1,
    )
    if not code_count or not name_count:
        raise SystemExit("Could not set app versionCode/versionName to 400/4.0.0")

    # The public upstream checkout intentionally omits the proprietary Discord
    # Social SDK AAR. Discord sign-in is an optional side feature and its activity
    # uses reflection with a guarded failure path; do not make it a build blocker.
    if not (app_dir / "libs/discord_partner_sdk.aar").is_file():
        text, discord_count = re.subn(
            r'(?m)^[ \t]*implementation\(files\("libs/discord_partner_sdk\.aar"\)\)[ \t]*\r?\n',
            "    // Optional proprietary Discord Social SDK is not included in this public build.\n",
            text,
            count=1,
        )
        if discord_count != 1:
            raise SystemExit(
                f"Expected exactly one optional Discord AAR dependency; found {discord_count}"
            )

    # Use the matching upstream JNI/core binaries from its signed Android
    # release. Do not rebuild or replace the native RPCS3 engine in this job.
    text = remove_gradle_block(
        text,
        "        externalNativeBuild {",
        "        ",
        "defaultConfig externalNativeBuild",
    )
    text = remove_gradle_block(
        text,
        "    externalNativeBuild {",
        "    ",
        "Android externalNativeBuild",
    )
    path.write_text(text, encoding="utf-8")


def patch_performance_tab(app_dir: Path) -> None:
    path = app_dir / "src/main/java/com/armsx2/ui/settings/PerformanceTab.kt"
    text = path.read_text(encoding="utf-8")

    if "detectTouchStationChipset" in text or "TouchStation chipset profiles" in text:
        raise SystemExit("TouchStation chipset profile patch is already present")

    import_marker = "import androidx.compose.runtime.MutableState\n"
    text = replace_once(
        text,
        import_marker,
        import_marker + "import androidx.compose.runtime.LaunchedEffect\n",
        "LaunchedEffect import",
    )

    composable_marker = "@Composable\nfun PerformanceTab(state: MutableState<Settings>) {"
    text = replace_once(
        text,
        composable_marker,
        PERFORMANCE_HELPER.strip() + "\n\n" + composable_marker,
        "PerformanceTab composable",
    )

    apply_marker = "    fun apply(updated: Settings) = InGameOverlay.saveSettings(updated)\n"
    text = replace_once(
        text,
        apply_marker,
        apply_marker + "\n" + PERFORMANCE_STATE,
        "PerformanceTab saveSettings helper",
    )

    section_marker = "        // Prominent latency preset: zero queued GS frames keeps the emulated CPU\n"
    text = replace_once(
        text,
        section_marker,
        PERFORMANCE_SECTION + "\n" + section_marker,
        "PerformanceTab column content",
    )
    path.write_text(text, encoding="utf-8")


def patch_app_name(app_dir: Path) -> None:
    resources = app_dir / "src/main/res"
    found = 0
    for strings in resources.glob("values*/strings.xml"):
        text = strings.read_text(encoding="utf-8")
        updated, count = re.subn(
            r'(<string\s+[^>]*name="app_name"[^>]*>).*?(</string>)',
            r"\1TouchStation\2",
            text,
            count=1,
            flags=re.DOTALL,
        )
        if count:
            strings.write_text(updated, encoding="utf-8")
            found += 1
    if found == 0:
        raise SystemExit("Could not find app_name in Android string resources")



def patch_launcher_manifest(app_dir: Path) -> None:
    path = app_dir / "src/main/AndroidManifest.xml"
    text = path.read_text(encoding="utf-8")

    replacements = (
        (r'android:label="[^"]+"', 'android:label="@string/app_name"', "app label"),
        (r'android:icon="[^"]+"', 'android:icon="@mipmap/ic_launcher"', "launcher icon"),
        (r'android:roundIcon="[^"]+"', 'android:roundIcon="@mipmap/ic_launcher_round"', "round launcher icon"),
    )
    for pattern, replacement, description in replacements:
        text, count = re.subn(pattern, replacement, text, count=1)
        if count != 1:
            raise SystemExit(f"Could not set Android manifest {description}")
    path.write_text(text, encoding="utf-8")


def make_touchstation_logo() -> Image.Image:
    """Create a crisp, monochrome square wordmark without external image files."""
    size = 512
    white = (255, 255, 255)
    image = Image.new("RGB", (size, size), (0, 0, 0))
    draw = ImageDraw.Draw(image)

    font_candidates = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    )

    def load_font(font_size: int):
        for font_path in font_candidates:
            try:
                return ImageFont.truetype(font_path, font_size)
            except OSError:
                continue
        return ImageFont.load_default()

    # Minimal handheld-console outline and controls, all in pure white.
    draw.rounded_rectangle((158, 64, 354, 224), radius=28, outline=white, width=9)
    center_x, center_y = 218, 145
    draw.line((center_x - 24, center_y, center_x + 24, center_y), fill=white, width=9)
    draw.line((center_x, center_y - 24, center_x, center_y + 24), fill=white, width=9)
    draw.ellipse((270, 116, 294, 140), outline=white, width=7)
    draw.ellipse((302, 150, 326, 174), outline=white, width=7)

    def centered_word(text: str, font, y: int) -> None:
        bounds = draw.textbbox((0, 0), text, font=font)
        text_width = bounds[2] - bounds[0]
        draw.text(((size - text_width) / 2, y), text, font=font, fill=white)

    centered_word("TOUCH", load_font(64), 276)
    centered_word("STATION", load_font(48), 366)
    return image


def write_launcher_icons(app_dir: Path, logo_b64: Path | None = None) -> None:
    source = None
    if logo_b64 is not None:
        encoded = "".join(logo_b64.read_text(encoding="ascii").split())
        encoded += "=" * (-len(encoded) % 4)
        try:
            raw = base64.b64decode(encoded, validate=True)
            source = Image.open(io.BytesIO(raw)).convert("RGB")
        except Exception as exc:
            print(f"WARNING: supplied logo could not be decoded ({exc}); using built-in artwork.")

    if source is None:
        source = make_touchstation_logo()

    # Crop the visible wordmark once, then render it larger on a black square.
    # The old blank top/bottom margins made legacy launcher icons look tiny.
    source = ImageOps.fit(source, (512, 512), method=Image.Resampling.LANCZOS)
    gray = ImageOps.grayscale(source)
    ink_mask = gray.point(lambda value: 255 if value > 24 else 0)
    bbox = ink_mask.getbbox()
    if bbox is None:
        raise SystemExit("TouchStation icon contains no visible logo artwork")

    left, top, right, bottom = bbox
    pad_x = max(4, int((right - left) * 0.025))
    pad_y = max(4, int((bottom - top) * 0.06))
    crop = source.crop((
        max(0, left - pad_x),
        max(0, top - pad_y),
        min(source.width, right + pad_x),
        min(source.height, bottom + pad_y),
    )).convert("RGBA")

    legacy = Image.new("RGB", (512, 512), (0, 0, 0))
    legacy_mark = ImageOps.contain(
        crop.convert("RGB"),
        (468, 468),
        method=Image.Resampling.LANCZOS,
    )
    legacy.paste(
        legacy_mark,
        ((512 - legacy_mark.width) // 2, (512 - legacy_mark.height) // 2),
    )

    # Turn the white artwork into an alpha mask so the adaptive foreground
    # stays transparent; Android composites it over the solid black background.
    foreground_art = Image.new("RGBA", crop.size, (255, 255, 255, 0))
    foreground_art.putalpha(ImageOps.grayscale(crop))
    foreground = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    mark = ImageOps.contain(
        foreground_art,
        (336, 336),
        method=Image.Resampling.LANCZOS,
    )
    foreground.alpha_composite(
        mark,
        ((512 - mark.width) // 2, (512 - mark.height) // 2),
    )
    background = Image.new("RGBA", (512, 512), (0, 0, 0, 255))

    res = app_dir / "src/main/res"
    for folder, size in DENSITIES.items():
        target = res / folder
        target.mkdir(parents=True, exist_ok=True)
        legacy.resize((size, size), Image.Resampling.LANCZOS).save(
            target / "ic_launcher.png", format="PNG", optimize=True
        )
        legacy.resize((size, size), Image.Resampling.LANCZOS).save(
            target / "ic_launcher_round.png", format="PNG", optimize=True
        )
        foreground.resize((size, size), Image.Resampling.LANCZOS).save(
            target / "ic_launcher_foreground.png", format="PNG", optimize=True
        )
        background.resize((size, size), Image.Resampling.LANCZOS).save(
            target / "ic_launcher_background.png", format="PNG", optimize=True
        )

    adaptive = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n'
        '    <background android:drawable="@mipmap/ic_launcher_background" />\n'
        '    <foreground android:drawable="@mipmap/ic_launcher_foreground" />\n'
        '</adaptive-icon>\n'
    )
    adaptive_dir = res / "mipmap-anydpi-v26"
    adaptive_dir.mkdir(parents=True, exist_ok=True)
    (adaptive_dir / "ic_launcher.xml").write_text(adaptive, encoding="utf-8")
    (adaptive_dir / "ic_launcher_round.xml").write_text(adaptive, encoding="utf-8")

    # Also update the app's in-app splash mark, without changing its layout.
    splash = res / "drawable/ic_armsx3_mark.png"
    splash.parent.mkdir(parents=True, exist_ok=True)
    legacy.save(splash, format="PNG", optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path, help="android/armsx3-ui source directory")
    parser.add_argument("--logo-b64", type=Path, help="Optional logo image in Base64; built-in monochrome artwork is used by default.")
    args = parser.parse_args()

    app_dir = args.source / "app"
    for required in (
        app_dir / "build.gradle.kts",
        app_dir / "src/main/java/com/armsx2/ui/settings/PerformanceTab.kt",
        app_dir / "src/main/res/values/strings.xml",
    ):
        if not required.is_file():
            raise SystemExit(f"Missing expected upstream source file: {required}")

    patch_gradle(app_dir)
    patch_performance_tab(app_dir)
    patch_app_name(app_dir)
    patch_launcher_manifest(app_dir)
    write_launcher_icons(app_dir, args.logo_b64)

    print("TouchStation source preparation complete.")
    print("App label: TouchStation")
    print("Version: 4.0.0 / versionCode 400")
    print("Chipset profiles: Auto detect, Dimensity, Snapdragon, Exynos")
    print("Auto applies a supported chipset profile when Performance settings are opened.")
    print("Native PPU/SPU/RSX libraries: supplied unchanged from the pinned upstream APK.")




if __name__ == "__main__":
    main()
