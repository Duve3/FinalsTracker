"""Standalone diagnostic script.
Run: python dump_windows.py          (dump all visible windows)
     python dump_windows.py screenshot (capture game window screenshot)
"""
import sys
import os
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from src.capture.window import dump_all_windows, GameWindow
from src.log_config import setup_logging

setup_logging(log_dir="logs", log_file="tracker.log")

if len(sys.argv) > 1 and sys.argv[1] == "screenshot":
    import cv2
    from src.capture.screen import ScreenCapture
    gw = GameWindow()
    if not gw.find():
        print("THE FINALS window not found")
        sys.exit(1)
    cap = ScreenCapture(gw)
    img = cap.capture_full_game_window()
    if img is not None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(os.path.dirname(__file__), f"game_screenshot_{ts}.png")
        cv2.imwrite(path, img)
        print(f"Screenshot saved: {path}")
        print(f"Window: {gw.width}x{gw.height} at ({gw.left},{gw.top})")
        from src.ocr.regions import HUD_REGIONS
        for name, (l, t, r, b) in HUD_REGIONS.items():
            abs_l = int(gw.left + l * gw.width)
            abs_t = int(gw.top + t * gw.height)
            abs_r = int(gw.left + r * gw.width)
            abs_b = int(gw.top + b * gw.height)
            print(f"  {name}: ({abs_l},{abs_t})-({abs_r},{abs_b}) = {abs_r-abs_l}x{abs_b-abs_t}")
    else:
        print("Failed to capture game window")
    cap.cleanup()
else:
    dump_all_windows()
