#!/usr/bin/env python
"""Debug replay tool launcher for FinalsTracker.

Usage:
    python debug_replay.py                          # Launch with empty viewer
    python debug_replay.py <session_path>           # Launch with session loaded
    python debug_replay.py --latest                 # Load most recent session
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.debug.replay import launch_replay


def find_latest_session():
    sessions_dir = Path(__file__).parent / "debug_sessions"
    if not sessions_dir.exists():
        return None
    sessions = [d for d in sessions_dir.iterdir() if d.is_dir()]
    if not sessions:
        return None
    latest = max(sessions, key=lambda d: d.stat().st_mtime)
    return str(latest)


def main():
    if "--latest" in sys.argv:
        session = find_latest_session()
        if session:
            print(f"Loading latest session: {session}")
            launch_replay(session)
        else:
            print("No sessions found. Launching empty viewer.")
            launch_replay()
    elif len(sys.argv) > 1:
        session = sys.argv[1]
        if os.path.isdir(session):
            launch_replay(session)
        else:
            print(f"Error: {session} is not a valid directory")
            sys.exit(1)
    else:
        launch_replay()


if __name__ == "__main__":
    main()