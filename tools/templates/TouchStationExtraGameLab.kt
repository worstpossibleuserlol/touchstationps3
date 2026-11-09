package com.armsx2.ui.settings

import android.app.ActivityManager
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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.edit
import com.armsx2.config.Settings
import com.armsx2.config.SettingsScope
import com.armsx2.reliability.TouchStationFinaleReliability
import com.armsx2.runtime.MainActivityRuntime
import com.armsx2.ui.InGameOverlay
import com.armsx3.core.ARMSX3
import org.json.JSONArray
import org.json.JSONObject
import java.security.MessageDigest
import java.util.Locale

private const val GAME_LAB_PREFS = "touchstation-extra-game-lab"

private data class GameLabDeviceSnapshot(
    val cpuCores: Int,
    val availableRamMb: Long,
    val appPssMb: Int,
    val freeStorageMb: Long,
    val thermalStatus: Int?,
    val soc: String,
    val nativeReady: Boolean,
)

private fun gameLabId(serial: String?): String =
    serial.orEmpty().filter { it.isLetterOrDigit() }.uppercase(Locale.ROOT).ifBlank { "unknown" }

private fun gameLabDeviceKey(): String =
    listOf(Build.MANUFACTURER, Build.MODEL, Build.HARDWARE, Build.SUPPORTED_ABIS.firstOrNull().orEmpty())
        .joinToString("|").lowercase(Locale.ROOT)
        .map { if (it.isLetterOrDigit()) it else '_' }.joinToString("").take(100)

private fun gameLabSnapshot(context: Context): GameLabDeviceSnapshot {
    val manager = context.getSystemService(Context.ACTIVITY_SERVICE) as? ActivityManager
    val memory = ActivityManager.MemoryInfo()
    val available = runCatching {
        if (manager == null) -1L else {
            manager.getMemoryInfo(memory)
            memory.availMem / (1024L * 1024L)
        }
    }.getOrDefault(-1L)
    val pss = runCatching {
        val info = Debug.MemoryInfo()
        Debug.getMemoryInfo(info)
        info.totalPss / 1024
    }.getOrDefault(-1)
    val storage = runCatching {
        StatFs(context.filesDir.absolutePath).availableBytes / (1024L * 1024L)
    }.getOrDefault(-1L)
    val thermal = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) runCatching {
        (context.getSystemService(Context.POWER_SERVICE) as? PowerManager)?.currentThermalStatus
    }.getOrNull() else null
    val soc = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
        listOf(Build.SOC_MANUFACTURER, Build.SOC_MODEL)
            .filter { it.isNotBlank() && !it.equals("unknown", true) }.joinToString(" ")
            .ifBlank { Build.HARDWARE.ifBlank { "Not reported" } }
    } else Build.HARDWARE.ifBlank { "Not reported" }
    return GameLabDeviceSnapshot(
        cpuCores = Runtime.getRuntime().availableProcessors().coerceAtLeast(1),
        availableRamMb = available,
        appPssMb = pss,
        freeStorageMb = storage,
        thermalStatus = thermal,
        soc = soc,
        nativeReady = runCatching { ARMSX3.initialized && MainActivityRuntime.nativeReady.value }.getOrDefault(false),
    )
}

private fun gameLabThermalLabel(status: Int?): String = when (status) {
    null -> "N/A"
    PowerManager.THERMAL_STATUS_NONE -> "Normal"
    PowerManager.THERMAL_STATUS_LIGHT -> "Light"
    PowerManager.THERMAL_STATUS_MODERATE -> "Moderate"
    PowerManager.THERMAL_STATUS_SEVERE -> "Severe"
    PowerManager.THERMAL_STATUS_CRITICAL -> "Critical"
    PowerManager.THERMAL_STATUS_EMERGENCY -> "Emergency"
    PowerManager.THERMAL_STATUS_SHUTDOWN -> "Shutdown"
    else -> "Unknown (" + status + ")"
}

private fun gameLabSettingsHash(settings: Settings): String {
    val json = settings.toJson()
    val keys = mutableListOf<String>()
    val iterator = json.keys()
    while (iterator.hasNext()) keys += iterator.next()
    val canonical = keys.sorted().joinToString("\n") { key -> key + "=" + json.opt(key).toString() }
    return MessageDigest.getInstance("SHA-256").digest(canonical.toByteArray(Charsets.UTF_8))
        .joinToString("") { "%02x".format(Locale.ROOT, it.toInt() and 0xff) }
}

