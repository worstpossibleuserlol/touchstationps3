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
        "        // Distinguishes delayed callbacks from a later stop operation.\n"
        "        @Volatile private var vmStopGeneration = 0L\n"
        "        @Volatile private var vmRestartAfterStop = false",
        "shutdown state fields")
    source = replace_once(source,
        """        fun isVmIdle(): Boolean = eState.value == EmuState.STOPPED && !vmStopInProgress && !vmRunLoopActive""",
        """        fun isVmIdle(): Boolean =
            eState.value == EmuState.STOPPED &&
                !vmStopInProgress &&
                !vmRunLoopActive &&
                (!nativeReady.value || runCatching { !NativeApp.hasActiveVM() }.getOrDefault(false))""",
        "native-aware VM idle predicate")
    source = replace_once(source,
        """        fun exitApp() {
            if (eState.value == EmuState.STOPPED && !vmStopInProgress && !vmRunLoopActive) {""",
        """        fun exitApp() {
            val nativeActive = nativeReady.value && runCatching { NativeApp.hasActiveVM() }.getOrDefault(true)
            if (eState.value == EmuState.STOPPED && !vmStopInProgress && !vmRunLoopActive && !nativeActive) {""",
        "native-aware app exit predicate")
    source = replace_once(source,
        """        fun start() {
            synchronized(vmLifecycleLock) {
                if (vmStopInProgress || vmRunLoopActive || eState.value != EmuState.STOPPED) {
                    vmRestartAfterStop = true
                    return
                }
                vmRunLoopActive = true
                vmRestartQueued = false
            }

            invoke {""",
        """        fun start() {
            val nativeReadyNow = nativeReady.value
            val nativeActive = nativeReadyNow && runCatching { NativeApp.hasActiveVM() }.getOrDefault(true)
            var staleNativeSession = false
            var staleFrontendState: EmuState? = null
            val shouldStart = synchronized(vmLifecycleLock) {
                // The frontend enum can lag behind a VM that has already stopped (for example,
                // after an abnormal guest exit). Trust a successful native-idle query only when
                // there is no run loop and no shutdown owner; normalize that stale UI state.
                if (nativeReadyNow && !nativeActive &&
                    !vmStopInProgress && !vmRunLoopActive && eState.value != EmuState.STOPPED
                ) {
                    staleFrontendState = eState.value
                    eState.value = EmuState.STOPPED
                }
                if (vmStopInProgress || vmRunLoopActive || eState.value != EmuState.STOPPED || nativeActive) {
                    vmRestartAfterStop = true
                    staleNativeSession = nativeActive && !vmStopInProgress && !vmRunLoopActive &&
                        eState.value == EmuState.STOPPED
                    false
                } else {
                    vmRunLoopActive = true
                    vmRestartQueued = false
                    true
                }
            }
            staleFrontendState?.let { previous ->
                TouchStationExtraShutdownDiagnostics.record(
                    com.armsx2.Pasx2Application.appContext,
                    "stale-frontend-state-recovered",
                    "Previous frontend state=" + previous + "; native VM reported idle and no run loop or shutdown was active.",
                )
            }
            if (!shouldStart) {
                // Only request a stop for a stale native session whose frontend flags
                // otherwise claim idle. Do not stop a legitimately running game.
                if (staleNativeSession) stop(restartAfterStop = true)
                return
            }

            invoke {""",
        "native-aware game start gate")
    source = replace_once(source,
        """            currentGame.value = info
            launchedExternally = external
            m_szGamefile = uri
            synchronized(vmLifecycleLock) {
                if (eState.value != EmuState.STOPPED || vmStopInProgress || vmRunLoopActive) {
                    vmRestartAfterStop = true
                }
            }
            if (eState.value == EmuState.STOPPED && !vmStopInProgress && !vmRunLoopActive)
                start()
            else
                stop(restartAfterStop = true)""",
        """            currentGame.value = info
            launchedExternally = external
            m_szGamefile = uri

            // A game-card tap can arrive after the native VM has stopped but before the
            // frontend enum has reconciled from RUNNING/STOPPING to STOPPED. Only normalize
            // that state when the native query positively reports idle and no app-side
            // run loop or shutdown owner remains.
            val nativeReadyForLaunch = nativeReady.value
            val nativeActiveForLaunch = nativeReadyForLaunch &&
                runCatching { NativeApp.hasActiveVM() }.getOrDefault(true)
            var recoveredFrontendState: EmuState? = null
            if (nativeReadyForLaunch && !nativeActiveForLaunch) {
                synchronized(vmLifecycleLock) {
                    if (!vmStopInProgress && !vmRunLoopActive && eState.value != EmuState.STOPPED) {
                        recoveredFrontendState = eState.value
                        eState.value = EmuState.STOPPED
                    }
                }
            }
            recoveredFrontendState?.let { previous ->
                TouchStationExtraShutdownDiagnostics.record(
                    com.armsx2.Pasx2Application.appContext,
                    "launch-recovered-stale-frontend-state",
                    "Previous frontend state=" + previous + "; native VM was idle before a new game-card launch.",
                )
            }

            synchronized(vmLifecycleLock) {
                if (eState.value != EmuState.STOPPED || vmStopInProgress || vmRunLoopActive) {
                    vmRestartAfterStop = true
                }
            }
            if (eState.value == EmuState.STOPPED && !vmStopInProgress && !vmRunLoopActive)
                start()
            else
                stop(restartAfterStop = true)""",
        "launch entry stale frontend-state reconciliation")
    source = replace_once(source,
        """            val shouldStart = synchronized(vmLifecycleLock) {
                if (vmStopInProgress || vmRunLoopActive || eState.value != EmuState.STOPPED) {""",
        """            val nativeActive = nativeReady.value && runCatching { NativeApp.hasActiveVM() }.getOrDefault(true)
            val shouldStart = synchronized(vmLifecycleLock) {
                if (vmStopInProgress || vmRunLoopActive || eState.value != EmuState.STOPPED || nativeActive) {""",
        "native-aware BIOS start gate")
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
    # BIOS/system-menu emulation has a separate run loop. It must use the same
    # native-idle gate; otherwise exiting BIOS can clear the stop latch while
    # NativeApp.shutdown() is still unwinding.
    source = replace_once(source,
        """                    eState.value = EmuState.STOPPED
                    com.armsx2.online.OnlineSession.release(com.armsx2.Pasx2Application.appContext)
                    val restartNow = synchronized(vmLifecycleLock) {
                        vmRunLoopActive = false
                        vmStopInProgress = false
                        if (vmRestartAfterStop) {""",
        """                    eState.value = EmuState.STOPPED
                    TouchStationExtraShutdownDiagnostics.record(
                        com.armsx2.Pasx2Application.appContext,
                        "bios-vm-run-loop-exited",
                        "The BIOS run loop returned; native shutdown completion is tracked separately.",
                    )
                    runCatching {
                        com.armsx2.online.OnlineSession.release(com.armsx2.Pasx2Application.appContext)
                    }.onFailure {
                        TouchStationExtraShutdownDiagnostics.record(
                            com.armsx2.Pasx2Application.appContext,
                            "bios-online-session-cleanup-failed",
                            it.javaClass.simpleName + ": " + (it.message ?: "no message"),
                        )
                    }
                    val nativeStillActive = runCatching { NativeApp.hasActiveVM() }.getOrDefault(true)
                    val restartNow = synchronized(vmLifecycleLock) {
                        vmRunLoopActive = false
                        if (vmShutdownCallReturned && !nativeStillActive) vmStopInProgress = false
                        if (vmRestartAfterStop) {""",
        "BIOS run-loop completion ordering")
    source = replace_once(source,
        """            val nativeActive = runCatching { NativeApp.hasActiveVM() }.getOrDefault(false)
            val shouldStop = synchronized(vmLifecycleLock) {""",
        """            // A failed native-state query is UNKNOWN, not proof that the VM is idle.
            val nativeActive = nativeReady.value && runCatching { NativeApp.hasActiveVM() }.getOrDefault(true)
            var queueShutdown = false
            var stopGeneration = 0L
            TouchStationExtraShutdownDiagnostics.record(
                com.armsx2.Pasx2Application.appContext,
                "stop-requested",
                "state=" + eState.value + "; nativeActive=" + nativeActive +
                    "; restart=" + restartAfterStop + "; saveAutosave=" + saveAutosave,
            )
            val shouldStop = synchronized(vmLifecycleLock) {""",
        "stop request tracking")
    source = replace_once(source,
        """                if (restartAfterStop)
                    vmRestartAfterStop = true
                else
                    vmRestartAfterStop = false""",
        """                if (restartAfterStop) {
                    vmRestartAfterStop = true
                } else if (!vmStopInProgress) {
                    // A fresh non-restart stop may discard a stale request, but a
                    // duplicate stop must not cancel a restart already in flight.
                    vmRestartAfterStop = false
                }""",
        "restart request preservation")
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
                    vmStopGeneration += 1
                    stopGeneration = vmStopGeneration
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
        """                onReturnedToLibrary()
                return
            }
            if (!queueShutdown) {""",
        """                onReturnedToLibrary()
                finishToLauncherIfRequested()
                return
            }
            if (!queueShutdown) {""",
        "already-stopped close exit handling")
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
                if (vmStopInProgress && vmStopGeneration == stopGeneration) {
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
        """                    if (restartNow) {
                        start()
                    } else if (!restartQueued) {
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
        """                    if (restartQueued) {
                        // The run-loop finally block already queued start() on this same
                        // serialized executor. Do not start a second copy here: that second
                        // start would see vmRunLoopActive and arm an unintended future restart.
                        if (restartNow) {
                            TouchStationExtraShutdownDiagnostics.record(
                                com.armsx2.Pasx2Application.appContext,
                                "duplicate-restart-suppressed",
                                "A launch was already queued by the VM run-loop completion path.",
                            )
                        }
                    } else if (restartNow) {
                        start()
                    } else {
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
                            "; stop latch retained; no force termination attempted; late recovery is scheduled.",
                    )
                    scheduleLateNativeIdleRecovery(shutdownStartedAt, stopGeneration, 0)
                }
            }
        }

        private fun scheduleLateNativeIdleRecovery(
            shutdownStartedAt: Long,
            stopGeneration: Long,
            attempt: Int,
        ) {
            if (!vmStopInProgress || vmStopGeneration != stopGeneration) return
            if (attempt >= 300) {
                TouchStationExtraShutdownDiagnostics.record(
                    com.armsx2.Pasx2Application.appContext,
                    "late-idle-recovery-expired",
                    "Native VM did not report idle within five minutes; stop latch retained. No native thread was force-killed.",
                )
                return
            }
            android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({
                if (!vmStopInProgress || vmStopGeneration != stopGeneration) return@postDelayed
                val stillActive = runCatching { NativeApp.hasActiveVM() }.getOrDefault(true)
                if (stillActive || vmRunLoopActive) {
                    scheduleLateNativeIdleRecovery(shutdownStartedAt, stopGeneration, attempt + 1)
                    return@postDelayed
                }
                var completed = false
                var restartQueued = false
                val restartNow = synchronized(vmLifecycleLock) {
                    if (!vmStopInProgress || vmStopGeneration != stopGeneration || vmRunLoopActive) {
                        false
                    } else {
                        completed = true
                        vmStopInProgress = false
                        restartQueued = vmRestartQueued
                        if (vmRestartAfterStop) {
                            vmRestartAfterStop = false
                            true
                        } else {
                            false
                        }
                    }
                }
                if (!completed) return@postDelayed
                TouchStationExtraShutdownDiagnostics.record(
                    com.armsx2.Pasx2Application.appContext,
                    "shutdown-late-idle-recovered",
                    "Native VM finally reported idle after " +
                        (SystemClock.elapsedRealtime() - shutdownStartedAt) + "ms; generation=" + stopGeneration,
                )
                if (restartNow) {
                    start()
                } else if (!restartQueued) {
                    synchronized(vmLifecycleLock) {
                        WindowImpl.toolbarVisible.value = true
                        WindowImpl.showLibrary.value = false
                        WindowImpl.overlayVisible.value = false
                    }
                    onReturnedToLibrary()
                    finishToLauncherIfRequested()
                }
            }, 1_000L)
        }

        fun restart() {""",
        "shutdown completion diagnostics")

    # A user pressing Exit Game owns the terminal outcome. A restart may already
    # have been queued while the guest was loading; this latch prevents that
    # stale queued task from reopening the game after the user asked to exit.
    def replace_if_present(src: str, old: str, new: str, label: str) -> str:
        if old not in src:
            return src
        return replace_once(src, old, new, label)

    source = replace_once(source,
        """@Volatile private var vmStopGeneration = 0L
        @Volatile private var vmRestartAfterStop = false""",
        """@Volatile private var vmStopGeneration = 0L
        @Volatile private var vmExitToMainMenuAfterStop = false
        @Volatile private var vmRestartAfterStop = false""",
        "Exit Game intent state")
    source = replace_if_present(source,
        """        /** Close the running game the way the user asked for.""",
        """        /** Return to TouchStation's own main menu after the VM and native shutdown are both idle.
         *  The stopping UI remains in place until terminal cleanup is safe. */
        private fun returnToMainMenuAfterVmStop() {
            synchronized(vmLifecycleLock) {
                WindowImpl.toolbarVisible.value = true
                WindowImpl.showLibrary.value = false
                WindowImpl.overlayVisible.value = false
            }
            onReturnedToLibrary()
            finishToLauncherIfRequested()
        }

        /** Close the running game the way the user asked for.""",
        "shared main-menu return")
    source = replace_if_present(source,
        """        fun closeGame(saveAutosave: Boolean = false) {
            if (launchedExternally && prefs.getBoolean("ui.exitToLauncherExternal", true))
                quitAfterStop = true
            stop(saveAutosave = saveAutosave)
        }""",
        """        fun closeGame(saveAutosave: Boolean = false) {
            synchronized(vmLifecycleLock) {
                // Exit Game is terminal and returns inside TouchStation, not to Android home.
                vmExitToMainMenuAfterStop = true
                vmRestartAfterStop = false
                vmRestartQueued = false
            }
            stop(saveAutosave = saveAutosave)
        }""",
        "Exit Game cancels queued restart and returns to TouchStation")
    source = replace_if_present(source,
        """                if (vmStopInProgress || vmRunLoopActive || eState.value != EmuState.STOPPED || nativeActive) {
                    vmRestartAfterStop = true""",
        """                if (vmExitToMainMenuAfterStop) {
                    false
                } else if (vmStopInProgress || vmRunLoopActive || eState.value != EmuState.STOPPED || nativeActive) {
                    vmRestartAfterStop = true""",
        "Exit Game blocks stale queued start")
    source = replace_if_present(source,
        """            currentGame.value = info
            launchedExternally = external
            m_szGamefile = uri""",
        """            // An explicit new game selection supersedes a previous Exit Game request.
            vmExitToMainMenuAfterStop = false
            currentGame.value = info
            launchedExternally = external
            m_szGamefile = uri""",
        "new game supersedes exit intent")
    source = replace_if_present(source,
        """                    val booted = NativeApp.runVMThread(bootTarget)""",
        """                    // Exit Game (or a newer game selection) can arrive while settings and
                    // renderer setup are still preparing this boot. Do not enter the native VM
                    // after that stop has already taken ownership of the session.
                    if (vmExitToMainMenuAfterStop || vmStopInProgress) {
                        TouchStationExtraShutdownDiagnostics.record(
                            com.armsx2.Pasx2Application.appContext,
                            "boot-cancelled-before-native-run",
                            "A terminal exit or replacement launch arrived during game preparation.",
                        )
                        return@invoke
                    }
                    val booted = NativeApp.runVMThread(bootTarget)""",
        "cancel loading game before native VM entry")
    source = replace_if_present(source,
        """                    NativeApp.runVMThread(m_szGamefile)""",
        """                    if (vmExitToMainMenuAfterStop || vmStopInProgress) {
                        TouchStationExtraShutdownDiagnostics.record(
                            com.armsx2.Pasx2Application.appContext,
                            "bios-boot-cancelled-before-native-run",
                            "A terminal exit arrived during BIOS preparation.",
                        )
                        return@invoke
                    }
                    NativeApp.runVMThread(m_szGamefile)""",
        "cancel BIOS boot before native VM entry")
    source = replace_if_present(source,
        """        fun startBios() {
            currentGame.value = null""",
        """        fun startBios() {
            vmExitToMainMenuAfterStop = false
            currentGame.value = null""",
        "BIOS launch clears exit intent")
    source = replace_if_present(source,
        """        fun restart() {
            synchronized(vmLifecycleLock) {
                vmRestartAfterStop = true""",
        """        fun restart() {
            synchronized(vmLifecycleLock) {
                vmExitToMainMenuAfterStop = false
                vmRestartAfterStop = true""",
        "explicit restart supersedes exit intent")

    # If the user exits while a restart is pending, the loop-finally path must
    # not enqueue that restart. Both game and BIOS loops share this ordering.
    restart_anchor = """                        if (vmShutdownCallReturned && !nativeStillActive) vmStopInProgress = false
                        if (vmRestartAfterStop) {"""
    restart_replacement = """                        if (vmShutdownCallReturned && !nativeStillActive) vmStopInProgress = false
                        if (vmExitToMainMenuAfterStop) {
                            vmRestartAfterStop = false
                            vmRestartQueued = false
                            false
                        } else if (vmRestartAfterStop) {"""
    if source.count(restart_anchor) != 2:
        raise SystemExit("Expected game and BIOS Exit Game restart gates; found " + str(source.count(restart_anchor)))
    source = source.replace(restart_anchor, restart_replacement, 2)

    # Keep the in-app stopping state until native shutdown and the run loop have
    # both finished. A natural, non-stopping game exit still returns immediately.
    game_return_old = """                    } else {
                        WindowImpl.toolbarVisible.value = true
                        WindowImpl.showLibrary.value = false
                        WindowImpl.overlayVisible.value = false
                        // This is the branch that actually fires on a normal game exit (stop()'s
                        // equivalent block loses the vmRunLoopActive race), so the return-to-library
                        // cleanup has to happen here or the launcher keeps the game's rotation.
                        onReturnedToLibrary()
                        finishToLauncherIfRequested()
                    }
                }
            }
        }

        /** Push setup-wizard renderer/upscale choices"""
    game_return_new = """                    } else if (!vmStopInProgress) {
                        returnToMainMenuAfterVmStop()
                    }
                }
            }
        }

        /** Push setup-wizard renderer/upscale choices"""
    source = replace_if_present(source, game_return_old, game_return_new,
        "wait for shutdown before leaving stopping screen")
    bios_return_old = """                    } else {
                        // BIOS exit had no cleanup at all — it relied entirely on stop()'s racy
                        // branch, so quitting the BIOS also left the launcher stuck in its rotation.
                        onReturnedToLibrary()
                    }
                }
            }
        }

        // pause/resume on a dedicated serialized executor"""
    bios_return_new = """                    } else if (!vmStopInProgress) {
                        returnToMainMenuAfterVmStop()
                    }
                }
            }
        }

        // pause/resume on a dedicated serialized executor"""
    source = replace_if_present(source, bios_return_old, bios_return_new,
        "BIOS waits for shutdown before menu return")

    source = replace_if_present(source,
        """                onReturnedToLibrary()
                finishToLauncherIfRequested()
                return
            }
            if (!queueShutdown) {""",
        """                returnToMainMenuAfterVmStop()
                return
            }
            if (!queueShutdown) {""",
        "already-idle Exit Game returns to menu")
    source = replace_if_present(source,
        """                    if (restartQueued) {
                        // The run-loop finally block already queued start() on this same""",
        """                    if (vmExitToMainMenuAfterStop) {
                        vmRestartAfterStop = false
                        vmRestartQueued = false
                        returnToMainMenuAfterVmStop()
                    } else if (restartQueued) {
                        // The run-loop finally block already queued start() on this same""",
        "shutdown completion honors Exit Game")
    source = replace_if_present(source,
        """                if (restartNow) {
                    start()
                } else if (!restartQueued) {
                    synchronized(vmLifecycleLock) {
                        WindowImpl.toolbarVisible.value = true
                        WindowImpl.showLibrary.value = false
                        WindowImpl.overlayVisible.value = false
                    }
                    onReturnedToLibrary()
                    finishToLauncherIfRequested()
                }
            }, 1_000L)""",
        """                if (vmExitToMainMenuAfterStop) {
                    vmRestartAfterStop = false
                    vmRestartQueued = false
                    returnToMainMenuAfterVmStop()
                } else if (restartNow) {
                    start()
                } else if (!restartQueued) {
                    returnToMainMenuAfterVmStop()
                }
            }, 1_000L)""",
        "late-idle recovery honors Exit Game")

    path.write_text(source, encoding="utf-8")


def patch_bridge(path: Path) -> None:
    """Fail a boot that never leaves Stopped instead of reporting a false success."""
    source = path.read_text(encoding="utf-8")
    if 'lastBootError = "BootTimeout"' in source:
        raise SystemExit("TouchStation Extra boot-timeout guard is already installed")
    source = replace_once(
        source,
        """        while (!stopRequested && ARMSX3.getState() == EmulatorState.Stopped &&
            settleMs < BOOT_SETTLE_TIMEOUT_MS
        ) {
            Thread.sleep(POLL_INTERVAL_MS)
            settleMs += POLL_INTERVAL_MS
        }

        // stopRequested is the escape hatch, and it is not optional.""",
        """        while (!stopRequested && ARMSX3.getState() == EmulatorState.Stopped &&
            settleMs < BOOT_SETTLE_TIMEOUT_MS
        ) {
            Thread.sleep(POLL_INTERVAL_MS)
            settleMs += POLL_INTERVAL_MS
        }

        // A successful BootResult is not proof that the VM actually started.
        // If it never left Stopped within the bounded settle window, report a
        // launch failure rather than starting pumps and returning true.
        // Preserve user-requested stops and an already-armed native restart.
        if (!stopRequested &&
            ARMSX3.getState() == EmulatorState.Stopped &&
            !restartPending()
        ) {
            lastBootError = "BootTimeout"
            android.util.Log.e(
                "ARMSX3",
                "boot did not leave Stopped within \${BOOT_SETTLE_TIMEOUT_MS}ms",
            )
            return false
        }

        // stopRequested is the escape hatch, and it is not optional.""",
        "native boot settle timeout",
    )
    path.write_text(source, encoding="utf-8")

def patch_native_compile_state(app_dir: Path) -> None:
    """Distinguish an unsupported native PPU-progress API from an idle compiler."""
    native_path = app_dir / "src/main/cpp/native-lib.cpp"
    kotlin_path = app_dir / "src/main/java/com/armsx3/core/ARMSX3.kt"
    native_source = native_path.read_text(encoding="utf-8")
    kotlin_source = kotlin_path.read_text(encoding="utf-8")

    old_native = "return coreLib.getPlayCompileState ? coreLib.getPlayCompileState() : 0;"
    new_native = "return coreLib.getPlayCompileState ? coreLib.getPlayCompileState() : -1;"
    old_kotlin = "    /** 0 while nothing compiles during play, else 1 + the PPU modules compiled so far in this stretch. */\n    external fun getPlayCompileState(): Int"
    new_kotlin = "    /** -1 if unsupported; 0 if no sustained PPU compile is reported; positive values encode progress. */\n    external fun getPlayCompileState(): Int"

    if new_native in native_source or new_kotlin in kotlin_source:
        raise SystemExit("Native PPU compile-state availability fix is already installed")
    patched_native = replace_once(native_source, old_native, new_native, "optional PPU compile-state JNI fallback")
    patched_kotlin = replace_once(kotlin_source, old_kotlin, new_kotlin, "PPU compile-state API contract")
    native_path.write_text(patched_native, encoding="utf-8")
    kotlin_path.write_text(patched_kotlin, encoding="utf-8")


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
    bridge = app_dir / "src/main/java/com/armsx3/Rpcs3Bridge.kt"
    native_glue = app_dir / "src/main/cpp/native-lib.cpp"
    core_api = app_dir / "src/main/java/com/armsx3/core/ARMSX3.kt"
    diagnostics = reliability_dir / "TouchStationExtraShutdownDiagnostics.kt"
    suite = settings_dir / "TouchStationExtraShutdownSuite.kt"
    for path in (runtime, performance, bridge, native_glue, core_api):
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
    patch_bridge(bridge)
    patch_native_compile_state(app_dir)
    patch_performance_tab(performance)
    print("Applied TouchStation Extra shutdown/boot lifecycle safeguards, native PPU-progress availability reporting, persisted diagnostics and recovery UI.")

if __name__ == "__main__":
    main()
