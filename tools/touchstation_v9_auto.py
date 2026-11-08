#!/usr/bin/env python3
"""Add TouchStation 9.0.0 device intelligence, auto profiles and recovery tools."""
from __future__ import annotations

import argparse
import re
from pathlib import Path


V9_SOURCE = r'''package com.armsx2.ui.settings

import android.app.ActivityManager
import android.content.Context
import android.content.Intent
import android.opengl.EGL14
import android.opengl.EGLConfig
import android.opengl.EGLContext
import android.opengl.EGLDisplay
import android.opengl.EGLSurface
import android.opengl.GLES20
import android.os.Build
import android.os.Debug
import android.os.PowerManager
import android.os.StatFs
import android.os.SystemClock
import android.view.WindowManager
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.armsx2.config.Settings
import com.armsx2.config.SettingsScope
import com.armsx2.runtime.MainActivityRuntime
import com.armsx2.ui.InGameOverlay
import com.armsx3.Rpcs3Bridge
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.util.Locale

private data class TouchStation9DeviceSnapshot(
    val device: String,
    val soc: String,
    val hardware: String,
    val cpuCores: Int,
    val supportedAbis: String,
    val android: String,
    val totalRamMb: Long?,
    val availableRamMb: Long?,
    val appPssMb: Int?,
    val freeStorageMb: Long?,
    val thermalStatus: Int?,
    val refreshRateHz: Float,
    val gpuRenderer: String,
    val gpuVendor: String,
    val glVersion: String,
    val vulkanFeature: String,
)

private data class TouchStation9Recommendation(
    val name: String,
    val reason: String,
    val settings: Settings,
    val outputLabel: String,
)

private data class TouchStation9LiveState(
    val availableRamMb: Long?,
    val appPssMb: Int?,
    val freeStorageMb: Long?,
    val thermalStatus: Int?,
)

private fun readTouchStation9GlInfo(): Triple<String, String, String> {
    var display: EGLDisplay = EGL14.EGL_NO_DISPLAY
    var surface: EGLSurface = EGL14.EGL_NO_SURFACE
    var context: EGLContext = EGL14.EGL_NO_CONTEXT
    try {
        display = EGL14.eglGetDisplay(EGL14.EGL_DEFAULT_DISPLAY)
        if (display == EGL14.EGL_NO_DISPLAY) return Triple("N/A", "N/A", "EGL unavailable")

        val versions = IntArray(2)
        if (!EGL14.eglInitialize(display, versions, 0, versions, 1)) {
            return Triple("N/A", "N/A", "EGL initialization unavailable")
        }

        val configAttributes = intArrayOf(
            EGL14.EGL_RENDERABLE_TYPE, EGL14.EGL_OPENGL_ES2_BIT,
            EGL14.EGL_SURFACE_TYPE, EGL14.EGL_PBUFFER_BIT,
            EGL14.EGL_NONE,
        )
        val configs = arrayOfNulls<EGLConfig>(1)
        val configCount = IntArray(1)
        if (!EGL14.eglChooseConfig(
                display, configAttributes, 0, configs, 0, configs.size, configCount, 0,
            ) || configCount[0] == 0
        ) {
            return Triple("N/A", "N/A", "No EGL config")
        }

        val config = configs[0] ?: return Triple("N/A", "N/A", "No EGL config")
        context = EGL14.eglCreateContext(
            display, config, EGL14.EGL_NO_CONTEXT,
            intArrayOf(EGL14.EGL_CONTEXT_CLIENT_VERSION, 2, EGL14.EGL_NONE), 0,
        ) ?: EGL14.EGL_NO_CONTEXT
        if (context == EGL14.EGL_NO_CONTEXT) return Triple("N/A", "N/A", "EGL context unavailable")

        surface = EGL14.eglCreatePbufferSurface(
            display, config,
            intArrayOf(EGL14.EGL_WIDTH, 1, EGL14.EGL_HEIGHT, 1, EGL14.EGL_NONE), 0,
        ) ?: EGL14.EGL_NO_SURFACE
        if (surface == EGL14.EGL_NO_SURFACE ||
            !EGL14.eglMakeCurrent(display, surface, surface, context)
        ) {
            return Triple("N/A", "N/A", "OpenGL context unavailable")
        }

        val vendor = GLES20.glGetString(0x1F00)?.trim().orEmpty().ifBlank { "N/A" }
        val renderer = GLES20.glGetString(0x1F01)?.trim().orEmpty().ifBlank { "N/A" }
        val version = GLES20.glGetString(0x1F02)?.trim().orEmpty().ifBlank { "N/A" }
        return Triple(renderer, vendor, version)
    } catch (_: Throwable) {
        return Triple("N/A", "N/A", "GPU query unavailable")
    } finally {
        if (display != EGL14.EGL_NO_DISPLAY) {
            runCatching {
                EGL14.eglMakeCurrent(
                    display, EGL14.EGL_NO_SURFACE, EGL14.EGL_NO_SURFACE, EGL14.EGL_NO_CONTEXT,
                )
            }
            if (surface != EGL14.EGL_NO_SURFACE) runCatching { EGL14.eglDestroySurface(display, surface) }
            if (context != EGL14.EGL_NO_CONTEXT) runCatching { EGL14.eglDestroyContext(display, context) }
            runCatching { EGL14.eglTerminate(display) }
        }
    }
}

private fun readTouchStation9LiveState(context: Context): TouchStation9LiveState {
    val activityManager = context.getSystemService(Context.ACTIVITY_SERVICE) as? ActivityManager
    val memory = ActivityManager.MemoryInfo()
    runCatching { activityManager?.getMemoryInfo(memory) }
    val availableRam = memory.availMem.takeIf { it > 0L }?.div(1024L * 1024L)
    val appPss = runCatching {
        val info = Debug.MemoryInfo()
        Debug.getMemoryInfo(info)
        info.totalPss.takeIf { it > 0 }?.div(1024)
    }.getOrNull()
    val freeStorage = runCatching {
        StatFs(context.filesDir.absolutePath).availableBytes / (1024L * 1024L)
    }.getOrNull()
    val thermal = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
        runCatching {
            (context.getSystemService(Context.POWER_SERVICE) as? PowerManager)?.currentThermalStatus
        }.getOrNull()
    } else null

    return TouchStation9LiveState(
        availableRamMb = availableRam,
        appPssMb = appPss,
        freeStorageMb = freeStorage,
        thermalStatus = thermal,
    )
}

private fun readTouchStation9DeviceSnapshot(context: Context): TouchStation9DeviceSnapshot {
    val activityManager = context.getSystemService(Context.ACTIVITY_SERVICE) as? ActivityManager
    val memory = ActivityManager.MemoryInfo()
    runCatching { activityManager?.getMemoryInfo(memory) }
    val totalRam = memory.totalMem.takeIf { it > 0L }?.div(1024L * 1024L)
    val live = readTouchStation9LiveState(context)
    val soc = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
        listOf(Build.SOC_MANUFACTURER, Build.SOC_MODEL)
            .filter { it.isNotBlank() && !it.equals("unknown", ignoreCase = true) }
            .joinToString(" ")
            .ifBlank { Build.HARDWARE.ifBlank { "Not reported" } }
    } else {
        Build.HARDWARE.ifBlank { "Not reported" }
    }
    val display = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
        context.display
    } else {
        (context.getSystemService(Context.WINDOW_SERVICE) as? WindowManager)?.defaultDisplay
    }
    val refreshRate = display?.refreshRate?.takeIf { it > 0f } ?: 0f
    val features = runCatching { context.packageManager.systemAvailableFeatures.toList() }.getOrDefault(emptyList())
    val vulkanVersion = features.firstOrNull { it.name == "android.hardware.vulkan.version" }
    val vulkanLevel = features.firstOrNull { it.name == "android.hardware.vulkan.level" }
    val vulkan = when {
        vulkanVersion != null && vulkanLevel != null ->
            "Android feature reported (version code " + vulkanVersion.version +
                ", level " + vulkanLevel.version + ")"
        vulkanVersion != null -> "Android feature version code " + vulkanVersion.version
        vulkanLevel != null -> "Android feature level " + vulkanLevel.version
        else -> "Not reported by Android"
    }
    val gl = readTouchStation9GlInfo()

    return TouchStation9DeviceSnapshot(
        device = Build.MANUFACTURER + " " + Build.MODEL,
        soc = soc,
        hardware = Build.HARDWARE.ifBlank { "N/A" },
        cpuCores = Runtime.getRuntime().availableProcessors().coerceAtLeast(1),
        supportedAbis = Build.SUPPORTED_ABIS.joinToString().ifBlank { "N/A" },
        android = Build.VERSION.RELEASE + " (API " + Build.VERSION.SDK_INT + ")",
        totalRamMb = totalRam,
        availableRamMb = live.availableRamMb,
        appPssMb = live.appPssMb,
        freeStorageMb = live.freeStorageMb,
        thermalStatus = live.thermalStatus,
        refreshRateHz = refreshRate,
        gpuRenderer = gl.first,
        gpuVendor = gl.second,
        glVersion = gl.third,
        vulkanFeature = vulkan,
    )
}

private fun touchStation9GpuProfile(renderer: String): Int {
    val value = renderer.lowercase(Locale.US)
    return when {
        "mali" in value -> 1
        "adreno" in value -> 2
        "powervr" in value -> 3
        "xclipse" in value -> 4
        else -> 0
    }
}

private fun touchStation9ThermalLabel(status: Int?): String {
    if (status == null) return "N/A — Android thermal status unavailable"
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

private fun touchStation9Recommendation(
    snapshot: TouchStation9DeviceSnapshot,
    current: Settings,
): TouchStation9Recommendation {
    val ram = snapshot.totalRamMb ?: 0L
    val thermal = snapshot.thermalStatus ?: PowerManager.THERMAL_STATUS_NONE
    val tier = when {
        ram >= 12L * 1024L && snapshot.cpuCores >= 8 &&
            thermal < PowerManager.THERMAL_STATUS_MODERATE -> "Quality"
        ram >= 7L * 1024L && snapshot.cpuCores >= 6 &&
            thermal < PowerManager.THERMAL_STATUS_SEVERE -> "Balanced"
        else -> "Performance"
    }
    val outputScale = when (tier) {
        "Quality" -> 0
        "Balanced" -> 720
        else -> 540
    }
    val ppuThreads = (snapshot.cpuCores / 2).coerceIn(1, 4)
    // Keep concurrent LLVM compiles conservative: each compile can hold a large module in RAM.
    val llvmThreads = if (ram >= 7L * 1024L) 2 else 1
    val gpuProfile = touchStation9GpuProfile(snapshot.gpuRenderer)
    val updated = current.copy(
        hwScaler = outputScale,
        gpuProfile = if (gpuProfile == 0) current.gpuProfile else gpuProfile,
        ps3 = current.ps3.copy(
            ppuThreads = ppuThreads,
            llvmThreads = llvmThreads,
            spuBlockSize = 0,
            preferredSpuThreads = 0,
            msaaMode = 0,
        ),
    )
    val reason = "Based on " + snapshot.cpuCores + " available CPU cores, " +
        (snapshot.totalRamMb?.let { String.format(Locale.US, "%.1f GB RAM", it / 1024f) } ?: "unknown RAM") +
        " and the detected thermal state. Manual settings remain available."
    val outputLabel = when (outputScale) {
        0 -> "Screen output"
        720 -> "720p output"
        else -> "540p output"
    }
    return TouchStation9Recommendation(tier, reason, updated, outputLabel)
}

private fun touchStation9AdaptiveOutput(snapshot: TouchStation9DeviceSnapshot): Pair<Int, String> {
    val thermal = snapshot.thermalStatus ?: PowerManager.THERMAL_STATUS_NONE
    val freeRam = snapshot.availableRamMb ?: Long.MAX_VALUE
    return when {
        thermal >= PowerManager.THERMAL_STATUS_SEVERE || freeRam < 900L ->
            540 to "540p output — high thermal pressure or low available RAM"
        thermal >= PowerManager.THERMAL_STATUS_MODERATE || freeRam < 1_600L ->
            720 to "720p output — moderate thermal pressure or limited available RAM"
        else -> 0 to "Screen output — no Android thermal or memory warning"
    }
}

private val touchStation9ShaderCacheNames = listOf(
    "vulkan_pipelines.bin",
    "vulkan_shaders.bin",
    "vulkan_shaders.idx",
    "gl_programs.bin",
    "gl_programs.idx",
)

private fun touchStation9ShaderCacheFiles(context: Context): List<File> {
    val cache = File(MainActivityRuntime.assetCopyRoot(context), "cache")
    return touchStation9ShaderCacheNames.map { File(cache, it) }
}

private fun touchStation9QuickCpuCheck(): String {
    val start = SystemClock.elapsedRealtime()
    val stopAt = start + 300L
    var state = 0x13579BDF2468ACE0L
    var iterations = 0L
    while (SystemClock.elapsedRealtime() < stopAt) {
        repeat(20_000) {
            state = state xor (state shl 13)
            state = state xor (state ushr 7)
            state = state xor (state shl 17)
        }
        iterations += 20_000L
    }
    // Keep the changing result live so the loop cannot be treated as dead work.
    if (state == 0L) android.util.Log.d("TouchStation9", "CPU check sentinel")
    val elapsed = (SystemClock.elapsedRealtime() - start).coerceAtLeast(1L)
    return String.format(
        Locale.US,
        "%,d operations in %d ms — device-local smoke test, not a game FPS prediction",
        iterations, elapsed,
    )
}

private fun touchStation9DiagnosticReport(
    snapshot: TouchStation9DeviceSnapshot,
    gameTitle: String,
    gameSerial: String,
    settings: Settings,
): String = buildString {
    appendLine("TouchStation 9.0.0 diagnostic report")
    appendLine("Device: " + snapshot.device)
    appendLine("SoC: " + snapshot.soc)
    appendLine("Hardware: " + snapshot.hardware)
    appendLine("CPU cores available: " + snapshot.cpuCores)
    appendLine("Supported ABIs: " + snapshot.supportedAbis)
    appendLine("Android: " + snapshot.android)
    appendLine("GPU renderer: " + snapshot.gpuRenderer)
    appendLine("GPU vendor: " + snapshot.gpuVendor)
    appendLine("OpenGL ES: " + snapshot.glVersion)
    appendLine("Vulkan: " + snapshot.vulkanFeature)
    appendLine("Refresh rate: " + if (snapshot.refreshRateHz > 0f) snapshot.refreshRateHz.toString() + " Hz" else "N/A")
    appendLine("Total RAM: " + (snapshot.totalRamMb?.toString() ?: "N/A") + " MB")
    appendLine("Available RAM: " + (snapshot.availableRamMb?.toString() ?: "N/A") + " MB")
    appendLine("App PSS: " + (snapshot.appPssMb?.toString() ?: "N/A") + " MB")
    appendLine("Free storage: " + (snapshot.freeStorageMb?.toString() ?: "N/A") + " MB")
    appendLine("Thermal status: " + touchStation9ThermalLabel(snapshot.thermalStatus))
    appendLine("Game: " + gameTitle)
    appendLine("Game serial: " + gameSerial)
    appendLine("PPU threads: " + settings.ps3.ppuThreads)
    appendLine("LLVM compile threads: " + settings.ps3.llvmThreads)
    appendLine("SPU block size: " + settings.ps3.spuBlockSize)
    appendLine("Output scaler: " + settings.hwScaler)
    appendLine("GPU profile index: " + settings.gpuProfile)
    appendLine("Native CPU compatibility: " + (Rpcs3Bridge.unsupportedCpuMessage ?: "No unsupported-CPU warning reported by the bridge"))
    appendLine("Physical GPU utilization and native per-instruction counters are N/A unless exposed by the driver or native overlay.")
}

@Composable
fun TouchStation9AutoOptimizationSuite(
    settings: Settings,
    onApply: (Settings) -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val snapshot = remember { mutableStateOf<TouchStation9DeviceSnapshot?>(null) }
    val benchmark = remember { mutableStateOf("Not run") }
    val busy = remember { mutableStateOf(false) }
    val message = remember { mutableStateOf("") }
    val cacheMessage = remember { mutableStateOf("") }
    val game = MainActivityRuntime.currentGame.value
    val gameTitle = game?.title?.takeIf { it.isNotBlank() } ?: "No game loaded"
    val gameSerial = game?.serial?.takeIf { it.isNotBlank() } ?: "N/A"
    val perGame = InGameOverlay.settingsScope.value == SettingsScope.Game

    LaunchedEffect(context) {
        snapshot.value = withContext(Dispatchers.IO) { readTouchStation9DeviceSnapshot(context) }
        while (true) {
            val live = withContext(Dispatchers.IO) { readTouchStation9LiveState(context) }
            snapshot.value = snapshot.value?.copy(
                availableRamMb = live.availableRamMb,
                appPssMb = live.appPssMb,
                freeStorageMb = live.freeStorageMb,
                thermalStatus = live.thermalStatus,
            )
            delay(3_000)
        }
    }

    val detected = snapshot.value
    val recommendation = detected?.let { touchStation9Recommendation(it, settings) }
    val adaptive = detected?.let { touchStation9AdaptiveOutput(it) }
    val cacheFiles = remember(detected, cacheMessage.value) {
        if (detected == null) emptyList() else touchStation9ShaderCacheFiles(context)
            .filter { it.isFile }
    }
    val cacheBytes = cacheFiles.sumOf { runCatching { it.length() }.getOrDefault(0L) }

    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = androidx.compose.foundation.shape.RoundedCornerShape(18.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(9.dp),
        ) {
            Text("TouchStation 9.0 Auto Optimization Suite", style = MaterialTheme.typography.titleLarge)
            Text(
                "Device detection, automatic profiles, adaptive output scaling, compatibility checks and recovery tools.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            TouchStation9Section("1. Automatic Device Detection") {
                if (detected == null) {
                    TouchStation9Row("Device scan", "Detecting hardware…")
                } else {
                    TouchStation9Row("Device", detected.device)
                    TouchStation9Row("SoC", detected.soc)
                    TouchStation9Row("Android / API", detected.android)
                    TouchStation9Row("CPU cores available", detected.cpuCores.toString())
                    TouchStation9Row("Supported ABIs", detected.supportedAbis)
                    TouchStation9Row("GPU renderer", detected.gpuRenderer)
                    TouchStation9Row("GPU vendor", detected.gpuVendor)
                    TouchStation9Row("OpenGL ES", detected.glVersion)
                    TouchStation9Row("Vulkan feature", detected.vulkanFeature)
                    TouchStation9Row(
                        "Display refresh rate",
                        if (detected.refreshRateHz > 0f) String.format(Locale.US, "%.1f Hz", detected.refreshRateHz) else "N/A",
                    )
                    TouchStation9Row("System RAM", detected.totalRamMb?.let { it.toString() + " MB" } ?: "N/A")
                    TouchStation9Row("Available RAM", detected.availableRamMb?.let { it.toString() + " MB" } ?: "N/A")
                    TouchStation9Row("Free app storage", detected.freeStorageMb?.let { it.toString() + " MB" } ?: "N/A")
                    TouchStation9Row("Thermal status", touchStation9ThermalLabel(detected.thermalStatus))
                }
            }

            TouchStation9Section("2. Auto Configuration Engine") {
                if (recommendation == null) {
                    TouchStation9Row("Recommended profile", "Waiting for device scan")
                } else {
                    TouchStation9Row("Recommended profile", recommendation.name)
                    TouchStation9Row("PPU threads", recommendation.settings.ps3.ppuThreads.toString())
                    TouchStation9Row("LLVM compile threads", recommendation.settings.ps3.llvmThreads.toString())
                    TouchStation9Row("SPU block size", "Safe")
                    TouchStation9Row("MSAA", "Off")
                    TouchStation9Row("GPU profile", recommendation.settings.gpuProfile.toString())
                    TouchStation9Row("Output scaling", recommendation.outputLabel)
                    Text(recommendation.reason, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Button(
                        onClick = {
                            onApply(recommendation.settings)
                            runCatching { MainActivityRuntime.surface.value?.applyOutputScale() }
                            MainActivityRuntime.prefs.edit()
                                .putString("touchstation.v9.lastProfile", recommendation.name)
                                .apply()
                            message.value = recommendation.name + " profile applied to " +
                                if (perGame) "the active game's settings." else "global settings."
                        },
                        modifier = Modifier.fillMaxWidth(),
                        enabled = !busy.value,
                    ) {
                        Text("Apply Automatic Settings")
                    }
                }
                Text(
                    "Automatic settings are a starting profile. Change any individual option later; TouchStation does not lock manual settings.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            TouchStation9Section("3. Adaptive Resolution Guard") {
                if (adaptive != null) {
                    TouchStation9Row("Suggested output scale", adaptive.second)
                    OutlinedButton(
                        onClick = {
                            onApply(settings.copy(hwScaler = adaptive.first))
                            runCatching { MainActivityRuntime.surface.value?.applyOutputScale() }
                            message.value = "Adaptive output scale applied. It changes the Android output surface, not the PS3 game's internal RSX resolution."
                        },
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text("Apply Adaptive Output Scale")
                    }
                }
                Text(
                    "Uses Android thermal severity and available RAM. The pinned native bridge does not expose a frame-time callback for safe closed-loop FPS scaling, so no FPS-based adjustment is claimed.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            TouchStation9Section("4. Thermal and Memory Monitor") {
                TouchStation9Row("Thermal severity", detected?.let { touchStation9ThermalLabel(it.thermalStatus) } ?: "N/A")
                TouchStation9Row("Available RAM", detected?.availableRamMb?.let { it.toString() + " MB" } ?: "N/A")
                TouchStation9Row("TouchStation app PSS", detected?.appPssMb?.let { it.toString() + " MB" } ?: "N/A")
                TouchStation9Row("Free internal storage", detected?.freeStorageMb?.let { it.toString() + " MB" } ?: "N/A")
                Text(
                    "Android thermal status is a severity level, not a measured SoC temperature. Battery temperature is intentionally not presented as CPU/GPU temperature.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            TouchStation9Section("5. Game-Specific Profiles") {
                TouchStation9Row("Current game", gameTitle)
                TouchStation9Row("Game serial", gameSerial)
                TouchStation9Row("Settings scope", if (perGame) "Per-game overrides" else "Global")
                TouchStation9Row("Profile storage", "Uses the upstream global / per-game settings system")
                Text(
                    "Apply Automatic Settings while a game-specific scope is active to save the profile for that game. Manual overrides remain supported.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            TouchStation9Section("6. Compatibility Checker 2.0") {
                TouchStation9Row("Native CPU requirement", detected?.let {
                    Rpcs3Bridge.unsupportedCpuMessage ?: "No unsupported-CPU warning reported"
                } ?: "Waiting for device scan")
                TouchStation9Row("Architecture", detected?.supportedAbis ?: "N/A")
                TouchStation9Row("GPU / driver", detected?.gpuRenderer ?: "N/A")
                TouchStation9Row("Game compatibility", "Upstream library metadata is retained")
                TouchStation9Row("Device-specific game rating", "Unknown until tested on this device and driver")
                TouchStation9Row("Active title", gameTitle)
                Text(
                    "A chipset name alone cannot prove that a PS3 title works. Device-specific compatibility is not guessed.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            TouchStation9Section("7. Performance Overlay") {
                TouchStation9Row("FPS and frame-time graphs", "Existing native in-game overlay")
                TouchStation9Row("PPU / SPU / guest RSX activity", "Only values exposed by the core")
                TouchStation9Row("Physical GPU utilization", "Driver counter required; otherwise N/A")
                TouchStation9Row("Overlay controls", "Settings → Performance → PPU Monitor")
                Text(
                    "This section reuses the 8.0.0 native overlay. It does not create fake Android GPU or emulator-core counters.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            TouchStation9Section("8. Shader Cache Manager") {
                TouchStation9Row("Tracked cache files", cacheFiles.size.toString())
                TouchStation9Row("Tracked cache size", String.format(Locale.US, "%.1f MB", cacheBytes / (1024f * 1024f)))
                OutlinedButton(
                    onClick = {
                        var deleted = 0
                        touchStation9ShaderCacheFiles(context).forEach { file ->
                            if (file.isFile && runCatching { file.delete() }.getOrDefault(false)) deleted++
                        }
                        cacheMessage.value = "Removed " + deleted + " known shader cache file(s). They rebuild when a game runs."
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("Clear Known Shader Caches")
                }
                if (cacheMessage.value.isNotBlank()) {
                    Text(cacheMessage.value, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Text(
                    "Only known compiled Vulkan/OpenGL cache files are touched. Game files, firmware, saves and configuration are not deleted.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            TouchStation9Section("9. Crash Recovery / Safe Mode") {
                TouchStation9Row("CPU compatibility warning", Rpcs3Bridge.unsupportedCpuMessage ?: "No unsupported-CPU warning")
                OutlinedButton(
                    onClick = {
                        val cores = detected?.cpuCores ?: Runtime.getRuntime().availableProcessors()
                        val recovery = settings.copy(
                            hwScaler = 540,
                            ps3 = settings.ps3.copy(
                                ppuThreads = (cores / 2).coerceIn(1, 2),
                                llvmThreads = 1,
                                spuBlockSize = 0,
                                preferredSpuThreads = 0,
                                msaaMode = 0,
                            ),
                        )
                        onApply(recovery)
                        runCatching { MainActivityRuntime.surface.value?.applyOutputScale() }
                        message.value = "Safe Mode profile applied. Game data, firmware and saves were not changed."
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("Apply Safe Recovery Profile")
                }
                OutlinedButton(
                    onClick = {
                        val report = touchStation9DiagnosticReport(
                            detected ?: readTouchStation9DeviceSnapshot(context),
                            gameTitle,
                            gameSerial,
                            settings,
                        )
                        val intent = Intent(Intent.ACTION_SEND).apply {
                            type = "text/plain"
                            putExtra(Intent.EXTRA_SUBJECT, "TouchStation diagnostic report")
                            putExtra(Intent.EXTRA_TEXT, report)
                        }
                        runCatching {
                            context.startActivity(Intent.createChooser(intent, "Share diagnostic report"))
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("Export Recovery Diagnostic")
                }
                Text(
                    "Safe Mode restores conservative emulator settings and provides a diagnostic report. It does not claim to intercept native process crashes or recover deleted game data.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            TouchStation9Section("10. Hardware Benchmark & Recommendation") {
                TouchStation9Row("Quick CPU check", benchmark.value)
                Button(
                    onClick = {
                        if (!busy.value) {
                            busy.value = true
                            scope.launch {
                                benchmark.value = withContext(Dispatchers.Default) {
                                    touchStation9QuickCpuCheck()
                                }
                                busy.value = false
                            }
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                    enabled = !busy.value,
                ) {
                    Text(if (busy.value) "Running brief CPU check…" else "Run Quick CPU Check")
                }
                Text(
                    "This short CPU smoke test checks that the app can run a bounded workload. It is not a GPU benchmark, PS3 game benchmark, or cross-device ranking.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            if (message.value.isNotBlank()) {
                Text(message.value, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.primary)
            }
            OutlinedButton(
                onClick = {
                    scope.launch {
                        snapshot.value = withContext(Dispatchers.IO) { readTouchStation9DeviceSnapshot(context) }
                        message.value = "Device and driver information refreshed."
                    }
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Refresh Device Detection")
            }
        }
    }
}

@Composable
private fun TouchStation9Section(title: String, content: @Composable () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text(title, style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.primary)
        content()
    }
}

@Composable
private fun TouchStation9Row(label: String, value: String) {
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


def replace_once(source: str, old: str, new: str, description: str) -> str:
    count = source.count(old)
    if count != 1:
        raise SystemExit(
            "Expected exactly one " + description + " marker; found " + str(count)
        )
    return source.replace(old, new, 1)


def patch_version(app_dir: Path) -> None:
    path = app_dir / "build.gradle.kts"
    text = path.read_text(encoding="utf-8")
    text, code_count = re.subn(
        r"(?m)^(\s*)versionCode\s*=\s*800\s*$",
        r"\g<1>versionCode = 900",
        text,
        count=1,
    )
    text, name_count = re.subn(
        r'(?m)^(\s*)versionName\s*=\s*"8\.0\.0"\s*$',
        r'\g<1>versionName = "9.0.0"',
        text,
        count=1,
    )
    if code_count != 1 or name_count != 1:
        raise SystemExit("Expected prepared 8.0.0 / versionCode 800 before promotion to 9.0.0 / 900")
    path.write_text(text, encoding="utf-8")


def patch_suite(app_dir: Path) -> None:
    settings_dir = app_dir / "src/main/java/com/armsx2/ui/settings"
    target = settings_dir / "TouchStation9AutoOptimizationSuite.kt"
    target.write_text(V9_SOURCE, encoding="utf-8")

    performance = settings_dir / "PerformanceTab.kt"
    text = performance.read_text(encoding="utf-8")
    marker = '''        TouchStation8MonitoringSuite(settings = s)
        SettingsDivider()

