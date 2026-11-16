#!/bin/sh
# Build the browser version of PySnake with pygbag.
#
#   web-support/build.sh        build into web-support/build/pysnake/build/web/
#
# Needs: pip install pygbag, and the opensnake package (the game rules; it's a
# dependency of PySnake, so `pip install -e .` brings it).
#
# To put it on an OpenSnake server, copy build/web/ into the server's
# web-support/clients/<name>/ (see the server's README).
set -e
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/.." && pwd)
final="$here/build/pysnake"
# Build next to the current build and only swap it in once it works, so a
# failed build (no internet, say) leaves the old one in place.
src="$here/build/next/pysnake"
python=${PYTHON:-python3}

rm -rf "$here/build/next"
mkdir -p "$src"
cp "$here/main.py" "$src/main.py"
# The game, and the rules it plays by (the opensnake package, without its server).
(cd "$root" && tar --exclude='__pycache__' -cf - pysnake) | (cd "$src" && tar -xf -)
rules=$("$python" -c 'import opensnake, os; print(os.path.dirname(opensnake.__file__))')
(cd "$(dirname "$rules")" && tar --exclude='__pycache__' --exclude='opensnake/server.py' -cf - opensnake) | (cd "$src" && tar -xf -)
cp "$root/packaging/linux/pysnake-256.png" "$src/favicon.png"

"$python" -m pygbag --build --title PySnake "$src"

# Name the game files after their contents (pysnake-<hash>.tar.gz) and point
# index.html at them, so a browser can't keep playing an old copy.
"$python" - "$src/build/web" <<'PY'
import hashlib, sys
from pathlib import Path
web = Path(sys.argv[1])
page = web / "index.html"
html = page.read_text(encoding="utf-8")
for ext in ("tar.gz", "apk"):
    old = web / f"pysnake.{ext}"
    new = f"pysnake-{hashlib.sha256(old.read_bytes()).hexdigest()[:12]}.{ext}"
    assert html.count(f'"{old.name}"') == 1, f"index.html doesn't load {old.name} the expected way"
    html = html.replace(f'"{old.name}"', f'"{new}"')
    old.rename(web / new)
page.write_text(html, encoding="utf-8")
PY
rm -rf "$final.old"
if [ -d "$final" ]; then mv "$final" "$final.old"; fi
mv "$src" "$final"
rm -rf "$final.old" "$here/build/next"
echo "Built: $final/build/web/"
