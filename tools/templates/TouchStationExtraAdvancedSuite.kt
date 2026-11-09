package com.armsx2.ui.settings

import android.app.Activity
import android.app.ActivityManager
import android.app.ApplicationExitInfo
import android.content.Context
import android.content.ContextWrapper
import android.content.Intent
import android.hardware.display.DisplayManager
import android.os.BatteryManager
import android.os.Build
import android.os.PowerManager
import android.os.StatFs
import android.view.Display
import android.view.InputDevice
import android.view.WindowManager
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.edit
import com.armsx2.config.Settings
import com.armsx2.config.SettingsScope
import com.armsx2.runtime.MainActivityRuntime
import com.armsx2.ui.InGameOverlay
import com.armsx3.core.ARMSX3
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.Locale

private const val EXTRA_ADVANCED_PREFS = "touchstation-extra-advanced"
private const val EXTRA_SETTINGS_HISTORY_KEY = "settingsHistory"

object TouchStationExtraSettingsHistory {
    fun record(context: Context, scope: SettingsScope, serial: String?, before: Settings, after: Settings) {
        runCatching {
            val oldJson = before.toJson()
            val newJson = after.toJson()
            val keys = newJson.keys()
            val changed = mutableListOf<String>()
            while (keys.hasNext()) {
                val key = keys.next()
                if (oldJson.opt(key)?.toString() != newJson.opt(key)?.toString()) changed += key
            }
            if (changed.isEmpty()) return
            val prefs = context.getSharedPreferences(EXTRA_ADVANCED_PREFS, Context.MODE_PRIVATE)
            val current = runCatching {
                JSONArray(prefs.getString(EXTRA_SETTINGS_HISTORY_KEY, "[]") ?: "[]")
            }.getOrDefault(JSONArray())
            val next = JSONArray()
            for (index in (current.length() - 38).coerceAtLeast(0) until current.length()) {
                current.optJSONObject(index)?.let { next.put(it) }
            }
            next.put(
                JSONObject()
                    .put("timestamp", System.currentTimeMillis())
                    .put("scope", scope.name)
                    .put("serial", serial.orEmpty())
                    .put("changed", changed.take(40).joinToString(","))
            )
            prefs.edit().putString(EXTRA_SETTINGS_HISTORY_KEY, next.toString()).apply()
        }
    }

    fun summary(context: Context): String {
        val events = runCatching {
            JSONArray(context.getSharedPreferences(EXTRA_ADVANCED_PREFS, Context.MODE_PRIVATE)
                .getString(EXTRA_SETTINGS_HISTORY_KEY, "[]") ?: "[]")
        }.getOrDefault(JSONArray())
        if (events.length() == 0) return "No settings changes recorded yet."
        val latest = events.optJSONObject(events.length() - 1) ?: return "Settings history unavailable."
        return events.length().toString() + " changes; latest " + latest.optString("scope") +
            " / " + latest.optString("serial", "global").ifBlank { "global" } +
            "; changed: " + latest.optString("changed", "N/A")
    }
}

private fun extraAdvancedActivity(context: Context): Activity? {
    var current: Context? = context
    while (current != null) {
        if (current is Activity) return current
        current = (current as? ContextWrapper)?.baseContext
    }
    return null
}

private fun extraAdvancedDeviceId(): String =
    listOf(Build.MANUFACTURER, Build.MODEL, Build.HARDWARE, Build.SUPPORTED_ABIS.firstOrNull().orEmpty())
        .joinToString("|").lowercase(Locale.ROOT)
        .map { if (it.isLetterOrDigit()) it else '_' }.joinToString("").take(100)

private fun extraAdvancedGameId(serial: String?): String =
    serial.orEmpty().filter { it.isLetterOrDigit() }.uppercase(Locale.ROOT).ifBlank { "unknown" }

private fun extraAdvancedGameKey(serial: String?): String =
    "game-tests." + extraAdvancedDeviceId() + "." + extraAdvancedGameId(serial)

private fun extraAdvancedReadTests(context: Context, serial: String?): JSONArray =
    runCatching {
        JSONArray(context.getSharedPreferences(EXTRA_ADVANCED_PREFS, Context.MODE_PRIVATE)
            .getString(extraAdvancedGameKey(serial), "[]") ?: "[]")
    }.getOrDefault(JSONArray())

private fun extraAdvancedRecordTest(context: Context, serial: String?, stage: String) {
    if (serial.isNullOrBlank()) return
    val prefs = context.getSharedPreferences(EXTRA_ADVANCED_PREFS, Context.MODE_PRIVATE)
    val old = extraAdvancedReadTests(context, serial)
    val next = JSONArray()
    for (index in (old.length() - 29).coerceAtLeast(0) until old.length()) {
        old.optJSONObject(index)?.let { next.put(it) }
    }
    next.put(
        JSONObject()
            .put("timestamp", System.currentTimeMillis())
            .put("stage", stage)
            .put("device", Build.MODEL)
            .put("hardware", Build.HARDWARE)
            .put("abi", Build.SUPPORTED_ABIS.firstOrNull().orEmpty())
            .put("build", "TouchStation Extra")
    )
    prefs.edit().putString(extraAdvancedGameKey(serial), next.toString()).apply()
}

