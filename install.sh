#!/usr/bin/env bash
# Bootstrap timesplice — clone or refresh, then run timesplice install.
set -euo pipefail

REPO="${TIMESPLICE_REPO:-https://github.com/DataKnifeAI/timesplice.git}"
DIR="${TIMESPLICE_SRC:-$HOME/.local/share/timesplice/src}"
BIN_DIR="${TIMESPLICE_BIN:-$HOME/.local/bin}"

if [[ -d "$DIR/.git" ]]; then
  git -C "$DIR" pull --ff-only
else
  mkdir -p "$(dirname "$DIR")"
  git clone "$REPO" "$DIR"
fi

mkdir -p "$BIN_DIR"
ln -sfn "$DIR/bin/timesplice" "$BIN_DIR/timesplice"

exec "$DIR/bin/timesplice" install "$@"
