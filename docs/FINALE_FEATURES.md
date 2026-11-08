# TouchStation Version Finale — feature map

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
42. **Crash and launch report export** — prepares a shareable diagnostic report.
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
