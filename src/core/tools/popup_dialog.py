from __future__ import annotations

import ctypes
import os
import threading

import i18n
from PyQt6.QtCore import QEventLoop, QTimer, Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QApplication, QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


class _PopupConfirmDialog(QDialog):
    def __init__(self, title: str, prompt_text: str, *, timeout_seconds: int = 30):
        super().__init__()

        self._prompt_text = prompt_text
        self._seconds_left = int(timeout_seconds)
        self._result_value = False

        self.setWindowTitle(title)
        self.setModal(False)
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setFixedSize(450, 200)

        self._label = QLabel()
        self._label.setWordWrap(True)
        self._label.setTextFormat(Qt.TextFormat.PlainText)
        self._label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self._confirm_button = QPushButton(i18n.t("popup_dialog.ui_confirm"))
        self._cancel_button = QPushButton(i18n.t("popup_dialog.ui_cancel"))

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(self._confirm_button)
        btn_row.addSpacing(20)
        btn_row.addWidget(self._cancel_button)
        btn_row.addStretch(1)

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 10, 20, 15)
        layout.addWidget(self._label, 1)
        layout.addLayout(btn_row)
        self.setLayout(layout)

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

        self._confirm_button.clicked.connect(self._on_confirm)
        self._cancel_button.clicked.connect(self._on_cancel)
        self.rejected.connect(self._on_cancel)

        self._refresh_text()
        self._timer.start()

        self._center_on_primary_screen()

    def _center_on_primary_screen(self) -> None:
        try:
            screen = QGuiApplication.primaryScreen()
            if screen is None:
                return
            geo = screen.availableGeometry()
            self.move(
                int(geo.x() + (geo.width() - self.width()) / 2),
                int(geo.y() + (geo.height() - self.height()) / 2),
            )
        except Exception:
            return

    def _refresh_text(self) -> None:
        hint = i18n.t("popup_dialog.ui_timeout_hint", seconds=self._seconds_left)
        self._label.setText(f"{self._prompt_text}{hint}")

    def _finish(self, value: bool) -> None:
        self._result_value = bool(value)
        try:
            self._timer.stop()
        except Exception:
            pass
        try:
            self.close()
        except Exception:
            pass

    def _on_confirm(self) -> None:
        self._finish(True)

    def _on_cancel(self) -> None:
        self._finish(False)

    def _tick(self) -> None:
        self._seconds_left -= 1
        if self._seconds_left < 0:
            self._on_cancel()
            return
        self._refresh_text()

    def result_value(self) -> bool:
        return bool(self._result_value)


def show_confirm_dialog(title: str, prompt_text: str) -> bool:
    """A tiny blocking confirm dialog.

    Public API contract (keep it simple):
    - Accepts only (title: str, prompt_text: str)
    - Blocks until user decides or 30s timeout
    - Returns bool (Confirm=True, Cancel/timeout/error=False)

    Note: Windows-only behavior is acceptable for this tool.
    """

    # One giant try/except: anything goes wrong -> default cancel.
    try:
        if os.name == "nt":
            try:
                # Provide an independent taskbar icon group for this process.
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                    "hachimidx.converter.tools.popup_dialog"
                )
            except Exception:
                pass

        # If caller calls this from a non-main thread, Qt will warn and behavior is undefined.
        # This tool keeps it simple: non-main-thread calls fail closed (return False).
        if threading.current_thread() is not threading.main_thread():
            return False

        app = QApplication.instance()
        created_app = False
        if app is None:
            created_app = True
            app = QApplication([])
            app.setQuitOnLastWindowClosed(True)

        dialog = _PopupConfirmDialog(title, prompt_text, timeout_seconds=30)
        event_loop = QEventLoop()
        dialog.finished.connect(lambda _code: event_loop.quit())
        dialog.show()
        event_loop.exec()

        if created_app:
            try:
                app.processEvents()
            except Exception:
                pass

        return dialog.result_value()

    except Exception:
        return False



if __name__ == "__main__":

    # init i18n
    tool_dir = os.path.dirname(os.path.abspath(__file__))
    locales_dir = os.path.normpath(os.path.join(tool_dir, "../../resources/locales"))
    i18n.load_path.append(locales_dir)
    i18n.set("filename_format", "{locale}.yaml")
    i18n.set("locale", "zh_CN")
    i18n.set("fallback", "en_US")

    # Multi-dialog manual test
    # 1st dialog shows immediately, 2nd dialog shows after 2 seconds
    app = QApplication.instance() or QApplication([])

    results: dict[str, bool] = {}

    d1 = _PopupConfirmDialog("弹窗1", "这是第一个弹窗，用于测试多弹窗同时显示。")
    d1.finished.connect(lambda _code: results.__setitem__("d1", d1.result_value()))
    d1.show()

    def _show_second() -> None:
        d2 = _PopupConfirmDialog("弹窗2", "这是第二个弹窗，应该与第一个同时存在。")
        d2.finished.connect(lambda _code: results.__setitem__("d2", d2.result_value()))
        d2.finished.connect(lambda _code: app.quit() if "d1" in results else None)
        d2.show()

    QTimer.singleShot(2000, _show_second)
    app.exec()
    print(f"Results: {results}")
