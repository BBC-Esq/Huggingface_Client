from __future__ import annotations
from PySide6.QtCore import QThread, Signal


class ApiWorker(QThread):
    finished = Signal(object)
    error = Signal(str)
    progress = Signal(int, int)

    def __init__(self, fn, *args, **kwargs) -> None:
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self._cancelled = False

    def run(self) -> None:
        try:
            result = self._fn(*self._args, **self._kwargs)
            if not self._cancelled:
                self.finished.emit(result)
        except Exception as e:
            if not self._cancelled:
                self.error.emit(str(e))

    def cancel(self) -> None:
        self._cancelled = True
