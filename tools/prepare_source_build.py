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



PERFORMANCE_MONITOR_SOURCE = r'''package com.armsx2.ui.settings

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import java.io.File
import java.util.Locale

private data class TouchStationMetricSample(
    val cpu: Float?,
    val gpu: Float?,
    val fps: Float?,
)

private object TouchStationMetricReader {
    private var previousCpu: Pair<Long, Long>? = null
    private var previousGpu: Pair<Long, Long>? = null

    @Synchronized
    fun reset() {
        previousCpu = null
        previousGpu = null
    }

    /** Device-wide CPU load, sampled from Linux procfs rather than guessed from clock speed. */
    @Synchronized
    fun cpuPercent(): Float? = runCatching {
        val fields = File("/proc/stat").useLines { lines ->
            lines.firstOrNull()?.trim()?.split(Regex("\\s+"))?.drop(1)
                ?.mapNotNull { it.toLongOrNull() }
        } ?: return null
        if (fields.size < 4) return null
        val values = fields.take(8)
        val total = values.sum()
        val idle = values[3] + (values.getOrNull(4) ?: 0L)
        val old = previousCpu
        previousCpu = total to idle
        if (old == null) return null
        val totalDelta = total - old.first
        val idleDelta = idle - old.second
        if (totalDelta <= 0L) return null
        ((totalDelta - idleDelta).toFloat() * 100f / totalDelta.toFloat()).coerceIn(0f, 100f)
    }.getOrNull()

    /** Reads real driver counters where the Android kernel exposes them to an app process. */
    @Synchronized
    fun gpuPercent(): Float? {
        val kgsl = runCatching {
            File("/sys/class/kgsl/kgsl-3d0/gpubusy").readText().trim()
                .split(Regex("\\s+")).mapNotNull { it.toLongOrNull() }
        }.getOrNull()

        if (kgsl != null && kgsl.size >= 2) {
            val busy = kgsl[0]
            val total = kgsl[1]
            val old = previousGpu
            previousGpu = busy to total
            if (old != null) {
                val busyDelta = busy - old.first
                val totalDelta = total - old.second
                if (busyDelta >= 0L && totalDelta > 0L) {
                    return (busyDelta.toFloat() * 100f / totalDelta.toFloat()).coerceIn(0f, 100f)
                }
            }
        }

        val fixedCandidates = listOf(
            File("/sys/class/kgsl/kgsl-3d0/gpu_busy_percentage"),
            File("/sys/class/misc/mali0/device/utilization"),
            File("/sys/class/misc/mali0/device/gpu_busy"),
        )
        for (candidate in fixedCandidates) {
            readPercent(candidate)?.let { return it }
        }

        val devfreq = File("/sys/class/devfreq")
        for (device in devfreq.listFiles().orEmpty()) {
            val identity = device.name.lowercase() + " " +
                runCatching { File(device, "name").readText().lowercase() }.getOrDefault("")
            if (!identity.contains("gpu") && !identity.contains("mali") &&
                !identity.contains("kgsl") && !identity.contains("adreno")
            ) continue
            for (name in listOf("load", "utilization", "gpu_busy_percentage")) {
                readPercent(File(device, name))?.let { return it }
            }
        }
        return null
    }

    private fun readPercent(file: File): Float? = runCatching {
        val raw = file.readText().trim()
        val number = Regex("""\d+(?:\.\d+)?""").find(raw)?.value?.toFloatOrNull()
        number?.takeIf { it in 0f..100f }
    }.getOrNull()

    /** This is a real core value when implemented; the current pinned bridge returns no sample. */
    fun fps(): Float? = runCatching {
        com.armsx3.NativeApp.getFPS().takeIf { it.isFinite() && it > 0f }
    }.getOrNull()

    fun appRamMb(): Int? = runCatching {
        val info = android.os.Debug.MemoryInfo()
        android.os.Debug.getMemoryInfo(info)
        (info.totalPss / 1024).takeIf { it > 0 }
    }.getOrNull()
}

@Composable
fun TouchStationPerformanceMonitor() {
    val history = remember { mutableStateListOf<TouchStationMetricSample>() }
    var appRamMb by remember { mutableStateOf<Int?>(null) }

    LaunchedEffect(Unit) {
        TouchStationMetricReader.reset()
        while (true) {
            history.add(
                TouchStationMetricSample(
                    cpu = TouchStationMetricReader.cpuPercent(),
                    gpu = TouchStationMetricReader.gpuPercent(),
                    fps = TouchStationMetricReader.fps(),
                ),
            )
            if (history.size > 60) history.removeAt(0)
            appRamMb = TouchStationMetricReader.appRamMb()
            delay(1_000)
        }
    }

    val latest = history.lastOrNull()
    val cpuColor = MaterialTheme.colorScheme.primary
    val gpuColor = MaterialTheme.colorScheme.tertiary
    val fpsColor = MaterialTheme.colorScheme.secondary

    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Text("TouchStation Performance Monitor", style = MaterialTheme.typography.titleLarge)
        Text(
            "Live readings · 1-second interval · rolling 60-second graphs",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            MetricTile(
                Modifier.weight(1f),
                "CPU",
                latest?.cpu?.let { String.format(Locale.US, "%.0f%%", it) } ?: "N/A",
                "device load",
            )
            MetricTile(
                Modifier.weight(1f),
                "GPU",
                latest?.gpu?.let { String.format(Locale.US, "%.0f%%", it) } ?: "N/A",
                "driver reading",
            )
            MetricTile(
                Modifier.weight(1f),
                "FPS",
                latest?.fps?.let { String.format(Locale.US, "%.1f", it) } ?: "N/A",
                "game frames",
            )
        }
        MetricTile(
            Modifier.fillMaxWidth(),
            "App RAM",
            appRamMb?.let { it.toString() + " MB" } ?: "N/A",
            "TouchStation process memory",
        )

        MetricGraph(
            title = "CPU usage",
            values = history.map { it.cpu },
            maximum = 100f,
            lineColor = cpuColor,
            unavailable = "CPU readings are not currently available from /proc/stat.",
        )
        MetricGraph(
            title = "GPU usage",
            values = history.map { it.gpu },
            maximum = 100f,
            lineColor = gpuColor,
            unavailable = "This device driver does not expose a readable GPU utilization counter.",
        )
        MetricGraph(
            title = "Game FPS",
            values = history.map { it.fps },
            maximum = 120f,
            lineColor = fpsColor,
            unavailable = "Game FPS is unavailable because the pinned RPCS3 bridge currently returns no FPS reading.",
        )
        Text(
            "CPU is device-wide load. GPU usage is read from supported kernel-driver counters when accessible. " +
                "FPS is only shown when the emulation core supplies a real value; unavailable metrics are not estimated.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun MetricTile(
    modifier: Modifier,
    label: String,
    value: String,
    detail: String,
) {
    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(14.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
    ) {
        Column(Modifier.padding(10.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(label, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text(value, style = MaterialTheme.typography.titleLarge)
            Text(detail, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun MetricGraph(
    title: String,
    values: List<Float?>,
    maximum: Float,
    lineColor: Color,
    unavailable: String,
) {
    val gridColor = MaterialTheme.colorScheme.outline.copy(alpha = 0.35f)
    Column(Modifier.fillMaxWidth()) {
        Text(title, style = MaterialTheme.typography.titleSmall)
        Canvas(Modifier.fillMaxWidth().height(76.dp)) {
            val left = 3.dp.toPx()
            val right = size.width - 3.dp.toPx()
            val top = 5.dp.toPx()
            val bottom = size.height - 5.dp.toPx()
            for (step in 0..4) {
                val y = top + (bottom - top) * step / 4f
                drawLine(
                    color = gridColor,
                    start = Offset(left, y),
                    end = Offset(right, y),
                    strokeWidth = 1.dp.toPx(),
                )
            }
            val scale = maxOf(maximum, values.filterNotNull().maxOrNull() ?: maximum)
            val path = Path()
            var segmentOpen = false
            values.forEachIndexed { index, value ->
                if (value == null) {
                    segmentOpen = false
                } else {
                    val x = if (values.size <= 1) right else {
                        left + (right - left) * index / (values.size - 1).toFloat()
                    }
                    val y = bottom - (value.coerceIn(0f, scale) / scale) * (bottom - top)
                    if (segmentOpen) path.lineTo(x, y) else {
                        path.moveTo(x, y)
                        segmentOpen = true
                    }
                }
            }
            drawPath(path, color = lineColor, style = Stroke(width = 2.dp.toPx()))
        }
        if (values.none { it != null }) {
            Text(
                unavailable,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}
'''

