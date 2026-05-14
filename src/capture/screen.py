import mss
import mss.tools
import numpy as np
from typing import Optional, Tuple, List
from .window import GameWindow
from ..log_config import get_logger

log = get_logger(__name__)


class ScreenCapture:
    def __init__(self, game_window: GameWindow):
        self.game_window = game_window
        self.sct = mss.mss()
        self.monitor_idx = 0
        self._available_monitors = len(self.sct.monitors)
        log.info("ScreenCapture initialized: %d monitor(s) detected", self._available_monitors - 1)

    def set_monitor(self, index: int):
        monitors = self.sct.monitors
        if 1 <= index < len(monitors):
            prev = self.monitor_idx
            self.monitor_idx = index
            log.info("Capture monitor changed: %d -> %d", prev, index)
        else:
            log.warning("Invalid monitor index: %d (available: %d)", index, len(monitors) - 1)

    def capture_region(self, left: int, top: int, width: int, height: int) -> Optional[np.ndarray]:
        if width <= 0 or height <= 0:
            log.debug("Skipping capture: invalid dimensions %dx%d", width, height)
            return None
        monitor = {"left": left, "top": top, "width": width, "height": height}
        try:
            sct_img = self.sct.grab(monitor)
            arr = np.array(sct_img)[:, :, :3]
            h, w, _ = arr.shape
            if h == 0 or w == 0:
                log.debug("Captured empty region (%d,%d %dx%d)", left, top, width, height)
                return None
            log.debug("Captured region (%d,%d %dx%d) -> %s", left, top, width, height, arr.shape)
            return arr
        except mss.exception.ScreenShotError as e:
            log.error("Screen capture out-of-bounds (%d,%d %dx%d): %s", left, top, width, height, e)
            return None
        except Exception as e:
            log.error("Screen capture failed for region (%d,%d %dx%d): %s", left, top, width, height, e)
            return None

    def capture_game_region(self, region_frac: Tuple[float, float, float, float]) -> Optional[np.ndarray]:
        if not self.game_window.is_on_screen:
            log.debug("Skipping game region capture: window not on screen")
            return None
        rect = self.game_window.get_abs_rect()
        if not rect:
            log.debug("Skipping game region capture: window rect unavailable")
            return None
        win_w = rect[2] - rect[0]
        win_h = rect[3] - rect[1]
        if win_w <= 0 or win_h <= 0:
            log.debug("Skipping capture: window has zero area (%dx%d)", win_w, win_h)
            return None
        l, t, r, b = region_frac
        abs_left = rect[0] + int(l * win_w)
        abs_top = rect[1] + int(t * win_h)
        abs_w = max(1, int((r - l) * win_w))
        abs_h = max(1, int((b - t) * win_h))
        return self.capture_region(abs_left, abs_top, abs_w, abs_h)

    def capture_full_game_window(self) -> Optional[np.ndarray]:
        rect = self.game_window.get_abs_rect()
        if not rect:
            return None
        w, h = rect[2] - rect[0], rect[3] - rect[1]
        log.debug("Capturing full game window: (%d,%d %dx%d)", rect[0], rect[1], w, h)
        return self.capture_region(rect[0], rect[1], w, h)

    def capture_multiple_regions(self, regions: List[Tuple[str, Tuple[float, float, float, float]]]):
        results = {}
        for name, frac in regions:
            img = self.capture_game_region(frac)
            if img is not None:
                results[name] = img
        if results:
            log.debug("Captured %d/%d game regions: %s", len(results), len(regions), list(results.keys()))
        return results

    def cleanup(self):
        log.info("Closing screen capture")
        self.sct.close()
