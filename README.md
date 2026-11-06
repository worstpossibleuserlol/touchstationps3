# TouchStation 4.0.0

TouchStation is an ARM64 Android distribution of the upstream ARMSX3 PlayStation 3 emulator. The Android application is built from its pinned upstream source, with the supplied TouchStation launcher artwork and a focused chipset-profile addition to the existing Performance settings. The native PPU/SPU/RSX libraries are kept unchanged from the matching upstream Android release.

## What changed in 4.0.0

- Launcher label is **TouchStation** (without the console name).
- Launcher and adaptive icons are generated from the supplied TouchStation artwork. The wordmark is placed inside Android's adaptive-icon safe area to avoid clipped or undersized artwork.
- The existing Performance page adds Auto, Dimensity, Snapdragon and Exynos profiles.
- Auto detection uses Android's SoC manufacturer/model fields. If the device is not identified as one of the three supported families, no profile is applied; the emulator's existing settings remain available.
- Profiles use existing RPCS3 settings: ARM64 LLVM PPU/SPU decoders, safe SPU block size, automatic SPU/LLVM thread allocation, Android's normal thread scheduler, and the default clock scale. Dimensity and Exynos profiles start with a 720p output scaler; Snapdragon leaves output scaling at the device's normal resolution.
- Profiles do not overclock, change voltage, or force CPU/GPU clocks. GPU Turbo remains a separate, optional upstream control and only operates on compatible Adreno hardware.
- Existing firmware/game setup, emulator settings, save data, trophies, renderer options, and physical/Bluetooth controller support are preserved from upstream.

Profiles are conservative starting points, not device-specific benchmark guarantees. A chipset family contains many tiers and GPU configurations; adjust output resolution and the manual Performance/Graphics controls for the actual phone. Other chipset families do not receive a TouchStation preset and continue using the upstream/manual settings.

## User-provided content

TouchStation does not bundle Sony firmware, commercial games, PSN licenses, or encryption keys. Users provide:
1. An official PS3 system update package (PUP).
2. Their own game content in a format supported by the upstream emulator.

Some digital PSN content can require its own license data. TouchStation cannot generate missing licenses.

## Device requirements

The release targets the upstream Android 15 / SDK 35 / ARMv8.2 ARM64 engine package. It requires a compatible 64-bit ARM device and Vulkan-capable graphics driver, plus sufficient RAM, storage and sustained cooling. A successful install does not guarantee that a particular game will boot or run smoothly.

The chipset profiles cover MediaTek Dimensity, Qualcomm Snapdragon and Samsung Exynos only. They are settings presets, not claims that every phone in those families has identical performance.

## Build pipeline

The workflow:
1. Checks out the pinned ARMSX3 Android application source.
2. Downloads the matching upstream ARM64 release and stages its original native libraries.
3. Applies the TouchStation app name, launcher artwork and chipset profiles.
4. Builds the Android application, verifies version 4.0.0 / code 400, and checks the PPU/SPU native library, JNI bridge, signing and alignment.
5. Uploads the APK as a GitHub Actions artifact.

The APK is not artificially padded. Its size is determined by the real emulator engine and app assets.

## Upstream and license

Upstream project: https://github.com/ARMSX2/ARMSX3  
Pinned source commit: https://github.com/ARMSX2/ARMSX3/commit/482d35b6a9f2eee61cdc6c0820a2d57392b235e6  
Upstream release: https://github.com/ARMSX2/ARMSX3/releases/tag/1.6.4  
Native emulator engine: RPCS3

The upstream application and emulator core retain their applicable GPL-2.0 terms. The reproducible TouchStation source-preparation script is in tools/prepare_source_build.py. See LICENSE and THIRD_PARTY_NOTICES.md.
