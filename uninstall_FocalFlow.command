#!/bin/bash
echo
echo "  =========================================="
echo "   FOCALFLOW UNINSTALLER"
echo "  =========================================="
echo
echo "  This will remove FocalFlow from this machine."
echo "  Your rendered videos will NOT be deleted."
echo
read -p "Press Enter to continue..."

# ── Find install location from config file ───────────────────────────────────
CONFIG_PATH="$HOME/Library/Application Support/FocalFlow/config.json"
if [ ! -f "$CONFIG_PATH" ]; then
    echo "FocalFlow does not appear to be installed."
    echo "Nothing to remove."
    read -p "Press Enter to exit..."
    exit 0
fi

INSTALL_DIR=$(python3 -c "import json; print(json.load(open('$CONFIG_PATH')).get('install_dir',''))" 2>/dev/null)

if [ -z "$INSTALL_DIR" ]; then
    echo "FocalFlow does not appear to be installed."
    echo "Nothing to remove."
    read -p "Press Enter to exit..."
    exit 0
fi

echo "Found install at: $INSTALL_DIR"
echo

# ── Remove bundled Python from user PATH ──────────────────────────────────────
echo "Cleaning up PATH..."
# Not applicable on macOS — FocalFlow.app is self-contained and was never
# added to PATH, so there's nothing to remove here.
echo "Done."

# ── Remove main install folder (the whole FocalFlow folder) ──────────────────
echo "Removing FocalFlow files..."
if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
    if [ -d "$INSTALL_DIR" ]; then
        echo "WARNING: Could not fully remove $INSTALL_DIR - try running with sudo."
    else
        echo "Done."
    fi
else
    echo "Install folder not found, skipping."
fi

# ── Remove Resolve scripts ─────────────────────────────────────────────────────
echo "Removing Resolve scripts..."
RS="$HOME/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Comp"
[ -f "$RS/launch_FocalFlow.py" ]       && rm -f "$RS/launch_FocalFlow.py"
[ -f "$RS/place_result_FocalFlow.py" ] && rm -f "$RS/place_result_FocalFlow.py"
[ -f "$RS/settings_FocalFlow.py" ]     && rm -f "$RS/settings_FocalFlow.py"
echo "Done."

# ── Remove config entries ──────────────────────────────────────────────────────
echo "Removing configuration..."
rm -rf "$HOME/Library/Application Support/FocalFlow"
echo "Done."

# ── Remove leftover temp files ─────────────────────────────────────────────────
echo "Cleaning up temp files..."
rm -f "${TMPDIR}focalflow_progress.txt" 2>/dev/null
echo "Done."

# ── Done ────────────────────────────────────────────────────────────────────────
echo
echo "  =========================================="
echo "   FOCALFLOW REMOVED SUCCESSFULLY"
echo "  =========================================="
echo
echo "  Your rendered videos in FocalFlow folders"
echo "  next to your source footage are untouched."
echo
read -p "Press Enter to exit..."