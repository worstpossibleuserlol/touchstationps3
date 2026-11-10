# TouchStation Extra — 100-point bug-fix and verification pass

This update targets the reported issue: GTA IV reaches **Stopping**, then TouchStation exits to Android home. It hardens the app-side stop sequence and persists the last shutdown stage.

## What this update changes

1. Coalesces repeated stop requests; a second close action cannot queue another native shutdown while the first owns the VMStop executor.
2. Keeps the stop latch until both the VM run loop and native shutdown return, with native idleness confirmed.
3. Prevents optional autosave exceptions from skipping the native shutdown attempt.
4. Persists shutdown stages before entering native code and shows the last stage after a process crash/relaunch.
5. Adds a 20-second warning-only watchdog; it never force-kills native threads.
6. Adds a diagnostics panel to refresh, record observed outcomes and share the shutdown report.

A late-idle watcher now recovers the app-side stop latch if the native VM reports idle after the initial five-second settle window. Failed native-state queries remain UNKNOWN/active, and delayed callbacks are tied to the stop generation so an old timer cannot unlock a later session. The watcher stops after five minutes and retains the lock if the native core still reports active.

These are app/frontend safeguards, not a guarantee that GTA IV will run or that a native SIGSEGV is fixed.

## Status labels

**IMPLEMENTED** = code added in this pass. **EXISTING / CHECKED** = an app-side guard is already present. **MANUAL / DEVICE TEST** = real-device/game test required. **NATIVE CORE REQUIRED** = the pinned prebuilt native engine does not expose the required implementation point.

### 1–10 · Shutdown and exit

1. **IMPLEMENTED** — coalesce repeated stop requests into one native shutdown operation.
2. **IMPLEMENTED** — keep the stop latch until the VM run loop and native shutdown both return.
3. **IMPLEMENTED** — isolate autosave failure so it does not prevent the shutdown call.
4. **IMPLEMENTED** — record stop request, queue, native start, native return and completion stages.
5. **IMPLEMENTED** — persist the last reached stage before invoking native shutdown.
6. **IMPLEMENTED** — observe a 20-second shutdown delay tied to a stop-generation token, then poll for late native-idle completion for up to five minutes without forcibly interrupting native threads.
7. **IMPLEMENTED** — do not claim shutdown completion while the native VM still reports active.
8. **IMPLEMENTED** — retain evidence of native shutdown exceptions and incomplete shutdowns.
9. **IMPLEMENTED** — protect lifecycle reconciliation from a Java-side online-session cleanup exception.
10. **MANUAL / DEVICE TEST** — repeat close, pause/resume, restart and exit tests on a real game and inspect the report.

### 11–20 · PPU stability

11. **NATIVE CORE REQUIRED** — validate PPU worker initialization.
12. **NATIVE CORE REQUIRED** — verify PPU execution threads terminate cleanly.
13. **NATIVE CORE REQUIRED** — validate guest PPU state transitions.
14. **NATIVE CORE REQUIRED** — release PPU guest-thread resources on every exit path.
15. **NATIVE CORE REQUIRED** — validate native PPU task references before reuse.
16. **NATIVE CORE REQUIRED** — capture structured PPU exception information.
17. **EXISTING / CHECKED** — retain app-side PPU settings validation and diagnostics export.
18. **NATIVE CORE REQUIRED** — expose PPU module unload completion.
19. **NATIVE CORE REQUIRED** — expose PPU synchronization and queue state.
20. **MANUAL / DEVICE TEST** — compare PPU behavior across launches; settings guidance is not a measured benchmark.

### 21–30 · SPU stability

21. **NATIVE CORE REQUIRED** — validate SPU worker lifecycle transitions.
22. **NATIVE CORE REQUIRED** — expose stalled SPU task detection.
23. **NATIVE CORE REQUIRED** — verify SPU worker completion signals.
24. **NATIVE CORE REQUIRED** — validate native SPU task-state ownership.
25. **NATIVE CORE REQUIRED** — prevent duplicate native SPU worker teardown.
26. **NATIVE CORE REQUIRED** — validate SPU queue cleanup and ownership.
27. **NATIVE CORE REQUIRED** — detect stale native SPU task references.
28. **EXISTING / CHECKED** — retain app-side SPU settings and error guidance without fabricating live counters.
29. **NATIVE CORE REQUIRED** — expose SPU starvation and retry telemetry.
30. **MANUAL / DEVICE TEST** — test repeated exits and record whether native shutdown completes.

