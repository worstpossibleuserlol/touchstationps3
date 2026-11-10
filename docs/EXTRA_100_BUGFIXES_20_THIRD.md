# TouchStation Extra — 20 more reliability fixes

This batch focuses on Android document permissions, safe file handling, controller input, memory-aware defaults and compatibility-test evidence.

1. **Sanitize document-provider filenames:** remove control characters before showing a selected filename.
2. **Bound displayed filenames:** cap provider-supplied names before they reach the UI report.
3. **Validate reported file sizes:** treat negative provider sizes as unknown instead of displaying invalid metadata.
4. **Validate saved backup-source access:** check the saved URI still has a persisted read grant when restoring the app.
5. **Validate saved restore-source access:** check the saved restore URI still has a persisted read grant when restoring the app.
6. **Clean stale document selections:** remove malformed or permission-revoked saved URI preferences rather than leaving unusable selections visible.
7. **Detect aliased SAF documents:** compare provider authority and document ID as well as raw URI equality before copying, preventing two URI forms for the same document from truncating the source.
8. **Preserve cancellation during inspection:** allow a cancelled file-inspection coroutine to cancel instead of converting it into a normal error report.
9. **Preserve cancellation during backup:** do not turn a cancelled backup coroutine into a completed failure message.
10. **Preserve cancellation during restore:** do not swallow cancellation in the restore-copy path.
11. **Filter the controller inventory:** list only non-virtual Android input devices reporting gamepad, joystick or D-pad sources. The pinned Compose key-event API does not expose the native device identity, so the key probe does not pretend to classify an individual key event.
12. **Do not consume diagnostic input:** record Compose KeyDown events for display and return false so keyboard and controller input can continue through the normal event path.
13. **Sanitize controller names:** remove control characters and cap device names before displaying them.
14. **Bound controller output:** show at most 16 detected physical controllers in the summary.
15. **Respect the safe PPU precompile gate:** the Advanced safe-boot profile now uses the existing RAM/thermal policy instead of always forcing LLVM precompile on.
16. **Use monotonic Game Lab timing:** measure same-boot test duration with Android elapsed realtime instead of relying entirely on the adjustable wall clock.
17. **Detect reboot boundaries:** record Android's boot count and use an explicitly labelled wall-clock fallback only for legacy sessions or sessions spanning a reboot.
18. **Validate active-session identity:** reject records belonging to another title ID while retaining valid legacy-format records during migration.
19. **Validate Game Lab observations:** reject malformed, oversized or non-object event arrays and accept only the defined manual observation stages.
20. **Compare nested settings deterministically:** canonicalize nested JSON values when comparing saved profiles so object-key ordering does not create false differences.

## Verification boundary

The new regression tests check the source safeguards and workflow integration. A green test suite does not itself prove an APK build or a GTA IV boot. The native PS3 core remains the pinned upstream binary and has not been rebuilt or changed by this batch.
