#!/usr/bin/env python3
"""Add the TouchStation Version Finale compatibility, device and GTA IV tools."""
from __future__ import annotations

import argparse
from pathlib import Path

KOTLIN_SOURCE = r'''package com.armsx2.ui.settings

import android.app.ActivityManager
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.Debug
import android.os.PowerManager
import android.os.StatFs
import android.view.InputDevice
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.edit
import com.armsx2.GameInfo
import com.armsx2.GamePlatform
import com.armsx2.data.library.GameLibraryRepository
import com.armsx2.config.Settings
import com.armsx2.config.SettingsScope
import com.armsx2.runtime.MainActivityRuntime
import com.armsx2.ui.InGameOverlay
import com.armsx3.HttpClient
import com.armsx3.core.ARMSX3
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File
import java.util.Locale

private const val TOUCHSTATION_FINALE_COMPAT_URL =
    "https://rpcs3.net/compatibility/?api=v1&export"
private const val TOUCHSTATION_FINALE_COMPAT_FILE = "touchstation-finale-compatibility.json"
private const val TOUCHSTATION_FINALE_COMPAT_SYNC_KEY = "touchstation.finale.compatLastSync"

/**
 * Shared exact-ID compatibility cache used by the settings centre and game-library tiles.
 * The displayed statuses are desktop RPCS3 references, not device-specific results.
 */
object TouchStationFinaleCompatibilityStore {
    val revision = mutableIntStateOf(0)
    private val statusById = mutableStateMapOf<String, String>()

    fun replace(database: JSONObject?) {
        statusById.clear()
        val results = database?.optJSONObject("results")
        if (results != null) {
            val keys = results.keys()
            while (keys.hasNext()) {
                val id = keys.next()
                val status = results.optJSONObject(id)?.optString("status")?.takeIf { it.isNotBlank() }
                if (status != null) {
                    statusById[touchStationFinaleNormaliseId(id)] = status
                }
            }
        }
        revision.intValue++
    }

    fun statusFor(serial: String?): String? {
        revision.intValue
        if (serial.isNullOrBlank()) return null
        return statusById[touchStationFinaleNormaliseId(serial)]
    }

    fun rankFor(serial: String?): Int? = when (statusFor(serial)?.lowercase(Locale.ROOT)) {
        "playable" -> 5
        "ingame" -> 4
        "intro" -> 3
        "loadable" -> 2
        "nothing" -> 1
        "unplayable" -> 0
        else -> null
    }

    suspend fun loadCache(context: Context) {
        replace(withContext(Dispatchers.IO) { touchStationFinaleReadCache(context) })
    }
}

private data class TouchStationFinaleDevice(
    val totalRamMb: Long?,
    val availableRamMb: Long?,
    val appPssMb: Int?,
    val freeStorageMb: Long?,
    val thermalStatus: Int?,
    val controllers: List<String>,
    val cpuCores: Int,
    val device: String,
    val soc: String,
    val abi: String,
)

private fun touchStationFinaleNormaliseId(value: String): String =
    value.filter { it.isLetterOrDigit() }.uppercase(Locale.ROOT)

private fun touchStationFinaleOfficialEntry(
    database: JSONObject?,
    serial: String?,
): JSONObject? {
    if (database == null || serial.isNullOrBlank()) return null
    val results = database.optJSONObject("results") ?: return null
    val wanted = touchStationFinaleNormaliseId(serial)
    if (wanted.isBlank()) return null
    val keys = results.keys()
    while (keys.hasNext()) {
        val key = keys.next()
        if (touchStationFinaleNormaliseId(key) == wanted) {
            return results.optJSONObject(key)
        }
    }
    return null
}

private fun touchStationFinaleReadCache(context: Context): JSONObject? =
    runCatching {
        val file = File(context.filesDir, TOUCHSTATION_FINALE_COMPAT_FILE)
        if (!file.isFile || file.length() <= 0L || file.length() > 32L * 1024L * 1024L) {
            null
        } else {
            JSONObject(file.readText(Charsets.UTF_8)).takeIf { it.optInt("return_code", -1) == 0 }
        }
    }.getOrNull()

private suspend fun touchStationFinaleFetchCompatibility(context: Context): Pair<JSONObject?, String> =
    withContext(Dispatchers.IO) {
        runCatching {
            val response = HttpClient.doRequest(
                url = TOUCHSTATION_FINALE_COMPAT_URL,
                userAgent = "TouchStation-Version-Finale/1.0",
                timeoutMs = 30_000,
            )
            if (response.statusCode !in 200..299) {
                error("Compatibility service returned HTTP " + response.statusCode)
            }
            if (response.data.isEmpty() || response.data.size > 32 * 1024 * 1024) {
                error("Compatibility database response was empty or exceeded the 32 MB safety limit")
            }
            val payload = JSONObject(response.data.toString(Charsets.UTF_8))
            if (payload.optInt("return_code", -1) != 0 || payload.optJSONObject("results") == null) {
                error("Compatibility service returned an invalid database response")
            }
            val target = File(context.filesDir, TOUCHSTATION_FINALE_COMPAT_FILE)
            val temporary = File(context.filesDir, TOUCHSTATION_FINALE_COMPAT_FILE + ".tmp")
            temporary.writeText(payload.toString(), Charsets.UTF_8)
            if (!temporary.renameTo(target)) {
                target.writeText(payload.toString(), Charsets.UTF_8)
                temporary.delete()
            }
            MainActivityRuntime.prefs.edit()
                .putLong(TOUCHSTATION_FINALE_COMPAT_SYNC_KEY, System.currentTimeMillis())
                .apply()
            payload to "Official compatibility database updated."
        }.getOrElse { null to ("Update failed: " + (it.message ?: "network or data error")) }
    }

private fun touchStationFinaleDeviceSnapshot(context: Context): TouchStationFinaleDevice {
    val manager = context.getSystemService(Context.ACTIVITY_SERVICE) as? ActivityManager
    val memory = ActivityManager.MemoryInfo()
    runCatching { manager?.getMemoryInfo(memory) }
    val pss = runCatching {
        val info = Debug.MemoryInfo()
        Debug.getMemoryInfo(info)
        info.totalPss.takeIf { it > 0 }?.div(1024)
    }.getOrNull()
    val thermal = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
        runCatching {
            (context.getSystemService(Context.POWER_SERVICE) as? PowerManager)?.currentThermalStatus
        }.getOrNull()
    } else null
    val freeStorage = runCatching {
        StatFs(context.filesDir.absolutePath).availableBytes / (1024L * 1024L)
    }.getOrNull()
    val controllers = runCatching {
        InputDevice.getDeviceIds().toList().mapNotNull { id: Int ->
            val device = InputDevice.getDevice(id)
            if (device == null) null else {
                val gamepad = (device.sources and InputDevice.SOURCE_GAMEPAD) == InputDevice.SOURCE_GAMEPAD
                val joystick = (device.sources and InputDevice.SOURCE_JOYSTICK) == InputDevice.SOURCE_JOYSTICK
                if (gamepad || joystick) device.name else null
            }
        }.distinct()
    }.getOrDefault(emptyList())
    val soc = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
        listOf(Build.SOC_MANUFACTURER, Build.SOC_MODEL)
            .filter { it.isNotBlank() }.joinToString(" ").ifBlank { "N/A" }
    } else {
        Build.HARDWARE.ifBlank { "N/A" }
    }
    return TouchStationFinaleDevice(
        totalRamMb = memory.totalMem.takeIf { it > 0L }?.div(1024L * 1024L),
        availableRamMb = memory.availMem.takeIf { it > 0L }?.div(1024L * 1024L),
        appPssMb = pss,
        freeStorageMb = freeStorage,
        thermalStatus = thermal,
        controllers = controllers,
        cpuCores = Runtime.getRuntime().availableProcessors().coerceAtLeast(1),
        device = Build.MANUFACTURER + " " + Build.MODEL,
        soc = soc,
        abi = Build.SUPPORTED_ABIS.firstOrNull() ?: "N/A",
    )
}

private fun touchStationFinaleThermal(status: Int?): String = when (status) {
    null -> "N/A — thermal status not exposed"
    PowerManager.THERMAL_STATUS_NONE -> "Normal"
    PowerManager.THERMAL_STATUS_LIGHT -> "Light"
    PowerManager.THERMAL_STATUS_MODERATE -> "Moderate"
    PowerManager.THERMAL_STATUS_SEVERE -> "Severe"
    PowerManager.THERMAL_STATUS_CRITICAL -> "Critical"
    PowerManager.THERMAL_STATUS_EMERGENCY -> "Emergency"
    PowerManager.THERMAL_STATUS_SHUTDOWN -> "Shutdown"
    else -> "Unknown (" + status + ")"
}

private fun touchStationFinaleMemory(value: Long?): String =
    value?.let { String.format(Locale.US, "%.0f MB", it.toFloat()) } ?: "N/A"

private fun touchStationFinaleDeviceKey(serial: String, device: TouchStationFinaleDevice): String {
    val game = touchStationFinaleNormaliseId(serial).ifBlank { "unknown" }
    val handset = touchStationFinaleNormaliseId(device.device).take(48).ifBlank { "device" }
    val abi = touchStationFinaleNormaliseId(device.abi)
    return "touchstation.finale.local.$game.$handset.$abi"
}

private fun touchStationFinaleGtaIv(title: String): Boolean {
    val normalized = title.lowercase(Locale.ROOT)
    return normalized.contains("grand theft auto iv") ||
        Regex("""\bgta\s*iv\b""", RegexOption.IGNORE_CASE).containsMatchIn(title)
}

private fun touchStationFinaleShareReport(context: Context, report: String) {
    runCatching {
        val intent = Intent(Intent.ACTION_SEND).apply {
            type = "text/plain"
            putExtra(Intent.EXTRA_SUBJECT, "TouchStation Version Finale diagnostic report")
            putExtra(Intent.EXTRA_TEXT, report)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        context.startActivity(Intent.createChooser(intent, "Share diagnostic report").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    }
}

@Composable
private fun TouchStationFinaleRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
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

@Composable
private fun TouchStationFinaleSection(title: String, content: @Composable () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(title, style = MaterialTheme.typography.titleMedium)
        content()
    }
}

@Composable
fun TouchStationFinaleSuite(
    settings: Settings,
    onApply: (Settings) -> Boolean,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val device = remember { mutableStateOf<TouchStationFinaleDevice?>(null) }
    val database = remember { mutableStateOf<JSONObject?>(null) }
    val libraryGames = remember { mutableStateOf<List<GameInfo>>(emptyList()) }
    val librarySearch = remember { mutableStateOf("") }
    val busy = remember { mutableStateOf(false) }
    val message = remember { mutableStateOf("Compatibility data has not been refreshed in this session.") }
    val game: GameInfo? = MainActivityRuntime.currentGame.value
    val gameTitle = game?.title?.takeIf { it.isNotBlank() } ?: "No game selected"
    val serial = game?.serial?.takeIf { it.isNotBlank() }
        ?: game?.settingsKey?.takeIf { it.isNotBlank() }
    val settingsArePerGame = InGameOverlay.settingsScope.value == SettingsScope.Game
    val isGtaIv = touchStationFinaleGtaIv(gameTitle)
    val officialEntry = touchStationFinaleOfficialEntry(database.value, serial)
    val officialStatus = officialEntry?.optString("status")?.takeIf { it.isNotBlank() } ?: "Not found in cached official database"
    val officialDate = officialEntry?.optString("date")?.takeIf { it.isNotBlank() } ?: "N/A"
    val officialUpdate = officialEntry?.optString("update")?.takeIf { it.isNotBlank() } ?: "N/A"
    val prefs = MainActivityRuntime.prefs
    val deviceSnapshot = device.value
    val syncTime = prefs.getLong(TOUCHSTATION_FINALE_COMPAT_SYNC_KEY, 0L)
    val localKey = serial?.let { currentSerial ->
        deviceSnapshot?.let { touchStationFinaleDeviceKey(currentSerial, it) }
    }
    val localStatus = localKey?.let { prefs.getString(it, "Not tested on this device") }
        ?: "Select a game with a title ID to record a test"
    val engineReady = ARMSX3.initialized
    val nativeReady = MainActivityRuntime.nativeReady.value

    LaunchedEffect(context) {
        device.value = withContext(Dispatchers.IO) { touchStationFinaleDeviceSnapshot(context) }
        database.value = withContext(Dispatchers.IO) { touchStationFinaleReadCache(context) }
        TouchStationFinaleCompatibilityStore.replace(database.value)
        libraryGames.value = withContext(Dispatchers.IO) {
            runCatching {
                GameLibraryRepository(context).loadCached().games
                    .filter { it.platform == GamePlatform.PS3 && !it.serial.isNullOrBlank() }
                    .distinctBy { touchStationFinaleNormaliseId(it.serial.orEmpty()) }
                    .sortedBy { it.title.lowercase(Locale.ROOT) }
            }.getOrDefault(emptyList())
        }
    }

    val report = buildString {
        appendLine("TouchStation Version Finale diagnostic report")
        appendLine("Device: " + (deviceSnapshot?.device ?: "N/A"))
        appendLine("SoC: " + (deviceSnapshot?.soc ?: "N/A"))
        appendLine("Android: " + Build.VERSION.RELEASE + " (API " + Build.VERSION.SDK_INT + ")")
        appendLine("ABI: " + (deviceSnapshot?.abi ?: "N/A"))
        appendLine("CPU cores: " + (deviceSnapshot?.cpuCores?.toString() ?: "N/A"))
        appendLine("Total RAM: " + touchStationFinaleMemory(deviceSnapshot?.totalRamMb))
        appendLine("Available RAM: " + touchStationFinaleMemory(deviceSnapshot?.availableRamMb))
        appendLine("App PSS: " + (deviceSnapshot?.appPssMb?.toString() ?: "N/A") + " MB")
        appendLine("Free app-private storage: " + (deviceSnapshot?.freeStorageMb?.toString() ?: "N/A") + " MB")
        appendLine("Thermal status: " + touchStationFinaleThermal(deviceSnapshot?.thermalStatus))
        appendLine("Physical controllers: " + (deviceSnapshot?.controllers?.joinToString().orEmpty().ifBlank { "None detected" }))
        appendLine("PS3 engine initialized: " + engineReady)
        appendLine("Native runtime ready: " + nativeReady)
        appendLine("Game: " + gameTitle)
        appendLine("Game ID: " + (serial ?: "N/A"))
        appendLine("Official PC compatibility: " + officialStatus)
        appendLine("Official test date: " + officialDate)
        appendLine("Local device test: " + localStatus)
        appendLine("PPU decoder: " + settings.ps3.ppuDecoder)
        appendLine("PPU threads: " + settings.ps3.ppuThreads)
        appendLine("LLVM threads: " + settings.ps3.llvmThreads)
        appendLine("SPU decoder: " + settings.ps3.spuDecoder)
        appendLine("SPU block size: " + settings.ps3.spuBlockSize)
        appendLine("SPU XFloat accuracy: " + settings.ps3.spuXFloat)
        appendLine("Shader mode: " + settings.ps3.shaderMode)
        appendLine("MSAA: " + settings.ps3.msaaMode)
        appendLine("The official compatibility result is for the desktop emulator and is not a device-specific guarantee.")
        appendLine("FPS and frametime are supplied only by the native in-game overlay when available.")
    }

    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(18.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("TouchStation Version Finale", style = MaterialTheme.typography.titleLarge)
            Text(
                "Compatibility intelligence, per-device testing, safe game profiles and a full device-readiness panel. Native metrics are shown only when the operating system or emulator exposes them.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            TouchStationFinaleSection("01 · Official game compatibility") {
                TouchStationFinaleRow("Current game", gameTitle)
                TouchStationFinaleRow("Game ID", serial ?: "N/A — exact ID required")
                TouchStationFinaleRow("RPCS3 desktop status", officialStatus)
                TouchStationFinaleRow("Last official test date", officialDate)
                TouchStationFinaleRow("Latest update", officialUpdate)
                TouchStationFinaleRow(
                    "Database cache",
                    if (syncTime > 0L) "Updated " + android.text.format.DateFormat.format("yyyy-MM-dd HH:mm", syncTime)
                    else "Not downloaded yet",
                )
                Button(
                    onClick = {
                        if (!busy.value) {
                            scope.launch {
                                busy.value = true
                                val result = touchStationFinaleFetchCompatibility(context)
                                if (result.first != null) {
                                    database.value = result.first
                                    TouchStationFinaleCompatibilityStore.replace(result.first)
                                }
                                message.value = result.second
                                busy.value = false
                            }
                        }
                    },
                    enabled = !busy.value,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(if (busy.value) "Updating compatibility database…" else "Update official compatibility database")
                }
                Text(
                    message.value + " Matching uses the exact normalized PS3 title ID, never a guessed title-name match. Official status is a desktop RPCS3 reference, not a promise that this Android device can run the game.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            TouchStationFinaleSection("02 · Full library compatibility index") {
                Text(
                    "Search the cached PS3 library by title or exact title ID. Each row is matched against the official compatibility database by normalized ID, not approximate title text.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                OutlinedTextField(
                    value = librarySearch.value,
                    onValueChange = { librarySearch.value = it },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    label = { Text("Search PS3 library") },
                )
                val query = librarySearch.value.trim().lowercase(Locale.ROOT)
                val matches = libraryGames.value.filter { item ->
                    query.isBlank() ||
                        item.title.lowercase(Locale.ROOT).contains(query) ||
                        item.serial.orEmpty().lowercase(Locale.ROOT).contains(query)
                }.take(40)
                if (matches.isEmpty()) {
                    Text(
                        if (libraryGames.value.isEmpty()) "No cached PS3 library entries yet. Scan your game folders in the library first."
                        else "No matching game in the cached PS3 library.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                } else {
                    matches.forEach { item ->
                        val entry = touchStationFinaleOfficialEntry(database.value, item.serial)
                        TouchStationFinaleRow(
                            item.title,
                            (item.serial ?: "No title ID") + " · " +
                                (entry?.optString("status")?.takeIf { it.isNotBlank() } ?: "No official entry"),
                        )
                    }
                }
                Text(
                    "Showing up to 40 matches. Download or refresh the official database above to populate status results. No untested title is labelled playable.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            TouchStationFinaleSection("03 · Your device test record") {
                TouchStationFinaleRow("This device's result", localStatus)
                Text(
                    "Record only what you personally observed on this handset and TouchStation build. This stays on this device and is separate from the official desktop compatibility database.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                val stages = listOf(
                    "Booted successfully",
                    "Reached main menu",
                    "Reached gameplay",
                    "Stable session (10+ min)",
                    "Failed to boot / crashed",
                )
                stages.chunked(2).forEach { group ->
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        group.forEach { stage ->
                            OutlinedButton(
                                onClick = {
                                    localKey?.let { key ->
                                        prefs.edit().putString(
                                            key,
                                            stage + " · " + android.text.format.DateFormat.format("yyyy-MM-dd HH:mm", System.currentTimeMillis()),
                                        ).apply()
                                        message.value = "Saved this device's local test record."
                                    }
                                },
                                enabled = localKey != null,
                                modifier = Modifier.weight(1f),
                            ) {
                                Text(stage, style = MaterialTheme.typography.labelSmall)
                            }
                        }
                        if (group.size == 1) {
                            androidx.compose.foundation.layout.Spacer(Modifier.weight(1f))
                        }
                    }
                }
            }

            TouchStationFinaleSection("04 · GTA IV compatibility profile") {
                TouchStationFinaleRow("Game detected", if (isGtaIv) "Grand Theft Auto IV" else "Not the selected game")
                TouchStationFinaleRow("Settings scope", if (settingsArePerGame) "Per-game" else "Global")
                Text(
                    "The conservative profile selects safe SPU block mode, accurate SPU XFloat, asynchronous shader recompilation, MSAA off, cached SPU code, precompilation and restrained LLVM/PPU thread counts. It does not add missing native core features or guarantee GTA IV will boot or run smoothly.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Button(
                    onClick = {
                        val cores = Runtime.getRuntime().availableProcessors().coerceAtLeast(1)
                        val configured = settings.copy(
                            ps3 = settings.ps3.copy(
                                ppuThreads = minOf(2, cores).coerceAtLeast(1),
                                llvmThreads = 1,
                                preferredSpuThreads = 0,
                                spuBlockSize = 0,
                                spuXFloat = 0,
                                shaderMode = 1,
                                msaaMode = 0,
                                spuCache = true,
                                llvmPrecompile = true,
                            ),
                        )
                        val saved = runCatching { onApply(configured) }.getOrDefault(false)
                        message.value = if (saved) {
                            "GTA IV conservative settings were saved and read back. Test the game and report the result separately."
                        } else {
                            "Settings could not be verified. No successful profile application is claimed."
                        }
                    },
                    enabled = isGtaIv && settingsArePerGame && game != null,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("Apply GTA IV per-game profile")
                }
                Text(
                    "This button is enabled only for a detected GTA IV title while the per-game settings scope is active. It changes existing supported settings only and leaves your global profile untouched.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            TouchStationFinaleSection("05 · Device readiness and system checks") {
                TouchStationFinaleRow("Device", deviceSnapshot?.device ?: "Scanning…")
                TouchStationFinaleRow("SoC", deviceSnapshot?.soc ?: "Scanning…")
                TouchStationFinaleRow("Android / ABI", Build.VERSION.RELEASE + " / " + (deviceSnapshot?.abi ?: "N/A"))
                TouchStationFinaleRow("Available CPU cores", deviceSnapshot?.cpuCores?.toString() ?: "N/A")
                TouchStationFinaleRow("Total / available RAM", touchStationFinaleMemory(deviceSnapshot?.totalRamMb) + " / " + touchStationFinaleMemory(deviceSnapshot?.availableRamMb))
                TouchStationFinaleRow("App memory (PSS)", (deviceSnapshot?.appPssMb?.toString() ?: "N/A") + " MB")
                TouchStationFinaleRow("Free app-private storage", (deviceSnapshot?.freeStorageMb?.toString() ?: "N/A") + " MB")
                TouchStationFinaleRow("Thermal severity", touchStationFinaleThermal(deviceSnapshot?.thermalStatus))
                TouchStationFinaleRow("Physical controllers", deviceSnapshot?.controllers?.joinToString().orEmpty().ifBlank { "None detected" })
                TouchStationFinaleRow("Engine initialized", if (engineReady) "Yes" else "No")
                TouchStationFinaleRow("Native runtime ready", if (nativeReady) "Yes" else "No")
                Text(
                    "GPU utilization and exact Vulkan extensions remain N/A unless the Android driver or native bridge exposes them. No fabricated FPS, GPU percentages or PPU compilation counters are displayed.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            TouchStationFinaleSection("06 · PS3 core configuration snapshot") {
                TouchStationFinaleRow("PPU decoder / threads", settings.ps3.ppuDecoder.toString() + " / " + settings.ps3.ppuThreads)
                TouchStationFinaleRow("LLVM threads / precompile", settings.ps3.llvmThreads.toString() + " / " + settings.ps3.llvmPrecompile)
                TouchStationFinaleRow("SPU decoder / block size", settings.ps3.spuDecoder.toString() + " / " + settings.ps3.spuBlockSize)
                TouchStationFinaleRow("SPU XFloat accuracy", settings.ps3.spuXFloat.toString())
                TouchStationFinaleRow("Shader recompilation mode", settings.ps3.shaderMode.toString())
                TouchStationFinaleRow("MSAA mode", settings.ps3.msaaMode.toString())
                TouchStationFinaleRow("SPU cache / LLVM precompile", settings.ps3.spuCache.toString() + " / " + settings.ps3.llvmPrecompile)
            }

            OutlinedButton(
                onClick = { touchStationFinaleShareReport(context, report) },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Export Finale diagnostic report")
            }
        }
    }
}
'''