private fun gameLabHistoryKey(serial: String?): String =
    "history." + gameLabDeviceKey() + "." + gameLabId(serial)

private fun gameLabActiveKey(serial: String?): String =
    "active." + gameLabDeviceKey() + "." + gameLabId(serial)

private fun gameLabProfileKey(serial: String?): String =
    "profile." + gameLabDeviceKey() + "." + gameLabId(serial)

private fun gameLabReadHistory(context: Context, serial: String?): JSONArray = runCatching {
    JSONArray(context.getSharedPreferences(GAME_LAB_PREFS, Context.MODE_PRIVATE)
        .getString(gameLabHistoryKey(serial), "[]") ?: "[]")
}.getOrDefault(JSONArray())

private fun gameLabReadActive(context: Context, serial: String?): JSONObject? = runCatching {
    context.getSharedPreferences(GAME_LAB_PREFS, Context.MODE_PRIVATE)
        .getString(gameLabActiveKey(serial), null)?.let { JSONObject(it) }
}.getOrNull()

private fun gameLabEvent(stage: String, settings: Settings, snapshot: GameLabDeviceSnapshot): JSONObject =
    JSONObject()
        .put("timestamp", System.currentTimeMillis())
        .put("stage", stage)
        .put("settingsSha256", gameLabSettingsHash(settings))
        .put("availableRamMb", snapshot.availableRamMb)
        .put("appPssMb", snapshot.appPssMb)
        .put("freeStorageMb", snapshot.freeStorageMb)
        .put("thermal", gameLabThermalLabel(snapshot.thermalStatus))
        .put("nativeEngineInitialized", ARMSX3.initialized)
        .put("nativeRuntimeReady", snapshot.nativeReady)

private fun gameLabStart(
    context: Context, serial: String?, title: String, settings: Settings, snapshot: GameLabDeviceSnapshot,
): String {
    if (serial.isNullOrBlank()) return "Select a game with a title ID before starting a test."
    val prefs = context.getSharedPreferences(GAME_LAB_PREFS, Context.MODE_PRIVATE)
    if (prefs.contains(gameLabActiveKey(serial))) return "An unfinished test already exists for this game on this device."
    val now = System.currentTimeMillis()
    val events = JSONArray().put(gameLabEvent("Test session started by user", settings, snapshot))
    val session = JSONObject()
        .put("startedAt", now)
        .put("gameId", gameLabId(serial))
        .put("title", title)
        .put("device", Build.MANUFACTURER + " " + Build.MODEL)
        .put("deviceKey", gameLabDeviceKey())
        .put("soc", snapshot.soc)
        .put("abi", Build.SUPPORTED_ABIS.firstOrNull().orEmpty())
        .put("settingsSha256", gameLabSettingsHash(settings))
        .put("events", events)
    prefs.edit().putString(gameLabActiveKey(serial), session.toString()).apply()
    return "Started a user-controlled compatibility test record. It does not launch or benchmark the game automatically."
}

private fun gameLabRecord(
    context: Context, serial: String?, stage: String, settings: Settings, snapshot: GameLabDeviceSnapshot,
): String {
    val prefs = context.getSharedPreferences(GAME_LAB_PREFS, Context.MODE_PRIVATE)
    val active = gameLabReadActive(context, serial) ?: return "Start a test session first."
    val events = active.optJSONArray("events") ?: JSONArray()
    if (events.length() >= 40) return "This test already contains the maximum of 40 observations."
    events.put(gameLabEvent(stage, settings, snapshot))
    active.put("events", events)
    prefs.edit().putString(gameLabActiveKey(serial), active.toString()).apply()
    return "Recorded user observation: " + stage
}

