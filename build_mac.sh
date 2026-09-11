#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="$SCRIPT_DIR/build_log.txt"

echo "Merging ffmpeg/ffprobe into universal2 binaries..."
lipo -create "$SCRIPT_DIR/ffmpeg9arm" "$SCRIPT_DIR/ffmpeg80intel" -output "$SCRIPT_DIR/ffmpeg_universal"
lipo -create "$SCRIPT_DIR/ffprobe9arm" "$SCRIPT_DIR/ffprobe80intel" -output "$SCRIPT_DIR/ffprobe_universal"
chmod +x "$SCRIPT_DIR/ffmpeg_universal" "$SCRIPT_DIR/ffprobe_universal"

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
       "$SCRIPT_DIR/compiled_license" "$SCRIPT_DIR/stage" "$SCRIPT_DIR/stage_upgrade" "$SCRIPT_DIR/stage_install" \
       "$SCRIPT_DIR"/*.spec "$SCRIPT_DIR"/*.so

echo "Compiling license.py for arm64..."
$PYTHON -m nuitka \
    --module \
    --macos-target-arch=arm64 \
    --output-dir="$SCRIPT_DIR/compiled_license_arm64" \
    --assume-yes-for-downloads \
    "$SCRIPT_DIR/license.py" >> "$LOG" 2>&1

echo "Compiling license.py for x86_64..."
$PYTHON -m nuitka \
    --module \
    --macos-target-arch=x86_64 \
    --output-dir="$SCRIPT_DIR/compiled_license_x86_64" \
    --assume-yes-for-downloads \
    "$SCRIPT_DIR/license.py" >> "$LOG" 2>&1

echo "Merging license.so into a universal2 binary with lipo..."
mkdir -p "$SCRIPT_DIR/compiled_license"
ARM_SO=$(find "$SCRIPT_DIR/compiled_license_arm64" -name "license*.so")
X86_SO=$(find "$SCRIPT_DIR/compiled_license_x86_64" -name "license*.so")
lipo -create "$ARM_SO" "$X86_SO" -output "$SCRIPT_DIR/compiled_license/license.cpython-313-darwin.so"
echo "[OK] license.so is now universal2:" | tee -a "$LOG"
lipo -info "$SCRIPT_DIR/compiled_license/license.cpython-313-darwin.so" | tee -a "$LOG"

echo "Staging FocalFlow build folder..."
STAGE="$SCRIPT_DIR/stage"
rm -rf "$STAGE"
mkdir -p "$STAGE"
cp "$SCRIPT_DIR/focalflow.py" "$STAGE/"
cp "$SCRIPT_DIR/focal_paths.py" "$STAGE/"
cp "$SCRIPT_DIR"/compiled_license/license*.so "$STAGE/"

echo "Building FocalFlow.app (universal2)..."
$PYTHON -m PyInstaller \
    --noconfirm \
    --windowed \
    --target-architecture universal2 \
    --exclude-module PIL._avif \
    --name FocalFlow \
    --distpath "$SCRIPT_DIR/dist" \
    --workpath "$SCRIPT_DIR/build" \
    "$STAGE/focalflow.py" >> "$LOG" 2>&1

echo "[OK] FocalFlow build complete." | tee -a "$LOG"
lipo -info "$SCRIPT_DIR/dist/FocalFlow.app/Contents/MacOS/FocalFlow" | tee -a "$LOG"

echo "Staging upgrade_FocalFlow build folder..."
STAGE_UP="$SCRIPT_DIR/stage_upgrade"
rm -rf "$STAGE_UP"
mkdir -p "$STAGE_UP"
cp "$SCRIPT_DIR/upgrade_FocalFlow.py" "$STAGE_UP/"
cp "$SCRIPT_DIR"/compiled_license/license*.so "$STAGE_UP/"

echo "Building upgrade_FocalFlow (universal2)..."
$PYTHON -m PyInstaller \
    --noconfirm \
    --onefile \
    --console \
    --target-architecture universal2 \
    --exclude-module PIL._avif \
    --name upgrade_FocalFlow \
    --distpath "$SCRIPT_DIR/dist_upgrade" \
    --workpath "$SCRIPT_DIR/build_upgrade" \
    "$STAGE_UP/upgrade_FocalFlow.py" >> "$LOG" 2>&1

if [ -f "$SCRIPT_DIR/dist_upgrade/upgrade_FocalFlow" ]; then
    echo "[OK] Upgrade tool build complete." | tee -a "$LOG"
    lipo -info "$SCRIPT_DIR/dist_upgrade/upgrade_FocalFlow" | tee -a "$LOG"
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

echo "Building install_FocalFlow (universal2)..."
$PYTHON -m PyInstaller \
    --noconfirm \
    --onefile \
    --console \
    --target-architecture universal2 \
    --exclude-module PIL._avif \
    --name install_FocalFlow \
    --distpath "$SCRIPT_DIR/dist_install" \
    --workpath "$SCRIPT_DIR/build_install" \
    "$STAGE_INST/install_mac.py" >> "$LOG" 2>&1

if [ -f "$SCRIPT_DIR/dist_install/install_FocalFlow" ]; then
    echo "[OK] Installer build complete." | tee -a "$LOG"
    lipo -info "$SCRIPT_DIR/dist_install/install_FocalFlow" | tee -a "$LOG"
else
    echo "ERROR: install_FocalFlow binary not found after build!" | tee -a "$LOG"
    exit 1
fi