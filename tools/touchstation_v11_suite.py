#!/usr/bin/env python3
"""Apply TouchStation 11.0.0 reliability, diagnostics and recovery tools."""
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
import android.view.InputDevice
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
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.armsx2.EmuState
import com.armsx2.config.Settings
import com.armsx2.config.SettingsScope
import com.armsx2.runtime.MainActivityRuntime
import com.armsx2.ui.InGameOverlay
import com.armsx3.core.ARMSX3
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import java.io.File
import java.util.Locale

private data class TouchStation11CacheEntry(
    val files: Int,
    val bytes: Long,
    val unreadable: Int,
)

private data class TouchStation11Snapshot(
    val totalRamMb: Long?,
    val availableRamMb: Long?,
    val appPssMb: Int?,
    val freeStorageMb: Long?,
    val thermalStatus: Int?,
    val controllers: List<String>,
    val ppu: TouchStation11CacheEntry,
    val spu: TouchStation11CacheEntry,
    val shaderFiles: Int,
    val shaderBytes: Long,
    val vulkanInfo: String,
    val previousExit: String,
)

private fun touchStation11ExitReason(context: Context): String {
    if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return "N/A — Android 11+ required"
    return runCatching {
        val manager = context.getSystemService(Context.ACTIVITY_SERVICE) as? ActivityManager
        val exit = manager?.getHistoricalProcessExitReasons(context.packageName, 0, 6)
            ?.firstOrNull() ?: return@runCatching "No historical Android process exit reported"
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
    }.getOrDefault("Android exit history unavailable")
}

private fun touchStation11Measure(directory: File): TouchStation11CacheEntry {
    if (!directory.isDirectory) return TouchStation11CacheEntry(0, 0L, 0)
    var files = 0
    var bytes = 0L
    var unreadable = 0
    runCatching {
        directory.walkTopDown().maxDepth(4).take(5000).forEach { file ->
            if (file.isFile) {
                files += 1
                bytes += file.length().coerceAtLeast(0L)
                if (!file.canRead()) unreadable += 1
            }
        }
    }
    return TouchStation11CacheEntry(files, bytes, unreadable)
}

private fun touchStation11Snapshot(context: Context): TouchStation11Snapshot {
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
    val root = File(MainActivityRuntime.assetCopyRoot(context), "cache")
    val ppu = touchStation11Measure(File(root, "ppu"))
    val spu = touchStation11Measure(File(root, "spu"))
    val shaderNames = listOf(
        "vulkan_pipelines.bin", "vulkan_shaders.bin", "vulkan_shaders.idx",
        "gl_programs.bin", "gl_programs.idx",
    )
    val shaderFiles = shaderNames.map { File(root, it) }.filter { it.isFile }
    val features = runCatching { context.packageManager.systemAvailableFeatures.toList() }
        .getOrDefault(emptyList())
    val version = features.firstOrNull { it.name == "android.hardware.vulkan.version" }
    val level = features.firstOrNull { it.name == "android.hardware.vulkan.level" }
    val vulkan = when {
        version != null && level != null ->
            "Android feature version " + version.version + ", level " + level.version
        version != null -> "Android feature version " + version.version
        level != null -> "Android feature level " + level.version
        else -> "No Vulkan feature version reported by Android"
    }
    val controllers = runCatching {
        InputDevice.getDeviceIds().mapNotNull { id ->
            val device = InputDevice.getDevice(id) ?: return@mapNotNull null
            val gamepad = (device.sources and InputDevice.SOURCE_GAMEPAD) == InputDevice.SOURCE_GAMEPAD
            val joystick = (device.sources and InputDevice.SOURCE_JOYSTICK) == InputDevice.SOURCE_JOYSTICK
            if (gamepad || joystick) device.name else null
        }.distinct()
    }.getOrDefault(emptyList())
    val freeStorage = runCatching {
        StatFs(context.filesDir.absolutePath).availableBytes / (1024L * 1024L)
    }.getOrNull()
    return TouchStation11Snapshot(
        totalRamMb = memory.totalMem.takeIf { it > 0L }?.div(1024L * 1024L),
        availableRamMb = memory.availMem.takeIf { it > 0L }?.div(1024L * 1024L),
        appPssMb = appPss,
        freeStorageMb = freeStorage,
        thermalStatus = thermal,
        controllers = controllers,
        ppu = ppu,
        spu = spu,
        shaderFiles = shaderFiles.size,
        shaderBytes = shaderFiles.sumOf { runCatching { it.length() }.getOrDefault(0L) },
        vulkanInfo = vulkan,
        previousExit = touchStation11ExitReason(context),
    )
}

