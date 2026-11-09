package com.armsx2.ui.settings

import android.app.ActivityManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.BatteryManager
import android.os.PowerManager
import android.os.StatFs
import android.provider.OpenableColumns
import android.view.InputDevice
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.focusable
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
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.input.key.KeyEventType
import androidx.compose.ui.input.key.nativeKeyEvent
import androidx.compose.ui.input.key.onPreviewKeyEvent
import androidx.compose.ui.input.key.type
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.edit
import com.armsx2.config.Settings
import com.armsx2.runtime.MainActivityRuntime
import com.armsx3.core.ARMSX3
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.security.MessageDigest
import java.util.Locale

private const val EXTRA100_PREFS = "touchstation-extra-100"
private const val EXTRA100_META_PREFIX = "game-meta."
private const val EXTRA100_PLAYTIME_PREFIX = "playtime."
private const val EXTRA100_METRICS_PREFIX = "metrics."

private fun extra100GameId(serial: String?): String =
    serial.orEmpty().filter { it.isLetterOrDigit() }.uppercase(Locale.ROOT).ifBlank { "unknown" }

private fun extra100LoadMeta(context: Context, serial: String?): JSONObject = runCatching {
    val key = EXTRA100_META_PREFIX + extra100GameId(serial)
    JSONObject(context.getSharedPreferences(EXTRA100_PREFS, Context.MODE_PRIVATE).getString(key, "{}") ?: "{}")
}.getOrDefault(JSONObject())

private fun extra100SaveMeta(
    context: Context, serial: String?, title: String, category: String, tags: String, favorite: Boolean,
    status: String, knownIssues: String, firmwareNote: String, updateNote: String, notes: String,
) {
    if (serial.isNullOrBlank()) return
    val prefs = context.getSharedPreferences(EXTRA100_PREFS, Context.MODE_PRIVATE)
    val key = EXTRA100_META_PREFIX + extra100GameId(serial)
    val previous = runCatching { JSONObject(prefs.getString(key, "{}") ?: "{}") }.getOrDefault(JSONObject())
    val next = JSONObject()
        .put("serial", extra100GameId(serial)).put("title", title.trim()).put("category", category.trim())
        .put("tags", tags.trim()).put("favorite", favorite).put("status", status.trim())
        .put("knownIssues", knownIssues.trim()).put("firmwareNote", firmwareNote.trim())
        .put("updateNote", updateNote.trim()).put("notes", notes.trim())
        .put("updatedAt", System.currentTimeMillis())
    val historyKey = "compatibility-history." + extra100GameId(serial)
    val history = runCatching { JSONArray(prefs.getString(historyKey, "[]") ?: "[]") }.getOrDefault(JSONArray())
    val oldStatus = previous.optString("status")
    if (oldStatus != status.trim()) {
        val updated = JSONArray()
        for (index in (history.length() - 19).coerceAtLeast(0) until history.length()) {
            history.optJSONObject(index)?.let { updated.put(it) }
        }
        updated.put(JSONObject().put("timestamp", System.currentTimeMillis())
            .put("previous", oldStatus).put("current", status.trim()))
        prefs.edit().putString(historyKey, updated.toString()).apply()
    }
    prefs.edit().putString(key, next.toString()).apply()
}

private fun extra100LibraryIndex(context: Context): List<String> {
    val prefs = context.getSharedPreferences(EXTRA100_PREFS, Context.MODE_PRIVATE)
    return prefs.all.entries.filter { it.key.startsWith(EXTRA100_META_PREFIX) }
        .mapNotNull { entry ->
            val raw = entry.value as? String ?: return@mapNotNull null
            val json = runCatching { JSONObject(raw) }.getOrNull() ?: return@mapNotNull null
            val serial = json.optString("serial", entry.key.removePrefix(EXTRA100_META_PREFIX))
            val title = json.optString("title").ifBlank { serial }
            val favorite = if (json.optBoolean("favorite")) "★ " else ""
            val category = json.optString("category").ifBlank { "Uncategorized" }
            favorite + title + " · " + serial + " · " + category
        }
        .sortedWith(compareByDescending<String> { it.startsWith("★ ") }.thenBy { it.lowercase(Locale.ROOT) })
}