CONTROLLER_MONITOR_SOURCE = r'''package com.armsx2.ui.controls

import android.content.Context
import android.hardware.input.InputManager
import android.os.Handler
import android.os.Looper
import android.view.InputDevice
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp

data class TouchStationControllerDevice(
    val id: Int,
    val name: String,
)

data class TouchStationControllerSnapshot(
    val devices: List<TouchStationControllerDevice> = emptyList(),
)

object TouchStationControllerMonitor {
    val state = mutableStateOf(TouchStationControllerSnapshot())
    private var inputManager: InputManager? = null

    private val listener = object : InputManager.InputDeviceListener {
        override fun onInputDeviceAdded(deviceId: Int) = refresh()
        override fun onInputDeviceRemoved(deviceId: Int) = refresh()
        override fun onInputDeviceChanged(deviceId: Int) = refresh()
    }

    @Synchronized
    fun start(context: Context) {
        val next = context.applicationContext.getSystemService(Context.INPUT_SERVICE) as? InputManager
            ?: return
        if (inputManager !== next) {
            runCatching { inputManager?.unregisterInputDeviceListener(listener) }
            inputManager = next
            next.registerInputDeviceListener(listener, Handler(Looper.getMainLooper()))
        }
        refresh()
    }

    @Synchronized
    fun refresh() {
        val devices = InputDevice.getDeviceIds().mapNotNull { id ->
            val device = InputDevice.getDevice(id) ?: return@mapNotNull null
            val hasGamepadSource = (device.sources and InputDevice.SOURCE_GAMEPAD) == InputDevice.SOURCE_GAMEPAD
            val hasJoystickSource = (device.sources and InputDevice.SOURCE_JOYSTICK) == InputDevice.SOURCE_JOYSTICK
            if (device.isVirtual || (!hasGamepadSource && !hasJoystickSource)) {
                null
            } else {
                TouchStationControllerDevice(device.id, device.name)
            }
        }.sortedBy { it.name.lowercase() }
        state.value = TouchStationControllerSnapshot(devices)
    }
}

@Composable
fun TouchStationControllerConnectionPanel() {
    val context = LocalContext.current
    LaunchedEffect(context) { TouchStationControllerMonitor.start(context) }
    val devices by TouchStationControllerMonitor.state

    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(18.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
    ) {
        Column(
            Modifier.padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(7.dp),
        ) {
            Text("Controller connection", style = MaterialTheme.typography.titleMedium)
            if (devices.devices.isEmpty()) {
                Text(
                    "No physical game controller detected.",
                    color = MaterialTheme.colorScheme.error,
                )
            } else {
                devices.devices.forEach { device ->
                    Text("Connected: " + device.name, style = MaterialTheme.typography.bodyMedium)
                }
            }
            Text(
                "Bluetooth pairing and USB reconnection are managed by Android. Reconnect the controller, " +
                    "return here, then refresh detection.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            OutlinedButton(onClick = TouchStationControllerMonitor::refresh) {
                Text("Refresh controllers")
            }
        }
    }
}

@Composable
fun TouchStationControllerWarning(modifier: Modifier = Modifier) {
    val context = LocalContext.current
    LaunchedEffect(context) { TouchStationControllerMonitor.start(context) }
    val devices by TouchStationControllerMonitor.state
    if (devices.devices.isEmpty()) {
        Surface(
            modifier = modifier,
            shape = RoundedCornerShape(16.dp),
            color = MaterialTheme.colorScheme.errorContainer,
            contentColor = MaterialTheme.colorScheme.onErrorContainer,
        ) {
            Text(
                "Controller disconnected — reconnect your controller to continue gameplay.",
                modifier = Modifier.padding(horizontal = 14.dp, vertical = 9.dp),
                style = MaterialTheme.typography.bodyMedium,
            )
        }
    }
}
'''


