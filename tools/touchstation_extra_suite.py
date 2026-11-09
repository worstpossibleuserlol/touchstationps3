#!/usr/bin/env python3
"""Generate TouchStation Extra diagnostics and crash-loop protection."""
from __future__ import annotations

import argparse
from pathlib import Path

EXTRA_KOTLIN_SOURCE = r'''package com.armsx2.ui.settings

import android.app.ActivityManager
import android.content.Context
import android.hardware.display.DisplayManager
import android.os.Build
import android.os.Debug
import android.os.StatFs
import android.view.Display
import androidx.compose.foundation.layout.Arrangement
import androidx.core.content.edit
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
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.armsx2.config.Settings
import com.armsx2.config.SettingsScope
import com.armsx2.reliability.TouchStationExtraCrashLoopGuard
import com.armsx2.reliability.TouchStationFinaleReliability
import com.armsx2.reliability.TouchStationFinaleRuntimeGuard
import com.armsx2.runtime.MainActivityRuntime
import com.armsx2.ui.InGameOverlay
import com.armsx3.core.ARMSX3
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.util.Locale

@Composable
private fun extraRow(label: String, value: String) {
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

private fun extraLibraryReport(context: Context): String {
    val dir = File(context.applicationInfo.nativeLibraryDir.orEmpty())
    return listOf("libarmsx3-core.so", "libarmsx3-jni.so").joinToString("; ") { name ->
        val file = File(dir, name)
        name + ": " + if (file.isFile && file.length() > 0L) "present" else "missing"
    }
}

private fun extraJvmThreads(): String = runCatching {
    val threads = Thread.getAllStackTraces().keys.filter { it.isAlive }
    val states = threads.groupingBy { it.state.name }.eachCount().toSortedMap()
    "JVM threads=" + threads.size + "; " +
        states.entries.joinToString { it.key + "=" + it.value } +
        "; native PPU/SPU thread identity/state=N/A"
}.getOrDefault("JVM thread snapshot unavailable")

private fun extraVulkan(context: Context): String = runCatching {
    context.packageManager.systemAvailableFeatures
        .filter { it.name?.contains("vulkan", true) == true }
        .joinToString { (it.name ?: "Vulkan") + " v" + it.version }
        .ifBlank { "No Vulkan system feature advertised" } +
        "; physical-device extensions/counters=N/A"
}.getOrDefault("Vulkan capability query unavailable")

private fun extraGraphics(context: Context): String = runCatching {
    val manager = context.getSystemService(Context.ACTIVITY_SERVICE) as? ActivityManager
    val gl = manager?.deviceConfigurationInfo?.reqGlEsVersion ?: 0
    val version = if (gl > 0) ((gl shr 16) and 0xffff).toString() + "." + (gl and 0xffff) else "N/A"
    "Hardware=" + Build.HARDWARE + "; required GLES=" + version +
        "; driver vendor/renderer=N/A without native graphics query"
}.getOrDefault("Graphics capability report unavailable")

private fun extraRefreshRate(context: Context): String = runCatching {
    val manager = context.getSystemService(Context.DISPLAY_SERVICE) as? DisplayManager
    val rate = manager?.getDisplay(Display.DEFAULT_DISPLAY)?.refreshRate
    rate?.takeIf { it > 0f }?.let { String.format(Locale.US, "%.1f Hz", it) } ?: "N/A"
}.getOrDefault("N/A")

private fun extraMemory(context: Context): String = runCatching {
    val manager = context.getSystemService(Context.ACTIVITY_SERVICE) as? ActivityManager
    val memory = ActivityManager.MemoryInfo()
    manager?.getMemoryInfo(memory)
    "Available RAM=" + memory.availMem / (1024L * 1024L) + " MB; app PSS=" +
        Debug.getPss() / 1024L + " MB; native allocations=N/A"
}.getOrDefault("Android memory snapshot unavailable")

private fun extraStorage(context: Context): String = runCatching {
    val stats = StatFs(context.filesDir.absolutePath)
    val free = stats.availableBytes
    val state = when {
        free < 1024L * 1024L * 1024L -> "CRITICAL"
        free < 3L * 1024L * 1024L * 1024L -> "WARNING"
        else -> "OK"
    }
    state + "; " + free / (1024L * 1024L) + " MB app-private free"
}.getOrDefault("Storage statistics unavailable")

private fun extraCacheReport(context: Context): String =
    "app cache: " + TouchStationFinaleReliability.inspectDirectory(context.cacheDir) +
    "; code cache: " + TouchStationFinaleReliability.inspectDirectory(context.codeCacheDir) +
    "; native PPU/SPU/shader cache internals=N/A"

private fun extraPreflight(context: Context, settings: Settings): String = buildString {
    appendLine("TouchStation Extra preflight")
    appendLine(TouchStationFinaleReliability.startupSelfTest(context, settings))
    appendLine("Native libraries: " + extraLibraryReport(context))
    appendLine("Engine initialized: " + ARMSX3.initialized)
    appendLine("Native runtime ready: " + MainActivityRuntime.nativeReady.value)
    appendLine("JVM threads: " + extraJvmThreads())
    appendLine("Graphics: " + extraGraphics(context))
    appendLine("Vulkan: " + extraVulkan(context))
    appendLine("Display refresh: " + extraRefreshRate(context))
    appendLine("Memory: " + extraMemory(context))
    appendLine("Storage: " + extraStorage(context))
    appendLine("Crash loop: " + TouchStationExtraCrashLoopGuard.status(context))
    appendLine("Cache inventory: " + extraCacheReport(context))
    appendLine("Native PPU/SPU/RSX internals remain N/A unless exported by the pinned core.")
}

@Composable
fun TouchStationExtraDiagnostics(
    settings: Settings,
    onApply: (Settings) -> Boolean,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val report = remember { mutableStateOf("Run Extra preflight to refresh diagnostics.") }
    val profileMessage = remember { mutableStateOf("No Extra profile applied this session.") }
    val cleanupMessage = remember { mutableStateOf("No cleanup requested.") }
    val game = MainActivityRuntime.currentGame.value
    val serial = game?.serial?.takeIf { it.isNotBlank() }
        ?: game?.settingsKey?.takeIf { it.isNotBlank() }
    val gameScope = InGameOverlay.settingsScope.value == SettingsScope.Game
    val safeMode = TouchStationFinaleReliability.isSafeMode(context)

    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(18.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text("TouchStation Extra", style = MaterialTheme.typography.titleLarge)
            Text(
                "30 additional PPU, SPU, RSX, graphics, recovery and Android reliability checks. Unsupported native metrics stay N/A.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Button(
                onClick = {
                    scope.launch {
                        report.value = "Collecting diagnostics…"
                        report.value = withContext(Dispatchers.IO) { extraPreflight(context, settings) }
                    }
                },
                modifier = Modifier.fillMaxWidth(),
            ) { Text("Run Extra preflight and diagnostics") }
            Text(report.value, style = MaterialTheme.typography.bodySmall)

            Text("01–10 · PPU and SPU", style = MaterialTheme.typography.titleMedium)
            extraRow("01 · PPU execution diagnostics", "Native counters/live execution state: N/A")
            extraRow("02 · PPU module validator", "Native module registry: N/A; package libraries: " + extraLibraryReport(context))
            extraRow("03 · PPU thread-state monitor", extraJvmThreads())
            extraRow("04 · PPU exception reporter", "Recorded game errors: " + TouchStationFinaleErrorHistory.eventCount() + "; latest: " + TouchStationFinaleErrorHistory.latestMessage().take(100))
            extraRow("05 · PPU cache integrity", extraCacheReport(context))
            extraRow("06 · SPU task diagnostics", "Native SPU task IDs/queue: N/A")
            extraRow("07 · SPU workload monitor", "Decoder=" + settings.ps3.spuDecoder + "; block=" + settings.ps3.spuBlockSize + "; preferred threads=" + settings.ps3.preferredSpuThreads)
            extraRow("08 · SPU timeout reporting", "Native task timeout=N/A; Android watchdog=" + TouchStationFinaleRuntimeGuard.activeSummary())
            extraRow("09 · SPU module validation", "Native SPU module registry: N/A")
            extraRow("10 · Native engine self-test", TouchStationFinaleRuntimeGuard.nativeCoreHealth(context, ARMSX3.initialized, MainActivityRuntime.nativeReady.value))

            Text("11–20 · RSX and graphics", style = MaterialTheme.typography.titleMedium)
            extraRow("11 · RSX command diagnostics", "Native command stream=N/A; FIFO errors=" + TouchStationFinaleErrorHistory.fifoFailureCount())
            extraRow("12 · FIFO queue health", "Error history available; live queue depth/progress=N/A")
            extraRow("13 · GPU synchronization", "GPU fence/synchronization telemetry=N/A")
            extraRow("14 · Shader compilation tracker", "Live shader job counters=N/A; known caches: " + extraCacheReport(context))
            extraRow("15 · Shader cache recovery", "Only orphaned TouchStation logcat temp file may be cleaned; emulator shader caches remain untouched")
            extraRow("16 · Vulkan capability checker", extraVulkan(context))
            extraRow("17 · Graphics driver report", extraGraphics(context))
            extraRow("18 · Frame pacing monitor", "Display=" + extraRefreshRate(context) + "; FPS/frametime use native in-game overlay")
            extraRow("19 · Resolution scaling profiles", "Output scaler=" + settings.hwScaler + "; GPU profile=" + settings.gpuProfile + "; internal RSX resolution unchanged")
            extraRow("20 · Graphics settings rollback", TouchStationFinaleSettingsRollback.description())

            Text("21–30 · Stability, recovery and storage", style = MaterialTheme.typography.titleMedium)
            extraRow("21 · Game launch preflight", "Engine=" + ARMSX3.initialized + "; runtime=" + MainActivityRuntime.nativeReady.value + "; game=" + (game?.title ?: "none"))
            extraRow("22 · Boot failure classifier", TouchStationFinaleErrorHistory.explanation(TouchStationFinaleErrorHistory.latestMessage()))
            extraRow("23 · Crash-loop protection", TouchStationExtraCrashLoopGuard.status(context))
            extraRow("24 · Session recovery report", TouchStationFinaleSettingsRollback.description() + "; " + TouchStationFinaleReliability.lifecycleStatus())
            extraRow("25 · Memory allocation diagnostics", extraMemory(context) + "; native allocations=N/A")
            extraRow("26 · Cache cleanup manager", cleanupMessage.value)
            extraRow("27 · Storage health warnings", extraStorage(context))
            extraRow("28 · Android lifecycle protection", TouchStationFinaleReliability.lifecycleStatus())
            extraRow("29 · Automated regression suite", "Patcher tests run in this GitHub Actions build; this screen does not run native-core tests")
            extraRow("30 · Per-game stability profiles", "Game=" + (game?.title ?: "none") + "; scope=" + if (gameScope) "Game" else "Global")

            OutlinedButton(
                onClick = {
                    val temporary = File(context.cacheDir, "TouchStation-logcat.tmp")
                    cleanupMessage.value = when {
                        !temporary.exists() -> "No orphaned TouchStation diagnostic temp file found; emulator caches unchanged."
                        temporary.isFile && temporary.delete() -> "Removed only TouchStation-logcat.tmp; games, firmware and emulator caches unchanged."
                        else -> "Could not remove temporary file; no other files changed."
                    }
                },
                modifier = Modifier.fillMaxWidth(),
            ) { Text("Clean orphaned TouchStation diagnostic temp file") }

            Button(
                onClick = {
                    if (game == null || serial.isNullOrBlank() || !gameScope || safeMode) {
                        profileMessage.value = "Select a game, activate Game scope and disable safe mode first."
                    } else {
                        val cores = Runtime.getRuntime().availableProcessors().coerceAtLeast(1)
                        val stable = settings.copy(
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
                        val applied = runCatching { onApply(stable) }.getOrDefault(false)
                        if (applied) {
                            context.getSharedPreferences("touchstation-extra-profiles", Context.MODE_PRIVATE)
                                .edit().putString("game." + serial, "Conservative stability profile").apply()
                            profileMessage.value = "Profile saved and settings read-back verified for " + (game.title ?: serial) + "."
                        } else {
                            profileMessage.value = "Profile not confirmed; settings read-back failed."
                        }
                    }
                },
                enabled = game != null && !serial.isNullOrBlank() && gameScope && !safeMode,
                modifier = Modifier.fillMaxWidth(),
            ) { Text("Apply per-game conservative stability profile") }
            Text(profileMessage.value, style = MaterialTheme.typography.bodySmall)
            Text(
                "This uses existing supported settings only. Native PPU/SPU worker control, RSX queue repair, GPU fence recovery and physical GPU utilization require native-core instrumentation and are not simulated.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}
'''

