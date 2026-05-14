import os
import re
import win32gui
import win32process
import win32con
import win32api
from typing import Optional, Tuple
from ..log_config import get_logger

log = get_logger(__name__)

_BROWSER_EXES = {
    "brave.exe", "chrome.exe", "msedge.exe", "firefox.exe",
    "opera.exe", "opera_gx.exe", "vivaldi.exe", "iexplore.exe",
}

_PYTHON_EXES = {"python.exe", "python3.exe", "pythonw.exe"}

# anti-cheat / game launcher processes that host THE FINALS
_ALLOWED_GAME_EXES = {"discovery.exe"}

_ZERO_WIDTH_CHARS = re.compile("[\u200b\u200c\u200d\u200e\u200f\ufeff\u2005\u2004\u2000-\u2009\u202f\u00a0]+")


def _strip_invisible(title: str) -> str:
    return _ZERO_WIDTH_CHARS.sub("", title)


def _get_process_name(hwnd: int) -> Optional[str]:
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        handle = win32api.OpenProcess(
            win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ,
            False, pid
        )
        if not handle:
            return None
        try:
            exe_path = win32process.GetModuleFileNameEx(handle, 0)
            return os.path.basename(exe_path).lower() if exe_path else None
        finally:
            win32api.CloseHandle(handle)
    except Exception as e:
        log.debug("Failed to get process name for hwnd=%s: %s", hwnd, e)
        return None


def _is_browser(exe_name: Optional[str]) -> bool:
    return exe_name in _BROWSER_EXES if exe_name else False


def _is_python_process(exe_name: Optional[str]) -> bool:
    return exe_name in _PYTHON_EXES if exe_name else False


def dump_all_windows():
    log.info("===== DUMPING ALL VISIBLE WINDOWS =====")
    count = 0

    def callback(hwnd, _ctx):
        nonlocal count
        if not (win32gui.IsWindowVisible(hwnd) and win32gui.IsWindowEnabled(hwnd)):
            return
        text = win32gui.GetWindowText(hwnd)
        if not text:
            return
        exe_name = _get_process_name(hwnd)
        rect = win32gui.GetWindowRect(hwnd)
        w = rect[2] - rect[0]
        h = rect[3] - rect[1]
        display_text = _strip_invisible(text) or repr(text)
        log.info("  hwnd=%-8d title='%s' exe='%s' rect=%s size=%dx%d",
                 hwnd, display_text, exe_name, rect, w, h)
        count += 1

    win32gui.EnumWindows(callback, None)
    log.info("===== %d visible window(s) dumped =====", count)


class GameWindow:
    MIN_WIDTH = 800
    MIN_HEIGHT = 600

    def __init__(self, title_substring: str = "THE FINALS"):
        self.title_substring = title_substring
        self.hwnd: Optional[int] = None
        self.rect: Tuple[int, int, int, int] = (0, 0, 0, 0)
        self._candidates: list[dict] = []
        self._current_exe: Optional[str] = None

    def find(self) -> bool:
        self._candidates = []

        def callback(hwnd, _ctx):
            if not (win32gui.IsWindowVisible(hwnd) and win32gui.IsWindowEnabled(hwnd)):
                return
            text = win32gui.GetWindowText(hwnd)
            if not text:
                return

            normalized = _strip_invisible(text).replace(" ", "")
            search = self.title_substring.replace(" ", "")
            if search.lower() not in normalized.lower():
                return

            exe_name = _get_process_name(hwnd)
            if _is_browser(exe_name):
                log.debug("Excluding browser window: hwnd=%s title='%s' exe='%s'",
                           hwnd, text, exe_name)
                return
            if _is_python_process(exe_name):
                log.debug("Excluding python window: hwnd=%s title='%s' exe='%s'",
                           hwnd, text, exe_name)
                return
            if exe_name in _ALLOWED_GAME_EXES:
                log.debug("Allowing known game process: '%s'", exe_name)

            rect = win32gui.GetWindowRect(hwnd)
            w = rect[2] - rect[0]
            h = rect[3] - rect[1]
            self._candidates.append({
                "hwnd": hwnd, "text": text, "exe": exe_name,
                "rect": rect, "width": w, "height": h,
            })

        win32gui.EnumWindows(callback, None)

        if not self._candidates:
            log.debug("No matching windows found (title contains '%s')",
                       self.title_substring)
            self.hwnd = None
            return False

        self._candidates.sort(key=lambda c: c["width"] * c["height"], reverse=True)

        for cand in self._candidates:
            w, h = cand["width"], cand["height"]
            display_text = _strip_invisible(cand["text"]) or repr(cand["text"])
            log.debug("Window candidate: '%s' exe='%s' at (%d,%d,%d,%d) = %dx%d",
                       display_text, cand.get("exe"), *cand["rect"], w, h)

            if w < self.MIN_WIDTH or h < self.MIN_HEIGHT:
                log.debug("  -> skipped (too small, min %dx%d)", self.MIN_WIDTH, self.MIN_HEIGHT)
                continue

            self.hwnd = cand["hwnd"]
            self.rect = cand["rect"]
            self._current_exe = cand.get("exe")
            log.info("Game window selected: hwnd=%s exe='%s' title='%s' rect=%s size=%dx%d",
                      self.hwnd, self._current_exe, display_text, self.rect, w, h)
            return True

        log.warning("Found %d matching window(s) but none meet minimum size %dx%d",
                     len(self._candidates), self.MIN_WIDTH, self.MIN_HEIGHT)
        self.hwnd = None
        return False

    def _update_rect(self):
        if self.hwnd:
            self.rect = win32gui.GetWindowRect(self.hwnd)

    def get_abs_rect(self) -> Optional[Tuple[int, int, int, int]]:
        self._update_rect()
        return self.rect if self.hwnd else None

    @property
    def left(self) -> int:
        return self.rect[0]

    @property
    def top(self) -> int:
        return self.rect[1]

    @property
    def width(self) -> int:
        return self.rect[2] - self.rect[0]

    @property
    def height(self) -> int:
        return self.rect[3] - self.rect[1]

    @property
    def is_on_screen(self) -> bool:
        return self.width > 0 and self.height > 0

    def is_foreground(self) -> bool:
        return self.hwnd is not None and win32gui.GetForegroundWindow() == self.hwnd

    def is_alive(self) -> bool:
        if not self.hwnd:
            return False
        try:
            _, pid = win32process.GetWindowThreadProcessId(self.hwnd)
            handle = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION, False, pid)
            if handle:
                win32api.CloseHandle(handle)
                return True
            return False
        except Exception as e:
            log.warning("Failed to check process health: %s", e)
            return False

    def bring_to_foreground(self):
        if self.hwnd:
            log.debug("Bringing game window to foreground")
            win32gui.ShowWindow(self.hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(self.hwnd)

    def __repr__(self) -> str:
        if self.hwnd:
            return (f"GameWindow(hwnd={self.hwnd}, exe={self._current_exe}, "
                    f"rect={self.rect}, size={self.width}x{self.height})")
        return "GameWindow(not found)"
