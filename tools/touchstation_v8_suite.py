#!/usr/bin/env python3
"""Apply TouchStation 8.0.0 monitoring, overlay control and subsystem dashboard patches."""
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
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Slider
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.armsx2.config.Settings
import com.armsx2.config.SettingsScope
import com.armsx2.ui.InGameOverlay
import com.armsx3.Rpcs3Settings
import kotlin.math.roundToInt

@Composable
fun TouchStationPpuMonitor(settings: Settings) {
    val overlayEnabled = InGameOverlay.osdMode.value != InGameOverlay.OsdMode.Off
    val scopeLabel = if (InGameOverlay.settingsScope.value == SettingsScope.Game) {
        "Per-game settings"
    } else {
        "Global settings"
    }
    val decoder = if (settings.ps3.ppuDecoder == 1) "LLVM Recompiler" else "Interpreter"
    val llvmThreads = if (settings.ps3.llvmThreads <= 0) "Automatic" else settings.ps3.llvmThreads.toString()
    val opacity = remember(settings.ps3.overlayOpacity) {
        mutableStateOf(settings.ps3.overlayOpacity.toFloat())
    }
    val fontSize = remember(settings.ps3.overlayFontSize) {
        mutableStateOf(settings.ps3.overlayFontSize.toFloat())
    }

    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = androidx.compose.foundation.shape.RoundedCornerShape(18.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(9.dp),
        ) {
            Text("TouchStation PPU Monitor 2.0", style = MaterialTheme.typography.titleLarge)
            Text(
                "PPU configuration, recompiler status and in-game performance overlay controls · " + scopeLabel,
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
                    Text("Show in-game performance overlay", style = MaterialTheme.typography.titleSmall)
                    Text(
                        if (overlayEnabled) "Visible while a game is running" else "Hidden while a game is running",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Switch(
                    checked = overlayEnabled,
                    onCheckedChange = { enabled ->
                        InGameOverlay.setOsdMode(
                            if (enabled) InGameOverlay.OsdMode.Full else InGameOverlay.OsdMode.Off,
                        )
                    },
                )
            }

            Text("Overlay position", style = MaterialTheme.typography.titleSmall)
            Row(horizontalArrangement = Arrangement.spacedBy(5.dp)) {
                listOf("Top-left", "Top-right", "Bottom-left", "Bottom-right").forEachIndexed { index, label ->
                    FilterChip(
                        selected = settings.ps3.overlayPosition == index,
                        onClick = {
                            InGameOverlay.saveSettings(
                                settings.copy(ps3 = settings.ps3.copy(overlayPosition = index)),
                            )
                            runCatching { Rpcs3Settings.setOverlayPosition(index) }
                        },
                        label = { Text(label) },
                    )
                }
            }

            Text("Overlay opacity: " + settings.ps3.overlayOpacity + "%", style = MaterialTheme.typography.bodyMedium)
            Slider(
                value = opacity.value.coerceIn(0f, 100f),
                onValueChange = { opacity.value = it },
                onValueChangeFinished = {
                    InGameOverlay.saveSettings(
                        settings.copy(ps3 = settings.ps3.copy(overlayOpacity = opacity.value.roundToInt())),
                    )
                },
                valueRange = 0f..100f,
                steps = 99,
            )

            Text("Overlay text size: " + settings.ps3.overlayFontSize + " px", style = MaterialTheme.typography.bodyMedium)
            Slider(
                value = fontSize.value.coerceIn(4f, 36f),
                onValueChange = { fontSize.value = it },
                onValueChangeFinished = {
                    InGameOverlay.saveSettings(
                        settings.copy(ps3 = settings.ps3.copy(overlayFontSize = fontSize.value.roundToInt())),
                    )
                },
                valueRange = 4f..36f,
                steps = 31,
            )

            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Column(Modifier.weight(1f)) {
                    Text("Framerate graph", style = MaterialTheme.typography.titleSmall)
                    Text("Use the native graph when supported by the overlay renderer.", style = MaterialTheme.typography.bodySmall)
                }
                Switch(
                    checked = settings.ps3.overlayFramerateGraph,
                    onCheckedChange = {
                        InGameOverlay.saveSettings(settings.copy(ps3 = settings.ps3.copy(overlayFramerateGraph = it)))
                    },
                )
            }
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Column(Modifier.weight(1f)) {
                    Text("Frametime graph", style = MaterialTheme.typography.titleSmall)
                    Text("Shows frame pacing when exposed by the native overlay.", style = MaterialTheme.typography.bodySmall)
                }
                Switch(
                    checked = settings.ps3.overlayFrametimeGraph,
                    onCheckedChange = {
                        InGameOverlay.saveSettings(settings.copy(ps3 = settings.ps3.copy(overlayFrametimeGraph = it)))
                    },
                )
            }

            PpuStatusRow("PPU decoder", decoder)
            PpuStatusRow("Configured PPU threads", settings.ps3.ppuThreads.toString())
            PpuStatusRow("Maximum LLVM compile threads", llvmThreads)
            PpuStatusRow("LLVM precompilation", if (settings.ps3.llvmPrecompile) "Enabled" else "Disabled")
            PpuStatusRow("PPU live workload", "Native in-game overlay")
            PpuStatusRow("PPU instruction / exception counters", "N/A — not exposed by the Android bridge")

            Text(
                "The in-game pause menu also has a one-press Performance Overlay action. Overlay mode is saved per game when a game-specific settings scope is active; otherwise the global choice is used. Unsupported native counters remain N/A.",
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
        Text(value, modifier = Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium)
    }
}
'''


SUITE_SOURCE = r'''package com.armsx2.ui.settings

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.armsx2.config.Settings
import com.armsx2.config.SettingsScope
import com.armsx2.input.PadRouter
import com.armsx2.runtime.MainActivityRuntime
import com.armsx2.ui.InGameOverlay
import kotlinx.coroutines.delay

