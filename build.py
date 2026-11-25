"""Build standalone FlashNX homebrew from a locally owned Steam game."""
import argparse
import hashlib
import importlib.util
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSETS = {
    "FlashNX.nro": "8525d0facce06af534e1876d803f3a4a959fca6d065f6f8247ec5564cf9721a5",
    "make_standalone.py": "ad2bf3d18ed4d72e82187e3174b03b4d0faba0843b3801612f2928eca4c37895",
}
GAMES = {
    "paradise": ("Paradise.swf", "paradise-translations.xml", "RustyLakeParadise", "Icon512.png"),
    "roots": ("RustyLakeRoots.swf", "roots-translations2.xml", "RustyLakeRoots", "icon128.png"),
    "hotel": ("RustyLakeHotel.swf", "hotel-translations.xml", "RustyLakeHotel", "Icon128.png"),
}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def asset(name):
    path = ROOT / ".cache" / name
    if not path.exists() or sha(path) != ASSETS[name]:
        path.parent.mkdir(parents=True, exist_ok=True)
        url = "https://github.com/Jonathan8520/FlashNX/releases/download/v2.1.1/" + name
        print("Downloading", url, flush=True)
        with urllib.request.urlopen(url, timeout=90) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != ASSETS[name]:
            raise RuntimeError("FlashNX download hash does not match: " + name)
        path.write_bytes(data)
    return path

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game", choices=GAMES)
    parser.add_argument("steam_dir", type=Path, help="Directory of your Steam game")
    args = parser.parse_args()
    swf, translation, app, icon = GAMES[args.game]
    source = args.steam_dir.resolve()
    for path in (source / swf, source / translation, source / "icons" / icon):
        if not path.is_file():
            parser.error("Missing game file: " + str(path))
    game = ROOT / "build" / args.game / "game"
    card = ROOT / "build" / args.game / "sd-card"
    game.mkdir(parents=True, exist_ok=True)
    if args.game == "paradise":
        command = [sys.executable, str(ROOT / "patch_paradise.py"), "--source", str(source / swf), "--out", str(game)]
    else:
        command = [sys.executable, str(ROOT / ("patch_" + args.game + ".py")), str(source / swf), str(game)]
    subprocess.run(command, check=True)
    companions = game / (Path(swf).stem + ".files")
    companions.mkdir(exist_ok=True)
    shutil.copy2(game / translation, companions / translation)
    runtime, builder_path = asset("FlashNX.nro"), asset("make_standalone.py")
    spec = importlib.util.spec_from_file_location("flashnx_builder", builder_path)
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    output = card / "switch" / app / (app + ".nro")
    output.parent.mkdir(parents=True, exist_ok=True)
    builder.make_standalone(str(runtime), str(game / swf), str(output), name="Rusty Lake " + args.game.title(),
        author="Unofficial FlashNX port", version="1.0.0", icon=str(source / "icons" / icon), files_dir=str(companions))
    info = builder.app_info(str(output))
    expected = {swf: game / swf, companions.name + "/" + translation: game / translation}
    actual = {}
    for name, entry in info["files"]:
        with open(entry.path, "rb") as f:
            f.seek(entry.offset)
            actual[name] = hashlib.sha256(f.read(entry.size)).hexdigest()
    if actual != {name: sha(path) for name, path in expected.items()} or info["flashnx"] != "2.1.1":
        raise RuntimeError("Package verification failed")
    config = card / "flashnx" / (swf + ".keymap.json")
    config.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "configs" / config.name, config)
    print("\nVerified SD card files:", card)
    print("NRO SHA256:", sha(output))

if __name__ == "__main__":
    main()
