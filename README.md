# TouchStation PS3

TouchStation PS3 is an Android application shell for managing a PS3 game file and the official PS3 system update package. Version **2.0.0** refreshes the interface around the supplied TouchStation logo, improves file import and validation, and adds a reproducible Android debug build workflow.

## Important: emulator-core status

**This repository does not currently contain a working PS3 emulator core.** It cannot execute PPU or SPU guest code, render RSX graphics, install firmware into an emulated console, or boot games. The current Android app is a frontend and import manager; the disabled Boot action is intentional. Calling this a complete or final PS3 emulator would be inaccurate.

A genuine PS3 implementation requires a substantial native emulation engine and platform integration. The project must link a compatible core before advertising game boot or release-ready emulation.

## User setup

The frontend asks the user for only:
1. One supported game file: `.iso`, `.pkg`, `.self`, or `.elf`.
2. An official `PS3UPDATE.PUP` firmware package.

The app checks the firmware PUP signature and stores persistable, read-only document references. It does not bundle games, Sony firmware, encryption keys, or other copyrighted system data. The firmware check is file identification only, not firmware installation.

## Included in 2.0.0

- TouchStation logo in the application and launcher icon.
- Dark blue/black mobile interface.
- Game and firmware import screens with persistent selections.
- Game file type identification and file-size display.
- PUP signature check before accepting a firmware file.
- Controller detection.
- Clear/remove controls for the two imported files.
- GitHub Actions workflow that builds and uploads a debug APK.

## Build

Requirements: Android Studio or Gradle 8.7, JDK 17, Android Gradle Plugin 8.6.1, Kotlin 2.0.20, and Android SDK 35.

Run:

```bash
gradle :app:assembleDebug
```

The CI workflow runs the same task and stores the APK as a workflow artifact.

## Next engineering requirement

To become an actual emulator, a legally compatible Android-capable PS3 engine must be integrated and tested on real devices. That work includes PPU/SPU execution, RSX/Vulkan, firmware installation, storage mapping, controller input, audio, lifecycle handling, and game boot. The current repository does not claim those features.

## License

The app source in this repository is under the MIT License. Any future emulator engine or third-party code must retain its own license and notices.
