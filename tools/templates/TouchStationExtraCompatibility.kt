package com.armsx2.ui.settings

import android.app.ActivityManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Debug
import android.os.PowerManager
import android.os.StatFs
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
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
import java.io.File
import java.security.MessageDigest
import java.util.Locale
import org.json.JSONObject

private const val EXTRA_COMPAT_PREFS = "touchstation-extra-compatibility"

private data class ExtraCompatibilitySnapshot(
    val availableRamMb: Long,
    val appPssMb: Int,
    val freeStorageMb: Long,
    val thermalStatus: Int?,
    val vulkanFeature: Boolean,
    val arm64Supported: Boolean,
    val nativeCorePresent: Boolean,
    val nativeJniPresent: Boolean,
)

private fun extraCompatibilitySnapshot(context: Context): ExtraCompatibilitySnapshot {
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
    val nativeDir = File(context.applicationInfo.nativeLibraryDir.orEmpty())
    return ExtraCompatibilitySnapshot(
        availableRamMb = available,
        appPssMb = pss,
        freeStorageMb = storage,
        thermalStatus = thermal,
        vulkanFeature = runCatching {
            context.packageManager.hasSystemFeature(PackageManager.FEATURE_VULKAN_HARDWARE_LEVEL)
        }.getOrDefault(false),
        arm64Supported = Build.SUPPORTED_ABIS.any { it.equals("arm64-v8a", true) },
        nativeCorePresent = File(nativeDir, "libarmsx3-core.so").let { it.isFile && it.length() > 0L },
        nativeJniPresent = File(nativeDir, "libarmsx3-jni.so").let { it.isFile && it.length() > 0L },
    )
}

private fun extraCompatibilityThermal(status: Int?): String = when (status) {
    null -> "Not reported"
    PowerManager.THERMAL_STATUS_NONE -> "Normal"
    PowerManager.THERMAL_STATUS_LIGHT -> "Light"
    PowerManager.THERMAL_STATUS_MODERATE -> "Moderate"
    PowerManager.THERMAL_STATUS_SEVERE -> "Severe"
    PowerManager.THERMAL_STATUS_CRITICAL -> "Critical"
    PowerManager.THERMAL_STATUS_EMERGENCY -> "Emergency"
    PowerManager.THERMAL_STATUS_SHUTDOWN -> "Shutdown"
    else -> "Unknown ($status)"
}

private fun extraCompatibilityGameKey(serial: String?): String {
    val raw = serial.orEmpty().trim().uppercase(Locale.ROOT)
    val digest = MessageDigest.getInstance("SHA-256").digest(raw.toByteArray(Charsets.UTF_8))
        .take(8).joinToString("") { "%02x".format(Locale.ROOT, it.toInt() and 0xff) }
    return "game.$digest"
}

private fun extraCompatibilityLoadRecord(context: Context, serial: String?): JSONObject =
    runCatching {
        val raw = context.getSharedPreferences(EXTRA_COMPAT_PREFS, Context.MODE_PRIVATE)
            .getString(extraCompatibilityGameKey(serial), null)
        if (raw.isNullOrBlank()) JSONObject() else JSONObject(raw)
    }.getOrDefault(JSONObject())

private fun extraCompatibilitySaveRecord(
    context: Context,
    serial: String?,
    title: String,
    status: String,
    failureStage: String,
    notes: String,
): String {
    if (serial.isNullOrBlank()) return "A game title ID is required before saving a compatibility record."
    val record = JSONObject()
        .put("gameId", serial)
        .put("title", title)
        .put("status", status.trim().take(80))
        .put("failureStage", failureStage.trim().take(120))
        .put("notes", notes.trim().take(2000))
        .put("updatedAt", System.currentTimeMillis())
    return runCatching {
        context.getSharedPreferences(EXTRA_COMPAT_PREFS, Context.MODE_PRIVATE).edit()
            .putString(extraCompatibilityGameKey(serial), record.toString()).apply()
        "Saved a local compatibility record for $serial. The status and notes are user-entered."
    }.getOrElse { "Could not save compatibility record: " + (it.message ?: "unknown error") }
}