EXTRA_CRASH_LOOP_KOTLIN_SOURCE = r'''package com.armsx2.reliability

import android.app.Application
import android.content.Context

/** Enables the existing safe mode after repeated uncaught app crashes. */
object TouchStationExtraCrashLoopGuard {
    private const val PREFS = "touchstation-extra-crash-loop"
    private const val KEY_TIMES = "crashTimes"
    private const val WINDOW_MS = 10L * 60L * 1000L
    private const val LIMIT = 3
    private val lock = Any()
    @Volatile private var installed = false

    private fun recent(context: Context, now: Long = System.currentTimeMillis()): List<Long> {
        val values = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY_TIMES, "").orEmpty()
        return values.split(',').mapNotNull { it.toLongOrNull() }
            .filter { it in (now - WINDOW_MS)..now }.takeLast(20)
    }

    fun status(context: Context): String {
        val count = recent(context).size
        return if (count >= LIMIT) {
            "SAFE MODE RECOMMENDED — " + count + " crashes within 10 minutes"
        } else {
            count.toString() + " of " + LIMIT + " crashes in the 10-minute window"
        }
    }

    fun install(application: Application) {
        synchronized(lock) {
            if (installed) return
            installed = true
        }
        val previous = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { thread, error ->
            val now = System.currentTimeMillis()
            val count = synchronized(lock) {
                val times = (recent(application, now) + now).takeLast(20)
                application.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
                    .putString(KEY_TIMES, times.joinToString(",")).apply()
                times.size
            }
            TouchStationFinaleReliability.recordEvent(
                application, "crash-loop-guard",
                "Uncaught crash on " + thread.name + "; recent count=" + count,
            )
            if (count >= LIMIT) {
                TouchStationFinaleReliability.setSafeMode(application, true)
                TouchStationFinaleReliability.recordEvent(
                    application, "crash-loop-guard",
                    "Three or more uncaught crashes within 10 minutes; safe mode enabled for next launch.",
                )
            }
            previous?.uncaughtException(thread, error)
        }
        if (recent(application).size >= LIMIT) {
            TouchStationFinaleReliability.setSafeMode(application, true)
        }
    }
}
'''


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Expected exactly one {label} marker; found {count}")
    return text.replace(old, new, 1)


