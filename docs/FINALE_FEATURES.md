# TouchStation Extra — cumulative feature map

This release combines the diagnostics and settings tools from the earlier TouchStation builds with the Finale compatibility, device-readiness and GTA IV profile panels. The 50 entries below describe product-facing capabilities across the full app. They are not 50 new native PS3-core features.

## PPU and SPU diagnostics

1. **PPU compilation visibility** — shows a clear unavailable state when the native bridge does not expose live job counters.
2. **PPU cache inventory** — reports discovered PPU cache files and total size.
3. **Suspicious PPU cache detection** — flags unreadable or empty files for review; it does not delete them.
4. **PPU thread recommendation** — proposes a conservative value based on available device resources.
5. **LLVM compile thread control** — exposes the existing native setting and saves it through the emulator configuration.
6. **SPU decoder selection** — exposes the supported decoder choices.
7. **SPU block-size selection** — exposes Safe, Mega and Giga modes.
8. **SPU cache inventory** — reports discovered SPU cache files and size.
9. **SPU workload/configuration diagnostics** — displays supported SPU options and available cache evidence.
10. **Recompiler and process-error evidence** — combines exposed settings with Android process-exit information; native PPU/SPU exception counters remain unavailable unless the core exports them.

## Compatibility and game library

11. **Official RPCS3 compatibility-data refresh** — downloads the official desktop compatibility export on request.
12. **Exact title-ID matching** — matches normalized PS3 title IDs, not approximate game names.
13. **Library search and compatibility badges** — filters the local PS3 library by title or ID and shows exact-ID desktop statuses on matching cards, clearly labelled PC.
14. **Official status and sorting** — displays the status attached to the matched ID and sorts by Playable, Ingame, Intro, Loadable and Nothing; unknown games remain below verified records.
15. **Official compatibility test date** — shows the database's recorded test date where present.
16. **Game update metadata** — displays the latest update field where the database supplies one.
17. **Device-local compatibility record** — stores a separate user-entered result for this game and handset.
18. **Local test-stage record** — lets the user record the latest observed boot, menu, gameplay, stable-session or failed-boot result for this handset.
19. **Game boot and launch readiness evidence** — brings together current engine/runtime state and prior process-exit evidence.
20. **GTA IV per-game profile** — applies a conservative set of existing PS3 settings only when GTA IV is selected and per-game settings are active.

## Performance and device monitoring

21. **CPU thread configuration** — shows the emulator's configured PPU/LLVM thread values; it is not presented as physical CPU utilization.
22. **Native in-game FPS** — uses the core's in-game overlay when exposed.
23. **Native frametime graph** — reuses the core's own graph rather than inventing frame samples.
24. **Available-RAM history** — keeps a bounded history and graph of Android-reported free memory.
25. **Application PSS** — reports Android's process memory estimate where available.
26. **Available memory** — shows Android's current available RAM estimate.
27. **Thermal state** — displays the Android thermal severity when the device exposes it.
28. **Thermal warnings** — highlights Android-reported elevated thermal states in the monitoring tools.
29. **Device capability snapshot** — reports the Android version, ABI, SoC identity when available, and processor count.
30. **Physical controller diagnostics** — lists detected gamepad/joystick devices and the existing controller monitor reports connection loss.

## Graphics, renderer and configuration

31. **OpenGL renderer information** — displays the renderer/vendor/version information where available.
32. **Vulkan system capability information** — displays Android-reported Vulkan feature information; this is not a full physical-device extension dump.
33. **Shader cache inventory** — reports known shader-cache files.
34. **Shader cache size** — reports the size of known cache files.
35. **Shader/cache warning evidence** — identifies available cache anomalies for review; it is not a GPU-driver certification.
36. **Display/output profiles** — exposes the existing output-scaling controls without claiming to change the game's internal RSX resolution.
37. **Per-game configuration backup** — saves the supported settings subset for the selected title.
38. **Audio configuration** — retains the existing audio backend, format and buffering controls.
39. **Per-game settings profiles** — keeps supported configuration separate by game.
40. **Automatic settings recommendations** — uses available device details to propose conservative profiles and verifies saved values.

