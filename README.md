# TouchStation 5.0.0 Final

TouchStation is an Android ARM64 distribution of the ARMSX3 Android PS3 emulator, based on its RPCS3-derived native engine.

## 5.0.0 Final

- **Exact supplied launcher artwork:** the supplied square TouchStation wordmark (black background, white lettering) is used for the launcher, adaptive/round launcher assets and splash mark. The build converts it to grayscale to remove JPEG colour artefacts and verifies that the packaged launcher contains no coloured pixels.
- **Controller-only gameplay:** the in-game virtual touchscreen overlay is not composed. Physical USB and Bluetooth game controllers remain the intended gameplay input. No virtual buttons or motion-control overlay are rendered.
- **In-game Settings shortcut:** one white gear icon sits in the top-right while a game is running. It opens the existing settings screen by touch only, has no controller binding, and cannot take PlayStation controller focus.
- **20+ real performance and compatibility controls:** output resolution scale, screen-resolution override, sustained-performance mode, Android Performance Hint Manager (ADPF), Adreno GPU Turbo, log suppression, thread scheduler mode, PPU decoder, SPU decoder, SPU block size, preferred SPU thread count, LLVM thread count, SPURS thread limit, clock scale, SPU cache, LLVM precompilation, SPU loop detection, accurate SPU DMA, savestate-compatible mode, accurate SPU RSV, accurate cache-line mode, SPU XFloat precision, frame-generation options and compiled-code cache management.
- **TouchStation additions:** automatic chipset detection and Dimensity, Snapdragon and Exynos profiles; Balanced, Performance and Compatibility targets; shader compiler thread control; shader and SPU compile notifications.

Chipset profiles only adjust supported emulator settings. They do not overclock the phone, change voltage, or replace graphics drivers. Performance depends on SoC generation, Vulkan driver, memory, thermals and the game being run. Some options are device- or game-dependent.

## Menu and controller access

The navigation drawer includes direct links to the TouchStation GitHub repository, the structured **Report a Bug** issue form, and **About TouchStation**. The About page shows the installed app/core versions, device details, project source, upstream base, and license information.

The drawer rows use the controller navigation system. While a game is running, open the pause menu and use the D-pad to move between tabs and controls. **Y** opens the Options tab; select **All Settings** with the confirm button to open the full in-game settings screen. **L1/R1** also cycle pause-menu tabs, and **B** backs out.

The small top-right gear remains touch-only so it does not take over a controller button that games may need. Controller users can reach the same full settings screen through **Pause Menu → Options → All Settings**. The in-game Settings page also exposes controller-focusable Resume Game, Restart Game, Save State & Exit, and Exit Game actions.

## Emulator engine

The native PPU/SPU execution, RSX/Vulkan rendering, firmware installation and game-boot workflows are provided by the pinned upstream ARMSX3 release. TouchStation is a downstream branded distribution with configuration additions, not a new emulator core.

## User setup

Users provide their own official PS3 system update package (PUP) and game files. No Sony firmware, commercial games, encryption keys or copyrighted game assets are bundled. Some digital content may also require its own license data.

## Release build

The GitHub Actions workflow builds the ARM64 APK, checks app name and version, verifies native libraries, validates the monochrome launcher icon, checks APK alignment and signature, uploads the correctly named artifact, and publishes the 5.0.0 Final release when all checks pass.

## License and credits

The emulator distribution is governed by GPL-2.0. See LICENSE and THIRD_PARTY_NOTICES.md for the upstream source and notices.
