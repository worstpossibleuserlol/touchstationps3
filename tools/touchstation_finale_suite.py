#!/usr/bin/env python3
"""Add the TouchStation Version Finale compatibility, device and GTA IV tools."""
from __future__ import annotations

import argparse
from pathlib import Path

KOTLIN_SOURCE = r'''package com.armsx2.ui.settings

import android.app.ActivityManager
import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
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
import com.armsx2.config.CoreSettingOverrides
import com.armsx2.runtime.MainActivityRuntime
import com.armsx2.reliability.TouchStationFinaleReliability
import com.armsx2.ui.InGameOverlay
import com.armsx3.HttpClient
import com.armsx3.core.ARMSX3
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.Locale
import java.util.concurrent.TimeUnit

private const val TOUCHSTATION_FINALE_COMPAT_URL =
    "https://rpcs3.net/compatibility/?api=v1&export"
private const val TOUCHSTATION_FINALE_COMPAT_FILE = "touchstation-finale-compatibility.json"
private const val TOUCHSTATION_FINALE_COMPAT_SYNC_KEY = "touchstation.finale.compatLastSync"
private const val TOUCHSTATION_FINALE_ERROR_HISTORY_KEY = "touchstation.finale.errorHistory"

/**
 * Shared exact-ID compatibility cache used by the settings centre and game-library tiles.
 * The displayed statuses are desktop RPCS3 references, not device-specific results.
 */
internal data class TouchStationFinaleCompatibilityEntry(
    val status: String,
    val date: String,
    val update: String,
)

object TouchStationFinaleCompatibilityStore {
    val revision = mutableIntStateOf(0)
    private val entriesById = mutableStateOf<Map<String, TouchStationFinaleCompatibilityEntry>>(emptyMap())

    fun replace(database: JSONObject?) {
        val next = LinkedHashMap<String, TouchStationFinaleCompatibilityEntry>()
        val results = database?.optJSONObject("results")
        if (results != null) {
            val keys = results.keys()
            while (keys.hasNext()) {
                val id = keys.next()
                val item = results.optJSONObject(id) ?: continue
                val status = item.optString("status").takeIf { it.isNotBlank() } ?: continue
                next[touchStationFinaleNormaliseId(id)] = TouchStationFinaleCompatibilityEntry(
                    status = status,
                    date = item.optString("date").takeIf { it.isNotBlank() } ?: "N/A",
                    update = item.optString("update").takeIf { it.isNotBlank() } ?: "N/A",
                )
            }
        }
        entriesById.value = next
        revision.intValue++
    }

    internal fun entryFor(serial: String?): TouchStationFinaleCompatibilityEntry? {
        revision.intValue
        if (serial.isNullOrBlank()) return null
        return entriesById.value[touchStationFinaleNormaliseId(serial)]
    }

    fun statusFor(serial: String?): String? = entryFor(serial)?.status

    fun rankFor(serial: String?): Int? = when (statusFor(serial)?.lowercase(Locale.ROOT)) {
        "playable" -> 5
        "ingame" -> 4
        "intro" -> 3
        "loadable" -> 2
        "nothing" -> 0
        else -> null
    }

    suspend fun loadCache(context: Context) {
        replace(withContext(Dispatchers.IO) { touchStationFinaleReadCache(context) })
    }
}


/**
 * Bounded, local-only game error history. Dismissal hides the banner, not the recorded event.
 * Only error text supplied by the bridge is stored; no log is uploaded automatically.
 */
object TouchStationFinaleErrorHistory {
    private fun readEvents(): JSONArray = runCatching {
        JSONArray(MainActivityRuntime.prefs.getString(TOUCHSTATION_FINALE_ERROR_HISTORY_KEY, "[]") ?: "[]")
    }.getOrDefault(JSONArray())

    fun record(message: String) {
        val previous = readEvents()
        val next = JSONArray()
        val start = (previous.length() - 29).coerceAtLeast(0)
        for (index in start until previous.length()) {
            previous.optJSONObject(index)?.let { next.put(it) }
        }
        next.put(
            JSONObject()
                .put("timestamp", System.currentTimeMillis())
                .put("message", message.take(2_000))
                .put("fifo", message.contains("FIFO", ignoreCase = true))
                .put("critical", isCritical(message)),
        )
        MainActivityRuntime.prefs.edit()
            .putString(TOUCHSTATION_FINALE_ERROR_HISTORY_KEY, next.toString())
            .apply()
        runCatching {
            TouchStationFinaleReliability.recordEvent(
                com.armsx2.Pasx2Application.appContext, "game-error", message,
            )
        }
    }

    fun latestMessage(): String {
        val events = readEvents()
        return events.optJSONObject(events.length() - 1)
            ?.optString("message").orEmpty().ifBlank { "None recorded" }
    }

    fun eventCount(): Int = readEvents().length()

    fun fifoFailureCount(): Int {
        val events = readEvents()
        return (0 until events.length()).count {
            events.optJSONObject(it)?.optBoolean("fifo", false) == true
        }
    }

    fun isCritical(message: String): Boolean {
        val value = message.lowercase(Locale.ROOT)
        return listOf("fatal", "dead fifo", "segmentation fault", "access violation", "abort",
            "panic", "native crash", "process terminated").any { it in value }
    }

    fun explanation(message: String): String {
        val value = message.lowercase(Locale.ROOT)
        return when {
            "dead fifo" in value || "fifo" in value ->
                "The RSX graphics command queue reported a failure. The game may have stopped; dismissing this notice cannot resume it."
            "out of memory" in value || "memory" in value ->
                "The emulator or game reported a memory problem. Close other apps and relaunch the game after checking available memory."
            "shader" in value ->
                "The graphics shader path reported an error. A shader cache or graphics-driver issue may be involved."
            "spu" in value || "ppu" in value ->
                "A PS3 processor task reported an error. The game may require a native-core fix or different supported settings."
            else ->
                "The emulator reported a game error. The exact cause needs the exported TouchStation.log for diagnosis."
        }
    }

    fun suggestion(message: String): String {
        val value = message.lowercase(Locale.ROOT)
        return when {
            "dead fifo" in value || "fifo" in value ->
                "Save the log, stop the game, then relaunch. Do not assume a dismissed FIFO error means the queue recovered."
            "shader" in value ->
                "Save the log and test the game with its shader cache preserved; do not delete cache files automatically."
            "memory" in value ->
                "Save the log, close other apps and retry after the device has cooled down."
            else ->
                "Export TouchStation.log and include the game title, title ID and the steps that led to the error."
        }
    }
}


private const val TOUCHSTATION_FINALE_SETTINGS_CHECKPOINT_KEY = "touchstation.finale.settingsCheckpoint"

/** User-controlled rollback point scoped to one settings tier and one game identity. */
object TouchStationFinaleSettingsRollback {
    fun save(settings: Settings, scope: SettingsScope, serial: String?): Pair<Boolean, String> {
        if (scope == SettingsScope.Game && serial.isNullOrBlank()) {
            return false to "A game title ID is required for a per-game checkpoint."
        }
        return runCatching {
            val payload = JSONObject()
                .put("scope", scope.name)
                .put("serial", serial.orEmpty())
                .put("createdAt", System.currentTimeMillis())
                .put("settings", settings.toJson())
            MainActivityRuntime.prefs.edit()
                .putString(TOUCHSTATION_FINALE_SETTINGS_CHECKPOINT_KEY, payload.toString())
                .apply()
            true to ("Checkpoint saved for " + scope.name + " scope.")
        }.getOrElse { false to ("Checkpoint failed: " + (it.message ?: "unknown error")) }
    }

    fun restore(scope: SettingsScope, serial: String?): Settings? = runCatching {
        val raw = MainActivityRuntime.prefs.getString(TOUCHSTATION_FINALE_SETTINGS_CHECKPOINT_KEY, null)
            ?: return null
        val payload = JSONObject(raw)
        if (payload.optString("scope") != scope.name) return null
        if (payload.optString("serial") != serial.orEmpty()) return null
        Settings.fromJson(payload.getJSONObject("settings"))
    }.getOrNull()

    fun description(): String {
        val raw = MainActivityRuntime.prefs.getString(TOUCHSTATION_FINALE_SETTINGS_CHECKPOINT_KEY, null)
            ?: return "No settings checkpoint saved."
        return runCatching {
            val payload = JSONObject(raw)
            "Saved checkpoint: " + payload.optString("scope", "Unknown") + " / " +
                payload.optString("serial", "").ifBlank { "global" }
        }.getOrDefault("Checkpoint is unreadable.")
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

/**
 * Read the last successfully downloaded desktop compatibility database.
 * Invalid, empty, oversized or partially-written cache files are ignored.
 */
private fun touchStationFinaleReadCache(context: Context): JSONObject? {
    val cacheFile = File(context.filesDir, TOUCHSTATION_FINALE_COMPAT_FILE)
    if (!cacheFile.isFile || cacheFile.length() !in 1L..(32L * 1024L * 1024L)) {
        return null
    }
    return runCatching {
        val payload = JSONObject(cacheFile.readText(Charsets.UTF_8))
        if (payload.optInt("return_code", -1) != 0 || payload.optJSONObject("results") == null) {
            null
        } else {
            payload
        }
    }.getOrNull()
}

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


private const val TOUCHSTATION_FINALE_FIFO_ACCURACY_PATH = "Core@@RSX FIFO Fetch Accuracy"
private const val TOUCHSTATION_FINALE_DRIVER_WAKE_DELAY_PATH = "Video@@Driver Wake-Up Delay"

private fun touchStationFinaleReadCoreSetting(path: String): String =
    runCatching {
        JSONObject(ARMSX3.instance.settingsGet(path)).opt("value")?.toString() ?: "N/A"
    }.getOrDefault("N/A")

/**
 * The native dead-FIFO exception recommends moving RSX FIFO accuracy away from PS3
 * mode and increasing Driver Wake-Up Delay. Apply supported values only to this
 * game's scope and read them back before reporting success.
 */
private fun touchStationFinaleApplyFifoRecoveryProfile(serial: String): Pair<Boolean, String> {
    if (serial.isBlank() || !ARMSX3.initialized) {
        return false to "Native runtime or game title ID is unavailable."
    }
    val accuracyValue = JSONObject.quote("Ordered & Atomic")
    val delayValue = "20"
    var accuracyApplied = false
    var delayApplied = false
    val batchStarted = runCatching { ARMSX3.instance.settingsBeginBatch() }.isSuccess
    try {
        accuracyApplied = runCatching {
            ARMSX3.instance.settingsSet(TOUCHSTATION_FINALE_FIFO_ACCURACY_PATH, accuracyValue)
        }.getOrDefault(false)
        delayApplied = runCatching {
            ARMSX3.instance.settingsSet(TOUCHSTATION_FINALE_DRIVER_WAKE_DELAY_PATH, delayValue)
        }.getOrDefault(false)
    } finally {
        if (batchStarted) runCatching { ARMSX3.instance.settingsEndBatch() }
    }
    // Match the upstream Core Settings screen: record the scoped override even when
    // the native setting is non-dynamic and declines an immediate in-game write.
    runCatching {
        CoreSettingOverrides.record(
            SettingsScope.Game, serial, TOUCHSTATION_FINALE_FIFO_ACCURACY_PATH, accuracyValue,
        )
    }
    runCatching {
        CoreSettingOverrides.record(
            SettingsScope.Game, serial, TOUCHSTATION_FINALE_DRIVER_WAKE_DELAY_PATH, delayValue,
        )
    }
    val accuracyReadback = touchStationFinaleReadCoreSetting(TOUCHSTATION_FINALE_FIFO_ACCURACY_PATH)
    val delayReadback = touchStationFinaleReadCoreSetting(TOUCHSTATION_FINALE_DRIVER_WAKE_DELAY_PATH)
    val storedOverrides = runCatching { CoreSettingOverrides.load(SettingsScope.Game, serial) }
        .getOrDefault(emptyMap())
    val accuracyPersisted = storedOverrides[TOUCHSTATION_FINALE_FIFO_ACCURACY_PATH] == accuracyValue
    val delayPersisted = storedOverrides[TOUCHSTATION_FINALE_DRIVER_WAKE_DELAY_PATH] == delayValue
    val accuracyAvailable = accuracyReadback != "N/A"
    val delayAvailable = delayReadback != "N/A"
    val persisted = accuracyPersisted && delayPersisted && accuracyAvailable && delayAvailable
    val activeNow = accuracyReadback == "Ordered & Atomic" && delayReadback == delayValue
    val detail = "RSX FIFO Fetch Accuracy: $accuracyReadback; Driver Wake-Up Delay: $delayReadback µs; " +
        "per-game overrides persisted: " + (accuracyPersisted && delayPersisted) + "; " +
        (if (activeNow) "both values are active now." else "saved for the next game launch; restart the game to apply non-dynamic settings.")
    return verified to detail
}

private fun touchStationFinaleGtaIv(title: String): Boolean {
    val normalized = title.lowercase(Locale.ROOT)
    return normalized.contains("grand theft auto iv") ||
        Regex("""\bgta\s*iv\b""", RegexOption.IGNORE_CASE).containsMatchIn(title)
}

private fun touchStationFinaleShareReport(
    context: Context,
    report: String,
    subject: String = "TouchStation Version Finale diagnostic report",
) {
    runCatching {
        val intent = Intent(Intent.ACTION_SEND).apply {
            type = "text/plain"
            putExtra(Intent.EXTRA_SUBJECT, subject)
            putExtra(Intent.EXTRA_TEXT, report)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        context.startActivity(Intent.createChooser(intent, "Share diagnostic report").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    }
}

private suspend fun touchStationFinaleCollectLog(context: Context, diagnosticReport: String): String =
    withContext(Dispatchers.IO) {
        val temporary = File(context.cacheDir, "TouchStation-logcat.tmp")
        val capture = runCatching {
            val process = ProcessBuilder(
                "logcat", "-d", "-t", "3000", "--pid=${android.os.Process.myPid()}",
            ).redirectErrorStream(true).redirectOutput(temporary).start()
            if (!process.waitFor(6, TimeUnit.SECONDS)) {
                process.destroyForcibly()
                error("logcat capture timed out")
            }
            if (temporary.isFile && temporary.length() in 1L..(4L * 1024L * 1024L)) {
                temporary.readText(Charsets.UTF_8).takeLast(2_000_000)
            } else {
                "No app-process log lines were returned. Android may restrict logcat access."
            }
        }.getOrElse {
            "App-process log capture unavailable: " + (it.message ?: "unknown error")
        }
        temporary.delete()
        buildString {
            appendLine("TouchStation.log")
            appendLine("Created: " + java.text.SimpleDateFormat("yyyy-MM-dd HH:mm:ss z", Locale.US).format(java.util.Date()))
            appendLine("Capture scope: this TouchStation app process only; system-wide logs are not collected.")
            appendLine("Recent error count: " + TouchStationFinaleErrorHistory.eventCount())
            appendLine("Recorded FIFO errors: " + TouchStationFinaleErrorHistory.fifoFailureCount())
            appendLine("Latest recorded error: " + TouchStationFinaleErrorHistory.latestMessage())
            appendLine()
            appendLine("=== Android app-process logcat ===")
            appendLine(capture)
            appendLine()
            val sessionLog = File(context.getExternalFilesDir(null) ?: context.filesDir, "logs/session.log")
            appendLine("=== Existing native stdout/stderr session log ===")
            appendLine(
                if (sessionLog.isFile && sessionLog.canRead()) {
                    runCatching { sessionLog.readText(Charsets.UTF_8).takeLast(2_000_000) }
                        .getOrElse { "Session log read failed: " + (it.message ?: "unknown error") }
                } else "No existing session.log was found.",
            )
            appendLine()
            appendLine("=== TouchStation Finale reliability events ===")
            val reliabilityLog = File(context.filesDir, "touchstation-finale-diagnostics/events.log")
            appendLine(
                if (reliabilityLog.isFile && reliabilityLog.canRead()) {
                    runCatching { reliabilityLog.readText(Charsets.UTF_8).takeLast(500_000) }
                        .getOrElse { "Reliability log read failed: " + (it.message ?: "unknown error") }
                } else "No reliability event log was found.",
            )
            appendLine()
            appendLine("=== Most recent Java/Kotlin crash report ===")
            appendLine(TouchStationFinaleReliability.latestCrashReport(context))
            appendLine()
            appendLine("=== TouchStation diagnostic snapshot ===")
            append(diagnosticReport)
        }.also {
            File(context.cacheDir, "TouchStation.log").writeText(it, Charsets.UTF_8)
        }
    }

private suspend fun touchStationFinaleSaveLog(context: Context, contents: String): Pair<Boolean, String> =
    withContext(Dispatchers.IO) {
        runCatching {
            require(contents.isNotBlank()) { "The log is empty." }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                val values = ContentValues().apply {
                    put(MediaStore.MediaColumns.DISPLAY_NAME, "TouchStation.log")
                    put(MediaStore.MediaColumns.MIME_TYPE, "text/plain")
                    put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS)
                }
                val uri = context.contentResolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)
                    ?: error("Android could not create the Downloads file.")
                try {
                    val output = context.contentResolver.openOutputStream(uri)
                        ?: error("Android could not open the Downloads file.")
                    output.use { it.write(contents.toByteArray(Charsets.UTF_8)) }
                } catch (error: Exception) {
                    context.contentResolver.delete(uri, null, null)
                    throw error
                }
                "Saved to Downloads/TouchStation.log"
            } else {
                val directory = context.getExternalFilesDir(Environment.DIRECTORY_DOCUMENTS) ?: context.filesDir
                val destination = File(directory, "TouchStation.log")
                destination.writeText(contents, Charsets.UTF_8)
                "Saved to " + destination.absolutePath
            }
        }.fold(
            onSuccess = { true to it },
            onFailure = { false to ("Log export failed: " + (it.message ?: "storage error")) },
        )
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
private fun TouchStationFinaleDashboardCard(
    title: String,
    value: String,
    modifier: Modifier = Modifier,
) {
    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(14.dp),
        color = MaterialTheme.colorScheme.surface,
        tonalElevation = 1.dp,
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Text(title, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text(value, style = MaterialTheme.typography.titleSmall, maxLines = 2)
        }
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
    val logBusy = remember { mutableStateOf(false) }
    val logContents = remember { mutableStateOf("") }
    val logMessage = remember { mutableStateOf("No TouchStation.log has been exported in this session.") }
    val safeMode = remember(context) { mutableStateOf(TouchStationFinaleReliability.isSafeMode(context)) }
    val reliabilitySnapshot = remember { mutableStateOf("Reliability diagnostics have not been refreshed yet.") }
    val gameSourceStatus = remember { mutableStateOf("Game source has not been checked yet.") }
    val gameHashStatus = remember { mutableStateOf("SHA-256 has not been calculated.") }
    val integrityBusy = remember { mutableStateOf(false) }
    val rollbackMessage = remember { mutableStateOf(TouchStationFinaleSettingsRollback.description()) }
    val game: GameInfo? = MainActivityRuntime.currentGame.value
    val gameTitle = game?.title?.takeIf { it.isNotBlank() } ?: "No game selected"
    val serial = game?.serial?.takeIf { it.isNotBlank() }
        ?: game?.settingsKey?.takeIf { it.isNotBlank() }
    val settingsArePerGame = InGameOverlay.settingsScope.value == SettingsScope.Game
    val isGtaIv = touchStationFinaleGtaIv(gameTitle)
    val officialEntry = TouchStationFinaleCompatibilityStore.entryFor(serial)
    val officialStatus = officialEntry?.status ?: "Not found in cached official database"
    val officialDate = officialEntry?.date ?: "N/A"
    val officialUpdate = officialEntry?.update ?: "N/A"
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
        TouchStationFinaleReliability.recordEvent(context, "finale-ui", "Finale diagnostics opened")
        device.value = withContext(Dispatchers.IO) { touchStationFinaleDeviceSnapshot(context) }
        reliabilitySnapshot.value = withContext(Dispatchers.IO) {
            TouchStationFinaleReliability.snapshot(context) + "\n" +
                TouchStationFinaleReliability.startupSelfTest(context, settings)
        }
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

    LaunchedEffect(context, game?.uri) {
        gameSourceStatus.value = withContext(Dispatchers.IO) {
            game?.let { TouchStationFinaleReliability.inspectGameUri(context, it.uri) }
                ?: "No game selected."
        }
    }

    val settingsValidation = TouchStationFinaleReliability.validateSettings(settings)
    val report = buildString {
        appendLine("TouchStation Version Finale diagnostic report")
        appendLine("Safe mode: " + safeMode.value)
        appendLine("Settings validation: " + settingsValidation.joinToString().ifBlank { "PASS" })
        appendLine("Game source: " + gameSourceStatus.value)
        appendLine(reliabilitySnapshot.value)
        appendLine("Latest Java crash report: " + TouchStationFinaleReliability.latestCrashSummary(context))
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
        appendLine("Recorded game errors: " + TouchStationFinaleErrorHistory.eventCount())
        appendLine("Recorded FIFO errors: " + TouchStationFinaleErrorHistory.fifoFailureCount())
        appendLine("Latest recorded error: " + TouchStationFinaleErrorHistory.latestMessage())
        appendLine("RSX FIFO Fetch Accuracy: " + touchStationFinaleReadCoreSetting(TOUCHSTATION_FINALE_FIFO_ACCURACY_PATH))
        appendLine("Driver Wake-Up Delay: " + touchStationFinaleReadCoreSetting(TOUCHSTATION_FINALE_DRIVER_WAKE_DELAY_PATH) + " µs")
        appendLine("Latest error explanation: " + TouchStationFinaleErrorHistory.explanation(TouchStationFinaleErrorHistory.latestMessage()))
        appendLine("Latest error recovery suggestion: " + TouchStationFinaleErrorHistory.suggestion(TouchStationFinaleErrorHistory.latestMessage()))
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

            TouchStationFinaleSection("Finale dashboard") {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    TouchStationFinaleDashboardCard(
                        "Compatibility",
                        if (database.value == null) "PC database not downloaded" else "PC: " + officialStatus,
                        Modifier.weight(1f),
                    )
                    TouchStationFinaleDashboardCard(
                        "Device readiness",
                        (deviceSnapshot?.soc ?: "SoC scanning") + " · " + touchStationFinaleMemory(deviceSnapshot?.availableRamMb) + " RAM",
                        Modifier.weight(1f),
                    )
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    TouchStationFinaleDashboardCard(
                        "GTA IV profile",
                        if (isGtaIv && settingsArePerGame) "Ready to apply per-game settings" else "Select GTA IV and Game scope",
                        Modifier.weight(1f),
                    )
                    TouchStationFinaleDashboardCard(
                        "PS3 runtime",
                        if (engineReady && nativeReady) "Engine and native runtime ready" else "Engine/runtime not ready",
                        Modifier.weight(1f),
                    )
                }
            }

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
                OutlinedButton(
                    onClick = {
                        scope.launch {
                            libraryGames.value = withContext(Dispatchers.IO) {
                                runCatching {
                                    GameLibraryRepository(context).loadCached().games
                                        .filter { it.platform == GamePlatform.PS3 && !it.serial.isNullOrBlank() }
                                        .distinctBy { touchStationFinaleNormaliseId(it.serial.orEmpty()) }
                                        .sortedBy { it.title.lowercase(Locale.ROOT) }
                                }.getOrDefault(emptyList())
                            }
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("Reload cached library index")
                }
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
                        val entry = TouchStationFinaleCompatibilityStore.entryFor(item.serial)
                        TouchStationFinaleRow(
                            item.title,
                            (item.serial ?: "No title ID") + " · " +
                                (entry?.status ?: "No official entry"),
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
                TouchStationFinaleRow("Finale safe mode", if (safeMode.value) "Enabled" else "Disabled")
                OutlinedButton(
                    onClick = {
                        TouchStationFinaleReliability.setSafeMode(context, !safeMode.value)
                        safeMode.value = !safeMode.value
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(if (safeMode.value) "Disable safe mode" else "Enable safe mode")
                }
                OutlinedButton(
                    onClick = {
                        val activeScope = if (settingsArePerGame) SettingsScope.Game else SettingsScope.Global
                        val saved = TouchStationFinaleSettingsRollback.save(settings, activeScope, serial)
                        rollbackMessage.value = saved.second
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("Save settings rollback point")
                }
                OutlinedButton(
                    onClick = {
                        val activeScope = if (settingsArePerGame) SettingsScope.Game else SettingsScope.Global
                        val saved = TouchStationFinaleSettingsRollback.restore(activeScope, serial)
                        if (saved == null) {
                            rollbackMessage.value = "No matching checkpoint exists for this scope and game."
                        } else {
                            val warnings = TouchStationFinaleReliability.validateSettings(saved)
                            if (warnings.isNotEmpty()) {
                                rollbackMessage.value = "Checkpoint rejected: " + warnings.joinToString()
                            } else {
                                val applied = runCatching { onApply(saved) }.getOrDefault(false)
                                rollbackMessage.value = if (applied) {
                                    "Checkpoint restored and settings read-back succeeded."
                                } else {
                                    "Checkpoint loaded, but the existing apply callback did not verify it."
                                }
                            }
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("Restore saved settings")
                }
                Text(
                    rollbackMessage.value + " " + TouchStationFinaleSettingsRollback.description(),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Text(
                    "The profile selects safe SPU block mode, accurate SPU XFloat, asynchronous shaders, MSAA off, SPU cache, LLVM precompile and restrained PPU/LLVM threads. It saves RSX FIFO Fetch Accuracy = Ordered & Atomic and Driver Wake-Up Delay = 20 µs to this game only. Non-dynamic values may require a game restart. Ordered & Atomic can reduce performance; this is a targeted stability test, not a GTA IV guarantee.",
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
                        val fifoResult = if (saved && serial != null) {
                            touchStationFinaleApplyFifoRecoveryProfile(serial)
                        } else {
                            false to "A per-game title ID or verified settings save is unavailable."
                        }
                        message.value = when {
                            !saved -> "Settings could not be verified. No successful profile application is claimed."
                            fifoResult.first -> "GTA IV profile and FIFO recovery settings were saved. " + fifoResult.second
                            else -> "The standard GTA IV profile was saved, but FIFO settings were not fully verified: " + fifoResult.second
                        }
                    },
                    enabled = isGtaIv && settingsArePerGame && game != null && !safeMode.value,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("Apply GTA IV per-game profile")
                }
                Text(
                    "This button is enabled only for a detected GTA IV title while per-game scope is active and safe mode is off. It changes supported settings only and leaves global settings untouched.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            TouchStationFinaleSection("05 · Reliability, recovery and preflight") {
                TouchStationFinaleRow("Application lifecycle", TouchStationFinaleReliability.lifecycleStatus())
                TouchStationFinaleRow("Memory trend", TouchStationFinaleReliability.memoryTrend(context))
                TouchStationFinaleRow("Crash report", TouchStationFinaleReliability.latestCrashSummary(context))
                TouchStationFinaleRow("App cache inventory", TouchStationFinaleReliability.inspectDirectory(context.cacheDir))
                TouchStationFinaleRow("Game source", gameSourceStatus.value)
                TouchStationFinaleRow("Settings validation", if (settingsValidation.isEmpty()) "PASS" else settingsValidation.joinToString())
                Text(
                    reliabilitySnapshot.value,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Text(
                    "Native PPU/SPU counters, RSX queue depth, GPU fences and shader-cache internals remain unavailable unless the native bridge exposes them. Missing telemetry is never shown as zero.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error,
                )
                Button(
                    onClick = {
                        if (!integrityBusy.value && game != null) {
                            scope.launch {
                                integrityBusy.value = true
                                gameSourceStatus.value = withContext(Dispatchers.IO) {
                                    TouchStationFinaleReliability.inspectGameUri(context, game.uri)
                                }
                                gameHashStatus.value = withContext(Dispatchers.IO) {
                                    TouchStationFinaleReliability.sha256GameUri(
                                        context, game.uri, 256L * 1024L * 1024L,
                                    )
                                }
                                integrityBusy.value = false
                            }
                        }
                    },
                    enabled = game != null && !integrityBusy.value,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(if (integrityBusy.value) "Checking game source…" else "Validate game source and calculate SHA-256")
                }
                Text(
                    gameHashStatus.value,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                OutlinedButton(
                    onClick = {
                        scope.launch {
                            reliabilitySnapshot.value = withContext(Dispatchers.IO) {
                                TouchStationFinaleReliability.snapshot(context)
                            }
                            gameSourceStatus.value = withContext(Dispatchers.IO) {
                                game?.let { TouchStationFinaleReliability.inspectGameUri(context, it.uri) }
                                    ?: "No game selected."
                            }
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("Refresh reliability diagnostics")
                }
            }

            TouchStationFinaleSection("06 · Device readiness and system checks") {
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

            TouchStationFinaleSection("07 · PS3 core configuration snapshot") {
                TouchStationFinaleRow("PPU decoder / threads", settings.ps3.ppuDecoder.toString() + " / " + settings.ps3.ppuThreads)
                TouchStationFinaleRow("LLVM threads / precompile", settings.ps3.llvmThreads.toString() + " / " + settings.ps3.llvmPrecompile)
                TouchStationFinaleRow("SPU decoder / block size", settings.ps3.spuDecoder.toString() + " / " + settings.ps3.spuBlockSize)
                TouchStationFinaleRow("SPU XFloat accuracy", settings.ps3.spuXFloat.toString())
                TouchStationFinaleRow("Shader recompilation mode", settings.ps3.shaderMode.toString())
                TouchStationFinaleRow("MSAA mode", settings.ps3.msaaMode.toString())
                TouchStationFinaleRow("SPU cache / LLVM precompile", settings.ps3.spuCache.toString() + " / " + settings.ps3.llvmPrecompile)
                TouchStationFinaleRow("RSX FIFO Fetch Accuracy", touchStationFinaleReadCoreSetting(TOUCHSTATION_FINALE_FIFO_ACCURACY_PATH))
                TouchStationFinaleRow("Driver Wake-Up Delay", touchStationFinaleReadCoreSetting(TOUCHSTATION_FINALE_DRIVER_WAKE_DELAY_PATH) + " µs")
            }

            TouchStationFinaleSection("08 · Error history and FIFO diagnostics") {
                TouchStationFinaleRow("Recorded game errors", TouchStationFinaleErrorHistory.eventCount().toString())
                TouchStationFinaleRow("Recorded FIFO failures", TouchStationFinaleErrorHistory.fifoFailureCount().toString())
                TouchStationFinaleRow("Latest error", TouchStationFinaleErrorHistory.latestMessage().take(160))
                Text(
                    TouchStationFinaleErrorHistory.explanation(TouchStationFinaleErrorHistory.latestMessage()),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Text(
                    TouchStationFinaleErrorHistory.suggestion(TouchStationFinaleErrorHistory.latestMessage()),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Text(
                    "The bundled native bridge does not expose live FIFO queue depth, command progress, GPU fences or RSX command validation. TouchStation records explicit FIFO errors and exports evidence, but cannot safely reset or repair a stalled native queue from the Android UI.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error,
                )
            }

            Button(
                onClick = {
                    if (!logBusy.value) {
                        scope.launch {
                            logBusy.value = true
                            val result = runCatching {
                                val contents = touchStationFinaleCollectLog(context, report)
                                logContents.value = contents
                                touchStationFinaleSaveLog(context, contents)
                            }.getOrElse {
                                false to ("Log export failed: " + (it.message ?: "unknown error"))
                            }
                            logMessage.value = result.second
                            logBusy.value = false
                        }
                    }
                },
                enabled = !logBusy.value,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(if (logBusy.value) "Collecting log…" else "Download TouchStation.log")
            }
            OutlinedButton(
                onClick = {
                    if (logContents.value.isNotBlank()) {
                        touchStationFinaleShareReport(context, logContents.value, "TouchStation.log")
                    }
                },
                enabled = logContents.value.isNotBlank(),
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Share TouchStation.log")
            }
            Text(
                logMessage.value,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
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

RELIABILITY_KOTLIN_SOURCE = r'''
package com.armsx2.reliability

