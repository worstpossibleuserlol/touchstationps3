#!/usr/bin/env python3
"""Fast regression tests for the TouchStation Finale source patcher."""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("touchstation_finale_suite.py")
SPEC = importlib.util.spec_from_file_location("touchstation_finale_suite", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
FINALE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FINALE)
FINALE_SOURCE_TEXT = SCRIPT.read_text(encoding="utf-8")

PREP_SCRIPT = Path(__file__).with_name("prepare_source_build.py")
PREP_SPEC = importlib.util.spec_from_file_location("prepare_source_build", PREP_SCRIPT)
assert PREP_SPEC is not None and PREP_SPEC.loader is not None
PREP = importlib.util.module_from_spec(PREP_SPEC)
PREP_SPEC.loader.exec_module(PREP)


class FinalePatchTests(unittest.TestCase):
    def test_kotlin_compiler_mirror_is_scoped_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            settings = root / "settings.gradle.kts"
            settings.write_text(
                """pluginManagement {
    repositories {
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
        // Discord Social SDK ships as a local .aar.
    }
}
""",
                encoding="utf-8",
            )
            PREP.patch_kotlin_compiler_mirror(root)
            once = settings.read_text(encoding="utf-8")
            PREP.patch_kotlin_compiler_mirror(root)
            twice = settings.read_text(encoding="utf-8")
            self.assertEqual(once, twice)
            self.assertEqual(once.count("kotlinCompilerEmbeddableMirror"), 1)
            self.assertIn(
                'includeModule("org.jetbrains.kotlin", "kotlin-compiler-embeddable")',
                once,
            )
            self.assertLess(
                once.index("kotlinCompilerEmbeddableMirror"),
                once.index("        mavenCentral()\n        // Discord"),
            )

    def test_version_promotion_is_exact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            app = Path(temporary)
            gradle = app / "build.gradle.kts"
            gradle.write_text(
                'defaultConfig {\n    versionCode = 1100\n    versionName = "11.0.0"\n}\n',
                encoding="utf-8",
            )
            FINALE.patch_version(app)
            result = gradle.read_text(encoding="utf-8")
            self.assertIn("versionCode = 1200", result)
            self.assertIn('versionName = "TouchStation Finale"', result)
            self.assertNotIn("versionCode = 1100", result)

    def test_version_promotion_rejects_unexpected_input(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            app = Path(temporary)
            gradle = app / "build.gradle.kts"
            gradle.write_text(
                'defaultConfig {\n    versionCode = 1199\n    versionName = "RC"\n}\n',
                encoding="utf-8",
            )
            with self.assertRaises(SystemExit):
                FINALE.patch_version(app)

    def test_performance_tab_insertion_is_single_and_idempotency_guarded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            app = Path(temporary)
            source = app / "src/main/java/com/armsx2/ui/settings/PerformanceTab.kt"
            source.parent.mkdir(parents=True)
            source.write_text(
                """package com.armsx2.ui.settings
fun PerformanceTab() {
    Column {
        TouchStation11ReliabilitySuite(
            settings = s,
            onApply = { updated ->
                runCatching {
                    apply(updated)
                    InGameOverlay.reloadSettings()
                    true
                }.getOrDefault(false)
            },
        )
        SettingsDivider()

    }
}
""",
                encoding="utf-8",
            )
            FINALE.patch_performance_tab(app)
            result = source.read_text(encoding="utf-8")
            self.assertEqual(result.count("TouchStationFinaleSuite("), 1)
            self.assertIn("saved.ps3.spuXFloat == updated.ps3.spuXFloat", result)
            with self.assertRaises(SystemExit):
                FINALE.patch_performance_tab(app)

    def test_library_badge_uses_exact_cached_desktop_status(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            app = Path(temporary)
            home = app / "src/main/java/com/armsx2/ui/home/HomeScreen.kt"
            vm = app / "src/main/java/com/armsx2/ui/home/HomeViewModel.kt"
            home.parent.mkdir(parents=True)
            home.write_text(
                """package com.armsx2.ui.home
import com.armsx2.GameInfo
fun HomeScreen() {
    val context = LocalContext.current
}
@Composable
private fun GameMetadata(game: GameInfo) {
    Row {
        game.regionFlag?.let { Text(it, fontSize = 13.sp) }
        if (game.compatibility > 0) {
            Text("★")
        }
    }
}
""",
                encoding="utf-8",
            )
            vm.write_text(
                """package com.armsx2.ui.home
import com.armsx2.GameInfo
class HomeViewModel {
    private fun buildState(base: HomeUiState): HomeUiState {
        val sorted = when (base.sort) {
            HomeSort.Compatibility -> filtered.sortedWith(
                compareByDescending<GameInfo> { it.compatibility }
                    .thenBy { it.sortKey(forceEn).lowercase() },
            )
        }
        return base.copy(visibleGames = sorted)
    }
}
""",
                encoding="utf-8",
            )
            FINALE.patch_library_compatibility(app)
            result = home.read_text(encoding="utf-8")
            self.assertIn("TouchStationFinaleCompatibilityStore.loadCache(context)", result)
            self.assertIn('StatusChip("PC: $status")', result)
            self.assertIn("import com.armsx2.ui.settings.TouchStationFinaleCompatibilityStore", result)
            self.assertIn("LaunchedEffect(compatibilityRevision, state.sort)", result)
            vm_result = vm.read_text(encoding="utf-8")
            self.assertIn("TouchStationFinaleCompatibilityStore.rankFor(it.serial) ?: -1", vm_result)
            with self.assertRaises(SystemExit):
                FINALE.patch_library_compatibility(app)

    def test_finale_source_has_exact_id_compatibility_and_safe_profile(self) -> None:
        source = FINALE.KOTLIN_SOURCE
        for marker in (
            "https://rpcs3.net/compatibility/?api=v1&export",
            "touchStationFinaleNormaliseId",
            "Full library compatibility index",
            "PS3 runtime",
            "Device readiness",
            "Finale dashboard",
            "Reload cached library index",
            "Apply GTA IV per-game profile",
            "settingsArePerGame",
            "spuXFloat = 0",
            "spuBlockSize = 0",
            "shaderMode = 1",
            "msaaMode = 0",
            "Export Finale diagnostic report",
            "Download TouchStation.log",
            "Share TouchStation.log",
            "TouchStationFinaleErrorHistory",
            "Recorded FIFO errors",
            "MediaStore.Downloads.EXTERNAL_CONTENT_URI",
            "logcat",
            "GPU fences",
            "Core@@RSX FIFO Fetch Accuracy",
            "Video@@Driver Wake-Up Delay",
            "Ordered & Atomic",
            "touchStationFinaleApplyFifoRecoveryProfile",
            "CoreSettingOverrides.record",
            "CoreSettingOverrides.load",
            "return persisted to detail",
            "TouchStationFinaleReliability.startupSelfTest(context, settings)",
            "TouchStationFinaleSettingsRollback.save",
            "TouchStationFinaleReliability.sha256GameUri",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)

    def test_compatibility_cache_reader_is_defined_and_bounded(self) -> None:
        source = FINALE.KOTLIN_SOURCE
        self.assertIn(
            "private fun touchStationFinaleReadCache(context: Context): JSONObject?",
            source,
        )
        self.assertIn("cacheFile.length() !in 1L..(32L * 1024L * 1024L)", source)
        self.assertIn('payload.optInt("return_code", -1) != 0', source)
        self.assertIn('payload.optJSONObject("results") == null', source)
        self.assertIn("cacheFile.readText(Charsets.UTF_8)", source)

    def test_error_banner_records_events_and_supports_upward_swipe(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            app = Path(temporary)
            banner = app / "src/main/java/com/armsx2/ui/emulation/GameErrorBanner.kt"
            banner.parent.mkdir(parents=True)
            banner.write_text(
                """package com.armsx2.ui.emulation
import androidx.compose.foundation.clickable
import androidx.compose.runtime.mutableStateOf
import com.armsx2.i18n.str
object GameErrorNotice {
    val reason = mutableStateOf<String?>(null)
    fun show(error: String) {
        val line = error.lineSequence().firstOrNull { it.isNotBlank() }?.trim() ?: return
        reason.value = line
    }
    fun clear() {
        reason.value = null
    }
}
@Composable
fun GameErrorBanner() {
    val reason by GameErrorNotice.reason
    AnimatedVisibility(visible = reason != null) {
        val shown = remember(reason) { reason }.orEmpty()
        Surface(
            modifier = Modifier
                .windowInsetsPadding(WindowInsets.safeDrawing.only(WindowInsetsSides.Top))
                .clickable { GameErrorNotice.clear() },
        ) {
            Column {
                Text(shown, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}
""",
                encoding="utf-8",
            )
            FINALE.patch_game_error_banner(app)
            result = banner.read_text(encoding="utf-8")
            self.assertIn("import androidx.compose.foundation.clickable", result)
            self.assertIn("import androidx.compose.foundation.gestures.detectVerticalDragGestures", result)
            self.assertIn("TouchStationFinaleErrorHistory.record(fullMessage)", result)
            self.assertIn("reason.value = fullMessage", result)
            self.assertIn("detectVerticalDragGestures", result)
            self.assertIn("verticalDrag.value <= -72f", result)
            self.assertIn("Critical error recorded", result)
            with self.assertRaises(SystemExit):
                FINALE.patch_game_error_banner(app)
        self.assertIn("fullMessage = error.trim().take(4_000)", FINALE_SOURCE_TEXT)

    def test_reliability_module_exposes_bounded_android_services(self) -> None:
        source = FINALE.RELIABILITY_KOTLIN_SOURCE
        for marker in (
            "registerActivityLifecycleCallbacks",
            "setDefaultUncaughtExceptionHandler",
            "SAFE_MODE_KEY",
            "uncaught exception was recorded; safe mode was enabled",
            "MAX_LOG_BYTES",
            "pruneCrashes",
            "inspectGameUri",
            "sha256GameUri",
            "startupSelfTest",
            "validateSettings",
            "memoryTrend",
            "No files changed.",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)

    def test_runtime_guard_is_a_separate_thread_safe_android_module(self) -> None:
        source = FINALE.RUNTIME_GUARD_KOTLIN_SOURCE
        for marker in (
            "ConcurrentHashMap",
            "putIfAbsent",
            "TouchStation-Finale-Watchdog",
            "operation-watchdog",
            "no native or worker thread was forcibly interrupted",
            "libarmsx3-core.so",
            "libarmsx3-jni.so",
            "fun nativeCoreHealth",
            "fun memoryPressure",
            "Android process thread count",
            "not a PPU/SPU worker count",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)

    def test_finale_long_running_actions_use_operation_watchdog(self) -> None:
        source = FINALE.KOTLIN_SOURCE
        for marker in (
            "TouchStationFinaleRuntimeGuard.begin",
            "TouchStationFinaleRuntimeGuard.finish",
            "compatibility-refresh",
            "game-integrity",
            "diagnostic-log-export",
            "Native core health",
            "Tracked Android operations",
            "Memory pressure",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)

    def test_application_reliability_patcher_is_idempotency_guarded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            app = Path(temporary)
            source = app / "src/main/java/com/armsx2/Pasx2Application.kt"
            source.parent.mkdir(parents=True)
            source.write_text(
                "package com.armsx2\nimport android.os.Build\nclass Pasx2Application {\n fun onCreate() {\n installCrashLogging()\n }\n}",
                encoding="utf-8",
            )
            FINALE.patch_application_reliability(app)
            result = source.read_text(encoding="utf-8")
            self.assertIn("import com.armsx2.reliability.TouchStationFinaleReliability", result)
            self.assertIn("TouchStationFinaleReliability.install(this)", result)
            with self.assertRaises(SystemExit):
                FINALE.patch_application_reliability(app)

    def test_native_fifo_limits_are_explicit_not_faked(self) -> None:
        source = FINALE.KOTLIN_SOURCE
        self.assertIn("does not expose live FIFO queue depth", source)
        self.assertIn("cannot safely reset or repair a stalled native queue", source)
        self.assertIn("TouchStation.log", source)
        self.assertIn("MediaStore.Downloads.EXTERNAL_CONTENT_URI", source)
        self.assertIn('JSONObject.quote("Ordered & Atomic")', source)
        self.assertIn('val delayValue = "20"', source)
        self.assertIn("SettingsScope.Game", source)

    def test_native_metrics_are_not_fabricated(self) -> None:
        source = FINALE.KOTLIN_SOURCE
        self.assertIn("GPU utilization and exact Vulkan extensions remain N/A", source)
        self.assertIn("FPS and frametime are supplied only by the native in-game overlay", source)
        self.assertIn("Official status is a desktop RPCS3 reference", source)
        self.assertIn("internal fun entryFor(serial: String?)", source)
        self.assertIn("entriesById.value = next", source)
        self.assertNotIn("touchStationFinaleOfficialEntry", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