def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Expected exactly one {label} marker; found {count}")
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
                        saved.ps3.preferredSpuThreads == updated.ps3.preferredSpuThreads &&
                        saved.ps3.spuBlockSize == updated.ps3.spuBlockSize &&
                        saved.ps3.spuXFloat == updated.ps3.spuXFloat &&
                        saved.ps3.shaderMode == updated.ps3.shaderMode &&
                        saved.ps3.msaaMode == updated.ps3.msaaMode &&
                        saved.ps3.spuCache == updated.ps3.spuCache &&
                        saved.ps3.llvmPrecompile == updated.ps3.llvmPrecompile
                    if (verified) {
                        com.armsx2.runtime.MainActivityRuntime.surface.value?.applyOutputScale()
                    }
                    verified
                }.getOrDefault(false)
            },'''


def patch_version(app_dir: Path) -> None:
    path = app_dir / "build.gradle.kts"
    text = path.read_text(encoding="utf-8")
    if "versionCode = 1100" not in text or 'versionName = "11.0.0"' not in text:
        raise SystemExit("Expected prepared 11.0.0 / versionCode 1100 app before Finale promotion")
    text = replace_once(text, "versionCode = 1100", "versionCode = 1200", "versionCode")
    text = replace_once(text, 'versionName = "11.0.0"', 'versionName = "Finale"', "versionName")
    path.write_text(text, encoding="utf-8")


def patch_performance_tab(app_dir: Path) -> None:
    path = app_dir / "src/main/java/com/armsx2/ui/settings/PerformanceTab.kt"
    text = path.read_text(encoding="utf-8")
    anchor = '''        TouchStation11ReliabilitySuite(
            settings = s,
            ''' + verification_callback() + ''' 
        )
        SettingsDivider()

