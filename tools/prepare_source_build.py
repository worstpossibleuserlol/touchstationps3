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


ADVANCED_SETTINGS_SECTION = r'''        CollapsibleSection("TouchStation Advanced Settings (26)", initiallyExpanded = false) {
            ToggleRow(
                label = "Multithreaded RSX",
                value = s.ps3.multithreadedRsx,
                description = "Run RSX graphics work across multiple threads. May improve some workloads, but can introduce timing issues in others.",
                onChange = { apply(s.copy(ps3 = s.ps3.copy(multithreadedRsx = it))) },
                notDefault = s.notDefault { it.ps3.multithreadedRsx },
            )
            SettingsDivider()
            ToggleRow(
                label = "Disable ZCULL",
                value = s.ps3.disableZcull,
                description = "Disable the PS3 ZCULL visibility-query path. Use only for titles with a related rendering issue.",
                onChange = { apply(s.copy(ps3 = s.ps3.copy(disableZcull = it))) },
                notDefault = s.notDefault { it.ps3.disableZcull },
            )
            SettingsDivider()
            ToggleRow(
                label = "Relaxed ZCULL synchronization",
                value = s.ps3.relaxedZcull,
                description = "Experimental synchronization behavior. It can cause missing or incorrect graphics in some games.",
                onChange = { apply(s.copy(ps3 = s.ps3.copy(relaxedZcull = it))) },
                notDefault = s.notDefault { it.ps3.relaxedZcull },
            )
            SettingsDivider()
            ToggleRow(
                label = "GPU texture scaling",
                value = s.ps3.gpuTextureScaling,
                description = "Allow the renderer to scale eligible textures on the GPU.",
                onChange = { apply(s.copy(ps3 = s.ps3.copy(gpuTextureScaling = it))) },
                notDefault = s.notDefault { it.ps3.gpuTextureScaling },
            )
            SettingsDivider()
            ToggleRow(
                label = "Force CPU framebuffer blit",
                value = s.ps3.forceCpuBlit,
                description = "Use the CPU path for framebuffer blits. This is a compatibility diagnostic and may be slower.",
                onChange = { apply(s.copy(ps3 = s.ps3.copy(forceCpuBlit = it))) },
                notDefault = s.notDefault { it.ps3.forceCpuBlit },
            )
            SettingsDivider()
            ToggleRow(
                label = "Strict rendering",
                value = s.ps3.strictRendering,
                description = "Use stricter RSX rendering behavior for games that need it; performance may decrease.",
                onChange = { apply(s.copy(ps3 = s.ps3.copy(strictRendering = it))) },
                notDefault = s.notDefault { it.ps3.strictRendering },
            )
            SettingsDivider()
            ToggleRow(
                label = "Write color buffers",
                value = s.ps3.writeColorBuffers,
                description = "Enable color-buffer writeback for effects that depend on it.",
                onChange = { apply(s.copy(ps3 = s.ps3.copy(writeColorBuffers = it))) },
                notDefault = s.notDefault { it.ps3.writeColorBuffers },
            )
            SettingsDivider()
            ToggleRow(
                label = "Write depth buffer",
                value = s.ps3.writeDepthBuffer,
                description = "Enable depth-buffer writeback for titles that require it.",
                onChange = { apply(s.copy(ps3 = s.ps3.copy(writeDepthBuffer = it))) },
                notDefault = s.notDefault { it.ps3.writeDepthBuffer },
            )
            SettingsDivider()
            ToggleRow(
                label = "Read color buffers",
                value = s.ps3.readColorBuffers,
                description = "Allow the renderer to read color buffers back when a game needs that behavior.",
                onChange = { apply(s.copy(ps3 = s.ps3.copy(readColorBuffers = it))) },
                notDefault = s.notDefault { it.ps3.readColorBuffers },
            )
            SettingsDivider()
            ToggleRow(
                label = "Read depth buffer",
                value = s.ps3.readDepthBuffer,
                description = "Allow depth-buffer readback for compatibility with affected titles.",
                onChange = { apply(s.copy(ps3 = s.ps3.copy(readDepthBuffer = it))) },
                notDefault = s.notDefault { it.ps3.readDepthBuffer },
            )
            SettingsDivider()
            ToggleRow(
                label = "Disable swapchain pre-rotation",
                value = s.ps3.disableSwapchainPrerotation,
                description = "Change Android surface rotation handling for devices or games with a rotated image.",
                onChange = { apply(s.copy(ps3 = s.ps3.copy(disableSwapchainPrerotation = it))) },
                notDefault = s.notDefault { it.ps3.disableSwapchainPrerotation },
            )
            SettingsDivider()
            ToggleRow(
                label = "Asynchronous texture streaming",
                value = s.ps3.asyncTexStream,
                description = "Stream eligible textures asynchronously. Results depend on game and storage speed.",
                onChange = { apply(s.copy(ps3 = s.ps3.copy(asyncTexStream = it))) },
                notDefault = s.notDefault { it.ps3.asyncTexStream },
            )
            SettingsDivider()
            IntSliderRow(
                label = "Texture LOD bias",
                value = s.ps3.textureLodBias.coerceIn(-16, 16),
                min = -16,
                max = 16,
                description = "Adjust texture level-of-detail selection. Large changes can make textures blurrier or sharper than intended.",
                valueFormatter = { it.toString() },
                onChange = { apply(s.copy(ps3 = s.ps3.copy(textureLodBias = it))) },
                notDefault = s.notDefault { it.ps3.textureLodBias },
            )
            SettingsDivider()
            IntSliderRow(
                label = "VRAM allocation limit",
                value = (s.ps3.vramLimitMb.coerceIn(256, 8192) / 256),
                min = 1,
                max = 32,
                description = "Hard allocation ceiling for renderer memory, not a target or memory cleaner. Too low can make games fail to allocate resources.",
                valueFormatter = { (it * 256).toString() + " MB" },
                onChange = { apply(s.copy(ps3 = s.ps3.copy(vramLimitMb = it * 256))) },
                notDefault = s.notDefault { it.ps3.vramLimitMb },
            )
            SettingsDivider()
            ToggleRow(
                label = "Accurate SPU reservation",
                value = s.ps3.accurateSpuRsv,
                description = "Use the more accurate SPU reservation path. It can reduce performance.",
                onChange = { apply(s.copy(ps3 = s.ps3.copy(accurateSpuRsv = it))) },
                notDefault = s.notDefault { it.ps3.accurateSpuRsv },
            )
            SettingsDivider()
            ToggleRow(
                label = "Accurate cache-line handling",
                value = s.ps3.accurateCacheLine,
                description = "Use stricter cache-line behavior for compatibility testing.",
                onChange = { apply(s.copy(ps3 = s.ps3.copy(accurateCacheLine = it))) },
                notDefault = s.notDefault { it.ps3.accurateCacheLine },
            )
            SettingsDivider()
            ToggleRow(
                label = "Accurate RSX reservation",
                value = s.ps3.accurateRsxRsv,
                description = "Use the accurate RSX reservation path where a title depends on it.",
                onChange = { apply(s.copy(ps3 = s.ps3.copy(accurateRsxRsv = it))) },
                notDefault = s.notDefault { it.ps3.accurateRsxRsv },
            )
            SettingsDivider()
            ToggleRow(
                label = "Prioritize PPU reservations",
                value = s.ps3.ppuRsvPriority,
                description = "Change reservation scheduling priority for compatibility testing.",
                onChange = { apply(s.copy(ps3 = s.ps3.copy(ppuRsvPriority = it))) },
                notDefault = s.notDefault { it.ps3.ppuRsvPriority },
            )
            SettingsDivider()
            ToggleRow(
                label = "SPU block verification",
                value = s.ps3.spuVerification,
                description = "Verify compiled SPU blocks before use. Keep enabled unless troubleshooting a specific issue.",
                onChange = { apply(s.copy(ps3 = s.ps3.copy(spuVerification = it))) },
                notDefault = s.notDefault { it.ps3.spuVerification },
            )
            SettingsDivider()
            ToggleRow(
                label = "Precise SPU verification",
                value = s.ps3.preciseSpuVerification,
                description = "Use a more thorough SPU cache check. It can add CPU overhead.",
                onChange = { apply(s.copy(ps3 = s.ps3.copy(preciseSpuVerification = it))) },
                notDefault = s.notDefault { it.ps3.preciseSpuVerification },
            )
            SettingsDivider()
            ToggleRow(
                label = "PPU vector NaN handling",
                value = s.ps3.ppuNanHandling,
                description = "Apply the PPU vector NaN compatibility fix used by supported titles.",
                onChange = { apply(s.copy(ps3 = s.ps3.copy(ppuNanHandling = it))) },
                notDefault = s.notDefault { it.ps3.ppuNanHandling },
            )
            SettingsDivider()
            ToggleRow(
                label = "Accurate DFMA",
                value = s.ps3.accurateDfma,
                description = "Use accurate fused multiply-add behavior. This may trade speed for precision.",
                onChange = { apply(s.copy(ps3 = s.ps3.copy(accurateDfma = it))) },
                notDefault = s.notDefault { it.ps3.accurateDfma },
            )
            SettingsDivider()
            ToggleRow(
                label = "DAZ / FTZ floating-point mode",
                value = s.ps3.setDazFtz,
                description = "Control denormals-are-zero and flush-to-zero behavior for compatibility testing.",
                onChange = { apply(s.copy(ps3 = s.ps3.copy(setDazFtz = it))) },
                notDefault = s.notDefault { it.ps3.setDazFtz },
            )
            SettingsDivider()
            ToggleRow(
                label = "HLE lightweight mutex",
                value = s.ps3.hleLwmutex,
                description = "Use the high-level lightweight mutex implementation where supported.",
                onChange = { apply(s.copy(ps3 = s.ps3.copy(hleLwmutex = it))) },
                notDefault = s.notDefault { it.ps3.hleLwmutex },
            )
            SettingsDivider()
            ToggleRow(
                label = "Debug console mode",
                value = s.ps3.debugConsoleMode,
                description = "Enable extra console diagnostics. This may generate additional log output.",
                onChange = { apply(s.copy(ps3 = s.ps3.copy(debugConsoleMode = it))) },
                notDefault = s.notDefault { it.ps3.debugConsoleMode },
            )
            SettingsDivider()
            SegmentedGridRow(
                label = "MSAA mode",
                options = listOf("Off", "Auto"),
                selectedIndex = s.ps3.msaaMode.coerceIn(0, 1),
                columns = 2,
                description = "Use multisample anti-aliasing when the graphics driver supports the required features. Off is safest on mobile.",
                onChange = { apply(s.copy(ps3 = s.ps3.copy(msaaMode = it))) },
                notDefault = s.notDefault { it.ps3.msaaMode },
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
        r"\g<1>versionCode = 502",
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
        PERFORMANCE_SECTION + "\n" + ADVANCED_SETTINGS_SECTION + "\n" + section_marker,
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




def patch_app_wordmark(app_dir: Path) -> None:
    """Replace upstream product-name strings shown in the Android UI."""
    arms = app_dir / "src/main/java/com/armsx2/ui/common/ArmsComponents.kt"
    text = arms.read_text(encoding="utf-8")
    text = replace_once(text, 'contentDescription = "ARMSX3",', 'contentDescription = "TouchStation",', "app mark accessibility name")
    text = replace_once(text, 'text = "ARMSX3",', 'text = "TouchStation",', "app header wordmark")
    arms.write_text(text, encoding="utf-8")

    # The XMB has a literal category title rather than an I18n string, so it
    # needs its own product-name substitution.
    xmb_home = app_dir / "src/main/java/com/armsx2/ui/xmb/XmbHome.kt"
    text = xmb_home.read_text(encoding="utf-8")
    text = replace_once(
        text,
        'title = "ARMSX3",',
        'title = "TouchStation",',
        "XMB TouchStation category title",
    )
    xmb_home.write_text(text, encoding="utf-8")

    screenshots = app_dir / "src/main/java/com/armsx2/Screenshots.kt"
    text = screenshots.read_text(encoding="utf-8")
    text = replace_once(text, 'private const val ALBUM = "ARMSX3"', 'private const val ALBUM = "TouchStation"', "screenshot album name")
    text = replace_once(text, '"ARMSX3_', '"TouchStation_', "screenshot file prefix")
    screenshots.write_text(text, encoding="utf-8")

    backup = app_dir / "src/main/java/com/armsx2/BackupManager.kt"
    text = backup.read_text(encoding="utf-8")
    text = replace_once(text, '"ARMSX2-backup-', '"TouchStation-backup-', "backup filename")
    backup.write_text(text, encoding="utf-8")

    skins = app_dir / "src/main/java/com/armsx2/ControllerSkinStore.kt"
    text = skins.read_text(encoding="utf-8")
    text = replace_once(text, '"ARMSX3 Textured"', '"TouchStation Textured"', "default controller skin display name")
    skins.write_text(text, encoding="utf-8")

    i18n = app_dir / "src/main/java/com/armsx2/i18n/I18n.kt"
    text = i18n.read_text(encoding="utf-8")
    text = replace_once(text, "Your ARMSX3 touch controls", "Your TouchStation touch controls", "remote play touch-controls description")
    i18n.write_text(text, encoding="utf-8")

    # All strings, including translations loaded from JSON, pass through I18n.get().
    old_lookup = '''    fun get(key: String): String {
        if (current != "en") tables[current]?.get(key)?.let { if (it.isNotEmpty()) return it }
        return EN[key] ?: key
    }
