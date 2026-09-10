#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="$SCRIPT_DIR/build_log.txt"

echo "Build started: $(date)" > "$LOG"

PYTHON=python3.13
if ! command -v $PYTHON &> /dev/null; then
    echo "ERROR: python3.13 not found." | tee -a "$LOG"
    exit 1
fi

echo "[OK] Python found: $($PYTHON --version)" | tee -a "$LOG"

echo "Installing Nuitka, PyInstaller, and dependencies..."
$PYTHON -m pip install --upgrade nuitka ordered-set zstandard \
    pyinstaller PyQt6 opencv-python-headless numpy pillow >> "$LOG" 2>&1

echo "Cleaning old build artifacts..."
rm -rf "$SCRIPT_DIR/dist" "$SCRIPT_DIR/build" \
       "$SCRIPT_DIR/dist_upgrade" "$SCRIPT_DIR/build_upgrade" \
       "$SCRIPT_DIR/dist_install" "$SCRIPT_DIR/build_install" \
       "$SCRIPT_DIR/compiled_license" "$SCRIPT_DIR/stage" "$SCRIPT_DIR/stage_upgrade" \
       "$SCRIPT_DIR"/*.spec "$SCRIPT_DIR"/*.so

echo "Compiling license.py to a native extension with Nuitka..."
$PYTHON -m nuitka \
    --module \
    --output-dir="$SCRIPT_DIR/compiled_license" \
    --assume-yes-for-downloads \
    "$SCRIPT_DIR/license.py" >> "$LOG" 2>&1

echo "[OK] license.py compiled. Output: $SCRIPT_DIR/compiled_license" | tee -a "$LOG"

echo "Staging FocalFlow build folder with compiled license module..."
STAGE="$SCRIPT_DIR/stage"
rm -rf "$STAGE"
mkdir -p "$STAGE"
cp "$SCRIPT_DIR/focalflow.py" "$STAGE/"
cp "$SCRIPT_DIR/focal_paths.py" "$STAGE/"
cp "$SCRIPT_DIR"/compiled_license/license*.so "$STAGE/"

echo "Building FocalFlow.app (GUI plain, license.py compiled)..."
$PYTHON -m PyInstaller \
    --noconfirm \
    --windowed \
    --name FocalFlow \
    --distpath "$SCRIPT_DIR/dist" \
    --workpath "$SCRIPT_DIR/build" \
    "$STAGE/focalflow.py" >> "$LOG" 2>&1

echo "[OK] FocalFlow build complete. Output: $SCRIPT_DIR/dist/FocalFlow.app" | tee -a "$LOG"

echo "Staging upgrade_FocalFlow build folder..."
STAGE_UP="$SCRIPT_DIR/stage_upgrade"
rm -rf "$STAGE_UP"
mkdir -p "$STAGE_UP"
cp "$SCRIPT_DIR/upgrade_FocalFlow.py" "$STAGE_UP/"
cp "$SCRIPT_DIR"/compiled_license/license*.so "$STAGE_UP/"

echo "Building upgrade_FocalFlow binary..."
$PYTHON -m PyInstaller \
    --noconfirm \
    --onefile \
    --console \
    --name upgrade_FocalFlow \
    --distpath "$SCRIPT_DIR/dist_upgrade" \
    --workpath "$SCRIPT_DIR/build_upgrade" \
    "$STAGE_UP/upgrade_FocalFlow.py" >> "$LOG" 2>&1

if [ -f "$SCRIPT_DIR/dist_upgrade/upgrade_FocalFlow" ]; then
    echo "[OK] Upgrade tool build complete. Output: $SCRIPT_DIR/dist_upgrade/upgrade_FocalFlow" | tee -a "$LOG"
else
    echo "ERROR: upgrade_FocalFlow binary not found after build!" | tee -a "$LOG"
    exit 1
fi

echo "Staging install_FocalFlow build folder..."
STAGE_INST="$SCRIPT_DIR/stage_install"
rm -rf "$STAGE_INST"
mkdir -p "$STAGE_INST"
cp "$SCRIPT_DIR/install_mac.py" "$STAGE_INST/"
cp "$SCRIPT_DIR/focal_paths.py" "$STAGE_INST/"
cp "$SCRIPT_DIR"/compiled_license/license*.so "$STAGE_INST/"

echo "Building install_FocalFlow binary..."
$PYTHON -m PyInstaller \
    --noconfirm \
    --onefile \
    --console \
    --name install_FocalFlow \
    --distpath "$SCRIPT_DIR/dist_install" \
    --workpath "$SCRIPT_DIR/build_install" \
    "$STAGE_INST/install_mac.py" >> "$LOG" 2>&1

if [ -f "$SCRIPT_DIR/dist_install/install_FocalFlow" ]; then
    echo "[OK] Installer build complete. Output: $SCRIPT_DIR/dist_install/install_FocalFlow" | tee -a "$LOG"
else
    echo "ERROR: install_FocalFlow binary not found after build!" | tee -a "$LOG"
    exit 1
fi