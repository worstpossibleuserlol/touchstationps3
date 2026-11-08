#!/usr/bin/env python3
"""Apply TouchStation 10.0.0 stability, PPU/SPU diagnostics and verified automation."""
from __future__ import annotations

import argparse
from pathlib import Path


KOTLIN_SOURCE = r'''package com.armsx2.ui.settings

import android.app.ActivityManager
import android.app.ApplicationExitInfo
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.Debug
import android.os.PowerManager
import android.os.StatFs
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.edit
import com.armsx2.EmuState
import com.armsx2.config.Settings
import com.armsx2.config.SettingsScope
import com.armsx2.runtime.MainActivityRuntime
import com.armsx2.ui.InGameOverlay
import com.armsx3.Rpcs3Bridge
import com.armsx3.core.ARMSX3
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import java.io.File
import java.util.Locale

private data class TouchStation10Snapshot(
    val totalRamMb: Long?,
    val availableRamMb: Long?,
    val appPssMb: Int?,
    val freeStorageMb: Long?,
    val thermalStatus: Int?,
    val vulkanFeature: String,
    val previousExit: String,
)

private data class TouchStation10CacheSnapshot(
    val ppuFiles: Int,
    val ppuBytes: Long,
    val spuFiles: Int,
    val spuBytes: Long,
    val shaderFiles: Int,
    val shaderBytes: Long,
)

private fun touchStation10ExitReason(context: Context, manager: ActivityManager?): String {
    if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return "N/A — Android 11+ required"
    return runCatching {
        val exit = manager?.getHistoricalProcessExitReasons(context.packageName, 0, 6)
            ?.firstOrNull() ?: return@runCatching "No historical process exit reported"
        val reason = when (exit.reason) {
            ApplicationExitInfo.REASON_CRASH -> "Java crash"
            ApplicationExitInfo.REASON_CRASH_NATIVE -> "Native crash"
            ApplicationExitInfo.REASON_ANR -> "Application not responding"
            ApplicationExitInfo.REASON_LOW_MEMORY -> "Low-memory termination"
            ApplicationExitInfo.REASON_EXCESSIVE_RESOURCE_USAGE -> "Excessive resource use"
            else -> "Android exit reason " + exit.reason
        }
        reason + " · " +
            android.text.format.DateFormat.format("yyyy-MM-dd HH:mm:ss", exit.timestamp) +
            (exit.description?.takeIf { it.isNotBlank() }?.let { " · " + it } ?: "")
    }.getOrDefault("Exit history unavailable")
}

private fun readTouchStation10Snapshot(context: Context): TouchStation10Snapshot {
    val manager = context.getSystemService(Context.ACTIVITY_SERVICE) as? ActivityManager
    val memory = ActivityManager.MemoryInfo()
    runCatching { manager?.getMemoryInfo(memory) }
    val appPss = runCatching {
        val info = Debug.MemoryInfo()
        Debug.getMemoryInfo(info)
        info.totalPss.takeIf { it > 0 }?.div(1024)
    }.getOrNull()
    val thermal = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
        runCatching {
            (context.getSystemService(Context.POWER_SERVICE) as? PowerManager)?.currentThermalStatus
        }.getOrNull()
    } else null
    val features = runCatching { context.packageManager.systemAvailableFeatures.toList() }
        .getOrDefault(emptyList())
    val version = features.firstOrNull { it.name == "android.hardware.vulkan.version" }
    val level = features.firstOrNull { it.name == "android.hardware.vulkan.level" }
    val vulkan = when {
        version != null && level != null ->
            "Android feature: version " + version.version + ", level " + level.version
        version != null -> "Android feature version " + version.version
        level != null -> "Android feature level " + level.version
        else -> "Not reported by Android"
    }
    val freeStorage = runCatching {
        StatFs(context.filesDir.absolutePath).availableBytes / (1024L * 1024L)
    }.getOrNull()
    return TouchStation10Snapshot(
        totalRamMb = memory.totalMem.takeIf { it > 0L }?.div(1024L * 1024L),
        availableRamMb = memory.availMem.takeIf { it > 0L }?.div(1024L * 1024L),
        appPssMb = appPss,
        freeStorageMb = freeStorage,
        thermalStatus = thermal,
        vulkanFeature = vulkan,
        previousExit = touchStation10ExitReason(context, manager),
    )
}

private fun touchStation10CacheSnapshot(context: Context): TouchStation10CacheSnapshot {
    val root = File(MainActivityRuntime.assetCopyRoot(context), "cache")
    fun measure(directory: File): Pair<Int, Long> {
        if (!directory.isDirectory) return 0 to 0L
        var count = 0
        var bytes = 0L
        runCatching {
            directory.walkTopDown().maxDepth(4).take(5000).forEach { file ->
                if (file.isFile) {
                    count += 1
                    bytes += file.length().coerceAtLeast(0L)
                }
            }
        }
        return count to bytes
    }
    val ppu = measure(File(root, "ppu"))
    val spu = measure(File(root, "spu"))
    val knownShaderNames = listOf(
        "vulkan_pipelines.bin", "vulkan_shaders.bin", "vulkan_shaders.idx",
        "gl_programs.bin", "gl_programs.idx",
    )
    val shaderFiles = knownShaderNames.map { File(root, it) }.filter { it.isFile }
    return TouchStation10CacheSnapshot(
        ppuFiles = ppu.first,
        ppuBytes = ppu.second,
        spuFiles = spu.first,
        spuBytes = spu.second,
        shaderFiles = shaderFiles.size,
        shaderBytes = shaderFiles.sumOf { runCatching { it.length() }.getOrDefault(0L) },
    )
}

private fun touchStation10Thermal(status: Int?): String {
    if (status == null) return "N/A"
    return when (status) {
        PowerManager.THERMAL_STATUS_NONE -> "Normal"
        PowerManager.THERMAL_STATUS_LIGHT -> "Light"
        PowerManager.THERMAL_STATUS_MODERATE -> "Moderate"
        PowerManager.THERMAL_STATUS_SEVERE -> "Severe"
        PowerManager.THERMAL_STATUS_CRITICAL -> "Critical"
        PowerManager.THERMAL_STATUS_EMERGENCY -> "Emergency"
        PowerManager.THERMAL_STATUS_SHUTDOWN -> "Shutdown"
        else -> "Unknown (" + status + ")"
    }
}

private fun touchStation10FormatBytes(value: Long): String {
    val mb = value / (1024f * 1024f)
    return if (mb >= 1024f) String.format(Locale.US, "%.2f GB", mb / 1024f)
        else String.format(Locale.US, "%.1f MB", mb)
}

private fun touchStation10Record(context: Context, event: String) {
    runCatching {
        val file = File(context.filesDir, "touchstation-v10-session.log")
        file.appendText(
            System.currentTimeMillis().toString() + " | " +
                event.replace('\n', ' ').take(500) + "\n"
        )
    }
}

private fun touchStation10Report(
    context: Context,
    snapshot: TouchStation10Snapshot?,
    cache: TouchStation10CacheSnapshot?,
    title: String,
    serial: String,
    settings: Settings,
): String = buildString {
    appendLine("TouchStation 10.0.0 diagnostic report")
    appendLine("Device: " + Build.MANUFACTURER + " " + Build.MODEL)
    val soc = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
        Build.SOC_MANUFACTURER + " " + Build.SOC_MODEL
    } else Build.HARDWARE
    appendLine("SoC: " + soc)
    appendLine("Hardware: " + Build.HARDWARE)
    appendLine("Android: " + Build.VERSION.RELEASE + " (API " + Build.VERSION.SDK_INT + ")")
    appendLine("ABI: " + Build.SUPPORTED_ABIS.joinToString())
    appendLine("CPU cores available: " + Runtime.getRuntime().availableProcessors())
    appendLine("Engine initialized: " + ARMSX3.initialized)
    appendLine("Native runtime ready: " + MainActivityRuntime.nativeReady.value)
    appendLine("CPU compatibility: " + (Rpcs3Bridge.unsupportedCpuMessage ?: "No unsupported-CPU warning reported"))
    appendLine("Game: " + title)
    appendLine("Game serial/key: " + serial)
    appendLine("Settings scope: " + InGameOverlay.settingsScope.value)
    appendLine("PPU decoder: " + settings.ps3.ppuDecoder)
    appendLine("PPU threads: " + settings.ps3.ppuThreads)
    appendLine("LLVM compile threads: " + settings.ps3.llvmThreads)
    appendLine("LLVM precompile: " + settings.ps3.llvmPrecompile)
    appendLine("SPU decoder: " + settings.ps3.spuDecoder)
    appendLine("SPU block size: " + settings.ps3.spuBlockSize)
    appendLine("Preferred SPU threads: " + settings.ps3.preferredSpuThreads)
    appendLine("RSX GPU profile: " + settings.gpuProfile)
    appendLine("Native in-game overlay mode: " + InGameOverlay.osdMode.value)
    appendLine("Total RAM MB: " + (snapshot?.totalRamMb?.toString() ?: "N/A"))
    appendLine("Available RAM MB: " + (snapshot?.availableRamMb?.toString() ?: "N/A"))
    appendLine("App PSS MB: " + (snapshot?.appPssMb?.toString() ?: "N/A"))
    appendLine("Free storage MB: " + (snapshot?.freeStorageMb?.toString() ?: "N/A"))
    appendLine("Thermal status: " + touchStation10Thermal(snapshot?.thermalStatus))
    appendLine("Vulkan: " + (snapshot?.vulkanFeature ?: "N/A"))
    appendLine("Previous Android exit: " + (snapshot?.previousExit ?: "N/A"))
    appendLine("PPU cache files/bytes: " + (cache?.ppuFiles?.toString() ?: "N/A") + " / " + (cache?.ppuBytes?.toString() ?: "N/A"))
    appendLine("SPU cache files/bytes: " + (cache?.spuFiles?.toString() ?: "N/A") + " / " + (cache?.spuBytes?.toString() ?: "N/A"))
    appendLine("Shader cache files/bytes: " + (cache?.shaderFiles?.toString() ?: "N/A") + " / " + (cache?.shaderBytes?.toString() ?: "N/A"))
    appendLine("Physical GPU utilization: N/A unless exposed by the Android GPU driver")
    appendLine("Native PPU/SPU compile timings, per-instruction counters and structured FIFO traces: N/A unless exposed by the pinned native bridge")
    appendLine("Deep game-file integrity scan: not available through the current Android storage/native bridge")
    appendLine("Session log: " + File(context.filesDir, "touchstation-v10-session.log").absolutePath)
}

@Composable
fun TouchStation10StabilitySuite(
    settings: Settings,
    onApply: (Settings) -> Boolean,
) {
    val context = LocalContext.current
    val snapshot = remember { mutableStateOf<TouchStation10Snapshot?>(null) }
    val cache = remember { mutableStateOf<TouchStation10CacheSnapshot?>(null) }
    val message = remember { mutableStateOf("") }
    val game = MainActivityRuntime.currentGame.value
    val gameTitle = game?.title?.takeIf { it.isNotBlank() } ?: "No game loaded"
    val gameSerial = game?.serial?.takeIf { it.isNotBlank() }
        ?: game?.settingsKey?.takeIf { it.isNotBlank() } ?: "N/A"
    val perGame = InGameOverlay.settingsScope.value == SettingsScope.Game
    val cpuCores = Runtime.getRuntime().availableProcessors().coerceAtLeast(1)
    val totalRam = snapshot.value?.totalRamMb ?: 0L
    val recommendedPpuThreads = when {
        cpuCores >= 8 && totalRam >= 8_192L -> 4
        cpuCores >= 6 && totalRam >= 6_144L -> 3
        else -> 2
    }.coerceAtMost(cpuCores).coerceAtLeast(1)
    val recommendedLlvmThreads = if (totalRam >= 7_168L) 2 else 1
    val engineReady = ARMSX3.initialized
    val nativeReady = MainActivityRuntime.nativeReady.value
    val stopped = MainActivityRuntime.eState.value == EmuState.STOPPED

    LaunchedEffect(context) {
        while (true) {
            snapshot.value = withContext(Dispatchers.IO) { readTouchStation10Snapshot(context) }
            cache.value = withContext(Dispatchers.IO) { touchStation10CacheSnapshot(context) }
            delay(5_000L)
        }
    }

    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = androidx.compose.foundation.shape.RoundedCornerShape(18.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(9.dp),
        ) {
            Text("TouchStation 10.0 PS3 Stability & Diagnostics Suite", style = MaterialTheme.typography.titleLarge)
            Text(
                "PPU/SPU diagnostics, game launch checks, recovery, graphics reporting and verified automatic settings.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            TouchStation10Section("1–6. PPU and SPU Engine") {
                TouchStation10Row("PPU decoder", settings.ps3.ppuDecoder.toString())
                TouchStation10Row("PPU threads configured", settings.ps3.ppuThreads.toString())
                TouchStation10Row("Recommended PPU threads", recommendedPpuThreads.toString())
                TouchStation10Row("LLVM compile threads", settings.ps3.llvmThreads.toString())
                TouchStation10Row("LLVM precompile", if (settings.ps3.llvmPrecompile) "Enabled" else "Disabled")
                TouchStation10Row("PPU cache", cache.value?.let {
                    it.ppuFiles.toString() + " files · " + touchStation10FormatBytes(it.ppuBytes)
                } ?: "Scanning…")
                TouchStation10Row("SPU decoder / block", settings.ps3.spuDecoder.toString() + " / " + settings.ps3.spuBlockSize)
                TouchStation10Row("Preferred SPU threads", settings.ps3.preferredSpuThreads.toString())
                TouchStation10Row("SPU cache", cache.value?.let {
                    it.spuFiles.toString() + " files · " + touchStation10FormatBytes(it.spuBytes)
                } ?: "Scanning…")
                TouchStation10Row("Live PPU/SPU activity", "Use native in-game performance overlay")
                TouchStation10Row("Compile error history", "N/A — no structured native error feed")
                TouchStation10Row("Compile timing / instruction counters", "N/A — not exported by pinned bridge")
                Button(
                    onClick = {
                        val updated = settings.copy(
                            ps3 = settings.ps3.copy(
                                ppuThreads = recommendedPpuThreads,
                                llvmThreads = recommendedLlvmThreads,
                            ),
                        )
                        val verified = runCatching { onApply(updated) }.getOrDefault(false)
                        message.value = if (verified) {
                            touchStation10Record(context, "PPU optimizer applied and read-back verified")
                            "PPU recommendation saved and verified."
                        } else {
                            "PPU recommendation was not verified. Check the active settings scope."
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Apply PPU Thread Recommendation") }
                Text(
                    "Thread recommendations are conservative hardware starting points, not per-game performance guarantees. Cache data is inspected only; save data is never targeted.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            TouchStation10Section("7–13. Game Launch and Stability") {
                TouchStation10Row("Current game", gameTitle)
                TouchStation10Row("Game serial / settings key", gameSerial)
                TouchStation10Row("Emulator engine", if (engineReady) "Initialized" else "Not initialized")
                TouchStation10Row("Native runtime", if (nativeReady) "Ready" else "Not ready")
                TouchStation10Row("Launch metadata", if (game != null && gameTitle != "No game loaded") "Game entry detected" else "No active game entry")
                TouchStation10Row("Deep game-file verification", "N/A — current bridge has no full integrity scan")
                TouchStation10Row("Previous process exit", snapshot.value?.previousExit ?: "Scanning…")
                TouchStation10Row("FIFO / RSX structured trace", "N/A — native bridge does not export FIFO event details")
                TouchStation10Row("Game settings profile", if (perGame) "Per-game scope · " + gameSerial else "Global scope")
                TouchStation10Row("Save-data protection", "Cache tools do not target dev_hdd0/home or game saves")
                OutlinedButton(
                    onClick = {
                        val ready = engineReady && nativeReady
                        message.value = if (ready) {
                            touchStation10Record(context, "Launch readiness check: engine and native runtime ready")
                            "Engine and native runtime are ready. Game-file integrity still requires the core loader."
                        } else {
                            touchStation10Record(context, "Launch readiness check: engine/runtime not ready")
                            "Launch is not ready: the emulator engine or native runtime is not initialized."
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Run Game Launch Readiness Check") }
                OutlinedButton(
                    onClick = {
                        val safe = settings.copy(
                            hwScaler = 540,
                            ps3 = settings.ps3.copy(
                                ppuThreads = recommendedPpuThreads.coerceAtMost(2),
                                llvmThreads = 1,
                                spuBlockSize = 0,
                                preferredSpuThreads = 0,
                                msaaMode = 0,
                            ),
                        )
                        val verified = runCatching { onApply(safe) }.getOrDefault(false)
                        message.value = if (verified) {
                            touchStation10Record(context, "Safe boot profile saved and verified")
                            "Safe boot profile saved and verified. Game files, firmware and saves were not changed."
                        } else {
                            "Safe boot profile could not be verified. Game files, firmware and saves were not changed."
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Apply Safe Game Boot Profile") }
                Text(
                    "Recovery changes emulator settings only. It does not delete, rewrite or restore games, firmware or savedata.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            TouchStation10Section("14–17. Graphics and Performance") {
                TouchStation10Row("Vulkan feature", snapshot.value?.vulkanFeature ?: "Scanning…")
                TouchStation10Row("OpenGL / GPU renderer", "See Automatic Device Detection in Auto Optimization")
                TouchStation10Row("Vulkan extension list", "N/A — Android feature data is not a Vulkan device query")
                TouchStation10Row("FPS / frametime", "Native in-game overlay")
                TouchStation10Row("Guest PPU/SPU/RSX activity", "Native in-game overlay where available")
                TouchStation10Row("Physical GPU utilization", "N/A unless the Android driver exposes counters")
                TouchStation10Row("Android thermal severity", touchStation10Thermal(snapshot.value?.thermalStatus))
                TouchStation10Row("Available RAM", snapshot.value?.availableRamMb?.let { it.toString() + " MB" } ?: "N/A")
                TouchStation10Row("Free storage", snapshot.value?.freeStorageMb?.let { it.toString() + " MB" } ?: "N/A")
                TouchStation10Row("Known shader cache", cache.value?.let {
                    it.shaderFiles.toString() + " files · " + touchStation10FormatBytes(it.shaderBytes)
                } ?: "Scanning…")
                Text(
                    "Adaptive output scaling changes the Android presentation surface, not the PS3 game's internal RSX resolution.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            TouchStation10Section("18–20. Automation and Session Diagnostics") {
                TouchStation10Row("Auto Settings 2.0", "Save → read-back verification → success/failure")
                TouchStation10Row("Game-specific optimization", if (perGame) "Active per-game settings scope" else "Global; open a game's settings for a per-game profile")
                TouchStation10Row("Session recorder", File(context.filesDir, "touchstation-v10-session.log").let {
                    if (it.isFile) it.length().toString() + " bytes recorded" else "No events recorded yet"
                })
                TouchStation10Row(
                    "Last verified apply",
                    MainActivityRuntime.prefs.getString("touchstation.v10.lastApply", "No verified apply recorded")
                        ?: "No verified apply recorded",
                )
                OutlinedButton(
                    onClick = {
                        val report = touchStation10Report(
                            context, snapshot.value, cache.value, gameTitle, gameSerial, settings,
                        )
                        val intent = Intent(Intent.ACTION_SEND).apply {
                            type = "text/plain"
                            putExtra(Intent.EXTRA_SUBJECT, "TouchStation 10.0 diagnostic report")
                            putExtra(Intent.EXTRA_TEXT, report)
                        }
                        runCatching {
                            context.startActivity(Intent.createChooser(intent, "Share TouchStation diagnostics"))
                            touchStation10Record(context, "Diagnostic report exported")
                        }.onFailure {
                            message.value = "Could not open Android share: " + (it.message ?: "unknown error")
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Export TouchStation 10 Diagnostic Report") }
                OutlinedButton(
                    onClick = {
                        touchStation10Record(
                            context,
                            "Manual snapshot · game=" + gameTitle +
                                " · serial=" + gameSerial +
                                " · ppuThreads=" + settings.ps3.ppuThreads +
                                " · llvmThreads=" + settings.ps3.llvmThreads,
                        )
                        message.value = "Session snapshot recorded in app-private storage."
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Record Session Snapshot") }
                Text(
                    "The session recorder writes locally in app-private storage. Nothing is uploaded automatically; export opens Android's share sheet only when requested.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            if (message.value.isNotBlank()) {
                Text(message.value, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.primary)
            }
            TouchStation10Row("VM state", if (stopped) "Stopped" else "Running")
            Text(
                "Only values available from Android or the pinned native bridge are reported. Unsupported engine counters, Vulkan extension enumeration and FIFO traces remain N/A.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun TouchStation10Section(title: String, content: @Composable () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text(title, style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.primary)
        content()
    }
}

@Composable
private fun TouchStation10Row(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            label,
            modifier = Modifier.weight(1f),
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            value,
            modifier = Modifier.weight(1f),
            style = MaterialTheme.typography.bodySmall,
        )
    }
}
'''


