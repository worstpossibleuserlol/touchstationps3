# TouchStation Extra – Compatibility (50 features)

This release tracks the exact 50 compatibility features requested for GTA IV and other PS3 games. It adds an in-app implementation map, puts the statuses into diagnostic reports, and keeps native-engine work separate from Android-side evidence.

**Status meanings**
- **APP IMPLEMENTED** — the Android wrapper implements the stated, bounded function.
- **EXISTING / EXTENDED** — a related TouchStation feature already exists and is surfaced or reused.
- **APP LIMITED** — only the stated Android-side evidence or limited file check exists; the full feature is not implemented.
- **DEVICE TEST REQUIRED** — an exposed setting exists, but its effect has not been established on a real game/device.
- **NATIVE CORE REQUIRED** — requires PPU/SPU/RSX/renderer/audio/save-state source changes and rebuilt native ARM64 libraries.

## 1–20 · PPU / SPU / RSX / GTA IV foundations

1. **Advanced PPU instruction compatibility — NATIVE CORE REQUIRED.** Requires guest opcode coverage, instruction tests and matching native PPU implementation changes.
2. **PPU recompilation recovery — NATIVE CORE REQUIRED.** Requires native recompiler error handling, cleanup and a verified fallback path.
3. **PPU cache integrity checker — NATIVE CORE REQUIRED.** Requires cache metadata, checksums and safe native cache rebuild APIs.
4. **PPU thread synchronization fixes — NATIVE CORE REQUIRED.** Requires guest-thread lock, wait and scheduling fixes in the native core.
5. **PPU memory-order validation — NATIVE CORE REQUIRED.** Requires native memory-order tests and ARM64-specific emulator fixes.
6. **SPU task scheduler — NATIVE CORE REQUIRED.** Requires native SPU worker-pool scheduling and workload telemetry.
7. **SPU exception isolation — NATIVE CORE REQUIRED.** Requires native worker exception boundaries and guest-job failure handling.
8. **SPU cache recovery — NATIVE CORE REQUIRED.** Requires native SPU cache validation and recovery APIs.
9. **SPU timing diagnostics — NATIVE CORE REQUIRED.** Requires guest SPU timing counters exported by the native bridge.
10. **SPU accuracy compatibility profile — DEVICE TEST REQUIRED.** The app can select exposed SPU decoder settings; per-game accuracy and performance must be tested.
11. **RSX command queue diagnostics — NATIVE CORE REQUIRED.** Requires native RSX queue instrumentation and exported diagnostics.
12. **RSX synchronization repair — NATIVE CORE REQUIRED.** Requires native command/fence synchronization changes.
13. **Shader compilation recovery — NATIVE CORE REQUIRED.** Requires shader compiler error reporting, cache invalidation and retry support in the renderer.
14. **Shader cache validation — NATIVE CORE REQUIRED.** Requires native shader-cache metadata and safe rebuild support.
15. **Render-target lifetime protection — NATIVE CORE REQUIRED.** Requires native RSX resource ownership and render-target lifetime tracking.
16. **GTA IV memory-pressure manager — APP LIMITED.** The app reports available RAM, app PSS, storage and thermal status; it cannot control the native guest allocator.
17. **Texture streaming diagnostics — NATIVE CORE REQUIRED.** Requires native texture upload, residency and eviction telemetry.
18. **Audio synchronization diagnostics — NATIVE CORE REQUIRED.** Requires guest audio clock and buffer timing callbacks.
19. **Save-state compatibility validation — NATIVE CORE REQUIRED.** Requires the emulator save-state schema, version and checksum APIs.
20. **GTA IV crash-stage reporting — APP IMPLEMENTED.** The app records the user-reported failure stage and captures device/settings evidence; it does not receive native guest crash callbacks.

## 21–50 · Expanded game compatibility