'''
    new_lookup = '''    fun get(key: String): String {
        val resolved = if (current != "en") {
            tables[current]?.get(key)?.takeIf { it.isNotEmpty() } ?: (EN[key] ?: key)
        } else {
            EN[key] ?: key
        }
        return resolved.replace("ARMSX3", "TouchStation")
    }
'''
    text = replace_once(text, old_lookup, new_lookup, "global localized TouchStation branding")
    i18n.write_text(text, encoding="utf-8")

    # The XMB boot animation renders its wordmark in Kotlin, rather than using
    # the app label or launcher icon. Replace that renderer's source text too.
    wordmark = app_dir / "src/main/java/com/armsx2/ui/xmb/XmbWordmark.kt"
    text = wordmark.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "import android.graphics.Shader\n",
        "import android.graphics.Shader\nimport android.graphics.Typeface\n",
        "XMB wordmark Typeface import",
    )
    render_pattern = re.compile(
        r"(?ms)^    fun render\(letterPx: Float\): Layers \{.*?^    \}"
    )
    render_body = r'''    fun render(letterPx: Float): Layers {
        val word = "TOUCHSTATION"
        val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            typeface = Typeface.create("sans-serif-black", Typeface.NORMAL)
            textSize = letterPx
            style = Paint.Style.FILL
            shader = LinearGradient(
                0f, 0f, 0f, letterPx,
                android.graphics.Color.WHITE,
                android.graphics.Color.rgb(0xD2, 0xD2, 0xD2),
                Shader.TileMode.CLAMP,
            )
            setShadowLayer(
                letterPx * 0.012f,
                letterPx * 0.045f,
                letterPx * 0.06f,
                android.graphics.Color.argb(0x73, 0, 0, 0),
            )
        }
        val metrics = paint.fontMetrics
        val wordTop = PAD
        val wordWidth = paint.measureText(word) / letterPx
        val wordHeight = (metrics.descent - metrics.ascent) / letterPx
        val unitsWide = PAD + wordWidth + PAD
        val unitsHigh = wordTop + wordHeight + PAD
        val logo = Bitmap.createBitmap(
            kotlin.math.ceil(unitsWide * letterPx).toInt().coerceAtLeast(1),
            kotlin.math.ceil(unitsHigh * letterPx).toInt().coerceAtLeast(1),
            Bitmap.Config.ARGB_8888,
        )
        Canvas(logo).drawText(
            word,
            PAD * letterPx,
            wordTop * letterPx - metrics.ascent,
            paint,
        )
        return Layers(logo, unitsWide, unitsHigh, wordTop, PAD + wordWidth / 2f)
    }'''
    text, count = render_pattern.subn(render_body, text, count=1)
    if count != 1:
        raise SystemExit("Could not patch the XMB boot wordmark to TouchStation")
    wordmark.write_text(text, encoding="utf-8")


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


def write_launcher_icons(app_dir: Path) -> None:
    """Install the supplied square TouchStation artwork at every launcher density."""
    size = 512
    logo_asset = Path(__file__).resolve().parent / "assets" / "touchstation-logo.png.b64"
    if not logo_asset.is_file():
        raise SystemExit(f"Missing TouchStation logo asset: {logo_asset}")

    try:
        encoded_logo = logo_asset.read_text(encoding="ascii").strip()
        logo_bytes = base64.b64decode(encoded_logo, validate=True)
        with Image.open(io.BytesIO(logo_bytes)) as source:
            if source.width != source.height:
                raise SystemExit(
                    f"TouchStation logo must be square; got {source.width}x{source.height}"
                )
            image = ImageOps.fit(
                source.convert("RGB"),
                (size, size),
                method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.5),
            )
    except (OSError, ValueError) as exc:
        raise SystemExit(f"Could not decode the TouchStation logo asset: {exc}") from exc

    res = app_dir / "src/main/res"
    for folder, density_size in DENSITIES.items():
        target = res / folder
        target.mkdir(parents=True, exist_ok=True)
        icon = image.resize((density_size, density_size), Image.Resampling.LANCZOS)
        icon.save(target / "ic_launcher.png", format="PNG", optimize=True)
        icon.save(target / "ic_launcher_round.png", format="PNG", optimize=True)

    # Remove adaptive XML resources so Android cannot select stale artwork.
    adaptive_dir = res / "mipmap-anydpi-v26"
    for name in ("ic_launcher.xml", "ic_launcher_round.xml"):
        adaptive = adaptive_dir / name
        if adaptive.exists():
            adaptive.unlink()

    # Use the exact same artwork for the splash mark.
    splash = res / "drawable/ic_armsx3_mark.png"
    splash.parent.mkdir(parents=True, exist_ok=True)
    image.save(splash, format="PNG", optimize=True)
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
    """Replace the legacy launcher vector with a plain black square."""
    path = app_dir / "src/main/res/drawable/touchstation_icon.xml"
    path.parent.mkdir(parents=True, exist_ok=True)
    vector = """<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="108dp"
    android:height="108dp"
    android:viewportWidth="108"
    android:viewportHeight="108">
    <path android:fillColor="#000000" android:pathData="M0,0h108v108h-108z" />
</vector>
"""
    path.write_text(vector, encoding="utf-8")



def patch_pause_menu_exit(app_dir: Path) -> None:
    """Make the existing pause-menu close action explicitly read Exit Game."""
    menu_path = app_dir / "src/main/java/com/armsx2/ui/emulation/EmulationMenuScreen.kt"
    xmb_path = app_dir / "src/main/java/com/armsx2/ui/xmb/XmbInGame.kt"
    if not menu_path.is_file() or not xmb_path.is_file():
        raise SystemExit("Missing expected in-game pause menu source files")

    menu = menu_path.read_text(encoding="utf-8")
    old = 'add(MenuAction(str("action.close"), MainActivityRuntime.currentGame.value?.title.orEmpty(), "■", Danger) {'
    new = 'add(MenuAction("Exit Game", MainActivityRuntime.currentGame.value?.title.orEmpty(), "■", Danger) {'
    menu = replace_once(menu, old, new, "pause-menu Exit Game action")
    menu_path.write_text(menu, encoding="utf-8")

    xmb = xmb_path.read_text(encoding="utf-8")
    old = 'val quit = fw("impose_plugin", "msg_game_quit2", "xmb.quitGame")'
    new = 'val quit = fw("impose_plugin", "msg_game_quit2", "Exit Game")'
    xmb = replace_once(xmb, old, new, "XMB Exit Game label")
    xmb_path.write_text(xmb, encoding="utf-8")


def patch_boot_splash_branding(app_dir: Path) -> None:
    """Show the TouchStation wordmark on the built-in splash instead of upstream branding."""
    layout = app_dir / "src/main/res/layout/activity_boot_splash.xml"
    layout_text = layout.read_text(encoding="utf-8")
    marker = "</FrameLayout>"
    image = '''    <ImageView
        android:id="@+id/boot_splash_logo"
        android:layout_width="match_parent"
        android:layout_height="match_parent"
        android:layout_gravity="center"
        android:contentDescription="@string/app_name"
        android:padding="48dp"
        android:scaleType="fitCenter"
        android:src="@drawable/ic_armsx3_mark"
        android:visibility="gone" />