def patch_version(app_dir: Path) -> None:
    path = app_dir / "build.gradle.kts"
    text = path.read_text(encoding="utf-8")
    if "versionCode = 1200" not in text or 'versionName = "TouchStation Finale"' not in text:
        raise SystemExit("Expected prepared TouchStation Finale / versionCode 1200 before Extra promotion")
    text = replace_once(text, "versionCode = 1200", "versionCode = 1300", "versionCode")
    text = replace_once(text, 'versionName = "TouchStation Finale"', 'versionName = "TouchStation Extra"', "versionName")
    path.write_text(text, encoding="utf-8")


def patch_performance_tab(app_dir: Path) -> None:
    path = app_dir / "PerformanceTab.kt"
    text = path.read_text(encoding="utf-8")
    if "TouchStationExtraDiagnostics(" in text:
        raise SystemExit("TouchStation Extra diagnostics call already exists")
    start = text.find("        TouchStationFinaleSuite(")
    if start < 0:
        raise SystemExit("TouchStation Finale suite call not found")
    divider = text.find("        SettingsDivider()", start)
    if divider < 0:
        raise SystemExit("TouchStation Finale suite divider not found")
    end = text.find("\n\n", divider)
    if end < 0:
        raise SystemExit("Could not locate end of TouchStation Finale suite block")
    addition = '''
        TouchStationExtraDiagnostics(
            settings = s,
            onApply = { updated ->
                runCatching {
                    apply(updated)
                    InGameOverlay.reloadSettings()
                    val saved = InGameOverlay.settingsState.value
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
                }.getOrDefault(false)
            },
        )
        SettingsDivider()

'''
    text = text[:end + 2] + addition + text[end + 2:]
    path.write_text(text, encoding="utf-8")


