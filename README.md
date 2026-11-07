# TouchStation 5.0.0

TouchStation is an Android ARM64 distribution of the ARMSX3 Android PS3 emulator, based on its RPCS3-derived native engine.

## TouchStation 5.0.0

- **Monochrome branding:** launcher artwork is black and white, with a build-time check that rejects coloured launcher pixels and the old blue vector accent.
- **No on-screen virtual controller:** the in-game touchscreen button overlay is hidden. Physical gamepad, keyboard and gyro input remain available.
- **Additional shader controls:** choose automatic or manual shader compiler thread counts and toggle shader/SPU compile notifications.
- **Chipset tuning:** retains the Auto detect, Dimensity, Snapdragon and Exynos profiles, with Balanced, Performance and Compatibility targets.

The chipset profiles adjust supported emulator settings only. They do not overclock the device, alter voltage, or replace GPU drivers. Actual performance and compatibility depend on the SoC generation, Vulkan driver, memory, thermals and game.

## Emulator engine

The native PPU/SPU execution, RSX/Vulkan rendering, firmware installation and game-boot workflows are provided by the pinned upstream ARMSX3 release. TouchStation is a downstream branded distribution with configuration additions, not a new emulator core.

## User setup

Users provide their own official PS3 system update package (PUP) and game files. No Sony firmware, commercial games, encryption keys or copyrighted game assets are bundled. Some digital content may also require its own license data.

## Release build

The GitHub Actions workflow builds the ARM64 APK, checks the app name and version, verifies native libraries, verifies the launcher icon is monochrome, aligns and signs the APK, and publishes the 5.0.0 Final release when all checks pass.

## License and credits

The emulator distribution is governed by GPL-2.0. See LICENSE and THIRD_PARTY_NOTICES.md for the upstream source and notices.
