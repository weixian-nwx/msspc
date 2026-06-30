"""Webcam capture + QR decoding on a background thread.

Frames are emitted for live preview; decoded QR strings are emitted separately
with a debounce so the same code isn't fired repeatedly while it stays in view.
"""
from __future__ import annotations

import time

import cv2
from PySide6.QtCore import QThread, Signal

from app import config


class ScannerThread(QThread):
    # Emitted for every captured frame (BGR numpy array) for live preview.
    frame_ready = Signal(object)
    # Emitted once per distinct decode (after debounce) with the decoded string.
    qr_decoded = Signal(str)
    # Emitted if the camera cannot be opened or read.
    error = Signal(str)

    def __init__(self, camera_index: int = 0, parent=None) -> None:
        super().__init__(parent)
        self._camera_index = camera_index
        self._running = False
        self._detector = cv2.QRCodeDetector()
        self._last_value = ""
        self._last_time = 0.0

    def run(self) -> None:  # noqa: D401 - QThread entry point
        cap = cv2.VideoCapture(self._camera_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            # Fall back to the default backend.
            cap = cv2.VideoCapture(self._camera_index)
        if not cap.isOpened():
            self.error.emit(
                "Could not open the webcam. Check that a camera is connected "
                "and not in use by another application."
            )
            return

        self._running = True
        read_failures = 0
        try:
            while self._running:
                ok, frame = cap.read()
                if not ok:
                    read_failures += 1
                    if read_failures > 30:
                        self.error.emit("Lost connection to the webcam.")
                        break
                    self.msleep(30)
                    continue
                read_failures = 0

                self.frame_ready.emit(frame)

                try:
                    value, points, _ = self._detector.detectAndDecode(frame)
                except cv2.error:
                    value = ""

                if value:
                    self._handle_decode(value)

                # Throttle the loop a little to keep CPU reasonable (~30 fps cap).
                self.msleep(15)
        finally:
            # Always release the device so the camera powers off, even on error.
            cap.release()

    def _handle_decode(self, value: str) -> None:
        now = time.monotonic()
        if value == self._last_value and (now - self._last_time) < config.SCAN_DEBOUNCE_SECONDS:
            return
        self._last_value = value
        self._last_time = now
        self.qr_decoded.emit(value)

    def stop(self) -> None:
        # Block until run() returns and the finally-block has released the camera.
        # The loop's per-iteration msleep bounds this to well under a second.
        self._running = False
        self.wait()
