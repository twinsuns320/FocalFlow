import os
import sys
import json
import platform
import subprocess
import hashlib
import hmac
import base64


def _deobfuscate(blob, xor_key=0x5A):
    raw = base64.b64decode(blob)
    return bytes(b ^ xor_key for b in raw).decode()

def _deobfuscate_bytes(blob, xor_key=0x5A):
    raw = base64.b64decode(blob)
    return bytes(b ^ xor_key for b in raw)

_APP_SECRET = _deobfuscate_bytes("oiudLTvsSv71NilUQQF1rC3HfDveLOcO6DrHZoEFuuI=")

TIER_TRIAL = 0
TIER_FULL  = 1

FREE_TRIAL_KEY = "FreeTrial"

GUMROAD_PRODUCT_ID = _deobfuscate("FT4uDCw+KBU+HxkRHQgJGQk2a2IYC2dn")

_MASTER_HASH = _deobfuscate("a2hsOTxsPjxiaztvOWtqPm0/ODtuP25sbjs/Pm5pOT4/Ozlta2lpY2ljamM5Pzk8azs+bWo/bTtvbmM7bz5saQ==")

if platform.system() == "Darwin":
    ACTIVATION_DIR = os.path.expanduser("~/Library/Application Support/FocalFlow")
else:
    ACTIVATION_DIR = os.path.join(os.environ.get("LOCALAPPDATA", "C:\\"), "FocalFlow")
ACTIVATION_PATH = os.path.join(ACTIVATION_DIR, "state.dat")


def _hardware_id():
    """Stable per-machine ID that does not travel if this file is copied
    to another PC."""
    if platform.system() == "Darwin":
        try:
            out = subprocess.run(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                capture_output=True, text=True, timeout=5
            ).stdout
            for line in out.splitlines():
                if "IOPlatformUUID" in line:
                    return line.split('"')[-2]
        except Exception:
            pass
        return "no-uuid-" + (os.environ.get("USER") or "unknown")
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                              r"SOFTWARE\Microsoft\Cryptography")
        guid, _ = winreg.QueryValueEx(key, "MachineGuid")
        winreg.CloseKey(key)
        return guid
    except Exception:
        return "no-machine-guid-" + (os.environ.get("COMPUTERNAME") or "unknown")


def _sign(tier, hw_id, salt):
    msg = f"{tier}:{hw_id}:{salt}".encode()
    return hmac.new(_APP_SECRET, msg, hashlib.sha256).hexdigest()


def write_activation(tier):
    hw_id = _hardware_id()
    salt  = base64.b64encode(os.urandom(9)).decode()
    token = _sign(tier, hw_id, salt)

    blob = {"d": tier, "h": hw_id, "n": salt, "s": token}
    encoded = base64.b64encode(json.dumps(blob).encode()).decode()

    os.makedirs(ACTIVATION_DIR, exist_ok=True)
    with open(ACTIVATION_PATH, "w") as f:
        f.write(encoded)


def read_activation():
    if not os.path.isfile(ACTIVATION_PATH):
        return None
    try:
        with open(ACTIVATION_PATH) as f:
            blob = json.loads(base64.b64decode(f.read()).decode())
        tier, hw_id, salt, token = blob["d"], blob["h"], blob["n"], blob["s"]
        if not hmac.compare_digest(_sign(tier, hw_id, salt), token):
            return None
        if hw_id != _hardware_id():
            return None
        return tier
    except Exception:
        return None


def verify_gumroad_key(key):
    import urllib.request
    import urllib.parse
    key = key.strip()

    if hashlib.sha256(key.encode()).hexdigest() == _MASTER_HASH:
        return True, TIER_FULL

    if key.lower() == FREE_TRIAL_KEY.lower():
        return True, TIER_TRIAL

    try:
        data = urllib.parse.urlencode({
            "product_id":           GUMROAD_PRODUCT_ID,
            "license_key":          key,
            "increment_uses_count": "true"
        }).encode()
        req = urllib.request.Request(
            "https://api.gumroad.com/v2/licenses/verify",
            data=data,
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode())

        if not result.get("success", False):
            return False, None

        if result.get("uses", 0) > 1:
            return False, None

        return True, TIER_FULL
    except Exception as e:
        print(f"\n  ERROR contacting Gumroad: {e}")
        return False, None
