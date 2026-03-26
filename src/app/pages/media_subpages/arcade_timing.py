from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QLabel, QVBoxLayout

from ..base_output_page import BaseOutputPage
from ...widgets import *
from ...ui_style import UI_Style

from src.core.build_worker_cmd import build_cmd_head_python_exe
from src.core.schemas.op_result import OpResult, ok, err, print_op_result
from src.core.tools import show_notify_dialog
from src.services import process_manager_api
from src.services.path_manage import PathManage
import i18n


I18N_Prefix = "app.media_subpages.arcade_timing"


class ArcadeTimingPage(BaseOutputPage):

    def setup_content(self):
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(10, 10, 10, 10)

        self.reference_path_display = None
        self.target_path_display = None

        self.bpm_line_edit = None
        self.click_count_combo_box = None
        self.click_start_time_line_edit = None

        self.run_button = None
        self.waveform_label = None

        self._active_runner_id = None

        self._build_file_section()
        self._build_param_section()
        self._build_preview_section()

        process_manager_api.get_signals().runner_output.connect(self.output_widget.handle_process_output)
        process_manager_api.get_signals().runner_ended.connect(self.output_widget.handle_process_ended)
        process_manager_api.get_signals().runner_ended.connect(self._on_runner_ended)

        self.content_layout.addStretch()



    def _build_file_section(self) -> None:
        self.content_layout.addWidget(create_divider(i18n.t(f"{I18N_Prefix}.ui_select_file_divider")))

        reference_button, self.reference_path_display, reference_help = create_file_selection_row(
            button_text=i18n.t(f"{I18N_Prefix}.ui_reference_file_button"),
            help_text=i18n.t(f"{I18N_Prefix}.ui_reference_file_help"),
        )
        self.create_row(reference_button, reference_help, self.reference_path_display)

        target_button, self.target_path_display, target_help = create_file_selection_row(
            button_text=i18n.t(f"{I18N_Prefix}.ui_target_file_button"),
            help_text=i18n.t(f"{I18N_Prefix}.ui_target_file_help"),
        )
        self.create_row(target_button, target_help, self.target_path_display)



    def _build_param_section(self) -> None:
        self.content_layout.addWidget(create_divider(i18n.t(f"{I18N_Prefix}.ui_params_divider")))

        bpm_label = create_label(i18n.t(f"{I18N_Prefix}.ui_bpm_label"))
        self.bpm_line_edit = create_line_edit(length=70, validator="float")
        bpm_help = create_help_icon(i18n.t(f"{I18N_Prefix}.ui_bpm_help"))

        click_count_label = create_label(i18n.t(f"{I18N_Prefix}.ui_click_count_label"))
        self.click_count_combo_box = create_combo_box(
            items=[str(i) for i in range(1, 10)], default_index=3, length=50)
        click_count_help = create_help_icon(i18n.t(f"{I18N_Prefix}.ui_click_count_help"))

        click_start_label = create_label(i18n.t(f"{I18N_Prefix}.ui_click_start_time_label"))
        self.click_start_time_line_edit = create_line_edit(default_text="0", length=70, validator="float")
        click_start_help = create_help_icon(i18n.t(f"{I18N_Prefix}.ui_click_start_time_help"))

        self.create_row(
            bpm_label,
            self.bpm_line_edit,
            bpm_help,
            click_count_label,
            self.click_count_combo_box,
            click_count_help,
            click_start_label,
            self.click_start_time_line_edit,
            click_start_help,
            add_stretch=True,
        )

        self.content_layout.addSpacing(UI_Style.widget_spacing)
        self.run_button = create_stated_button(i18n.t(f"{I18N_Prefix}.ui_run_button"), isbig=True)
        self.run_button.clicked.connect(self.on_run_clicked)

        self.create_row(self.run_button, add_stretch=True)



    def _build_preview_section(self) -> None:
        self.content_layout.addWidget(create_divider(i18n.t(f"{I18N_Prefix}.ui_preview_divider")))

        self.waveform_label = QLabel()
        self.waveform_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.waveform_label.setMinimumHeight(210)
        self.waveform_label.hide()
        self.content_layout.addWidget(self.waveform_label)



    def _parse_inputs(self) -> OpResult[dict]:
        reference_file = (self.reference_path_display.text() if self.reference_path_display else "").strip()
        target_file = (self.target_path_display.text() if self.target_path_display else "").strip()

        if not reference_file:
            return err(i18n.t(f"{I18N_Prefix}.warning_reference_file_required"))
        if not target_file:
            return err(i18n.t(f"{I18N_Prefix}.warning_target_file_required"))

        try:
            bpm = float((self.bpm_line_edit.text() if self.bpm_line_edit else "").strip())
        except Exception:
            return err(i18n.t(f"{I18N_Prefix}.warning_invalid_bpm"))
        if not 10 <= bpm <= 400:
            return err(i18n.t(f"{I18N_Prefix}.warning_invalid_bpm"))

        try:
            click_count = int((self.click_count_combo_box.currentText()).strip())
        except Exception:
            return err(i18n.t(f"{I18N_Prefix}.warning_invalid_click_count"))
        if click_count < 1:
            return err(i18n.t(f"{I18N_Prefix}.warning_invalid_click_count"))

        try:
            click_start_time = float((self.click_start_time_line_edit.text() if self.click_start_time_line_edit else "").strip())
        except Exception:
            return err(i18n.t(f"{I18N_Prefix}.warning_invalid_click_start_time"))
        if click_start_time < 0:
            return err(i18n.t(f"{I18N_Prefix}.warning_invalid_click_start_time"))

        return ok({
            "reference_file": reference_file,
            "target_file": target_file,
            "bpm": bpm,
            "click_count": click_count,
            "click_start_time": click_start_time,
        })



    def on_run_clicked(self) -> None:
        if self._active_runner_id:
            return

        self.run_button.setEnabled(False)
        self.waveform_label.hide()
        self.waveform_label.clear()

        try:
            res = self._parse_inputs()
            if not res.is_ok:
                show_notify_dialog(i18n.t(f"{I18N_Prefix}.dialog_title"), res.error_msg)
                return
            data = res.value

            cmd = build_cmd_head_python_exe(PathManage.AUDIO_ALIGN_WORKER_PATH)
            cmd.extend([
                str(data["reference_file"]),
                str(data["target_file"]),
                str(data["bpm"]),
                str(data["click_count"]),
                str(data["click_start_time"]),
            ])

            self.output_widget.append_text(i18n.t(f"{I18N_Prefix}.notice_run_start"))

            result = process_manager_api.start(cmd)
            if not result.is_ok:
                show_notify_dialog(
                    i18n.t(f"{I18N_Prefix}.dialog_title"),
                    i18n.t(f"{I18N_Prefix}.warning_worker_start_failed", error=print_op_result(result)),
                )
                return

            self._active_runner_id = result.value
            self.output_widget.bind_current_runner_id(self._active_runner_id)

        finally:
            if not self._active_runner_id:
                self.run_button.setEnabled(True)



    def _on_runner_ended(self, runner_id: str, ended) -> None:
        if not self._active_runner_id or runner_id != self._active_runner_id:
            return

        self._active_runner_id = None
        self.run_button.setEnabled(True)

        if getattr(ended, "cancelled", False):
            self.output_widget.append_text(i18n.t(f"{I18N_Prefix}.notice_run_cancelled"))
            return

        failed = bool(getattr(ended, "crashed", False))
        exit_code = getattr(ended, "exit_code", None)
        if exit_code is None or exit_code != 0:
            failed = True

        if failed:
            self.output_widget.append_text(i18n.t(f"{I18N_Prefix}.warning_run_failed"))
            return

        self.output_widget.append_text(i18n.t(f"{I18N_Prefix}.notice_run_success"))
        self._try_show_wave_image()



    def _try_show_wave_image(self) -> None:

        wave_path = PathManage.TEMP_WAV_IMAGE_PATH
        if not wave_path.is_file():
            self.output_widget.append_text(i18n.t(f"{I18N_Prefix}.warning_wave_not_found"))
            return

        pixmap = QPixmap(str(Path(wave_path)))
        if pixmap.isNull():
            self.output_widget.append_text(i18n.t(f"{I18N_Prefix}.warning_wave_load_failed"))
            return

        self.waveform_label.setPixmap(pixmap)
        self.waveform_label.show()

        try:
            if wave_path.is_file():
                wave_path.unlink()
        except Exception:
            pass
