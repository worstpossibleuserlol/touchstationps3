# TouchStation PS3

TouchStation PS3 is an Android application for organizing PlayStation 3 game files and user-provided PS3 system software. It provides a mobile library interface, document import, basic file identification, and controller connection status.

## Requirements
- Android 8.0 (API 26) or newer
- Android Studio with JDK 17
- Android Gradle Plugin 8.6.1 and Kotlin 2.0.20

## Build
Open this repository in Android Studio and run the app configuration, or run `./gradlew assembleDebug`.

## Importing files
1. Open **Library** and choose a game file using Android's system document picker.
2. Open **Firmware** and choose your legally obtained `PS3UPDATE.PUP`.
3. The app stores selected document references and displays the selected filenames.

The app does not include Sony firmware, game data, encryption keys, or copyrighted system files. Supply files you are authorized to use.

## Included
- Android-native game and firmware document import
- Persistent selected-file references
- Library, firmware, controller, and settings screens
- Android game-controller connection status

## Emulation status
This repository is an Android frontend and file-management application. It does **not** implement a complete PlayStation 3 emulator, firmware installation, PPU/SPU execution, RSX graphics emulation, or commercial game boot. The interface does not claim otherwise.

## License
Source code in this repository is provided under the MIT License. Third-party dependencies retain their respective licenses.