private fun extraAdvancedTestSummary(context: Context, serial: String?): String {
    val tests = extraAdvancedReadTests(context, serial)
    if (tests.length() == 0) return "No handset observations recorded."
    val good = (0 until tests.length()).count {
        tests.optJSONObject(it)?.optString("stage") == "Stable session (10+ min)"
    }
    val failed = (0 until tests.length()).count {
        tests.optJSONObject(it)?.optString("stage") in setOf("Crash / failed boot", "Freeze / stalled boot")
    }
    val score = if (good + failed == 0) null else good * 100 / (good + failed)
    return tests.length().toString() + " observations; " + good + " stable; " + failed + " failures; " +
        (score?.let { "$it% observation index (not a compatibility rating)" } ?: "more evidence needed")
}

private fun extraAdvancedCrashHistory(context: Context, serial: String?): String {
    val tests = extraAdvancedReadTests(context, serial)
    val crashes = (0 until tests.length()).mapNotNull { tests.optJSONObject(it) }
        .filter { it.optString("stage") in setOf("Crash / failed boot", "Freeze / stalled boot") }
    if (crashes.isEmpty()) return "No user-recorded crashes/freezes for this game on this device."
    val latest = crashes.last()
    return crashes.size.toString() + " user-recorded failures; latest " + latest.optString("stage") +
        " at " + android.text.format.DateFormat.format("yyyy-MM-dd HH:mm", latest.optLong("timestamp"))
}

private fun extraAdvancedRegression(context: Context, serial: String?): String {
    val tests = extraAdvancedReadTests(context, serial)
    val stages = (0 until tests.length()).mapNotNull { tests.optJSONObject(it)?.optString("stage") }
    val latest = stages.lastOrNull() ?: return "No comparison evidence yet."
    val failure = latest == "Crash / failed boot" || latest == "Freeze / stalled boot"
    val priorPlay = stages.dropLast(1).any { it == "Gameplay reached" || it == "Stable session (10+ min)" }
    return if (failure && priorPlay) "Possible regression: latest observation failed after an earlier gameplay/stable observation."
    else "No recorded failure-after-success regression pattern."
}

private fun extraAdvancedExitReason(reason: Int): String = when (reason) {
    ApplicationExitInfo.REASON_ANR -> "ANR / app not responding"
    ApplicationExitInfo.REASON_CRASH -> "Java/Kotlin app crash"
    ApplicationExitInfo.REASON_CRASH_NATIVE -> "Native app crash"
    ApplicationExitInfo.REASON_LOW_MEMORY -> "Android low-memory termination"
    ApplicationExitInfo.REASON_EXCESSIVE_RESOURCE_USAGE -> "Excessive resource use"
    ApplicationExitInfo.REASON_USER_REQUESTED -> "User-requested termination"
    ApplicationExitInfo.REASON_USER_STOPPED -> "User stopped app"
    ApplicationExitInfo.REASON_EXIT_SELF -> "App exited itself"
    ApplicationExitInfo.REASON_DEPENDENCY_DIED -> "Dependent process died"
    ApplicationExitInfo.REASON_SIGNALED -> "Process terminated by signal"
    else -> "Other / unknown process exit"
}

private fun extraAdvancedProcessExits(context: Context): String {
    if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return "Historical exit reasons require Android 11+."
    return runCatching {
        val manager = context.getSystemService(Context.ACTIVITY_SERVICE) as? ActivityManager
            ?: return@runCatching "Android ActivityManager unavailable."
        val exits = manager.getHistoricalProcessExitReasons(context.packageName, 0, 10)
        if (exits.isEmpty()) return@runCatching "No historical app-process exit records returned by Android."
        exits.take(5).joinToString("\n") { info ->
            extraAdvancedExitReason(info.reason) + " · " +
                android.text.format.DateFormat.format("yyyy-MM-dd HH:mm", info.timestamp) +
                " · " + info.description.orEmpty().take(100)
        }
    }.getOrDefault("Historical exit reason query unavailable.")
}

