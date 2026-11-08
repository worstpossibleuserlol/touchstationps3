#!/usr/bin/env python3
"""Apply TouchStation 7.0.0 native performance overlay and PPU monitor patches."""
from __future__ import annotations

import argparse
import re
from pathlib import Path


PPU_MONITOR_SOURCE = r'''package com.armsx2.ui.settings

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.armsx2.config.Settings
import com.armsx2.runtime.MainActivityRuntime
import com.armsx2.ui.InGameOverlay
import com.armsx3.Rpcs3Settings

private const val TOUCHSTATION_V7_OVERLAY_MIGRATION =
    "touchstation.v7.performanceOverlay.migrated"

@Composable
fun TouchStationPpuMonitor(settings: Settings) {
    // Existing v6 installs are upgraded to the new overlay once. After that, the
    // user's Off/Full choice is retained across boots and game launches.
    val migrated = runCatching {
        MainActivityRuntime.prefs.getBoolean(TOUCHSTATION_V7_OVERLAY_MIGRATION, false)
    }.getOrDefault(false)
    val overlayEnabled = if (migrated) {
        InGameOverlay.osdMode.value != InGameOverlay.OsdMode.Off
    } else {
        true
    }

    val decoder = if (settings.ps3.ppuDecoder == 1) "LLVM Recompiler" else "Interpreter"
    val llvmThreads = if (settings.ps3.llvmThreads <= 0) {
        "Automatic (core default)"
    } else {
        settings.ps3.llvmThreads.toString()
    }

    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(18.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(9.dp),
        ) {
            Text("TouchStation PPU Monitor", style = MaterialTheme.typography.titleLarge)
            Text(
                "PPU configuration and native runtime diagnostics",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Column(
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.spacedBy(2.dp),
                ) {
                    Text("In-game performance overlay", style = MaterialTheme.typography.titleSmall)
                    Text(
                        "Top-left · High detail · FPS and frame graphs",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Switch(
                    checked = overlayEnabled,
                    onCheckedChange = { enabled ->
                        runCatching {
                            MainActivityRuntime.prefs.edit()
                                .putBoolean(TOUCHSTATION_V7_OVERLAY_MIGRATION, true)
                                .apply()
                        }
                        InGameOverlay.setOsdMode(
                            if (enabled) InGameOverlay.OsdMode.Full
                            else InGameOverlay.OsdMode.Off,
                        )
                        if (enabled) Rpcs3Settings.setOverlayPosition(0)
                    },
                )
            }

            PpuStatusRow("PPU decoder", decoder)
            PpuStatusRow("Configured PPU threads", settings.ps3.ppuThreads.toString())
            PpuStatusRow("Max LLVM compile threads", llvmThreads)
            PpuStatusRow(
                "LLVM precompilation",
                if (settings.ps3.llvmPrecompile) "Enabled" else "Disabled",
            )
            PpuStatusRow("PPU module compile notices", "Native compile banner")
            PpuStatusRow("Live PPU / SPU thread counts", "Native in-game overlay")
            PpuStatusRow("PPU / SPU / RSX guest utilization", "Native in-game overlay")
            PpuStatusRow("Separate PPU exception counter", "N/A — not exposed by the Android bridge")
            PpuStatusRow("PPU instruction breakdown", "N/A — not exposed by the Android bridge")

            Text(
                "When enabled, the native RPCS3 high-detail overlay draws at the top-left while a game is running. " +
                    "It supplies real FPS, host CPU utilization, guest PPU/SPU/RSX utilization, PPU/SPU thread counts, " +
                    "RSX load, and framerate/frametime graphs. RSX load is the emulated PS3 GPU workload; it is not " +
                    "the phone's Mali/Adreno utilization. Android host-GPU usage is only available in the separate " +
                    "Performance Monitor when the device driver exposes a readable counter. The Android FPS tile " +
                    "remains N/A because the pinned bridge has no direct FPS getter; the native in-game overlay " +
                    "gets FPS from the emulator's own frame counter.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun PpuStatusRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        verticalAlignment = Alignment.CenterVertically,
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
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}
'''


def replace_once(source: str, old: str, new: str, description: str) -> str:
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"Expected exactly one {description} marker; found {count}")
    return source.replace(old, new, 1)


def patch_version(app_dir: Path) -> None:
    path = app_dir / "build.gradle.kts"
    text = path.read_text(encoding="utf-8")
    text, code_count = re.subn(
        r"(?m)^(\s*)versionCode\s*=\s*600\s*$",
        r"\g<1>versionCode = 700",
        text,
        count=1,
    )
    text, name_count = re.subn(
        r'(?m)^(\s*)versionName\s*=\s*"6\.0\.0"\s*$',
        r'\g<1>versionName = "7.0.0"',
        text,
        count=1,
    )
    if code_count != 1 or name_count != 1:
        raise SystemExit("Expected prepared 6.0.0 / versionCode 600 before promotion to 7.0.0 / 700")
    path.write_text(text, encoding="utf-8")