import android.app.Activity
import android.app.ActivityManager
import android.app.Application
import android.content.Context
import android.net.Uri
import android.os.Build
import android.os.Debug
import android.os.PowerManager
import android.os.StatFs
import android.provider.OpenableColumns
import android.view.InputDevice
import com.armsx2.config.Settings
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.security.MessageDigest
import java.util.Collections
import java.util.WeakHashMap
import java.util.concurrent.atomic.AtomicInteger

/** Bounded Android reliability services. Native PPU/SPU/RSX internals are not fabricated here. */
object TouchStationFinaleReliability {
    private const val PREFS = "touchstation-finale-reliability"
    private const val SAFE_MODE_KEY = "safeMode"
    private const val MEMORY_KEY = "pssSamples"
    private const val MAX_LOG_BYTES = 512L * 1024L
    private val lock = Any()
    private val started = Collections.newSetFromMap(WeakHashMap<Activity, Boolean>())
    private val foreground = AtomicInteger(0)
    @Volatile private var installed = false

    fun install(application: Application) {
        synchronized(lock) {
            if (installed) return
            installed = true
        }
        val directory = diagnosticsDir(application)
        val marker = File(directory, "uncaught.marker")
        if (marker.isFile) {
            recordEvent(application, "crash-recovery", "A previous Java/Kotlin uncaught exception was recorded.")
            marker.delete()
        }
        application.registerActivityLifecycleCallbacks(object : Application.ActivityLifecycleCallbacks {
            override fun onActivityCreated(a: Activity, state: android.os.Bundle?) = Unit
            override fun onActivityStarted(a: Activity) {
                synchronized(lock) { if (started.add(a)) foreground.incrementAndGet() }
                recordEvent(application, "lifecycle", "Started " + a.javaClass.simpleName)
            }
            override fun onActivityResumed(a: Activity) {
                recordEvent(application, "lifecycle", "Resumed " + a.javaClass.simpleName)
            }
            override fun onActivityPaused(a: Activity) = Unit
            override fun onActivityStopped(a: Activity) {
                synchronized(lock) { if (started.remove(a)) foreground.updateAndGet { (it - 1).coerceAtLeast(0) } }
            }
            override fun onActivitySaveInstanceState(a: Activity, state: android.os.Bundle) = Unit
            override fun onActivityDestroyed(a: Activity) {
                synchronized(lock) { if (started.remove(a)) foreground.updateAndGet { (it - 1).coerceAtLeast(0) } }
            }
        })
        val previous = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { thread, error ->
            runCatching {
                directory.mkdirs()
                File(directory, "uncaught.marker").writeText(System.currentTimeMillis().toString())
                File(directory, "crash-" + System.currentTimeMillis() + ".txt").writeText(
                    "TouchStation Finale crash\nThread: " + thread.name +
                        "\nDevice: " + Build.MANUFACTURER + " " + Build.MODEL +
                        "\nAndroid: " + Build.VERSION.RELEASE +
                        "\n\n" + android.util.Log.getStackTraceString(error),
                )
                pruneCrashes(directory)
                recordEvent(application, "uncaught-exception", error.javaClass.name + ": " + (error.message ?: ""))
            }
            previous?.uncaughtException(thread, error)
        }
        recordEvent(application, "startup", "Reliability services initialized.")
    }