def replace_once(text: str, old: str, new: str, description: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(
            "Expected exactly one " + description + " marker; found " + str(count)
        )
    return text.replace(old, new, 1)


def patch_version(app_dir: Path) -> None:
    path = app_dir / "build.gradle.kts"
    text = path.read_text(encoding="utf-8")
    if "versionCode = 900" not in text or 'versionName = "9.0.0"' not in text:
        raise SystemExit("Expected prepared 9.0.0 / versionCode 900 app before v10 promotion")
    text = replace_once(text, "versionCode = 900", "versionCode = 1000", "versionCode")
    text = replace_once(text, 'versionName = "9.0.0"', 'versionName = "10.0.0"', "versionName")
    path.write_text(text, encoding="utf-8")


def patch_v9_apply_verification(app_dir: Path) -> None:
    path = app_dir / "src/main/java/com/armsx2/ui/settings/TouchStation9AutoOptimizationSuite.kt"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "onApply: (Settings) -> Unit,",
        "onApply: (Settings) -> Boolean,",
        "v9 apply callback type",
    )
    old_auto = '''                        onClick = {
                            onApply(recommendation.settings)
                            runCatching { MainActivityRuntime.surface.value?.applyOutputScale() }
                            MainActivityRuntime.prefs.edit()
                                .putString("touchstation.v9.lastProfile", recommendation.name)
                                .apply()
                            message.value = recommendation.name + " profile applied to " +
                                if (perGame) "the active game's settings." else "global settings."
                        },'''
    new_auto = '''                        onClick = {
                            val verified = runCatching { onApply(recommendation.settings) }.getOrDefault(false)
                            if (verified) {
                                MainActivityRuntime.prefs.edit()
                                    .putString("touchstation.v10.lastApply", recommendation.name + " · verified")
                                    .putString("touchstation.v9.lastProfile", recommendation.name)
                                    .apply()
                                message.value = recommendation.name + " profile saved and read-back verified in " +
                                    if (perGame) "the active game's settings." else "global settings."
                            } else {
                                message.value = "Apply was not verified. TouchStation did not report success; reopen settings and check the selected scope."
                            }
                        },'''
    text = replace_once(text, old_auto, new_auto, "automatic settings Apply handler")
    old_adaptive = '''                            onApply(settings.copy(hwScaler = adaptive.first))
                            runCatching { MainActivityRuntime.surface.value?.applyOutputScale() }
                            message.value = "Adaptive output scale applied. It changes the Android output surface, not the PS3 game's internal RSX resolution."'''
    new_adaptive = '''                            val verified = runCatching {
                                onApply(settings.copy(hwScaler = adaptive.first))
                            }.getOrDefault(false)
                            message.value = if (verified) {
                                "Adaptive output scale saved and verified. It changes the Android output surface, not the PS3 game's internal RSX resolution."
                            } else {
                                "Adaptive output scale was not verified; the previous setting remains the reported state."
                            }'''
    text = replace_once(text, old_adaptive, new_adaptive, "adaptive output apply handler")
    old_recovery = '''                        onApply(recovery)
                        runCatching { MainActivityRuntime.surface.value?.applyOutputScale() }
                        message.value = "Safe Mode profile applied. Game data, firmware and saves were not changed."'''
    new_recovery = '''                        val verified = runCatching { onApply(recovery) }.getOrDefault(false)
                        message.value = if (verified) {
                            "Safe Mode profile saved and verified. Game data, firmware and saves were not changed."
                        } else {
                            "Safe Mode settings were not verified. Game data, firmware and saves were not changed."
                        }'''
    text = replace_once(text, old_recovery, new_recovery, "safe recovery apply handler")
    text = text.replace("TouchStation 9.0 Auto Optimization Suite", "TouchStation 10.0 Auto Optimization Suite")
    text = text.replace("TouchStation 9.0.0 diagnostic report", "TouchStation 10.0.0 diagnostic report")
    path.write_text(text, encoding="utf-8")


