#!/usr/bin/env python3
"""Regression tests for TouchStation Extra shutdown hardening and its 100-point audit."""
from __future__ import annotations
import importlib.util
import re
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("touchstation_extra_bugfixes.py")
SPEC = importlib.util.spec_from_file_location("touchstation_extra_bugfixes", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)
ROOT = Path(__file__).resolve().parents[1]
DOC = (ROOT / "docs" / "EXTRA_100_BUGFIXES.md").read_text(encoding="utf-8")
TEMPLATE = (ROOT / "tools" / "templates" / "TouchStationExtraShutdownSuite.kt").read_text(encoding="utf-8")

RUNTIME_FIXTURE = r'''package com.armsx2.runtime
import com.armsx2.ui.WindowImpl
@Volatile private var vmStopInProgress = false
        @Volatile private var vmRestartAfterStop = false
fun loopFinally() {
                    eState.value = EmuState.STOPPED
                    // The game's RPCN session goes with it (see onStart).
                    com.armsx2.online.OnlineSession.release(com.armsx2.Pasx2Application.appContext)
                    val restartNow = synchronized(vmLifecycleLock) {
                        vmRunLoopActive = false
                        vmStopInProgress = false
                        if (vmRestartAfterStop) {
"""
fun stop(saveAutosave: Boolean = false, restartAfterStop: Boolean = false) {
            val nativeActive = runCatching { NativeApp.hasActiveVM() }.getOrDefault(false)
            val shouldStop = synchronized(vmLifecycleLock) {
                if (restartAfterStop)
                    vmRestartAfterStop = true
                else
                    vmRestartAfterStop = false

                if (vmStopInProgress) {
                    nativeActive
                } else if (eState.value == EmuState.STOPPED && !vmRunLoopActive && !nativeActive) {
                    false
                } else {
                    vmStopInProgress = true
                    true
                }
            }
            if (!shouldStop) {
                // Nothing left to stop (the VM self-terminated). Still reconcile the library
                // state — this early return also used to leak a stale per-game rotation.
                onReturnedToLibrary()
                return
            }

            WindowImpl.overlayVisible.value = false
            WindowImpl.showLibrary.value = false
            val doAutosave = saveAutosave
            vmStopControl.execute {
                println("@@ANDROID_STOP_JAVA@@ begin saveAutosave=$doAutosave forced=$saveAutosave restart=$restartAfterStop")
                if (doAutosave)
                    NativeApp.saveAutosaveState()
                NativeApp.shutdown()
                println("@@ANDROID_STOP_JAVA@@ shutdown_return active=${NativeApp.hasActiveVM()} runLoop=$vmRunLoopActive state=${eState.value}")
                if (!vmRunLoopActive && (eState.value == EmuState.STOPPED || !NativeApp.hasActiveVM())) {
                    eState.value = EmuState.STOPPED
                    var restartQueued = false
                    val restartNow = synchronized(vmLifecycleLock) {
                        vmStopInProgress = false
                        restartQueued = vmRestartQueued
                        if (vmRestartAfterStop) {
                            vmRestartAfterStop = false
                            true
                        } else {
                            false
                        }
                    }
                    if (restartNow) {
                        start()
                    } else if (!restartQueued) {
                        onReturnedToLibrary()
                        finishToLauncherIfRequested()
                    }
                }
            }
        }

        fun restart() {
'''

class ShutdownBugfixTests(unittest.TestCase):
    def test_audit_contains_exactly_100_numbered_checks(self):
        entries = re.findall(r"(?m)^\d+\. \*\*(?:IMPLEMENTED|EXISTING / CHECKED|MANUAL / DEVICE TEST|NATIVE CORE REQUIRED)\*\*", DOC)
        self.assertEqual(len(entries), 100)
        self.assertIn("coalesce repeated stop requests", DOC)
        self.assertIn("NATIVE CORE REQUIRED", DOC)

    def test_runtime_patch_coalesces_stop_requests_and_waits_for_both_sides(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "MainActivityRuntime.kt"
            path.write_text(RUNTIME_FIXTURE, encoding="utf-8")
            PATCH.patch_runtime(path)
            result = path.read_text(encoding="utf-8")
            self.assertIn("var queueShutdown = false", result)
            self.assertIn("duplicate-stop-coalesced", result)
            self.assertIn("val nativeStillActive = runCatching { NativeApp.hasActiveVM() }.getOrDefault(true)", result)
            self.assertIn("if (vmShutdownCallReturned && !nativeStillActive) vmStopInProgress = false", result)
            self.assertIn("for (attempt in 0 until 50)", result)
            self.assertNotIn("vmRunLoopActive = false\n                        vmStopInProgress = false", result)
            self.assertIn("autosave-failed-shutdown-continuing", result)
            self.assertIn("runCatching { NativeApp.shutdown() }", result)
            self.assertIn("shutdown-timeout-observed", result)
            self.assertIn("if (!vmRunLoopActive && !stillActive)", result)
            with self.assertRaises(SystemExit):
                PATCH.patch_runtime(path)

    def test_performance_tab_insertion_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "PerformanceTab.kt"
            path.write_text("fun tab() {\n        TouchStationExtra100Suite(settings = s)\n        SettingsDivider()\n}\n", encoding="utf-8")
            PATCH.patch_performance_tab(path)
            result = path.read_text(encoding="utf-8")
            self.assertEqual(result.count("TouchStationExtraShutdownSuite()"), 1)
            with self.assertRaises(SystemExit):
                PATCH.patch_performance_tab(path)

    def test_diagnostic_template_has_persisted_stages_and_manual_outcomes(self):
        for marker in (
            "prefs.edit().putString(KEY_EVENTS, next.toString()).commit()",
            "native-shutdown-started",
            "shutdown-completed",
            "User observed an app crash back to Android home.",
            "User observed the app remain on the stopping screen.",
            "Share shutdown report",
            "MainActivityRuntime.isVmStopInProgress()",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, TEMPLATE)

if __name__ == "__main__":
    unittest.main(verbosity=2)