def patch_ppu_defaults(app_dir: Path) -> None:
    path = app_dir / "src/main/java/com/armsx2/config/Settings.kt"
    text = path.read_text(encoding="utf-8")
    replacements = [
        ("val overlayEnabled: Boolean = false,", "val overlayEnabled: Boolean = true,"),
        ("val overlayDetail: Int = 3,", "val overlayDetail: Int = 4,"),
        ("val overlayFramerateGraph: Boolean = false,", "val overlayFramerateGraph: Boolean = true,"),
        ("val overlayFrametimeGraph: Boolean = false,", "val overlayFrametimeGraph: Boolean = true,"),
    ]
    for old, new in replacements:
        text = replace_once(text, old, new, "default native performance overlay setting")
    path.write_text(text, encoding="utf-8")


def patch_ppu_monitor(app_dir: Path) -> None:
    settings_dir = app_dir / "src/main/java/com/armsx2/ui/settings"
    (settings_dir / "TouchStationPpuMonitor.kt").write_text(
        PPU_MONITOR_SOURCE,
        encoding="utf-8",
    )

    performance = settings_dir / "PerformanceTab.kt"
    text = performance.read_text(encoding="utf-8")
    marker = "        TouchStationControlCenter()\n        SettingsDivider()\n\n"
    replacement = marker + "        TouchStationPpuMonitor(settings = s)\n        SettingsDivider()\n\n"
    text = replace_once(text, marker, replacement, "PPU monitor placement in PerformanceTab")
    performance.write_text(text, encoding="utf-8")


def patch_native_osd_boot(app_dir: Path) -> None:
    path = app_dir / "src/main/java/com/armsx2/ui/InGameOverlay.kt"
    text = path.read_text(encoding="utf-8")
    if "touchstation.v7.performanceOverlay.migrated" in text:
        raise SystemExit("TouchStation 7.0.0 native overlay migration is already present")

    old = """        } else {
            applyOsdMode(osdMode.value)
        }
    }
"""
    new = """        } else {
            applyOsdMode(osdMode.value)
        }

        // One-time v7 upgrade: turn on the native high-detail performance overlay for
        // existing installs, even when an older saved OSD mode was Custom/Off. The
        // choice is then persisted by setOsdMode and the user can turn it off normally.
        val v7MigrationKey = "touchstation.v7.performanceOverlay.migrated"
        if (!MainActivityRuntime.prefs.getBoolean(v7MigrationKey, false)) {
            setOsdMode(OsdMode.Full)
            MainActivityRuntime.prefs.edit().putBoolean(v7MigrationKey, true).apply()
        }

        // TouchStation's requested default placement is the top-left corner.
        if (osdMode.value != OsdMode.Off) {
            com.armsx3.Rpcs3Settings.setOverlayPosition(0)
        }
    }
"""
    text = replace_once(text, old, new, "native OSD boot migration")
    path.write_text(text, encoding="utf-8")


def patch_monitor_copy(app_dir: Path) -> None:
    path = app_dir / "src/main/java/com/armsx2/ui/settings/TouchStationPerformanceMonitor.kt"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "Game FPS is unavailable because the pinned RPCS3 bridge currently returns no FPS reading.",
        "The Android FPS tile has no direct bridge sample; use the native in-game overlay for live FPS and frame graphs.",
        "FPS monitor explanation",
    )
    path.write_text(text, encoding="utf-8")

    control_center = app_dir / "src/main/java/com/armsx2/ui/settings/TouchStationControlCenter.kt"
    text = control_center.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "TouchStation 6.0.0 diagnostic report",
        "TouchStation 7.0.0 diagnostic report",
        "Control Center diagnostic version",
    )
    control_center.write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args()
    app_dir = args.source / "app"

    patch_version(app_dir)
    patch_ppu_defaults(app_dir)
    patch_ppu_monitor(app_dir)
    patch_native_osd_boot(app_dir)
    patch_monitor_copy(app_dir)

    print("TouchStation 7.0.0 PPU monitor and native in-game performance overlay applied.")
    print("Native high-detail OSD: top-left, FPS, host CPU, guest PPU/SPU/RSX, thread counts, RSX load, framerate and frametime graphs.")
    print("Android bridge-only FPS and host GPU fields remain N/A when no real source is exposed.")


if __name__ == "__main__":
    main()