def verification_callback() -> str:
    return '''onApply = { updated ->
                runCatching {
                    apply(updated)
                    InGameOverlay.reloadSettings()
                    val saved = InGameOverlay.settingsState.value
                    val verified =
                        saved.hwScaler == updated.hwScaler &&
                        saved.gpuProfile == updated.gpuProfile &&
                        saved.ps3.ppuThreads == updated.ps3.ppuThreads &&
                        saved.ps3.llvmThreads == updated.ps3.llvmThreads &&
                        saved.ps3.spuBlockSize == updated.ps3.spuBlockSize &&
                        saved.ps3.preferredSpuThreads == updated.ps3.preferredSpuThreads &&
                        saved.ps3.msaaMode == updated.ps3.msaaMode
                    if (verified) {
                        com.armsx2.runtime.MainActivityRuntime.surface.value?.applyOutputScale()
                    }
                    verified
                }.getOrDefault(false)
            },'''


def patch_performance_tab(app_dir: Path) -> None:
    path = app_dir / "src/main/java/com/armsx2/ui/settings/PerformanceTab.kt"
    text = path.read_text(encoding="utf-8")
    old_callback = '''            onApply = { updated ->
                apply(updated)
                com.armsx2.runtime.MainActivityRuntime.surface.value?.applyOutputScale()
            },'''
    text = replace_once(text, old_callback, "            " + verification_callback(), "verified settings callback in PerformanceTab")
    anchor = '''        TouchStation9AutoOptimizationSuite(
            settings = s,
            ''' + verification_callback() + '''
        )
        SettingsDivider()

'''
    addition = anchor + '''        TouchStation10StabilitySuite(
            settings = s,
            ''' + verification_callback() + '''
        )
        SettingsDivider()

'''
    text = replace_once(text, anchor, addition, "TouchStation 10 suite placement")
    path.write_text(text, encoding="utf-8")


