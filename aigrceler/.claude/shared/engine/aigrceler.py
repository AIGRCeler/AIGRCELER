#!/usr/bin/env python3
"""AIGRCeler v2 engine entry point.

Windows:  py -3 aigrceler.py <group> <command> [options]
Every record, status, fingerprint, journal line and index is written by this
program and by nothing else. Agents call it; they never edit those files by hand.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    from aig.cli import main
    sys.exit(main())
