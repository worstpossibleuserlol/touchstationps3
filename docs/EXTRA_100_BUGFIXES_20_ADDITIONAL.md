# TouchStation Extra — 20 additional bug fixes

This batch hardens app-side reliability and the build validator. These changes do not modify or rebuild the pinned native PS3 core and do not claim to make GTA IV boot.

1. **Finale error-banner build validation:** accept the real 72 dp Finale swipe threshold as well as the 56 dp standalone Extra implementation.
2. **Error-banner regression guard:** keep the gesture recognizer and upward exit animation checks while avoiding a false failure caused by one exact threshold literal.
3. **Game Lab title-ID key collisions:** hash the original title ID after preserving a short readable prefix.
4. **Game Lab device-key collisions:** hash the full device fingerprint rather than relying on a lossy sanitized string.
5. **Game Lab history migration:** move existing history from the old preference key to the new collision-resistant key on first read.
6. **Game Lab active-session migration:** preserve unfinished sessions across the key-format change.
7. **Game Lab profile migration:** preserve saved settings snapshots across the key-format change.
8. **Active-session JSON parsing:** do not treat a preference entry as a valid session until it parses as an object.
9. **Session start-time validation:** reject malformed active records that lack a positive start timestamp.
10. **Session event validation:** reject malformed active records that do not contain an event array.
11. **Corrupt-session recovery:** remove an unreadable active-session key so it cannot permanently block a new test.
12. **Recovery feedback:** tell the user when a damaged unfinished record was cleared before a new test starts.
13. **Game Lab save-scope guard:** refuse to save a per-game profile while settings are in Global scope.
14. **Game Lab save-button guard:** disable the save action unless a selected game and per-game settings scope are active.
15. **Game Lab comparison-scope guard:** refuse to compare a per-game snapshot from Global scope.
16. **Game Lab comparison-button guard:** disable comparison outside per-game scope.
17. **Removed-setting detection:** compare the union of saved and current JSON keys so removed settings are no longer missed.
18. **Stable settings fingerprints:** canonicalize nested JSON objects before hashing so key ordering does not create false settings changes.
19. **Advanced-suite identity and history safety:** use collision-resistant game/device keys, migrate legacy test/profile data on read, and include removed settings in change history.
20. **Picker, controller, and report UX:** cancelling a document picker keeps the previous selection; virtual input devices are not reported as physical controllers; share actions report failure instead of falsely claiming the chooser opened.

## Verification boundary

The Python regression checks validate source markers and patcher behavior. GitHub Actions must still complete the full Android build before an APK can be called build-successful. GTA IV gameplay remains unverified until tested on the target phone with useful native diagnostics.
