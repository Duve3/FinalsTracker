#!/usr/bin/env python
"""Region Calibrator tool for FinalsTracker.

Usage:
    python region_calibrator.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.debug.region_calibrator import launch_calibrator

if __name__ == "__main__":
    launch_calibrator()