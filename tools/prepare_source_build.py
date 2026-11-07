#!/usr/bin/env python3
"""Prepare a pinned ARMSX3 Android source tree for the TouchStation 5.0.0 build.

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
        CollapsibleSection("TouchStation shader controls") {
            IntSliderRow(
                label = "Shader compiler threads",
                value = s.ps3.shaderCompThreads.coerceIn(0, 16),
                min = 0,
                max = 16,
                description = "Number of parallel Vulkan shader compiler workers. Auto lets RPCS3 choose from the device. This setting matters only with asynchronous shader compilation; more workers can use more memory.",
                valueFormatter = { if (it == 0) "Auto" else "$it" },
                onChange = { apply(s.copy(ps3 = s.ps3.copy(shaderCompThreads = it))) },
                notDefault = s.notDefault { it.ps3.shaderCompThreads },
            )
            SettingsDivider()
            ToggleRow(
                label = "Show shader compile notifications",
                value = s.ps3.showShaderCompileHint,
                description = "Show the emulator's on-screen notice while a game shader is compiling.",
                onChange = { apply(s.copy(ps3 = s.ps3.copy(showShaderCompileHint = it))) },
                notDefault = s.notDefault { it.ps3.showShaderCompileHint },
            )
            SettingsDivider()
            ToggleRow(
                label = "Show SPU compile notifications",
                value = s.ps3.showSpuCompileHint,
                description = "Show the emulator's on-screen notice while SPU code is compiling.",
                onChange = { apply(s.copy(ps3 = s.ps3.copy(showSpuCompileHint = it))) },
                notDefault = s.notDefault { it.ps3.showSpuCompileHint },
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
        r"\g<1>versionCode = 500",
        text,
        count=1,
    )
    text, name_count = re.subn(
        r'(?m)^(\s*)versionName\s*=\s*"[^"]+"\s*$',
        r'\g<1>versionName = "5.0.0"',
        text,
        count=1,
    )
    if not code_count or not name_count:
        raise SystemExit("Could not set app versionCode/versionName to 500/5.0.0")

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


def write_launcher_icons(app_dir: Path, logo_b64: Path | None = None) -> None:
    """Create the intentionally plain, solid-black TouchStation launcher icon."""
    # The requested icon is a blank black screen: no wordmark, no symbols,
    # no external image dependency, and no fallback artwork.
    source = Image.new("RGB", (512, 512), (0, 0, 0))
    gray = ImageOps.grayscale(source)
    legacy = Image.merge("RGB", (gray, gray, gray))

    # A fully black foreground/background produces a uniformly black adaptive icon.
    foreground = Image.new("RGBA", (512, 512), (255, 255, 255, 0))
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
        '<?xml version="1.0" encoding="utf-8"?>' + chr(10)
        + '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">' + chr(10)
        + '    <background android:drawable="@mipmap/ic_launcher_background" />' + chr(10)
        + '    <foreground android:drawable="@mipmap/ic_launcher_foreground" />' + chr(10)
        + '</adaptive-icon>' + chr(10)
    )
    adaptive_dir = res / "mipmap-anydpi-v26"
    adaptive_dir.mkdir(parents=True, exist_ok=True)
    (adaptive_dir / "ic_launcher.xml").write_text(adaptive, encoding="utf-8")
    (adaptive_dir / "ic_launcher_round.xml").write_text(adaptive, encoding="utf-8")

    # Use the same plain black image for the in-app splash mark.
    splash = res / "drawable/ic_armsx3_mark.png"
    splash.parent.mkdir(parents=True, exist_ok=True)
    legacy.save(splash, format="PNG", optimize=True)

def patch_touch_controls(app_dir: Path) -> None:
    """Remove virtual touch layers entirely; retain native physical gamepad support."""
    path = app_dir / "src/main/java/com/armsx2/ui/touch/TouchControlsOverlay.kt"
    if not path.is_file():
        raise SystemExit(f"Missing expected touch overlay source: {path}")
    text = path.read_text(encoding="utf-8")

    def matching_brace(source: str, opening: int) -> int:
        depth = 0
        i = opening
        state = "code"
        block_depth = 0
        while i < len(source):
            if state == "code":
                if source.startswith("//", i):
                    state = "line"
                    i += 2
                    continue
                if source.startswith("/*", i):
                    state = "block"
                    block_depth = 1
                    i += 2
                    continue
                if source.startswith('"""', i):
                    state = "triple"
                    i += 3
                    continue
                ch = source[i]
                if ch == '"':
                    state = "string"
                elif ch == "'":
                    state = "char"
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        return i
            elif state == "line":
                if source[i] == chr(10):
                    state = "code"
            elif state == "block":
                if source.startswith("/*", i):
                    block_depth += 1
                    i += 2
                    continue
                if source.startswith("*/", i):
                    block_depth -= 1
                    i += 2
                    if block_depth == 0:
                        state = "code"
                    continue
            elif state == "string":
                if source[i] == chr(92):
                    i += 2
                    continue
                if source[i] == '"':
                    state = "code"
            elif state == "triple":
                if source.startswith('"""', i):
                    state = "code"
                    i += 3
                    continue
            elif state == "char":
                if source[i] == chr(92):
                    i += 2
                    continue
                if source[i] == "'":
                    state = "code"
            i += 1
        raise SystemExit("Could not find the end of a Kotlin composable")

    for function_name in ("TouchControlsOverlay", "RemotePlayTouchControls"):
        marker = f"fun {function_name}() {{"
        start = text.find(marker)
        if start < 0:
            raise SystemExit(f"Could not find expected {function_name} entry point")
        opening = start + len(marker) - 1
        closing = matching_brace(text, opening)
        disabled_body = (
            chr(10)
            + "    // TouchStation 5.0.0: physical controller input only; "
            + "virtual touchscreen and motion overlays are removed."
            + chr(10)
        )
        text = text[: opening + 1] + disabled_body + text[closing:]

    path.write_text(text, encoding="utf-8")




