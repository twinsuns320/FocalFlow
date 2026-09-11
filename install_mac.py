import os
import sys
import json
import shutil
import subprocess
import focal_paths
import license


RESOLVE_SCRIPTS = focal_paths.resolve_comp_scripts_dir()


MIN_PY = (3, 10)
MAX_PY = (3, 13)

def check_system_python():
    """
    Returns (found_and_supported: bool, version_str: str | None).
    Rejects missing Python, the Apple CLT stub, and anything outside
    the tested range.
    """
    try:
        result = subprocess.run(
            ["python3", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        output = (result.stdout + result.stderr).strip()
        if result.returncode != 0 or not output.lower().startswith("python"):
            return False, None

        version_str = output.split()[1]  # e.g. "3.9.6"
        parts = tuple(int(x) for x in version_str.split(".")[:2])

        if parts < MIN_PY or parts > MAX_PY:
            print(f"  Found Python {version_str}, but FocalFlow needs")
            print(f"  {MIN_PY[0]}.{MIN_PY[1]}–{MAX_PY[0]}.{MAX_PY[1]} for Resolve scripting.")
            return False, output

        return True, output
    except FileNotFoundError:
        return False, None
    except Exception:
        return False, None


def prompt_python_install(here):
    python_installer = None
    for name in os.listdir(here):
        low = name.lower()
        if low.startswith("python") and low.endswith(".pkg"):
            python_installer = os.path.join(here, name)
            break

    print()
    print("  ==========================================")
    print("   PYTHON NOT FOUND — ACTION REQUIRED")
    print("  ==========================================")
    print()
    print("  DaVinci Resolve needs Python installed")
    print("  system-wide before FocalFlow can be set up.")
    print()
    print("  A Python installer is included in this folder.")
    print("  It will open when you press Enter below.")
    print()

    if python_installer:
        print("  !! WHEN IT OPENS, BEFORE YOU CLICK ANYTHING !!")
        print()
        print('     ☑  Follow the installer through to the end')
        print('     ☑  Enter your Mac password when prompted')
        print()
        print("     Both steps are needed to finish install.")
        print("     Both are easy to miss. Don't skip them.")
        print("     If you miss them, Resolve will never find")
        print("     Python and FocalFlow scripts won't run.")
        print()
        input("  Press Enter to open the Python installer.")
        try:
            subprocess.Popen(["open", python_installer])
            print()
            print("  ──────────────────────────────────────────")
            print("  Python installer launched.")
            print()
            print("  This window will now close.")
            print()
            print("  Once Python is installed, double-click")
            print("  INSTALL_FOCALFLOW again to continue.")
            print("  ──────────────────────────────────────────")
            print()
            input("  Press Enter and this window will close.")
            sys.exit(0)
        except Exception as e:
            print(f"\n  Could not launch automatically: {e}")
            print(f"  Open it manually: {python_installer}")
            print()
            print("  Follow it through, install Python, then")
            print("  double-click INSTALL_FOCALFLOW again.")
            print()
            input("  Press Enter to exit.")
            sys.exit(0)
    else:
        print("  No Python installer found in this folder.")
        print("  Download Python from https://www.python.org/downloads/")
        print("  Double-click the installer and follow it through.")
        print()
        print("  Once Python is installed, double-click")
        print("  install_FocalFlow again to continue.")
        print()
        input("  Press Enter to exit.")
        sys.exit(0)


def write_registry(install_dir, python_path):
    try:
        focal_paths.write_config(
            install_dir=install_dir,
            python_path=python_path,
            focal_app_path=os.path.join(install_dir, "FocalFlow.app",
                                         "Contents", "MacOS", "FocalFlow"),
        )
        return True
    except Exception as e:
        print(f"\n  ERROR writing configuration: {e}")
        return False


def add_to_path(install_dir):
    pass  # Not needed on macOS — FocalFlow.app is self-contained and Resolve
          # scripts resolve paths via focal_paths.py, not a PATH lookup.


def cleanup_downloads(here):
    downloads = os.path.expanduser("~/Downloads")
    downloads_lower = downloads.lower()

    candidate = here
    for _ in range(3):
        parent = os.path.dirname(candidate)
        if parent.lower() == downloads_lower:
            folder_name = os.path.basename(candidate).lower()
            if "focalflow" in folder_name:
                try:
                    shutil.rmtree(candidate)
                except Exception as e:
                    print(f"  WARNING: Could not clean up installer folder: {e}")
                try:
                    for f in os.listdir(downloads):
                        low = f.lower()
                        if "focalflow" in low and (low.endswith(".zip") or low.endswith(".dmg")):
                            os.remove(os.path.join(downloads, f))
                except Exception as e:
                    print(f"  WARNING: Could not clean up zip file: {e}")
            else:
                print("  Skipping Downloads cleanup (folder name not recognised).")
            return
        candidate = parent


def cleanup_installer_contents(here):
    """Delete everything in the installer folder except this script itself."""
    try:
        for item in os.listdir(here):
            item_path = os.path.join(here, item)
            if os.path.abspath(item_path) == os.path.abspath(__file__):
                continue
            try:
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)
            except Exception:
                pass
    except Exception:
        pass


def check_resolve_installed():
    return focal_paths.check_resolve_installed()


def main():
    here = os.path.dirname(os.path.abspath(
        sys.executable if getattr(sys, "frozen", False) else __file__
    ))
    if not check_resolve_installed():
        print()
        print("  ==========================================")
        print("   DAVINCI RESOLVE NOT FOUND")
        print("  ==========================================")
        print()
        print("  FocalFlow requires DaVinci Resolve to be")
        print("  installed before running this installer.")
        print()
        input("  Press Enter to exit.")
        sys.exit(1)

    print()
    print("  ==========================================")
    print("   FOCALFLOW INSTALLER")
    print("  ==========================================")
    print()

    print("  Checking for Python on the system PATH...")
    found, ver = check_system_python()
    if found:
        print(f"  Found: {ver}")
        print()
    else:
        prompt_python_install(here)

    print("  Enter your license key from your Gumroad")
    print("  receipt email and press Enter.")
    print()
    print("  No key yet? Type  FreeTrial  to install")
    print("  the free trial version. Trial exports will")
    print("  have a FOCALFLOW watermark burned into the")
    print("  video. Enter a valid license key at any")
    print("  time to upgrade to the full version.")
    print()
    key = input("  > ").strip()

    if not key:
        print("\n  No key entered. Installation cancelled.")
        input("\n  Press Enter to exit.")
        sys.exit(1)

    print("\n  Verifying license key...")
    ok, tier = license.verify_gumroad_key(key)
    if not ok:
        print()
        print("  ==========================================")
        print("   LICENSE KEY INVALID OR ALREADY USED")
        print("  ==========================================")
        print()
        print("  Your key has already been used.")
        print("  If you believe this is a mistake")
        print("  contact: twinsuns320@gmail.com")
        print()
        input("  Press Enter to exit.")
        sys.exit(1)

    print("  License verified.")
    print()

    install_dir = os.path.join(os.path.expanduser("~"), "FocalFlow")
    python_path = shutil.which("python3") or "/usr/bin/python3"
    app_dir     = install_dir

    print(f"  Installing to: {install_dir}")
    print()

    print("  Copying FocalFlow application...")
    focal_src = os.path.join(here, "FocalFlow.app")
    if not os.path.isdir(focal_src):
        print(f"\n  ERROR: FocalFlow.app not found at {focal_src}")
        input("\n  Press Enter to exit."); sys.exit(1)
    app_dst = os.path.join(app_dir, "FocalFlow.app")
    if os.path.isdir(app_dst):
        shutil.rmtree(app_dst)
    shutil.copytree(focal_src, app_dst)
    print("  Done.")

    print("  Copying splash screen...")
    splash_src = os.path.join(here, "splash_FocalFlow")
    if os.path.isfile(splash_src):
        splash_dst = os.path.join(install_dir, "splash_FocalFlow")
        shutil.copy2(splash_src, splash_dst)
        os.chmod(splash_dst, 0o755)
        try:
            subprocess.run(["xattr", "-d", "com.apple.quarantine", splash_dst],
                            capture_output=True)
        except Exception:
            pass
        print("  Done.")
    else:
        print(f"  WARNING: splash_FocalFlow not found at {splash_src}")

    macos_dir = os.path.join(app_dst, "Contents", "MacOS")

    for exe in ["ffmpeg", "ffprobe"]:
        src = os.path.join(here, exe)
        if os.path.isfile(src):
            print(f"  Copying {exe}...")
            shutil.copy2(src, os.path.join(install_dir, exe))
            shutil.copy2(src, os.path.join(macos_dir, exe))
            os.chmod(os.path.join(install_dir, exe), 0o755)
            os.chmod(os.path.join(macos_dir, exe), 0o755)
            for f in [os.path.join(install_dir, exe), os.path.join(macos_dir, exe)]:
                try:
                    subprocess.run(["xattr", "-d", "com.apple.quarantine", f],
                                    capture_output=True)
                except Exception:
                    pass
            print("  Done.")
        else:
            print(f"  WARNING: {exe} not found — FocalFlow will look on PATH.")

    print("  Copying Resolve scripts...")
    print(f"  (Looking for scripts in: {here})")
    os.makedirs(RESOLVE_SCRIPTS, exist_ok=True)
    missing = []
    for script in ["launch_FocalFlow.py", "place_result_FocalFlow.py",
                   "settings_FocalFlow.py", "focal_paths.py"]:
        src = os.path.join(here, script)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(RESOLVE_SCRIPTS, script))
            print(f"    [OK] {script}")
        else:
            missing.append(script)
            print(f"    [MISSING] {script} not found at {src}")

    if missing:
        print()
        print("  ==========================================")
        print("   WARNING: SOME RESOLVE SCRIPTS WERE NOT COPIED")
        print("  ==========================================")
        print(f"  Missing: {', '.join(missing)}")
        print("  Make sure install_FocalFlow is run from inside")
        print("  the full extracted FocalFlow folder, not moved")
        print("  out on its own.")
        print()
        input("  Press Enter to exit.")
        sys.exit(1)
    print("  Done.")

    for f in ["README.txt", "uninstall_FocalFlow.command"]:
        src = os.path.join(here, f)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(install_dir, f))
            if f.endswith(".command"):
                os.chmod(os.path.join(install_dir, f), 0o755)

    print("  Copying upgrader...")
    upgrade_src = os.path.join(here, "upgrade_FocalFlow")
    if os.path.isfile(upgrade_src):
        upgrade_dst = os.path.join(install_dir, "upgrade_FocalFlow")
        shutil.copy2(upgrade_src, upgrade_dst)
        os.chmod(upgrade_dst, 0o755)
        try:
            subprocess.run(["xattr", "-d", "com.apple.quarantine", upgrade_dst],
                            capture_output=True)
        except Exception:
            pass
        print("  Done.")
    else:
        print(f"  WARNING: upgrade_FocalFlow not found at {upgrade_src}")
        print("  upgrade_FocalFlow was not installed.")

    print("  Writing registry entries...")
    if not write_registry(install_dir, python_path):
        input("\n  Press Enter to exit."); sys.exit(1)
    add_to_path(install_dir)
    print("  Done.")

    print("  Activating this device...")
    try:
        license.write_activation(tier)
        print("  Done.")
    except Exception as e:
        print(f"\n  ERROR writing activation: {e}")
        input("\n  Press Enter to exit."); sys.exit(1)

    print()
    print("  ==========================================")
    print("   FOCALFLOW INSTALLED SUCCESSFULLY")
    print("  ==========================================")
    print()
    print(f"  Installed to : {install_dir}")
    print("  Resolve menu : Workspace > Scripts > launch_FocalFlow")
    print("                 Workspace > Scripts > place_result_FocalFlow")
    print("                 Workspace > Scripts > settings_FocalFlow")
    print()
    print("  NOTE: Please restart DaVinci Resolve for")
    print("  the new scripts to appear in the menu.")
    print()
    cleanup_installer_contents(here)
    input("  Press Enter to exit.")
    cleanup_downloads(here)


if __name__ == "__main__":
    main()
