#!/bin/sh
# Install PySnake system-wide, with its menu entry and icon.
#
#   sudo ./install.sh              install the PySnake program next to this script
#   sudo ./install.sh PATH         install the program at PATH instead
#   sudo ./install.sh --uninstall  remove everything this script installed
#
# Set PREFIX to install somewhere other than /usr (e.g. PREFIX=$HOME/.local).
set -e

here=$(cd "$(dirname "$0")" && pwd)
prefix=${PREFIX:-/usr}
apps="$prefix/share/applications"
icons="$prefix/share/icons/hicolor"

refresh() {
    command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q "$apps" || true
    command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -q -t "$icons" || true
}

if [ "$1" = "--uninstall" ]; then
    rm -f "$prefix/bin/pysnake" "$apps/pysnake.desktop" \
          "$icons/scalable/apps/pysnake.svg" "$icons/256x256/apps/pysnake.png"
    refresh
    echo "PySnake removed."
    exit 0
fi

program=${1:-$here/PySnake}
if [ ! -f "$program" ]; then
    echo "Can't find the PySnake program at $program" >&2
    echo "Pass its path: sudo ./install.sh /path/to/PySnake" >&2
    exit 1
fi

install -Dm755 "$program" "$prefix/bin/pysnake"
install -Dm644 "$here/pysnake.desktop" "$apps/pysnake.desktop"
install -Dm644 "$here/pysnake.svg" "$icons/scalable/apps/pysnake.svg"
install -Dm644 "$here/pysnake-256.png" "$icons/256x256/apps/pysnake.png"
if [ "$prefix" != "/usr" ]; then
    # The menu entry points at /usr/bin by default; follow the chosen prefix.
    sed -i "s|^Exec=.*|Exec=$prefix/bin/pysnake|" "$apps/pysnake.desktop"
fi
refresh
echo "PySnake installed: run 'pysnake' or find it in your applications menu."