'''
    layout_text = replace_once(layout_text, marker, image + marker, "TouchStation splash image")
    layout.write_text(layout_text, encoding="utf-8")

    activity = app_dir / "src/main/java/com/armsx2/BootSplashActivity.kt"
    source = activity.read_text(encoding="utf-8")
    old = '''        setContentView(R.layout.activity_boot_splash)
        rootView = findViewById(R.id.boot_splash_root)
        val textureView = findViewById<TextureView?>(R.id.boot_splash_video)
        rootView?.apply {
            setOnClickListener { leave() }
            postDelayed(timeoutRunnable, HARD_TIMEOUT_MS)
        }
        if (textureView == null) {
            leave()
            return
        }
'''
    new = '''        setContentView(R.layout.activity_boot_splash)
        rootView = findViewById(R.id.boot_splash_root)
        val textureView = findViewById<TextureView?>(R.id.boot_splash_video)
        val splashLogo = findViewById<android.widget.ImageView?>(R.id.boot_splash_logo)
        val customIntro = BootIntro.installed(this)
        if (customIntro == null) {
            textureView?.visibility = View.GONE
            splashLogo?.visibility = View.VISIBLE
            rootView?.apply {
                setOnClickListener { leave() }
                postDelayed(timeoutRunnable, 1800L)
            }
            return
        }
        splashLogo?.visibility = View.GONE
        rootView?.apply {
            setOnClickListener { leave() }
            postDelayed(timeoutRunnable, HARD_TIMEOUT_MS)
        }
        if (textureView == null) {
            leave()
            return
        }