@Composable
fun TouchStation8MonitoringSuite(settings: Settings) {
    val context = LocalContext.current
    val padCount = remember { mutableStateOf(PadRouter.connectedPads().size) }
    LaunchedEffect(Unit) {
        while (true) {
            padCount.value = runCatching { PadRouter.connectedPads().size }.getOrDefault(0)
            delay(2_000)
        }
    }

    val game = MainActivityRuntime.currentGame.value
    val gameTitle = game?.title?.takeIf { it.isNotBlank() } ?: "No game running"
    val gameSerial = game?.serial?.takeIf { it.isNotBlank() } ?: "N/A"
    val perGame = InGameOverlay.settingsScope.value == SettingsScope.Game
    val spuBlock = when (settings.ps3.spuBlockSize) {
        1 -> "Mega"
        2 -> "Giga"
        else -> "Safe"
    }
    val gpuProfile = when (settings.gpuProfile) {
        1 -> "Mali"
        2 -> "Adreno"
        3 -> "PowerVR"
        4 -> "Xclipse"
        else -> "Auto"
    }

    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(18.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text("TouchStation 8.0 Monitoring Suite", style = MaterialTheme.typography.titleLarge)
            Text(
                "PPU, SPU and RSX configuration diagnostics, game context and support shortcuts.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            SuiteSection("SPU Monitor") {
                SuiteRow("SPU decoder index", settings.ps3.spuDecoder.toString())
                SuiteRow("SPU block size", spuBlock)
                SuiteRow("Preferred SPU threads", if (settings.ps3.preferredSpuThreads <= 0) "Automatic" else settings.ps3.preferredSpuThreads.toString())
                SuiteRow("Maximum SPURS threads", settings.ps3.maxSpursThreads.toString())
                SuiteRow("SPU cache", if (settings.ps3.spuCache) "Enabled" else "Disabled")
                SuiteRow("SPU loop detection", if (settings.ps3.spuLoopDetection) "Enabled" else "Disabled")
                SuiteRow("Accurate SPU DMA", if (settings.ps3.accurateSpuDma) "Enabled" else "Disabled")
                SuiteRow("Live SPU workload", "Native in-game overlay")
                SuiteRow("Standalone SPU instruction counters", "N/A — not exposed by the Android bridge")
            }

            SuiteSection("RSX Graphics Monitor") {
                SuiteRow("GPU profile", gpuProfile)
                SuiteRow("Emulated RSX workload", "Native in-game overlay")
                SuiteRow("Physical Android GPU utilization", "Driver counter required; otherwise N/A")
                SuiteRow("Graphics / shader diagnostics", "Existing Renderer and shader compiler settings")
                SuiteRow("Native RSX instruction counters", "N/A — not exposed by the Android bridge")
            }

            SuiteSection("Controller Center") {
                SuiteRow("Connected physical controllers", padCount.value.toString())
                SuiteRow("Button mapping and player assignment", "Available in Controller Manager")
                SuiteRow("Saved controller profiles and hotkeys", "Available in Controller Manager")
                SuiteRow("Gameplay input", "Physical controllers only")
            }

            SuiteSection("Game Compatibility and Profiles") {
                SuiteRow("Current game", gameTitle)
                SuiteRow("Game serial", gameSerial)
                SuiteRow("Settings scope", if (perGame) "Per-game overrides" else "Global")
                SuiteRow("Compatibility metadata", "Upstream library metadata retained")
                SuiteRow("Device-specific compatibility rating", "Not inferred; requires an actual test")
                SuiteRow("Per-game configuration", "Supported by the existing settings system")
            }

            SuiteSection("Stability, Crash Diagnostics and Audio / Display") {
                SuiteRow("Thermal, RAM and storage health", "TouchStation Control Center above")
                SuiteRow("Diagnostic report export", "TouchStation Control Center above")
                SuiteRow("Structured crash / bug report", "Button below")
                SuiteRow("Audio configuration", "Existing Audio settings")
                SuiteRow("Renderer and display configuration", "Existing Renderer and Overlay settings")
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
                Text("Report a Compatibility or Emulator Issue")
            }

            Text(
                "The upstream Android app already provides controller remapping and profiles, per-game settings, game compatibility metadata, audio, renderer, shader and firmware management. This suite brings their status together without duplicating those systems. Live PPU/SPU/RSX utilization is shown by the native in-game overlay; unavailable counters are never fabricated.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun SuiteSection(title: String, content: @Composable () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
        Text(title, style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.primary)
        content()
    }
}

@Composable
private fun SuiteRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Text(
            label,
            modifier = Modifier.weight(1f),
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(value, modifier = Modifier.weight(1f), style = MaterialTheme.typography.bodySmall)
    }
}
'''


def replace_once(source: str, old: str, new: str, description: str) -> str:
    count = source.count(old)
    if count != 1:
        raise SystemExit("Expected exactly one " + description + " marker; found " + str(count))
    return source.replace(old, new, 1)


def patch_version(app_dir: Path) -> None:
    path = app_dir / "build.gradle.kts"
    text = path.read_text(encoding="utf-8")
    text, code_count = re.subn(
        r"(?m)^(\s*)versionCode\s*=\s*700\s*$",
        r"\g<1>versionCode = 800",
        text,
        count=1,
    )
    text, name_count = re.subn(
        r'(?m)^(\s*)versionName\s*=\s*"7\.0\.0"\s*$',
        r'\g<1>versionName = "8.0.0"',
        text,
        count=1,
    )
    if code_count != 1 or name_count != 1:
        raise SystemExit("Expected prepared 7.0.0 / versionCode 700 before promotion to 8.0.0 / 800")
    path.write_text(text, encoding="utf-8")


def patch_overlay_persistence(app_dir: Path) -> None:
    path = app_dir / "src/main/java/com/armsx2/ui/InGameOverlay.kt"
    text = path.read_text(encoding="utf-8")
    old = '''    private var osdLoaded = false

    private fun ensureOsdLoaded() {
        if (osdLoaded) return
        osdLoaded = true
        val name = runCatching { MainActivityRuntime.prefs.getString(OsdModeKey, null) }.getOrNull()
        osdMode.value = OsdMode.entries.firstOrNull { it.name == name } ?: OsdMode.Custom
    }
