# focal_paths.py — shared cross-platform path resolution for FocalFlow
import sys, os, json, platform

IS_MAC = platform.system() == "Darwin"

def _config_path():
    if IS_MAC:
        d = os.path.expanduser("~/Library/Application Support/FocalFlow")
    else:
        d = os.path.join(os.environ.get("LOCALAPPDATA", "C:\\"), "FocalFlow")
    return os.path.join(d, "config.json")

def write_config(install_dir, python_path, focal_app_path):
    """Called once by the installer."""
    path = _config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump({
            "install_dir": install_dir,
            "python_path": python_path,
            "focal_app_path": focal_app_path,
        }, f, indent=2)

def read_config():
    """Returns dict or None if not installed."""
    path = _config_path()
    if not os.path.isfile(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None

def get_install_dir():
    cfg = read_config()
    if cfg:
        return cfg.get("install_dir")
    return os.path.join(os.path.expanduser("~"), "FocalFlow")

def get_python_path():
    cfg = read_config()
    if cfg:
        return cfg.get("python_path")
    return None

def get_focal_app_path():
    """Path to the actual launchable binary inside FocalFlow.app on Mac,
    or FocalFlow.exe on Windows."""
    cfg = read_config()
    if cfg and cfg.get("focal_app_path"):
        return cfg["focal_app_path"]
    install_dir = get_install_dir()
    if IS_MAC:
        return os.path.join(install_dir, "FocalFlow.app", "Contents", "MacOS", "FocalFlow")
    return os.path.join(install_dir, "FocalFlow", "FocalFlow.exe")

def resolve_scripting_modules_path():
    """Fallback path to DaVinciResolveScript module."""
    if IS_MAC:
        return os.path.expanduser(
            "~/Library/Application Support/Blackmagic Design/DaVinci Resolve/"
            "Developer/Scripting/Modules"
        )
    return (r"C:\ProgramData\Blackmagic Design\DaVinci Resolve"
            r"\Support\Developer\Scripting\Modules")

def resolve_comp_scripts_dir():
    """Where launch_FocalFlow.py etc. get installed so Resolve's menu finds them."""
    if IS_MAC:
        return os.path.expanduser(
            "~/Library/Application Support/Blackmagic Design/DaVinci Resolve/"
            "Fusion/Scripts/Comp"
        )
    return os.path.join(
        os.environ.get("ProgramData", "C:\\ProgramData"),
        "Blackmagic Design", "DaVinci Resolve", "Fusion", "Scripts", "Comp"
    )

def check_resolve_installed():
    if IS_MAC:
        return os.path.isdir("/Applications/DaVinci Resolve.app")
    resolve_path = os.path.join(
        os.environ.get("ProgramData", "C:\\ProgramData"),
        "Blackmagic Design", "DaVinci Resolve"
    )
    return os.path.isdir(resolve_path)
