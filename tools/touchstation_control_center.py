#!/usr/bin/env python3
"""Add the TouchStation 6.0.0 device Control Center to the pinned upstream app."""
from __future__ import annotations

import argparse
import re
from pathlib import Path


CONTROL_CENTER_SOURCE = r'''package com.armsx2.ui.settings

import android.app.ActivityManager
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.net.Uri
import android.os.BatteryManager
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
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.armsx2.runtime.MainActivityRuntime
import com.armsx2.ui.controls.TouchStationControllerMonitor
import com.armsx3.core.ARMSX3
import kotlinx.coroutines.delay
import java.util.Locale

private data class TouchStationDeviceSnapshot(
    val soc: String,
    val android: String,
    val thermalStatus: Int?,
    val batteryPercent: Int?,
    val batteryTemperatureC: Float?,
    val totalRamMb: Long?,
    val availableRamMb: Long?,
    val appPssMb: Int?,
    val freeStorageMb: Long?,
    val vulkan: String,
)

private fun readTouchStationDeviceSnapshot(context: Context): TouchStationDeviceSnapshot {
    val soc = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
        listOf(Build.SOC_MANUFACTURER, Build.SOC_MODEL)
            .filter { it.isNotBlank() && !it.equals("unknown", ignoreCase = true) }
            .joinToString(" ")
            .ifBlank { Build.HARDWARE.ifBlank { "Not reported" } }
    } else {
        Build.HARDWARE.ifBlank { "Not reported" }
    }
    val thermal = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
        runCatching {
            (context.getSystemService(Context.POWER_SERVICE) as? PowerManager)?.currentThermalStatus
        }.getOrNull()
    } else null
    val battery = runCatching {
        context.registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
    }.getOrNull()
    val batteryPercent = battery?.let {
        val level = it.getIntExtra(BatteryManager.EXTRA_LEVEL, -1)
        val scale = it.getIntExtra(BatteryManager.EXTRA_SCALE, -1)
        if (level >= 0 && scale > 0) (level * 100 / scale).coerceIn(0, 100) else null
    }
    val batteryTemperature = battery?.getIntExtra(
        BatteryManager.EXTRA_TEMPERATURE, Int.MIN_VALUE,
    )?.takeIf { it != Int.MIN_VALUE && it > 0 }?.div(10f)

    val manager = context.getSystemService(Context.ACTIVITY_SERVICE) as? ActivityManager
    val memory = ActivityManager.MemoryInfo()
    runCatching { manager?.getMemoryInfo(memory) }
    val totalRam = memory.totalMem.takeIf { it > 0L }?.div(1024L * 1024L)
    val availableRam = memory.availMem.takeIf { it > 0L }?.div(1024L * 1024L)
    val appPss = runCatching {
        val info = Debug.MemoryInfo()
        Debug.getMemoryInfo(info)
        info.totalPss.takeIf { it > 0 }?.div(1024)
    }.getOrNull()
    val freeStorage = runCatching {
        StatFs(context.filesDir.absolutePath).availableBytes / (1024L * 1024L)
    }.getOrNull()
    val vulkan = runCatching {
        val features = context.packageManager.systemAvailableFeatures
        val level = features.firstOrNull { it.name == "android.hardware.vulkan.level" }
        val version = features.firstOrNull { it.name == "android.hardware.vulkan.version" }
        when {
            level != null && version != null ->
                "Reported by Android (level " + level.version + ", version code " + version.version + ")"
            level != null -> "Reported by Android (level " + level.version + ")"
            version != null -> "Reported by Android (version code " + version.version + ")"
            else -> "Not reported by Android"
        }
    }.getOrDefault("Not available")

    return TouchStationDeviceSnapshot(
        soc = soc,
        android = Build.VERSION.RELEASE + " (API " + Build.VERSION.SDK_INT + ")",
        thermalStatus = thermal,
        batteryPercent = batteryPercent,
        batteryTemperatureC = batteryTemperature,
        totalRamMb = totalRam,
        availableRamMb = availableRam,
        appPssMb = appPss,
        freeStorageMb = freeStorage,
        vulkan = vulkan,
    )
}

private fun touchStationThermalLabel(status: Int?): String {
    if (status == null) return "N/A (Android thermal status unavailable)"
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

@Composable
fun TouchStationControlCenter() {
    val context = LocalContext.current
    val controllers by TouchStationControllerMonitor.state
    var snapshot by remember { mutableStateOf(readTouchStationDeviceSnapshot(context)) }
    LaunchedEffect(context) {
        TouchStationControllerMonitor.start(context.applicationContext)
        while (true) {
            TouchStationControllerMonitor.refresh()
            snapshot = readTouchStationDeviceSnapshot(context)
            delay(2_500)
        }
    }

    val thermal = snapshot.thermalStatus
    val warning = thermal != null && thermal >= PowerManager.THERMAL_STATUS_MODERATE
    val severe = thermal != null && thermal >= PowerManager.THERMAL_STATUS_SEVERE
    val warningColor = when {
        severe -> MaterialTheme.colorScheme.errorContainer
        warning -> MaterialTheme.colorScheme.tertiaryContainer
        else -> MaterialTheme.colorScheme.surfaceVariant
    }
    val currentGame = MainActivityRuntime.currentGame.value?.title
        ?.takeIf { it.isNotBlank() } ?: "No game running"
    val engineReady = runCatching { ARMSX3.initialized }.getOrDefault(false)
    val controllerNames = controllers.devices.joinToString { it.name }
        .ifBlank { "No physical controller detected" }

    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(18.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(9.dp)) {
            Text("TouchStation Control Center", style = MaterialTheme.typography.titleLarge)
            Text(
                "Live device diagnostics · refreshed every 2.5 seconds",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(12.dp),
                color = warningColor,
            ) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                    Text(
                        "Thermal status: " + touchStationThermalLabel(thermal),
                        style = MaterialTheme.typography.titleSmall,
                    )
                    Text(
                        when {
                            severe -> "Android reports high thermal pressure. Consider pausing and allowing the device to cool."
                            warning -> "Android reports rising thermal pressure. Performance may be reduced to protect the device."
                            thermal == null -> "This Android build does not expose a thermal status reading to the app."
                            else -> "No Android thermal warning is currently reported."
                        },
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
            }

            Text("Device", style = MaterialTheme.typography.titleMedium)
            TouchStationControlRow("SoC / hardware", snapshot.soc)
            TouchStationControlRow("Android", snapshot.android)
            TouchStationControlRow("System RAM", snapshot.totalRamMb?.let { it.toString() + " MB" } ?: "N/A")
            TouchStationControlRow("Available RAM", snapshot.availableRamMb?.let { it.toString() + " MB" } ?: "N/A")
            TouchStationControlRow("TouchStation app RAM", snapshot.appPssMb?.let { it.toString() + " MB PSS" } ?: "N/A")
            TouchStationControlRow("Free internal storage", snapshot.freeStorageMb?.let { it.toString() + " MB" } ?: "N/A")
            TouchStationControlRow("Battery level", snapshot.batteryPercent?.let { it.toString() + "%" } ?: "N/A")
            TouchStationControlRow(
                "Battery temperature",
                snapshot.batteryTemperatureC?.let {
                    String.format(Locale.US, "%.1f °C (battery sensor)", it)
                } ?: "N/A",
            )
            TouchStationControlRow("Vulkan feature", snapshot.vulkan)

            Text("Emulator and session", style = MaterialTheme.typography.titleMedium)
            TouchStationControlRow("Native engine", if (engineReady) "Initialized" else "Not initialized")
            TouchStationControlRow("Current game", currentGame)
            TouchStationControlRow("Physical controllers", controllerNames)
            Text(
                "CPU, GPU and FPS graphs are shown above in the Performance Monitor. GPU values depend on readable driver counters. FPS is shown only when the native bridge supplies a real value. Battery temperature is not SoC temperature, and Android thermal status is a severity level rather than a temperature reading.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            Button(
                onClick = {
                    val report = buildString {
                        appendLine("TouchStation 6.0.0 diagnostic report")
                        appendLine("Device: " + Build.MANUFACTURER + " " + Build.MODEL)
                        appendLine("SoC / hardware: " + snapshot.soc)
                        appendLine("Android: " + snapshot.android)
                        appendLine("Supported ABIs: " + Build.SUPPORTED_ABIS.joinToString())
                        appendLine("Native engine initialized: " + engineReady)
                        appendLine("Current game: " + currentGame)
                        appendLine("Physical controllers: " + controllerNames)
                        appendLine("Thermal status: " + touchStationThermalLabel(snapshot.thermalStatus))
                        appendLine("Battery level: " + (snapshot.batteryPercent?.let { it.toString() + "%" } ?: "N/A"))
                        appendLine("Battery temperature: " + (snapshot.batteryTemperatureC?.let {
                            String.format(Locale.US, "%.1f °C (battery sensor)", it)
                        } ?: "N/A"))
                        appendLine("Vulkan feature: " + snapshot.vulkan)
                        appendLine("System RAM: " + (snapshot.totalRamMb?.let { it.toString() + " MB" } ?: "N/A"))
                        appendLine("Available RAM: " + (snapshot.availableRamMb?.let { it.toString() + " MB" } ?: "N/A"))
                        appendLine("App PSS: " + (snapshot.appPssMb?.let { it.toString() + " MB" } ?: "N/A"))
                        appendLine("Free internal storage: " + (snapshot.freeStorageMb?.let { it.toString() + " MB" } ?: "N/A"))
                        appendLine("CPU/GPU/FPS readings are in the in-app Performance Monitor when exposed by the OS, driver or core.")
                    }
                    val send = Intent(Intent.ACTION_SEND).apply {
                        type = "text/plain"
                        putExtra(Intent.EXTRA_SUBJECT, "TouchStation diagnostic report")
                        putExtra(Intent.EXTRA_TEXT, report)
                    }
                    runCatching {
                        context.startActivity(Intent.createChooser(send, "Share diagnostic report"))
                    }
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Export diagnostic report")
            }
            OutlinedButton(
                onClick = {
                    runCatching {
                        context.startActivity(
                            Intent(
                                Intent.ACTION_VIEW,
                                Uri.parse("https://github.com/worstpossibleuserlol/touchstationps3/issues/new?template=bug_report.yml"),
                            ),
                        )
                    }
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Report a Bug")
            }
        }
    }
}

@Composable
private fun TouchStationControlRow(title: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(
            title,
            modifier = Modifier.weight(0.9f),
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            value,
            modifier = Modifier.weight(1.1f),
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}
'''


