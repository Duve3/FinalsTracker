import asyncio
import json
import ctypes
import logging
import time
import os
import cv2
from pathlib import Path
from .capture.window import GameWindow, dump_all_windows
from .capture.screen import ScreenCapture
from .ocr.pipeline import ocr_text, ocr_scoreboard_row, enable_debug_saves
from .ocr.pipeline import tesseract_path as _tesseract_available
from .ocr.regions import HUD_REGIONS, SCOREBOARD_REGIONS, SUMMARY_REGIONS
from .game.state_machine import GameState, StateMachine
from .game.parser import MatchData, ScoreboardEntry, parse_cash_text, parse_summary_result
from .tracker.session import SessionTracker
from .tracker.database import MatchDatabase
from .server.server import LiveServer
from .log_config import setup_logging, get_logger
from .debug.recorder import get_recorder
from datetime import datetime

log = get_logger(__name__)

VK_TAB = 0x09
user32 = ctypes.windll.user32

_DEBUG_SCREENSHOT_DIR = Path(__file__).parent.parent / "debug_captures"


def _save_debug_screenshot(capture, game_window, label: str):
    _DEBUG_SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    img = capture.capture_full_game_window()
    if img is not None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = _DEBUG_SCREENSHOT_DIR / f"{label}_{ts}.png"
        cv2.imwrite(str(path), img)
        log.debug("Debug screenshot saved: %s", path)


def is_tab_down():
    return user32.GetAsyncKeyState(VK_TAB) & 0x8000 != 0