private fun extraAdvancedLaunchRisk(context: Context): String {
    val manager = context.getSystemService(Context.ACTIVITY_SERVICE) as? ActivityManager
    val memory = ActivityManager.MemoryInfo()
    runCatching { manager?.getMemoryInfo(memory) }
    val storage = runCatching { StatFs(context.filesDir.absolutePath).availableBytes }.getOrDefault(-1L)
    val thermal = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) runCatching {
        (context.getSystemService(Context.POWER_SERVICE) as? PowerManager)?.currentThermalStatus
    }.getOrNull() else null
    val risks = mutableListOf<String>()
    if (memory.lowMemory || memory.availMem <= memory.threshold) risks += "Android reports low memory"
    if (storage in 0L until 1024L * 1024L * 1024L) risks += "less than 1 GiB app-private storage free"
    if (thermal != null && thermal >= PowerManager.THERMAL_STATUS_SEVERE) risks += "elevated thermal severity"
    if (TouchStationExtraCrashLoopGuard.status(context).startsWith("SAFE MODE")) risks += "recent app crash loop"
    if (!ARMSX3.initialized || !MainActivityRuntime.nativeReady.value) risks += "native runtime not ready"
    return if (risks.isEmpty()) "No current Android readiness warning. This is not a prediction that a game will run."
    else risks.joinToString("; ") + ". Risk indicators only; no crash probability is calculated."
}

private fun extraAdvancedThermal(context: Context): String {
    if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) return "N/A on this Android version"
    val value = runCatching {
        (context.getSystemService(Context.POWER_SERVICE) as? PowerManager)?.currentThermalStatus
    }.getOrNull() ?: return "N/A"
    return when (value) {
        PowerManager.THERMAL_STATUS_NONE -> "Normal"
        PowerManager.THERMAL_STATUS_LIGHT -> "Light"
        PowerManager.THERMAL_STATUS_MODERATE -> "Moderate"
        PowerManager.THERMAL_STATUS_SEVERE -> "Severe"
        PowerManager.THERMAL_STATUS_CRITICAL -> "Critical"
        PowerManager.THERMAL_STATUS_EMERGENCY -> "Emergency"
        PowerManager.THERMAL_STATUS_SHUTDOWN -> "Shutdown"
        else -> "Unknown ($value)"
    }
}

private fun extraAdvancedBattery(context: Context): String = runCatching {
    val manager = context.getSystemService(Context.BATTERY_SERVICE) as? BatteryManager
    val percent = manager?.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY) ?: -1
    if (percent in 0..100) "$percent% battery" else "Battery percentage unavailable"
}.getOrDefault("Battery status unavailable")

private fun extraAdvancedStorage(context: Context): String = runCatching {
    fun size(directory: File, depth: Int = 0, budget: IntArray = intArrayOf(0)): Long {
        if (depth > 5 || budget[0] >= 3_000 || !directory.exists() || !directory.canRead()) return 0L
        if (directory.isFile) {
            budget[0]++
            return directory.length().coerceAtLeast(0L)
        }
        var total = 0L
        directory.listFiles()?.forEach { child ->
            if (budget[0] < 3_000) total += size(child, depth + 1, budget)
        }
        return total
    }
    val files = size(context.filesDir)
    val cache = size(context.cacheDir)
    val code = size(context.codeCacheDir)
    val free = StatFs(context.filesDir.absolutePath).availableBytes
    "App files=" + files / (1024L * 1024L) + " MB; cache=" +
        cache / (1024L * 1024L) + " MB; code cache=" +
        code / (1024L * 1024L) + " MB; free=" +
        free / (1024L * 1024L) + " MB (bounded scan; game/firmware folders excluded)"
}.getOrDefault("Storage inventory unavailable")

private fun extraAdvancedControllers(): List<String> = runCatching {
    InputDevice.getDeviceIds().mapNotNull { id ->
        InputDevice.getDevice(id)?.takeIf {
            !it.isVirtual && (
                (it.sources and InputDevice.SOURCE_GAMEPAD) == InputDevice.SOURCE_GAMEPAD ||
                (it.sources and InputDevice.SOURCE_JOYSTICK) == InputDevice.SOURCE_JOYSTICK
            )
        }?.name
    }.distinct()
}.getOrDefault(emptyList())

private fun extraAdvancedCompatibilityConfidence(context: Context, serial: String?): String {
    val official = TouchStationFinaleCompatibilityStore.statusFor(serial)
    val local = extraAdvancedReadTests(context, serial).length()
    return when {
        local > 0 -> "User-recorded handset evidence ($local observations); not independently verified"
        !official.isNullOrBlank() -> "Desktop RPCS3 reference only ($official); no device-specific test"
        else -> "Unknown / untested on this handset"
    }
}

private fun extraAdvancedDeviceProfileKey(serial: String?): String =
    "device-profile." + extraAdvancedDeviceId() + "." + extraAdvancedGameId(serial)

private fun extraAdvancedSaveDeviceProfile(context: Context, serial: String?, settings: Settings): String {
    if (serial.isNullOrBlank()) return "A game title ID is required."
    return runCatching {
        context.getSharedPreferences(EXTRA_ADVANCED_PREFS, Context.MODE_PRIVATE).edit()
            .putString(extraAdvancedDeviceProfileKey(serial), settings.toJson().toString()).apply()
        "Saved a device-specific configuration for " + Build.MODEL + " / " + serial + "."
    }.getOrElse { "Device profile save failed: " + (it.message ?: "unknown error") }
}