def patch_performance_tab(app_dir: Path) -> None:
    path = app_dir / "src/main/java/com/armsx2/ui/settings/PerformanceTab.kt"
    text = path.read_text(encoding="utf-8")

    advanced_labels = [
        line.strip()[9:-2]
        for line in ADVANCED_SETTINGS_SECTION.splitlines()
        if line.strip().startswith('label = "')
    ]
    if len(advanced_labels) != 26 or len(set(advanced_labels)) != 26:
        raise SystemExit(
            f"Expected 26 uniquely named TouchStation advanced controls; found {len(advanced_labels)}"
        )

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



def patch_touchstation_drawer(app_dir: Path) -> None:
    """Replace upstream community links with TouchStation project actions."""
    path = app_dir / "src/main/java/com/armsx2/navigation/NavigationDrawer.kt"
    text = path.read_text(encoding="utf-8")

    if "TouchStation report bug drawer entry" in text:
        raise SystemExit("TouchStation drawer branding patch is already present")

    old_urls = """internal const val DiscordUrl = "https://discord.gg/2Tynvwhc4A"
internal const val GithubUrl = "https://github.com/ARMSX2/ARMSX3"
internal const val WebsiteUrl = "https://armsx2.net/armsx3"""
    new_urls = """internal const val GithubUrl = "https://github.com/worstpossibleuserlol/touchstationps3"
internal const val ReportBugUrl = "https://github.com/worstpossibleuserlol/touchstationps3/issues/new?template=bug_report.yml"""
    text = replace_once(text, old_urls, new_urls, "upstream drawer links")

    old_item_end = """    val xmbWave: Boolean = false,
)"""
    new_item_end = """    val xmbWave: Boolean = false,
    // Explicit TouchStation labels bypass upstream translations but keep unique controller IDs.
    val displayTitle: String? = null,
)"""
    text = replace_once(text, old_item_end, new_item_end, "drawer display title field")

    old_about = """    val about = listOf(
        DrawerItem("about.discord", "💬", iconRes = com.armsx2.R.drawable.ic_discord,
            onAction = { openExternalUrl(context, DiscordUrl); onDismiss() }),
        DrawerItem("about.github", "🐙", iconRes = com.armsx2.R.drawable.ic_github,
            onAction = { openExternalUrl(context, GithubUrl); onDismiss() }),
        DrawerItem("about.website", "🌐", onAction = { openExternalUrl(context, WebsiteUrl); onDismiss() }),
        // In-app release notes. A destination rather than a link-out because the point is to read
        // what changed without leaving for a browser — the GitHub row above is still there for
        // anyone who wants the repo itself.
        DrawerItem("news.title", "📰", AppRoute.News),
        DrawerItem("friends.title", "👥", AppRoute.Friends, friendsBadge = true),
        DrawerItem("remoteplay.title", "📡", AppRoute.RemotePlay),
        // About left the settings tab strip: it is a read-only page, not a setting, and it sat in
        // the tab row costing a slot on every settings visit.
        DrawerItem("about.title", "ℹ️", AppRoute.About),
    )"""
    new_about = """    val about = listOf(
        DrawerItem(
            "touchstation.github",
            "🐙",
            iconRes = com.armsx2.R.drawable.ic_github,
            onAction = { openExternalUrl(context, GithubUrl); onDismiss() },
            displayTitle = "GitHub",
        ),
        // TouchStation report bug drawer entry: this opens the working structured GitHub issue form.
        DrawerItem(
            "touchstation.reportBug",
            "🐛",
            onAction = { openExternalUrl(context, ReportBugUrl); onDismiss() },
            displayTitle = "Report a Bug",
        ),
        DrawerItem("news.title", "📰", AppRoute.News),
        DrawerItem("friends.title", "👥", AppRoute.Friends, friendsBadge = true),
        DrawerItem("remoteplay.title", "📡", AppRoute.RemotePlay),
        DrawerItem(
            "touchstation.about",
            "ℹ️",
            AppRoute.About,
            displayTitle = "About TouchStation",
        ),
    )"""
    text = replace_once(text, old_about, new_about, "drawer About section")
    text = replace_once(
        text,
        'title = str(item.titleKey),',
        'title = item.displayTitle ?: str(item.titleKey),',
        "drawer row title binding",
    )
    path.write_text(text, encoding="utf-8")


