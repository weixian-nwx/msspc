"""Live webcam preview with a colored result overlay for each scan."""
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

        # Translucent colored wash drawn over the video on each scan. It is a
        # child of this widget (not in the layout) so it can float on top; its
        # geometry is kept in sync with the widget in resizeEvent.
        self.overlay = QLabel("", self)
        self.overlay.setAlignment(Qt.AlignCenter)
        self.overlay.setWordWrap(True)
        self.overlay.hide()

        # Clears a transient scan overlay back to the clean live view.
        self._reset_timer = QTimer(self)
        self._reset_timer.setSingleShot(True)
        self._reset_timer.timeout.connect(self._hide_overlay)

    # ----------------------------------------------------------- lifecycle
    def start(self) -> bool:
        if self._scanner is not None:
            return True
        self._scanner = ScannerThread()
        self._scanner.frame_ready.connect(self._on_frame)
        self._scanner.qr_decoded.connect(self._on_decoded)
        self._scanner.error.connect(self._on_error)
        self._scanner.start()
        self._hide_overlay()
        return True

    def stop(self) -> None:
        if self._scanner is not None:
            self._scanner.stop()
            self._scanner = None
        self._hide_overlay()
        self.video.setText("Camera off")
        self.video.setPixmap(QPixmap())

    def is_running(self) -> bool:
        return self._scanner is not None

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt override
        # Keep the overlay covering the full video area as the window resizes.
        self.overlay.setGeometry(self.rect())
        super().resizeEvent(event)

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
        self._show_overlay(level, message)
        # Persist the result briefly, then clear back to the clean live view.
        self._reset_timer.start(2500)

    def _on_error(self, message: str) -> None:
        # Errors stay visible until the next scan or stop (no auto-clear).
        self._reset_timer.stop()
        self._show_overlay("error", message)

    # ------------------------------------------------------------- overlay
    def _show_overlay(self, level: str, text: str) -> None:
        self.overlay.setStyleSheet(self._overlay_style(level))
        self.overlay.setText(text)
        self.overlay.setGeometry(self.rect())
        self.overlay.show()
        self.overlay.raise_()

    def _hide_overlay(self) -> None:
        self._reset_timer.stop()
        self.overlay.hide()

    @staticmethod
    def _overlay_style(level: str) -> str:
        # (r, g, b) of the translucent wash drawn over the video.
        colors = {
            "ok": (30, 126, 52),
            "warn": (184, 134, 11),
            "error": (167, 29, 42),
            "ready": (11, 94, 215),
        }
        r, g, b = colors.get(level, (40, 40, 40))
        return (
            f"background:rgba({r},{g},{b},190); color:#ffffff; "
            "border-radius:8px; font-size:32px; font-weight:700; padding:24px;"
        )