'''
    # The v11 script inserts the suite followed by exactly this divider. Match
    # the call shape without depending on incidental whitespace around the lambda.
    start = text.find("        TouchStation11ReliabilitySuite(")
    if start < 0:
        raise SystemExit("TouchStation 11 suite call not found in PerformanceTab.kt")
    end_marker = "        SettingsDivider()"
    end = text.find(end_marker, start)
    if end < 0:
        raise SystemExit("TouchStation 11 suite divider not found")
    end = text.find("\n\n", end)
    if end < 0:
        raise SystemExit("Could not locate the end of TouchStation 11 suite block")
    block = text[start:end + 2]
    if "TouchStationFinaleSuite(" in text:
        raise SystemExit("TouchStation Finale suite already present; refusing duplicate insertion")
    if "onApply = { updated ->" not in block or "InGameOverlay.reloadSettings()" not in block:
        raise SystemExit("TouchStation 11 suite callback shape did not match; refusing unsafe patch")
    addition = '''
        TouchStationFinaleSuite(
            settings = s,
            ''' + verification_callback() + '''
        )
        SettingsDivider()

'''
    text = text[:end + 2] + addition + text[end + 2:]
    path.write_text(text, encoding="utf-8")


def patch_library_compatibility(app_dir: Path) -> None:
    """Show exact-ID desktop compatibility on library cards and use it for compatibility sorting."""
    home = app_dir / "src/main/java/com/armsx2/ui/home/HomeScreen.kt"
    text = home.read_text(encoding="utf-8")
    import_anchor = "import com.armsx2.GameInfo\n"
    if "TouchStationFinaleCompatibilityStore" in text:
        raise SystemExit("Finale library compatibility patch is already present")
    text = replace_once(
        text,
        import_anchor,
        import_anchor + "import com.armsx2.ui.settings.TouchStationFinaleCompatibilityStore\n",
        "library compatibility store import",
    )
    home_anchor = "    val context = LocalContext.current\n"
    home_start = text.index("fun HomeScreen(")
    anchor_index = text.find(home_anchor, home_start)
    if anchor_index < 0:
        raise SystemExit("HomeScreen context anchor not found")
    load_cache = """    LaunchedEffect(context) {
        TouchStationFinaleCompatibilityStore.loadCache(context)
    }
"""
    text = text[:anchor_index] + text[anchor_index:].replace(home_anchor, home_anchor + load_cache, 1)
    revision = """    val compatibilityRevision = TouchStationFinaleCompatibilityStore.revision.intValue
    LaunchedEffect(compatibilityRevision, state.sort) {
        if (compatibilityRevision > 0 && state.sort == HomeSort.Compatibility) {
            viewModel.setSort(HomeSort.Compatibility)
        }
    }
"""
    text = replace_once(
        text,
        load_cache,
        load_cache + revision,
        "library compatibility sort observer",
    )
    metadata_anchor = """        game.regionFlag?.let { Text(it, fontSize = 13.sp) }
        if (game.compatibility > 0) {"""
    metadata_replacement = """        game.regionFlag?.let { Text(it, fontSize = 13.sp) }
        TouchStationFinaleCompatibilityStore.statusFor(game.serial)?.let { status ->
            StatusChip("PC: $status")
        }
        if (game.compatibility > 0) {"""
    text = replace_once(text, metadata_anchor, metadata_replacement, "library desktop compatibility badge")
    home.write_text(text, encoding="utf-8")

    view_model = app_dir / "src/main/java/com/armsx2/ui/home/HomeViewModel.kt"
    vm_text = view_model.read_text(encoding="utf-8")
    vm_import = "import com.armsx2.GameInfo\n"
    vm_text = replace_once(
        vm_text,
        vm_import,
        vm_import + "import com.armsx2.ui.settings.TouchStationFinaleCompatibilityStore\n",
        "compatibility sorter store import",
    )
    sorter_old = """            HomeSort.Compatibility -> filtered.sortedWith(
                compareByDescending<GameInfo> { it.compatibility }
                    .thenBy { it.sortKey(forceEn).lowercase() },
            )"""
    sorter_new = """            HomeSort.Compatibility -> filtered.sortedWith(
                compareByDescending<GameInfo> {
                    TouchStationFinaleCompatibilityStore.rankFor(it.serial) ?: -1
                }.thenBy { it.sortKey(forceEn).lowercase() },
            )"""
    vm_text = replace_once(vm_text, sorter_old, sorter_new, "official compatibility sort comparator")
    view_model.write_text(vm_text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args()
    app_dir = args.source / "app"
    settings_dir = app_dir / "src/main/java/com/armsx2/ui/settings"
    performance_tab = settings_dir / "PerformanceTab.kt"
    version_file = app_dir / "build.gradle.kts"
    for path in (version_file, performance_tab, settings_dir / "TouchStation11ReliabilitySuite.kt"):
        if not path.is_file():
            raise SystemExit("Missing required prepared source file: " + str(path))
    suite_path = settings_dir / "TouchStationFinaleSuite.kt"
    if suite_path.exists():
        raise SystemExit("TouchStation Finale suite already exists; refusing to overwrite")
    patch_version(app_dir)
    suite_path.write_text(KOTLIN_SOURCE, encoding="utf-8")
    patch_performance_tab(app_dir)
    patch_library_compatibility(app_dir)

    required_markers = [
        "Update official compatibility database",
        "exact normalized PS3 title ID",
        "Stable session (10+ min)",
        "GTA IV per-game profile",
        "SPU XFloat",
        "safe SPU block mode",
        "Export Finale diagnostic report",
        "Physical controllers",
        "Engine initialized",
        "GPU utilization",
    ]
    missing = [marker for marker in required_markers if marker not in KOTLIN_SOURCE]
    # The URL and some explanatory copy intentionally live in different parts
    # of the template, so test the exact API route and title-ID matching separately.
    if "https://rpcs3.net/compatibility/?api=v1&export" not in KOTLIN_SOURCE:
        missing.append("Official compatibility API endpoint")
    if "touchStationFinaleNormaliseId" not in KOTLIN_SOURCE:
        missing.append("Exact title-ID normalizer")
    if missing:
        raise SystemExit("Missing Finale source markers: " + ", ".join(missing))
    print("Applied TouchStation Version Finale suite, official compatibility sync and GTA IV settings profile.")


if __name__ == "__main__":
    main()