def replace_once(text: str, old: str, new: str, description: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Expected exactly one {description} marker; found {count}")
    return text.replace(old, new, 1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args()
    app_dir = args.source / "app"

    gradle = app_dir / "build.gradle.kts"
    if not gradle.is_file():
        raise SystemExit(f"Missing Android app Gradle file: {gradle}")
    gradle_text = gradle.read_text(encoding="utf-8")
    gradle_text, code_count = re.subn(
        r"(?m)^(\s*)versionCode\s*=\s*502\s*$",
        r"\g<1>versionCode = 600",
        gradle_text,
        count=1,
    )
    gradle_text, name_count = re.subn(
        r'(?m)^(\s*)versionName\s*=\s*"5\.0\.0"\s*$',
        r'\g<1>versionName = "6.0.0"',
        gradle_text,
        count=1,
    )
    if code_count != 1 or name_count != 1:
        raise SystemExit(
            "Could not promote the prepared upstream app from versionCode 502 / 5.0.0 to 600 / 6.0.0"
        )
    gradle.write_text(gradle_text, encoding="utf-8")

    package_dir = app_dir / "src/main/java/com/armsx2/ui/settings"
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "TouchStationControlCenter.kt").write_text(
        CONTROL_CENTER_SOURCE,
        encoding="utf-8",
    )

    performance = package_dir / "PerformanceTab.kt"
    text = performance.read_text(encoding="utf-8")
    marker = "        TouchStationPerformanceMonitor()\n        SettingsDivider()\n\n"
    if "TouchStationControlCenter()" in text:
        raise SystemExit("TouchStation Control Center insertion already exists")
    text = replace_once(
        text,
        marker,
        marker + "        TouchStationControlCenter()\n        SettingsDivider()\n\n",
        "Control Center insertion in PerformanceTab",
    )
    performance.write_text(text, encoding="utf-8")

    print("TouchStation 6.0.0 Control Center added.")
    print("Added Android thermal status, battery/device telemetry, Vulkan feature detection, controller state and diagnostic sharing.")
    print("Existing CPU/GPU/FPS graphs remain authoritative; unsupported metrics are shown as N/A.")


if __name__ == "__main__":
    main()
