# TouchStation PS3

TouchStation PS3 is an Android frontend for organising a PS3 game file and the official PS3 system update package. Version **2.0.0** includes the supplied TouchStation identity, a redesigned dashboard, dedicated game and firmware screens, persistent document access, and an Android build workflow.

## Emulator engine status

**This repository does not yet contain a working PS3 emulator core.** It does not currently execute PPU or SPU guest code, render RSX graphics, install PS3 firmware into an emulated console, or boot games. The app is an import manager and frontend at this stage. The game boot action is intentionally unavailable rather than pretending that a native emulator engine is connected.

A real PS3 implementation needs a compatible native engine and Android integration. A practical route is to integrate and maintain an Android-capable RPCS3-derived core, then validate the PPU/SPU, RSX/Vulkan, firmware and game-boot paths on supported hardware. This is substantial native C++/LLVM/Vulkan work; the current Kotlin app is not a substitute for that engine.

## User setup

The current import flow asks for only:

1. One PS3 game file: .iso, .pkg, .self, or .elf.
2. An official PS3UPDATE.PUP firmware package.

The app stores persistable, read-only document references, so it does not ask users to move files into additional folders. The firmware screen checks the SCE PUP header only. It does **not** decrypt, verify the full package, or install firmware.

TouchStation does not bundle games, Sony firmware, encryption keys, or copyrighted system data. Importing files does not make them playable until a PS3 core is integrated.

## Included in 2.0.0

- TouchStation logo and launcher identity.
- Redesigned dark dashboard with blue accents and bottom navigation.
- Separate Home, Library, Firmware, and Settings screens.
- Persistent game and firmware document references.
- Game extension and file-size identification.
- Basic PS3 PUP header recognition.
- Connected controller detection through Android input devices.
- Clear/replace controls for imported files.
- GitHub Actions workflow that builds and uploads a debug APK.

## Build

Requirements: Android Studio or Gradle 8.7, JDK 17, Android Gradle Plugin 8.6.1, Kotlin 2.0.20, and Android SDK 35.

Run:

    gradle :app:assembleDebug

The GitHub Actions workflow runs the same task and stores the APK as a workflow artifact.

## License

The current frontend source is under the MIT License. Any future emulator engine or third-party code must retain its own license and notices. In particular, integrating an RPCS3-derived core requires preserving its applicable GPL-2.0 obligations.
