/*DIAGNOSTICS-BEGIN*/
package com.armsx2.reliability
import android.content.Context
import android.util.Log
import org.json.JSONArray
import org.json.JSONObject

/** Persisted app-side shutdown evidence; not a source of native PPU/SPU/RSX telemetry. */
object TouchStationExtraShutdownDiagnostics {
    private const val PREFS = "touchstation-extra-shutdown"
    private const val KEY_EVENTS = "events"
    private const val MAX_EVENTS = 100
    private val lock = Any()

    fun record(context: Context, stage: String, details: String = "") {
        runCatching {
            synchronized(lock) {
                val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                val old = runCatching { JSONArray(prefs.getString(KEY_EVENTS, "[]") ?: "[]") }
                    .getOrDefault(JSONArray())
                val next = JSONArray()
                for (index in (old.length() - MAX_EVENTS + 1).coerceAtLeast(0) until old.length()) {
                    old.optJSONObject(index)?.let { next.put(it) }
                }
                next.put(JSONObject()
                    .put("timestamp", System.currentTimeMillis())
                    .put("stage", stage.take(80))
                    .put("details", details.take(500)))
                // Persist before entering native code so the last stage can survive process death.
                prefs.edit().putString(KEY_EVENTS, next.toString()).commit()
            }
            Log.i("TouchStationShutdown", stage + ": " + details.take(240))
        }
    }

    fun report(context: Context): String = runCatching {
        val events = synchronized(lock) {
            JSONArray(context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .getString(KEY_EVENTS, "[]") ?: "[]")
        }
        if (events.length() == 0) return@runCatching "No shutdown events recorded yet."
        var lastStarted = -1
        var lastCompleted = -1
        for (index in 0 until events.length()) {
            val stage = events.optJSONObject(index)?.optString("stage").orEmpty()
            if (stage == "native-shutdown-started") lastStarted = index
            if (stage == "shutdown-completed") lastCompleted = index
        }
        buildString {
            appendLine("Persisted shutdown events: " + events.length())
            if (lastStarted > lastCompleted) {
                appendLine("WARNING: the latest native shutdown did not record a clean completion.")
                appendLine("The last stage may help distinguish a native shutdown crash from an Android lifecycle failure.")
            } else {
                appendLine("Latest recorded shutdown: completed, or no incomplete shutdown was recorded.")
            }
            appendLine("Recent stages:")
            for (index in (events.length() - 18).coerceAtLeast(0) until events.length()) {
                val item = events.optJSONObject(index) ?: continue
                val time = android.text.format.DateFormat.format("MM-dd HH:mm:ss", item.optLong("timestamp"))
                appendLine(time.toString() + " · " + item.optString("stage") + " · " + item.optString("details"))
            }
            appendLine("Android process-exit reasons are separate from guest-game crash callbacks.")
            appendLine("PPU/SPU/RSX internals and GPU fences remain unavailable unless the native core exports them.")
        }
    }.getOrDefault("Shutdown report unavailable.")

    fun recordManualObservation(context: Context, outcome: String) {
        record(context, "manual-observation", outcome)
    }
}
/*DIAGNOSTICS-END*/

/*SUITE-BEGIN*/
package com.armsx2.ui.settings
import android.content.Intent
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
import com.armsx2.reliability.TouchStationExtraShutdownDiagnostics
import com.armsx2.runtime.MainActivityRuntime

@Composable
fun TouchStationExtraShutdownSuite() {
    val context = LocalContext.current
    val report = remember { mutableStateOf(TouchStationExtraShutdownDiagnostics.report(context)) }
    val message = remember { mutableStateOf("No manual shutdown observation recorded this session.") }
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(18.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(9.dp)) {
            Text("TouchStation Extra · Shutdown & crash diagnostics", style = MaterialTheme.typography.titleLarge)
            Text(
                "Single-flight stop requests, native shutdown stage history and next-launch evidence. No native thread is force-killed.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                "VM state: " + MainActivityRuntime.eState.value.name +
                    " · stop in progress: " + MainActivityRuntime.isVmStopInProgress(),
                style = MaterialTheme.typography.bodySmall,
            )
            Button(
                onClick = { report.value = TouchStationExtraShutdownDiagnostics.report(context) },
                modifier = Modifier.fillMaxWidth(),
            ) { Text("Refresh shutdown report") }
            Text(report.value, style = MaterialTheme.typography.bodySmall)
            Text("After testing a game exit, record what actually happened:", style = MaterialTheme.typography.bodyMedium)
            Row(horizontalArrangement = Arrangement.spacedBy(7.dp)) {
                OutlinedButton(
                    onClick = {
                        TouchStationExtraShutdownDiagnostics.recordManualObservation(context, "User observed a clean return to the library.")
                        message.value = "Recorded: clean return to library."
                        report.value = TouchStationExtraShutdownDiagnostics.report(context)
                    },
                    modifier = Modifier.weight(1f),
                ) { Text("Clean exit") }
                OutlinedButton(
                    onClick = {
                        TouchStationExtraShutdownDiagnostics.recordManualObservation(context, "User observed an app crash back to Android home.")
                        message.value = "Recorded: crash to Android home."
                        report.value = TouchStationExtraShutdownDiagnostics.report(context)
                    },
                    modifier = Modifier.weight(1f),
                ) { Text("Crashed to home") }
            }
            OutlinedButton(
                onClick = {
                    TouchStationExtraShutdownDiagnostics.recordManualObservation(context, "User observed the app remain on the stopping screen.")
                    message.value = "Recorded: stuck on stopping."
                    report.value = TouchStationExtraShutdownDiagnostics.report(context)
                },
                modifier = Modifier.fillMaxWidth(),
            ) { Text("Stuck on stopping") }
            Text(message.value, style = MaterialTheme.typography.bodySmall)
            OutlinedButton(
                onClick = {
                    runCatching {
                        val intent = Intent(Intent.ACTION_SEND).apply {
                            type = "text/plain"
                            putExtra(Intent.EXTRA_TEXT, TouchStationExtraShutdownDiagnostics.report(context))
                        }
                        context.startActivity(Intent.createChooser(intent, "Share shutdown diagnostics"))
                    }.onFailure { message.value = "Could not open Android share sheet: " + (it.message ?: "unknown error") }
                },
                modifier = Modifier.fillMaxWidth(),
            ) { Text("Share shutdown report") }
            Text(
                "A native SIGSEGV can still terminate the Android process. The report preserves the last stage reached, but the prebuilt native engine cannot be repaired from Kotlin alone.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}
/*SUITE-END*/