private fun extraCompatibilityCandidate(
    settings: Settings,
    snapshot: ExtraCompatibilitySnapshot,
    gtaIv: Boolean,
    lowMemory: Boolean,
): Settings {
    val severeThermal = snapshot.thermalStatus != null &&
        snapshot.thermalStatus >= PowerManager.THERMAL_STATUS_SEVERE
    val constrained = lowMemory || snapshot.availableRamMb in 0L..3071L || severeThermal
    val ppuThreads = if (gtaIv || constrained) 1
        else minOf(2, Runtime.getRuntime().availableProcessors()).coerceAtLeast(1)
    return settings.copy(
        ps3 = settings.ps3.copy(
            ppuDecoder = 1,
            spuDecoder = 3,
            ppuThreads = ppuThreads,
            llvmThreads = 1,
            preferredSpuThreads = 0,
            spuBlockSize = 0,
            spuXFloat = 0,
            shaderMode = 1,
            msaaMode = 0,
            spuCache = true,
            llvmPrecompile = TouchStationFinaleNativeDiagnostics.allowPpuPrecompile(
                snapshot.availableRamMb,
                snapshot.thermalStatus,
            ),
        ),
    )
}

private fun extraCompatibilitySettingsFingerprint(settings: Settings): String = runCatching {
    val bytes = settings.toJson().toString().toByteArray(Charsets.UTF_8)
    MessageDigest.getInstance("SHA-256").digest(bytes)
        .joinToString("") { "%02x".format(Locale.ROOT, it.toInt() and 0xff) }
}.getOrDefault("unavailable")

private fun extraCompatibilityReadinessReport(
    snapshot: ExtraCompatibilitySnapshot,
    serial: String?,
    settings: Settings,
    gtaIv: Boolean,
    failureStage: String,
): String {
    val validation = TouchStationFinaleReliability.validateSettings(settings)
    return buildString {
        appendLine("TouchStation Extra - Compatibility preflight")
        appendLine("Selected game ID: " + (serial ?: "Unavailable"))
        appendLine("Device: " + Build.MANUFACTURER + " " + Build.MODEL)
        appendLine("Android: " + Build.VERSION.RELEASE + " / API " + Build.VERSION.SDK_INT)
        appendLine("ABI: " + Build.SUPPORTED_ABIS.joinToString())
        appendLine("ARM64 ABI: " + snapshot.arm64Supported)
        appendLine("Vulkan hardware-level feature advertised by Android: " + snapshot.vulkanFeature)
        appendLine("Native PS3 core present: " + snapshot.nativeCorePresent)
        appendLine("Native JNI bridge present: " + snapshot.nativeJniPresent)
        appendLine("Available system RAM: " + snapshot.availableRamMb + " MB")
        appendLine("App PSS: " + snapshot.appPssMb + " MB")
        appendLine("App-private free storage: " + snapshot.freeStorageMb + " MB")
        appendLine("Thermal status: " + extraCompatibilityThermal(snapshot.thermalStatus))
        appendLine("Native engine initialized: " + runCatching { com.armsx3.core.ARMSX3.initialized }.getOrDefault(false))
        appendLine("Settings validation: " + if (validation.isEmpty()) "passed" else validation.joinToString())
        appendLine("Settings SHA-256: " + extraCompatibilitySettingsFingerprint(settings))
        appendLine("User-recorded failure stage: " + failureStage.trim().take(120).ifBlank { "Not recorded" })
        if (gtaIv) {
            appendLine("GTA IV profile target: BLES00229 (exact serial match)")
            appendLine("PPU instruction/module trace: NOT EXPOSED BY PINNED NATIVE CORE")
            appendLine("PPU recompiler failure/recovery counters: NOT EXPOSED BY PINNED NATIVE CORE")
            appendLine("PPU cache integrity/rebuild state: NOT EXPOSED BY PINNED NATIVE CORE")
            appendLine("PPU guest-thread lock and memory-order trace: NOT EXPOSED BY PINNED NATIVE CORE")
            appendLine("SPU worker queue, scheduling and starvation counters: NOT EXPOSED BY PINNED NATIVE CORE")
            appendLine("SPU worker exception isolation and cache-recovery state: NOT EXPOSED BY PINNED NATIVE CORE")
            appendLine("SPU guest timing counters: NOT EXPOSED BY PINNED NATIVE CORE")
            appendLine("RSX command queue and GPU-fence trace: NOT EXPOSED BY PINNED NATIVE CORE")
            appendLine("RSX render-target and texture lifetime trace: NOT EXPOSED BY PINNED NATIVE CORE")
            appendLine("Shader compile/cache recovery counters: NOT EXPOSED BY PINNED NATIVE CORE")
            appendLine("Guest audio clock/buffer timing: NOT EXPOSED BY PINNED NATIVE CORE")
            appendLine("Guest save-state schema/checksum validation: NOT EXPOSED BY PINNED NATIVE CORE")
            appendLine("This report records Android and exposed settings evidence only; it does not claim these native fixes are implemented.")
        }
        appendLine("Package-manager Vulkan feature is not a live Vulkan device/extension query.")
        appendLine("PPU/SPU worker state, RSX queues, shader internals and guest crash callbacks are not exposed by the pinned core.")
        appendLine("This preflight does not launch or certify the selected game.")
    }
}