private fun extraAdvancedLoadDeviceProfile(context: Context, serial: String?): Settings? =
    runCatching {
        val raw = context.getSharedPreferences(EXTRA_ADVANCED_PREFS, Context.MODE_PRIVATE)
            .getString(extraAdvancedDeviceProfileKey(serial), null) ?: return null
        Settings.fromJson(JSONObject(raw))
    }.getOrNull()

private fun extraAdvancedProfileKey(serial: String?, gameScope: Boolean, slot: Int): String =
    "profile." + extraAdvancedDeviceId() + "." +
        (if (gameScope) extraAdvancedGameId(serial) else "global") + "." + slot

private fun extraAdvancedSaveProfile(
    context: Context, serial: String?, gameScope: Boolean, slot: Int, settings: Settings,
): String {
    if (slot !in 1..3) return "Profile slot must be 1, 2 or 3."
    if (gameScope && serial.isNullOrBlank()) return "A game title ID is required for a per-game profile."
    return runCatching {
        context.getSharedPreferences(EXTRA_ADVANCED_PREFS, Context.MODE_PRIVATE).edit()
            .putString(extraAdvancedProfileKey(serial, gameScope, slot), settings.toJson().toString()).apply()
        "Saved slot $slot for " + (if (gameScope) serial else "Global") + "."
    }.getOrElse { "Profile save failed: " + (it.message ?: "unknown error") }
}

private fun extraAdvancedLoadProfile(context: Context, serial: String?, gameScope: Boolean, slot: Int): Settings? =
    runCatching {
        val raw = context.getSharedPreferences(EXTRA_ADVANCED_PREFS, Context.MODE_PRIVATE)
            .getString(extraAdvancedProfileKey(serial, gameScope, slot), null) ?: return null
        Settings.fromJson(JSONObject(raw))
    }.getOrNull()

private fun extraAdvancedSettingGuide(): List<Pair<String, String>> = listOf(
    "PPU decoder" to "CPU emulation backend. Live instruction profiling and automatic fallback are native-core features.",
    "PPU threads" to "Maximum configured PPU execution threads. More threads do not automatically mean faster emulation.",
    "LLVM compile threads" to "Controls concurrent PPU LLVM compilation jobs; more jobs can increase memory use.",
    "SPU decoder" to "Selects the configured SPU emulation backend; compare real game results before changing it.",
    "SPU block size" to "Safe, Mega or Giga compilation mode. Safer settings may be slower.",
    "SPU cache" to "Controls the supported SPU cache option. Native cache internals are not exposed here.",
    "LLVM precompile" to "Allows supported PPU modules to compile ahead of execution; startup time and memory use may rise.",
    "Shader mode" to "Controls the available shader recompilation mode; live job counters are not exposed.",
    "MSAA" to "Multisample anti-aliasing quality setting; higher values can increase GPU cost.",
    "Output scaler" to "Android presentation output scale. It does not change the game's internal RSX resolution.",
    "GPU profile" to "Configured renderer profile. Physical GPU utilization remains driver-dependent.",
    "RSX FIFO accuracy" to "Graphics command fetch policy. Changing it can affect stability and performance.",
    "Driver wake-up delay" to "Native graphics scheduling delay; use per-game overrides and preserve a rollback point."
)

