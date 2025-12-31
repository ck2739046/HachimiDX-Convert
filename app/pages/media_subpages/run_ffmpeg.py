from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.pages.base_tool_page import BaseToolPage
from app.ui_style import COLORS

from app.widgets import (
    FileSelectRow,
    HelpIcon,
    OptionalFloatLineEdit,
    OptionalSignedFloatLineEdit,
    SegmentedControl,
    StyledCheckBox,
    StyledComboBox,
    ValidatedLineEdit,
    QuickActionButton,
    SubmitButton,
)

from tasks.task_scheduler import TaskScheduler
from tasks.task_configs import RunFfmpegTaskConfig

class RunFfmpegPage(BaseToolPage):
    def setup_content(self):
        self._scheduler = TaskScheduler.instance()

        # Bind scheduler media process output into this page log.
        try:
            self._scheduler.get_media_process().readyReadStandardOutput.connect(
                self.output_widget.handle_raw_output
            )
        except Exception:
            pass

        self._input_path: str | None = None
        self._detected_type: str | None = None
        self._input_duration_sec: float | None = None
        self._origin_width: int | None = None
        self._origin_height: int | None = None
        self._origin_fps: float | None = None

        wrapper = QWidget()
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(10)

        # Row 1: file select + detect
        row1 = QWidget()
        row1_l = QHBoxLayout(row1)
        row1_l.setContentsMargins(0, 0, 0, 0)
        row1_l.setSpacing(5)

        self.file_row = FileSelectRow(button_text="Select file")
        self.file_row.fileSelected.connect(self._on_file_selected)
        row1_l.addWidget(self.file_row, 1)

        script_path = str(self._project_root() / "core" / "ffmpeg_utils" / "ffprobe_launcher.py")
        self.detect_btn = QuickActionButton(
            text_idle="Detect",
            text_running="Cancel",
            program=sys.executable,
            args_builder=lambda: ["-u", script_path, (self._input_path or "")],
            output_widget=self.output_widget,
            parse_json=True,
        )
        self.detect_btn.setFixedSize(100, 25)
        self.detect_btn.jsonReady.connect(self._on_detect_json)
        row1_l.addWidget(self.detect_btn)
        row1_l.addWidget(HelpIcon("Run ffprobe to detect media type and stream info."))

        wrapper_layout.addWidget(row1)

        # Row 2: detected info
        row2 = QWidget()
        row2_l = QHBoxLayout(row2)
        row2_l.setContentsMargins(0, 0, 0, 0)
        row2_l.setSpacing(10)

        self.detected_label = QLabel("type: (not detected)")
        self.detected_label.setStyleSheet(f"color: {COLORS['accent']}; font-size: 13px; font-weight: bold;")
        row2_l.addWidget(self.detected_label)

        self.streams_label = QLabel("")
        self.streams_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        self.streams_label.setWordWrap(True)
        row2_l.addWidget(self.streams_label, 1)

        wrapper_layout.addWidget(row2)

        # Row 3: media type manual override
        row3 = QWidget()
        row3_l = QHBoxLayout(row3)
        row3_l.setContentsMargins(0, 0, 0, 0)
        row3_l.setSpacing(10)

        row3_l.addWidget(self._label("Media type"))
        self.media_type_seg = SegmentedControl(["audio", "video", "video_muted"], height=25)
        self.media_type_seg.valueChanged.connect(self._on_media_type_changed)
        row3_l.addWidget(self.media_type_seg)
        row3_l.addStretch(1)
        wrapper_layout.addWidget(row3)

        # Options grid
        self.options_panel = QWidget()
        self.options_grid = QGridLayout(self.options_panel)
        self.options_grid.setContentsMargins(0, 0, 0, 0)
        self.options_grid.setHorizontalSpacing(10)
        self.options_grid.setVerticalSpacing(8)
        wrapper_layout.addWidget(self.options_panel)

        self._build_options_controls()
        self._refresh_visibility()

        # Submit row
        submit_row = QWidget()
        submit_l = QHBoxLayout(submit_row)
        submit_l.setContentsMargins(0, 0, 0, 0)
        submit_l.setSpacing(10)

        self.submit_btn = SubmitButton("Submit")
        self.submit_btn.clicked.connect(self._on_submit)
        submit_l.addWidget(self.submit_btn)
        submit_l.addWidget(HelpIcon("Submit a ffmpeg task to the scheduler. Output appears in the log below."))
        submit_l.addStretch(1)
        wrapper_layout.addWidget(submit_row)

        self.content_layout.addWidget(wrapper)

    # ===== UI helpers =====

    def _project_root(self) -> Path:
        return Path(__file__).resolve().parents[3]

    def _label(self, text: str) -> QLabel:
        lb = QLabel(text)
        lb.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 13px;")
        return lb

    def _small_label(self, text: str) -> QLabel:
        lb = QLabel(text)
        lb.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        return lb

    def _mk_checkbox(self, checked: bool) -> StyledCheckBox:
        cb = StyledCheckBox(size=18)
        cb.setChecked(bool(checked))
        return cb

    # ===== Controls =====

    def _build_options_controls(self) -> None:
        r = 0

        # Common: clear metadata
        self.clear_metadata_cb = self._mk_checkbox(True)
        self.options_grid.addWidget(self._label("Clear metadata"), r, 0)
        self.options_grid.addWidget(self.clear_metadata_cb, r, 1)
        self.options_grid.addWidget(HelpIcon("Add -map_metadata -1"), r, 2)
        r += 1

        # Timing
        self.trim_start_in = OptionalFloatLineEdit(value_type="double", min_val=0.0, max_val=86400.0, decimals=3, width=120, placeholder="sec")
        self.trim_end_in = OptionalSignedFloatLineEdit(min_val=-86400.0, max_val=86400.0, decimals=3, width=120, placeholder="sec (neg ok)")
        self.pad_start_in = OptionalFloatLineEdit(value_type="double", min_val=0.0, max_val=86400.0, decimals=3, width=120, placeholder="sec")
        self.pad_end_in = OptionalFloatLineEdit(value_type="double", min_val=0.0, max_val=86400.0, decimals=3, width=120, placeholder="sec")

        self.options_grid.addWidget(self._label("Trim start"), r, 0)
        self.options_grid.addWidget(self.trim_start_in, r, 1)
        self.options_grid.addWidget(HelpIcon("-ss (mutually exclusive with pad start)"), r, 2)
        r += 1

        self.options_grid.addWidget(self._label("Trim end"), r, 0)
        self.options_grid.addWidget(self.trim_end_in, r, 1)
        self.options_grid.addWidget(HelpIcon("-to. Negative means: duration + value (requires detect)."), r, 2)
        r += 1

        self.options_grid.addWidget(self._label("Pad start"), r, 0)
        self.options_grid.addWidget(self.pad_start_in, r, 1)
        self.options_grid.addWidget(HelpIcon("audio: adelay, video: tpad start_duration"), r, 2)
        r += 1

        self.options_grid.addWidget(self._label("Pad end"), r, 0)
        self.options_grid.addWidget(self.pad_end_in, r, 1)
        self.options_grid.addWidget(HelpIcon("audio: apad, video: tpad stop_duration"), r, 2)
        r += 1

        # Audio section
        self.options_grid.addWidget(self._label("Audio format"), r, 0)
        self.audio_format_combo = StyledComboBox(width=120)
        self.audio_format_combo.set_items(["ogg", "mp3"], default_index=0)
        self.options_grid.addWidget(self.audio_format_combo, r, 1)
        r += 1

        self.options_grid.addWidget(self._label("Audio quality"), r, 0)
        self.audio_quality_combo = StyledComboBox(width=120)
        self.audio_quality_combo.set_items(["0", "1", "2"], default_index=1)
        self.options_grid.addWidget(self.audio_quality_combo, r, 1)
        r += 1

        self.options_grid.addWidget(self._label("Sample rate"), r, 0)
        self.sample_rate_combo = StyledComboBox(width=120)
        self.sample_rate_combo.set_items(["44100", "48000"], default_index=0)
        self.options_grid.addWidget(self.sample_rate_combo, r, 1)
        r += 1

        self.options_grid.addWidget(self._label("Volume %"), r, 0)
        self.volume_in = ValidatedLineEdit(value_type="int", min_val=0, max_val=200, width=120, placeholder="0-200")
        self.volume_in.setText("100")
        self.options_grid.addWidget(self.volume_in, r, 1)
        r += 1

        # Video section
        self.options_grid.addWidget(self._label("Use origin resolution"), r, 0)
        self.use_origin_res_cb = self._mk_checkbox(True)
        self.use_origin_res_cb.stateChanged.connect(lambda _: self._refresh_video_enablement())
        self.options_grid.addWidget(self.use_origin_res_cb, r, 1)
        r += 1

        self.options_grid.addWidget(self._label("Width"), r, 0)
        self.width_in = OptionalFloatLineEdit(value_type="int", min_val=16, max_val=7680, width=120, placeholder="px")
        self.options_grid.addWidget(self.width_in, r, 1)
        self.options_grid.addWidget(self._small_label("(origin shown after detect)"), r, 2)
        r += 1

        self.options_grid.addWidget(self._label("Height"), r, 0)
        self.height_in = OptionalFloatLineEdit(value_type="int", min_val=16, max_val=4320, width=120, placeholder="px")
        self.options_grid.addWidget(self.height_in, r, 1)
        r += 1

        self.options_grid.addWidget(self._label("Use origin fps"), r, 0)
        self.use_origin_fps_cb = self._mk_checkbox(True)
        self.use_origin_fps_cb.stateChanged.connect(lambda _: self._refresh_video_enablement())
        self.options_grid.addWidget(self.use_origin_fps_cb, r, 1)
        r += 1

        self.options_grid.addWidget(self._label("FPS"), r, 0)
        self.fps_in = OptionalFloatLineEdit(value_type="double", min_val=0.1, max_val=240.0, decimals=3, width=120, placeholder="fps")
        self.options_grid.addWidget(self.fps_in, r, 1)
        r += 1

        self.options_grid.addWidget(self._label("CRF"), r, 0)
        self.crf_in = ValidatedLineEdit(value_type="int", min_val=0, max_val=51, width=120)
        self.crf_in.setText("23")
        self.options_grid.addWidget(self.crf_in, r, 1)
        r += 1

        self.options_grid.addWidget(self._label("Preset"), r, 0)
        self.preset_combo = StyledComboBox(width=160)
        self.preset_combo.set_items(
            [
                "ultrafast",
                "superfast",
                "veryfast",
                "faster",
                "fast",
                "medium",
                "slow",
                "slower",
                "veryslow",
            ],
            default_index=5,
        )
        self.options_grid.addWidget(self.preset_combo, r, 1)
        r += 1

        self.options_grid.addWidget(self._label("GOP=30"), r, 0)
        self.gop_cb = self._mk_checkbox(False)
        self.options_grid.addWidget(self.gop_cb, r, 1)
        self.options_grid.addWidget(HelpIcon("If checked, sets -g 30"), r, 2)
        r += 1

        # Keep references for show/hide
        self._audio_rows = set(range(4, 8))  # audio_format..volume (approx; refreshed below)

        self._refresh_video_enablement()

    def _refresh_video_enablement(self) -> None:
        use_origin_res = self.use_origin_res_cb.isChecked()
        self.width_in.setEnabled(not use_origin_res)
        self.height_in.setEnabled(not use_origin_res)

        use_origin_fps = self.use_origin_fps_cb.isChecked()
        self.fps_in.setEnabled(not use_origin_fps)

    def _refresh_visibility(self) -> None:
        media = self._current_media_type()
        is_video = media in ("video", "video_muted")

        # Row indices in the grid are fixed by insertion order above.
        # 0 clear_metadata
        # 1-4 timing
        # 5-8 audio (format/quality/sr/volume)
        # 9+ video (origin res/width/height/origin fps/fps/crf/preset/gop)
        for row in range(self.options_grid.rowCount()):
            show = True
            if row >= 9:
                show = is_video
            # audio controls are always relevant for audio + video (except muted still uses quality/sr for nothing; we keep visible for simplicity)
            if media == "video_muted" and 5 <= row <= 8:
                # Keep audio format visible only for pure audio.
                show = False

            for col in range(self.options_grid.columnCount()):
                item = self.options_grid.itemAtPosition(row, col)
                if item is None:
                    continue
                w = item.widget()
                if w is None:
                    continue
                w.setVisible(show)

        self._refresh_video_enablement()

    def _current_media_type(self) -> str:
        idx = self.media_type_seg.index()
        return ["audio", "video", "video_muted"][idx if 0 <= idx <= 2 else 0]

    # ===== Events =====

    def _on_file_selected(self, path: str) -> None:
        self._input_path = path
        self._detected_type = None
        self._input_duration_sec = None
        self._origin_width = None
        self._origin_height = None
        self._origin_fps = None

        self.detected_label.setText("type: (not detected)")
        self.streams_label.setText("")

    def _on_media_type_changed(self, _idx: int) -> None:
        self._refresh_visibility()

    def _on_detect_json(self, obj: Any) -> None:
        if not isinstance(obj, dict):
            self.output_widget.append_text("[detect] invalid JSON")
            return

        ok = bool(obj.get("ok"))
        if not ok:
            self.detected_label.setText("type: unknown")
            self.streams_label.setText(str(obj.get("error") or "detect failed"))
            return

        file_type = str(obj.get("file_type") or "unknown")
        streams = obj.get("streams") or []

        self._detected_type = file_type
        self.detected_label.setText(f"type: {file_type}")

        # Try extract duration + origin info
        self._input_duration_sec = None
        self._origin_width = None
        self._origin_height = None
        self._origin_fps = None

        lines: list[str] = []
        if isinstance(streams, list):
            for s in streams:
                if not isinstance(s, dict):
                    continue
                ctype = s.get("codec_type")
                codec = s.get("codec_name")
                dur = s.get("duration")
                if dur is not None:
                    try:
                        d = float(dur)
                        if self._input_duration_sec is None or d > self._input_duration_sec:
                            self._input_duration_sec = d
                    except Exception:
                        pass

                if ctype == "video":
                    w = s.get("width")
                    h = s.get("height")
                    try:
                        self._origin_width = int(w) if w is not None else self._origin_width
                        self._origin_height = int(h) if h is not None else self._origin_height
                    except Exception:
                        pass

                    afr = s.get("avg_frame_rate")
                    try:
                        if isinstance(afr, str) and "/" in afr:
                            n, d = afr.split("/", 1)
                            self._origin_fps = float(n) / float(d) if float(d) != 0 else None
                        elif afr is not None:
                            self._origin_fps = float(afr)
                    except Exception:
                        pass

                if ctype in ("audio", "video"):
                    lines.append(f"{ctype}:{codec}")

        info = ", ".join(lines)
        if self._origin_width and self._origin_height:
            info += f" | {self._origin_width}x{self._origin_height}"
        if self._origin_fps:
            info += f" | {self._origin_fps:.3f} fps"
        if self._input_duration_sec:
            info += f" | {self._input_duration_sec:.3f} sec"
        self.streams_label.setText(info)

        # Set segmented selection based on detect
        mapping = {"audio": 0, "video": 1, "video_muted": 2}
        if file_type in mapping:
            self.media_type_seg.set_index(mapping[file_type])
        self._refresh_visibility()

    def _on_submit(self) -> None:
        if not self._input_path:
            self.output_widget.append_text("[submit] please select a file")
            return

        media_type = self._current_media_type()

        # Validate timing mutual exclusion at UI level too (for clearer messages)
        ts = self.trim_start_in.get_value()
        te = self.trim_end_in.get_value()
        ps = self.pad_start_in.get_value()
        pe = self.pad_end_in.get_value()

        if ts.error:
            self.output_widget.append_text(f"[submit] trim_start_sec: {ts.error}")
            return
        if te.error:
            self.output_widget.append_text(f"[submit] trim_end_sec: {te.error}")
            return
        if ps.error:
            self.output_widget.append_text(f"[submit] pad_start_sec: {ps.error}")
            return
        if pe.error:
            self.output_widget.append_text(f"[submit] pad_end_sec: {pe.error}")
            return

        if ts.value is not None and ps.value is not None:
            self.output_widget.append_text("[submit] trim_start_sec and pad_start_sec cannot both be set")
            return
        if te.value is not None and pe.value is not None:
            self.output_widget.append_text("[submit] trim_end_sec and pad_end_sec cannot both be set")
            return

        vol = self.volume_in.get_value()
        if vol.error:
            self.output_widget.append_text(f"[submit] volume: {vol.error}")
            return

        crf = self.crf_in.get_value()
        if crf.error:
            self.output_widget.append_text(f"[submit] crf: {crf.error}")
            return

        width = self.width_in.get_value()
        if width.error:
            self.output_widget.append_text(f"[submit] width: {width.error}")
            return

        height = self.height_in.get_value()
        if height.error:
            self.output_widget.append_text(f"[submit] height: {height.error}")
            return

        fps = self.fps_in.get_value()
        if fps.error:
            self.output_widget.append_text(f"[submit] fps: {fps.error}")
            return

        # Negative trim_end requires duration from detect
        input_duration = self._input_duration_sec
        if te.value is not None and float(te.value) < 0 and not input_duration:
            self.output_widget.append_text("[submit] negative trim_end_sec requires Detect (duration)")
            return

        try:
            cfg = RunFfmpegTaskConfig(
                input_path=self._input_path,
                media_type=media_type,
                clear_metadata=self.clear_metadata_cb.isChecked(),
                trim_start_sec=(float(ts.value) if ts.value is not None else None),
                trim_end_sec=(float(te.value) if te.value is not None else None),
                pad_start_sec=(float(ps.value) if ps.value is not None else None),
                pad_end_sec=(float(pe.value) if pe.value is not None else None),
                input_duration_sec=input_duration,
                audio_format=self.audio_format_combo.currentText(),
                audio_quality=int(self.audio_quality_combo.currentText()),
                sample_rate=int(self.sample_rate_combo.currentText()),
                volume=int(vol.value) if vol.value is not None else 100,
                use_origin_resolution=self.use_origin_res_cb.isChecked(),
                width=(int(width.value) if width.value is not None else None),
                height=(int(height.value) if height.value is not None else None),
                use_origin_fps=self.use_origin_fps_cb.isChecked(),
                fps=(float(fps.value) if fps.value is not None else None),
                crf=int(crf.value) if crf.value is not None else 23,
                preset=self.preset_combo.currentText(),
                gop_30=self.gop_cb.isChecked(),
            )
        except Exception as e:
            self.output_widget.append_text(f"[submit] config error: {e}")
            return

        task_id = self._scheduler.submit_media_task(cfg, task_name="Run FFmpeg")
        self.output_widget.append_text(f"[submit] accepted task_id={task_id}")
        if cfg.output_path is not None:
            self.output_widget.append_text(f"[submit] output: {cfg.output_path}")