## Stability, storage and reporting

41. **Android crash/exit history** — displays process exit reasons exposed by Android.
42. **Downloadable TouchStation.log** — captures this app process's available logcat output plus a device/game diagnostic snapshot, then saves it to Downloads on Android 10+; no system-wide logs are collected.
43. **Safe-mode startup/recovery** — retains the existing frontend recovery path.
44. **Safe frontend relaunch** — only offers the relaunch action when the emulator reports STOPPED.
45. **Last-known settings recovery** — retains a recovery point for supported settings.
46. **Settings read-back validation** — checks that key values persist after saving and reloading.
47. **Per-game profile restore** — restores the supported settings subset from a saved profile.
48. **Storage/cache inventory** — reports available app-private storage and known cache usage.
49. **Read-only diagnostic policy** — inspection never automatically deletes game saves, firmware or cache contents.
50. **Full system diagnostic report** — combines device, controller, engine-state, compatibility and configuration evidence for troubleshooting.

## Compatibility data interpretation

The official database is the desktop RPCS3 compatibility list. Its result is associated with a specific game ID and is not a prediction for a particular Android phone. The local device record is separate, user-entered evidence. The app never upgrades an unknown game to a positive status just because a title string looks similar.

The GTA IV profile is a conservative configuration preset, not a port, patch or native-core modification. It selects Accurate SPU XFloat, Safe SPU block size, asynchronous shader recompilation, MSAA off, SPU cache on, LLVM precompilation on, one LLVM compile thread and at most two PPU threads. The profile is restricted to GTA IV while per-game settings are active. A successful settings write does not mean the game has booted or is playable.

## Branding and source notices

TouchStation is the product-facing app identity. Unneeded upstream social and website links are not part of the TouchStation navigation. Third-party package names, copyright notices, licence texts, source attribution and corresponding-source availability are retained as required. The Android package and native library identifiers are implementation details and are not renamed in a way that would break the runtime.

## APK size

The APK is built from the actual application, dependencies, native engine libraries and enabled assets. It is not padded with unused files or arbitrary data to hit a byte target. The APK download is kept separate from the larger corresponding-source archive and its checksum.


## TouchStation Finale stability update

The Finale Android frontend now includes the following user-facing stability tools:

1. Download `TouchStation.log` to Downloads (Android 10+) or app-specific Documents on older Android versions.
2. Share the exported log through Android's share sheet.
3. Capture a game-error snapshot when the bridge supplies an error notice. Full process-death tombstones are not guaranteed.
4. Classify and count explicit FIFO error messages.
5. Persist the last 30 game-error notices locally.
6. Swipe an error banner upward to hide it.
7. Dismissal hides the banner only; it does not resume a stopped game.
8. Keep critical-error wording and event history visible in diagnostics.
9. Show plain-language explanations for common FIFO, shader, memory, PPU and SPU messages.
10. Show a relevant next-step suggestion for common errors.
11. No live FIFO stall watchdog is claimed: the bundled native bridge exposes no queue-depth or command-progress counter.
12. The Android GTA IV profile applies the core-supported RSX FIFO Fetch Accuracy value "Ordered & Atomic" and Driver Wake-Up Delay 20 µs per game; this follows the native error's own recommendation to move away from PS3 FIFO mode and raise the driver wake delay, but is not proven to fix every title.
13. No GPU-fence synchronization health check is claimed without native fence telemetry.
14. No RSX command-stream validator is claimed without native command instrumentation.
15. No automatic GPU queue recovery is attempted; an unsafe reset could corrupt emulator state.
16. Existing per-game settings profiles remain isolated from global settings.
17. Existing cache inventory is read-only; no cache files are deleted automatically.
18. Existing Android memory reporting is retained; low-memory status is evidence, not a guarantee of successful emulation.
19. Existing Android thermal reporting is retained; elevated status is surfaced without fabricating GPU telemetry.
20. Existing exact-title-ID desktop compatibility lookup remains a reference only and is not represented as a Dimensity 7100 compatibility guarantee.