private fun gameLabFinish(
    context: Context, serial: String?, result: String, settings: Settings, snapshot: GameLabDeviceSnapshot,
): String {
    val prefs = context.getSharedPreferences(GAME_LAB_PREFS, Context.MODE_PRIVATE)
    val active = gameLabReadActive(context, serial) ?: return "There is no unfinished test to finish."
    val events = active.optJSONArray("events") ?: JSONArray()
    if (events.length() < 40) events.put(gameLabEvent("Test finished: " + result, settings, snapshot))
    val start = active.optLong("startedAt", System.currentTimeMillis())
    active.put("events", events)
    active.put("finishedAt", System.currentTimeMillis())
    active.put("durationMs", (System.currentTimeMillis() - start).coerceAtLeast(0L))
    active.put("result", result)
    val old = gameLabReadHistory(context, serial)
    val next = JSONArray()
    for (index in (old.length() - 19).coerceAtLeast(0) until old.length()) {
        old.optJSONObject(index)?.let { next.put(it) }
    }
    next.put(active)
    prefs.edit().putString(gameLabHistoryKey(serial), next.toString())
        .remove(gameLabActiveKey(serial)).apply()
    return "Saved test result: " + result + ". This is user-recorded evidence, not an emulator compatibility certification."
}

private fun gameLabRecover(
    context: Context, serial: String?, settings: Settings, snapshot: GameLabDeviceSnapshot,
): String {
    val active = gameLabReadActive(context, serial) ?: return "No unfinished test was found."
    active.put("interruptionNote", "The app was reopened before the test was finished; the cause is unknown and is not proof of a guest-game crash.")
    context.getSharedPreferences(GAME_LAB_PREFS, Context.MODE_PRIVATE)
        .edit().putString(gameLabActiveKey(serial), active.toString()).apply()
    return gameLabFinish(context, serial, "inconclusive / interrupted", settings, snapshot)
}

private fun gameLabHistorySummary(context: Context, serial: String?): String {
    val history = gameLabReadHistory(context, serial)
    if (history.length() == 0) return "No repeatable test sessions have been saved for this game on this device."
    var stable = 0
    var failed = 0
    for (index in 0 until history.length()) {
        when (history.optJSONObject(index)?.optString("result")) {
            "stable" -> stable++
            "failed" -> failed++
        }
    }
    return history.length().toString() + " saved sessions · " + stable + " user-marked stable · " +
        failed + " user-marked failed · remaining inconclusive. Not a compatibility percentage."
}

private fun gameLabRegressionSummary(context: Context, serial: String?, settings: Settings): String {
    val history = gameLabReadHistory(context, serial)
    val currentHash = gameLabSettingsHash(settings)
    val matching = (0 until history.length()).mapNotNull { history.optJSONObject(it) }
        .filter { it.optString("settingsSha256") == currentHash }
    if (matching.size < 2) return "Need at least two saved sessions with the exact current settings fingerprint."
    val latest = matching.last()
    val hadStableBefore = matching.dropLast(1).any { it.optString("result") == "stable" }
    return if (latest.optString("result") == "failed" && hadStableBefore)
        "Possible same-settings regression: a later session was marked failed after an earlier session was marked stable."
    else "No same-settings failure-after-stable pattern is recorded."
}

private fun gameLabSaveProfile(context: Context, serial: String?, settings: Settings): String {
    if (serial.isNullOrBlank()) return "Select a game before saving a per-game profile."
    return runCatching {
        context.getSharedPreferences(GAME_LAB_PREFS, Context.MODE_PRIVATE).edit()
            .putString(gameLabProfileKey(serial), settings.toJson().toString()).apply()
        "Saved a device-specific settings snapshot for " + gameLabId(serial) + "."
    }.getOrElse { "Profile save failed: " + (it.message ?: "unknown error") }
}

private fun gameLabProfileDiff(context: Context, serial: String?, settings: Settings): String {
    val raw = context.getSharedPreferences(GAME_LAB_PREFS, Context.MODE_PRIVATE)
        .getString(gameLabProfileKey(serial), null) ?: return "No saved profile exists for this game on this device."
    return runCatching {
        val saved = JSONObject(raw)
        val current = settings.toJson()
        val keys = mutableSetOf<String>()
        val iterator = current.keys()
        while (iterator.hasNext()) keys += iterator.next()
        val changed = keys.sorted().filter { saved.opt(it)?.toString() != current.opt(it)?.toString() }
        if (changed.isEmpty()) "Saved profile and current settings match at the top-level JSON fields."
        else "Different fields: " + changed.take(12).joinToString() +
            if (changed.size > 12) " (+" + (changed.size - 12) + " more)" else ""
    }.getOrDefault("Saved profile could not be compared.")
}