private fun extra100InspectDocument(context: Context, uri: Uri): String = runCatching {
    var name = uri.lastPathSegment ?: "selected document"
    var size = -1L
    context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE), null, null, null)?.use { cursor ->
        if (cursor.moveToFirst()) {
            val nameIndex = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
            val sizeIndex = cursor.getColumnIndex(OpenableColumns.SIZE)
            if (nameIndex >= 0) name = cursor.getString(nameIndex) ?: name
            if (sizeIndex >= 0 && !cursor.isNull(sizeIndex)) size = cursor.getLong(sizeIndex)
        }
    }
    val readable = context.contentResolver.openInputStream(uri)?.use { input ->
        val sample = ByteArray(4096)
        input.read(sample) > 0
    } ?: false
    val extension = name.substringAfterLast('.', "").lowercase(Locale.ROOT)
    val candidate = extension in setOf("iso", "pkg", "rap", "edat", "self", "sprx", "bin")
    "File: " + name + "; size=" + (if (size >= 0L) size.toString() + " bytes" else "not provided") +
        "; readable=" + readable + "; recognized extension candidate=" + candidate +
        ". This is a metadata/readability check, not a full PS3 image, package or integrity validation."
}.getOrDefault("Could not inspect the selected document. Check its permission and try again.")

private fun extra100Digest(context: Context, uri: Uri): String {
    val digest = MessageDigest.getInstance("SHA-256")
    context.contentResolver.openInputStream(uri)?.use { input ->
        val buffer = ByteArray(64 * 1024)
        while (true) {
            val count = input.read(buffer)
            if (count < 0) break
            digest.update(buffer, 0, count)
        }
    } ?: error("Cannot open selected source document")
    return digest.digest().joinToString("") { "%02x".format(it) }
}

private fun extra100CopyAndVerify(context: Context, source: Uri, destination: Uri): String {
    val digest = MessageDigest.getInstance("SHA-256")
    var bytes = 0L
    context.contentResolver.openInputStream(source)?.use { input ->
        context.contentResolver.openOutputStream(destination, "wt")?.use { output ->
            val buffer = ByteArray(64 * 1024)
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                digest.update(buffer, 0, count)
                output.write(buffer, 0, count)
                bytes += count.toLong()
            }
            output.flush()
        } ?: error("Cannot open chosen destination")
    } ?: error("Cannot open selected source")
    val expected = digest.digest().joinToString("") { "%02x".format(it) }
    val actual = extra100Digest(context, destination)
    check(expected == actual) { "Destination checksum differs from source" }
    "Copied and re-read $bytes bytes. SHA-256 verified: $actual"
}

private fun extra100ControllerSummary(): String {
    val devices = InputDevice.getDeviceIds().mapNotNull { InputDevice.getDevice(it) }
        .filter { device ->
            (device.sources and InputDevice.SOURCE_GAMEPAD) == InputDevice.SOURCE_GAMEPAD ||
                (device.sources and InputDevice.SOURCE_JOYSTICK) == InputDevice.SOURCE_JOYSTICK
        }
    return if (devices.isEmpty()) "No Android gamepad/joystick input device is currently reported."
    else devices.joinToString("\n") { it.name + " · id=" + it.id + " · sources=" + it.sources }
}

