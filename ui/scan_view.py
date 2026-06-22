"""Live webcam preview with a colored result banner for each scan."""
from __future__ import annotations

import cv2
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from app.scanner import ScannerThread


class ScanView(QWidget):
    """Owns the scanner thread and renders frames + scan feedback.

    The owner connects to ``on_decoded`` by passing a callback that returns a
    (level, message) tuple, where level is 'ok' | 'warn' | 'error'.
    """

    def __init__(self, decode_handler, parent=None) -> None:
        super().__init__(parent)
        self._decode_handler = decode_handler
        self._scanner: ScannerThread | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.video = QLabel("Camera off")
        self.video.setAlignment(Qt.AlignCenter)
        self.video.setMinimumSize(480, 360)
        self.video.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video.setStyleSheet(
            "background:#1e1e1e; color:#bbb; border-radius:8px; font-size:15px;"
        )
        layout.addWidget(self.video, 1)

        self.banner = QLabel("")
        self.banner.setAlignment(Qt.AlignCenter)
        self.banner.setWordWrap(True)
        self.banner.setMinimumHeight(56)
        self.banner.setStyleSheet(self._banner_style("idle"))
        self.banner.setText("Scanner stopped.")
        layout.addWidget(self.banner)

        # Clears a transient banner back to a neutral 'ready' state.
        self._reset_timer = QTimer(self)
        self._reset_timer.setSingleShot(True)
        self._reset_timer.timeout.connect(self._set_ready)

    # ----------------------------------------------------------- lifecycle
    def start(self) -> bool:
        if self._scanner is not None:
            return True
        self._scanner = ScannerThread()
        self._scanner.frame_ready.connect(self._on_frame)
        self._scanner.qr_decoded.connect(self._on_decoded)
        self._scanner.error.connect(self._on_error)
        self._scanner.start()
        self._set_ready()
        return True

    def stop(self) -> None:
        if self._scanner is not None:
            self._scanner.stop()
            self._scanner = None
        self.video.setText("Camera off")
        self.video.setPixmap(QPixmap())
        self._show_banner("idle", "Scanner stopped.")

    def is_running(self) -> bool:
        return self._scanner is not None

    # -------------------------------------------------------------- slots
    def _on_frame(self, frame) -> None:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        img = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        pix = QPixmap.fromImage(img).scaled(
            self.video.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.video.setPixmap(pix)

    def _on_decoded(self, value: str) -> None:
        level, message = self._decode_handler(value)
        self._show_banner(level, message)
        self._reset_timer.start(2500)

    def _on_error(self, message: str) -> None:
        self._show_banner("error", message)

    # -------------------------------------------------------------- banner
    def _set_ready(self) -> None:
        if self.is_running():
            self._show_banner("ready", "Ready — present a QR code to the camera.")

    def _show_banner(self, level: str, text: str) -> None:
        self.banner.setStyleSheet(self._banner_style(level))
        self.banner.setText(text)

    @staticmethod
    def _banner_style(level: str) -> str:
        colors = {
            "ok": ("#1e7e34", "#d4edda"),
            "warn": ("#b8860b", "#fff3cd"),
            "error": ("#a71d2a", "#f8d7da"),
            "ready": ("#0b5ed7", "#e7f1ff"),
            "idle": ("#555", "#eee"),
        }
        fg, bg = colors.get(level, colors["idle"])
        return (
            f"background:{bg}; color:{fg}; border:1px solid {fg}; "
            "border-radius:8px; font-size:16px; font-weight:600; padding:8px;"
        )
