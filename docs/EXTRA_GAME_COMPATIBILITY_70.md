# TouchStation Extra — 70-feature GTA IV and all-game expansion

This is the implementation map for the 70-feature expansion. The new Game Compatibility Lab adds Android-side tools and structured observations. Existing Extra suites already supply settings profiles, per-game notes, device telemetry, compatibility references, rollback, shutdown diagnostics, and app-side regression checks.

Status labels:
- **APP IMPLEMENTED** — available through the Android app or its settings/diagnostics.
- **EXISTING / EXTENDED** — an earlier Extra feature already supplies the capability; this expansion extends its evidence or UI.
- **NATIVE CORE REQUIRED** — cannot honestly be implemented by an Android settings panel. It needs matching PPU/SPU/RSX/JNI source changes, rebuilt ARM64 libraries, and device testing.
- **DEVICE TEST REQUIRED** — the UI can record the test, but the outcome must be observed on real hardware.

## 1–10 · PPU

1. Adaptive PPU recompiler — NATIVE CORE REQUIRED; current bridge does not expose backend-selection control.
2. PPU LLVM compilation queue — configured thread count is shown; live queue state is NATIVE CORE REQUIRED.
3. Persistent PPU cache — existing upstream cache remains in use; private cache lifecycle control is NATIVE CORE REQUIRED.
4. PPU cache validation — existing read-only evidence only; native cache integrity API is NATIVE CORE REQUIRED.
5. PPU compilation fallback — NATIVE CORE REQUIRED.
6. PPU thread scheduler — configured thread guidance exists; adaptive guest scheduler is NATIVE CORE REQUIRED.
7. PPU deadlock detection — guest-thread liveness callbacks are NATIVE CORE REQUIRED.
8. PPU instruction diagnostics — instruction counters and failing-opcode trace are NATIVE CORE REQUIRED.
9. PPU performance telemetry — configured values are visible; live PPU telemetry is NATIVE CORE REQUIRED.
10. Per-game PPU profiles — EXISTING / EXTENDED with device-specific profile snapshots and comparison.

## 11–20 · SPU

11. Adaptive SPU worker scheduler — NATIVE CORE REQUIRED.
12. SPU workload balancing — NATIVE CORE REQUIRED.
13. SPU queue monitoring — NATIVE CORE REQUIRED.
14. SPU LLVM cache improvements — existing cache configuration; internal cache work is NATIVE CORE REQUIRED.
15. SPU decoder fallback — NATIVE CORE REQUIRED.
16. SPU starvation detection — NATIVE CORE REQUIRED.
17. SPU synchronization improvements — NATIVE CORE REQUIRED.
18. SPU exception recovery — NATIVE CORE REQUIRED.
19. Per-game SPU configuration — EXISTING / EXTENDED through per-game settings snapshots.
20. SPU performance telemetry — configured decoder/thread values only; live telemetry is NATIVE CORE REQUIRED.

## 21–30 · RSX and graphics

21. Adaptive RSX renderer selection — NATIVE CORE REQUIRED.
22. Vulkan capability detection — EXISTING Android-reported capability panel; actual driver feature validation requires the native/graphics bridge.
23. RSX FIFO diagnostics — existing error history; live command queue progress is NATIVE CORE REQUIRED.
24. RSX command validation — NATIVE CORE REQUIRED.
25. GPU fence monitoring — NATIVE CORE REQUIRED.
26. Shader cache management — existing read-only visibility where exposed; native cache controls are NATIVE CORE REQUIRED.
27. Shader compilation scheduling — NATIVE CORE REQUIRED.
28. Texture memory budgeting — NATIVE CORE REQUIRED for guest RSX allocations.
29. Dynamic resolution scaling — Android presentation guidance exists; live guest RSX resolution control is NATIVE CORE REQUIRED.
30. Graphics fallback modes — NATIVE CORE REQUIRED unless supported by an exposed renderer setting.

## 31–40 · Android stability and device-aware configuration