### 31–40 · RSX and graphics stability

31. **NATIVE CORE REQUIRED** — validate RSX shutdown ordering.
32. **NATIVE CORE REQUIRED** — drain pending RSX/GPU submissions before native resource destruction.
33. **NATIVE CORE REQUIRED** — validate RSX resource lifetime and ownership.
34. **NATIVE CORE REQUIRED** — expose Vulkan device-lost and driver error callbacks.
35. **EXISTING / CHECKED** — retain Android graphics capability and renderer-readiness checks.
36. **NATIVE CORE REQUIRED** — validate command-buffer state transitions.
37. **NATIVE CORE REQUIRED** — expose actual GPU fence completion telemetry.
38. **NATIVE CORE REQUIRED** — expose shader compile errors and completion status.
39. **NATIVE CORE REQUIRED** — make native GPU resource release idempotent.
40. **MANUAL / DEVICE TEST** — repeat shutdown under different renderer and frame-limit settings; no preset guarantees a fix.

### 41–50 · Android lifecycle

41. **IMPLEMENTED** — prevent duplicate Android close actions from enqueueing duplicate native shutdown calls.
42. **EXISTING / CHECKED** — report Android historical process-exit reasons where supported.
43. **EXISTING / CHECKED** — keep Android app-process crash evidence distinct from guest-game crash records.
44. **EXISTING / CHECKED** — retain low-memory readiness warnings.
45. **EXISTING / CHECKED** — retain Android API and device capability checks.
46. **EXISTING / CHECKED** — retain controller-disconnect and input-device diagnostics.
47. **MANUAL / DEVICE TEST** — test activity recreation and orientation transitions during/after a game.
48. **EXISTING / CHECKED** — retain activity and native-runtime readiness guards.
49. **MANUAL / DEVICE TEST** — validate on Android 16 and an earlier supported Android version.
50. **IMPLEMENTED** — persist shutdown-stage evidence for inspection after the next app launch.

### 51–60 · Memory and resources

51. **EXISTING / CHECKED** — inspect Android available RAM and app PSS.
52. **EXISTING / CHECKED** — classify Android low-memory conditions.
53. **NATIVE CORE REQUIRED** — expose native heap and allocator statistics.
54. **NATIVE CORE REQUIRED** — detect native resource leaks across game sessions.
55. **EXISTING / CHECKED** — retain bounded local diagnostic histories.
56. **EXISTING / CHECKED** — keep save-data transfer buffers bounded.
57. **EXISTING / CHECKED** — inspect app-private storage availability.
58. **NATIVE CORE REQUIRED** — expose native PPU/SPU/RSX allocation leak checks.
59. **EXISTING / CHECKED** — retain cleanup after app-side initialization failures.
60. **MANUAL / DEVICE TEST** — run repeated start/stop cycles while monitoring Android memory and thermal state.

### 61–70 · Game launch and runtime

61. **EXISTING / CHECKED** — inspect selected game-document readability and metadata.
62. **EXISTING / CHECKED** — validate firmware header recognition without claiming a full integrity check.
63. **EXISTING / CHECKED** — verify required native libraries are present in the packaged APK.
64. **EXISTING / CHECKED** — validate settings serialization and read-back.
65. **EXISTING / CHECKED** — retain game boot error reporting.
66. **EXISTING / CHECKED** — retain native-runtime readiness checks before launch.
67. **MANUAL / DEVICE TEST** — distinguish a game that exits normally from an app-process crash.
68. **EXISTING / CHECKED** — retain protection against launching another VM while shutdown is pending.
69. **EXISTING / CHECKED** — retain startup and failure diagnostics.
70. **MANUAL / DEVICE TEST** — repeat GTA IV launch/stop and compare the persisted last-stage report.

### 71–80 · Controller and input

