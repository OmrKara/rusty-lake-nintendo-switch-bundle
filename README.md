# Rusty Lake Nintendo Switch Bundle

Unofficial homebrew ports of **Rusty Lake Hotel**, **Rusty Lake Roots**, and **Rusty Lake Paradise**, running on [FlashNX](https://github.com/Jonathan8520/FlashNX) 2.1.1. These are fan projects and are not affiliated with Rusty Lake.

The three ports have been reported working on a modded Switch, including gameplay, controls, sound, menus and text. This does not mean every scene or puzzle has been tested.

## Installation

1. You need a Nintendo Switch capable of running homebrew, a microSD card, and a way to copy files to it.
2. Download the ZIP for each game you want from the `packages` folder: [Hotel](packages/RustyLakeHotel-Switch.zip), [Roots](packages/RustyLakeRoots-Switch.zip), or [Paradise](packages/RustyLakeParadise-Switch.zip). On GitHub, open the file and use Download.
3. Extract each ZIP to the **root of your Switch microSD card**. Keep both the `switch` and `flashnx` folders and merge them with any existing folders. For example, Hotel's NRO should be at `sd:/switch/RustyLakeHotel/RustyLakeHotel.nro` and its controller configuration at `sd:/flashnx/RustyLakeHotel.swf.keymap.json`.
4. Open the Homebrew Menu and launch the game. The NRO is standalone: no separate FlashNX installation is needed. An optional home-screen forwarder can target the NRO path above (adjust the game name for Roots or Paradise).
5. Keep backups of your saves, especially before replacing an existing installation.

## Controls

- Touch screen: interact directly.
- Left analog stick: move cursor; **A** or **ZR**: left click.
- Paradise and Roots: **B** or **ZL** sends right click, used for the back action in the adapted game. Actual behavior depends on the scene.
- Hotel: **ZL** sends right click; this can open a graphics/settings menu. A general previous-scene shortcut and D-pad arrow selection are not implemented. Use the on-screen arrows for navigation.

## Build from your own Steam files

The repository also contains reproducible patching and packaging scripts. You need Python 3 and Pillow (`python -m pip install pillow`), an installed Steam copy of the game, and internet access to download the pinned FlashNX 2.1.1 release assets. The tools verify the original SWF and the FlashNX downloads by SHA-256; other game versions may be rejected.

On Windows, open a terminal in this repository and run the relevant command, replacing the Steam paths if needed:

```powershell
python build.py hotel "C:\Program Files (x86)\Steam\steamapps\common\Rusty Lake Hotel"
python build.py roots "C:\Program Files (x86)\Steam\steamapps\common\Rusty Lake Roots"
python build.py paradise "C:\Program Files (x86)\Steam\steamapps\common\Rusty Lake Paradise"
```

Copy the contents of `build/<game>/sd-card/` to the root of the microSD card. Building locally does not alter the original Steam installation. The build includes assets from your game copy; do not redistribute a build unless you have the necessary rights.

## Credits

Games and their assets belong to Rusty Lake. FlashNX is developed by [Jonathan8520 and contributors](https://github.com/Jonathan8520/FlashNX); its [license](https://github.com/Jonathan8520/FlashNX/blob/main/LICENSE) applies to FlashNX. These ports modify the original SWF for compatibility and use FlashNX to run it.