def patch_in_game_settings_button(app_dir: Path) -> None:
    """Add one touch-only Settings shortcut without binding a gamepad control."""
    path = app_dir / "src/main/java/com/armsx2/ui/WindowImpl.kt"
    if not path.is_file():
        raise SystemExit(f"Missing expected in-game window source: {path}")
    text = path.read_text(encoding="utf-8")

    if "TouchStation in-game settings button" in text:
        raise SystemExit("TouchStation in-game settings button patch is already present")

    text = replace_once(
        text,
        "import androidx.compose.ui.draw.clip\n",
        "import androidx.compose.ui.draw.clip\n"
        + "import androidx.compose.ui.focus.focusProperties\n",
        "settings shortcut focus import",
    )

    marker = (
        "                    com.armsx2.ui.touch.TouchControlsOverlay()\n"
        "                }\n\n"
        "                // The keys the IME does not have"
    )
    replacement = (
        "                    com.armsx2.ui.touch.TouchControlsOverlay()\n"
        "                }\n\n"
        "                // TouchStation in-game settings button: touch-only; "
        "the gamepad remains dedicated to gameplay.\n"
        "                if (gameOnScreen && !showLibrary.value && !overlayVisible.value &&\n"
        "                    inGameScreen.value == null\n"
        "                ) {\n"
        "                    Box(\n"
        "                        modifier = Modifier\n"
        "                            .align(Alignment.TopEnd)\n"
        "                            .padding(12.dp)\n"
        "                            .size(48.dp)\n"
        "                            .focusProperties { canFocus = false }\n"
        "                            .clip(CircleShape)\n"
        "                            .background(Color.Black.copy(alpha = 0.58f))\n"
        "                            .clickable(onClickLabel = \"Open settings\") {\n"
        "                                InGameOverlay.open()\n"
        "                                WindowImpl.openInGameScreen(InGameScreen.Settings)\n"
        "                            },\n"
        "                        contentAlignment = Alignment.Center,\n"
        "                    ) {\n"
        "                        Text(\n"
        "                            \"⚙\",\n"
        "                            color = Color.White,\n"
        "                            fontWeight = FontWeight.Bold,\n"
        "                            style = MaterialTheme.typography.titleLarge,\n"
        "                        )\n"
        "                    }\n"
        "                }\n\n"
        "                // The keys the IME does not have"
    )
    text = replace_once(text, marker, replacement, "in-game settings shortcut insertion")
    path.write_text(text, encoding="utf-8")


def patch_launcher_vector(app_dir: Path) -> None:
    """Replace the legacy blue-accent vector with a black-and-white mark."""
    path = app_dir / "src/main/res/drawable/touchstation_icon.xml"
    path.parent.mkdir(parents=True, exist_ok=True)
    vector = """<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="108dp"
    android:height="108dp"
    android:viewportWidth="108"
    android:viewportHeight="108">
    <path android:fillColor="#000000" android:pathData="M0,0h108v108h-108z" />
    <path
        android:strokeColor="#FFFFFF"
        android:strokeWidth="6"
        android:strokeLineCap="round"
        android:strokeLineJoin="round"
        android:fillColor="@android:color/transparent"
        android:pathData="M18,25h23c7,0 9,2 9,8v3c0,6 -2,8 -9,8h-6c-7,0 -9,2 -9,8v8 M58,25h22 M69,25v27c0,6 -3,9 -10,9h-9 M86,25h15 M86,39h13 M86,59h15" />
</vector>
"""
    path.write_text(vector, encoding="utf-8")


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
    patch_launcher_vector(app_dir)
    patch_touch_controls(app_dir)
    patch_in_game_settings_button(app_dir)
    write_launcher_icons(app_dir, args.logo_b64)

    print("TouchStation source preparation complete.")
    print("App label: TouchStation")
    print("Version: 5.0.0 / versionCode 500")
    print("Virtual gameplay controls: hidden; physical PlayStation/gamepad input remains dedicated to the game.")
    print("In-game settings access: one white, touch-only gear at the top-right; it cannot take controller focus.")
    print("Extra shader controls: compiler threads and shader/SPU compile notifications.")
    print("Chipset profiles: Auto detect, Dimensity, Snapdragon, Exynos")
    print("Auto applies a supported chipset profile when Performance settings are opened.")
    print("Native PPU/SPU/RSX libraries: supplied unchanged from the pinned upstream APK.")




if __name__ == "__main__":
    main()