21. **PPU fallback execution engine — NATIVE CORE REQUIRED.** Requires a second native PPU execution path with correctness tests.
22. **PPU cache version management — NATIVE CORE REQUIRED.** Requires native cache format/version metadata and migration or invalidation logic.
23. **SPU workload balancing — NATIVE CORE REQUIRED.** Requires native worker queue metrics and adaptive dispatch.
24. **SPU DMA compatibility improvements — NATIVE CORE REQUIRED.** Requires native SPU DMA semantics and regression tests.
25. **SPU event handling improvements — NATIVE CORE REQUIRED.** Requires native SPU event and signal synchronization changes.
26. **RSX command validation — NATIVE CORE REQUIRED.** Requires native command-stream validation and error reporting.
27. **RSX memory synchronization — NATIVE CORE REQUIRED.** Requires native guest/host graphics memory synchronization fixes.
28. **GPU buffer management — NATIVE CORE REQUIRED.** Requires renderer-side GPU buffer allocation, reuse and lifetime changes.
29. **Vulkan compatibility layer improvements — NATIVE CORE REQUIRED.** Requires renderer/Vulkan backend changes; Android's Vulkan feature flag alone is not a capability query.
30. **OpenGL fallback support — NATIVE CORE REQUIRED.** Requires an OpenGL renderer backend and per-device validation.
31. **Shader precision compatibility — NATIVE CORE REQUIRED.** Requires renderer shader translation and precision handling changes.
32. **Shader compilation scheduling — NATIVE CORE REQUIRED.** Requires native asynchronous compilation scheduling and synchronization.
33. **Pipeline cache recovery — NATIVE CORE REQUIRED.** Requires native pipeline-cache versioning, validation and rebuild support.
34. **Frame pacing improvements — NATIVE CORE REQUIRED.** Requires renderer timing and presentation scheduling changes.
35. **Resolution scaling profiles — EXISTING / EXTENDED.** Existing TouchStation output-scaling controls can be configured; best results remain device/game dependent.
36. **Texture format compatibility — NATIVE CORE REQUIRED.** Requires native RSX texture format decoding and conversion coverage.
37. **Texture cache recovery — NATIVE CORE REQUIRED.** Requires native texture-cache validation, generation tracking and rebuild support.
38. **Audio buffer management — NATIVE CORE REQUIRED.** Requires native guest audio buffer and clock controls.
39. **Audio format compatibility — NATIVE CORE REQUIRED.** Requires native guest audio format conversion and compatibility tests.
40. **Disc image integrity checking — APP LIMITED.** The existing app performs bounded read-only file signature checks; this is not a full image integrity check.
41. **Game update compatibility checking — NATIVE CORE REQUIRED.** Reliable update compatibility needs title/build metadata and native mount/load validation.
42. **DLC compatibility validation — NATIVE CORE REQUIRED.** Requires native content mounting and title/DLC compatibility validation.
43. **Per-game configuration storage — EXISTING / EXTENDED.** Existing game-scoped settings and local records are retained and surfaced by Compatibility Center.
44. **Automatic configuration backup — EXISTING / EXTENDED.** Existing settings backup/restore tools can preserve configurations; a backup is not a game compatibility fix.
45. **Crash recovery reporting — EXISTING / EXTENDED.** Existing Android launch/error reporting is reused; detailed guest crash reasons require native callbacks.
46. **Loading-stage diagnostics — EXISTING / EXTENDED.** Existing boot timeline and user-entered failure stage record the last observable stage.
47. **Memory leak detection — NATIVE CORE REQUIRED.** Android PSS sampling is not a leak detector; native allocation ownership and leak instrumentation are required.
48. **Thermal performance monitoring — APP IMPLEMENTED.** The app reports Android thermal status and refreshes device readiness evidence.
49. **Android background-process protection — APP LIMITED.** The app can report Android state but cannot guarantee that the OS will not suspend or terminate it.
50. **Compatibility test database — APP LIMITED.** The app keeps local per-game records; a verified shared device/game database is not implemented.

## Native-core boundary

The current build workflow packages a pinned prebuilt ARM64 PS3 engine. It does not compile or patch the native PPU, SPU, RSX, Vulkan/OpenGL renderer, shader compiler, guest audio engine or save-state internals. Therefore every **NATIVE CORE REQUIRED** item is tracked but is not claimed as implemented by this Android-only update.

The app-side changes in this update are: the complete 50-item in-app status map; explicit status counts and explanations in exported compatibility reports; retained per-game profile/record/preflight tools; and a corrected digital-input diagnostic that no longer depends on a Compose API absent from the pinned source version.

A successful Android build only verifies compilation and packaging. It does not prove GTA IV or another title boots, reaches gameplay, renders correctly, performs acceptably, or shuts down safely. Actual game compatibility still requires device testing with the user's legally obtained game files and suitable firmware.
