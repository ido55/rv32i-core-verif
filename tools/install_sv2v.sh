#!/usr/bin/env bash
# Install the pinned sv2v release (SystemVerilog -> Verilog-2005 converter) into $1
# (default ~/.local/bin). Used by CI and the Dockerfile; checks the download's SHA-256.
#
# Why: Yosys 0.33's own SystemVerilog parser rejects parts of standard SV that this RTL
# uses (package imports in module headers, `inside`). sv2v converts the RTL to plain
# Verilog for synthesis only; simulation and lint still read the original SystemVerilog.
set -euo pipefail

VERSION=v0.0.13
SHA256=552799a1d76cd177b9b4cc63a3e77823a3d2a6eb4ec006569288abeff28e1ff8
DEST=${1:-$HOME/.local/bin}

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
curl -sSfL -o "$tmp/sv2v.zip" "https://github.com/zachjs/sv2v/releases/download/$VERSION/sv2v-Linux.zip"
echo "$SHA256  $tmp/sv2v.zip" | sha256sum --check --quiet
python3 -c "import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" \
    "$tmp/sv2v.zip" "$tmp"
mkdir -p "$DEST"
install -m 755 "$tmp/sv2v-Linux/sv2v" "$DEST/sv2v"
"$DEST/sv2v" --version
