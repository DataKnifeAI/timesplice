#!/usr/bin/env python3
"""Add or remove a Steam non-Steam shortcut and Proton mapping.

Stdlib only. shortcuts.vdf is binary VDF; config.vdf is text VDF.
"""

from __future__ import annotations

import argparse
import binascii
import json
import os
import re
import shutil
import struct
import sys
from pathlib import Path

APP_NAME_DEFAULT = "TimeSplitters Rewind"
GAME_DIR_NAME = "TimeSplittersRewind"

# Steam library artwork filenames relative to docs/assets/steam-grid/.
# Written as {id}{suffix} for both the 32-bit shortcut appid and the 64-bit grid id.
GRID_FILES = (
    ("p.png", "capsule.png"),
    (".png", "header.png"),
    ("_hero.png", "hero.png"),
    ("_logo.png", "logo.png"),
    ("_icon.png", "icon.png"),
)


def parse_binary_vdf(data: bytes, offset: int = 0) -> tuple[dict, int]:
    result: dict = {}
    while offset < len(data):
        type_byte = data[offset]
        if type_byte == 8:
            return result, offset + 1
        offset += 1
        key_end = data.find(b"\x00", offset)
        if key_end == -1:
            raise ValueError("corrupt binary VDF: unterminated key")
        key = data[offset:key_end].decode("utf-8", errors="replace")
        offset = key_end + 1
        if type_byte == 0:
            value, offset = parse_binary_vdf(data, offset)
            result[key] = value
        elif type_byte == 1:
            val_end = data.find(b"\x00", offset)
            if val_end == -1:
                raise ValueError("corrupt binary VDF: unterminated string")
            result[key] = data[offset:val_end].decode("utf-8", errors="replace")
            offset = val_end + 1
        elif type_byte == 2:
            result[key] = struct.unpack_from("<I", data, offset)[0]
            offset += 4
        elif type_byte == 7:
            result[key] = struct.unpack_from("<Q", data, offset)[0]
            offset += 8
        else:
            raise ValueError(f"unsupported binary VDF type {type_byte}")
    return result, offset


def serialize_binary_vdf(payload: dict) -> bytes:
    out = bytearray()
    for key, value in payload.items():
        key_bytes = key.encode("utf-8") + b"\x00"
        if isinstance(value, dict):
            out.append(0)
            out.extend(key_bytes)
            out.extend(serialize_binary_vdf(value))
        elif isinstance(value, str):
            out.append(1)
            out.extend(key_bytes)
            out.extend(value.encode("utf-8") + b"\x00")
        elif isinstance(value, bool):
            raise TypeError("refusing to serialize bool as VDF int")
        elif isinstance(value, int):
            out.append(2)
            out.extend(key_bytes)
            out.extend(struct.pack("<I", value & 0xFFFFFFFF))
        else:
            raise TypeError(f"unsupported VDF value type: {type(value)}")
    out.append(8)
    return bytes(out)


def load_shortcuts(path: Path) -> dict:
    if not path.exists() or path.stat().st_size == 0:
        return {}
    data = path.read_bytes()
    if data[0] != 0:
        raise ValueError(f"{path} is not a binary VDF map")
    key_end = data.find(b"\x00", 1)
    root_key = data[1:key_end].decode("utf-8")
    if root_key != "shortcuts":
        raise ValueError(f"{path} root key is {root_key!r}, expected 'shortcuts'")
    shortcuts, _ = parse_binary_vdf(data, key_end + 1)
    return shortcuts