private fun gameLabLoadProfile(context: Context, serial: String?): Settings? = runCatching {
    val raw = context.getSharedPreferences(GAME_LAB_PREFS, Context.MODE_PRIVATE)
        .getString(gameLabProfileKey(serial), null) ?: return null
    Settings.fromJson(JSONObject(raw))
}.getOrNull()

private fun gameLabCandidate(settings: Settings, snapshot: GameLabDeviceSnapshot, gtaIv: Boolean): Settings {
    val severeThermal = snapshot.thermalStatus != null &&
        snapshot.thermalStatus >= PowerManager.THERMAL_STATUS_SEVERE
    val limitedMemory = snapshot.availableRamMb in 0L..2048L
    val ppuThreads = if (gtaIv || limitedMemory || severeThermal) 1
        else minOf(2, snapshot.cpuCores).coerceAtLeast(1)
    return settings.copy(
        ps3 = settings.ps3.copy(
            ppuThreads = ppuThreads,
            llvmThreads = 1,
            preferredSpuThreads = 0,
            spuBlockSize = 0,
            spuXFloat = 0,
            shaderMode = 1,
            msaaMode = 0,
            spuCache = true,
            llvmPrecompile = snapshot.availableRamMb >= 3072L && !severeThermal,
        ),
    )
}

private fun gameLabApply(candidate: Settings, onApply: (Settings) -> Boolean): String {
    val issues = TouchStationFinaleReliability.validateSettings(candidate)
    if (issues.isNotEmpty()) return "Settings rejected by validation: " + issues.take(3).joinToString()
    return if (runCatching { onApply(candidate) }.getOrDefault(false))
        "Settings applied and the settings read-back callback confirmed the saved values."
    else "Settings were not confirmed. The previous settings should be checked before another launch."
}

