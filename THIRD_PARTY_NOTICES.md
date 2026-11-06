# Third-party notices

## ARMSX3 / RPCS3

TouchStation 4.0.0 is a downstream Android distribution of ARMSX3 1.6.4.

- Upstream project: https://github.com/ARMSX2/ARMSX3
- Pinned Android application source commit: https://github.com/ARMSX2/ARMSX3/commit/482d35b6a9f2eee61cdc6c0820a2d57392b235e6
- Upstream Android release: https://github.com/ARMSX2/ARMSX3/releases/tag/1.6.4
- Emulator core: RPCS3, https://github.com/RPCS3/rpcs3
- License: GNU General Public License version 2.0 (see LICENSE)

The build compiles the Android application from the pinned upstream source, stages the matching upstream ARM64 native libraries unchanged, and applies a TouchStation-specific patch to the Performance settings, app label and launcher icon. The exact source-preparation logic is provided in tools/prepare_source_build.py.

The PPU/SPU/RSX native emulator engine is not reimplemented by TouchStation. All upstream copyright notices and applicable GPL obligations remain in force. ARMSX3/RPCS3 are independent projects and are not affiliated with TouchStation or Sony Interactive Entertainment.

## Sony firmware and games

No PlayStation 3 firmware, commercial game, PSN license, encryption key, or copyrighted game asset is bundled. Users provide their own legally obtained game files and official PS3 system software. PlayStation is a trademark of Sony Interactive Entertainment; TouchStation is an independent, unaffiliated project.