def save_shortcuts(path: Path, shortcuts: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(serialize_binary_vdf({"shortcuts": shortcuts}))


def shortcut_appid(exe_quoted: str, name: str) -> int:
    key = f"{exe_quoted}{name}".encode("utf-8")
    return (binascii.crc32(key) | 0x80000000) & 0xFFFFFFFF


def grid_id(appid: int) -> int:
    return (appid << 32) | 0x02000000


def grid_ids(appid: int) -> tuple[int, int]:
    return appid, grid_id(appid)


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def artwork_dir() -> Path:
    env = os.environ.get("TIMESPLICE_ARTWORK")
    if env:
        return Path(env).expanduser()
    return repo_root() / "docs" / "assets" / "steam-grid"


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise ValueError(f"{path} is not a PNG with IHDR")
    return struct.unpack(">II", data[16:24])


def install_artwork(grid_dir: Path, appid: int, assets_dir: Path | None = None) -> list[str]:
    assets_dir = assets_dir or artwork_dir()
    missing = [name for _, name in GRID_FILES if not (assets_dir / name).is_file()]
    if missing:
        print(f"timesplice: missing artwork {', '.join(missing)} in {assets_dir}", file=sys.stderr)
    grid_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for gid in grid_ids(appid):
        for suffix, name in GRID_FILES:
            src = assets_dir / name
            if not src.is_file():
                continue
            dest = grid_dir / f"{gid}{suffix}"
            shutil.copy2(src, dest)
            written.append(str(dest))
    return written


def remove_artwork(grid_dir: Path, appid: int) -> int:
    if not grid_dir.is_dir():
        return 0
    extra = ("p.jpg", ".jpg", "_hero.jpg", "_logo.jpg", "_icon.jpg")
    suffixes = tuple(suffix for suffix, _ in GRID_FILES) + extra
    removed = 0
    for gid in grid_ids(appid):
        for suffix in suffixes:
            path = grid_dir / f"{gid}{suffix}"
            if path.is_file():
                path.unlink()
                removed += 1
    return removed


def resolve_icon(appid: int, grid_dir: Path, explicit: str | None, fallback: str) -> str:
    if explicit:
        return explicit
    copied = grid_dir / f"{appid}_icon.png"
    if copied.is_file():
        return str(copied)
    bundled = artwork_dir() / "icon.png"
    if bundled.is_file():
        return str(bundled)
    return fallback


def find_steam_roots() -> list[Path]:
    home = Path.home()
    candidates = [
        Path(os.environ["STEAM_DIR"]) if os.environ.get("STEAM_DIR") else None,
        home / ".steam" / "root",
        home / ".local" / "share" / "Steam",
        home / ".steam" / "steam",
        home / ".var" / "app" / "com.valvesoftware.Steam" / ".local" / "share" / "Steam",
    ]
    roots: list[Path] = []
    seen: set[Path] = set()
    for raw in candidates:
        if raw is None:
            continue
        path = raw.expanduser()
        if not path.exists():
            continue
        resolved = path.resolve()
        if resolved in seen:
            continue
        if (resolved / "userdata").is_dir() or (resolved / "config").is_dir():
            seen.add(resolved)
            roots.append(resolved)
    return roots


def libraryfolders_vdf(steam_root: Path) -> Path | None:
    for candidate in (
        steam_root / "config" / "libraryfolders.vdf",
        steam_root / "steamapps" / "libraryfolders.vdf",
    ):
        if candidate.is_file():
            return candidate
    return None


def parse_libraryfolders(text: str) -> list[dict]:
    """Read Steam libraryfolders.vdf (text VDF) into ordered library dicts."""
    libraries: list[dict] = []
    for match in re.finditer(
        r'"(\d+)"\s*\{(.*?)\n\t\}',
        text,
        re.DOTALL,
    ):
        index = match.group(1)
        body = match.group(2)
        path_m = re.search(r'"path"\s+"([^"]+)"', body)
        if not path_m:
            continue
        cid_m = re.search(r'"contentid"\s+"([^"]+)"', body)
        label_m = re.search(r'"label"\s+"([^"]*)"', body)
        apps = re.findall(r'"(\d+)"\s+"\d+"', body)
        libraries.append(
            {
                "index": int(index),
                "path": path_m.group(1).replace("\\\\", "/"),
                "contentid": cid_m.group(1) if cid_m else "",
                "label": label_m.group(1) if label_m else "",
                "app_count": len(apps),
            }
        )
    return libraries


def _path_usable(path: Path) -> bool:
    try:
        return path.is_dir() and os.access(path, os.W_OK)
    except OSError:
        return False


def _path_score(path: Path) -> tuple:
    raw = str(path)
    return (
        1 if _path_usable(path) else 0,
        0 if raw.startswith("/run/media/") else 1,
        0 if "/.local/share/Steam" in raw or raw.endswith("/.steam/steam") else 1,
    )


def discover_libraries(steam_root: Path) -> list[dict]:
    vdf_path = libraryfolders_vdf(steam_root)
    raw: list[dict] = []
    if vdf_path:
        raw = parse_libraryfolders(vdf_path.read_text(encoding="utf-8", errors="replace"))
    if not raw:
        raw = [{"index": 0, "path": str(steam_root), "contentid": "", "label": "", "app_count": 0}]

    steam_resolved = steam_root.resolve()
    by_id: dict[str, dict] = {}
    ordered: list[dict] = []
    for entry in raw:
        path = Path(entry["path"]).expanduser()
        resolved = path.resolve() if path.exists() else path
        is_root = resolved == steam_resolved or entry["index"] == 0
        key = entry["contentid"] or str(resolved)
        row = {
            "index": entry["index"],
            "path": str(resolved),
            "contentid": entry["contentid"],
            "label": entry["label"],
            "app_count": entry["app_count"],
            "exists": path.is_dir(),
            "writable": _path_usable(path if path.is_dir() else path.parent),
            "is_root": is_root,
            "mounted": path.is_dir(),
        }
        existing = by_id.get(key)
        if existing is None:
            by_id[key] = row
            ordered.append(row)
            continue
        if _path_score(Path(row["path"])) > _path_score(Path(existing["path"])):
            existing.update(row)
    return ordered


def default_library(libraries: list[dict]) -> dict | None:
    extras = [lib for lib in libraries if not lib["is_root"] and lib["exists"] and lib["writable"]]
    if extras:
        return extras[0]
    roots = [lib for lib in libraries if lib["is_root"] and lib["writable"]]
    if roots:
        return roots[0]
    return libraries[0] if libraries else None


def default_install_dir(steam_root: Path | None = None) -> dict:
    roots = [steam_root] if steam_root else find_steam_roots()
    if not roots:
        home_fallback = Path.home() / "Games" / GAME_DIR_NAME
        return {
            "default_library": None,
            "install_dir": str(home_fallback),
            "libraries": [],
        }
    libraries = discover_libraries(roots[0])
    chosen = default_library(libraries)
    if chosen:
        install = str(Path(chosen["path"]) / GAME_DIR_NAME)
    else:
        install = str(Path.home() / "Games" / GAME_DIR_NAME)
    return {
        "steam_root": str(roots[0]),
        "default_library": chosen["path"] if chosen else None,
        "install_dir": install,
        "libraries": libraries,
    }


def userdata_dirs(steam_root: Path) -> list[Path]:
    users = steam_root / "userdata"
    if not users.is_dir():
        return []
    found = []
    for child in sorted(users.iterdir()):
        if not child.is_dir() or not child.name.isdigit():
            continue
        if (child / "config").is_dir():
            found.append(child)
    return found


def _compat_tool_name_from_vdf(text: str) -> str | None:
    match = re.search(
        r'"compat_tools"\s*\{\s*"([^"]+)"',
        text,
        re.DOTALL,
    )
    return match.group(1) if match else None


def discover_proton_tools(steam_root: Path) -> list[dict]:
    tools: list[dict] = []
    seen: set[str] = set()

    def add(name: str, source: str, path: str = "") -> None:
        if name in seen:
            return
        seen.add(name)
        tools.append({"name": name, "source": source, "path": path})

    common = steam_root / "steamapps" / "common"
    mapping = (
        ("Proton - Experimental", "proton_experimental"),
        ("Proton 10.0", "proton_10"),
        ("Proton 9.0", "proton_9"),
        ("Proton 8.0", "proton_8"),
        ("Proton Hotfix", "proton_hotfix"),
    )
    if common.is_dir():
        for folder, internal in mapping:
            if (common / folder).is_dir():
                add(internal, "steam", str(common / folder))

    extra_roots = [
        steam_root / "compatibilitytools.d",
        Path("/usr/share/steam/compatibilitytools.d"),
        Path.home() / ".steam" / "root" / "compatibilitytools.d",
    ]
    for extra in extra_roots:
        if not extra.is_dir():
            continue
        for tool_dir in extra.iterdir():
            vdf_path = tool_dir / "compatibilitytool.vdf"
            if not vdf_path.is_file():
                continue
            name = _compat_tool_name_from_vdf(vdf_path.read_text(errors="replace"))
            if name:
                add(name, "compatibilitytools.d", str(tool_dir))

    return tools


def pick_proton(tools: list[dict], preferred: str | None, variant: str) -> str:
    names = [t["name"] for t in tools]
    if preferred:
        if preferred in names or preferred.startswith("proton"):
            return preferred
        raise SystemExit(f"proton tool {preferred!r} not found. have: {', '.join(names) or 'none'}")

    order = []
    if variant == "cachyos":
        order.extend(n for n in names if "cachyos" in n.lower())
    order.extend(["proton_10", "proton_experimental", "proton_hotfix", "proton_9", "proton_8"])
    for name in order:
        if name in names:
            return name
    if names:
        return names[0]
    return "proton_experimental"


def upsert_shortcut(
    shortcuts: dict,
    *,
    name: str,
    exe: Path,
    icon: str,
) -> tuple[str, int]:
    exe_quoted = f'"{exe}"'
    start_dir = f'"{exe.parent}/"'
    appid = shortcut_appid(exe_quoted, name)
    entry = {
        "appid": appid,
        "AppName": name,
        "Exe": exe_quoted,
        "StartDir": start_dir,
        "icon": icon,
        "ShortcutPath": "",
        "LaunchOptions": "",
        "IsHidden": 0,
        "AllowDesktopConfig": 1,
        "AllowOverlay": 1,
        "OpenVR": 0,
        "Devkit": 0,
        "DevkitGameID": "",
        "DevkitOverrideAppID": 0,
        "LastPlayTime": 0,
        "FlatpakAppID": "",
        "tags": {},
    }
    for key, existing in shortcuts.items():
        if existing.get("AppName") == name:
            existing.update(entry)
            return key, appid
    index = 0
    while str(index) in shortcuts:
        index += 1
    key = str(index)
    shortcuts[key] = entry
    return key, appid


def remove_named(shortcuts: dict, name: str) -> list[int]:
    remove = [key for key, value in shortcuts.items() if value.get("AppName") == name]
    appids: list[int] = []
    for key in remove:
        appid = shortcuts[key].get("appid")
        if isinstance(appid, int):
            appids.append(appid)
        del shortcuts[key]
    return appids


def _upsert_compat_block(block: str, appid: str, proton: str) -> str:
    entry_re = re.compile(
        rf'("{re.escape(appid)}"\s*\{{)(.*?)(\n\s*\}})',
        re.DOTALL,
    )

    def replace_name(match: re.Match[str]) -> str:
        body = re.sub(r'"name"\s+"[^"]*"', f'"name"\t\t"{proton}"', match.group(2), count=1)
        if '"name"' not in body:
            body = f'\n\t\t\t\t\t"name"\t\t"{proton}"\n\t\t\t\t\t"config"\t\t""\n\t\t\t\t\t"priority"\t\t"250"' + body
        return f"{match.group(1)}{body}{match.group(3)}"

    updated, count = entry_re.subn(replace_name, block, count=1)
    if count:
        return updated
    entry = (
        f'\n\t\t\t\t\t"{appid}"\n'
        f"\t\t\t\t\t{{\n"
        f'\t\t\t\t\t\t"name"\t\t"{proton}"\n'
        f'\t\t\t\t\t\t"config"\t\t""\n'
        f'\t\t\t\t\t\t"priority"\t\t"250"\n'
        f"\t\t\t\t\t}}"
    )
    brace = block.find("{")
    if brace == -1:
        raise ValueError("CompatToolMapping has no opening brace")
    return block[: brace + 1] + entry + block[brace + 1 :]


def set_compat_mapping(config_path: Path, appid: int, proton: str) -> None:
    if not config_path.is_file():
        raise SystemExit(f"missing Steam config: {config_path}")
    text = config_path.read_text(encoding="utf-8", errors="replace")
    appid_s = str(appid)
    match = re.search(r'"CompatToolMapping"\s*\{', text)
    if not match:
        steam_match = re.search(r'"Steam"\s*\{', text)
        if not steam_match:
            raise SystemExit(f"could not find Steam section in {config_path}")
        insert_at = steam_match.end()
        block = (
            f'\n\t\t\t\t"CompatToolMapping"\n'
            f"\t\t\t\t{{\n"
            f'\t\t\t\t\t"{appid_s}"\n'
            f"\t\t\t\t\t{{\n"
            f'\t\t\t\t\t\t"name"\t\t"{proton}"\n'
            f'\t\t\t\t\t\t"config"\t\t""\n'
            f'\t\t\t\t\t\t"priority"\t\t"250"\n'
            f"\t\t\t\t\t}}\n"
            f"\t\t\t\t}}"
        )
        text = text[:insert_at] + block + text[insert_at:]
    else:
        start = match.start()
        depth = 0
        i = match.end() - 1
        while i < len(text):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
            i += 1
        else:
            raise SystemExit("unbalanced CompatToolMapping in config.vdf")
        new_block = _upsert_compat_block(text[start:end], appid_s, proton)
        text = text[:start] + new_block + text[end:]

    backup = config_path.with_suffix(".vdf.timesplice.bak")
    if not backup.exists():
        backup.write_text(config_path.read_text(encoding="utf-8", errors="replace"))
    config_path.write_text(text, encoding="utf-8")


def cmd_add(args: argparse.Namespace) -> int:
    exe = Path(args.exe).expanduser().resolve()
    if not exe.is_file():
        raise SystemExit(f"exe not found: {exe}")
    roots = [Path(args.steam_root)] if args.steam_root else find_steam_roots()
    if not roots:
        raise SystemExit("Steam install not found. Set STEAM_DIR or install Steam.")

    assets = Path(args.assets).expanduser() if getattr(args, "assets", None) else artwork_dir()
    written = []
    for root in roots:
        users = userdata_dirs(root)
        if args.user:
            users = [u for u in users if u.name == str(args.user)]
        if not users:
            continue
        tools = discover_proton_tools(root)
        proton = pick_proton(tools, args.proton, args.variant)
        for user in users:
            vdf_path = user / "config" / "shortcuts.vdf"
            if vdf_path.exists():
                backup = vdf_path.with_suffix(".vdf.timesplice.bak")
                if not backup.exists():
                    backup.write_bytes(vdf_path.read_bytes())
            shortcuts = load_shortcuts(vdf_path)
            exe_quoted = f'"{exe}"'
            appid = shortcut_appid(exe_quoted, args.name)
            grid_dir = user / "config" / "grid"
            art = install_artwork(grid_dir, appid, assets)
            icon = resolve_icon(appid, grid_dir, args.icon, str(exe))
            upsert_shortcut(shortcuts, name=args.name, exe=exe, icon=icon)
            save_shortcuts(vdf_path, shortcuts)
            set_compat_mapping(root / "config" / "config.vdf", appid, proton)
            written.append(
                {
                    "steam_root": str(root),
                    "user": user.name,
                    "shortcuts": str(vdf_path),
                    "appid": appid,
                    "grid_id": grid_id(appid),
                    "proton": proton,
                    "exe": str(exe),
                    "icon": icon,
                    "name": args.name,
                    "artwork": art,
                }
            )
    if not written:
        raise SystemExit("no Steam userdata profiles found")
    print(json.dumps({"ok": True, "shortcuts": written}, indent=2))
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    roots = [Path(args.steam_root)] if args.steam_root else find_steam_roots()
    removed = 0
    art_removed = 0
    for root in roots:
        for user in userdata_dirs(root):
            vdf_path = user / "config" / "shortcuts.vdf"
            if not vdf_path.exists():
                continue
            shortcuts = load_shortcuts(vdf_path)
            appids = remove_named(shortcuts, args.name)
            if appids:
                save_shortcuts(vdf_path, shortcuts)
                removed += len(appids)
                for appid in appids:
                    art_removed += remove_artwork(user / "config" / "grid", appid)
    print(json.dumps({"ok": True, "removed": removed, "artwork_removed": art_removed}))
    return 0


def cmd_artwork(args: argparse.Namespace) -> int:
    roots = [Path(args.steam_root)] if args.steam_root else find_steam_roots()
    if not roots:
        raise SystemExit("Steam install not found. Set STEAM_DIR or install Steam.")
    assets = Path(args.assets).expanduser() if args.assets else artwork_dir()
    written = []
    for root in roots:
        users = userdata_dirs(root)
        if args.user:
            users = [u for u in users if u.name == str(args.user)]
        for user in users:
            vdf_path = user / "config" / "shortcuts.vdf"
            shortcuts = load_shortcuts(vdf_path) if vdf_path.exists() else {}
            matches = [
                (key, entry)
                for key, entry in shortcuts.items()
                if entry.get("AppName") == args.name
            ]
            if not matches and args.exe:
                exe = Path(args.exe).expanduser().resolve()
                appid = shortcut_appid(f'"{exe}"', args.name)
                matches = [(None, {"appid": appid, "Exe": f'"{exe}"'})]
            if not matches:
                continue
            for key, entry in matches:
                appid = int(entry["appid"])
                grid_dir = user / "config" / "grid"
                art = install_artwork(grid_dir, appid, assets)
                icon = resolve_icon(appid, grid_dir, args.icon, str(entry.get("icon") or ""))
                if key is not None and icon:
                    shortcuts[key]["icon"] = icon
                    if vdf_path.exists():
                        backup = vdf_path.with_suffix(".vdf.timesplice.bak")
                        if not backup.exists():
                            backup.write_bytes(vdf_path.read_bytes())
                    save_shortcuts(vdf_path, shortcuts)
                written.append(
                    {
                        "steam_root": str(root),
                        "user": user.name,
                        "appid": appid,
                        "grid_id": grid_id(appid),
                        "icon": icon,
                        "artwork": art,
                    }
                )
    if not written:
        raise SystemExit(
            f"no shortcut named {args.name!r} found. Pass --exe to write grid files from a computed appid."
        )
    print(json.dumps({"ok": True, "artwork": written}, indent=2))
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    roots = [Path(args.steam_root)] if args.steam_root else find_steam_roots()
    rows = []
    for root in roots:
        info = default_install_dir(root)
        rows.append(
            {
                "steam_root": str(root),
                "default_library": info["default_library"],
                "install_dir": info["install_dir"],
                "libraries": info["libraries"],
                "proton": discover_proton_tools(root),
                "users": [u.name for u in userdata_dirs(root)],
            }
        )
    print(json.dumps(rows, indent=2))
    return 0


def cmd_libraries(args: argparse.Namespace) -> int:
    root = Path(args.steam_root) if args.steam_root else None
    print(json.dumps(default_install_dir(root), indent=2))
    return 0


def cmd_selftest(_args: argparse.Namespace) -> int:
    name = "TimeSplitters Rewind"
    exe = Path("/tmp/TimeSplittersRewind.exe")
    exe_quoted = f'"{exe}"'
    appid = shortcut_appid(exe_quoted, name)
    shortcuts: dict = {}
    upsert_shortcut(shortcuts, name=name, exe=exe, icon=str(exe))
    blob = serialize_binary_vdf({"shortcuts": shortcuts})
    assert blob[0] == 0
    key_end = blob.find(b"\x00", 1)
    parsed, _ = parse_binary_vdf(blob, key_end + 1)
    entry = next(iter(parsed.values()))
    assert entry["AppName"] == name
    assert entry["appid"] == appid
    assert entry["Exe"] == exe_quoted

    sample = """
"libraryfolders"
{
	"0"
	{
		"path"		"/home/lee/.local/share/Steam"
		"label"		""
		"contentid"		"111"
		"apps"
		{
			"228980"		"1"
		}
	}
	"1"
	{
		"path"		"/run/media/lee/game1/SteamLibrary"
		"label"		""
		"contentid"		"222"
		"apps"
		{
			"1903340"		"0"
		}
	}
	"3"
	{
		"path"		"/mnt/game1/SteamLibrary"
		"label"		""
		"contentid"		"222"
		"apps"
		{
			"553850"		"1"
		}
	}
}
"""
    parsed_libs = parse_libraryfolders(sample)
    assert [lib["path"] for lib in parsed_libs] == [
        "/home/lee/.local/share/Steam",
        "/run/media/lee/game1/SteamLibrary",
        "/mnt/game1/SteamLibrary",
    ]

    assert grid_id(3652944655) == 15689277827356557312
    assets = artwork_dir()
    for name in ("capsule.png", "header.png", "hero.png", "logo.png", "icon.png"):
        assert (assets / name).is_file(), f"missing shipped artwork {name}"
    assert png_size(assets / "header.png") == (920, 430), "header.png must be 920x430"
    assert png_size(assets / "hero.png") == (3840, 1240), "hero.png must be 3840x1240"
    tmp_grid = Path("/tmp/timesplice-selftest-grid")
    if tmp_grid.exists():
        shutil.rmtree(tmp_grid)
    files = install_artwork(tmp_grid, appid, assets)
    assert len(files) == 10
    for gid in grid_ids(appid):
        for suffix, _src in GRID_FILES:
            assert (tmp_grid / f"{gid}{suffix}").is_file()
    assert remove_artwork(tmp_grid, appid) == 10
    shutil.rmtree(tmp_grid, ignore_errors=True)

    print(json.dumps({"ok": True, "appid": appid, "grid_id": grid_id(appid)}))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Steam non-Steam shortcut helper")
    sub = parser.add_subparsers(dest="cmd", required=True)

    add = sub.add_parser("add")
    add.add_argument("--exe", required=True)
    add.add_argument("--name", default=APP_NAME_DEFAULT)
    add.add_argument("--icon")
    add.add_argument("--assets")
    add.add_argument("--proton")
    add.add_argument("--steam-root")
    add.add_argument("--user")
    add.add_argument("--variant", default="generic")
    add.set_defaults(func=cmd_add)

    remove = sub.add_parser("remove")
    remove.add_argument("--name", default=APP_NAME_DEFAULT)
    remove.add_argument("--steam-root")
    remove.set_defaults(func=cmd_remove)

    art = sub.add_parser("artwork")
    art.add_argument("--name", default=APP_NAME_DEFAULT)
    art.add_argument("--exe")
    art.add_argument("--icon")
    art.add_argument("--assets")
    art.add_argument("--steam-root")
    art.add_argument("--user")
    art.set_defaults(func=cmd_artwork)

    listed = sub.add_parser("list")
    listed.add_argument("--steam-root")
    listed.set_defaults(func=cmd_list)

    libraries = sub.add_parser("libraries")
    libraries.add_argument("--steam-root")
    libraries.set_defaults(func=cmd_libraries)

    test = sub.add_parser("selftest")
    test.set_defaults(func=cmd_selftest)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