class FinalsTracker:
    def __init__(self, config_path: str = "config.json"):
        self.config = self._load_config(config_path)
        self.running = True

        self.game_window = GameWindow(
            title_substring=self.config["game"]["window_title"]
        )
        self.capture = ScreenCapture(self.game_window)
        self.state_machine = StateMachine()
        self.state_machine.scoreboard_debounce = self.config["game"]["scoreboard_debounce_sec"]

        self.session = SessionTracker()
        db_path = self.config["database"]["path"]
        self.db = MatchDatabase(os.path.join(os.path.dirname(config_path), db_path))

        dash_dir = str(Path(__file__).parent / "dashboard")
        self.server = LiveServer(
            host=self.config["server"]["host"],
            port=self.config["server"]["port"],
            dashboard_dir=dash_dir,
        )

        self.current_match_data = MatchData()
        self._setup_callbacks()
        self._setup_server_messaging()
        self._menu_frame_count = 0
        self._last_state_check = 0.0

    def _load_config(self, path: str) -> dict:
        default = {
            "ver": 0.1,
            "capture": {"fps": 10, "monitor_index": 0},
            "game": {"window_title": "THE FINALS", "scoreboard_debounce_sec": 0.3},
            "server": {"host": "127.0.0.1", "port": 8080},
            "database": {"path": "data/matches.db"},
            "logging": {"console_level": "INFO", "file_level": "DEBUG", "log_dir": "logs", "log_file": "tracker.log"},
            "debug": {"save_captures": False, "save_dir": "debug_captures", "record_sessions": False, "sessions_dir": "debug_sessions"},
            "calibration": {"regions_preset": "2560x1440", "custom_regions": {}}
        }
        try:
            with open(path) as f:
                cfg = json.load(f)
                for section in default:
                    if section not in cfg:
                        cfg[section] = default[section]
                    else:
                        for key in default[section]:
                            cfg[section].setdefault(key, default[section][key])
                return cfg
        except FileNotFoundError:
            log.warning("config.json not found, using defaults")
            return default

    def _setup_logging(self):
        log_cfg = self.config.get("logging", {})
        level_map = {"DEBUG": logging.DEBUG, "INFO": logging.INFO,
                     "WARNING": logging.WARNING, "ERROR": logging.ERROR}
        setup_logging(
            log_dir=log_cfg.get("log_dir", "logs"),
            log_file=log_cfg.get("log_file", "tracker.log"),
            console_level=level_map.get(log_cfg.get("console_level", "INFO"), logging.INFO),
            file_level=level_map.get(log_cfg.get("file_level", "DEBUG"), logging.DEBUG),
        )

    def _setup_debug(self):
        debug_cfg = self.config.get("debug", {})
        if debug_cfg.get("save_captures", False):
            enable_debug_saves(debug_cfg.get("save_dir", "debug_captures"))

    def _check_environment(self):
        if not _tesseract_available:
            log.critical("Tesseract OCR is NOT installed or not found!")
            log.critical("Download from: https://github.com/UB-Mannheim/tesseract/wiki")
            log.critical("Install to: C:\\Program Files\\Tesseract-OCR\\")
        else:
            log.info("Tesseract OCR check: OK")
        if not self.game_window.find():
            log.warning("THE FINALS window not detected. Make sure the game is running.")
        else:
            log.info("Game window detected: %s", self.game_window)

    def _setup_callbacks(self):
        async def on_transition(old: GameState, new: GameState):
            log.debug("Callback: state %s -> %s (was from scoreboard=%s)",
                      old.value, new.value, old == GameState.SCOREBOARD)
            await self.server.send_state_change(new.value)

            recorder = get_recorder()
            if recorder:
                if new == GameState.INGAME and old != GameState.SCOREBOARD:
                    recorder.start_session()
                    log.info("Debug recording started")

            if new == GameState.INGAME:
                if old != GameState.SCOREBOARD:
                    self.session.start_match()
                _save_debug_screenshot(self.capture, self.game_window, "ingame")
            elif new == GameState.SUMMARY:
                if recorder and recorder.is_recording:
                    recorder.stop_session()
                    log.info("Debug recording stopped - session saved")
                await self._handle_match_end()
            elif new == GameState.MENU:
                if recorder and recorder.is_recording:
                    session_path = recorder.stop_session()
                    log.info(f"Debug recording stopped - session saved to {session_path}")
                await self._push_session_data()

        self.state_machine.on_transition(on_transition)

    def _setup_server_messaging(self):
        async def on_ws_message(data):
            action = data.get("action", "")
            if action == "force_ingame":
                log.info("User confirmed mid-game start via dashboard")
                self._midgame_pending_confirm = False
                self.state_machine.transition_to(GameState.INGAME)

        self.server.on_message(on_ws_message)
        self._midgame_pending_confirm = False

    async def _handle_match_end(self):
        log.info("Handling match end")
        result = None
        summary_img = self.capture.capture_game_region(SUMMARY_REGIONS["match_result"])
        if summary_img is not None:
            text = ocr_text(summary_img)
            if text:
                result = parse_summary_result(text)
                log.info("Match result OCR: '%s' -> %s", text[:50], result)
            else:
                log.warning("No text detected on match summary screen")
        else:
            log.warning("Could not capture match summary region")
        self.session.end_match(result)
        if self.session.matches:
            record = self.session.matches[-1]
            self.db.insert_match(record.to_dict())
        await self.server.send_match_history(self.session.get_recent_matches())

    async def _push_session_data(self):
        summary = self.session.get_session_summary()
        log.info("Pushing session data: %d matches played", summary.get("matches_played", 0))
        await self.server.send_session_summary(summary)
        career = self.db.get_stats()
        await self.server.send_career_stats(career)

    async def _capture_loop(self):
        log.info("Capture loop started (%.1f fps)", self.config["capture"]["fps"])
        target_interval = 1.0 / self.config["capture"]["fps"]
        frame_interval = target_interval

        while self.running:
            try:
                loop_start = time.perf_counter()
                current_state = self.state_machine.state

                if current_state == GameState.MENU:
                    self._detect_ingame_from_content()
                elif current_state == GameState.INGAME:
                    await self._capture_hud()
                elif current_state == GameState.SCOREBOARD:
                    await self._capture_scoreboard()

                elapsed = time.perf_counter() - loop_start
                sleep_time = max(0, frame_interval - elapsed)
                await asyncio.sleep(sleep_time)

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("Capture loop error: %s", e, exc_info=True)
                await asyncio.sleep(1.0)

    def _detect_ingame_from_content(self):
        """If in MENU but HUD content is visible, transition to INGAME."""
        if self.state_machine.state != GameState.MENU:
            return
        now = time.time()
        if now - self._last_state_check < 1.0:
            return
        self._last_state_check = now

        for name, frac in [("team_score", HUD_REGIONS["team_score"])]:
            img = self.capture.capture_game_region(frac)
            if img is not None and img.size > 0:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                bright_pixels = cv2.countNonZero(gray)
                if bright_pixels > 50:
                    if not self._midgame_pending_confirm:
                        self._midgame_pending_confirm = True
                        log.info("Game HUD detected in '%s' (%d bright px) — transitioning to INGAME",
                                 name, bright_pixels)
                        asyncio.ensure_future(self.server.send_game_detected())
                    self.state_machine.transition_to(GameState.INGAME)
                    return

    async def _capture_hud(self):
        regions = self.capture.capture_multiple_regions(list(HUD_REGIONS.items()))
        ocr_results = {}

        if regions:
            for name, img in regions.items():
                text = ocr_text(img)
                ocr_results[name] = text
                if text and name == "team_score":
                    score = parse_cash_text(text)
                    if score is not None:
                        self.current_match_data.team_cash = score

            self.session.update_match(self.current_match_data)
            await self.server.send_match_update(self.current_match_data.to_dict())

        recorder = get_recorder()
        if recorder and recorder.is_recording and regions:
            full_frame = self.capture.capture_full_game_window()
            hud_regions_dict = {k: list(v) for k, v in HUD_REGIONS.items()}
            recorder.record_frame(
                full_frame=full_frame,
                captured_regions=hud_regions_dict,
                extracted_values={
                    "hud": self.current_match_data.to_dict(),
                    "raw_ocr": ocr_results
                },
                game_state=self.state_machine.state.value
            )

    async def _capture_scoreboard(self):
        regions = self.capture.capture_multiple_regions(list(SCOREBOARD_REGIONS.items()))

        if "header" in regions:
            header_text = ocr_text(regions["header"])
            if header_text and ("kills" in header_text.lower() or "k" in header_text.lower()):
                log.debug("Scoreboard header confirmed: '%s'", header_text[:40])

        player_entries = []
        for i in range(1, 10):
            key = f"player_{i}"
            if key in regions and regions[key] is not None and regions[key].size > 0:
                row_data = ocr_scoreboard_row(regions[key])
                if row_data:
                    entry = ScoreboardEntry(
                        name=row_data.get("name", ""),
                        kills=row_data.get("kills", 0) or 0,
                        deaths=row_data.get("deaths", 0) or 0,
                        assists=row_data.get("assists", 0) or 0,
                    )
                    player_entries.append(entry)
                    log.debug("Parsed scoreboard row %d: name='%s' k=%d d=%d a=%d",
                              i, entry.name, entry.kills, entry.deaths, entry.assists)

        if player_entries:
            self.session.update_scoreboard(player_entries)
            await self.server.send_scoreboard_update([e.to_dict() for e in player_entries])

            recorder = get_recorder()
            if recorder and recorder.is_recording:
                full_frame = self.capture.capture_full_game_window()
                sb_regions_dict = {k: list(v) for k, v in SCOREBOARD_REGIONS.items()}
                recorder.record_frame(
                    full_frame=full_frame,
                    captured_regions=sb_regions_dict,
                    extracted_values={"players": [e.to_dict() for e in player_entries]},
                    game_state=self.state_machine.state.value
                )

    async def _input_monitor(self):
        log.debug("Input monitor started")
        while self.running:
            try:
                tab_down = is_tab_down()
                self.state_machine.handle_scoreboard_detected(tab_down)
                await asyncio.sleep(0.05)
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("Input monitor error: %s", e, exc_info=True)
                await asyncio.sleep(0.5)

    async def _game_detector(self):
        log.info("Game detector started (polling every 2s)")
        delay = 2
        while self.running:
            try:
                if self.game_window.find():
                    if self.state_machine.state == GameState.UNKNOWN:
                        self.state_machine.transition_to(GameState.MENU)
                        await self.server.send_state_change("menu")
                        delay = 60
                        log.info("Game found (polling every 60s for window loss)")
                else:
                    if self.state_machine.state != GameState.UNKNOWN:
                        log.info("Game window lost")
                        self.state_machine.reset()
                        await self.server.send_state_change("unknown")
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("Game detector error: %s", e, exc_info=True)
                await asyncio.sleep(5.0)

    def run(self):
        self._setup_logging()
        self._setup_debug()

        log.info("========================================")
        log.info("  FinalsTracker starting up")
        log.info("========================================")

        self._check_environment()

        async def async_main():
            runner = await self.server.start_async()
            log.info("Dashboard: http://%s:%d", self.server.host, self.server.port)

            tasks = [
                asyncio.create_task(self._game_detector(), name="game_detector"),
                asyncio.create_task(self._capture_loop(), name="capture_loop"),
                asyncio.create_task(self._input_monitor(), name="input_monitor"),
            ]
            try:
                done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
                for task in done:
                    exc = task.exception()
                    if exc:
                        log.critical("Task '%s' crashed: %s", task.get_name(), exc, exc_info=exc)
                for task in pending:
                    task.cancel()
            except asyncio.CancelledError:
                log.debug("All tasks cancelled")
            finally:
                log.info("Cleaning up...")
                recorder = get_recorder()
                if recorder and recorder.is_recording:
                    session_path = recorder.stop_session()
                    log.info(f"Debug session saved on shutdown: {session_path}")
                await runner.cleanup()
                self.capture.cleanup()

        try:
            asyncio.run(async_main())
        except KeyboardInterrupt:
            log.info("Shutdown requested (Ctrl+C)")


def main():
    import sys
    args = [a for a in sys.argv[1:] if a]
    if "--dump-windows" in args:
        from .log_config import setup_logging
        setup_logging(log_dir="logs", log_file="tracker.log")
        dump_all_windows()
        return
    config_path = args[0] if args and not args[0].startswith("--") else "config.json"
    if not os.path.isabs(config_path):
        config_path = os.path.join(os.path.dirname(__file__), "..", config_path)
    tracker = FinalsTracker(config_path)
    tracker.run()


if __name__ == "__main__":
    main()