'''
    new = '''    private var osdLoaded = false
    private var loadedOsdPreferenceKey: String? = null

    private fun osdPreferenceKey(): String {
        val serial = MainActivityRuntime.currentGame.value?.settingsKey
            ?.takeIf { it.isNotBlank() }
        return if (serial == null) OsdModeKey else "ui.osdMode.game." + serial
    }

    private fun ensureOsdLoaded() {
        val key = osdPreferenceKey()
        if (osdLoaded && loadedOsdPreferenceKey == key) return
        osdLoaded = true
        loadedOsdPreferenceKey = key
        val name = runCatching {
            MainActivityRuntime.prefs.getString(key, null)
                ?: MainActivityRuntime.prefs.getString(OsdModeKey, null)
        }.getOrNull()
        osdMode.value = OsdMode.entries.firstOrNull { it.name == name } ?: OsdMode.Custom
    }
'''
    text = replace_once(text, old, new, "per-game overlay preference loader")

    old = '''    fun setOsdMode(mode: OsdMode) {
        ensureOsdLoaded()
        applyOsdMode(mode)
        runCatching { MainActivityRuntime.prefs.edit().putString(OsdModeKey, mode.name).apply() }
    }
'''
    new = '''    fun setOsdMode(mode: OsdMode) {
        ensureOsdLoaded()
        applyOsdMode(mode)
        runCatching {
            MainActivityRuntime.prefs.edit().putString(osdPreferenceKey(), mode.name).apply()
        }
    }
