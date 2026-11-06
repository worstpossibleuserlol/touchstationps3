# TouchStation 4.0.0

TouchStation is an Android ARM64 distribution of the ARMSX3 Android PS3 emulator, based on the RPCS3-derived native engine. Version 4.0.0 changes the app's visible name to **TouchStation**, refreshes launcher branding, and adds a bundled chipset-family tuning guide for MediaTek Dimensity, Qualcomm Snapdragon and Samsung Exynos devices.

## Emulator engine

The native PPU/SPU execution, RSX/Vulkan rendering, firmware installation and game-boot workflows are preserved from the pinned upstream ARMSX3 release. This is a downstream rebrand and configuration guide, not a new emulator core. Game compatibility and performance depend on the exact CPU, GPU, Vulkan driver, thermal limits and title.

## Device profiles

TouchStation includes a tuning reference for exactly these chipset families:

- **MediaTek Dimensity** — Mali/Immortalis Vulkan baseline, conservative resolution scaling, asynchronous shader compilation and safe/default SPU settings.
- **Qualcomm Snapdragon** — Adreno Vulkan baseline, default system driver and per-game tuning.
- **Samsung Exynos** — Mali/Xclipse Vulkan baseline, conservative resolution scaling and per-game tuning.

The profiles are guidance for settings exposed by the upstream emulator. They do not change clock speeds or voltage, replace GPU drivers, or guarantee compatibility. Start with the engine's default settings and adjust one option at a time. Use per-game overrides where available.

The guide is bundled at `assets/touchstation-soc-profiles.json` inside the app package. Hardware support varies between generations; an SoC family name alone does not guarantee a working Vulkan driver.

## User setup

Users provide their own official PS3 system update package (PUP) and game files. No Sony firmware, commercial games, encryption keys or copyrighted game assets are bundled. Some digital content may also require its own license data.

## Release build

The workflow downloads the pinned upstream ARMSX3 Android ARM64 release, verifies that its native core and JNI libraries are present, applies TouchStation name/version/icon branding, rebuilds, aligns and signs the APK, then verifies the package version and native libraries.

The APK is ARM64 only. It is not padded to reach an arbitrary file size.

## License and credits

The emulator distribution is governed by GPL-2.0. See LICENSE and THIRD_PARTY_NOTICES.md for the upstream source and notices.