31. Device-aware conservative profile — APP IMPLEMENTED; uses reported RAM, CPU core count and thermal status.
32. Thermal-aware guidance — EXISTING / EXTENDED using Android thermal severity; it does not force OS throttling.
33. Low-memory readiness warning — EXISTING / EXTENDED using Android-reported available RAM and app PSS.
34. Memory-pressure evidence — APP IMPLEMENTED in test-session snapshots; it is not a native leak detector.
35. Android lifecycle and shutdown protection — EXISTING from the Extra shutdown/runtime guards.
36. Shutdown state verification — EXISTING; native shutdown completion is recorded separately from guest-game status.
37. App-process exit classification — EXISTING; Android process exits are not treated as guest crashes.
38. Game freeze detection — DEVICE TEST REQUIRED; user records the observed freeze because guest progress callbacks are not exposed.
39. Diagnostic report sharing — APP IMPLEMENTED with game ID, device and configuration fingerprints.
40. Safe profile rollback — EXISTING through settings rollback and read-back verification.

## 41–50 · Universal compatibility evidence

41. Game serial recognition — EXISTING via the current game's title ID/settings key.
42. Per-game settings — EXISTING / EXTENDED with device-specific saved snapshots.
43. Repeatable test-session record — APP IMPLEMENTED.
44. Device and settings fingerprint per attempt — APP IMPLEMENTED.
45. Same-settings regression comparison — APP IMPLEMENTED; labels a possible pattern, not a proven cause.
46. Game update notes — EXISTING user-entered metadata; installed patch version is not automatically verified.
47. Firmware notes — EXISTING user-entered metadata; installed firmware contents/version are not automatically verified.
48. Known-issue notes — EXISTING per-game notes and error guidance.
49. Game-file header inspection — APP IMPLEMENTED as a bounded read-only signature check; not a full image or package validator.
50. Test history export — APP IMPLEMENTED via Android share sheet.

## 51–60 · GTA IV / BLES00229

51. Exact BLES00229 detection — APP IMPLEMENTED; the GTA IV profile appears only for this title ID.
52. Conservative GTA IV starting profile — APP IMPLEMENTED; one PPU/LLVM thread, conservative SPU settings, no MSAA and precompile disabled under constrained memory/thermal conditions.
53. Per-game scope guard — APP IMPLEMENTED; the profile cannot be applied from the global settings scope.
54. Repeatable GTA IV test session — APP IMPLEMENTED; user starts the record before launching the game.
55. Boot and gameplay stage observations — APP IMPLEMENTED as manual observations, not automatic guest callbacks.
56. Stable/failed/inconclusive results — APP IMPLEMENTED as user-selected outcomes, not emulator-certified states.
57. Interrupted-session recovery — APP IMPLEMENTED; unknown interruption is not mislabeled as a crash.
58. Device and settings capture — APP IMPLEMENTED per observation.
59. Same-configuration regression hint — APP IMPLEMENTED when the same settings fingerprint has prior stable and later failed observations.
60. GTA IV report export — APP IMPLEMENTED.

## 61–70 · Other PS3 games

61. Generic per-game repeatable tests — APP IMPLEMENTED for any selected game with an ID.
62. Per-game configuration save/restore — EXISTING / EXTENDED.
63. Current-versus-saved settings comparison — APP IMPLEMENTED.
64. Device-aware profile recommendation — APP IMPLEMENTED; applied only after explicit user action and read-back check.
65. Game-specific compatibility history — APP IMPLEMENTED per device and game ID.
66. Game-file signature preflight — APP IMPLEMENTED for common PKG/SELF and ISO/UDF markers; unknown headers remain inconclusive.
67. Verified save-data backup — EXISTING, streaming copy with SHA-256 re-read verification.
68. Controller diagnostics — EXISTING Android device and digital key-event checks; native analog calibration remains unavailable.
69. Game-specific diagnostic export — APP IMPLEMENTED.
70. Automated source regression checks — APP IMPLEMENTED in CI; they do not replace real gameplay tests.

## Native-engine boundary

The build pipeline uses pinned prebuilt ARM64 native emulator libraries. This expansion does not claim to rebuild or modify native PPU, SPU, RSX, Vulkan, GPU scheduling, guest-thread synchronization, or guest crash callbacks. Those items are explicitly **NATIVE CORE REQUIRED** above. A successful Android build verifies compilation and packaging only; GTA IV and other games still require real device testing, and no profile guarantees playability or stable frame rate.