### FIFO fix boundary

The visible `Dead FIFO commands queue state has been detected` message is thrown by the native RSX FIFO recovery path. That function explicitly recommends increasing Driver Wake-Up Delay or moving RSX FIFO Fetch Accuracy to the next mode. The GTA IV profile now writes `Ordered & Atomic` and `20` µs to the selected game's settings scope using the core's supported settings API, and reads both values back. This is a targeted mitigation, not a native FIFO algorithm rewrite or a guarantee that GTA IV will run. The bundled ARM64 engine remains prebuilt; changes to GPU fences, command scheduling, live queue watchdogs or queue-reset logic still require a native-core rebuild and game-specific validation. Dismissing the banner never pretends to recover the game.

The log export is user-initiated and stays on-device until the user explicitly shares it. The logcat capture is limited to TouchStation's own process and may be unavailable on some Android builds; the diagnostic snapshot is still included and the export reports the limitation.


The error banner preserves the complete native error text (up to 4,000 characters), not only its first line, so the engine's suggested setting names and next enum value remain visible. The error remains saved in the bounded local history after swipe dismissal.


## Finale Android reliability layer

The Finale source patcher now generates a dedicated `com.armsx2.reliability.TouchStationFinaleReliability` module and initializes it from the Android Application:

- Bounded diagnostic event writer (512 KiB active log with one rotated copy), Java/Kotlin crash reports (latest five), previous-crash marker and activity lifecycle tracking.
- Guarded-operation helper, app PSS trend sampling, available RAM, free app storage, thermal snapshot and physical input-device enumeration.
- Startup self-tests for settings JSON round-trip, app-cache read/write, native-library directory visibility and arm64-v8a ABI presence.
- Safe-mode state, settings range/serialization validation, explicit Global/per-game settings rollback checkpoints and user-confirmed restore via the existing apply callback.
- Game-source readability checks, user-triggered SHA-256 with a 256 MiB limit, and a bounded app-cache inventory.
- Diagnostic export combines the existing stdout/stderr session log, app-process logcat, Finale event history and the latest Java/Kotlin crash report.

These are Android-side reliability aids. The app does not automatically restart a failed game or reset native worker threads. The pinned prebuilt native engine exposes no trustworthy PPU/SPU task counters, RSX FIFO queue depth, GPU fences, shader-cache internals or safe native FIFO recovery API. These remain marked unavailable and require native-source changes, rebuilt ARM64 libraries and real-device testing.

The OS owns Bluetooth pairing/reconnection; TouchStation can enumerate connected physical input devices but cannot force a reconnect. PSS trends are diagnostic hints, not proof of a memory leak. The app-cache inventory does not inspect private shader-cache internals or delete files. Large game images are not hashed automatically.


## Finale runtime guard and native health checks

The Android-side reliability layer now has a separate `TouchStationFinaleRuntimeGuard` module:

- A thread-safe keyed operation gate prevents duplicate compatibility refreshes, game-source integrity jobs and diagnostic exports from running concurrently.
- A daemon watchdog records when one of those operations exceeds its configured deadline. It reports elapsed work and keeps the operation visible in the diagnostics panel; it does not cancel, interrupt or reset any emulator/native worker.
- Native health checks verify that the packaged `libarmsx3-core.so` and `libarmsx3-jni.so` files are present and non-empty, and display the existing engine/runtime readiness flags. This checks packaging visibility, not full native correctness.
- Memory pressure is classified from Android's `ActivityManager.MemoryInfo` low-memory flag and OS threshold. It is a device-pressure warning, not a guarantee of emulator stability.
- The current active-operation list, native-library health and memory-pressure reading are included in the Finale diagnostics and export report.