def patch_control_center(app_dir: Path) -> None:
    path = app_dir / "src/main/java/com/armsx2/ui/settings/TouchStationControlCenter.kt"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "TouchStation 8.0.0 diagnostic report",
        "TouchStation 10.0.0 diagnostic report",
    )
    path.write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args()
    app_dir = args.source / "app"
    settings_dir = app_dir / "src/main/java/com/armsx2/ui/settings"
    required = [
        app_dir / "build.gradle.kts",
        settings_dir / "PerformanceTab.kt",
        settings_dir / "TouchStation9AutoOptimizationSuite.kt",
        settings_dir / "TouchStationControlCenter.kt",
    ]
    for path in required:
        if not path.is_file():
            raise SystemExit("Missing expected source file: " + str(path))

    patch_version(app_dir)
    patch_v9_apply_verification(app_dir)
    patch_performance_tab(app_dir)
    patch_control_center(app_dir)
    (settings_dir / "TouchStation10StabilitySuite.kt").write_text(
        KOTLIN_SOURCE,
        encoding="utf-8",
    )

    print("TouchStation 10.0.0 suite applied.")
    print("Added PPU/SPU configuration diagnostics, cache inspection, launch readiness, crash history, recovery profiles, Vulkan/thermal reports, per-game settings context and session export.")
    print("Fixed Auto Settings: apply, re-read ConfigStore, compare persisted settings, and report success only after verification.")
    print("Unsupported native metrics, deep game-file checks, Vulkan extension details and FIFO traces remain N/A unless the pinned bridge exposes them.")


if __name__ == "__main__":
    main()
