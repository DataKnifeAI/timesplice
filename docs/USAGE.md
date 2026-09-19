# Advanced usage

Everyday install, what timesplice does, and troubleshooting live on the [project README](../README.md). This page covers library overrides, `--from`, artwork re-apply, flags, and env vars.

## Install from a zip or extracted tree

```bash
# You already downloaded the IndieDB zip
./bin/timesplice install --from ~/Downloads/TimeSplittersRewind_EarlyAccess_V03.3.zip

# Game is already extracted
./bin/timesplice install --from /mnt/game1/SteamLibrary/TimeSplittersRewind --shutdown-steam
```

`--from` accepts a zip or an extracted tree. Override the install location with `--library`, `--dir`, or `$TIMESPLICE_DIR` (see below).

## Steam library selection

Install path comes from Steam's `libraryfolders.vdf`: extra libraries first (the game drives), Steam root only if that is the only folder. Duplicate `/run/media` vs `/mnt` entries for the same `contentid` collapse to the mounted writable path.

Override with `--library`, `--dir`, or `$TIMESPLICE_DIR`. `--library PATH` installs into `PATH/TimeSplittersRewind`.

`timesplice doctor` prints the chosen library and every folder Steam knows about.

## Commands

| Command | Purpose |
| --- | --- |
| `timesplice install` | Download/extract + Steam shortcut + artwork |
| `timesplice shortcut` | Shortcut + artwork |
| `timesplice artwork` | Artwork only (existing shortcut) |
| `timesplice doctor` | Steam, Proton, disk, exe |
| `timesplice uninstall` | Remove the shortcut and grid art (keeps files) |

```text
--from PATH       zip or extracted tree
--dir PATH        install directory
--library PATH    Steam library folder (installs into PATH/TimeSplittersRewind)
--proton NAME     compat tool internal name
--source archive  Archive.org (default)
--source official IndieDB instructions
--yes             non-interactive
--keep-zip
--shutdown-steam
--install-deps
```

`TIMESPLICE_DIR` overrides the install directory. `STEAM_DIR` points at a Steam root (native or Flatpak data dir).

## Artwork

Steam has **no store details page** for non-Steam games. `shortcuts.vdf` can store a name, exe, start dir, icon, and launch options — not a description. Launch options are passed to the game, so timesplice does not put a blurb there. Steam Game Notes are personal overlay notes, not a public about-this-game field.

What *does* work is custom artwork in `userdata/<id>/config/grid/`. timesplice writes both the 32-bit shortcut appid and the 64-bit grid id `(appid << 32) | 0x02000000`:

| File | Steam use |
| --- | --- |
| `{id}p.png` | Portrait library capsule |
| `{id}.png` | Landscape header |
| `{id}_hero.png` | Library hero |
| `{id}_logo.png` | Transparent logo overlay |
| `{id}_icon.png` | List / shortcut icon |

Art is Rewind's own marketing (official wordmark, TSR mark, Early Access trailer still). Original-trilogy box art on the about page is not used. Sources: [assets/SOURCES.txt](assets/SOURCES.txt) and [assets/steam-grid/SOURCES.txt](assets/steam-grid/SOURCES.txt).

Re-apply without rewriting the shortcut:

```bash
./bin/timesplice artwork --shutdown-steam
```

## Controller notes

Steam Input / Xbox pad works under Proton. The game does not show controller glyphs. Keep a keyboard and mouse nearby for a few screens.