The watchdog protects Android-managed operations; it is not a PPU/SPU execution watchdog. Native PPU task progress, SPU worker validation, RSX command-stream validation, GPU-fence synchronization and private shader-cache validation still require instrumentation in a rebuilt native core. The existing PSS trend remains a diagnostic trend only and must not be described as a confirmed memory-leak detector.


## TouchStation Extra — 30-feature stability and diagnostics update

TouchStation Extra builds on the previous releases and adds an Android-side diagnostics panel. The 30 entries below are represented in the Extra UI. Where the pinned native bridge does not provide a required hook, the UI explicitly reports N/A; it does not invent counters or claim native recovery.

### PPU and SPU diagnostics

1. **PPU execution diagnostics** — identifies live instruction counters and execution state as unavailable when the native bridge does not export them.
2. **PPU module validator** — verifies that the packaged core and JNI libraries are present; native module-registry validation remains unavailable.
3. **PPU thread-state monitor** — reports Android/JVM thread counts and states, not native PPU worker identities.
4. **PPU exception reporter** — combines the bounded game-error history and available Android crash evidence.
5. **PPU cache integrity** — inspects known app/code cache directories read-only; private native PPU cache internals remain unavailable.
6. **SPU task diagnostics** — shows an explicit unavailable state for native task IDs and queue contents.
7. **SPU workload monitor** — displays the actual configured SPU decoder, block size and preferred thread count.
8. **SPU timeout reporting** — displays the Android operation watchdog; native SPU task timeouts remain unavailable.
9. **SPU module validation** — reports native module-registry validation as unavailable.
10. **Native engine self-test** — combines the existing startup self-tests, native-library presence, engine initialization and runtime readiness.

### RSX and graphics diagnostics

11. **RSX command diagnostics** — surfaces available FIFO error history; native command-stream traces remain unavailable.
12. **FIFO queue health** — reports recorded FIFO errors and explicitly marks live queue depth/progress unavailable.
13. **GPU synchronization diagnostics** — GPU-fence and synchronization counters remain unavailable without native instrumentation.
14. **Shader compilation tracker** — reports that live shader job counters are unavailable and shows known app cache evidence.
15. **Shader cache recovery** — offers cleanup of only an orphaned TouchStation logcat temporary file; it does not clear emulator shader caches.
16. **Vulkan capability checker** — lists Vulkan features advertised by Android PackageManager; physical-device extension details remain unavailable.
17. **Graphics driver report** — reports Android hardware and required GLES information; active native driver vendor/renderer details remain unavailable.
18. **Frame pacing monitor** — reports display refresh rate and directs users to the existing native in-game FPS/frametime overlay.
19. **Resolution scaling profiles** — shows the current Android output scaler and GPU profile without claiming to change internal RSX resolution.
20. **Graphics settings rollback** — exposes the existing user-controlled settings checkpoint information.

### Stability, recovery and storage

21. **Game launch preflight** — combines game selection, engine initialization and native runtime readiness.
22. **Boot failure classifier** — uses the existing plain-language game-error classifier.
23. **Crash-loop protection** — counts uncaught app crashes in a rolling ten-minute window and enables the existing safe mode after three or more.
24. **Session recovery report** — displays the settings checkpoint and lifecycle status.
25. **Memory allocation diagnostics** — reports Android available RAM and process PSS; native allocation breakdowns remain unavailable.
26. **Cache cleanup manager** — deletes only an orphaned app-owned `TouchStation-logcat.tmp` file after a user action.
27. **Storage health warnings** — warns below 3 GiB app-private free space and marks below 1 GiB critical.
28. **Android lifecycle protection** — surfaces the existing Android activity lifecycle tracking.
29. **Automated regression suite** — adds dedicated patcher tests to the Extra GitHub Actions workflow; this is not a native emulator test suite.
30. **Per-game stability profiles** — applies a conservative existing-settings preset only when a game is selected, Game scope is active, safe mode is off and settings read-back succeeds.