def patch_application(app_dir: Path) -> None:
    path = app_dir / "src/main/java/com/armsx2/Pasx2Application.kt"
    text = path.read_text(encoding="utf-8")
    call = "TouchStationExtraCrashLoopGuard.install(this)"
    if call in text:
        raise SystemExit("TouchStation Extra crash-loop guard already installed")
    import_anchor = "import com.armsx2.reliability.TouchStationFinaleReliability\n"
    text = replace_once(
        text, import_anchor,
        import_anchor + "import com.armsx2.reliability.TouchStationExtraCrashLoopGuard\n",
        "Extra crash-loop import",
    )
    call_anchor = "TouchStationFinaleReliability.install(this)\n"
    text = replace_once(
        text, call_anchor,
        call_anchor + "\t\tTouchStationExtraCrashLoopGuard.install(this)\n",
        "Extra crash-loop initialization",
    )
    path.write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args()
    app_dir = args.source / "app"
    settings_dir = app_dir / "src/main/java/com/armsx2/ui/settings"
    reliability_dir = app_dir / "src/main/java/com/armsx2/reliability"
    for path in (
        app_dir / "build.gradle.kts",
        settings_dir / "PerformanceTab.kt",
        settings_dir / "TouchStationFinaleSuite.kt",
        app_dir / "src/main/java/com/armsx2/Pasx2Application.kt",
    ):
        if not path.is_file():
            raise SystemExit("Missing required prepared source file: " + str(path))
    new_ui = settings_dir / "TouchStationExtraDiagnostics.kt"
    new_guard = reliability_dir / "TouchStationExtraCrashLoopGuard.kt"
    if new_ui.exists() or new_guard.exists():
        raise SystemExit("Extra Kotlin source already exists; refusing to overwrite")
    patch_version(app_dir)
    reliability_dir.mkdir(parents=True, exist_ok=True)
    new_ui.write_text(EXTRA_KOTLIN_SOURCE, encoding="utf-8")
    new_guard.write_text(EXTRA_CRASH_LOOP_KOTLIN_SOURCE, encoding="utf-8")
    patch_performance_tab(settings_dir)
    patch_application(app_dir)
    print("Applied TouchStation Extra diagnostics and crash-loop protection.")


if __name__ == "__main__":
    main()
