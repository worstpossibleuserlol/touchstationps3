# TouchStation Extra — 100-feature implementation map

This document maps the requested 100-feature plan to existing Extra capabilities, the new app-side companion module, or an explicit native-core limitation. It is an implementation map, not a claim that every low-level emulator API exists.

## 1–10 · Game compatibility

1. Per-game compatibility database — existing official RPCS3 index plus device-local observations.
2. Automatic game identification — existing current-game serial/settings-key lookup.
3. Compatibility status — official desktop status plus separately labelled handset observations.
4. Known-issues database — user-entered per-game known-issue notes.
5. Game-specific recommendations — existing per-game profiles and safe profile controls.
6. Compatibility notes — user-entered per-game notes.
7. Game update information — per-game manual update/version note; the pinned bridge does not expose installed update metadata.
8. Firmware requirement checker — per-game manual firmware requirement note; installed firmware version is not exposed by the current bridge.
9. Game boot failure history — existing user-recorded boot/crash/freeze observations.
10. Compatibility changes between versions — local status-change history with timestamps when the user updates the status.

## 11–20 · PPU

11. PPU configuration profiles — existing per-game/global settings profiles.
12. PPU thread guidance — existing conservative thread advisor.
13. PPU module-load diagnostics — engine readiness only; native module trace is N/A.
14. PPU error reporting — existing diagnostics/error export; structured native PPU exception counters are N/A.
15. PPU settings validation — existing settings validation and full JSON read-back.
16. PPU instruction compatibility — native instruction/profile counters N/A.
17. PPU compilation-cache management — cache evidence and settings; private native cache management API N/A.
18. PPU compilation error history — app/process evidence only; native compile error stream N/A.
19. PPU performance recommendations — existing configuration guidance, not a measured benchmark.
20. PPU diagnostics export — existing report plus Extra 100 shareable report.

## 21–30 · SPU

21. SPU configuration profiles — existing saved profiles.
22. SPU thread guidance — existing settings advisor.
23. SPU cache management — configured cache visibility; private cache path/API N/A.
24. SPU error history — app-level evidence only; guest SPU exception stream N/A.
25. SPU settings validation — existing settings validation and full JSON read-back.
26. SPU workload diagnostics — configured decoder/thread values only.
27. SPU module compatibility — native module registry N/A.
28. SPU performance recommendations — existing conservative settings guidance.
29. SPU memory-pressure warnings — Android memory snapshot and launch-risk warning.
30. SPU diagnostic export — existing diagnostic export.

## 31–40 · RSX and graphics

31. Graphics profiles — existing settings presets.
32. Presentation scaling — existing Android output-scale control.
33. Aspect-ratio presets — existing upstream display configuration.
34. Frame-pacing diagnostics — existing native overlay access; native per-frame feed is not duplicated.
35. Graphics settings validation — existing settings validation/read-back.
36. Shader cache management — visibility only where exposed; private engine cache control N/A.
37. Graphics error history — existing FIFO/error history.
38. Texture filtering presets — existing upstream graphics settings.
39. Graphics memory warnings — Android RAM/thermal/storage indicators, not RSX VRAM telemetry.
40. Graphics troubleshooting — existing diagnostics recommendations and report.

## 41–50 · Performance monitoring

41. Live FPS overlay — existing native in-game overlay when provided by the pinned build.
42. Frame-time graph — existing native overlay when provided by the pinned build.
43. CPU usage history — Android process/device reporting only where exposed; not PS3 guest CPU utilization.
44. Memory graph/history — existing Android memory history plus Extra 100 snapshots.
45. Temperature monitoring — Android thermal status only.
46. Battery monitoring — Android BatteryManager readings.
47. Storage monitoring — bounded app-private storage inventory.
48. Session recording — user-controlled playtime/session records; not automatic guest lifecycle detection.
49. Session comparison — Android metric snapshot comparison, not a game benchmark.
50. Performance report — existing diagnostics export plus Extra 100 share sheet.

## 51–60 · Game library companion