private fun extraCompatibilityShare(context: Context, report: String): Boolean = runCatching {
    val send = Intent(Intent.ACTION_SEND).apply {
        type = "text/plain"
        putExtra(Intent.EXTRA_SUBJECT, "TouchStation Extra - Compatibility report")
        putExtra(Intent.EXTRA_TEXT, report)
        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    }
    context.startActivity(Intent.createChooser(send, "Share compatibility report")
        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    true
}.getOrDefault(false)

@Composable
fun TouchStationExtraCompatibilitySuite(
    settings: Settings,
    onApply: (Settings) -> Boolean,
) {
    val context = LocalContext.current
    val game = MainActivityRuntime.currentGame.value
    val serial = game?.serial?.takeIf { it.isNotBlank() }
        ?: game?.settingsKey?.takeIf { it.isNotBlank() }
    val title = game?.title?.takeIf { it.isNotBlank() } ?: "Untitled / unavailable"
    val gtaIv = game?.serial?.equals("BLES00229", ignoreCase = true) == true
    val gameScope = InGameOverlay.settingsScope.value == SettingsScope.Game
    val snapshot = remember(context) { mutableStateOf(extraCompatibilitySnapshot(context)) }
    val stored = remember(serial, context) { extraCompatibilityLoadRecord(context, serial) }
    val status = remember(serial) { mutableStateOf(stored.optString("status", "Not tested")) }
    val failureStage = remember(serial) { mutableStateOf(stored.optString("failureStage", "Not recorded")) }
    val notes = remember(serial) { mutableStateOf(stored.optString("notes", "")) }
    val message = remember { mutableStateOf("No compatibility action performed.") }
    val report = remember { mutableStateOf("") }
    val canApply = !serial.isNullOrBlank() && gameScope

    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(18.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(9.dp),
        ) {
            Text("TouchStation Extra - Compatibility", style = MaterialTheme.typography.titleLarge)
            Text(
                "Universal per-game profiles and preflight checks, plus an exact GTA IV BLES00229 profile. Native PPU/SPU/RSX features are shown as unavailable when the pinned core does not expose them.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text("Selected game: $title")
            Text("Game ID: " + (serial ?: "Not available") + " · scope: " +
                if (gameScope) "per-game" else "global")
            Text(
                "RAM: " + snapshot.value.availableRamMb + " MB available · app PSS: " +
                    snapshot.value.appPssMb + " MB · free storage: " +
                    snapshot.value.freeStorageMb + " MB",
                style = MaterialTheme.typography.bodySmall,
            )
            Text(
                "ARM64: " + snapshot.value.arm64Supported +
                    " · Vulkan feature: " + snapshot.value.vulkanFeature +
                    " · native core/JNI: " + snapshot.value.nativeCorePresent +
                    "/" + snapshot.value.nativeJniPresent,
                style = MaterialTheme.typography.bodySmall,
            )
            Text("Thermal status: " + extraCompatibilityThermal(snapshot.value.thermalStatus),
                style = MaterialTheme.typography.bodySmall)

            Text("Universal game profiles", style = MaterialTheme.typography.titleMedium)
            Text(
                "Profiles only change settings already exposed by this Android wrapper. They do not rewrite PPU/SPU/RSX native code.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Button(
                onClick = {
                    val candidate = extraCompatibilityCandidate(settings, snapshot.value, false, false)
                    val issues = TouchStationFinaleReliability.validateSettings(candidate)
                    message.value = when {
                        !gameScope -> "Select per-game settings scope before applying a profile."
                        issues.isNotEmpty() -> "Profile rejected by settings validation: " + issues.take(3).joinToString()
                        runCatching { onApply(candidate) }.getOrDefault(false) ->
                            "Universal conservative profile applied and full settings read-back verified."
                        else -> "Profile was not confirmed. Check the selected game's settings before retrying."
                    }
                },
                enabled = canApply,
                modifier = Modifier.fillMaxWidth(),
            ) { Text("Apply Universal Compatibility Profile") }
            OutlinedButton(
                onClick = {
                    val candidate = extraCompatibilityCandidate(settings, snapshot.value, false, true)
                    val issues = TouchStationFinaleReliability.validateSettings(candidate)
                    message.value = when {
                        !gameScope -> "Select per-game settings scope before applying a profile."
                        issues.isNotEmpty() -> "Low-memory profile rejected: " + issues.take(3).joinToString()
                        runCatching { onApply(candidate) }.getOrDefault(false) ->
                            "Low-memory compatibility profile applied and read-back verified."
                        else -> "Low-memory profile was not confirmed."
                    }
                },
                enabled = canApply,
                modifier = Modifier.fillMaxWidth(),
            ) { Text("Apply Low-Memory Compatibility Profile") }

            Text("GTA IV compatibility · BLES00229", style = MaterialTheme.typography.titleMedium)
            if (gtaIv) {
                Text(
                    "Exact serial match detected. This profile uses one PPU thread, conservative LLVM PPU/SPU settings, no MSAA and the existing memory/thermal precompile guard. It is a test profile, not a native GTA IV patch or a playability guarantee.",
                    style = MaterialTheme.typography.bodySmall,
                )
                Button(
                    onClick = {
                        val candidate = extraCompatibilityCandidate(settings, snapshot.value, true, true)
                        val issues = TouchStationFinaleReliability.validateSettings(candidate)
                        message.value = when {
                            !gameScope -> "Select per-game settings scope before applying the GTA IV profile."
                            issues.isNotEmpty() -> "GTA IV profile rejected: " + issues.take(3).joinToString()
                            runCatching { onApply(candidate) }.getOrDefault(false) ->
                                "GTA IV BLES00229 conservative profile applied and read-back verified."
                            else -> "GTA IV profile was not confirmed."
                        }
                    },
                    enabled = canApply,
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Apply GTA IV BLES00229 Profile") }
            } else {
                Text(
                    "Hidden for other games. This profile becomes available only when the detected game serial is exactly BLES00229.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            if (gtaIv) {
                Text("GTA IV technical evidence", style = MaterialTheme.typography.titleMedium)
                Text(
                    "Record the last stage reached. This is user-entered evidence; native PPU/SPU/RSX traces are not exposed by the current prebuilt core.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                OutlinedTextField(
                    value = failureStage.value,
                    onValueChange = { failureStage.value = it.take(120) },
                    label = { Text("Failure stage (for example: launch, PPU, SPU, RSX, audio, save/load, shutdown)") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                )
            }

            Text("Per-game compatibility record", style = MaterialTheme.typography.titleMedium)
            OutlinedTextField(
                value = status.value,
                onValueChange = { status.value = it.take(80) },
                label = { Text("Your test status (not an automatic rating)") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
            )
            OutlinedTextField(
                value = notes.value,
                onValueChange = { notes.value = it.take(2000) },
                label = { Text("Known issues / failure stage / notes") },
                modifier = Modifier.fillMaxWidth(),
                minLines = 2,
            )
            OutlinedButton(
                onClick = {
                    message.value = extraCompatibilitySaveRecord(
                        context, serial, title, status.value, failureStage.value, notes.value
                    )
                },
                enabled = !serial.isNullOrBlank(),
                modifier = Modifier.fillMaxWidth(),
            ) { Text("Save this game's compatibility record") }

            Text("Run Android-side preflight", style = MaterialTheme.typography.titleMedium)
            OutlinedButton(
                onClick = {
                    snapshot.value = extraCompatibilitySnapshot(context)
                    report.value = extraCompatibilityReadinessReport(
                        snapshot.value, serial, settings, gtaIv, failureStage.value
                    )
                    message.value = if (gtaIv) {
                        "GTA IV diagnostic snapshot captured. Native guest internals remain unavailable."
                    } else {
                        "Preflight refreshed. It reports Android/device evidence, not PS3 guest internals."
                    }
                },
                modifier = Modifier.fillMaxWidth(),
            ) { Text(if (gtaIv) "Capture GTA IV diagnostic snapshot" else "Refresh and run preflight checks") }
            if (report.value.isNotBlank()) {
                Text(report.value, style = MaterialTheme.typography.bodySmall)
                OutlinedButton(
                    onClick = {
                        message.value = if (extraCompatibilityShare(context, report.value))
                            "Opened Android share sheet for the compatibility preflight."
                        else "Could not open the Android share sheet."
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Share compatibility preflight") }
            }
            Text(
                "Native-core work still required: actual PPU instruction/recompiler recovery, SPU worker scheduling and exception callbacks, RSX command/fence synchronization, shader/texture lifetime management, guest audio timing, save-state format validation and guest crash callbacks. These cannot be enabled by Android-side settings.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(message.value, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.primary)
        }
    }
}
