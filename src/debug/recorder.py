import json
import os
import time
import threading
import queue
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import cv2
import numpy as np

from ..log_config import get_logger

log = get_logger(__name__)


class AsyncDiskWriter:
    def __init__(self):
        self._queue: queue.Queue = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._current_session_path = None
        self._frame_count = 0

    def start_session(self, session_path: Path):
        self._current_session_path = session_path
        self._frame_count = 0
        self._running = True
        self._thread = threading.Thread(target=self._writer_loop, daemon=True)
        self._thread.start()
        log.debug("AsyncDiskWriter: started writer thread")

    def stop_session(self) -> Optional[str]:
        if not self._running:
            return None
        self._running = False
        self._queue.put(None)
        if self._thread:
            self._thread.join(timeout=5)
        session_path = str(self._current_session_path) if self._current_session_path else None
        self._current_session_path = None
        log.debug(f"AsyncDiskWriter: stopped, wrote {self._frame_count} frames")
        return session_path

    def write_frame(self, frame_data: dict):
        if self._running:
            try:
                self._queue.put_nowait(frame_data)
            except queue.Full:
                log.warning("AsyncDiskWriter: queue full, dropping frame")

    def _writer_loop(self):
        while self._running:
            try:
                frame_data = self._queue.get(timeout=0.1)
                if frame_data is None:
                    continue
                self._write_frame_to_disk(frame_data)
            except queue.Empty:
                continue
            except Exception as e:
                log.error(f"AsyncDiskWriter: error writing frame: {e}")

    def _write_frame_to_disk(self, frame_data: dict):
        if self._current_session_path is None:
            return

        frame_id = frame_data["frame_id"]
        timestamp = frame_data["timestamp"]
        regions = frame_data["regions"]
        extracted_values = frame_data["extracted_values"]
        game_state = frame_data["game_state"]
        full_frame = frame_data.get("full_frame")

        frames_dir = self._current_session_path / "frames" / frame_id
        frames_dir.mkdir(exist_ok=True)

        if full_frame is not None:
            raw_path = frames_dir / "raw.png"
            cv2.imwrite(str(raw_path), full_frame)

        frame_metadata = {
            "frame_id": frame_id,
            "timestamp": timestamp,
            "regions": regions,
            "extracted_values": extracted_values,
            "game_state": game_state,
        }
        frame_metadata_path = frames_dir / "metadata.json"
        with open(frame_metadata_path, 'w') as f:
            json.dump(frame_metadata, f, indent=2)

        self._frame_count += 1
        if self._frame_count % 50 == 0:
            log.debug(f"AsyncDiskWriter: written {self._frame_count} frames")


class DebugRecorder:
    def __init__(self, session_dir: str = "debug_sessions"):
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.current_session_id = None
        self.current_session_path = None
        self.frame_count = 0
        self.is_recording = False
        self._session_config = {}
        self._writer = AsyncDiskWriter()
        self._session_start_time = None

    def _load_session_config(self):
        try:
            config_path = Path("config.json")
            if config_path.exists():
                with open(config_path, 'r') as f:
                    self._session_config = json.load(f)
        except Exception:
            pass

    def start_session(self, session_name: Optional[str] = None):
        if session_name is None:
            session_name = f"session_{time.strftime('%Y%m%d_%H%M%S')}"
        self.current_session_id = session_name
        self.current_session_path = self.session_dir / session_name
        self.current_session_path.mkdir(parents=True, exist_ok=True)
        (self.current_session_path / "frames").mkdir(exist_ok=True)
        self.frame_count = 0
        self._session_start_time = time.time()
        self.is_recording = True
        self._load_session_config()
        self._writer.start_session(self.current_session_path)
        log.info(f"Debug recording started: {session_name}")

    def stop_session(self) -> Optional[str]:
        if not self.is_recording or self.current_session_path is None:
            return None
        self.is_recording = False
        session_path = self._writer.stop_session()
        self._save_session_metadata()
        log.info(f"Debug recording stopped: {self.frame_count} frames saved to {session_path}")
        self.current_session_id = None
        self.current_session_path = None
        return session_path

    def _save_session_metadata(self):
        if self.current_session_path is None:
            return
        metadata = {
            "session_id": self.current_session_id,
            "start_time": self._session_start_time or time.time(),
            "end_time": time.time(),
            "frame_count": self.frame_count,
            "capture_config": {
                "fps": self._session_config.get("capture", {}).get("fps", 10),
                "window_title": self._session_config.get("game", {}).get("window_title", "THE FINALS"),
            }
        }
        metadata_path = self.current_session_path / "metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

    def record_frame(self,
                     full_frame: Optional[np.ndarray] = None,
                     captured_regions: Optional[Dict[str, List[float]]] = None,
                     extracted_values: Optional[Dict[str, Any]] = None,
                     game_state: str = "unknown"):
        if not self.is_recording or self.current_session_path is None:
            return

        frame_id = f"frame_{self.frame_count:06d}"
        timestamp = time.time()

        frame_data = {
            "frame_id": frame_id,
            "timestamp": timestamp,
            "regions": captured_regions or {},
            "extracted_values": extracted_values or {},
            "game_state": game_state,
            "full_frame": full_frame,
        }

        self._writer.write_frame(frame_data)

        self.frame_count += 1
        if self.frame_count % 50 == 0:
            log.debug(f"Queued {self.frame_count} frames for writing")

    def get_session_path(self) -> Optional[str]:
        if self.current_session_path:
            return str(self.current_session_path)
        return None


class DebugRecorderSingleton:
    _instance = None
    _recorder = None

    @classmethod
    def get_instance(cls) -> Optional[DebugRecorder]:
        if cls._instance is None:
            cls._instance = cls()
            cls._recorder = DebugRecorder()
        return cls._recorder


def get_recorder() -> Optional[DebugRecorder]:
    return DebugRecorderSingleton.get_instance()