'''
    replacement = marker + '''        TouchStation9AutoOptimizationSuite(
            settings = s,
            onApply = { updated ->
                apply(updated)
                com.armsx2.runtime.MainActivityRuntime.surface.value?.applyOutputScale()
            },
        )
        SettingsDivider()

'''
    text = replace_once(text, marker, replacement, "TouchStation 9.0 suite placement")
    performance.write_text(text, encoding="utf-8")


def patch_diagnostic_version(app_dir: Path) -> None:
    path = app_dir / "src/main/java/com/armsx2/ui/settings/TouchStationControlCenter.kt"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "TouchStation 8.0.0 diagnostic report",
        "TouchStation 9.0.0 diagnostic report",
        "Control Center diagnostic report version",
    )
    path.write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args()
    app_dir = args.source / "app"

    for required in (
        app_dir / "build.gradle.kts",
        app_dir / "src/main/java/com/armsx2/ui/settings/PerformanceTab.kt",
        app_dir / "src/main/java/com/armsx2/ui/settings/TouchStation8MonitoringSuite.kt",
        app_dir / "src/main/java/com/armsx2/ui/settings/TouchStationControlCenter.kt",
    ):
        if not required.is_file():
            raise SystemExit("Missing expected source file: " + str(required))

    patch_version(app_dir)
    patch_suite(app_dir)
    patch_diagnostic_version(app_dir)

    print("TouchStation 9.0.0 Auto Optimization Suite applied.")
    print("Added hardware detection, automatic settings, adaptive output scaling, thermal/memory monitoring, per-game profiles, compatibility checks, overlay integration, shader cache management, safe recovery and a bounded CPU check.")
    print("Driver/native metrics remain N/A unless exposed; compatibility is not guessed.")
    

if __name__ == "__main__":
    main()
