#!/usr/bin/env python3
"""
Quick smoke test — generates and validates a UART UVM testbench.

Usage:
  python regression/smoke.py
  python regression/smoke.py --spec configs/uart16550-1.5.core
"""

import argparse
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser(description="UVM smoke test")
    parser.add_argument("--spec", default="configs/uart16550-1.5.core")
    args = parser.parse_args()

    print(f"[SMOKE] Generating from {args.spec}")
    t0 = time.time()

    result = subprocess.run(
        [sys.executable, "-m", "src.main", "--spec", args.spec],
        capture_output=True, text=True, timeout=120
    )

    elapsed = time.time() - t0
    print(f"[SMOKE] Completed in {elapsed:.1f}s")

    if result.returncode != 0:
        print(f"[SMOKE] FAILED (return code {result.returncode})")
        print(result.stderr[:2000])
        sys.exit(1)

    print("[SMOKE] PASSED")
    print(result.stdout[-1000:] if result.stdout else "(no output)")


if __name__ == "__main__":
    main()