private fun extra100CaptureMetrics(context: Context, serial: String?): String {
    val manager = context.getSystemService(Context.ACTIVITY_SERVICE) as? ActivityManager
    val memory = ActivityManager.MemoryInfo()
    val availableMb = runCatching {
        if (manager == null) -1L else {
            manager.getMemoryInfo(memory)
            memory.availMem / (1024L * 1024L)
        }
    }.getOrDefault(-1L)
    val battery = runCatching {
        (context.getSystemService(Context.BATTERY_SERVICE) as? BatteryManager)
            ?.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY) ?: -1
    }.getOrDefault(-1)
    val storageMb = runCatching { StatFs(context.filesDir.absolutePath).availableBytes / (1024L * 1024L) }
        .getOrDefault(-1L)
    val thermal = runCatching {
        (context.getSystemService(Context.POWER_SERVICE) as? PowerManager)?.currentThermalStatus
    }.getOrNull() ?: -1
    val record = JSONObject().put("timestamp", System.currentTimeMillis())
        .put("serial", extra100GameId(serial)).put("availableRamMb", availableMb)
        .put("batteryPercent", battery).put("appStorageFreeMb", storageMb).put("thermalStatus", thermal)
    val prefs = context.getSharedPreferences(EXTRA100_PREFS, Context.MODE_PRIVATE)
    val key = EXTRA100_METRICS_PREFIX + extra100GameId(serial)
    val old = runCatching { JSONArray(prefs.getString(key, "[]") ?: "[]") }.getOrDefault(JSONArray())
    val next = JSONArray()
    for (index in (old.length() - 29).coerceAtLeast(0) until old.length()) {
        old.optJSONObject(index)?.let { next.put(it) }
    }
    next.put(record)
    prefs.edit().putString(key, next.toString()).apply()
    return "Snapshot saved: Android RAM " + availableMb + " MB; battery " + battery +
        "%; app-private free storage " + storageMb + " MB; Android thermal status " + thermal +
        ". These are device metrics, not PS3 guest CPU/GPU counters."
}

private fun extra100CompareMetrics(context: Context, serial: String?): String = runCatching {
    val key = EXTRA100_METRICS_PREFIX + extra100GameId(serial)
    val records = JSONArray(context.getSharedPreferences(EXTRA100_PREFS, Context.MODE_PRIVATE)
        .getString(key, "[]") ?: "[]")
    if (records.length() < 2) return@runCatching "Capture at least two Android metric snapshots to compare sessions."
    val older = records.optJSONObject(records.length() - 2) ?: return@runCatching "Earlier snapshot unavailable."
    val newer = records.optJSONObject(records.length() - 1) ?: return@runCatching "Latest snapshot unavailable."
    val before = older.optLong("availableRamMb", -1L)
    val after = newer.optLong("availableRamMb", -1L)
    "Latest vs previous Android snapshot: available RAM " +
        (if (before >= 0L && after >= 0L) (after - before).toString() + " MB" else "N/A") +
        "; battery " + older.optInt("batteryPercent", -1) + "% → " + newer.optInt("batteryPercent", -1) +
        "%; app storage " + older.optLong("appStorageFreeMb", -1L) + " MB → " +
        newer.optLong("appStorageFreeMb", -1L) + " MB. Not a guest-game benchmark."
}.getOrDefault("Metric comparison unavailable.")

private fun extra100SelfChecks(context: Context, settings: Settings, serial: String?): String {
    val nativeDir = File(context.applicationInfo.nativeLibraryDir.orEmpty())
    val core = File(nativeDir, "libarmsx3-core.so").let { it.isFile && it.length() > 0L }
    val jni = File(nativeDir, "libarmsx3-jni.so").let { it.isFile && it.length() > 0L }
    val settingsValid = runCatching { settings.toJson().toString().isNotBlank() }.getOrDefault(false)
    val storage = runCatching { StatFs(context.filesDir.absolutePath).availableBytes }.getOrDefault(-1L)
    return listOf(
        "Selected game ID: " + (serial ?: "none"),
        "Settings serialization: " + if (settingsValid) "OK" else "FAILED",
        "Native core library: " + if (core) "present" else "missing/not unpacked",
        "Native JNI library: " + if (jni) "present" else "missing/not unpacked",
        "Native engine initialized: " + ARMSX3.initialized,
        "App-private free storage: " + if (storage >= 0L) storage.toString() + " bytes" else "N/A",
        "Guest-game boot test: not run by this app-side checklist",
    ).joinToString("\n")
}

private fun extra100Share(context: Context, report: String) {
    val intent = Intent(Intent.ACTION_SEND).apply {
        type = "text/plain"
        putExtra(Intent.EXTRA_TEXT, report)
    }
    context.startActivity(Intent.createChooser(intent, "Share TouchStation Extra report"))
}

private fun extra100Duration(milliseconds: Long): String {
    val seconds = (milliseconds / 1000L).coerceAtLeast(0L)
    return "%02d:%02d:%02d".format(seconds / 3600L, (seconds / 60L) % 60L, seconds % 60L)
}

