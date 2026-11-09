# Third-party notices and licensing

## TouchStation and the ARMSX3 / RPCS3 codebase

TouchStation is an independent downstream Android ARM64 distribution built from the ARMSX3 Android application and its RPCS3-derived PlayStation 3 emulation engine. TouchStation does not claim authorship of the upstream emulator core.

- TouchStation source and build scripts: https://github.com/worstpossibleuserlol/touchstationps3
- Upstream ARMSX3 project: https://github.com/ARMSX2/ARMSX3
- Pinned upstream source commit: https://github.com/ARMSX2/ARMSX3/commit/482d35b6a9f2eee61cdc6c0820a2d57392b235e6
- Upstream Android release used for the matching ARM64 native libraries: https://github.com/ARMSX2/ARMSX3/releases/tag/1.6.4
- RPCS3 upstream project: https://github.com/RPCS3/rpcs3
- License for the covered TouchStation downstream work: GNU General Public License, version 2.0 only (GPL-2.0-only). See LICENSE.

The build starts from the pinned ARMSX3 source revision, stages the matching ARM64 native libraries from the upstream 1.6.4 Android release without modifying those library files, and applies the TouchStation patches in tools/. The generated application source, source-preparation scripts, and build workflow are included in the corresponding-source archive attached to each TouchStation release.

The release source archive contains the complete pinned ARMSX3 repository source tree, initialized Git submodule source trees, the modified Android application source, the TouchStation patch scripts, the build workflow, this license, and the source-distribution instructions. The archive is intended to be the preferred form for making modifications to the exact released downstream build. The archive is generated from the same workflow run and source revision as the APK. See SOURCE_DISTRIBUTION.md.

All upstream copyright, license, and attribution notices are retained. TouchStation modifications to upstream text source files receive a dated downstream-change notice during the build. Binary resource changes are recorded in TOUCHSTATION_MODIFICATIONS.md inside the generated source bundle.

## Other components

The APK also contains third-party components and Android platform libraries under their respective licenses. Their upstream license and copyright files are retained in the source tree where supplied. This notice does not relicense independent third-party components under GPL where their own licenses say otherwise; consult each component's included license.

## Online compatibility reference data

The Finale compatibility panel can download the public RPCS3 desktop compatibility export from `https://rpcs3.net/compatibility/?api=v1&export` when the user requests an update. The response is cached in the app's private storage and is matched by PS3 title ID. These records describe desktop RPCS3 test results; they are not TouchStation or device-specific test results. The compatibility website and its database remain third-party services and are not represented as TouchStation-owned data.

## Sony firmware and games

No PlayStation 3 firmware, commercial game, PSN license, encryption key, or copyrighted game asset is bundled. Users must provide system software and game files they are legally entitled to use. PlayStation is a trademark of Sony Interactive Entertainment. TouchStation is independent and is not affiliated with Sony, ARMSX2, or RPCS3.