def patch_touchstation_about(app_dir: Path) -> None:
    """Brand About with TouchStation details and correctly attribute the upstream engine."""
    path = app_dir / "src/main/java/com/armsx2/ui/about/AboutScreen.kt"
    text = path.read_text(encoding="utf-8")

    if "TouchStationRepositoryUrl" in text or 'title = "About TouchStation"' in text:
        raise SystemExit("TouchStation About screen patch is already present")

    old_urls = """private const val RepositoryUrl = "https://github.com/ARMSX2/ARMSX3"
private const val Rpcs3RepositoryUrl = "https://github.com/RPCS3/rpcs3"""
    new_urls = """private const val TouchStationRepositoryUrl = "https://github.com/worstpossibleuserlol/touchstationps3"
private const val UpstreamRepositoryUrl = "https://github.com/ARMSX2/ARMSX3"""
    text = replace_once(text, old_urls, new_urls, "About repository links")
    text = replace_once(
        text,
        'title = str("about.title"),',
        'title = "About TouchStation",',
        "About screen title",
    )
    text = replace_once(
        text,
        "ArmsLogo(showWordmark = true)",
        'Text("TouchStation", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)',
        "About TouchStation wordmark",
    )
    text = replace_once(
        text,
        'str("about.tagline"),',
        '"A downstream Android ARM64 distribution of ARMSX3, using its RPCS3-derived PS3 emulation engine.",',
        "About TouchStation description",
    )

    text = replace_once(
        text,
        'import com.armsx2.ui.common.RoundAction\n',
        'import com.armsx2.ui.common.RoundAction\nimport com.armsx2.ui.settings.controllerFocusable\n',
        "About controller-focus import",
    )
    text = replace_once(
        text,
        'leading = { RoundAction("←", str("action.back"), onBack) },',
        'leading = { RoundAction("←", str("action.back"), onBack, controllerId = "about.back") },',
        "About back-button controller focus",
    )
    text = replace_once(
        text,
        '        modifier = modifier.fillMaxWidth(),\n        shape = RoundedCornerShape(20.dp),',
        '        modifier = modifier.fillMaxWidth().controllerFocusable(\n'
        '            "about.project.$repository",\n'
        '            RoundedCornerShape(20.dp),\n'
        '            onConfirm = onOpen,\n'
        '        ),\n'
        '        shape = RoundedCornerShape(20.dp),',
        "About project-card controller focus",
    )

    station_pattern = re.compile(
        r'(?m)^([ \t]*)title = str\("about.repository.title"\),\n'
        r'[ \t]*repository = "ARMSX2/ARMSX3",\n'
        r'[ \t]*description = str\("about.repository.description"\),\n'
        r'[ \t]*glyph = "⌘",'
    )

    def station_card(match: re.Match[str]) -> str:
        indent = match.group(1)
        return "\n".join((
            indent + 'title = "TouchStation project",',
            indent + 'repository = "worstpossibleuserlol/touchstationps3",',
            indent + 'description = "Source code, releases, build workflows and bug reports.",',
            indent + 'glyph = "TS",',
        ))

    text, station_count = station_pattern.subn(station_card, text)
    if station_count != 2:
        raise SystemExit(
            f"Expected two TouchStation repository cards in About screen; found {station_count}"
        )
    if text.count("uriHandler.openUri(RepositoryUrl)") != 2:
        raise SystemExit("Expected two original About repository card actions")
    text = text.replace(
        "uriHandler.openUri(RepositoryUrl)",
        "uriHandler.openUri(TouchStationRepositoryUrl)",
    )

    upstream_pattern = re.compile(
        r'(?m)^([ \t]*)title = str\("about.rpcs3.title"\),\n'
        r'[ \t]*repository = "RPCS3/rpcs3",\n'
        r'[ \t]*description = str\("about.rpcs3.description"\),\n'
        r'[ \t]*glyph = "PS3",'
    )

    def upstream_card(match: re.Match[str]) -> str:
        indent = match.group(1)
        return "\n".join((
            indent + 'title = "Upstream emulator base",',
            indent + 'repository = "ARMSX2/ARMSX3",',
            indent + 'description = "Android frontend and ARM64 engine distribution used by TouchStation.",',
            indent + 'glyph = "PS3",',
        ))

    text, upstream_count = upstream_pattern.subn(upstream_card, text)
    if upstream_count != 2:
        raise SystemExit(
            f"Expected two upstream About cards; found {upstream_count}"
        )
    if text.count("uriHandler.openUri(Rpcs3RepositoryUrl)") != 2:
        raise SystemExit("Expected two original upstream card actions")
    text = text.replace(
        "uriHandler.openUri(Rpcs3RepositoryUrl)",
        "uriHandler.openUri(UpstreamRepositoryUrl)",
    )

    attribution_marker = "                    // Every third-party component in the APK and its license: BSD, MIT, Apache-2.0"
    attribution = """                    Text(
                        "TouchStation is an independent downstream project. Its PS3 emulation engine is provided through ARMSX3 and derives from RPCS3. TouchStation is not affiliated with Sony or the upstream projects.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.fillMaxWidth().padding(top = 4.dp),
                    )
                    // Every third-party component in the APK and its license: BSD, MIT, Apache-2.0"""
    text = replace_once(text, attribution_marker, attribution, "About upstream attribution")
    path.write_text(text, encoding="utf-8")