@Composable
fun TouchStationExtra100Suite(settings: Settings) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val game = MainActivityRuntime.currentGame.value
    val serial = game?.serial?.takeIf { it.isNotBlank() } ?: game?.settingsKey?.takeIf { it.isNotBlank() }
    val prefs = remember(context) { context.getSharedPreferences(EXTRA100_PREFS, Context.MODE_PRIVATE) }
    val metadata = remember(serial, prefs) { extra100LoadMeta(context, serial) }
    val title = remember(serial) { mutableStateOf(metadata.optString("title", "")) }
    val category = remember(serial) { mutableStateOf(metadata.optString("category", "")) }
    val tags = remember(serial) { mutableStateOf(metadata.optString("tags", "")) }
    val favorite = remember(serial) { mutableStateOf(metadata.optBoolean("favorite")) }
    val compatibility = remember(serial) { mutableStateOf(metadata.optString("status", "Unknown")) }
    val knownIssues = remember(serial) { mutableStateOf(metadata.optString("knownIssues", "")) }
    val firmwareNote = remember(serial) { mutableStateOf(metadata.optString("firmwareNote", "")) }
    val updateNote = remember(serial) { mutableStateOf(metadata.optString("updateNote", "")) }
    val notes = remember(serial) { mutableStateOf(metadata.optString("notes", "")) }
    val librarySearch = remember { mutableStateOf("") }
    val libraryEntries = extra100LibraryIndex(context).filter {
        librarySearch.value.isBlank() || it.contains(librarySearch.value, true)
    }
    val actionMessage = remember { mutableStateOf("No Extra 100 action performed.") }
    val fileReport = remember { mutableStateOf("No game file has been inspected.") }
    val transferReport = remember { mutableStateOf("No save-data file transfer performed.") }
    val selectedSave = remember { mutableStateOf<Uri?>(null) }
    val selectedRestore = remember { mutableStateOf<Uri?>(null) }
    val controllers = remember { mutableStateOf(extra100ControllerSummary()) }
    val lastInput = remember { mutableStateOf("No controller key received yet.") }
    val focusRequester = remember { FocusRequester() }
    val sessionKey = EXTRA100_PLAYTIME_PREFIX + extra100GameId(serial)
    val sessionStart = remember(serial) { mutableStateOf(prefs.getLong(sessionKey + ".activeSince", 0L)) }
    val totalPlaytime = remember(serial) { mutableStateOf(prefs.getLong(sessionKey + ".totalMs", 0L)) }
    val liveElapsed = remember(serial) { mutableStateOf(0L) }

    LaunchedEffect(sessionStart.value) {
        if (sessionStart.value > 0L) {
            while (true) {
                liveElapsed.value = (System.currentTimeMillis() - sessionStart.value).coerceAtLeast(0L)
                delay(1000L)
            }
        } else liveElapsed.value = 0L
    }

    val gameFilePicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) scope.launch {
            fileReport.value = withContext(Dispatchers.IO) { extra100InspectDocument(context, uri) }
        }
    }
    val saveFilePicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        selectedSave.value = uri
        if (uri != null) transferReport.value = "Selected save-data document. Choose Create backup to copy it safely."
    }
    val backupDestinationPicker = rememberLauncherForActivityResult(
        ActivityResultContracts.CreateDocument("application/octet-stream")
    ) { destination ->
        val source = selectedSave.value
        if (source != null && destination != null) scope.launch {
            transferReport.value = withContext(Dispatchers.IO) {
                runCatching { extra100CopyAndVerify(context, source, destination) }
                    .getOrElse { "Backup failed: " + (it.message ?: "unknown error") }
            }
        }
    }
    val restoreFilePicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        selectedRestore.value = uri
        if (uri != null) transferReport.value = "Selected backup document. Choose a destination file before restoring."
    }
    val restoreDestinationPicker = rememberLauncherForActivityResult(
        ActivityResultContracts.CreateDocument("application/octet-stream")
    ) { destination ->
        val source = selectedRestore.value
        if (source != null && destination != null) scope.launch {
            transferReport.value = withContext(Dispatchers.IO) {
                runCatching { extra100CopyAndVerify(context, source, destination) }
                    .getOrElse { "Restore copy failed: " + (it.message ?: "unknown error") }
            }
        }
    }

    Surface(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(18.dp),
        color = MaterialTheme.colorScheme.surfaceVariant) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text("TouchStation Extra · 100-feature companion suite", style = MaterialTheme.typography.titleLarge)
            Text("App-side library tools, safe document backup, controller input checks and device-session records. Native-core telemetry remains separately identified as unavailable.",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)

            Text("51–60 · Game library companion", style = MaterialTheme.typography.titleMedium)
            Text("Selected game ID: " + (serial ?: "No game selected"), style = MaterialTheme.typography.bodySmall)
            OutlinedTextField(value = title.value, onValueChange = { title.value = it },
                label = { Text("Display title / game name") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(value = category.value, onValueChange = { category.value = it },
                label = { Text("Category") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(value = tags.value, onValueChange = { tags.value = it },
                label = { Text("Tags (comma separated)") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("Favorite this game")
                Switch(checked = favorite.value, onCheckedChange = { favorite.value = it })
            }
            OutlinedTextField(value = compatibility.value, onValueChange = { compatibility.value = it },
                label = { Text("Handset compatibility status (user-entered)") },
                modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(value = knownIssues.value, onValueChange = { knownIssues.value = it },
                label = { Text("Known issues / troubleshooting notes") }, modifier = Modifier.fillMaxWidth(), minLines = 2)
            OutlinedTextField(value = firmwareNote.value, onValueChange = { firmwareNote.value = it },
                label = { Text("Firmware requirement / installed version note") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(value = updateNote.value, onValueChange = { updateNote.value = it },
                label = { Text("Game update / patch version note") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(value = notes.value, onValueChange = { notes.value = it },
                label = { Text("Personal game notes") }, modifier = Modifier.fillMaxWidth(), minLines = 2)
            Button(onClick = {
                extra100SaveMeta(context, serial, title.value, category.value, tags.value, favorite.value,
                    compatibility.value, knownIssues.value, firmwareNote.value, updateNote.value, notes.value)
                actionMessage.value = "Saved per-game library metadata for " + extra100GameId(serial) + "."
            }, enabled = !serial.isNullOrBlank(), modifier = Modifier.fillMaxWidth()) {
                Text("Save selected-game metadata")
            }
            OutlinedTextField(value = librarySearch.value, onValueChange = { librarySearch.value = it },
                label = { Text("Search saved game entries") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            Text("Local metadata index: " + libraryEntries.size + " saved entries", style = MaterialTheme.typography.bodySmall)
            libraryEntries.take(12).forEach { Text(it, style = MaterialTheme.typography.bodySmall) }
            Text("The index stores user-entered metadata; it does not replace the emulator's installed-game library.",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)

            Text("61–70 · Save-data and file safety", style = MaterialTheme.typography.titleMedium)
            OutlinedButton(onClick = { gameFilePicker.launch(arrayOf("*/*")) }, modifier = Modifier.fillMaxWidth()) {
                Text("Inspect selected game file")
            }
            Text(fileReport.value, style = MaterialTheme.typography.bodySmall)
            OutlinedButton(onClick = { saveFilePicker.launch(arrayOf("*/*")) }, modifier = Modifier.fillMaxWidth()) {
                Text("Choose one save-data file to back up")
            }
            Text("Selected source: " + (selectedSave.value?.lastPathSegment ?: "none"), style = MaterialTheme.typography.bodySmall)
            OutlinedButton(onClick = { backupDestinationPicker.launch("TouchStation-save-backup.bin") },
                enabled = selectedSave.value != null, modifier = Modifier.fillMaxWidth()) {
                Text("Create verified save-data backup")
            }
            OutlinedButton(onClick = { restoreFilePicker.launch(arrayOf("*/*")) }, modifier = Modifier.fillMaxWidth()) {
                Text("Choose a backup file to restore")
            }
            Text("Restore source: " + (selectedRestore.value?.lastPathSegment ?: "none"), style = MaterialTheme.typography.bodySmall)
            OutlinedButton(onClick = { restoreDestinationPicker.launch("TouchStation-restored-save.bin") },
                enabled = selectedRestore.value != null, modifier = Modifier.fillMaxWidth()) {
                Text("Copy backup to a chosen destination")
            }
            Text(transferReport.value, style = MaterialTheme.typography.bodySmall)
            Text("Transfers copy one user-selected document and verify SHA-256 after writing. They never overwrite emulator save folders automatically. File inspection checks readability and metadata only.",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)

            Text("71–80 · Controller and input checks", style = MaterialTheme.typography.titleMedium)
            OutlinedButton(onClick = { controllers.value = extra100ControllerSummary() }, modifier = Modifier.fillMaxWidth()) {
                Text("Refresh Android controller list")
            }
            Text(controllers.value, style = MaterialTheme.typography.bodySmall)
            Text("Tap this area to focus it, then press a controller button:",
                modifier = Modifier.fillMaxWidth().clickable { runCatching { focusRequester.requestFocus() } }
                    .focusRequester(focusRequester)
                    .onPreviewKeyEvent { event ->
                        if (event.type == KeyEventType.KeyDown) {
                            lastInput.value = "Android key code " + event.nativeKeyEvent.keyCode +
                                " · label " + event.nativeKeyEvent.displayLabel
                            true
                        } else false
                    }.focusable().padding(10.dp),
                style = MaterialTheme.typography.bodyMedium)
            Text("Last input: " + lastInput.value, style = MaterialTheme.typography.bodySmall)
            Text("This checks digital Android key events. Analog axis calibration and emulator remapping still depend on the native controller bridge.",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)

            Text("81–90 · Personalization and session tracking", style = MaterialTheme.typography.titleMedium)
            Text("Tracked time: " + extra100Duration(totalPlaytime.value + liveElapsed.value),
                style = MaterialTheme.typography.bodyMedium)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = {
                    sessionStart.value = System.currentTimeMillis()
                    prefs.edit().putLong(sessionKey + ".activeSince", sessionStart.value).apply()
                    actionMessage.value = "Started user-controlled playtime tracking."
                }, enabled = !serial.isNullOrBlank() && sessionStart.value == 0L,
                    modifier = Modifier.weight(1f)) { Text("Start session") }
                OutlinedButton(onClick = {
                    val elapsed = if (sessionStart.value > 0L)
                        (System.currentTimeMillis() - sessionStart.value).coerceAtLeast(0L) else 0L
                    totalPlaytime.value += elapsed
                    sessionStart.value = 0L
                    prefs.edit().putLong(sessionKey + ".activeSince", 0L)
                        .putLong(sessionKey + ".totalMs", totalPlaytime.value).apply()
                    actionMessage.value = "Saved user-controlled playtime session."
                }, enabled = sessionStart.value > 0L, modifier = Modifier.weight(1f)) { Text("Stop and save") }
            }
            Text("The timer is user-started and measures wall-clock time; it is not an automatic emulator gameplay detector.",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)

            Text("91–100 · Diagnostics, performance evidence and recovery", style = MaterialTheme.typography.titleMedium)
            OutlinedButton(onClick = { actionMessage.value = extra100CaptureMetrics(context, serial) },
                modifier = Modifier.fillMaxWidth()) { Text("Capture Android performance snapshot") }
            Text(extra100CompareMetrics(context, serial), style = MaterialTheme.typography.bodySmall)
            OutlinedButton(onClick = {
                extra100Share(context, "TouchStation Extra · app-side diagnostics\n" +
                    extra100SelfChecks(context, settings, serial) + "\n" +
                    "Performance comparison: " + extra100CompareMetrics(context, serial) + "\n" +
                    "Compatibility record: " + compatibility.value +
                    "\nFirmware/update notes are user-entered and require manual verification.")
                actionMessage.value = "Opened Android share sheet for the app-side diagnostic report."
            }, modifier = Modifier.fillMaxWidth()) { Text("Share Extra 100 diagnostic report") }
            OutlinedButton(onClick = { actionMessage.value = extra100SelfChecks(context, settings, serial) },
                modifier = Modifier.fillMaxWidth()) { Text("Run app-side regression and readiness checks") }
            Text(actionMessage.value, style = MaterialTheme.typography.bodySmall)
            Text("Android RAM, battery and storage values are device metrics. PPU/SPU/RSX counters, guest crash callbacks, GPU utilization and live shader/FIFO internals remain unavailable until the native core exports them.",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}