### Native-core boundary

The pinned ARM64 engine remains a prebuilt upstream binary. TouchStation Extra does not rebuild or modify native PPU, SPU, RSX, Vulkan or GPU scheduling code. Consequently, live PPU execution/module/exception counters, SPU task queues and worker states, RSX command-stream validation, FIFO queue depth, GPU fences, shader compilation counters, physical GPU utilization and native memory allocation traces remain N/A until the native core exports those APIs and matching ARM64 libraries are rebuilt and tested.

The watchdog in this release monitors Android-managed operations only. It does not kill or reset native threads. Crash-loop protection records uncaught application crashes and enables frontend safe mode on a subsequent launch; it cannot guarantee recovery from every native process termination. Cache cleanup is narrowly limited to a TouchStation-owned temporary log file and never deletes game files, firmware, save data or emulator shader caches.

The Extra build uses version name **TouchStation Extra** and version code **1300**. The APK and corresponding-source archive remain separate downloads, and existing upstream notices, licensing and corresponding-source obligations remain intact.

## TouchStation Extra — advanced 50-feature suite

The Advanced Suite adds the following product-facing feature areas. Android-side features are implemented where the app APIs support them. Native-only telemetry is explicitly N/A.

### 1–10: stability and crash prevention

1. **Pre-launch crash-risk advisory** — checks low memory, free app storage, thermal severity, crash-loop state and native-runtime readiness. It is a checklist, not a crash probability.
2. **Application crash detection** — reads Android historical process-exit records on Android 11+. These do not prove that a PS3 guest game crashed.
3. **Crash reason analyzer** — classifies Android-reported ANR, Java/Kotlin crash, native app crash, low-memory termination and other exit reasons.
4. **Safe game boot** — offers a conservative existing-settings profile for explicit application while Game settings scope is active.
5. **Configuration recovery** — restores a matching Global or per-game checkpoint through the settings apply/read-back path.
6. **Game-session watchdog evidence** — displays the Android operation watchdog; it does not monitor or reset native game threads.
7. **Memory-pressure protection** — shows Android available memory and low-memory warnings where available.
8. **Thermal protection** — reports Android thermal severity, not measured SoC temperature.
9. **Per-game failure history** — stores the latest 30 user-entered boot, stable-session, crash or freeze observations per game and handset.
10. **Stability observation index** — summarizes recorded stable-session and failure observations; it is not a benchmark or universal compatibility score.

### 11–20: compatibility

11. **Expanded compatibility lookup** — reuses the official desktop RPCS3 database and exact PS3 title-ID matching.
12. **Compatibility confidence** — separates desktop-only references from user-entered handset observations and unknown/unverified results.
13. **Device-specific game profile** — saves supported settings per handset fingerprint and game title ID.
14. **Compatibility regression hint** — flags a user-recorded failure after an earlier gameplay/stable-session observation.
15. **Boot-stage tracker** — lets users record boot start, menu, gameplay, stable session, crash or freeze; stages are manual observations because guest boot callbacks are not exposed.
16. **Known-issue matching** — reuses the existing plain-language game-error classifier.
17. **Per-game recommendations** — calculates a conservative PPU thread suggestion from Android CPU/RAM information, not a game benchmark.
18. **Compatibility report generator** — exports device, title ID, test observations, error history and configuration through Android's share sheet.
19. **Controller compatibility notes** — lists physical gamepads and saves a local detected-controller note; it does not test every button automatically.
20. **Firmware/game-update warnings** — identifies that installed PUP and game-update versions are not exposed by the bridge and must be checked manually.

### 21–26: PPU

21. **PPU execution profiler surface** — shows configured PPU decoder/threads; native instruction counters remain N/A.
22. **PPU LLVM monitor** — shows configured compile-thread count; live compilation progress remains N/A.
23. **Interpreter fallback status** — shows the configured decoder and marks automatic native fallback unavailable.
24. **PPU thread advisor** — recommends a conservative count from Android CPU cores and available memory.
25. **PPU module diagnostics** — reports engine initialization; native module registry/load traces remain N/A.
26. **PPU cache validation boundary** — identifies known read-only cache inventory and private native PPU-cache integrity as unavailable.