'''
    text = replace_once(text, old, new, "per-game overlay preference writer")

    forced_top_left = '''        // TouchStation's requested default placement is the top-left corner.
        if (osdMode.value != OsdMode.Off) {
            com.armsx3.Rpcs3Settings.setOverlayPosition(0)
        }
'''
    if forced_top_left in text:
        text = text.replace(forced_top_left, "", 1)
    path.write_text(text, encoding="utf-8")


def patch_ppu_monitor(app_dir: Path) -> None:
    path = app_dir / "src/main/java/com/armsx2/ui/settings/TouchStationPpuMonitor.kt"
    if not path.is_file():
        raise SystemExit("Missing TouchStation 7.0.0 PPU Monitor generated by the 7.0.0 patch")
    path.write_text(PPU_MONITOR_SOURCE, encoding="utf-8")


def patch_monitoring_suite(app_dir: Path) -> None:
    settings_dir = app_dir / "src/main/java/com/armsx2/ui/settings"
    suite = settings_dir / "TouchStation8MonitoringSuite.kt"
    suite.write_text(SUITE_SOURCE, encoding="utf-8")

    performance = settings_dir / "PerformanceTab.kt"
    text = performance.read_text(encoding="utf-8")
    marker = '''        TouchStationPpuMonitor(settings = s)
        SettingsDivider()

'''
    replacement = marker + '''        TouchStation8MonitoringSuite(settings = s)
        SettingsDivider()

'''
    text = replace_once(text, marker, replacement, "TouchStation 8.0 Monitoring Suite placement")
    performance.write_text(text, encoding="utf-8")


def patch_pause_menu_quick_toggle(app_dir: Path) -> None:
    path = app_dir / "src/main/java/com/armsx2/ui/emulation/EmulationMenuScreen.kt"
    text = path.read_text(encoding="utf-8")
    if "Performance Overlay" in text:
        raise SystemExit("Performance Overlay quick toggle already exists in pause menu")
    anchor = '''        add(MenuAction(str("memcard.restart"), str("action.reset"), "↻", null, MainActivityRuntime::restart))
'''
    insert = anchor + '''        add(MenuAction(
            "Performance Overlay",
            if (com.armsx2.ui.InGameOverlay.osdMode.value == com.armsx2.ui.InGameOverlay.OsdMode.Off)
                "Hidden · select to show FPS and graphs"
            else
                "Visible · select to hide FPS and graphs",
            "◉",
            null,
        ) {
            val next = if (
                com.armsx2.ui.InGameOverlay.osdMode.value == com.armsx2.ui.InGameOverlay.OsdMode.Off
            ) com.armsx2.ui.InGameOverlay.OsdMode.Full
            else com.armsx2.ui.InGameOverlay.OsdMode.Off
            com.armsx2.ui.InGameOverlay.setOsdMode(next)
        })
'''
    text = replace_once(text, anchor, insert, "pause-menu quick overlay toggle")
    path.write_text(text, encoding="utf-8")


def patch_diagnostic_version(app_dir: Path) -> None:
    path = app_dir / "src/main/java/com/armsx2/ui/settings/TouchStationControlCenter.kt"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "TouchStation 7.0.0 diagnostic report",
        "TouchStation 8.0.0 diagnostic report",
        "diagnostic report version label",
    )
    path.write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args()
    app_dir = args.source / "app"

    for required in (
        app_dir / "build.gradle.kts",
        app_dir / "src/main/java/com/armsx2/ui/InGameOverlay.kt",
        app_dir / "src/main/java/com/armsx2/ui/emulation/EmulationMenuScreen.kt",
        app_dir / "src/main/java/com/armsx2/ui/settings/PerformanceTab.kt",
        app_dir / "src/main/java/com/armsx2/ui/settings/TouchStationPpuMonitor.kt",
        app_dir / "src/main/java/com/armsx2/ui/settings/TouchStationControlCenter.kt",
    ):
        if not required.is_file():
            raise SystemExit("Missing expected source file: " + str(required))

    patch_version(app_dir)
    patch_overlay_persistence(app_dir)
    patch_ppu_monitor(app_dir)
    patch_monitoring_suite(app_dir)
    patch_pause_menu_quick_toggle(app_dir)
    patch_diagnostic_version(app_dir)

    print("TouchStation 8.0.0 monitoring suite applied.")
    print("Added SPU and RSX subsystem diagnostics, per-game overlay persistence and one-press pause-menu overlay control.")
    print("Integrated existing controller, compatibility, game-profile, stability, diagnostics, audio and display systems.")
    print("Unsupported native/driver telemetry remains N/A rather than fabricated.")


if __name__ == "__main__":
    main()
