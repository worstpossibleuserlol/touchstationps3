# TouchStation Extra - Compatibility

This compatibility expansion is split into two tracks: 20 universal features for other PS3 games, and 20 GTA IV-specific features for BLES00229. The Android-side Compatibility Center is an evidence and settings layer. A setting, preflight result, or user-entered status is not proof that a PS3 game is playable.

Status meanings:
- **APP IMPLEMENTED** — implemented in the Android app in this expansion.
- **EXISTING / EXTENDED** — supplied by existing TouchStation Extra modules or connected to this new center.
- **DEVICE TEST REQUIRED** — the app can configure or record the test, but the result must be observed on the handset.
- **NATIVE CORE REQUIRED** — needs matching PPU/SPU/RSX/JNI source changes and rebuilt ARM64 native libraries; the current workflow packages a pinned prebuilt core.

## 1–20 · Universal / other PS3 games

1. **Universal game-ID detection — EXISTING / EXTENDED.** Uses the active game's title ID/settings key to scope profiles and records.
2. **Per-game compatibility records — APP IMPLEMENTED.** Stores a local user-entered status and notes under a hashed game ID.
3. **Per-game settings snapshots — EXISTING / EXTENDED.** Reuses the Game Compatibility Lab's save, restore and compare tools.
4. **Validated universal profile — APP IMPLEMENTED.** Adds a conservative profile using only settings already exposed by the current wrapper.
5. **Low-memory profile — APP IMPLEMENTED.** Selects conservative worker counts and uses the existing RAM/thermal precompile guard.
6. **PPU recompiler recovery — NATIVE CORE REQUIRED.** Requires native compiler error handling and a tested fallback path.
7. **SPU workload scheduler — NATIVE CORE REQUIRED.** Requires native worker-pool scheduling and workload telemetry.
8. **SPU accuracy profile — DEVICE TEST REQUIRED.** The app can select the exposed decoder setting; accuracy and speed need per-game validation.
9. **PPU/SPU cache integrity manager — NATIVE CORE REQUIRED.** Android cannot safely validate internal guest-code cache entries without native cache APIs.
10. **Thread-stall diagnostics — NATIVE CORE REQUIRED.** Requires guest-thread liveness and lock/wait telemetry from the core.
11. **Vulkan capability preflight — APP IMPLEMENTED.** Reports Android's advertised Vulkan hardware-level feature, not full device extensions or runtime renderer success.
12. **Asynchronous shader compilation — NATIVE CORE REQUIRED.** Requires renderer shader scheduling changes.
13. **Shader-cache verification and recovery — NATIVE CORE REQUIRED.** Requires native shader-cache metadata and invalidation APIs.
14. **RSX synchronization diagnostics — NATIVE CORE REQUIRED.** Requires native RSX queue/fence telemetry and synchronization fixes.
15. **Render-target lifetime protection — NATIVE CORE REQUIRED.** Requires native RSX resource ownership changes.
16. **Memory-pressure monitor — APP IMPLEMENTED.** Reports Android available RAM, app PSS and app-private free storage.
17. **Texture streaming manager — NATIVE CORE REQUIRED.** Requires guest texture upload and eviction controls in the RSX backend.
18. **Audio timing diagnostics — NATIVE CORE REQUIRED.** Requires guest audio buffer/clock telemetry not exported by the current bridge.
19. **Save-state integrity validation — NATIVE CORE REQUIRED.** Requires the emulator's save-state format and checksum/version APIs; document copying alone is not save-state validation.
20. **Compatibility preflight report — APP IMPLEMENTED.** Exports game ID, device/ABI, native-library presence, Vulkan feature flag, RAM, storage, thermal status and settings validation.

## 21–40 · GTA IV / BLES00229

21. **Exact BLES00229 profile gate — APP IMPLEMENTED.** The GTA IV control is shown only when the detected game serial exactly matches BLES00229.
22. **Conservative GTA IV profile — APP IMPLEMENTED.** Uses one PPU thread, exposed LLVM PPU/SPU settings, no MSAA and the existing RAM/thermal precompile guard. It is a test starting point.
23. **PPU compilation failure recovery — NATIVE CORE REQUIRED.** Needs native error callbacks, compiler-state cleanup and a validated retry path.
24. **PPU cache integrity — NATIVE CORE REQUIRED.** Needs native cache entry validation and safe rebuild support.
25. **PPU instruction compatibility diagnostics — NATIVE CORE REQUIRED.** Needs failing guest instruction/opcode and module diagnostics.
26. **PPU thread synchronization repair — NATIVE CORE REQUIRED.** Needs guest worker wait/lock tracing and native synchronization changes.
27. **PPU memory-order validation — NATIVE CORE REQUIRED.** Needs native emulator memory-order tests and ARM64-specific fixes.
28. **SPU XFloat profile evidence — DEVICE TEST REQUIRED.** The exposed profile selects the current conservative XFloat setting; whether it fixes GTA IV physics/collision behavior must be tested on the matching executable.
29. **Collision-job compatibility patch — NATIVE CORE REQUIRED.** Any patch must be validated against the exact BLES00229 executable/build; no executable-specific patch is applied by this Android module.
30. **SPU workload scheduling — NATIVE CORE REQUIRED.** Needs native SPU worker scheduling changes and live queue/starvation counters.
31. **SPU cache validation — NATIVE CORE REQUIRED.** Needs native cache metadata and corruption recovery.
32. **SPU exception isolation — NATIVE CORE REQUIRED.** Needs native worker exception boundaries and safe guest-job failure reporting.
33. **Multithreaded RSX optimization — NATIVE CORE REQUIRED.** Needs renderer/core source changes and GTA IV-specific regression testing.
34. **RSX synchronization repair — NATIVE CORE REQUIRED.** Needs native command queue and fence instrumentation.
35. **Render-target lifetime validation — NATIVE CORE REQUIRED.** Needs native RSX resource lifetime tracking.
36. **Texture-cache validation — NATIVE CORE REQUIRED.** Needs native texture-cache keys, generation tracking and recovery.
37. **Shader compilation recovery — NATIVE CORE REQUIRED.** Needs native shader compiler diagnostics and retry/invalidation support.
38. **Mali/Vulkan readiness diagnostics — APP IMPLEMENTED.** Reports ARM64 and Android's Vulkan hardware-level feature flag; detailed Mali driver extensions remain unavailable.
39. **Memory/thermal profile guidance — APP IMPLEMENTED.** Reports RAM, app PSS and Android thermal status; it does not force native scheduling or dynamic resolution.
40. **GTA IV failure report — APP IMPLEMENTED.** Exports Android/device/settings evidence; native PPU/SPU/RSX guest-failure callbacks remain unavailable.

## Native-core boundary

The current build pipeline checks out the pinned ARMSX3 Android source but packages the upstream prebuilt ARM64 native core/JNI libraries. The new Compatibility Center does not patch or rebuild the native PPU, SPU, RSX, shader compiler, guest audio engine or Mali/Vulkan renderer internals. Those items are **not claimed as fixed**. Implementing them requires matching native sources, native tests, a rebuilt ARM64 library, successful package verification, and device testing with representative games, including BLES00229.

A successful Android build only verifies compilation and packaging. It does not demonstrate that GTA IV or any other game boots, reaches gameplay, renders correctly, maintains performance, or exits safely.
