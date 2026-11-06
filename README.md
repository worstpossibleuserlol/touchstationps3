# TouchStation PS3 4.0.0

TouchStation PS3 is an ARM64 Android distribution of the upstream ARMSX3 PS3 emulator. This repository pins the upstream Android APK, preserves its native emulator libraries and app functionality, and applies TouchStation branding. It is a downstream rebrand, not a new emulator implementation.

## What is included

The upstream emulator package is expected to provide its own PS3 engine and user-facing workflows, including PPU/SPU execution, RSX/Vulkan rendering, firmware setup, game library and boot, per-game settings, save data, and controller support. The exact features and behavior are those of the pinned upstream release; this repository does not independently implement or test each subsystem.

The upstream app supports Android input devices, including compatible Bluetooth controllers. Controller recognition, button mapping, vibration, and individual game behavior depend on the upstream build and the connected device. This rebrand does not add a new controller-only input mode or remove upstream touch controls.

## User-provided content

The distribution does not include Sony firmware, commercial games, PSN licenses, or encryption keys. Users must supply:
1. An official PS3 system update package (PUP).
2. Their own game content in a format supported by the upstream emulator.

Some digital PSN content may require its own license data. The app cannot generate missing licenses.

## Device requirements

The release pipeline targets the upstream Android 15 / SDK 35 / ARMv8.2 ARM64 build. A compatible 64-bit ARM processor, Vulkan-capable graphics driver, sufficient memory and storage, and sustained cooling are required. PS3 emulation is demanding; a successful install does not guarantee that a particular game will boot or run smoothly.

## Build pipeline

The workflow downloads the pinned upstream ARMSX3 1.6.4 Android package, verifies its expected ARM64 native libraries, applies the supplied TouchStation launcher branding and version 4.0.0, rebuilds, aligns, signs, verifies, and uploads the APK as a GitHub Actions artifact.

The upstream package is roughly 79 MB. The final APK is not artificially padded to meet a size target. No APK is considered released until the workflow completes successfully and the resulting artifact is checked.

## Upstream and license

The emulator engine and upstream application remain governed by their upstream licenses. See LICENSE and THIRD_PARTY_NOTICES.md for details and pinned-source information.