def patch_touchstation_xmb(app_dir: Path) -> None:
    """Replace upstream Website/Discord entries in the XMB with TouchStation destinations."""
    path = app_dir / "src/main/java/com/armsx2/ui/xmb/XmbHome.kt"
    text = path.read_text(encoding="utf-8")

    if "ReportBugUrl" in text:
        raise SystemExit("TouchStation XMB branding patch is already present")

    old_imports = """import com.armsx2.navigation.AppRoute
import com.armsx2.navigation.DiscordUrl
import com.armsx2.navigation.GithubUrl
import com.armsx2.navigation.UiNavigator
import com.armsx2.navigation.WebsiteUrl
import com.armsx2.navigation.openExternalUrl"""
    new_imports = """import com.armsx2.navigation.AppRoute
import com.armsx2.navigation.GithubUrl
import com.armsx2.navigation.ReportBugUrl
import com.armsx2.navigation.UiNavigator
import com.armsx2.navigation.openExternalUrl"""
    text = replace_once(text, old_imports, new_imports, "XMB community-link imports")

    old_website = """            XmbNode.Action("net.browser", fw(full, "msg_browser", "xmb.browser"), XmbIcon("explore_category_network", "tex_browser", "🌐"), WebsiteUrl.removePrefix("https://").trimEnd('/')) {
                openExternalUrl(context, WebsiteUrl)
            },"""
    new_bug_link = """            XmbNode.Action("net.reportBug", "Report a Bug", XmbIcon("explore_category_network", "tex_browser", "🐛"), ReportBugUrl.removePrefix("https://").trimEnd('/')) {
                openExternalUrl(context, ReportBugUrl)
            },"""
    text = replace_once(text, old_website, new_bug_link, "XMB Website destination")

    text = replace_once(
        text,
        "// Where PlayStation Network was: ARMSX3's own news and links, under ARMSX3's mark.",
        "// TouchStation project links and the in-app About page live in this column.",
        "XMB project column comment",
    )
    old_discord = """            XmbNode.Action("armsx3.discord", str("about.discord"), XmbIcon(model = R.drawable.ic_discord, glyph = "💬")) {
                openExternalUrl(context, DiscordUrl)
            },
"""
    text = replace_once(text, old_discord, "", "XMB Discord action")
    text = replace_once(
        text,
        'XmbNode.Action("armsx3.github", str("about.github"), XmbIcon(model = R.drawable.ic_github, glyph = "🐙")) {',
        'XmbNode.Action("touchstation.github", "GitHub", XmbIcon(model = R.drawable.ic_github, glyph = "🐙")) {',
        "XMB GitHub action title",
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



def patch_touchstation_runtime_features(app_dir: Path) -> None:
    """Add honest live metrics, physical-controller hotplug status and About guidance."""
    monitor_path = app_dir / "src/main/java/com/armsx2/ui/settings/TouchStationPerformanceMonitor.kt"
    monitor_path.write_text(PERFORMANCE_MONITOR_SOURCE, encoding="utf-8")

    controller_path = app_dir / "src/main/java/com/armsx2/ui/controls/TouchStationControllerMonitor.kt"
    controller_path.write_text(CONTROLLER_MONITOR_SOURCE, encoding="utf-8")

    performance = app_dir / "src/main/java/com/armsx2/ui/settings/PerformanceTab.kt"
    text = performance.read_text(encoding="utf-8")
    if "TouchStationPerformanceMonitor()" in text:
        raise SystemExit("TouchStation performance monitor insertion is already present")
    marker = '        CollapsibleSection("TouchStation chipset profiles", initiallyExpanded = true) {'
    text = replace_once(
        text,
        marker,
        "        TouchStationPerformanceMonitor()\n        SettingsDivider()\n\n" + marker,
        "PerformanceTab live monitor panel",
    )
    performance.write_text(text, encoding="utf-8")

    about = app_dir / "src/main/java/com/armsx2/ui/about/AboutScreen.kt"
    text = about.read_text(encoding="utf-8")
    controls_marker = "                    // Every third-party component in the APK and its license: BSD, MIT, Apache-2.0"
    controls_note = """                    Text(
                        "Gameplay requires a physical controller. On-screen gameplay controls are disabled; touchscreen input is only for menus and settings.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.fillMaxWidth().padding(top = 4.dp),
                    )
                    // Every third-party component in the APK and its license: BSD, MIT, Apache-2.0"""
    text = replace_once(text, controls_marker, controls_note, "About physical-controller notice")
    about.write_text(text, encoding="utf-8")

    controller_screen = app_dir / "src/main/java/com/armsx2/ui/controls/ControllerManagerScreen.kt"
    text = controller_screen.read_text(encoding="utf-8")
    panel_marker = "            BoxWithConstraints(Modifier.fillMaxWidth()) {"
    text = replace_once(
        text,
        panel_marker,
        "            TouchStationControllerConnectionPanel()\n"
        "            Spacer(Modifier.height(10.dp))\n"
        + panel_marker,
        "controller connection status panel",
    )
    controller_screen.write_text(text, encoding="utf-8")

    window = app_dir / "src/main/java/com/armsx2/ui/WindowImpl.kt"
    text = window.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "import com.armsx2.runtime.MainActivityRuntime\n",
        "import com.armsx2.runtime.MainActivityRuntime\n"
        "import com.armsx2.ui.controls.TouchStationControllerWarning\n",
        "controller warning import",
    )
    window_marker = (
        "                val gameOnScreen = MainActivityRuntime.eState.value == EmuState.RUNNING ||\n"
        "                    MainActivityRuntime.eState.value == EmuState.PAUSED\n"
        "                if (gameOnScreen && !showLibrary.value) {"
    )
    text = replace_once(
        text,
        window_marker,
        window_marker,
        "window game-state anchor",
    )
    warning_marker = (
        "                KeyboardExtraKeys()\n\n"
        "            if (showLibrary.value && MainActivityRuntime.eState.value == EmuState.RUNNING && !overlayVisible.value) {"
    )
    warning_replacement = (
        "                KeyboardExtraKeys()\n\n"
        "            // Draw above the game surface and artwork so the disconnect warning stays visible.\n"
        "            if (gameOnScreen && !showLibrary.value && !overlayVisible.value && inGameScreen.value == null) {\n"
        "                TouchStationControllerWarning(\n"
        "                    Modifier.align(Alignment.TopCenter).padding(top = 12.dp),\n"
        "                )\n"
        "            }\n\n"
        "            if (showLibrary.value && MainActivityRuntime.eState.value == EmuState.RUNNING && !overlayVisible.value) {"
    )
    text = replace_once(text, warning_marker, warning_replacement, "top-layer controller disconnect warning")
    window.write_text(text, encoding="utf-8")


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


