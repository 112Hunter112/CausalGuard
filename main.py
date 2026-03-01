"""
CausalGuard Entry Point
=======================
Main entry point for the CausalGuard hackathon demo.
Choose: (A) Unprotected demo, (B) Protected demo, (C) Run tests, (D) Calibrate.
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv()


def print_menu():
    print("\n" + "=" * 60)
    print("  CausalGuard — Inference-Time Firewall Demo")
    print("=" * 60)
    print("  A) Unprotected demo (show the attack)")
    print("  B) Protected demo (two-act: attack then defense)")
    print("  C) Run all tests")
    print("  D) Calibrate thresholds")
    print("  Q) Quit")
    print("=" * 60)


def main():
    print_menu()
    choice = input("  Choice [A/B/C/D/Q]: ").strip().upper() or "B"

    if choice == "A":
        from demo_unprotected import run_unprotected_demo
        asyncio.run(run_unprotected_demo())

    elif choice == "B":
        from demo_protected import run_demo
        asyncio.run(run_demo())

    elif choice == "C":
        import subprocess
        code = subprocess.call(
            [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        sys.exit(code)

    elif choice == "D":
        from calibrate import calibrate
        asyncio.run(calibrate())

    elif choice == "Q":
        print("  Goodbye.")
        sys.exit(0)

    else:
        print("  Invalid choice. Running protected demo (B).")
        from demo_protected import run_demo
        asyncio.run(run_demo())


if __name__ == "__main__":
    main()
