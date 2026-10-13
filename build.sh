#!/usr/bin/env bash
# Packs chocobo_tales/ into chocobo_tales.apworld; installs it unless --package-only is passed.
set -euo pipefail
cd "$(dirname "$0")"
if [[ $# -gt 1 || ( $# -eq 1 && "$1" != "--package-only" ) ]]; then
    echo "Usage: $0 [--package-only]" >&2
    exit 2
fi
rm -f chocobo_tales.apworld
find chocobo_tales -name __pycache__ -prune -exec rm -rf {} +
python3 -I -c '
import pathlib, zipfile
with zipfile.ZipFile("chocobo_tales.apworld", "w", zipfile.ZIP_DEFLATED) as z:
    for path in sorted(pathlib.Path("chocobo_tales").rglob("*")):
        if path.is_file():
            z.write(path)
'
if [[ "${1:-}" == "--package-only" ]]; then
    echo "Built $(pwd)/chocobo_tales.apworld"
    exit 0
fi
install_dir="${HOME}/.local/share/Archipelago/worlds"
mkdir -p "$install_dir"
cp chocobo_tales.apworld "$install_dir/"
echo "Installed $install_dir/chocobo_tales.apworld"
