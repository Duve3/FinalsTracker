import sys
import os
from pathlib import Path
from typing import Optional, List, Tuple

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsRectItem,
    QGraphicsTextItem, QLabel, QPushButton, QFileDialog, QListWidget, QListWidgetItem,
    QSplitter, QGroupBox, QGridLayout, QStatusBar, QMessageBox, QLineEdit
)
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QPixmap, QColor, QPen, QBrush, QFont, QImage


class SelectionOverlay(QGraphicsRectItem):
    def __init__(self):
        super().__init__(0, 0, 0, 0)
        self.setPen(QPen(QColor(0, 255, 0), 2))
        self.setBrush(QBrush(QColor(0, 255, 0, 50)))
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable, False)


SAVED_REGION_COLORS = [
    QColor(255, 0, 127),
    QColor(0, 127, 255),
    QColor(127, 255, 0),
    QColor(255, 127, 0),
    QColor(127, 0, 255),
    QColor(0, 255, 127),
    QColor(255, 127, 127),
    QColor(127, 127, 255),
    QColor(255, 255, 127),
    QColor(127, 255, 255),
]


class SavedRegionOverlay(QGraphicsRectItem):
    def __init__(self, x: float, y: float, w: float, h: float, name: str, color: QColor):
        super().__init__(x, y, w, h)
        self.name = name
        self.setPen(QPen(color, 2))
        self.setBrush(QBrush(QColor(color.red(), color.green(), color.blue(), 80)))
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable, False)


class RegionCalibratorView(QGraphicsView):
    selection_made = None

    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self._selection_item = None
        self._selection_start = None
        self._image_item = None
        self._image_size = (0, 0)
        self._saved_region_items = []
        self._saved_regions = []

    def set_image(self, pixmap: QPixmap):
        self.scene.clear()
        self._image_size = (pixmap.width(), pixmap.height())

        if not pixmap.isNull():
            self._image_item = QGraphicsPixmapItem(pixmap)
            self.scene.addItem(self._image_item)
            self.scene.setSceneRect(0, 0, pixmap.width(), pixmap.height())

        self._selection_item = SelectionOverlay()
        self.scene.addItem(self._selection_item)
        self._redraw_saved_regions()
        self.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def update_saved_regions(self, regions):
        self._saved_regions = regions
        self._redraw_saved_regions()

    def _redraw_saved_regions(self):
        for item in self._saved_region_items:
            self.scene.removeItem(item)
        self._saved_region_items.clear()

        if not self._saved_regions or self._image_size[0] == 0:
            return

        img_w, img_h = self._image_size
        for i, (name, l, t, r, b) in enumerate(self._saved_regions):
            color = SAVED_REGION_COLORS[i % len(SAVED_REGION_COLORS)]
            x = l * img_w
            y = t * img_h
            w = (r - l) * img_w
            h = (b - t) * img_h

            rect_item = SavedRegionOverlay(x, y, w, h, name, color)
            self.scene.addItem(rect_item)
            self._saved_region_items.append(rect_item)

            text_item = QGraphicsTextItem(name)
            text_item.setPos(x, y)
            text_item.setDefaultTextColor(0)
            font = QFont("Arial", 20, QFont.Weight.Bold)
            text_item.setFont(font)
            self.scene.addItem(text_item)
            self._saved_region_items.append(text_item)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._image_item and self._selection_item:
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                pos = self.mapToScene(event.pos())
                self._selection_start = pos
                self._selection_item.setRect(QRectF(pos.x(), pos.y(), 0, 0))
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._selection_start and self._selection_item:
            pos = self.mapToScene(event.pos())
            x = min(self._selection_start.x(), pos.x())
            y = min(self._selection_start.y(), pos.y())
            w = abs(pos.x() - self._selection_start.x())
            h = abs(pos.y() - self._selection_start.y())
            self._selection_item.setRect(QRectF(x, y, w, h))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._selection_start and self._selection_item:
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self._selection_start = None
                rect = self._selection_item.rect()
                if rect.width() > 5 and rect.height() > 5:
                    self._notify_selection()
                event.accept()
                return
        super().mouseReleaseEvent(event)

    def _notify_selection(self):
        if not self._selection_item:
            return
        rect = self._selection_item.rect()
        img_w, img_h = self._image_size
        if img_w > 0 and img_h > 0:
            l = rect.x() / img_w
            t = rect.y() / img_h
            r = (rect.x() + rect.width()) / img_w
            b = (rect.y() + rect.height()) / img_h
            self.window().on_region_selected(l, t, r, b)

    def clear_selection(self):
        if self._selection_item:
            self._selection_item.setRect(QRectF(0, 0, 0, 0))

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            zoom = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self.scale(zoom, zoom)
            event.accept()
        else:
            super().wheelEvent(event)


class RegionCalibratorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Region Calibrator - FinalsTracker")
        self.setMinimumSize(1200, 800)
        self.current_image_path = None
        self.saved_regions: List[Tuple[str, float, float, float, float]] = []

        self._setup_ui()
        self.apply_dark_theme()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        toolbar = QHBoxLayout()
        self.load_btn = QPushButton("Load Screenshot")
        self.load_btn.clicked.connect(self._load_screenshot)
        self.clear_btn = QPushButton("Clear Selection")
        self.clear_btn.clicked.connect(self._clear_selection)
        self.copy_btn = QPushButton("Copy to Clipboard")
        self.copy_btn.clicked.connect(self._copy_to_clipboard)
        toolbar.addWidget(self.load_btn)
        toolbar.addWidget(self.clear_btn)
        toolbar.addWidget(self.copy_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.viewer = RegionCalibratorView()
        splitter.addWidget(self.viewer)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        info_group = QGroupBox("Current Selection")
        info_layout = QGridLayout()
        info_layout.addWidget(QLabel("Left:"), 0, 0)
        self.left_input = QLineEdit()
        self.left_input.setPlaceholderText("0.0000")
        self.left_input.textChanged.connect(self._on_manual_input_changed)
        info_layout.addWidget(self.left_input, 0, 1)
        info_layout.addWidget(QLabel("Top:"), 1, 0)
        self.top_input = QLineEdit()
        self.top_input.setPlaceholderText("0.0000")
        self.top_input.textChanged.connect(self._on_manual_input_changed)
        info_layout.addWidget(self.top_input, 1, 1)
        info_layout.addWidget(QLabel("Right:"), 2, 0)
        self.right_input = QLineEdit()
        self.right_input.setPlaceholderText("0.0000")
        self.right_input.textChanged.connect(self._on_manual_input_changed)
        info_layout.addWidget(self.right_input, 2, 1)
        info_layout.addWidget(QLabel("Bottom:"), 3, 0)
        self.bottom_input = QLineEdit()
        self.bottom_input.setPlaceholderText("0.0000")
        self.bottom_input.textChanged.connect(self._on_manual_input_changed)
        info_layout.addWidget(self.bottom_input, 3, 1)
        self.apply_btn = QPushButton("Apply Selection")
        self.apply_btn.clicked.connect(self._apply_manual_selection)
        info_layout.addWidget(self.apply_btn, 4, 0, 1, 2)
        info_group.setLayout(info_layout)
        right_layout.addWidget(info_group)

        saved_group = QGroupBox("Saved Regions")
        saved_layout = QVBoxLayout()
        self.regions_list = QListWidget()
        saved_layout.addWidget(self.regions_list)
        btn_row = QHBoxLayout()
        self.save_region_btn = QPushButton("Save Region")
        self.save_region_btn.clicked.connect(self._save_current_region)
        self.remove_region_btn = QPushButton("Remove")
        self.remove_region_btn.clicked.connect(self._remove_selected_region)
        btn_row.addWidget(self.save_region_btn)
        btn_row.addWidget(self.remove_region_btn)
        saved_layout.addLayout(btn_row)
        saved_group.setLayout(saved_layout)
        right_layout.addWidget(saved_group)

        export_group = QGroupBox("Export")
        export_layout = QVBoxLayout()
        self.export_btn = QPushButton("Export All as Python Dict")
        self.export_btn.clicked.connect(self._export_regions)
        export_layout.addWidget(self.export_btn)
        export_group.setLayout(export_layout)
        right_layout.addWidget(export_group)

        right_layout.addStretch()
        splitter.addWidget(right_panel)
        splitter.setSizes([800, 400])

        layout.addWidget(splitter, 1)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Load a screenshot to start")

    def apply_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #1a1a1a; }
            QWidget { background-color: #1a1a1a; color: #ffffff; }
            QLabel { color: #ffffff; }
            QPushButton { background-color: #333333; color: #ffffff; border: 1px solid #555555; padding: 5px; }
            QPushButton:hover { background-color: #444444; }
            QGroupBox { border: 1px solid #444444; margin-top: 10px; padding-top: 10px; }
            QGroupBox::title { color: #00ff00; }
            QListWidget { background-color: #222222; color: #ffffff; border: 1px solid #444444; }
            QSplitter::handle { background-color: #333333; }
            QStatusBar { background-color: #222222; color: #cccccc; }
        """)

    def _load_screenshot(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Screenshot", "", "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if file_path:
            self.current_image_path = file_path
            pixmap = QPixmap(file_path)
            if pixmap.isNull():
                QMessageBox.warning(self, "Error", "Failed to load image")
                return
            self.viewer.set_image(pixmap)
            self.status_bar.showMessage(f"Loaded: {os.path.basename(file_path)} ({pixmap.width()}x{pixmap.height()}) - Hold SHIFT + drag to select a region")

    def on_region_selected(self, l: float, t: float, r: float, b: float):
        self.left_input.setText(f"{l:.4f}")
        self.top_input.setText(f"{t:.4f}")
        self.right_input.setText(f"{r:.4f}")
        self.bottom_input.setText(f"{b:.4f}")
        self._update_visual_selection(l, t, r, b)
        self.status_bar.showMessage("Region selected - click 'Save Region' to store it")

    def _on_manual_input_changed(self):
        try:
            l = float(self.left_input.text()) if self.left_input.text() else 0
            t = float(self.top_input.text()) if self.top_input.text() else 0
            r = float(self.right_input.text()) if self.right_input.text() else 0
            b = float(self.bottom_input.text()) if self.bottom_input.text() else 0
            self._update_visual_selection(l, t, r, b)
        except ValueError:
            pass

    def _update_visual_selection(self, l: float, t: float, r: float, b: float):
        if self.viewer._image_item:
            img_w = self.viewer._image_size[0]
            img_h = self.viewer._image_size[1]
            x = l * img_w
            y = t * img_h
            w = (r - l) * img_w
            h = (b - t) * img_h
            self.viewer._selection_item.setRect(QRectF(x, y, w, h))

    def _apply_manual_selection(self):
        try:
            l = float(self.left_input.text())
            t = float(self.top_input.text())
            r = float(self.right_input.text())
            b = float(self.bottom_input.text())
            self.status_bar.showMessage(f"Manual region set: ({l:.4f}, {t:.4f}, {r:.4f}, {b:.4f})")
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please enter valid numeric values")

    def _clear_selection(self):
        self.viewer.clear_selection()
        self.left_input.clear()
        self.top_input.clear()
        self.right_input.clear()
        self.bottom_input.clear()

    def _save_current_region(self):
        try:
            l = float(self.left_input.text())
            t = float(self.top_input.text())
            r = float(self.right_input.text())
            b = float(self.bottom_input.text())
        except ValueError:
            QMessageBox.warning(self, "No Selection", "Please select or enter a region first")
            return

        region = (l, t, r, b)
        name, ok = self._get_region_name()
        if not ok:
            return

        self.saved_regions.append((name, *region))
        self.regions_list.addItem(f"{name}: ({l:.4f}, {t:.4f}, {r:.4f}, {b:.4f})")
        self.viewer.update_saved_regions(self.saved_regions)
        self.status_bar.showMessage(f"Saved region: {name}")

    def _get_region_name(self):
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Region Name", "Enter a name for this region:")
        return name.strip() if ok else "", ok

    def _remove_selected_region(self):
        row = self.regions_list.currentRow()
        if row >= 0:
            self.saved_regions.pop(row)
            self.regions_list.takeItem(row)
            self.viewer.update_saved_regions(self.saved_regions)

    def _copy_to_clipboard(self):
        try:
            l = float(self.left_input.text())
            t = float(self.top_input.text())
            r = float(self.right_input.text())
            b = float(self.bottom_input.text())
            text = f"({l:.4f}, {t:.4f}, {r:.4f}, {b:.4f})"
        except ValueError:
            return
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(text)
        self.status_bar.showMessage(f"Copied: {text}")
        self.copy_btn.setText("Copied!")
        self.copy_btn.setStyleSheet("background-color: #00aa00; color: white;")
        def reset_btn():
            self.copy_btn.setText("Copy to Clipboard")
            self.copy_btn.setStyleSheet("")
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1500, reset_btn)

    def _export_regions(self):
        if not self.saved_regions:
            QMessageBox.warning(self, "No Regions", "No regions to export")
            return

        code = "REGIONS = {\n"
        for name, l, t, r, b in self.saved_regions:
            code += f'    "{name}": ({l:.4f}, {t:.4f}, {r:.4f}, {b:.4f}),\n'
        code += "}\n"

        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(code)
        self.status_bar.showMessage("Exported to clipboard as Python dict")
        self.export_btn.setText("Exported!")
        self.export_btn.setStyleSheet("background-color: #00aa00; color: white;")
        def reset_btn():
            self.export_btn.setText("Export All as Python Dict")
            self.export_btn.setStyleSheet("")
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1500, reset_btn)


def launch_calibrator():
    app = QApplication(sys.argv)
    window = RegionCalibratorWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    launch_calibrator()