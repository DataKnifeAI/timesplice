# Usage

CachyOS is the primary target. Arch, Fedora, Debian/Ubuntu, and SteamOS work with the same flags.

There is no native Linux build. timesplice downloads the official Windows Early Access zip (or uses one you already have), extracts it, writes `shortcuts.vdf`, and maps the shortcut to Proton.

## Install

```bash
# CachyOS / Arch / Fedora / Debian — after cloning
./bin/timesplice install --install-deps --shutdown-steam

# You already downloaded the IndieDB zip
./bin/timesplice install --from ~/Downloads/TimeSplittersRewind_EarlyAccess_V03.3.zip

# Game is already extracted
./bin/timesplice install --from /mnt/game1/SteamLibrary/TimeSplittersRewind --shutdown-steam
```

One-liner after this repo is on GitHub:

```bash
curl -fsSL https://raw.githubusercontent.com/DataKnifeAI/timesplice/main/install.sh | bash
```

`--install-deps` installs `curl`, `unzip`, `python3`, and `steam` when they are missing.

Need ~50 GiB free while the zip and extracted tree both exist. The zip is deleted after extract unless `--keep-zip`.

## Steam library selection

Install path comes from Steam's `libraryfolders.vdf`: extra libraries first (the game drives), Steam root only if that is the only folder. Duplicate `/run/media` vs `/mnt` entries for the same `contentid` collapse to the mounted writable path.

Override with `--library`, `--dir`, or `$TIMESPLICE_DIR`. `--library PATH` installs into `PATH/TimeSplittersRewind`.

`timesplice doctor` prints the chosen library and every folder Steam knows about.

## What it does

1. Installs `curl`, `unzip`, `python3`, and `steam` if you pass `--install-deps`.
2. Downloads Early Access v0.3 (~13.5 GiB) from the Archive.org mirror (IndieDB is Cloudflare-gated and not scriptable). Use `--source official` to print the [IndieDB](https://www.indiedb.com/games/timesplitters-rewind1/downloads/timesplitters-rewind-early-access-v03) page and require `--from`.
3. Extracts `TimeSplittersRewind.exe`.
4. Quits Steam if needed (`--shutdown-steam`) so it does not overwrite `shortcuts.vdf`.
5. Adds **TimeSplitters Rewind** to every local Steam profile as a non-Steam shortcut, with Rewind library artwork and the official TSR icon.
6. Forces Proton: `proton-cachyos` on CachyOS when installed, otherwise **Proton 10**, then Experimental.

Same flow as adding the `.exe` by hand, without the clicks.

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

## Troubleshooting

- **`timesplice doctor`** — Steam root, libraries, Proton, disk, and whether `TimeSplittersRewind.exe` is present.
- **Steam overwrites the shortcut** — quit Steam first, or pass `--shutdown-steam`. If Steam is still running after a shutdown request, quit it fully and re-run.
- **Low disk space** — plan on ~50 GiB while the zip and extracted tree both exist. The zip is ~13.5 GiB; the installed tree is ~35 GiB.
- **Official IndieDB zip** — `--source official` prints the download page and requires `--from`. IndieDB is Cloudflare-gated and not scriptable.
- **Already extracted** — `timesplice install --from /path/to/TimeSplittersRewind` (or `timesplice shortcut`) writes the shortcut without downloading again.
- **Wrong library** — pass `--library`, `--dir`, or `TIMESPLICE_DIR`. `doctor` shows which folder was chosen.
- **Uninstall** — `timesplice uninstall` removes the shortcut and grid art. Game files stay on disk.

## Credits

Official site: https://www.timesplittersrewind.com/ — Early Access trailer: https://www.youtube.com/watch?v=ZzWSrgQ3eMI

TimeSplitters Rewind is a fan project and is not affiliated with the original creators. This repo only automates the Linux Steam setup.
