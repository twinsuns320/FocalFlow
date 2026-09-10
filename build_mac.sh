#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="$SCRIPT_DIR/build_log.txt"

echo "Build started: $(date)" > "$LOG"

PYTHON=python3.13
if ! command -v $PYTHON &> /dev/null; then
    echo "ERROR: python3.13 not found. Install via python.org or brew." | tee -a "$LOG"
    exit 1
fi

echo "[OK] Python found: $($PYTHON --version)" | tee -a "$LOG"

echo "Installing Nuitka..."
$PYTHON -m pip install --upgrade nuitka ordered-set zstandard >> "$LOG" 2>&1

echo "Cleaning old build artifacts..."
rm -rf "$SCRIPT_DIR/dist" "$SCRIPT_DIR/build" "$SCRIPT_DIR"/*.app

echo "Building FocalFlow.app..."
$PYTHON -m nuitka \
    --mode=standalone \
    --macos-create-app-bundle \
    --enable-plugin=pyqt6 \
    --include-qt-plugins=platforms,imageformats,styles \
    --include-package=PIL \
    --include-package=cv2 \
    --include-package=numpy \
    --include-package=PyQt6 \
    --assume-yes-for-downloads \
    --show-progress \
    --output-dir="$SCRIPT_DIR/dist" \
    --output-filename=FocalFlow \
    --report="$SCRIPT_DIR/nuitka_report_focalflow.xml" \
    --main="$SCRIPT_DIR/focalflow.py" >> "$LOG" 2>&1

echo "[OK] Build complete. Output: $SCRIPT_DIR/dist/FocalFlow.app" | tee -a "$LOG"

# Optional, once you have a Developer ID (add after $99 step):
# --macos-sign-identity="Developer ID Application: Your Name (TEAMID)"