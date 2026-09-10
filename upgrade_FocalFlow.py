#!/usr/bin/env python3


import sys
from license import verify_gumroad_key, write_activation, read_activation, TIER_FULL, TIER_TRIAL


def main():
    print()
    print("  ==========================================")
    print("   FOCALFLOW — UPGRADE TO FULL VERSION")
    print("  ==========================================")
    print()

    current = read_activation()
    if current == TIER_FULL:
        print("  This machine is already activated as the full version.")
        print()
        input("  Press Enter to exit.")
        sys.exit(0)
    elif current == TIER_TRIAL:
        print("  Currently running: Free Trial")
    else:
        print("  No activation currently found on this machine.")
    print()

    print("  Enter your license key from your Gumroad")
    print("  receipt email and press Enter.")
    print()
    key = input("  > ").strip()

    if not key:
        print("\n  No key entered. Nothing changed.")
        input("\n  Press Enter to exit.")
        sys.exit(1)

    print("\n  Verifying license key...")
    ok, tier = verify_gumroad_key(key)

    if not ok:
        print()
        print("  ==========================================")
        print("   LICENSE KEY INVALID OR ALREADY USED")
        print("  ==========================================")
        print()
        print("  This key is invalid or has already been used.")
        print("  Each key can only be activated once. If you")
        print("  believe this is an error, contact support:")
        print("  twinsuns320@gmail.com")
        print()
        input("  Press Enter to exit.")
        sys.exit(1)

    if tier != TIER_FULL:
        # A real Gumroad key always maps to TIER_FULL in verify_gumroad_key.
        # This branch only triggers if someone types "FreeTrial" here, which
        # would be a downgrade, not an upgrade — refuse it rather than silently
        # doing something the user didn't ask for.
        print()
        print("  That key only grants the free trial, which is")
        print("  already active or would be a downgrade.")
        print("  Enter a paid Gumroad license key to upgrade.")
        print()
        input("  Press Enter to exit.")
        sys.exit(1)

    try:
        write_activation(tier)
    except Exception as e:
        print(f"\n  ERROR writing activation: {e}")
        input("\n  Press Enter to exit.")
        sys.exit(1)

    print()
    print("  ==========================================")
    print("   UPGRADE SUCCESSFUL")
    print("  ==========================================")
    print()
    print("  This machine is now activated as the full version.")
    print("  Watermark will no longer be applied on export.")
    print()
    print("  Restart FocalFlow if it's currently running.")
    print()
    input("  Press Enter to exit.")


if __name__ == "__main__":
    main()
