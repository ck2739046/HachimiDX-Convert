from __future__ import annotations

import json
from typing import Callable, Optional

from PyQt6.QtCore import QObject, QProcess, pyqtSignal
from PyQt6.QtWidgets import QPushButton

from app import ui_style
from app.widgets.output_log import OutputLogWidget
from tasks.qprocess_utils import kill_qprocess_tree


class QuickActionButton(QPushButton):
    """Blue 'Run' button that becomes red 'Cancel' while a QProcess is running.

    - Owns a QProcess.
    - Forwards raw output into an OutputLogWidget (if provided).

    Typical usage:
        btn = QuickActionButton(
            text_idle='Detect',
            program=sys.executable,
            args_builder=lambda: [script_path, input_path],
            output_widget=page.output_widget,
            parse_json=True,
        )
    """

    jsonReady = pyqtSignal(object)  # parsed JSON object
    finishedText = pyqtSignal(str)  # full collected text
    processStarted = pyqtSignal()
    processEnded = pyqtSignal(int)  # exit code

    def __init__(
        self,
        *,
        text_idle: str,
        text_running: str = "Cancel",
        program: str,
        args_builder: Callable[[], list[str]],
        output_widget: Optional[OutputLogWidget] = None,
        parse_json: bool = False,
        parent: Optional[QObject] = None,
    ):
        super().__init__(text_idle, parent)

        self._text_idle = text_idle
        self._text_running = text_running
        self._program = program
        self._args_builder = args_builder
        self._output_widget = output_widget
        self._parse_json = parse_json

        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)

        self._buffer = ""

        self._process.readyReadStandardOutput.connect(self._on_ready_read)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)

        self.clicked.connect(self._on_clicked)

        self._apply_idle_style()

    @property
    def is_running(self) -> bool:
        return self._process.state() != QProcess.ProcessState.NotRunning

    def _apply_idle_style(self) -> None:
        self.setText(self._text_idle)
        self.setStyleSheet(
            f"""
            QPushButton {{ background-color: {ui_style.COLORS['accent']}; color: {ui_style.COLORS['text_primary']}; border: none; }}
            QPushButton:hover {{ background-color: {ui_style.COLORS['accent_hover']}; }}
            """
        )

    def _apply_running_style(self) -> None:
        self.setText(self._text_running)
        self.setStyleSheet(
            f"""
            QPushButton {{ background-color: {ui_style.COLORS['stop']}; color: {ui_style.COLORS['text_primary']}; border: none; }}
            QPushButton:hover {{ background-color: {ui_style.COLORS['stop_hover']}; }}
            """
        )

    def _on_clicked(self) -> None:
        if self.is_running:
            self.cancel()
            return

        self._buffer = ""
        args = self._args_builder() or []

        self._process.setProgram(self._program)
        self._process.setArguments(args)
        self._apply_running_style()

        if self._output_widget is not None:
            self._output_widget.append_text(f"[quick] running: {self._program} {' '.join(args)}")

        self._process.start()
        self.processStarted.emit()

    def cancel(self) -> None:
        if not self.is_running:
            return
        if self._output_widget is not None:
            self._output_widget.append_text("[quick] cancel requested")
        kill_qprocess_tree(self._process)

    def _on_ready_read(self) -> None:
        out = self._process.readAllStandardOutput()
        if not out:
            return

        # Decode similarly to OutputLogWidget
        raw = bytes(out)
        try:
            text = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            text = raw.decode("gbk", errors="replace")

        self._buffer += text

        if self._output_widget is not None:
            # Feed text into the output widget using its raw pipeline.
            self._output_widget.feed_raw_text(text)

    def _on_error(self, err: QProcess.ProcessError) -> None:
        if self._output_widget is not None:
            self._output_widget.append_text(f"[quick] process_error={err.name}")

    def _on_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        _ = exit_status
        self._apply_idle_style()
        self.processEnded.emit(int(exit_code))

        text = self._buffer
        self.finishedText.emit(text)

        if self._parse_json:
            try:
                obj = json.loads(text.strip())
                self.jsonReady.emit(obj)
            except Exception as e:
                if self._output_widget is not None:
                    self._output_widget.append_text(f"[quick] JSON parse failed: {e}")