def patch_in_game_settings_exit(app_dir: Path) -> None:
    """Add safe, controller-focusable session controls to the in-game gear Settings page."""
    path = app_dir / "src/main/java/com/armsx2/ui/settingshub/SettingsScreen.kt"
    if not path.is_file():
        raise SystemExit(f"Missing expected in-game Settings screen source: {path}")
    text = path.read_text(encoding="utf-8")

    if "settings.action.exitGame" in text:
        raise SystemExit("TouchStation in-game session controls patch is already present")

    state_anchor = '''    var showReset by remember { mutableStateOf(false) }
'''
    state_replacement = state_anchor + '''    var pendingSessionAction by remember { mutableStateOf<String?>(null) }
'''
    text = replace_once(
        text,
        state_anchor,
        state_replacement,
        "in-game session confirmation state",
    )

    marker = '''                if (scopeContext != null) {
                    // Global ↔ Per-Game switch. Re-load()s the ViewModel for the chosen scope, which'''
    replacement = '''                // TouchStation game-session actions appear only while a title is open.
                // Every destructive action asks for confirmation before touching the VM.
                if (scopeGame != null) {
                    Column(
                        Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 16.dp, vertical = 8.dp),
                    ) {
                        Text(
                            "GAME SESSION",
                            color = MaterialTheme.colorScheme.primary,
                            style = MaterialTheme.typography.titleSmall,
                        )
                        Spacer(Modifier.height(4.dp))
                        Text(
                            "Control the game currently running behind this Settings screen.",
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            style = MaterialTheme.typography.bodySmall,
                        )
                        Spacer(Modifier.height(8.dp))

                        Box(
                            Modifier
                                .fillMaxWidth()
                                .controllerFocusable(
                                    "settings.action.resumeGame",
                                    RoundedCornerShape(12.dp),
                                    onConfirm = onBack,
                                ),
                        ) {
                            TextButton(onClick = onBack, modifier = Modifier.fillMaxWidth()) {
                                Text("↩  Resume Game")
                            }
                        }
                        Box(
                            Modifier
                                .fillMaxWidth()
                                .controllerFocusable(
                                    "settings.action.restartGame",
                                    RoundedCornerShape(12.dp),
                                    onConfirm = { pendingSessionAction = "restart" },
                                ),
                        ) {
                            TextButton(
                                onClick = { pendingSessionAction = "restart" },
                                modifier = Modifier.fillMaxWidth(),
                            ) {
                                Text("↻  Restart Game")
                            }
                        }
                        Box(
                            Modifier
                                .fillMaxWidth()
                                .controllerFocusable(
                                    "settings.action.saveAndExit",
                                    RoundedCornerShape(12.dp),
                                    onConfirm = { pendingSessionAction = "save_and_exit" },
                                ),
                        ) {
                            TextButton(
                                onClick = { pendingSessionAction = "save_and_exit" },
                                modifier = Modifier.fillMaxWidth(),
                            ) {
                                Text("▣  Save State & Exit")
                            }
                        }
                        Box(
                            Modifier
                                .fillMaxWidth()
                                .controllerFocusable(
                                    "settings.action.exitGame",
                                    RoundedCornerShape(12.dp),
                                    onConfirm = { pendingSessionAction = "exit" },
                                ),
                        ) {
                            TextButton(
                                onClick = { pendingSessionAction = "exit" },
                                modifier = Modifier.fillMaxWidth(),
                            ) {
                                Text(
                                    "■  Exit Game",
                                    color = MaterialTheme.colorScheme.error,
                                )
                            }
                        }
                    }
                }

                if (scopeContext != null) {
                    // Global ↔ Per-Game switch. Re-load()s the ViewModel for the chosen scope, which'''
    text = replace_once(
        text,
        marker,
        replacement,
        "in-game gear Settings session controls",
    )

    dialog_marker = '''            onDismiss = { showReset = false },
        )
    }
}

/** Floating "back to top" affordance'''
    dialog_replacement = '''            onDismiss = { showReset = false },
        )
    }

    pendingSessionAction?.let { action ->
        val details = when (action) {
            "restart" -> Triple(
                "Restart Game?",
                "The current game will restart. Progress since your last in-game save may be lost.",
                "Restart Game",
            )
            "save_and_exit" -> Triple(
                "Save State & Exit?",
                "TouchStation will write an autosave state, then close the current game and return to the library.",
                "Save State & Exit",
            )
            else -> Triple(
                "Exit Game?",
                "The current game will close and return to the library. Progress since your last in-game save may be lost.",
                "Exit Game",
            )
        }
        com.armsx2.ui.common.ConfirmOverlay(
            title = details.first,
            message = details.second,
            confirmLabel = details.third,
            destructive = true,
            idPrefix = "touchstation-session-$action",
            onConfirm = {
                pendingSessionAction = null
                com.armsx2.ui.WindowImpl.inGameScreen.value = null
                when (action) {
                    "restart" -> com.armsx2.runtime.MainActivityRuntime.restart()
                    "save_and_exit" -> com.armsx2.runtime.MainActivityRuntime.closeGame(saveAutosave = true)
                    else -> com.armsx2.runtime.MainActivityRuntime.closeGame()
                }
            },
            onDismiss = { pendingSessionAction = null },
        )
    }
}

/** Floating "back to top" affordance'''
    text = replace_once(
        text,
        dialog_marker,
        dialog_replacement,
        "in-game session action confirmation dialogs",
    )
    path.write_text(text, encoding="utf-8")

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
    patch_touchstation_drawer(app_dir)
    patch_touchstation_about(app_dir)
    patch_touchstation_xmb(app_dir)
    patch_performance_tab(app_dir)
    patch_app_name(app_dir)
    patch_app_wordmark(app_dir)
    patch_launcher_manifest(app_dir)
    patch_launcher_vector(app_dir)
    patch_touch_controls(app_dir)
    patch_in_game_settings_button(app_dir)
    patch_in_game_settings_exit(app_dir)
    patch_touchstation_runtime_features(app_dir)
    patch_pause_menu_exit(app_dir)
    patch_boot_splash_branding(app_dir)
    write_launcher_icons(app_dir)

    print("TouchStation source preparation complete.")
    print("App label and visible wordmarks: TouchStation")
    print("Version: 5.0.0 / versionCode 502")
    print("Virtual gameplay controls: hidden; physical PlayStation/gamepad input remains dedicated to the game.")
    print("In-game settings access: touch-only gear plus controller route through Pause Menu > Options > All Settings.")
    print("In-game gear Settings screen: controller-focusable Exit Game stops the VM and returns to the library.")
    print("Extra shader controls: compiler threads and shader/SPU compile notifications.")
    print("TouchStation advanced settings: 26 additional live-applied RSX, SPU, VRAM, and compatibility controls.")
    print("Pause menu: explicit Exit Game action in classic and XMB menus.")
    print("Built-in splash: TouchStation wordmark; custom user intro videos remain supported.")
    print("Chipset profiles: Auto detect, Dimensity, Snapdragon, Exynos")
    print("Auto applies a supported chipset profile when Performance settings are opened.")
    print("Native PPU/SPU/RSX libraries: supplied unchanged from the pinned upstream APK.")




if __name__ == "__main__":
    main()