71. **EXISTING / CHECKED** — enumerate Android gamepad and joystick devices.
72. **EXISTING / CHECKED** — refresh the device list and show detected controllers.
73. **NATIVE CORE REQUIRED** — validate native controller mapping application.
74. **EXISTING / CHECKED** — preserve supported per-game controller settings.
75. **EXISTING / CHECKED** — retain upstream controller reset controls.
76. **NATIVE CORE REQUIRED** — implement analog-axis calibration in the native bridge.
77. **NATIVE CORE REQUIRED** — verify trigger sensitivity at the native input layer.
78. **EXISTING / CHECKED** — capture Android digital key events.
79. **EXISTING / CHECKED** — enumerate multiple Android input devices.
80. **MANUAL / DEVICE TEST** — test controller disconnect/reconnect while a game is running and while stopping.

### 81–90 · Files and settings

81. **EXISTING / CHECKED** — retain the upstream game library as the source of installed-game state.
82. **EXISTING / CHECKED** — retain current dashboard and navigation behavior.
83. **EXISTING / CHECKED** — preserve existing theme settings.
84. **EXISTING / CHECKED** — retain the native performance overlay rather than inventing guest metrics.
85. **EXISTING / CHECKED** — retain searchable advanced settings.
86. **EXISTING / CHECKED** — retain settings category separation.
87. **EXISTING / CHECKED** — retain conservative/safe profile support.
88. **EXISTING / CHECKED** — record settings history.
89. **EXISTING / CHECKED** — retain settings checkpoint rollback.
90. **EXISTING / CHECKED** — respect Android accessibility and display scaling.

### 91–100 · Diagnostics and regression

91. **EXISTING / CHECKED** — run app-side startup/native-readiness checks.
92. **EXISTING / CHECKED** — inspect selected game file readability and metadata.
93. **EXISTING / CHECKED** — distinguish PUP header recognition from full firmware verification.
94. **EXISTING / CHECKED** — retain crash-loop safe-mode behavior.
95. **EXISTING / CHECKED** — retain failed-launch recovery and settings rollback.
96. **IMPLEMENTED** — show persisted shutdown events and the last reached stage.
97. **IMPLEMENTED** — export the shutdown report through Android's share sheet.
98. **EXISTING / CHECKED** — retain per-game user-recorded stability observations.
99. **EXISTING / CHECKED** — preserve safe mode as an app recovery path.
100. **MANUAL / DEVICE TEST** — execute repeated real-game boot, shutdown and relaunch regression runs.

## Native-core boundary

The workflow uses a pinned prebuilt ARM64 emulator release. This update does not rebuild native PPU, SPU, RSX, Vulkan or GPU engine code. Items labelled **NATIVE CORE REQUIRED** are integration requirements, not implemented native fixes. A Kotlin watchdog cannot safely cancel a stuck native shutdown or recover from a native SIGSEGV. Native repair requires source-level changes, a matching ARM64 rebuild and real-device testing.

The 100 checks are not proof of 100 successful real-game tests. The GTA IV shutdown test must still be run on the target device.


## Follow-up lifecycle audit

The follow-up audit found two additional frontend defects and adds regression coverage:

- **BIOS/system-menu stop path:** startBios() had a separate finally block that cleared vmStopInProgress without waiting for NativeApp.shutdown() to return and the native VM to report idle. It now uses the same native-idle gate as the game run loop.
- **Restart-intent clobbering:** a duplicate ordinary stop request could set vmRestartAfterStop = false while a restart was already pending. A duplicate stop now preserves the in-flight restart intent; a fresh stop can still clear a stale request.
- **Regression coverage:** the shutdown patch test fixture now includes both game and BIOS run-loop completion paths and asserts both use the native-idle gate.
- **Already-stopped external close:** the early-return path now calls finishToLauncherIfRequested(), so a close request from an external frontend is not silently ignored if the guest stopped just before the close action.
- **Late-recovery report accuracy:** the diagnostics report now treats shutdown-late-idle-recovered as a successful completion, instead of continuing to warn that the same session never completed.
- **False boot success:** the native bridge previously returned success after its 10-second boot-settle wait even if the emulator never left Stopped. It now reports BootTimeout and returns false, while preserving a user stop or an armed restart. A passing BootResult alone is no longer treated as proof that the VM started.

These changes are frontend lifecycle safeguards. They do not repair a native-core hang or prove GTA IV/GTA SA stability on the target handset.

## Follow-up pass

See [EXTRA_100_BUGFIXES_20_MORE.md](EXTRA_100_BUGFIXES_20_MORE.md) for 20 additional fixes covering identifier collisions, document-provider streams, backup safety and session tracking.