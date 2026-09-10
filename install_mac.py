import os
import sys
import json
import shutil
import subprocess
import focal_paths
import license


RESOLVE_SCRIPTS = focal_paths.resolve_comp_scripts_dir()


def check_system_python():
    """
    Returns (found: bool, version_str: str | None).
    We deliberately avoid 'which python3' and rely purely on the shell
    resolving 'python3' the same way Resolve would.
    """
    try:
        result = subprocess.run(
            ["python3", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        output = (result.stdout + result.stderr).strip()
        if result.returncode == 0 and output.lower().startswith("python"):
            return True, output
        return False, None
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
    focal_src = os.path.join(here, "dist", "FocalFlow.app")
    if not os.path.isdir(focal_src):
        print(f"\n  ERROR: FocalFlow.app not found at {focal_src}")
        input("\n  Press Enter to exit."); sys.exit(1)
    app_dst = os.path.join(app_dir, "FocalFlow.app")
    if os.path.isdir(app_dst):
        shutil.rmtree(app_dst)
    shutil.copytree(focal_src, app_dst)
    print("  Done.")

    print("  Copying scripts...")
    splash_src = os.path.join(here, "splash_FocalFlow.py")
    if os.path.isfile(splash_src):
        shutil.copy2(splash_src, os.path.join(install_dir, "splash_FocalFlow.py"))
    print("  Done.")

    import platform
    machine = platform.machine()
    ffmpeg_name  = "ffmpeg9arm"  if machine == "arm64" else "ffmpeg80intel"
    ffprobe_name = "ffprobe9arm" if machine == "arm64" else "ffprobe80intel"
    macos_dir = os.path.join(app_dst, "Contents", "MacOS")

    for exe, dst_name in [(ffmpeg_name, "ffmpeg"), (ffprobe_name, "ffprobe")]:
        src = os.path.join(here, exe)
        if os.path.isfile(src):
            print(f"  Copying {exe}...")
            shutil.copy2(src, os.path.join(install_dir, dst_name))
            shutil.copy2(src, os.path.join(macos_dir,   dst_name))
            os.chmod(os.path.join(install_dir, dst_name), 0o755)
            os.chmod(os.path.join(macos_dir, dst_name),   0o755)
            for f in [os.path.join(install_dir, dst_name), os.path.join(macos_dir, dst_name)]:
                try:
                    subprocess.run(["xattr", "-d", "com.apple.quarantine", f],
                                    capture_output=True)
                except Exception:
                    pass
            print("  Done.")
        else:
            print(f"  WARNING: {exe} not found — FocalFlow will look on PATH.")

    print("  Copying Resolve scripts...")
    os.makedirs(RESOLVE_SCRIPTS, exist_ok=True)
    for script in ["launch_FocalFlow.py", "place_result_FocalFlow.py",
                   "settings_FocalFlow.py"]:
        src = os.path.join(here, script)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(RESOLVE_SCRIPTS, script))
    print("  Done.")

    for f in ["README.txt", "uninstall_FocalFlow.sh"]:
        src = os.path.join(here, f)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(install_dir, f))

    print("  Copying upgrader...")
    upgrade_src = os.path.join(here, "dist_upgrade", "upgrade_FocalFlow.app")
    if os.path.isdir(upgrade_src):
        upgrade_dst = os.path.join(install_dir, "upgrade_FocalFlow.app")
        if os.path.isdir(upgrade_dst):
            shutil.rmtree(upgrade_dst)
        shutil.copytree(upgrade_src, upgrade_dst)
        print("  Done.")
    else:
        print(f"  WARNING: upgrade_FocalFlow.app not found at {upgrade_src}")
        print("  upgrade_FocalFlow.app was not installed.")

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
