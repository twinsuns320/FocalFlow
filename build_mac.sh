#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="$SCRIPT_DIR/build_log.txt"

# Build natively for whatever architecture this runner is.
# We no longer attempt universal2 PyInstaller builds because
# opencv-python-headless (and often Pillow) do not ship universal2
# wheels, which breaks PyInstaller's COLLECT step with
# "is not a fat binary!" errors. Run this script once per arch
# (e.g. once on an arm64 runner, once on an x86_64 runner) via a
# GitHub Actions matrix, and ship two separate packages.
ARCH=$(uname -m)   # arm64 or x86_64
echo "Building for native arch: $ARCH"

echo "Selecting ffmpeg/ffprobe binary for $ARCH..."
if [ "$ARCH" = "arm64" ]; then
    cp "$SCRIPT_DIR/ffmpeg9arm" "$SCRIPT_DIR/ffmpeg_universal"
    cp "$SCRIPT_DIR/ffprobe9arm" "$SCRIPT_DIR/ffprobe_universal"
else
    cp "$SCRIPT_DIR/ffmpeg80intel" "$SCRIPT_DIR/ffmpeg_universal"
    cp "$SCRIPT_DIR/ffprobe80intel" "$SCRIPT_DIR/ffprobe_universal"
fi
chmod +x "$SCRIPT_DIR/ffmpeg_universal" "$SCRIPT_DIR/ffprobe_universal"

echo "Build started: $(date)" > "$LOG"
echo "Target architecture: $ARCH" | tee -a "$LOG"

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
       "$SCRIPT_DIR/dist_splash" "$SCRIPT_DIR/build_splash" \
       "$SCRIPT_DIR/dist_settings" "$SCRIPT_DIR/build_settings" \
       "$SCRIPT_DIR/compiled_license" "$SCRIPT_DIR/compiled_license_$ARCH" \
       "$SCRIPT_DIR/stage" "$SCRIPT_DIR/stage_upgrade" "$SCRIPT_DIR/stage_install" "$SCRIPT_DIR/stage_splash" "$SCRIPT_DIR/stage_settings" \
       "$SCRIPT_DIR"/*.spec "$SCRIPT_DIR"/*.so

echo "Compiling license.py for $ARCH..."
$PYTHON -m nuitka \
    --module \
    --macos-target-arch=$ARCH \
    --output-dir="$SCRIPT_DIR/compiled_license_$ARCH" \
    --assume-yes-for-downloads \
    "$SCRIPT_DIR/license.py" >> "$LOG" 2>&1

echo "Staging compiled license.so ($ARCH)..."
mkdir -p "$SCRIPT_DIR/compiled_license"
SO_FILE=$(find "$SCRIPT_DIR/compiled_license_$ARCH" -name "license*.so")
if [ -z "$SO_FILE" ]; then
    echo "ERROR: compiled license.so not found for $ARCH!" | tee -a "$LOG"
    exit 1
fi
cp "$SO_FILE" "$SCRIPT_DIR/compiled_license/license.cpython-313-darwin.so"
echo "[OK] license.so compiled for $ARCH:" | tee -a "$LOG"
lipo -info "$SCRIPT_DIR/compiled_license/license.cpython-313-darwin.so" | tee -a "$LOG"

echo "Staging FocalFlow build folder..."
STAGE="$SCRIPT_DIR/stage"
rm -rf "$STAGE"
mkdir -p "$STAGE"
cp "$SCRIPT_DIR/focalflow.py" "$STAGE/"
cp "$SCRIPT_DIR/focal_paths.py" "$STAGE/"
cp "$SCRIPT_DIR"/compiled_license/license*.so "$STAGE/"

echo "Building FocalFlow.app (native $ARCH)..."
$PYTHON -m PyInstaller \
    --noconfirm \
    --windowed \
    --target-architecture $ARCH \
    --hidden-import=hmac \
    --hidden-import=hashlib \
    --hidden-import=base64 \
    --hidden-import=platform \
    --hidden-import=subprocess \
    --hidden-import=urllib.request \
    --hidden-import=urllib.parse \
    --hidden-import=json \
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

echo "Building upgrade_FocalFlow (native $ARCH)..."
$PYTHON -m PyInstaller \
    --noconfirm \
    --onefile \
    --console \
    --target-architecture $ARCH \
    --hidden-import=hmac \
    --hidden-import=hashlib \
    --hidden-import=base64 \
    --hidden-import=platform \
    --hidden-import=subprocess \
    --hidden-import=urllib.request \
    --hidden-import=urllib.parse \
    --hidden-import=json \
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

echo "Building install_FocalFlow (native $ARCH)..."
$PYTHON -m PyInstaller \
    --noconfirm \
    --onefile \
    --console \
    --target-architecture $ARCH \
    --hidden-import=hmac \
    --hidden-import=hashlib \
    --hidden-import=base64 \
    --hidden-import=platform \
    --hidden-import=subprocess \
    --hidden-import=urllib.request \
    --hidden-import=urllib.parse \
    --hidden-import=json \
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

echo "Staging splash_FocalFlow build folder..."
STAGE_SPLASH="$SCRIPT_DIR/stage_splash"
rm -rf "$STAGE_SPLASH"
mkdir -p "$STAGE_SPLASH"
cp "$SCRIPT_DIR/splash_FocalFlow.py" "$STAGE_SPLASH/"

echo "Building splash_FocalFlow (native $ARCH)..."
$PYTHON -m PyInstaller \
    --noconfirm \
    --windowed \
    --target-architecture $ARCH \
    --name splash_FocalFlow \
    --distpath "$SCRIPT_DIR/dist_splash" \
    --workpath "$SCRIPT_DIR/build_splash" \
    "$STAGE_SPLASH/splash_FocalFlow.py" >> "$LOG" 2>&1

if [ -d "$SCRIPT_DIR/dist_splash/splash_FocalFlow.app" ]; then
    echo "[OK] Splash build complete." | tee -a "$LOG"
    lipo -info "$SCRIPT_DIR/dist_splash/splash_FocalFlow.app/Contents/MacOS/splash_FocalFlow" | tee -a "$LOG"
else
    echo "ERROR: splash_FocalFlow.app not found after build!" | tee -a "$LOG"
    exit 1
fi


echo "Staging Settings_FocalFlow build folder..."
STAGE_SETTINGS="$SCRIPT_DIR/stage_settings"
rm -rf "$STAGE_SETTINGS"
mkdir -p "$STAGE_SETTINGS"
cp "$SCRIPT_DIR/settings_app.py" "$STAGE_SETTINGS/"
cp "$SCRIPT_DIR/focal_paths.py" "$STAGE_SETTINGS/"

echo "Building Settings_FocalFlow (native $ARCH)..."
$PYTHON -m PyInstaller \
    --noconfirm \
    --windowed \
    --target-architecture $ARCH \
    --name Settings_FocalFlow \
    --distpath "$SCRIPT_DIR/dist_settings" \
    --workpath "$SCRIPT_DIR/build_settings" \
    "$STAGE_SETTINGS/settings_app.py" >> "$LOG" 2>&1

if [ -d "$SCRIPT_DIR/dist_settings/Settings_FocalFlow.app" ]; then
    echo "[OK] Settings app build complete." | tee -a "$LOG"
else
    echo "ERROR: Settings_FocalFlow.app not found after build!" | tee -a "$LOG"
    exit 1
fi