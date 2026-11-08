# TouchStation 7.0.0 Release

TouchStation is an Android ARM64 distribution built from the ARMSX3 Android PS3 emulator application. Its native emulator core is provided by the pinned upstream ARMSX3 release, which is derived from RPCS3. TouchStation is a downstream project, not a PS3 emulator core written from scratch.

## 7.0.0 Release

- **TouchStation Control Center:** a consolidated device diagnostics panel inside Performance settings.
- **Native in-game performance OSD:** automatically enabled for existing installations on first 7.0.0 game launch, displayed in the top-left corner, and configurable from the new PPU Monitor panel.
- **Live in-game metrics:** native FPS, host CPU utilization, guest PPU/SPU/RSX utilization, PPU/SPU thread counts, RSX load, framerate graph and frametime graph. The native OSD reads these values from the emulator core rather than the Android bridge's unimplemented FPS getter.
- **Dedicated PPU Monitor:** shows the selected PPU decoder, configured PPU threads, LLVM compile-thread limit, LLVM precompilation state, native compile notifications, and controls the in-game overlay.
- **Live performance monitoring:** rolling CPU, GPU and FPS graphs, plus app memory. CPU readings are device-wide; GPU readings depend on counters exposed by the Android driver; FPS is shown only when the native bridge returns a real reading.
- **Thermal and battery information:** Android thermal-severity status, battery level and battery-sensor temperature. Battery temperature is not the SoC temperature. Android thermal status is a severity level, not a temperature measurement.
- **Device and graphics information:** SoC/hardware identity, Android version, RAM, app PSS, free internal storage, and Vulkan feature information reported by Android.
- **Diagnostic sharing:** export a text report containing device, system, core-initialization, current-game, controller, thermal and memory information, or open the structured TouchStation bug-report form.
- **Controller status:** physical gamepad hot-plug monitoring, connection status, and an in-game disconnect warning.
- **Controller-only gameplay:** virtual touchscreen gameplay controls remain disabled. Touch input is retained for menus and settings.
- **Existing upstream management features are retained:** game-folder scanning, game search, cover art, recent games, favourites and categories, per-game settings, firmware installation/management, and the upstream game compatibility metadata.

Unsupported Android/driver metrics remain **N/A**; TouchStation does not invent host-GPU utilization, PPU activity, or SoC temperature. The Android FPS tile remains N/A because the pinned Java bridge has no direct getter, but the native in-game OSD obtains FPS from the emulator's own frame counter.

## Control Center location

Open **Settings → Performance**. The live Performance Monitor appears first, followed by the TouchStation Control Center. The control center refreshes device diagnostics every 2.5 seconds. Use **Export diagnostic report** to share a report with a support contact, or **Report a Bug** to open the repository's structured issue form.

The existing performance monitor reports:
- CPU load sampled from Linux `/proc/stat`.
- GPU utilization only when a supported kernel driver counter is readable by the app.
- FPS only when the pinned native bridge supplies a valid frame-rate reading.
- TouchStation process memory and rolling 60-second graphs.

Some Android devices restrict GPU utilization counters and thermal information. These fields correctly show N/A when unavailable. The native in-game OSD separately reports the emulated PS3 RSX workload; RSX load is not the phone's Mali/Adreno utilization.

## PPU Monitor and in-game performance overlay

Open **Settings → Performance → TouchStation PPU Monitor**. The overlay switch enables the native RPCS3 high-detail OSD and places it at the top-left while a game is running. It displays FPS, host CPU utilization, guest PPU/SPU/RSX utilization, PPU/SPU thread counts, RSX load, and both framerate and frametime graphs. The first 7.0.0 game launch migrates existing installs to the new enabled default; the user's subsequent Full/Off choice is saved across launches.

The PPU panel also shows the selected PPU decoder, configured PPU thread count, LLVM compile-thread limit and precompilation state. Active PPU/SPU thread counts and guest utilization come from the native in-game OSD. Separate PPU instruction and exception counters are not exposed by the pinned Android bridge and are labelled N/A rather than fabricated. Host GPU utilization remains dependent on readable Android driver counters in the separate Performance Monitor.

## Emulator engine and firmware

The build downloads the ARM64 native engine libraries from the pinned ARMSX3 Android release and builds the matching upstream Android application with TouchStation changes. It does **not** compile a new PS3 engine from scratch or replace the upstream PPU, SPU, RSX or Vulkan implementations.

Users provide their own official PS3 system update package (PUP) and game files they are legally entitled to use. Sony firmware, commercial games, encryption keys and copyrighted game assets are not bundled.

## Build and release

The GitHub Actions workflow:
1. Checks out the pinned ARMSX3 Android application source.
2. stages the matching ARM64 native libraries from the upstream release;
3. applies TouchStation branding, controller-only gameplay, advanced settings, monitoring and Control Center patches;
4. builds the ARM64 release APK;
5. verifies app version, native libraries, launcher artwork, APK signature and alignment;
6. uploads the APK artifact and publishes the `v6.0.0` GitHub release when all checks pass.

The release workflow is the authoritative APK build path. The upstream source revision and native library release are intentionally pinned for reproducibility.

## Menu and controller access

The navigation drawer includes direct links to the TouchStation GitHub repository, the structured **Report a Bug** issue form, and **About TouchStation**. About shows project attribution and explains that gameplay requires a physical controller.

While a game is running, the pause menu provides access to Options and All Settings. A touch-only gear also opens the in-game Settings screen without taking over a gamepad button. **Y** opens the pause-menu Options tab; **L1/R1** cycle tabs and **B** backs out.

## License and credits

The emulator distribution is governed by GPL-2.0. See [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for upstream source and third-party notices.