private fun gameLabShare(context: Context, subject: String, report: String) {
    runCatching {
        val send = Intent(Intent.ACTION_SEND).apply {
            type = "text/plain"
            putExtra(Intent.EXTRA_SUBJECT, subject)
            putExtra(Intent.EXTRA_TEXT, report)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        context.startActivity(Intent.createChooser(send, "Share TouchStation Game Lab report")
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    }
}

@Composable
fun TouchStationExtraGameLabSuite(settings: Settings, onApply: (Settings) -> Boolean) {
    val context = LocalContext.current
    val game = MainActivityRuntime.currentGame.value
    val serial = game?.serial?.takeIf { it.isNotBlank() }
        ?: game?.settingsKey?.takeIf { it.isNotBlank() }
    val gtaIv = game?.serial?.equals("BLES00229", ignoreCase = true) == true
    val title = game?.title?.takeIf { it.isNotBlank() } ?: "Untitled / unavailable"
    val gameScope = InGameOverlay.settingsScope.value == SettingsScope.Game
    val snapshot = remember(context) { mutableStateOf(gameLabSnapshot(context)) }
    val message = remember { mutableStateOf("No Game Lab action performed.") }
    val prefs = remember(context) { context.getSharedPreferences(GAME_LAB_PREFS, Context.MODE_PRIVATE) }
    val active = remember(serial, prefs) { mutableStateOf(gameLabReadActive(context, serial)?.toString()) }
    val savedProfile = remember(serial, prefs) {
        mutableStateOf(prefs.getString(gameLabProfileKey(serial), null))
    }
    val canApply = !serial.isNullOrBlank() && gameScope
    val currentHash = gameLabSettingsHash(settings)
    val activeStatus = if (active.value == null) "No unfinished test session."
        else "An unfinished test exists. Finish it or mark it interrupted before starting another."

    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(18.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(9.dp)) {
            Text("TouchStation Extra · Game Compatibility Lab", style = MaterialTheme.typography.titleLarge)
            Text(
                "Repeatable per-game test records, settings fingerprints, cautious device-aware profiles and diagnostic export. Manual observations are not native guest-game telemetry.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            Text("Selected game: " + title + " · ID: " + (serial ?: "not available"))
            Text("Device: " + snapshot.value.soc + " · " + snapshot.value.cpuCores + " CPU cores · " +
                snapshot.value.availableRamMb + " MB Android-reported available RAM")
            Text("App PSS: " + snapshot.value.appPssMb + " MB · app-private free storage: " +
                snapshot.value.freeStorageMb + " MB · thermal: " + gameLabThermalLabel(snapshot.value.thermalStatus))
            Text("Native engine ready: " + snapshot.value.nativeReady +
                " · settings scope: " + if (gameScope) "per-game" else "global")
            Text("Current settings SHA-256: " + currentHash.take(16) + "…")
            OutlinedButton(
                onClick = {
                    snapshot.value = gameLabSnapshot(context)
                    message.value = "Refreshed Android device snapshot."
                },
                modifier = Modifier.fillMaxWidth(),
            ) { Text("Refresh device readiness snapshot") }

            Text("Device-aware profile", style = MaterialTheme.typography.titleMedium)
            Text(
                "The profile uses one PPU thread for GTA IV, low available RAM or severe thermal pressure; it uses one LLVM thread, conservative SPU settings and disables precompile when available RAM is below 3 GiB. This is a cautious starting point, not a performance guarantee.",
                style = MaterialTheme.typography.bodySmall,
            )
            Button(
                onClick = {
                    message.value = if (!gameScope) "Select per-game settings scope before applying a game profile."
                    else gameLabApply(gameLabCandidate(settings, snapshot.value, false), onApply)
                },
                enabled = canApply,
                modifier = Modifier.fillMaxWidth(),
            ) { Text("Apply device-aware conservative profile") }

            if (gtaIv) {
                Text("GTA IV profile · BLES00229", style = MaterialTheme.typography.titleMedium)
                Text(
                    "Exact title-ID match only. Uses a low-memory conservative PPU/SPU/RSX-settings starting profile. It does not add native GTA IV fixes and has not been validated as playable on this handset.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Button(
                    onClick = {
                        message.value = if (!gameScope) "Select per-game settings scope before applying the GTA IV profile."
                        else gameLabApply(gameLabCandidate(settings, snapshot.value, true), onApply)
                    },
                    enabled = canApply,
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Apply GTA IV conservative test profile") }
            }

            Text("Per-game settings snapshot", style = MaterialTheme.typography.titleMedium)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(
                    onClick = {
                        message.value = gameLabSaveProfile(context, serial, settings)
                        savedProfile.value = prefs.getString(gameLabProfileKey(serial), null)
                    },
                    enabled = !serial.isNullOrBlank(),
                    modifier = Modifier.weight(1f),
                ) { Text("Save current profile") }
                OutlinedButton(
                    onClick = {
                        val candidate = gameLabLoadProfile(context, serial)
                        message.value = when {
                            !gameScope -> "Select per-game settings scope before restoring a profile."
                            candidate == null -> "No valid saved profile exists."
                            else -> gameLabApply(candidate, onApply)
                        }
                    },
                    enabled = canApply && savedProfile.value != null,
                    modifier = Modifier.weight(1f),
                ) { Text("Restore saved profile") }
            }
            OutlinedButton(
                onClick = { message.value = gameLabProfileDiff(context, serial, settings) },
                enabled = savedProfile.value != null,
                modifier = Modifier.fillMaxWidth(),
            ) { Text("Compare saved profile with current settings") }

            Text("Repeatable launch test", style = MaterialTheme.typography.titleMedium)
            Text(activeStatus, style = MaterialTheme.typography.bodySmall)
            Button(
                onClick = {
                    message.value = gameLabStart(context, serial, title, settings, snapshot.value)
                    active.value = gameLabReadActive(context, serial)?.toString()
                },
                enabled = !serial.isNullOrBlank() && active.value == null,
                modifier = Modifier.fillMaxWidth(),
            ) { Text("Start test record before launching game") }

            listOf(
                "Boot started (user observed)",
                "Main menu reached",
                "Gameplay reached",
                "Stable session (10+ min)",
                "Freeze / stalled boot observed",
                "App returned to Android home (observed)",
                "Stuck on stopping (observed)",
                "Clean exit observed",
            ).chunked(2).forEach { group ->
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    group.forEach { stage ->
                        OutlinedButton(
                            onClick = {
                                message.value = gameLabRecord(context, serial, stage, settings, gameLabSnapshot(context))
                                active.value = gameLabReadActive(context, serial)?.toString()
                            },
                            enabled = active.value != null,
                            modifier = Modifier.weight(1f),
                        ) { Text(stage, style = MaterialTheme.typography.labelSmall) }
                    }
                }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(
                    onClick = {
                        message.value = gameLabFinish(context, serial, "stable", settings, gameLabSnapshot(context))
                        active.value = gameLabReadActive(context, serial)?.toString()
                    },
                    enabled = active.value != null,
                    modifier = Modifier.weight(1f),
                ) { Text("Finish: stable") }
                OutlinedButton(
                    onClick = {
                        message.value = gameLabFinish(context, serial, "failed", settings, gameLabSnapshot(context))
                        active.value = gameLabReadActive(context, serial)?.toString()
                    },
                    enabled = active.value != null,
                    modifier = Modifier.weight(1f),
                ) { Text("Finish: failed") }
            }
            OutlinedButton(
                onClick = {
                    message.value = gameLabFinish(context, serial, "inconclusive", settings, gameLabSnapshot(context))
                    active.value = gameLabReadActive(context, serial)?.toString()
                },
                enabled = active.value != null,
                modifier = Modifier.fillMaxWidth(),
            ) { Text("Finish: inconclusive") }
            OutlinedButton(
                onClick = {
                    message.value = gameLabRecover(context, serial, settings, gameLabSnapshot(context))
                    active.value = gameLabReadActive(context, serial)?.toString()
                },
                enabled = active.value != null,
                modifier = Modifier.fillMaxWidth(),
            ) { Text("Mark interrupted · cause unknown") }

            Text("Saved evidence", style = MaterialTheme.typography.titleMedium)
            Text(gameLabHistorySummary(context, serial), style = MaterialTheme.typography.bodySmall)
            Text(gameLabRegressionSummary(context, serial, settings), style = MaterialTheme.typography.bodySmall)
            OutlinedButton(
                onClick = {
                    val history = gameLabReadHistory(context, serial)
                    val report = buildString {
                        appendLine("TouchStation Extra · Game Compatibility Lab")
                        appendLine("Game: " + title + " / " + (serial ?: "N/A"))
                        appendLine("Device: " + Build.MANUFACTURER + " " + Build.MODEL + " / " + snapshot.value.soc)
                        appendLine("ABI: " + Build.SUPPORTED_ABIS.firstOrNull())
                        appendLine("Android: " + Build.VERSION.RELEASE + " / API " + Build.VERSION.SDK_INT)
                        appendLine("Current settings SHA-256: " + currentHash)
                        appendLine("Native engine ready: " + snapshot.value.nativeReady)
                        appendLine("Available RAM: " + snapshot.value.availableRamMb + " MB")
                        appendLine("App PSS: " + snapshot.value.appPssMb + " MB")
                        appendLine("Thermal: " + gameLabThermalLabel(snapshot.value.thermalStatus))
                        appendLine("History: " + gameLabHistorySummary(context, serial))
                        appendLine("Regression: " + gameLabRegressionSummary(context, serial, settings))
                        appendLine("Saved sessions (latest 5):")
                        for (index in (history.length() - 5).coerceAtLeast(0) until history.length()) {
                            val item = history.optJSONObject(index) ?: continue
                            appendLine(item.optString("gameId") + " · " + item.optString("result") +
                                " · " + item.optLong("durationMs") + " ms · settings " +
                                item.optString("settingsSha256").take(16))
                        }
                        appendLine("Observations are user-entered. Android process exits are not proof of a PS3 guest crash.")
                        appendLine("Native PPU/SPU/RSX counters, FIFO/shader traces and guest crash callbacks remain unavailable unless exported by the pinned native core.")
                    }
                    gameLabShare(context, "TouchStation Game Compatibility Lab report", report)
                    message.value = "Opened Android share sheet for the Game Lab report."
                },
                modifier = Modifier.fillMaxWidth(),
            ) { Text("Share game compatibility report") }

            Text(message.value, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.primary)
            Text(
                "Important: test results describe manual observations on this device and settings fingerprint. They are not proof that a game is universally compatible or that GTA IV will run.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}