'''
    source = replace_once(source, old, new, "default TouchStation splash behavior")
    activity.write_text(source, encoding="utf-8")



def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path, help="android/armsx3-ui source directory")
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
    patch_app_wordmark(app_dir)
    patch_launcher_manifest(app_dir)
    patch_launcher_vector(app_dir)
    patch_touch_controls(app_dir)
    patch_in_game_settings_button(app_dir)
    patch_pause_menu_exit(app_dir)
    patch_boot_splash_branding(app_dir)
    write_launcher_icons(app_dir)

    print("TouchStation source preparation complete.")
    print("App label and visible wordmarks: TouchStation")
    print("Version: 5.0.0 / versionCode 500")
    print("Virtual gameplay controls: hidden; physical PlayStation/gamepad input remains dedicated to the game.")
    print("In-game settings access: one white, touch-only gear at the top-right; it cannot take controller focus.")
    print("Extra shader controls: compiler threads and shader/SPU compile notifications.")
    print("TouchStation advanced settings: 26 additional live-applied RSX, SPU, VRAM, and compatibility controls.")
    print("Pause menu: explicit Exit Game action in classic and XMB menus.")
    print("Built-in splash: TouchStation wordmark; custom user intro videos remain supported.")
    print("Chipset profiles: Auto detect, Dimensity, Snapdragon, Exynos")
    print("Auto applies a supported chipset profile when Performance settings are opened.")
    print("Native PPU/SPU/RSX libraries: supplied unchanged from the pinned upstream APK.")




if __name__ == "__main__":
    main()
