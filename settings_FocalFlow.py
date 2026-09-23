import sys, os

try:
    _SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _SCRIPT_DIR = os.path.expanduser("~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Comp")
if _SCRIPT_DIR not in sys.path:
    sys.path.append(_SCRIPT_DIR)

import focal_paths

LOG = os.path.join(os.path.expanduser("~"), "focal_settings_log.txt")

def _log(msg):
    try:
        with open(LOG, "a") as f:
            f.write(msg + "\n")
    except Exception:
        pass

if focal_paths.IS_MAC:
    import subprocess, traceback
    INSTALL_DIR = focal_paths.get_install_dir()
    SETTINGS_APP_PATH = os.path.join(
        INSTALL_DIR, "Settings_FocalFlow.app", "Contents", "MacOS", "Settings_FocalFlow")
    try:
        if not os.path.isfile(SETTINGS_APP_PATH):
            _log(f"Settings app not found at: {SETTINGS_APP_PATH}")
            subprocess.run(["osascript", "-e",
                f'display alert "FocalFlow Settings" message '
                f'"App not found at:\\n{SETTINGS_APP_PATH}\\n\\nReinstall FocalFlow." as critical'])
        else:
            subprocess.Popen([SETTINGS_APP_PATH])
    except Exception:
        _log(traceback.format_exc())
    sys.exit(0)

# ── Windows: unchanged original behavior ────────────────────────────────────
PREFERRED_PYTHON = focal_paths.get_python_path()

if PREFERRED_PYTHON and sys.executable.lower() != PREFERRED_PYTHON.lower():
    import subprocess, traceback
    try:
        subprocess.Popen([PREFERRED_PYTHON, os.path.abspath(__file__)])
    except Exception:
        _log(traceback.format_exc())
    sys.exit(0)

# If we're already running under the preferred Python, fall through and
# run settings_app.main() directly in-process (Windows path).
if _SCRIPT_DIR not in sys.path:
    sys.path.append(_SCRIPT_DIR)
import settings_app
settings_app.main()