51. Searchable saved game metadata — Extra 100 local metadata index.
52. Cover artwork — existing emulator library artwork remains authoritative; no duplicate scraper is added.
53. Categories — user-managed per-game category.
54. Recently played — not automatically inferred by the companion; the emulator's existing recent list remains authoritative.
55. Playtime tracking — user-started and user-stopped wall-clock timer.
56. Per-game notes — saved metadata notes.
57. Favorites — per-game favorite flag.
58. Sorting — local metadata index sorts favorites first, then entry title.
59. Duplicate detection — normalized serial IDs prevent duplicate metadata keys; this does not scan duplicate ISO contents.
60. Invalid/missing file warnings — selected-document readability and extension candidate check; not full PS3 file validation.

## 61–70 · Save data and storage

61. Save-data browser — user selects a document through Android's document picker.
62. Save-data backup — stream-copy of one selected document.
63. Save-data restore — copy to a user-selected destination; no automatic save-folder overwrite.
64. Backup history — source/destination checksum result is shown in the current session; no hidden cloud history.
65. Storage by category — existing bounded app-private storage inventory.
66. Cache cleanup — existing cleanup is restricted to the app-owned temporary diagnostic file.
67. Free-space warnings — existing app-private free-space checks.
68. Backup verification — SHA-256 is re-read from the destination after copy.
69. Storage destination — Android document picker lets the user choose the destination.
70. Save-data integrity — verified copy checksum; guest save-format validation remains N/A.

## 71–80 · Controller and input

71. Bluetooth controller detection — Android input-device enumeration.
72. Controller connection status — refreshable device list.
73. Custom button mapping — native mapping remains in the existing controller settings; no duplicate remapper is invented.
74. Per-game controller profiles — use existing upstream per-game controller/settings paths where supported.
75. Controller reset — existing upstream controller settings.
76. Analog calibration — native axis bridge required; not falsely claimed by the key tester.
77. Trigger sensitivity — existing upstream/native controller support only.
78. Controller input tester — Extra 100 captures Android digital key events.
79. Multiple controllers — Android reports all matching gamepad/joystick devices.
80. Disconnect warnings — current device list can be refreshed; asynchronous disconnect monitoring requires a lifecycle/input-manager integration.

## 81–90 · Interface and usability

81. Game library interface — existing emulator library remains in place.
82. Dashboard customization — existing app layout remains authoritative.
83. Themes — existing app theme settings.
84. Compact performance overlay — existing native overlay; no duplicate fake overlay.
85. Searchable settings — existing Extra advanced settings search.
86. Settings categories — existing upstream categories and Extra panels.
87. One-tap safe configuration — existing safe profile.
88. Settings history — Extra advanced settings history.
89. Rollback — existing checkpoint restore.
90. Accessibility — native Android font/display accessibility remains respected; no app-level override is forced.

## 91–100 · Diagnostics, stability and automation

91. Startup health check — existing app/native readiness plus Extra 100 self-checks.
92. Game-file validation — selected-file metadata/readability check only.
93. Firmware validation — firmware version/contents not exposed by current bridge; manual note only.
94. Crash-loop protection — existing Extra crash-loop guard.
95. Failed-launch recovery — existing safe mode and settings rollback.
96. Diagnostic log viewer — existing app diagnostics and event history.
97. Diagnostic export — existing and Extra 100 report sharing.
98. Per-game stability history — existing user-entered handset observations.
99. Safe mode — existing crash-loop safe mode.
100. Regression testing — Python patcher regression suites and app-side readiness checklist; these do not replace running a real game test.

## Native-core limitations

The pinned ARM64 emulator remains a prebuilt upstream engine. The following require native-core source changes, matching ARM64 libraries, and actual runtime testing: PPU instruction and module counters; SPU worker queues/starvation/retry; RSX command/FIFO queue traces; GPU fences and shader internals; precise physical GPU utilization; analog-axis calibration hooks; and guest-game crash callbacks. TouchStation does not report these as live metrics until they are exported by the engine.

The Extra 100 companion's Android RAM, battery, thermal, storage, process and controller readings describe Android/device state, not the PS3 guest. File checks and user-entered compatibility notes are evidence aids, not guaranteed compatibility ratings.
