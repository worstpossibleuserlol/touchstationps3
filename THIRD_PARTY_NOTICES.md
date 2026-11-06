# Third-party notices

## ARMSX3 / RPCS3

TouchStation PS3 3.0.0 is a branded downstream distribution of the Android PS3 emulator ARMSX3 1.6.4, built from the upstream release dated 5 November 2026.

- Upstream project: https://github.com/ARMSX2/ARMSX3
- Pinned source commit: https://github.com/ARMSX2/ARMSX3/commit/482d35b6a9f2eee61cdc6c0820a2d57392b235e6
- Upstream release: https://github.com/ARMSX2/ARMSX3/releases/tag/1.6.4
- Upstream native engine: RPCS3, https://github.com/RPCS3/rpcs3
- License: GNU General Public License version 2.0 (see LICENSE)

The TouchStation build workflow downloads the upstream ARM64 Android release APK, applies the TouchStation name, version and launcher icon, then rebuilds and signs the package. The native emulator libraries are kept intact; this repository does not reimplement or replace the PPU, SPU, or RSX engine.

All upstream copyright notices and applicable GPL obligations remain in force. The ARMSX3 project is independently developed and is not affiliated with TouchStation or Sony Interactive Entertainment.

## Sony firmware and games

No PlayStation 3 firmware, game, encryption key, or commercial game asset is bundled. Users provide their own legally obtained game files and official PS3 system software. PlayStation is a trademark of Sony Interactive Entertainment; TouchStation PS3 is an independent, unaffiliated project.