    private fun diagnosticsDir(context: Context) = File(context.filesDir, "touchstation-finale-diagnostics")

    fun recordEvent(context: Context, component: String, message: String) {
        val line = System.currentTimeMillis().toString() + " [" +
            component.replace('\n', ' ').replace('\r', ' ').take(80) + "] " +
            message.replace('\n', ' ').replace('\r', ' ').take(1_800)
        runCatching {
            val dir = diagnosticsDir(context)
            if (!dir.exists() && !dir.mkdirs()) return
            val log = File(dir, "events.log")
            synchronized(lock) {
                if (log.length() > MAX_LOG_BYTES) {
                    val old = File(dir, "events.previous.log")
                    old.delete()
                    log.renameTo(old)
                }
                FileOutputStream(log, true).bufferedWriter(Charsets.UTF_8).use { it.appendLine(line) }
            }
        }
        android.util.Log.i("TouchStationFinale", line)
    }

    fun <T> guarded(context: Context, component: String, fallback: T, action: () -> T): T =
        try { action() } catch (error: Exception) {
            recordEvent(context, component, error.javaClass.simpleName + ": " + (error.message ?: "failed"))
            fallback
        }

    fun isSafeMode(context: Context) =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getBoolean(SAFE_MODE_KEY, false)

    fun setSafeMode(context: Context, enabled: Boolean) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putBoolean(SAFE_MODE_KEY, enabled).apply()
        recordEvent(context, "safe-mode", if (enabled) "Enabled" else "Disabled")
    }

    fun lifecycleStatus() = "Foreground activities: " + foreground.get().coerceAtLeast(0)

    fun snapshot(context: Context): String {
        val manager = context.getSystemService(Context.ACTIVITY_SERVICE) as? ActivityManager
        val memory = ActivityManager.MemoryInfo()
        manager?.getMemoryInfo(memory)
        val pss = runCatching { Debug.getPss() / 1024L }.getOrNull()
        val free = runCatching { StatFs(context.filesDir.absolutePath).availableBytes / (1024L * 1024L) }.getOrNull()
        val thermal = runCatching {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                (context.getSystemService(Context.POWER_SERVICE) as? PowerManager)?.currentThermalStatus?.toString() ?: "N/A"
            } else "Unsupported"
        }.getOrDefault("N/A")
        val pads = mutableListOf<String>()
        InputDevice.getDeviceIds().forEach { id ->
            runCatching {
                val device = InputDevice.getDevice(id)
                if (device != null && !device.isVirtual) {
                    pads.add(device.name + " (" + id + ")")
                }
            }
        }
        recordPss(context, pss)
        return "Lifecycle: " + lifecycleStatus() +
            "\nAvailable RAM: " + memory.availMem / (1024L * 1024L) + " MB" +
            "\nLow memory: " + memory.lowMemory +
            "\nApp PSS: " + (pss?.toString() ?: "N/A") + " MB" +
            "\nFree app storage: " + (free?.toString() ?: "N/A") + " MB" +
            "\nThermal status: " + thermal +
            "\nPhysical controllers: " + pads.joinToString().ifBlank { "None detected" } +
            "\nMemory trend: " + memoryTrend(context) +
            "\nNative PPU/SPU counters, RSX FIFO depth, GPU fences and GPU utilization: unavailable from current bridge."
    }

    private fun recordPss(context: Context, current: Long?) {
        if (current == null || current < 0) return
        runCatching {
            val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            val previous = prefs.getString(MEMORY_KEY, "").orEmpty()
            val samples = previous.split(',').mapNotNull { it.toLongOrNull() }.takeLast(7) + current
            prefs.edit().putString(MEMORY_KEY, samples.joinToString(",")).apply()
        }
    }

    fun memoryTrend(context: Context): String {
        val samples = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(MEMORY_KEY, "").orEmpty().split(',').mapNotNull { it.toLongOrNull() }
        if (samples.size < 2) return "Collecting samples"
        val delta = samples.last() - samples.first()
        return (if (delta >= 0) "PSS rose by " else "PSS fell by ") +
            kotlin.math.abs(delta) + " MB across samples (trend only; not proof of a leak)"
    }

    fun latestCrashSummary(context: Context): String {
        val file = latestCrash(context) ?: return "No Java/Kotlin crash report recorded."
        return file.name + " · " + file.length() + " bytes"
    }

    fun latestCrashReport(context: Context): String {
        val file = latestCrash(context) ?: return "No Java/Kotlin crash report recorded."
        return runCatching { file.readText(Charsets.UTF_8).takeLast(120_000) }
            .getOrElse { "Crash report read failed: " + (it.message ?: "unknown") }
    }

    private fun latestCrash(context: Context): File? =
        diagnosticsDir(context).listFiles()
            ?.filter { it.isFile && it.name.startsWith("crash-") && it.extension == "txt" }
            ?.maxByOrNull { it.lastModified() }

    private fun pruneCrashes(directory: File) {
        directory.listFiles()?.filter { it.isFile && it.name.startsWith("crash-") && it.extension == "txt" }
            ?.sortedByDescending { it.lastModified() }?.drop(5)?.forEach { it.delete() }
    }

    fun inspectDirectory(directory: File): String {
        if (!directory.exists()) return "Directory does not exist"
        if (!directory.isDirectory || !directory.canRead()) return "Directory is not readable"
        val all = directory.listFiles() ?: return "Directory listing unavailable"
        val checked = all.take(2_000)
        val empty = checked.count { it.isFile && it.length() == 0L }
        val unreadable = checked.count { it.isFile && !it.canRead() }
        return checked.size.toString() + " entries; " + empty + " empty; " + unreadable +
            " unreadable; scan cap 2,000. No files changed."
    }

    fun inspectGameUri(context: Context, uri: Uri): String = runCatching {
        var name = uri.lastPathSegment ?: "game source"
        var size = -1L
        context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE), null, null, null)
            ?.use { cursor ->
                if (cursor.moveToFirst()) {
                    val ni = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                    val si = cursor.getColumnIndex(OpenableColumns.SIZE)
                    if (ni >= 0) name = cursor.getString(ni) ?: name
                    if (si >= 0 && !cursor.isNull(si)) size = cursor.getLong(si)
                }
            }
        val descriptor = context.contentResolver.openFileDescriptor(uri, "r")
            ?: error("Content provider did not return a readable descriptor")
        val descriptorSize = descriptor.use { it.statSize }
        when {
            descriptorSize == 0L -> "Source is empty: " + name
            size > 0L -> "Readable source: " + name + " · " + size / (1024L * 1024L) + " MB"
            descriptorSize > 0L -> "Readable source: " + name + " · " + descriptorSize / (1024L * 1024L) + " MB"
            else -> "Descriptor opened: " + name + " · size unavailable"
        }
    }.getOrElse { "Source check failed: " + (it.message ?: "provider error") }

    fun sha256GameUri(context: Context, uri: Uri, maxBytes: Long): String {
        return runCatching {
            val digest = MessageDigest.getInstance("SHA-256")
            val stream = context.contentResolver.openInputStream(uri) ?: error("Source stream unavailable")
            var total = 0L
            stream.use { input ->
                val buffer = ByteArray(64 * 1024)
                while (true) {
                    val count = input.read(buffer)
                    if (count < 0) break
                    total += count
                    if (total > maxBytes) {
                        return@runCatching "Hash skipped: source exceeds " + maxBytes / (1024L * 1024L) + " MB limit"
                    }
                    digest.update(buffer, 0, count)
                }
            }
            "SHA-256 (" + total + " bytes): " + digest.digest().joinToString("") { "%02x".format(it.toInt() and 0xff) }
        }.getOrElse { "SHA-256 failed: " + (it.message ?: "source error") }
    }

    fun startupSelfTest(context: Context, settings: Settings): String {
        val checks = mutableListOf<String>()
        val issues = validateSettings(settings)
        checks += if (issues.isEmpty()) "PASS settings serialize/read back" else "FAIL settings: " + issues.joinToString()
        val cacheOk = runCatching {
            val file = File(context.cacheDir, "finale-self-test.tmp")
            file.writeText("TouchStation Finale self-test", Charsets.UTF_8)
            val valid = file.readText(Charsets.UTF_8) == "TouchStation Finale self-test"
            file.delete()
            valid
        }.getOrDefault(false)
        checks += if (cacheOk) "PASS app cache read/write" else "FAIL app cache read/write"
        val nativeDirectory = File(context.applicationInfo.nativeLibraryDir.orEmpty())
        val libraryCount = nativeDirectory.listFiles()?.count { it.isFile && it.extension == "so" } ?: 0
        checks += if (libraryCount > 0) "PASS native library directory (" + libraryCount + " .so files)"
            else "WARN native libraries not visible in nativeLibraryDir"
        checks += if (Build.SUPPORTED_ABIS.contains("arm64-v8a")) "PASS arm64-v8a ABI available"
            else "WARN arm64-v8a ABI not listed"
        checks += "INFO Android " + Build.VERSION.RELEASE + " / API " + Build.VERSION.SDK_INT
        checks += "INFO package " + context.packageName
        checks += "INFO " + latestCrashSummary(context)
        return checks.joinToString("\n")
    }

    fun validateSettings(settings: Settings): List<String> {
        val issues = mutableListOf<String>()
        val json = runCatching { settings.toJson() }.getOrElse {
            return listOf("Settings serialization failed: " + (it.message ?: "unknown"))
        }
        val decoded = runCatching { Settings.fromJson(JSONObject(json.toString())) }.getOrElse {
            return listOf("Settings read-back failed: " + (it.message ?: "unknown"))
        }
        val roundTrip = runCatching { decoded.toJson() }.getOrNull()
        if (roundTrip == null || !roundTrip.has("ps3PpuThreads") || !roundTrip.has("ps3SpuBlockSize")) {
            issues.add("PS3 settings did not survive JSON round-trip validation")
        }
        if (settings.ps3.ppuThreads !in 1..16) issues.add("PPU threads outside validation range 1–16")
        if (settings.ps3.llvmThreads !in 0..32) issues.add("LLVM threads outside validation range 0–32")
        if (settings.ps3.spuBlockSize !in 0..2) issues.add("SPU block size must be Safe, Mega or Giga")
        if (settings.ps3.shaderMode !in 0..3) issues.add("Shader mode outside known enum range")
        return issues
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
    text = replace_once(text, 'versionName = "11.0.0"', 'versionName = "TouchStation Finale"', "versionName")
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




def patch_application_reliability(app_dir: Path) -> None:
    """Initialize Finale lifecycle and crash diagnostics from Application.onCreate."""
    path = app_dir / "src/main/java/com/armsx2/Pasx2Application.kt"
    text = path.read_text(encoding="utf-8")
    if "TouchStationFinaleReliability.install(this)" in text:
        raise SystemExit("Application reliability hook is already installed")
    import_anchor = "import android.os.Build\n"
    text = replace_once(
        text,
        import_anchor,
        import_anchor + "import com.armsx2.reliability.TouchStationFinaleReliability\n",
        "Application reliability import",
    )
    text = replace_once(
        text,
        "installCrashLogging()\n",
        "installCrashLogging()\n\t\tTouchStationFinaleReliability.install(this)\n",
        "Application reliability initialization",
    )
    path.write_text(text, encoding="utf-8")



def patch_game_error_banner(app_dir: Path) -> None:
    """Record game errors and make the banner dismissible with an upward swipe."""
    path = app_dir / "src/main/java/com/armsx2/ui/emulation/GameErrorBanner.kt"
    text = path.read_text(encoding="utf-8")
    if "TouchStationFinaleErrorHistory" in text:
        raise SystemExit("Finale game-error banner patch is already present")

    text = replace_once(
        text,
        "import androidx.compose.foundation.clickable\n",
        "import androidx.compose.foundation.clickable\nimport androidx.compose.foundation.gestures.detectVerticalDragGestures\n",
        "game-error swipe gesture import",
    )
    text = replace_once(
        text,
        "import androidx.compose.runtime.mutableStateOf\n",
        "import androidx.compose.runtime.mutableStateOf\nimport androidx.compose.ui.graphics.graphicsLayer\nimport androidx.compose.ui.input.pointer.pointerInput\n",
        "game-error pointer input imports",
    )
    text = replace_once(
        text,
        "import com.armsx2.i18n.str\n",
        "import com.armsx2.i18n.str\nimport com.armsx2.ui.settings.TouchStationFinaleErrorHistory\n",
        "game-error history import",
    )
    text = replace_once(
        text,
        "    fun clear() {\n        reason.value = null\n    }",
        "    fun clear() {\n        reason.value = null\n    }\n\n    fun isCritical(error: String): Boolean = TouchStationFinaleErrorHistory.isCritical(error)",
        "game-error critical classifier",
    )
    text = replace_once(
        text,
        "        val line = error.lineSequence().firstOrNull { it.isNotBlank() }?.trim() ?: return",
        "        val fullMessage = error.trim().take(4_000)\n        val line = fullMessage.lineSequence().firstOrNull { it.isNotBlank() }?.trim() ?: return",
        "game-error full message",
    )
    text = replace_once(
        text,
        "        reason.value = line",
        "        TouchStationFinaleErrorHistory.record(fullMessage)\n        reason.value = fullMessage",
        "game-error history recording",
    )
    text = replace_once(
        text,
        "        val shown = remember(reason) { reason }.orEmpty()",
        "        val shown = remember(reason) { reason }.orEmpty()\n        val critical = GameErrorNotice.isCritical(shown)\n        val verticalDrag = remember(reason) { mutableStateOf(0f) }",
        "game-error drag state",
    )
    text = replace_once(
        text,
        "            modifier = Modifier\n                .windowInsetsPadding",
        """            modifier = Modifier
                .pointerInput(reason) {
                    detectVerticalDragGestures(
                        onVerticalDrag = { change, dragAmount ->
                            change.consume()
                            verticalDrag.value = (verticalDrag.value + dragAmount).coerceAtMost(0f)
                        },
                        onDragEnd = {
                            if (verticalDrag.value <= -72f) GameErrorNotice.clear()
                            verticalDrag.value = 0f
                        },
                        onDragCancel = { verticalDrag.value = 0f },
                    )
                }
                .graphicsLayer { translationY = verticalDrag.value }
                .windowInsetsPadding""",
        "game-error swipe modifier",
    )
    text = replace_once(
        text,
        "                Text(shown, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)",
        """                Text(shown, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text(
                    TouchStationFinaleErrorHistory.explanation(shown),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Text(
                    if (critical) "Critical error recorded. Swiping only hides this notice; it does not resume the game."
                    else "Swipe this notice upward to dismiss it. The event remains in error history.",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )""",
        "game-error explanation and safety copy",
    )
    path.write_text(text, encoding="utf-8")


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
    patch_game_error_banner(app_dir)
    reliability_dir = app_dir / "src/main/java/com/armsx2/reliability"
    reliability_dir.mkdir(parents=True, exist_ok=True)
    reliability_path = reliability_dir / "TouchStationFinaleReliability.kt"
    if reliability_path.exists():
        raise SystemExit("TouchStation Finale reliability module already exists; refusing to overwrite")
    reliability_path.write_text(RELIABILITY_KOTLIN_SOURCE, encoding="utf-8")
    patch_application_reliability(app_dir)

    required_markers = [
        "Update official compatibility database",
        "exact normalized PS3 title ID",
        "Stable session (10+ min)",
        "GTA IV per-game profile",
        "SPU XFloat",
        "safe SPU block mode",
        "Export Finale diagnostic report",
        "Download TouchStation.log",
        "Share TouchStation.log",
        "Core@@RSX FIFO Fetch Accuracy",
        "Video@@Driver Wake-Up Delay",
        "Ordered & Atomic",
        "touchStationFinaleApplyFifoRecoveryProfile",
        "TouchStationFinaleErrorHistory.fifoFailureCount()",
        "Download TouchStation.log",
        "Physical controllers",
        "Engine initialized",
        "GPU utilization",
    ]
    missing = [marker for marker in required_markers if marker not in KOTLIN_SOURCE]
    reliability_markers = [
        "registerActivityLifecycleCallbacks",
        "setDefaultUncaughtExceptionHandler",
        "MAX_LOG_BYTES",
        "inspectGameUri",
        "sha256GameUri",
        "validateSettings",
        "memoryTrend",
    ]
    missing.extend(
        "reliability module: " + marker
        for marker in reliability_markers
        if marker not in RELIABILITY_KOTLIN_SOURCE
    )
    application_source = (app_dir / "src/main/java/com/armsx2/Pasx2Application.kt").read_text(encoding="utf-8")
    if "TouchStationFinaleReliability.install(this)" not in application_source:
        missing.append("Application reliability initialization")
    # The URL and some explanatory copy intentionally live in different parts
    # of the template, so test the exact API route and title-ID matching separately.
    if "https://rpcs3.net/compatibility/?api=v1&export" not in KOTLIN_SOURCE:
        missing.append("Official compatibility API endpoint")
    if "touchStationFinaleNormaliseId" not in KOTLIN_SOURCE:
        missing.append("Exact title-ID normalizer")
    if missing:
        raise SystemExit("Missing Finale source markers: " + ", ".join(missing))
    print("Applied TouchStation Finale suite, modular crash/lifecycle diagnostics, bounded logs, and file/settings validation.")


if __name__ == "__main__":
    main()
