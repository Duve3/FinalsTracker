import sys
import os
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
import cv2
import numpy as np
from dataclasses import dataclass

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsRectItem,
    QGraphicsTextItem, QSplitter, QSlider, QLabel, QPushButton,
    QScrollArea, QGroupBox, QSizePolicy, QFileDialog, QMessageBox,
    QComboBox, QStatusBar, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QPixmap, QColor, QPen, QBrush, QFont, QPainter

COLOR_HUD = QColor(255, 165, 0, 180)
COLOR_SCOREBOARD = QColor(0, 128, 255, 180)
COLOR_SUMMARY = QColor(255, 0, 255, 180)


@dataclass
class LoadedFrame:
    frame_id: str
    timestamp: float
    raw_image_path: str
    regions: Dict[str, List[float]]
    extracted_values: Dict[str, Any]
    game_state: str


class RegionOverlayItem(QGraphicsRectItem):
    def __init__(self, x: float, y: float, w: float, h: float, label: str, color: QColor):
        super().__init__(x, y, w, h)
        self.setPen(QPen(color, 2))
        self.setBrush(QBrush(color))
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable, False)


class ImageViewer(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self._current_pixmap_item = None

    def set_frame(self, pixmap: QPixmap, regions: Dict[str, List[float]]):
        self.scene.clear()
        self._current_pixmap_item = None

        if not pixmap.isNull():
            self._current_pixmap_item = QGraphicsPixmapItem(pixmap)
            self.scene.addItem(self._current_pixmap_item)
            self.scene.setSceneRect(0, 0, pixmap.width(), pixmap.height())

            img_w = pixmap.width()
            img_h = pixmap.height()

            for name, region in regions.items():
                if len(region) >= 4:
                    l, t, r, b = region
                    x = l * img_w
                    y = t * img_h
                    w = (r - l) * img_w
                    h = (b - t) * img_h

                    color = COLOR_HUD if "score" in name.lower() or "timer" in name.lower() else COLOR_SCOREBOARD

                    rect_item = RegionOverlayItem(x, y, w, h, name, color)
                    self.scene.addItem(rect_item)

                    text_item = QGraphicsTextItem(name)
                    text_item.setPos(x, max(0, y - 18))
                    text_item.setDefaultTextColor(QColor(0, 255, 0))
                    font = QFont("Arial", 9, QFont.Weight.Bold)
                    text_item.setFont(font)
                    self.scene.addItem(text_item)

        self.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            zoom = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self.scale(zoom, zoom)
            event.accept()
        else:
            super().wheelEvent(event)


class DataPanel(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        search_layout = QHBoxLayout()
        search_label = QLabel("Search:")
        search_label.setStyleSheet("color: #888888;")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter keys...")
        self.search_input.setStyleSheet("background-color: #333333; color: #ffffff; border: 1px solid #555555; padding: 3px;")
        self.search_input.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)

        self._current_data = None
        self._current_frame = None

        self.group_boxes = {}
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(10)

        groups = ["Frame Info", "Extracted Values"]
        for group_name in groups:
            gb = QGroupBox(group_name)
            gb_layout = QVBoxLayout()
            gb.setLayout(gb_layout)
            self.group_boxes[group_name] = gb_layout
            container_layout.addWidget(gb)

        container_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

    def _on_search_changed(self, text):
        if self._current_frame:
            self._display_data(self._current_frame, text.lower() if text else "")

    def update_data(self, frame: LoadedFrame):
        self._current_frame = frame
        search_text = self.search_input.text().lower() if self.search_input.text() else ""
        self._display_data(frame, search_text)

    def _display_data(self, frame: LoadedFrame, search_text: str):
        for gb in self.group_boxes.values():
            while gb.count():
                w = gb.takeAt(0).widget()
                if w:
                    w.deleteLater()

        self._add_row_filtered("Frame ID", frame.frame_id, "Frame Info", search_text)
        self._add_row_filtered("Timestamp", f"{frame.timestamp:.3f}", "Frame Info", search_text)
        self._add_row_filtered("Game State", frame.game_state, "Frame Info", search_text)

        for key, value in frame.extracted_values.items():
            if isinstance(value, dict):
                for sub_key, sub_val in value.items():
                    full_key = f"{key}.{sub_key}"
                    self._add_row_filtered(full_key, str(sub_val), "Extracted Values", search_text)
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        for sub_key, sub_val in item.items():
                            full_key = f"{key}[{i}].{sub_key}"
                            self._add_row_filtered(full_key, str(sub_val), "Extracted Values", search_text)
            else:
                self._add_row_filtered(key, str(value), "Extracted Values", search_text)

    def _add_row_filtered(self, key: str, value: str, group: str, search_text: str):
        if search_text and search_text not in key.lower():
            return
        if group in self.group_boxes:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            key_label = QLabel(key)
            key_label.setStyleSheet("color: #00ff00; font-weight: bold;")
            key_label.setFixedWidth(150)
            key_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            val_label = QLabel(str(value))
            val_label.setStyleSheet("color: #ffffff;")
            val_label.setWordWrap(True)
            row_layout.addWidget(key_label)
            row_layout.addWidget(val_label, 1)
            self.group_boxes[group].addWidget(row)

    def _add_row(self, key: str, value: str, group: str):
        if group in self.group_boxes:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            key_label = QLabel(key)
            key_label.setStyleSheet("color: #00ff00; font-weight: bold;")
            key_label.setFixedWidth(150)
            key_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            val_label = QLabel(str(value))
            val_label.setStyleSheet("color: #ffffff;")
            val_label.setWordWrap(True)
            row_layout.addWidget(key_label)
            row_layout.addWidget(val_label, 1)
            self.group_boxes[group].addWidget(row)


STATE_COLORS = {
    "menu": QColor(128, 128, 128),
    "loading": QColor(255, 165, 0),
    "ingame": QColor(0, 255, 0),
    "scoreboard": QColor(0, 128, 255),
    "summary": QColor(255, 0, 255),
    "unknown": QColor(64, 64, 64),
}


class StateTimeline(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(24)
        self._states = []
        self._timestamps = []
        self._current_frame = 0
        self._total_frames = 0
        self._group_size = 5

    def set_data(self, states: list, timestamps: list, current_frame: int, total_frames: int):
        self._states = states
        self._timestamps = timestamps
        self._current_frame = current_frame
        self._total_frames = total_frames
        self.update()

    def paintEvent(self, event):
        if not self._states or self._total_frames == 0:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        if len(self._timestamps) < 2:
            frame_width = w / self._total_frames
            for i, state in enumerate(self._states):
                color = STATE_COLORS.get(state.lower(), STATE_COLORS["unknown"])
                x = i * frame_width
                painter.fillRect(int(x), 0, max(1, int(frame_width)), h, color)
        else:
            total_duration = self._timestamps[-1] - self._timestamps[0]
            if total_duration <= 0:
                total_duration = 1

            for i in range(0, len(self._states), self._group_size):
                group_end = min(i + self._group_size, len(self._states))
                state = self._states[i]

                if group_end < len(self._timestamps):
                    group_duration = self._timestamps[group_end] - self._timestamps[i]
                else:
                    group_duration = 0.1

                bar_width = (group_duration / total_duration) * w
                bar_width = max(2, int(bar_width))

                color = STATE_COLORS.get(state.lower(), STATE_COLORS["unknown"])
                x_start = int((self._timestamps[i] - self._timestamps[0]) / total_duration * w)
                painter.fillRect(x_start, 0, bar_width, h, color)

        if self._total_frames > 0 and len(self._timestamps) > 0:
            total_duration = self._timestamps[-1] - self._timestamps[0]
            if total_duration > 0:
                indicator_pos = (self._timestamps[self._current_frame] - self._timestamps[0]) / total_duration * w
                painter.fillRect(int(indicator_pos) - 1, 0, 3, h, QColor(255, 255, 255))


class TimelineControl(QWidget):
    position_changed = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        top_row = QHBoxLayout()
        self.play_btn = QPushButton("▶ Play")
        self.play_btn.setFixedWidth(80)
        self.frame_label = QLabel("Frame: 0 / 0")
        self.frame_label.setStyleSheet("color: #ffffff;")
        self.state_label = QLabel("State: -")
        self.state_label.setStyleSheet("color: #aaaaaa;")
        top_row.addWidget(self.play_btn)
        top_row.addWidget(self.frame_label)
        top_row.addWidget(self.state_label)
        top_row.addStretch()
        layout.addLayout(top_row)

        self.state_timeline = StateTimeline()
        layout.addWidget(self.state_timeline)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setValue(0)
        self.slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider.setTickInterval(1)
        self.slider.valueChanged.connect(self._on_slider_changed)
        layout.addWidget(self.slider)

        legend_row = QHBoxLayout()
        legend_label = QLabel("Legend:")
        legend_label.setStyleSheet("color: #888888;")
        legend_row.addWidget(legend_label)
        for state, color in STATE_COLORS.items():
            color_label = QLabel(state.upper())
            color_label.setStyleSheet(f"color: {color.name()}; font-size: 10px;")
            legend_row.addWidget(color_label)
        legend_row.addStretch()
        layout.addLayout(legend_row)

        bottom_row = QHBoxLayout()
        self.prev_frame_btn = QPushButton("◀◀")
        self.prev_frame_btn.setFixedWidth(50)
        self.prev_frame_btn.clicked.connect(self._prev_frame)
        self.next_frame_btn = QPushButton("▶▶")
        self.next_frame_btn.setFixedWidth(50)
        self.next_frame_btn.clicked.connect(self._next_frame)
        self.goto_start_btn = QPushButton("|<")
        self.goto_start_btn.setFixedWidth(40)
        self.goto_start_btn.clicked.connect(self._goto_start)
        self.goto_end_btn = QPushButton(">|")
        self.goto_end_btn.setFixedWidth(40)
        self.goto_end_btn.clicked.connect(self._goto_end)
        speed_label = QLabel("Speed:")
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["0.25x", "0.5x", "1x", "2x", "4x"])
        self.speed_combo.setCurrentText("1x")
        bottom_row.addWidget(self.goto_start_btn)
        bottom_row.addWidget(self.prev_frame_btn)
        bottom_row.addStretch()
        bottom_row.addWidget(speed_label)
        bottom_row.addWidget(self.speed_combo)
        bottom_row.addStretch()
        bottom_row.addWidget(self.next_frame_btn)
        bottom_row.addWidget(self.goto_end_btn)
        layout.addLayout(bottom_row)

        self.is_playing = False
        self.play_timer = QTimer()
        self.play_timer.timeout.connect(self._play_next)
        self.current_fps = 10

    def _on_slider_changed(self, value):
        self.position_changed.emit(value)

    def _play_next(self):
        if self.slider.value() < self.slider.maximum():
            self.slider.setValue(self.slider.value() + 1)
        else:
            self.stop()

    def play(self):
        self.is_playing = True
        self.play_btn.setText("⏸ Pause")
        interval = 1000 / self.current_fps
        speed = float(self.speed_combo.currentText().rstrip('x'))
        self.play_timer.start(int(interval / speed))

    def stop(self):
        self.is_playing = False
        self.play_btn.setText("▶ Play")
        self.play_timer.stop()

    def toggle(self):
        if self.is_playing:
            self.stop()
        else:
            self.play()

    def set_total_frames(self, total: int, states: list = None, timestamps: list = None):
        self.slider.setMaximum(max(0, total - 1))
        self.frame_label.setText(f"Frame: 0 / {total}")
        if states and timestamps:
            self.state_timeline.set_data(states, timestamps, 0, total)

    def set_current_frame(self, frame: int, state: str = None, timestamp: float = None):
        self.slider.setValue(frame)
        self.frame_label.setText(f"Frame: {frame} / {self.slider.maximum() + 1}")
        if state:
            self.state_label.setText(f"State: {state}")
        if self.state_timeline._total_frames > 0 and self.state_timeline._timestamps:
            self.state_timeline.set_data(
                self.state_timeline._states,
                self.state_timeline._timestamps,
                frame,
                self.state_timeline._total_frames
            )

    def set_fps(self, fps: int):
        self.current_fps = fps

    def _prev_frame(self):
        self.slider.setValue(max(0, self.slider.value() - 1))

    def _next_frame(self):
        self.slider.setValue(min(self.slider.maximum(), self.slider.value() + 1))

    def _goto_start(self):
        self.slider.setValue(0)

    def _goto_end(self):
        self.slider.setValue(self.slider.maximum())


class DebugReplayWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FinalsTracker Debug Replay")
        self.setMinimumSize(1400, 900)
        self.frames: List[LoadedFrame] = []
        self.current_frame_index = 0
        self.session_metadata = None
        self._last_loaded_session = None

        self._setup_ui()
        self._setup_menu()
        self.apply_dark_theme()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.timeline = TimelineControl()
        self.timeline.position_changed.connect(self._on_timeline_changed)
        self.timeline.play_btn.clicked.connect(self.timeline.toggle)
        main_layout.addWidget(self.timeline)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.viewer = ImageViewer()
        splitter.addWidget(self.viewer)

        self.data_panel = DataPanel()
        splitter.addWidget(self.data_panel)
        splitter.setSizes([1000, 400])

        main_layout.addWidget(splitter, 1)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("No session loaded")

    def _setup_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("File")
        open_action = file_menu.addAction("Open Session...")
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._open_session)
        file_menu.addSeparator()
        exit_action = file_menu.addAction("Exit")
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)

        view_menu = menubar.addMenu("View")
        zoom_in_action = view_menu.addAction("Zoom In")
        zoom_in_action.setShortcut("Ctrl++")
        zoom_in_action.triggered.connect(lambda: self.viewer.scale(1.2, 1.2))
        zoom_out_action = view_menu.addAction("Zoom Out")
        zoom_out_action.setShortcut("Ctrl+-")
        zoom_out_action.triggered.connect(lambda: self.viewer.scale(1/1.2, 1/1.2))
        fit_action = view_menu.addAction("Fit to Window")
        fit_action.setShortcut("Ctrl+0")
        fit_action.triggered.connect(self._fit_to_window)

    def apply_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #1a1a1a; }
            QWidget { background-color: #1a1a1a; color: #ffffff; }
            QLabel { color: #ffffff; }
            QPushButton { background-color: #333333; color: #ffffff; border: 1px solid #555555; padding: 5px; }
            QPushButton:hover { background-color: #444444; }
            QPushButton:pressed { background-color: #222222; }
            QSlider::groove:horizontal { background: #333333; height: 8px; }
            QSlider::handle:horizontal { background: #00aa00; width: 14px; margin: -3px 0; }
            QSlider::sub-page:horizontal { background: #00aa00; }
            QGroupBox { border: 1px solid #444444; margin-top: 10px; padding-top: 10px; }
            QGroupBox::title { color: #00ff00; }
            QScrollArea { background-color: #1a1a1a; }
            QSplitter::handle { background-color: #333333; }
            QMenuBar { background-color: #222222; color: #ffffff; }
            QMenuBar::item:selected { background-color: #333333; }
            QMenu { background-color: #222222; color: #ffffff; }
            QMenu::item:selected { background-color: #333333; }
            QStatusBar { background-color: #222222; color: #cccccc; }
            QComboBox { background-color: #333333; color: #ffffff; border: 1px solid #555555; }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView { background-color: #333333; color: #ffffff; }
        """)

    def _open_session(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Debug Session Directory")
        if dir_path:
            self.load_session(dir_path)

    def load_session(self, session_path: str):
        session_path_obj = Path(session_path)
        metadata_path = session_path_obj / "metadata.json"
        frames_dir = session_path_obj / "frames"

        if not metadata_path.exists():
            QMessageBox.warning(self, "Error", "No metadata.json found in session directory")
            return

        with open(metadata_path, 'r') as f:
            self.session_metadata = json.load(f)

        capture_config = self.session_metadata.get("capture_config", {})
        self.timeline.set_fps(capture_config.get("fps", 10))

        self.frames = []
        frame_dirs = sorted(frames_dir.iterdir(), key=lambda x: x.name)

        for frame_dir in frame_dirs:
            if not frame_dir.is_dir():
                continue

            frame_metadata_path = frame_dir / "metadata.json"
            if not frame_metadata_path.exists():
                continue

            with open(frame_metadata_path, 'r') as f:
                frame_meta = json.load(f)

            raw_path = frame_dir / "raw.png"
            if not raw_path.exists():
                continue

            loaded_frame = LoadedFrame(
                frame_id=frame_meta.get("frame_id", frame_dir.name),
                timestamp=frame_meta.get("timestamp", 0),
                raw_image_path=str(raw_path),
                regions=frame_meta.get("regions", {}),
                extracted_values=frame_meta.get("extracted_values", {}),
                game_state=frame_meta.get("game_state", "unknown")
            )
            self.frames.append(loaded_frame)

        self._last_loaded_session = session_path
        states = [f.game_state for f in self.frames]
        timestamps = [f.timestamp for f in self.frames]
        self.timeline.set_total_frames(len(self.frames), states, timestamps)
        self.status_bar.showMessage(f"Loaded {len(self.frames)} frames from {session_path_obj.name}")

        if self.frames:
            self._show_frame(0)

    def _show_frame(self, index: int):
        if 0 <= index < len(self.frames):
            self.current_frame_index = index
            frame = self.frames[index]
            self.timeline.set_current_frame(index, frame.game_state, frame.timestamp)

            if os.path.exists(frame.raw_image_path):
                pixmap = QPixmap(frame.raw_image_path)
                self.viewer.set_frame(pixmap, frame.regions)

            self.data_panel.update_data(frame)
            self.status_bar.showMessage(f"Frame {index + 1}/{len(self.frames)}: {frame.frame_id} | State: {frame.game_state}")

    def _on_timeline_changed(self, position: int):
        self._show_frame(position)

    def _fit_to_window(self):
        self.viewer.fitInView(self.viewer.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)


def launch_replay(session_path: Optional[str] = None):
    app = QApplication(sys.argv)
    window = DebugReplayWindow()
    window.show()
    if session_path and os.path.isdir(session_path):
        window.load_session(session_path)
    sys.exit(app.exec())


if __name__ == "__main__":
    session = sys.argv[1] if len(sys.argv) > 1 else None
    if session is not None:
        launch_replay(session)
    else:
        launch_replay()