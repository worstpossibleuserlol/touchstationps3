# TouchStation PS3 3.0.0

TouchStation PS3 3.0.0 is an ARM64 Android PS3 emulator distribution built on the RPCS3-derived native engine in ARMSX3 1.6.4. Unlike the old 2.0 frontend shell, this release pipeline packages the real upstream Android application and its native emulator libraries, then applies the TouchStation name and supplied launcher logo.

## Emulator engine

The upstream engine provides native PPU and SPU execution, RSX graphics rendering through Vulkan, firmware installation, game boot, and the surrounding emulator systems. The Android app also includes the upstream library, package-install, controller/touch input, save-state, trophy/save-data and per-game configuration workflows.

This is a downstream rebrand, not a new emulator core written from scratch. Compatibility and performance remain game- and device-dependent; an emulator feature being present does not mean every PS3 title will boot or run well.

## User setup

The app does not bundle Sony firmware, commercial games, or encryption keys. The user supplies:
1. An official PS3 system update package (PUP).
2. Their own PS3 game content in a format supported by the engine.

Disc images and package installs are handled by the upstream emulator. Certain digital/PSN content can require its own license data; this is a property of that content, not a file the app should invent or bundle.

## Device target

The release workflow uses the upstream Android 15 / SDK 35 / ARMv8.2 build. It is 64-bit ARM only. A device needs a compatible 64-bit ARM CPU, a working Vulkan driver, sufficient memory and storage, and enough sustained performance. PS3 emulation is demanding: a newer Android version alone does not guarantee that a specific game will be playable.

## Build and release

The workflow pins:
- ARMSX3 release 1.6.4
- upstream commit 482d35b6a9f2eee61cdc6c0820a2d57392b235e6
- upstream release APK ARMSX3-1.6.4-a15-armv8.2-sdk35.apk
- Apktool 3.0.3 for resource-safe branding changes

It verifies that the upstream ARM64 native core is present, applies the TouchStation app label/version/icon, rebuilds the APK, aligns and signs it, verifies the signature, and uploads the APK as a GitHub Actions artifact.

The resulting APK is based on a roughly 79 MB upstream emulator package. The final size can vary after rebuilding and signing. It is not artificially padded to reach 200 MB: file size is not a measure of emulation capability.

## License and credits

The emulator distribution is governed by GPL-2.0. See LICENSE and THIRD_PARTY_NOTICES.md for the upstream source, pinned commit, and notices.