### 27–32: SPU

27. **SPU workload distribution surface** — shows configured SPU decoder/preferred threads; native worker distribution remains N/A.
28. **SPU decoder comparison** — identifies the current decoder without claiming unmeasured game benchmarks.
29. **SPU starvation detector status** — native worker scheduling telemetry remains N/A.
30. **SPU compilation recovery status** — native retry/fallback APIs are not exposed; preserve caches and export diagnostics.
31. **SPU cache management status** — shows the cache option; private native cache paths remain unavailable.
32. **SPU performance advisor** — recommends Safe block size for stability and displays preferred-thread configuration.

### 33–40: RSX and graphics

33. **RSX command diagnostics** — combines recorded FIFO errors with N/A for live native command traces.
34. **FIFO deadlock diagnostics** — reuses the existing FIFO error explanation and next-step guidance.
35. **RSX synchronization monitor** — native GPU-fence/synchronization counters remain N/A.
36. **Shader failure recovery guidance** — recommends preserving caches and exporting logs; native shader retry remains unavailable.
37. **Shader cache version status** — private native shader-cache version metadata remains N/A.
38. **GPU driver compatibility fingerprint** — keys profiles by handset/hardware/ABI; exact GPU driver version is N/A without a native query.
39. **Dynamic output-scale recommendation** — suggests Android presentation scaling using available RAM/thermal severity; it does not change internal RSX resolution.
40. **Frame-pacing guidance** — displays Android refresh rate and directs users to the native in-game FPS/frametime overlay.

### 41–50: app settings and user experience

41. **Searchable settings guide** — filters a glossary of documented PPU, SPU, shader, output and graphics settings.
42. **Three-slot settings profiles** — saves/loads JSON profiles per device and Global/per-game scope, with validation and apply/read-back checks.
43. **Confirmed settings reset** — restores upstream Settings() defaults for the active scope after confirmation; it does not delete games, firmware or saves.
44. **Settings change history** — records changed top-level settings fields, timestamp, scope and game ID through the central saveSettings path.
45. **Advanced setting descriptions** — explains PPU, SPU, shader, MSAA, output-scaler, GPU-profile and FIFO options.
46. **Automatic device detection** — reports Android manufacturer/model, hardware and supported ABI.
47. **Battery/balanced/performance profiles** — applies user-selected emulator settings profiles and verifies supported values. These do not overclock the phone or guarantee higher FPS.
48. **Keep-screen-on control** — keeps the display awake while TouchStation is in use; it does not create a background emulation service.
49. **Storage manager** — reports bounded app cache/code-cache inventory and app-private free space; it does not recurse through filesDir or game/firmware folders.
50. **Advanced diagnostics dashboard** — combines compatibility, game observations, controller notes, process exits, memory, thermal, storage and settings history in a shareable report.

### Evidence and native-core limits

Per-game boot stages, crash/freeze observations and controller notes are user-entered, device-local evidence. The stability index summarizes these entries; it is not an automatic compatibility rating. Android process-exit history is application-wide and cannot prove that a guest game failed.

The pinned ARM64 core remains a prebuilt upstream binary. Native PPU instruction profiling/fallback/module traces, SPU worker distribution/starvation/retry, RSX command-stream validation, live FIFO queue depth, GPU fences, private shader-cache metadata, exact GPU driver counters and physical GPU utilization remain unavailable until the native core exports those APIs and matching ARM64 libraries are rebuilt and tested.

Settings profiles are device/scope separated. Applying a preset is user initiated, goes through the existing settings callback and is only reported as successful after supported read-back checks. Keep-screen-on is an Android window flag, not a background-service control. The storage scan is bounded and read-only.