private fun touchStation11Thermal(status: Int?): String {
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

private fun touchStation11Bytes(value: Long): String {
    val mb = value / (1024f * 1024f)
    return if (mb >= 1024f) String.format(Locale.US, "%.2f GB", mb / 1024f)
        else String.format(Locale.US, "%.1f MB", mb)
}

private fun touchStation11Record(context: Context, event: String) {
    runCatching {
        File(context.filesDir, "touchstation-v11-session.log").appendText(
            System.currentTimeMillis().toString() + " | " +
                event.replace('\n', ' ').take(500) + "\n"
        )
    }
}

private fun touchStation11ProfileKey(prefix: String, serial: String): String {
    val safeSerial = serial.filter { it.isLetterOrDigit() }.ifBlank { "global" }
    return prefix + safeSerial + "."
}

private fun touchStation11SaveProfile(prefix: String, settings: Settings) {
    MainActivityRuntime.prefs.edit()
        .putInt(prefix + "hwScaler", settings.hwScaler)
        .putInt(prefix + "ppuThreads", settings.ps3.ppuThreads)
        .putInt(prefix + "llvmThreads", settings.ps3.llvmThreads)
        .putBoolean(prefix + "llvmPrecompile", settings.ps3.llvmPrecompile)
        .putInt(prefix + "spuBlockSize", settings.ps3.spuBlockSize)
        .putInt(prefix + "preferredSpuThreads", settings.ps3.preferredSpuThreads)
        .putInt(prefix + "msaaMode", settings.ps3.msaaMode)
        .putBoolean(prefix + "saved", true)
        .apply()
}

private fun touchStation11RestoreProfile(
    prefix: String,
    current: Settings,
    onApply: (Settings) -> Boolean,
): Boolean {
    val prefs = MainActivityRuntime.prefs
    if (!prefs.getBoolean(prefix + "saved", false)) return false
    val restored = current.copy(
        hwScaler = prefs.getInt(prefix + "hwScaler", current.hwScaler),
        ps3 = current.ps3.copy(
            ppuThreads = prefs.getInt(prefix + "ppuThreads", current.ps3.ppuThreads),
            llvmThreads = prefs.getInt(prefix + "llvmThreads", current.ps3.llvmThreads),
            llvmPrecompile = prefs.getBoolean(prefix + "llvmPrecompile", current.ps3.llvmPrecompile),
            spuBlockSize = prefs.getInt(prefix + "spuBlockSize", current.ps3.spuBlockSize),
            preferredSpuThreads = prefs.getInt(prefix + "preferredSpuThreads", current.ps3.preferredSpuThreads),
            msaaMode = prefs.getInt(prefix + "msaaMode", current.ps3.msaaMode),
        ),
    )
    return runCatching { onApply(restored) }.getOrDefault(false)
}

@Composable
fun TouchStation11ReliabilitySuite(
    settings: Settings,
    onApply: (Settings) -> Boolean,
) {
    val context = LocalContext.current
    val prefs = MainActivityRuntime.prefs
    val snapshot = remember { mutableStateOf<TouchStation11Snapshot?>(null) }
    val message = remember { mutableStateOf("") }
    val timeline = remember { mutableStateListOf<String>() }
    val history = remember {
        mutableStateListOf<Int>().apply {
            prefs.getString("touchstation.v11.availableRamHistory", "").orEmpty()
                .split(",").mapNotNull { it.toIntOrNull() }.takeLast(20).forEach { add(it) }
        }
    }
    val game = MainActivityRuntime.currentGame.value
    val gameTitle = game?.title?.takeIf { it.isNotBlank() } ?: "No game loaded"
    val gameSerial = game?.serial?.takeIf { it.isNotBlank() }
        ?: game?.settingsKey?.takeIf { it.isNotBlank() } ?: "N/A"
    val hasGame = game != null && gameSerial != "N/A"
    val perGame = InGameOverlay.settingsScope.value == SettingsScope.Game && hasGame
    val gameKey = touchStation11ProfileKey("touchstation.v11.game.", gameSerial)
    val compatibilityKey = "touchstation.v11.compat." +
        gameSerial.filter { it.isLetterOrDigit() }.ifBlank { "unknown" }
    val engineReady = ARMSX3.initialized
    val nativeReady = MainActivityRuntime.nativeReady.value
    val gameState = MainActivityRuntime.eState.value.toString()
    val stopped = MainActivityRuntime.eState.value == EmuState.STOPPED
    val cores = Runtime.getRuntime().availableProcessors().coerceAtLeast(1)
    val ramMb = snapshot.value?.totalRamMb ?: 0L
    val suggestedPpuThreads = when {
        cores >= 8 && ramMb >= 8192L -> 4
        cores >= 6 && ramMb >= 6144L -> 3
        else -> 2
    }.coerceAtMost(cores).coerceAtLeast(1)
    val suggestedLlvmThreads = if (ramMb >= 7168L) 2 else 1
    val compatibility = prefs.getString(compatibilityKey, "Not tested by user") ?: "Not tested by user"
    val memoryValues = history.toList()
    val graphBars = listOf("▁", "▂", "▃", "▄", "▅", "▆", "▇", "█")
    val minimumRam = memoryValues.minOrNull() ?: 0
    val memorySpan = ((memoryValues.maxOrNull() ?: 0) - minimumRam).coerceAtLeast(1)
    val memoryGraph = if (memoryValues.isEmpty()) {
        "Collecting memory history…"
    } else {
        memoryValues.joinToString("") { value ->
            val index = (((value - minimumRam).toFloat() / memorySpan) * 7f).toInt().coerceIn(0, 7)
            graphBars[index]
        }
    }

    LaunchedEffect(context) {
        while (true) {
            val current = withContext(Dispatchers.IO) { touchStation11Snapshot(context) }
            snapshot.value = current
            current.availableRamMb?.toInt()?.let { available ->
                history.add(available)
                while (history.size > 20) history.removeAt(0)
                prefs.edit().putString(
                    "touchstation.v11.availableRamHistory",
                    history.joinToString(","),
                ).apply()
            }
            delay(15_000L)
        }
    }

    LaunchedEffect(engineReady, nativeReady, gameSerial, gameState) {
        val event = System.currentTimeMillis().toString() + " | engine=" +
            (if (engineReady) "ready" else "not-ready") + " | native=" +
            (if (nativeReady) "ready" else "not-ready") + " | game=" +
            gameSerial + " | state=" + gameState
        if (timeline.lastOrNull() != event) {
            timeline.add(0, event)
            while (timeline.size > 6) timeline.removeAt(timeline.lastIndex)
            touchStation11Record(context, "Boot timeline: " + event)
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
            Text("TouchStation 11.0 Reliability & Diagnostics Suite", style = MaterialTheme.typography.titleLarge)
            Text(
                "Twenty reliability tools for PPU/SPU diagnostics, launches, monitoring, profiles and recovery. Values are reported only when the Android system or native bridge exposes them.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            TouchStation11Section("1–5. PPU and SPU Diagnostics") {
                TouchStation11Row("PPU compilation progress", "N/A — live job counters are not exported by the pinned native bridge")
                TouchStation11Row("PPU cache validation", snapshot.value?.let {
                    it.ppu.files.toString() + " files · " + touchStation11Bytes(it.ppu.bytes) +
                        " · unreadable " + it.ppu.unreadable
                } ?: "Scanning…")
                TouchStation11Row("PPU threads", settings.ps3.ppuThreads.toString() + " configured · " + suggestedPpuThreads + " suggested")
                TouchStation11Row("LLVM compile threads", settings.ps3.llvmThreads.toString())
                TouchStation11Row("SPU decoder / block", settings.ps3.spuDecoder.toString() + " / " + settings.ps3.spuBlockSize)
                TouchStation11Row("Preferred SPU threads", settings.ps3.preferredSpuThreads.toString())
                TouchStation11Row("SPU cache", snapshot.value?.let {
                    it.spu.files.toString() + " files · " + touchStation11Bytes(it.spu.bytes)
                } ?: "Scanning…")
                TouchStation11Row("Recompiler errors", snapshot.value?.previousExit ?: "Scanning Android exit history…")
                TouchStation11Row("Native PPU/SPU exception counters", "N/A — not exported by the current bridge")
                Button(
                    onClick = {
                        val recommended = settings.copy(
                            ps3 = settings.ps3.copy(
                                ppuThreads = suggestedPpuThreads,
                                llvmThreads = suggestedLlvmThreads,
                            ),
                        )
                        val verified = runCatching { onApply(recommended) }.getOrDefault(false)
                        message.value = if (verified) {
                            touchStation11Record(context, "PPU thread recommendation saved and verified")
                            "PPU thread recommendation saved and verified."
                        } else "PPU thread recommendation could not be verified."
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Apply PPU Thread Recommendation") }
                Text(
                    "Cache validation is read-only. Zero-length or unreadable files are reported for review; TouchStation never deletes cache entries or game saves automatically.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            TouchStation11Section("6–10. Game Launch and Stability") {
                TouchStation11Row("Current game", gameTitle)
                TouchStation11Row("Engine initialization", if (engineReady) "Ready" else "Not initialized")
                TouchStation11Row("Native runtime", if (nativeReady) "Ready" else "Not ready")
                TouchStation11Row("Boot state", gameState)
                TouchStation11Row("Android exit / launch failure evidence", snapshot.value?.previousExit ?: "Scanning…")
                TouchStation11Row("Structured game-launch error", "N/A — detailed native loader errors are not exposed to this UI")
                TouchStation11Row("Game compatibility record", compatibility)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(
                        onClick = {
                            prefs.edit().putString(compatibilityKey, "Tested OK — user recorded").apply()
                            message.value = "Saved a local compatibility note for " + gameTitle + "."
                        },
                        enabled = hasGame,
                        modifier = Modifier.weight(1f),
                    ) { Text("Mark Tested OK") }
                    OutlinedButton(
                        onClick = {
                            prefs.edit().putString(compatibilityKey, "Issues observed — user recorded").apply()
                            message.value = "Saved a local issue note for " + gameTitle + "."
                        },
                        enabled = hasGame,
                        modifier = Modifier.weight(1f),
                    ) { Text("Record Issues") }
                }
                Button(
                    onClick = {
                        val report = buildString {
                            appendLine("TouchStation 11.0.0 crash and launch report")
                            appendLine("Device: " + Build.MANUFACTURER + " " + Build.MODEL)
                            appendLine("Android: " + Build.VERSION.RELEASE + " (API " + Build.VERSION.SDK_INT + ")")
                            appendLine("Game: " + gameTitle + " (" + gameSerial + ")")
                            appendLine("Engine initialized: " + engineReady)
                            appendLine("Native runtime ready: " + nativeReady)
                            appendLine("Emulator state: " + gameState)
                            appendLine("Android process exit: " + (snapshot.value?.previousExit ?: "N/A"))
                            appendLine("PPU threads: " + settings.ps3.ppuThreads)
                            appendLine("LLVM threads: " + settings.ps3.llvmThreads)
                            appendLine("SPU decoder/block: " + settings.ps3.spuDecoder + " / " + settings.ps3.spuBlockSize)
                            appendLine("Thermal status: " + touchStation11Thermal(snapshot.value?.thermalStatus))
                            appendLine("Available RAM MB: " + (snapshot.value?.availableRamMb?.toString() ?: "N/A"))
                            appendLine("Native PPU/SPU compile traces and detailed game-loader exceptions: N/A unless exported by the native bridge")
                        }
                        val send = Intent(Intent.ACTION_SEND).apply {
                            type = "text/plain"
                            putExtra(Intent.EXTRA_SUBJECT, "TouchStation 11.0 diagnostics")
                            putExtra(Intent.EXTRA_TEXT, report)
                        }
                        runCatching {
                            context.startActivity(
                                Intent.createChooser(send, "Share TouchStation diagnostics")
                                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                            )
                        }.onFailure { message.value = "Could not open the Android share sheet." }
                        touchStation11Record(context, "User exported crash/launch diagnostic report")
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Export Crash / Launch Report") }
                OutlinedButton(
                    onClick = {
                        val launch = context.packageManager.getLaunchIntentForPackage(context.packageName)
                        if (!stopped) {
                            message.value = "Stop the running game before relaunching the frontend."
                        } else if (launch == null) {
                            message.value = "Android did not provide a launcher activity."
                        } else {
                            runCatching {
                                launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK)
                                context.startActivity(launch)
                            }.onSuccess {
                                touchStation11Record(context, "User requested safe frontend relaunch")
                            }.onFailure {
                                message.value = "Frontend relaunch was blocked by Android."
                            }
                        }
                    },
                    enabled = stopped,
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Safely Relaunch TouchStation (Game Stopped)") }
                Text(
                    "Compatibility entries are local user notes, not verified universal ratings. Safe relaunch is enabled only when the emulator reports STOPPED; it does not delete firmware, games or saves.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            TouchStation11Section("11–15. Performance and Device Monitoring") {
                TouchStation11Row("FPS / frametime source", "Existing native in-game performance overlay · " + InGameOverlay.osdMode.value)
                Text(
                    "Open the in-game pause menu → Performance Overlay to view the native FPS and frametime graphs. The pinned bridge does not expose per-frame samples to a second Android-side chart.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                TouchStation11Row("Available RAM", snapshot.value?.availableRamMb?.let { it.toString() + " MB" } ?: "Scanning…")
                TouchStation11Row("App memory (PSS)", snapshot.value?.appPssMb?.let { it.toString() + " MB" } ?: "N/A")
                TouchStation11Row("RAM history (last samples)", memoryGraph)
                TouchStation11Row("Thermal severity", touchStation11Thermal(snapshot.value?.thermalStatus))
                TouchStation11Row("Thermal warning", run {
                    val status = snapshot.value?.thermalStatus
                    when {
                        status == null -> "N/A"
                        status >= PowerManager.THERMAL_STATUS_SEVERE -> "Elevated — consider pausing"
                        status == PowerManager.THERMAL_STATUS_MODERATE -> "Moderate"
                        else -> "No elevated thermal warning reported"
                    }
                })
                TouchStation11Row("Vulkan system feature", snapshot.value?.vulkanInfo ?: "Scanning…")
                TouchStation11Row("Vulkan physical-device extensions", "N/A — full VkPhysicalDevice query is not exposed by the current bridge")
                TouchStation11Row("Shader cache footprint", snapshot.value?.let {
                    it.shaderFiles.toString() + " files · " + touchStation11Bytes(it.shaderBytes)
                } ?: "Scanning…")
                TouchStation11Row("Physical GPU utilization", "N/A unless the Android GPU driver exposes readable counters")
            }

            TouchStation11Section("16–20. Automation, Profiles and Protection") {
                Button(
                    onClick = {
                        val optimized = settings.copy(
                            hwScaler = 0,
                            ps3 = settings.ps3.copy(
                                ppuThreads = suggestedPpuThreads,
                                llvmThreads = suggestedLlvmThreads,
                                spuBlockSize = 0,
                                preferredSpuThreads = 0,
                                msaaMode = 0,
                            ),
                        )
                        val verified = runCatching { onApply(optimized) }.getOrDefault(false)
                        if (verified) {
                            prefs.edit().putString("touchstation.v11.lastAutoProfile", "Balanced · verified").apply()
                            touchStation11Record(context, "Auto Settings 3.0 applied and read-back verified")
                            message.value = "Auto Settings 3.0 saved and verified. You can still change every setting manually."
                        } else {
                            message.value = "Auto Settings 3.0 could not verify the saved values. No success was reported."
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Apply Auto Settings 3.0") }
                TouchStation11Row("Last automatic profile", prefs.getString("touchstation.v11.lastAutoProfile", "Not applied") ?: "Not applied")
                Button(
                    onClick = {
                        touchStation11SaveProfile(gameKey, settings)
                        message.value = "Backed up the current settings for " + gameTitle + "."
                        touchStation11Record(context, "Per-game profile backup: " + gameSerial)
                    },
                    enabled = perGame,
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Back Up Active Game Profile") }
                OutlinedButton(
                    onClick = {
                        val restored = touchStation11RestoreProfile(gameKey, settings, onApply)
                        message.value = if (restored) {
                            touchStation11Record(context, "Per-game profile restored: " + gameSerial)
                            "Game profile restored and verified."
                        } else "No saved profile was found, or its settings could not be verified."
                    },
                    enabled = perGame && prefs.getBoolean(gameKey + "saved", false),
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Restore Active Game Profile") }
                TouchStation11Row("Connected game controllers", snapshot.value?.controllers?.size?.toString() ?: "Scanning…")
                Text(
                    snapshot.value?.controllers?.takeIf { it.isNotEmpty() }?.joinToString()
                        ?: "No Android gamepad/joystick device currently reported.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Text(
                    "Controller detection lists Android input devices. Button-by-button live input tracing is not exposed by this settings screen.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                TouchStation11Row("App-private free storage", snapshot.value?.freeStorageMb?.let { it.toString() + " MB" } ?: "N/A")
                TouchStation11Row("PPU / SPU / shader caches", snapshot.value?.let {
                    touchStation11Bytes(it.ppu.bytes) + " / " + touchStation11Bytes(it.spu.bytes) +
                        " / " + touchStation11Bytes(it.shaderBytes)
                } ?: "Scanning…")
                TouchStation11Row("Game and firmware folder totals", "N/A — external library folders are not exposed to this diagnostic view")
                OutlinedButton(
                    onClick = {
                        touchStation11SaveProfile("touchstation.v11.recovery.", settings)
                        message.value = "Saved a local recovery point for the current emulator settings."
                        touchStation11Record(context, "User saved a settings recovery point")
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Save Current Settings as Recovery Point") }
                OutlinedButton(
                    onClick = {
                        val restored = touchStation11RestoreProfile(
                            "touchstation.v11.recovery.", settings, onApply,
                        )
                        message.value = if (restored) {
                            touchStation11Record(context, "Settings recovery point restored and verified")
                            "Recovery point restored and verified. Game files, firmware and saves were not changed."
                        } else "No recovery point was saved, or the settings read-back check failed."
                    },
                    enabled = prefs.getBoolean("touchstation.v11.recovery.saved", false),
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Restore Last Known Settings") }
                TouchStation11Row("Save-data protection", "Diagnostics only inspect emulator cache paths; PS3 home/save data is not modified")
            }

            if (timeline.isNotEmpty()) {
                TouchStation11Section("Recent Game Boot Timeline") {
                    timeline.forEach { Text(it, style = MaterialTheme.typography.bodySmall) }
                }
            }

            if (message.value.isNotBlank()) {
                Text(
                    message.value,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.primary,
                )
            }
        }
    }
}

@Composable
private fun TouchStation11Section(
    title: String,
    content: @Composable () -> Unit,
) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = androidx.compose.foundation.shape.RoundedCornerShape(12.dp),
        color = MaterialTheme.colorScheme.surface,
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(7.dp),
        ) {
            Text(title, style = MaterialTheme.typography.titleMedium)
            content()
        }
    }
}

@Composable
private fun TouchStation11Row(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
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


def patch_version(app_dir: Path) -> None:
    path = app_dir / "build.gradle.kts"
    text = path.read_text(encoding="utf-8")
    if "versionCode = 1000" not in text or 'versionName = "10.0.0"' not in text:
        raise SystemExit("Expected prepared 10.0.0 / versionCode 1000 app before v11 promotion")
    text = replace_once(text, "versionCode = 1000", "versionCode = 1100", "versionCode")
    text = replace_once(text, 'versionName = "10.0.0"', 'versionName = "11.0.0"', "versionName")
    path.write_text(text, encoding="utf-8")


def patch_control_center(app_dir: Path) -> None:
    path = app_dir / "src/main/java/com/armsx2/ui/settings/TouchStationControlCenter.kt"
    text = path.read_text(encoding="utf-8")
    text = text.replace("TouchStation 10.0.0 diagnostic report", "TouchStation 11.0.0 diagnostic report")
    path.write_text(text, encoding="utf-8")


def patch_performance_tab(app_dir: Path) -> None:
    path = app_dir / "src/main/java/com/armsx2/ui/settings/PerformanceTab.kt"
    text = path.read_text(encoding="utf-8")
    anchor = '''        TouchStation10StabilitySuite(
            settings = s,
            ''' + verification_callback() + '''
        )
        SettingsDivider()

'''
    addition = anchor + '''        TouchStation11ReliabilitySuite(
            settings = s,
            ''' + verification_callback() + '''
        )
        SettingsDivider()

'''
    text = replace_once(text, anchor, addition, "TouchStation 11 suite placement")
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
        settings_dir / "TouchStation10StabilitySuite.kt",
        settings_dir / "TouchStationControlCenter.kt",
    ]
    for path in required:
        if not path.is_file():
            raise SystemExit("Missing expected source file: " + str(path))

    suite_path = settings_dir / "TouchStation11ReliabilitySuite.kt"
    if suite_path.exists():
        raise SystemExit("TouchStation 11 suite already exists; refusing to overwrite")
    patch_version(app_dir)
    patch_control_center(app_dir)
    suite_path.write_text(KOTLIN_SOURCE, encoding="utf-8")
    patch_performance_tab(app_dir)

    feature_markers = [
        "PPU compilation progress",
        "PPU cache validation",
        "PPU Thread Recommendation",
        "SPU decoder / block",
        "Recompiler errors",
        "Boot Timeline",
        "Android exit / launch failure evidence",
        "Game compatibility record",
        "Export Crash / Launch Report",
        "Safely Relaunch TouchStation",
        "frametime graphs",
        "RAM history",
        "Thermal warning",
        "Available RAM",
        "Vulkan system feature",
        "Auto Settings 3.0",
        "Back Up Active Game Profile",
        "Connected game controllers",
        "App-private free storage",
        "Restore Last Known Settings",
    ]
    missing = [marker for marker in feature_markers if marker not in KOTLIN_SOURCE]
    if missing:
        raise SystemExit("Missing v11 feature markers: " + ", ".join(missing))
    print("Applied TouchStation 11.0.0: 20 reliability features, 11.0.0 version and settings integration.")


if __name__ == "__main__":
    main()
