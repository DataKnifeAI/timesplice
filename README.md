# timesplice

![timesplice — splice TimeSplitters Rewind onto Linux Steam](docs/assets/timesplice-hero.jpg)

Art: [TimeSplitters Rewind](https://www.timesplittersrewind.com/) — Early Access trailer https://www.youtube.com/watch?v=ZzWSrgQ3eMI

Splices [TimeSplitters Rewind](https://www.timesplittersrewind.com/) onto Linux Steam as a **non-Steam game** with Proton forced on.

## Usage

CachyOS is the primary target. Arch, Fedora, Debian/Ubuntu, and SteamOS work with the same flags.

There is no native Linux build. timesplice downloads the official Windows Early Access zip (or uses one you already have), extracts it, writes `shortcuts.vdf`, and maps the shortcut to Proton.

Restart Steam and launch TimeSplitters Rewind from the library.

Steam Input / Xbox pad works under Proton. The game does not show controller glyphs. Keep a keyboard and mouse nearby for a few screens.

## Install

```bash
# after cloning
./bin/timesplice install --install-deps --shutdown-steam
```

One-liner after this repo is on GitHub:

```bash
curl -fsSL https://raw.githubusercontent.com/DataKnifeAI/timesplice/main/install.sh | bash
```

`--install-deps` installs `curl`, `unzip`, `python3`, and `steam` when they are missing.

Need ~50 GiB free while the zip and extracted tree both exist. The zip is deleted after extract unless `--keep-zip`.

## What it does

1. Installs `curl`, `unzip`, `python3`, and `steam` if you pass `--install-deps`.
2. Downloads Early Access v0.3 (~13.5 GiB) from the Archive.org mirror (IndieDB is Cloudflare-gated and not scriptable). Use `--source official` to print the [IndieDB](https://www.indiedb.com/games/timesplitters-rewind1/downloads/timesplitters-rewind-early-access-v03) page and require `--from`.
3. Extracts `TimeSplittersRewind.exe`.
4. Quits Steam if needed (`--shutdown-steam`) so it does not overwrite `shortcuts.vdf`.
5. Adds **TimeSplitters Rewind** to every local Steam profile as a non-Steam shortcut, with Rewind library artwork and the official TSR icon.
6. Forces Proton: `proton-cachyos` on CachyOS when installed, otherwise **Proton 10**, then Experimental.

Same flow as adding the `.exe` by hand, without the clicks.

## Troubleshooting

- **`timesplice doctor`** — Steam root, libraries, Proton, disk, and whether `TimeSplittersRewind.exe` is present.
- **Steam overwrites the shortcut** — quit Steam first, or pass `--shutdown-steam`. If Steam is still running after a shutdown request, quit it fully and re-run.
- **Low disk space** — plan on ~50 GiB while the zip and extracted tree both exist. The zip is ~13.5 GiB; the installed tree is ~35 GiB.
- **Official IndieDB zip** — `--source official` prints the download page and requires `--from`. IndieDB is Cloudflare-gated and not scriptable.
- **Already extracted** — `timesplice install --from /path/to/TimeSplittersRewind` (or `timesplice shortcut`) writes the shortcut without downloading again.
- **Wrong library** — pass `--library`, `--dir`, or `TIMESPLICE_DIR`. `doctor` shows which folder was chosen.
- **Uninstall** — `timesplice uninstall` removes the shortcut and grid art. Game files stay on disk.

Library selection, `--from` / `--library` / `--dir`, artwork re-apply, and the full flag list: [docs/USAGE.md](docs/USAGE.md).

TimeSplitters Rewind is a fan project and is not affiliated with the original creators. This repo only automates the Linux Steam setup.

## License

MIT — see [LICENSE](LICENSE).