private fun extraAdvancedShare(context: Context, subject: String, text: String) {
    runCatching {
        val intent = Intent(Intent.ACTION_SEND).apply {
            type = "text/plain"
            putExtra(Intent.EXTRA_SUBJECT, subject)
            putExtra(Intent.EXTRA_TEXT, text)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        context.startActivity(
            Intent.createChooser(intent, "Share TouchStation Extra report").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        )
    }
}

private fun extraAdvancedApplyProfile(candidate: Settings, onApply: (Settings) -> Boolean): Boolean {
    if (TouchStationFinaleReliability.validateSettings(candidate).isNotEmpty()) return false
    return runCatching { onApply(candidate) }.getOrDefault(false)
}

private fun extraAdvancedDisplay(context: Context): String = runCatching {
    val manager = context.getSystemService(Context.DISPLAY_SERVICE) as? DisplayManager
    val refresh = manager?.getDisplay(Display.DEFAULT_DISPLAY)?.refreshRate
    refresh?.takeIf { it > 0f }?.let { java.lang.String.format(Locale.US, "%.1f Hz", it) } ?: "N/A"
}.getOrDefault("N/A")

private fun extraAdvancedReport(context: Context, settings: Settings, serial: String?): String = buildString {
    appendLine("TouchStation Extra advanced diagnostics")
    appendLine("Game ID: " + (serial ?: "N/A"))
    appendLine("Device: " + Build.MANUFACTURER + " " + Build.MODEL)
    appendLine("Hardware: " + Build.HARDWARE)
    appendLine("ABI: " + Build.SUPPORTED_ABIS.firstOrNull())
    appendLine("Android: " + Build.VERSION.RELEASE + " / API " + Build.VERSION.SDK_INT)
    appendLine("PPU decoder / threads: " + settings.ps3.ppuDecoder + " / " + settings.ps3.ppuThreads)
    appendLine("LLVM compile threads: " + settings.ps3.llvmThreads)
    appendLine("SPU decoder / block / preferred threads: " + settings.ps3.spuDecoder + " / " +
        settings.ps3.spuBlockSize + " / " + settings.ps3.preferredSpuThreads)
    appendLine("Official desktop compatibility: " + (TouchStationFinaleCompatibilityStore.statusFor(serial) ?: "Unknown"))
    appendLine("Handset evidence: " + extraAdvancedTestSummary(context, serial))
    appendLine("Handset confidence: " + extraAdvancedCompatibilityConfidence(context, serial))
    appendLine("Per-game failure history: " + extraAdvancedCrashHistory(context, serial))
    appendLine("Compatibility regression check: " + extraAdvancedRegression(context, serial))
    appendLine("Crash risk indicators: " + extraAdvancedLaunchRisk(context))
    appendLine("Android process exits:\n" + extraAdvancedProcessExits(context))
    appendLine("Thermal: " + extraAdvancedThermal(context))
    appendLine("Battery: " + extraAdvancedBattery(context))
    appendLine("Storage: " + extraAdvancedStorage(context))
    appendLine("Controllers: " + extraAdvancedControllers().joinToString().ifBlank { "None detected" })
    appendLine("Settings change history: " + TouchStationExtraSettingsHistory.summary(context))
    appendLine("Native PPU/SPU/RSX execution counters, worker states, command traces, GPU fences and physical GPU utilization remain N/A when not exported by the core.")
}

private fun extraAdvancedRow(label: String, value: String) {
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        Text(label, modifier = Modifier.weight(1f), style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, modifier = Modifier.weight(1f), style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
fun TouchStationExtraAdvancedSuite(settings: Settings, onApply: (Settings) -> Boolean) {
    val context = LocalContext.current
    val game = MainActivityRuntime.currentGame.value
    val serial = game?.serial?.takeIf { it.isNotBlank() }
        ?: game?.settingsKey?.takeIf { it.isNotBlank() }
    val gameScope = InGameOverlay.settingsScope.value == SettingsScope.Game
    val prefs = remember(context) { context.getSharedPreferences(EXTRA_ADVANCED_PREFS, Context.MODE_PRIVATE) }
    val search = remember { mutableStateOf("") }
    val actionMessage = remember { mutableStateOf("No advanced settings action performed.") }
    val showResetDialog = remember { mutableStateOf(false) }
    val keepScreenOn = remember { mutableStateOf(prefs.getBoolean("keepScreenOnWhileEmulating", false)) }
    val observations = extraAdvancedReadTests(context, serial)
    val controllers = extraAdvancedControllers()
    val settingMatches = extraAdvancedSettingGuide().filter {
        search.value.isBlank() || it.first.contains(search.value, true) || it.second.contains(search.value, true)
    }.take(12)

    LaunchedEffect(keepScreenOn.value) {
        prefs.edit().putBoolean("keepScreenOnWhileEmulating", keepScreenOn.value).apply()
        val activity = extraAdvancedActivity(context)
        if (keepScreenOn.value) activity?.window?.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        else activity?.window?.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
    }

    val safeSettings = settings.copy(
        ps3 = settings.ps3.copy(
            ppuThreads = minOf(2, Runtime.getRuntime().availableProcessors()).coerceAtLeast(1),
            llvmThreads = 1, preferredSpuThreads = 0, spuBlockSize = 0,
            spuXFloat = 0, shaderMode = 1, msaaMode = 0, spuCache = true, llvmPrecompile = true,
        )
    )
    val availableRamMb = runCatching {
        val manager = context.getSystemService(Context.ACTIVITY_SERVICE) as? ActivityManager
        val info = ActivityManager.MemoryInfo()
        manager?.getMemoryInfo(info)
        info.availMem / (1024L * 1024L)
    }.getOrDefault(0L)
    val ppuRecommendation = if (availableRamMb in 1L..3072L) {
        minOf(1, Runtime.getRuntime().availableProcessors()).coerceAtLeast(1)
    } else minOf(2, Runtime.getRuntime().availableProcessors()).coerceAtLeast(1)
    val report = extraAdvancedReport(context, settings, serial)

    if (showResetDialog.value) {
        AlertDialog(
            onDismissRequest = { showResetDialog.value = false },
            title = { Text("Restore default emulator settings?") },
            text = { Text("This applies upstream Settings() defaults to the currently selected " +
                (if (gameScope) "game-specific" else "global") +
                " scope. Saved games, firmware and controller mappings are not deleted.") },
            confirmButton = {
                TextButton(onClick = {
                    showResetDialog.value = false
                    actionMessage.value = if (extraAdvancedApplyProfile(Settings(), onApply))
                        "Default settings applied and read-back verified."
                    else "Default settings were not confirmed; validation or read-back failed."
                }) { Text("Restore defaults") }
            },
            dismissButton = { TextButton(onClick = { showResetDialog.value = false }) { Text("Cancel") } },
        )
    }

    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(18.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text("TouchStation Extra · Advanced suite", style = MaterialTheme.typography.titleLarge)
            Text("Compatibility evidence, crash prevention, PPU/SPU/RSX guidance and user-controlled settings management. Unsupported native metrics remain N/A.",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)

            Text("01–10 · Game stability and crash prevention", style = MaterialTheme.typography.titleMedium)
            extraAdvancedRow("01 · Pre-launch crash predictor", extraAdvancedLaunchRisk(context))
            extraAdvancedRow("02 · Automatic crash detection", extraAdvancedProcessExits(context) + "; app-process exits are not guest-game crashes")
            extraAdvancedRow("03 · Crash reason analyzer", extraAdvancedProcessExits(context).lineSequence().firstOrNull().orEmpty())
            extraAdvancedRow("04 · Safe game boot", "Conservative profile is available below; explicit user action required")
            extraAdvancedRow("05 · Automatic configuration recovery", TouchStationFinaleSettingsRollback.description())
            extraAdvancedRow("06 · Game session watchdog", TouchStationFinaleRuntimeGuard.activeSummary())
            extraAdvancedRow("07 · Memory pressure protection", if (availableRamMb < 1024L) "LOW — less than 1 GiB available" else "$availableRamMb MB Android-reported available RAM")
            extraAdvancedRow("08 · Thermal protection", extraAdvancedThermal(context))
            extraAdvancedRow("09 · Crash history per game", extraAdvancedCrashHistory(context, serial))
            extraAdvancedRow("10 · Stability score", extraAdvancedTestSummary(context, serial))

            Text("11–20 · Compatibility improvements", style = MaterialTheme.typography.titleMedium)
            extraAdvancedRow("11 · Expanded compatibility database", "Official desktop status: " + (TouchStationFinaleCompatibilityStore.statusFor(serial) ?: "Unknown"))
            extraAdvancedRow("12 · Compatibility confidence", extraAdvancedCompatibilityConfidence(context, serial))
            extraAdvancedRow("13 · Device-specific compatibility profile", if (serial.isNullOrBlank()) "Select a game with a title ID" else "Profile key: " + extraAdvancedDeviceId().take(48))
            extraAdvancedRow("14 · Compatibility regression detector", extraAdvancedRegression(context, serial))
            extraAdvancedRow("15 · Game boot stage tracker", "Record observed boot stages below; automatic guest boot callbacks are not exposed")
            extraAdvancedRow("16 · Known issue matching", TouchStationFinaleErrorHistory.explanation(TouchStationFinaleErrorHistory.latestMessage()))
            extraAdvancedRow("17 · Per-game configuration recommendations", "Conservative PPU thread recommendation: " + ppuRecommendation)
            extraAdvancedRow("18 · Compatibility report generator", "Exports device, game ID, observations, errors and configuration")
            extraAdvancedRow("19 · Controller compatibility database", controllers.joinToString().ifBlank { "No physical gamepads detected" })
            extraAdvancedRow("20 · Firmware / game update warnings", "Installed PUP and game-update versions are not exposed; verify versions manually")

            listOf("Boot started", "Main menu reached", "Gameplay reached", "Stable session (10+ min)",
                "Crash / failed boot", "Freeze / stalled boot").chunked(2).forEach { group ->
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    group.forEach { stage ->
                        OutlinedButton(
                            onClick = {
                                extraAdvancedRecordTest(context, serial, stage)
                                actionMessage.value = "Recorded observation: $stage"
                            },
                            enabled = !serial.isNullOrBlank(),
                            modifier = Modifier.weight(1f),
                        ) { Text(stage, style = MaterialTheme.typography.labelSmall) }
                    }
                }
            }
            OutlinedButton(
                onClick = {
                    prefs.edit().putString("controllerTest." + extraAdvancedDeviceId(),
                        controllers.joinToString().ifBlank { "No gamepad detected" }).apply()
                    actionMessage.value = "Saved detected controller list as a local note; this is not an automatic button test."
                },
                enabled = controllers.isNotEmpty(), modifier = Modifier.fillMaxWidth(),
            ) { Text("Record detected controllers for testing") }

            Text("21–26 · PPU improvements", style = MaterialTheme.typography.titleMedium)
            extraAdvancedRow("21 · PPU execution profiler", "Decoder=" + settings.ps3.ppuDecoder + "; threads=" + settings.ps3.ppuThreads + "; native instruction counters=N/A")
            extraAdvancedRow("22 · PPU LLVM compilation monitor", "Configured LLVM threads=" + settings.ps3.llvmThreads + "; live job progress=N/A")
            extraAdvancedRow("23 · PPU interpreter fallback", "Native automatic decoder fallback not exposed; decoder code=" + settings.ps3.ppuDecoder)
            extraAdvancedRow("24 · PPU thread configuration advisor", "Recommendation=" + ppuRecommendation + "; current=" + settings.ps3.ppuThreads)
            extraAdvancedRow("25 · PPU module loading diagnostics", "Engine initialized=" + ARMSX3.initialized + "; native module registry/load trace=N/A")
            extraAdvancedRow("26 · PPU compilation cache validation", "Read-only app/code cache inspection; private native PPU cache integrity=N/A")

            Text("27–32 · SPU improvements", style = MaterialTheme.typography.titleMedium)
            extraAdvancedRow("27 · SPU workload distribution", "Decoder=" + settings.ps3.spuDecoder + "; preferred threads=" + settings.ps3.preferredSpuThreads + "; native worker distribution=N/A")
            extraAdvancedRow("28 · SPU decoder comparison", "Current decoder=" + settings.ps3.spuDecoder + "; no game benchmark is claimed")
            extraAdvancedRow("29 · SPU thread starvation detector", "Native worker scheduling telemetry=N/A")
            extraAdvancedRow("30 · SPU compilation failure recovery", "Native retry/fallback API=N/A; export diagnostics and preserve caches")
            extraAdvancedRow("31 · SPU cache management", "Configured cache=" + settings.ps3.spuCache + "; private native cache paths not exposed")
            extraAdvancedRow("32 · SPU performance advisor", "Safe block size prioritizes stability; preferred threads=" + settings.ps3.preferredSpuThreads)

            Text("33–40 · RSX and graphics improvements", style = MaterialTheme.typography.titleMedium)
            extraAdvancedRow("33 · RSX command-stream diagnostics", "Recorded FIFO errors=" + TouchStationFinaleErrorHistory.fifoFailureCount() + "; live trace=N/A")
            extraAdvancedRow("34 · FIFO deadlock diagnostics", TouchStationFinaleErrorHistory.suggestion(TouchStationFinaleErrorHistory.latestMessage()))
            extraAdvancedRow("35 · RSX synchronization monitor", "GPU fence and RSX synchronization counters=N/A")
            extraAdvancedRow("36 · Shader compilation failure recovery", "Preserve caches and export logs; native retry API=N/A")
            extraAdvancedRow("37 · Shader cache version manager", "Native shader cache version metadata=N/A")
            extraAdvancedRow("38 · GPU driver compatibility profiles", "Device fingerprint=" + extraAdvancedDeviceId().take(64) + "; exact driver version=N/A")
            extraAdvancedRow("39 · Dynamic resolution recommendations", "Android output scaler=" + settings.hwScaler + "; internal RSX resolution unchanged")
            extraAdvancedRow("40 · Frame pacing optimizer", "Display=" + extraAdvancedDisplay(context) + "; use native in-game FPS/frametime overlay")

            Text("41–50 · App settings and user experience", style = MaterialTheme.typography.titleMedium)
            OutlinedTextField(value = search.value, onValueChange = { search.value = it },
                modifier = Modifier.fillMaxWidth(), singleLine = true,
                label = { Text("Search emulator settings and descriptions") })
            settingMatches.forEach { extraAdvancedRow(it.first, it.second) }
            extraAdvancedRow("41 · Complete settings search", "Search the documented settings glossary above")
            extraAdvancedRow("42 · Settings profiles", "Three save slots per device and settings scope")
            extraAdvancedRow("43 · One-tap settings reset", "Confirmed reset to upstream Settings() defaults")
            extraAdvancedRow("44 · Settings change history", TouchStationExtraSettingsHistory.summary(context))
            extraAdvancedRow("45 · Advanced setting descriptions", "Searchable descriptions for PPU, SPU, shader, output and graphics settings")
            extraAdvancedRow("46 · Automatic device detection", Build.MANUFACTURER + " " + Build.MODEL + " · " + Build.HARDWARE + " · " + Build.SUPPORTED_ABIS.firstOrNull())
            extraAdvancedRow("47 · Battery and performance modes", extraAdvancedBattery(context) + "; apply a profile below")
            extraAdvancedRow("48 · Background activity controls", "Keep screen awake while using TouchStation")
            extraAdvancedRow("49 · Storage manager", extraAdvancedStorage(context))
            extraAdvancedRow("50 · Diagnostics dashboard", "Crash risk, compatibility, observations, controllers, memory, thermal, storage and settings")

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                (1..3).forEach { slot ->
                    Column(modifier = Modifier.weight(1f)) {
                        OutlinedButton(onClick = {
                            actionMessage.value = extraAdvancedSaveProfile(context, serial, gameScope, slot, settings)
                        }, modifier = Modifier.fillMaxWidth()) { Text("Save slot $slot") }
                        OutlinedButton(onClick = {
                            val loaded = extraAdvancedLoadProfile(context, serial, gameScope, slot)
                            actionMessage.value = when {
                                loaded == null -> "Slot $slot is empty or unreadable."
                                TouchStationFinaleReliability.validateSettings(loaded).isNotEmpty() -> "Slot $slot rejected by validation."
                                extraAdvancedApplyProfile(loaded, onApply) -> "Slot $slot applied and read-back verified."
                                else -> "Slot $slot not applied; read-back failed."
                            }
                        }, modifier = Modifier.fillMaxWidth()) { Text("Load slot $slot") }
                    }
                }
            }

            OutlinedButton(onClick = {
                actionMessage.value = extraAdvancedSaveDeviceProfile(context, serial, settings)
            }, enabled = !serial.isNullOrBlank(), modifier = Modifier.fillMaxWidth()) {
                Text("Save device-specific game profile")
            }
            OutlinedButton(onClick = {
                val loaded = extraAdvancedLoadDeviceProfile(context, serial)
                actionMessage.value = when {
                    loaded == null -> "No device-specific profile exists for this game."
                    extraAdvancedApplyProfile(loaded, onApply) -> "Device-specific profile applied and verified."
                    else -> "Device-specific profile rejected or read-back failed."
                }
            }, enabled = !serial.isNullOrBlank(), modifier = Modifier.fillMaxWidth()) {
                Text("Load device-specific game profile")
            }

            Button(onClick = {
                actionMessage.value = if (extraAdvancedApplyProfile(safeSettings, onApply))
                    "Safe game boot profile applied and read-back verified."
                else "Safe game boot profile was not confirmed."
            }, enabled = game != null && gameScope, modifier = Modifier.fillMaxWidth()) {
                Text("Apply safe game boot profile")
            }

            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("Keep screen awake while using TouchStation")
                Switch(checked = keepScreenOn.value, onCheckedChange = { keepScreenOn.value = it })
            }

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = {
                    val candidate = settings.copy(hwScaler = 540, ps3 = settings.ps3.copy(
                        ppuThreads = 1, llvmThreads = 1, preferredSpuThreads = 0, msaaMode = 0))
                    actionMessage.value = if (extraAdvancedApplyProfile(candidate, onApply))
                        "Battery-focused profile applied and read-back verified."
                    else "Battery-focused profile was not confirmed."
                }, modifier = Modifier.weight(1f)) { Text("Battery mode") }
                OutlinedButton(onClick = {
                    val candidate = settings.copy(ps3 = settings.ps3.copy(
                        ppuThreads = minOf(2, Runtime.getRuntime().availableProcessors()).coerceAtLeast(1),
                        llvmThreads = 1))
                    actionMessage.value = if (extraAdvancedApplyProfile(candidate, onApply))
                        "Balanced profile applied and read-back verified."
                    else "Balanced profile was not confirmed."
                }, modifier = Modifier.weight(1f)) { Text("Balanced mode") }
                OutlinedButton(onClick = {
                    val candidate = settings.copy(ps3 = settings.ps3.copy(
                        ppuThreads = minOf(4, Runtime.getRuntime().availableProcessors()).coerceAtLeast(1),
                        llvmThreads = minOf(2, Runtime.getRuntime().availableProcessors()).coerceAtLeast(1)))
                    actionMessage.value = if (extraAdvancedApplyProfile(candidate, onApply))
                        "Performance profile applied and read-back verified; watch memory and thermal status."
                    else "Performance profile was not confirmed."
                }, modifier = Modifier.weight(1f)) { Text("Performance mode") }
            }

            Button(onClick = { showResetDialog.value = true }, modifier = Modifier.fillMaxWidth()) {
                Text("Reset settings to defaults…")
            }
            OutlinedButton(onClick = {
                extraAdvancedShare(context, "TouchStation Extra compatibility report",
                    extraAdvancedReport(context, settings, serial))
                actionMessage.value = "Opened Android share sheet for the report."
            }, modifier = Modifier.fillMaxWidth()) { Text("Export compatibility and diagnostic report") }

            Text(actionMessage.value, style = MaterialTheme.typography.bodySmall)
            Text(
                "Handset observations are user-entered, not independently verified compatibility ratings. Android process exit records are not proof that a guest game crashed. The score is an observation index, not a prediction. Native PPU/SPU/RSX profiling, module registries, worker scheduling, FIFO queue depth, GPU fences, shader retry and physical GPU telemetry require native-core instrumentation.",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}
