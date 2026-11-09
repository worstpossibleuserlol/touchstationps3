#!/usr/bin/env python3
"""Apply TouchStation Extra's shutdown coalescing and crash-diagnostic safeguards."""
from __future__ import annotations
import argparse
from pathlib import Path

TEMPLATE = Path(__file__).parent / "templates" / "TouchStationExtraShutdownSuite.kt"

def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"Expected exactly one {label} marker; found {count}")
    return source.replace(old, new, 1)

def patch_runtime(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    if "TouchStationExtraShutdownDiagnostics.record(" in source:
        raise SystemExit("TouchStation Extra shutdown safeguards are already installed")
    source = replace_once(source, "import com.armsx2.ui.WindowImpl\n",
        "import com.armsx2.ui.WindowImpl\nimport com.armsx2.reliability.TouchStationExtraShutdownDiagnostics\n",
        "shutdown diagnostics import")
    source = replace_once(source,
        "@Volatile private var vmStopInProgress = false\n        @Volatile private var vmRestartAfterStop = false",
        "@Volatile private var vmStopInProgress = false\n"
        "        // Native shutdown and the VM run loop must both finish before this latch clears.\n"
        "        @Volatile private var vmShutdownCallReturned = false\n"
        "        @Volatile private var vmRestartAfterStop = false",
        "shutdown state fields")
    source = replace_once(source,
        """                    eState.value = EmuState.STOPPED
                    // The game's RPCN session goes with it (see onStart).
                    com.armsx2.online.OnlineSession.release(com.armsx2.Pasx2Application.appContext)
                    val restartNow = synchronized(vmLifecycleLock) {
                        vmRunLoopActive = false
                        vmStopInProgress = false
                        if (vmRestartAfterStop) {""",
        """                    eState.value = EmuState.STOPPED
                    TouchStationExtraShutdownDiagnostics.record(
                        com.armsx2.Pasx2Application.appContext,
                        "vm-run-loop-exited",
                        "The guest run loop returned; native shutdown completion is tracked separately.",
                    )
                    // Session-release failures must not skip lifecycle state reconciliation.
                    runCatching {
                        com.armsx2.online.OnlineSession.release(com.armsx2.Pasx2Application.appContext)
                    }.onFailure {
                        TouchStationExtraShutdownDiagnostics.record(
                            com.armsx2.Pasx2Application.appContext,
                            "online-session-cleanup-failed",
                            it.javaClass.simpleName + ": " + (it.message ?: "no message"),
                        )
                    }
                    val nativeStillActive = runCatching { NativeApp.hasActiveVM() }.getOrDefault(true)
                    val restartNow = synchronized(vmLifecycleLock) {
                        vmRunLoopActive = false
                        // Keep the latch set until native shutdown has returned AND reported idle.
                        if (vmShutdownCallReturned && !nativeStillActive) vmStopInProgress = false
                        if (vmRestartAfterStop) {""",
        "run-loop completion ordering")
    source = replace_once(source,
        """            val nativeActive = runCatching { NativeApp.hasActiveVM() }.getOrDefault(false)
            val shouldStop = synchronized(vmLifecycleLock) {""",
        """            val nativeActive = runCatching { NativeApp.hasActiveVM() }.getOrDefault(false)
            var queueShutdown = false
            TouchStationExtraShutdownDiagnostics.record(
                com.armsx2.Pasx2Application.appContext,
                "stop-requested",
                "state=" + eState.value + "; nativeActive=" + nativeActive +
                    "; restart=" + restartAfterStop + "; saveAutosave=" + saveAutosave,
            )
            val shouldStop = synchronized(vmLifecycleLock) {""",
        "stop request tracking")
    source = replace_once(source,
        """                if (vmStopInProgress) {
                    nativeActive
                } else if (eState.value == EmuState.STOPPED && !vmRunLoopActive && !nativeActive) {
                    false
                } else {
                    vmStopInProgress = true
                    true
                }""",
        """                if (vmStopInProgress) {
                    // A stop already owns the VMStop queue. Coalesce this request; never enqueue
                    // a second NativeApp.shutdown() while the first one is still unwinding.
                    true
                } else if (eState.value == EmuState.STOPPED && !vmRunLoopActive && !nativeActive) {
                    false
                } else {
                    vmStopInProgress = true
                    vmShutdownCallReturned = false
                    queueShutdown = true
                    true
                }""",
        "single-flight stop guard")
    source = replace_once(source,
        """            if (!shouldStop) {
                // Nothing left to stop (the VM self-terminated). Still reconcile the library
                // state — this early return also used to leak a stale per-game rotation.
                onReturnedToLibrary()
                return
            }

            WindowImpl.overlayVisible.value = false""",
        """            if (!shouldStop) {
                // Nothing left to stop (the VM self-terminated). Still reconcile the library
                // state — this early return also used to leak a stale per-game rotation.
                onReturnedToLibrary()
                return
            }
            if (!queueShutdown) {
                TouchStationExtraShutdownDiagnostics.record(
                    com.armsx2.Pasx2Application.appContext,
                    "duplicate-stop-coalesced",
                    "An existing native shutdown owns VMStop; no second shutdown was enqueued.",
                )
                return
            }

            WindowImpl.overlayVisible.value = false""",
        "duplicate stop queue suppression")
    source = replace_once(source,
        """            val doAutosave = saveAutosave
            vmStopControl.execute {
                println("@@ANDROID_STOP_JAVA@@ begin saveAutosave=$doAutosave forced=$saveAutosave restart=$restartAfterStop")
                if (doAutosave)
                    NativeApp.saveAutosaveState()
                NativeApp.shutdown()
""",
        """            val doAutosave = saveAutosave
            TouchStationExtraShutdownDiagnostics.record(
                com.armsx2.Pasx2Application.appContext,
                "native-shutdown-queued",
                "The serialized VMStop executor accepted the shutdown task.",
            )
            android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({
                if (vmStopInProgress) {
                    TouchStationExtraShutdownDiagnostics.record(
                        com.armsx2.Pasx2Application.appContext,
                        "shutdown-timeout-observed",
                        "Shutdown is pending after 20 seconds. No native thread was forcibly interrupted.",
                    )
                }
            }, 20_000L)
            vmStopControl.execute {
                val shutdownStartedAt = SystemClock.elapsedRealtime()
                TouchStationExtraShutdownDiagnostics.record(
                    com.armsx2.Pasx2Application.appContext,
                    "native-shutdown-started",
                    "saveAutosave=" + doAutosave + "; restart=" + restartAfterStop,
                )
                if (doAutosave) {
                    val autosaveResult = runCatching { NativeApp.saveAutosaveState() }
                    autosaveResult.exceptionOrNull()?.let { error ->
                        TouchStationExtraShutdownDiagnostics.record(
                            com.armsx2.Pasx2Application.appContext,
                            "autosave-failed-shutdown-continuing",
                            error.javaClass.simpleName + ": " + (error.message ?: "no message"),
                        )
                    }
                }
                // A failed optional autosave must never bypass the native shutdown attempt.
                val shutdownResult = runCatching { NativeApp.shutdown() }
                shutdownResult.exceptionOrNull()?.let { error ->
                    TouchStationExtraShutdownDiagnostics.record(
                        com.armsx2.Pasx2Application.appContext,
                        "native-shutdown-exception",
                        error.javaClass.simpleName + ": " + (error.message ?: "no message"),
                    )
                }
                // The flag records return from shutdown(), not proof that the VM is idle.
                synchronized(vmLifecycleLock) { vmShutdownCallReturned = true }
                var stillActive = runCatching { NativeApp.hasActiveVM() }.getOrDefault(true)
                // Allow a bounded hand-off for the run loop and native active flag to settle.
                // Never interrupt a native worker or assume that a timeout means it is safe.
                for (attempt in 0 until 50) {
                    if (!stillActive && !vmRunLoopActive) break
                    try {
                        Thread.sleep(100L)
                    } catch (_: InterruptedException) {
                        Thread.currentThread().interrupt()
                        break
                    }
                    stillActive = runCatching { NativeApp.hasActiveVM() }.getOrDefault(true)
                }
""",
        "safe native shutdown worker")
    # Existing debug println includes an extra unguarded hasActiveVM() query. Replace it safely.
    log_old = '                println("@@ANDROID_STOP_JAVA@@ shutdown_return active=' + '$' + '{NativeApp.hasActiveVM()} runLoop=' + '$vmRunLoopActive state=' + '$' + '{eState.value}")\n'
    source = replace_once(source, log_old,
        '                println("@@ANDROID_STOP_JAVA@@ shutdown_return")\n',
        "shutdown return log")
    source = replace_once(source,
        "                if (!vmRunLoopActive && (eState.value == EmuState.STOPPED || !NativeApp.hasActiveVM())) {",
        """                TouchStationExtraShutdownDiagnostics.record(
                    com.armsx2.Pasx2Application.appContext,
                    "native-shutdown-returned",
                    "durationMs=" + (SystemClock.elapsedRealtime() - shutdownStartedAt) +
                        "; nativeActive=" + stillActive + "; runLoopActive=" + vmRunLoopActive,
                )
                if (!vmRunLoopActive && !stillActive) {""",
        "native idle completion gate")
    source = replace_once(source,
        """                    } else if (!restartQueued) {
                        synchronized(vmLifecycleLock) {
                            WindowImpl.toolbarVisible.value = true
                            WindowImpl.showLibrary.value = false
                            WindowImpl.overlayVisible.value = false
                        }
                        // Clear the current-game pointer (so Settings reverts to Global scope) and
                        // hand rotation back to the launcher. Shared with the other terminal paths.
                        onReturnedToLibrary()
                        finishToLauncherIfRequested()
                    }
                }
            }
        }

        fun restart() {""",
        """                    } else if (!restartQueued) {
                        synchronized(vmLifecycleLock) {
                            WindowImpl.toolbarVisible.value = true
                            WindowImpl.showLibrary.value = false
                            WindowImpl.overlayVisible.value = false
                        }
                        // Clear the current-game pointer (so Settings reverts to Global scope) and
                        // hand rotation back to the launcher. Shared with the other terminal paths.
                        onReturnedToLibrary()
                        finishToLauncherIfRequested()
                    }
                    TouchStationExtraShutdownDiagnostics.record(
                        com.armsx2.Pasx2Application.appContext,
                        "shutdown-completed",
                        "durationMs=" + (SystemClock.elapsedRealtime() - shutdownStartedAt),
                    )
                } else {
                    TouchStationExtraShutdownDiagnostics.record(
                        com.armsx2.Pasx2Application.appContext,
                        "shutdown-not-complete",
                        "nativeActive=" + stillActive + "; runLoopActive=" + vmRunLoopActive +
                            "; stop latch retained; no force termination attempted.",
                    )
                }
            }
        }

        fun restart() {""",
        "shutdown completion diagnostics")
    path.write_text(source, encoding="utf-8")

def patch_performance_tab(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    if "TouchStationExtraShutdownSuite()" in source:
        raise SystemExit("TouchStation Extra shutdown suite is already inserted")
    anchor = """        TouchStationExtra100Suite(settings = s)
        SettingsDivider()
"""
    source = replace_once(source, anchor, anchor + """
        TouchStationExtraShutdownSuite()
        SettingsDivider()
""", "Extra 100 suite insertion point")
    path.write_text(source, encoding="utf-8")

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args()
    app_dir = args.source / "app"
    runtime = app_dir / "src/main/java/com/armsx2/runtime/MainActivityRuntime.kt"
    settings_dir = app_dir / "src/main/java/com/armsx2/ui/settings"
    reliability_dir = app_dir / "src/main/java/com/armsx2/reliability"
    performance = settings_dir / "PerformanceTab.kt"
    diagnostics = reliability_dir / "TouchStationExtraShutdownDiagnostics.kt"
    suite = settings_dir / "TouchStationExtraShutdownSuite.kt"
    for path in (runtime, performance):
        if not path.is_file():
            raise SystemExit("Required upstream source file is missing: " + str(path))
    if not TEMPLATE.is_file():
        raise SystemExit("Shutdown suite template is missing: " + str(TEMPLATE))
    if diagnostics.exists() or suite.exists():
        raise SystemExit("TouchStation Extra shutdown source already exists; refusing to overwrite")
    kotlin = TEMPLATE.read_text(encoding="utf-8")
    for marker in ("fun TouchStationExtraShutdownSuite(", "TouchStationExtraShutdownDiagnostics"):
        if marker not in kotlin:
            raise SystemExit("Shutdown suite template is missing marker: " + marker)
    reliability_dir.mkdir(parents=True, exist_ok=True)
    diagnostics.write_text(
        kotlin[kotlin.index("/*DIAGNOSTICS-BEGIN*/") + len("/*DIAGNOSTICS-BEGIN*/"):kotlin.index("/*DIAGNOSTICS-END*/")].strip() + "\n",
        encoding="utf-8")
    suite.write_text(
        kotlin[kotlin.index("/*SUITE-BEGIN*/") + len("/*SUITE-BEGIN*/"):kotlin.index("/*SUITE-END*/")].strip() + "\n",
        encoding="utf-8")
    patch_runtime(runtime)
    patch_performance_tab(performance)
    print("Applied TouchStation Extra shutdown coalescing, lifecycle gating, persisted diagnostics and recovery UI.")

if __name__ == "__main__":
    main()
