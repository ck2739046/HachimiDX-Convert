from PyQt6.QtWidgets import QVBoxLayout
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
I18N_Simply_Align_Prefix = "app.media_subpages.simply_align"



class SimplyAlignPage(BaseOutputPage):
    def setup_content(self):

        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(10, 10, 10, 10)

        self.reference_path_display = None
        self.target_media_input = None

        self.run_button = None
        self.offset_label = None

        self._active_runner_id = None

        self._build_file_section()
        self._build_action_section()

        process_manager_api.get_signals().runner_output.connect(self.output_widget.handle_process_output)
        process_manager_api.get_signals().runner_ended.connect(self.output_widget.handle_process_ended)
        process_manager_api.get_signals().runner_ended.connect(self._on_runner_ended)

        self.content_layout.addStretch()




    def _build_file_section(self) -> None:
        self.content_layout.addWidget(create_divider(i18n.t(f"{I18N_Prefix}.ui_select_file_divider")))

        reference_button, self.reference_path_display, reference_help = create_file_selection_row(
            button_text=i18n.t(f"{I18N_Prefix}.ui_reference_file_button"),
            help_text=i18n.t(f"{I18N_Simply_Align_Prefix}.ui_reference_file_help"),
        )
        self.create_row(reference_button, reference_help, self.reference_path_display)

        self.target_media_input = MediaInputProbeWidget(
            select_file_button_help=i18n.t(f"{I18N_Simply_Align_Prefix}.ui_target_file_help")
        )
        self.target_media_input.media_loaded.connect(self.on_target_input_selected)
        self.content_layout.addWidget(self.target_media_input)



    def _build_action_section(self) -> None:
        self.run_button = create_stated_button(i18n.t(f"{I18N_Prefix}.ui_run_button"), isbig=True)
        self.run_button.clicked.connect(self.on_run_clicked)

        self.offset_label = create_label(bold=True)
        self.offset_label.hide()

        self.content_layout.addSpacing(UI_Style.widget_spacing)
        self.create_row(self.run_button, self.offset_label, add_stretch=True)



    def on_target_input_selected(self, error_msg: str) -> None:
        if len(error_msg) > 0:
            show_notify_dialog(i18n.t(f"{I18N_Simply_Align_Prefix}.dialog_title"), error_msg)



    def _parse_inputs(self) -> OpResult[dict]:
        reference_file = self.reference_path_display.text().strip()
        target_file = self.target_media_input.get_path().strip()

        if not reference_file:
            return err(i18n.t(f"{I18N_Prefix}.warning_reference_file_required"))
        if not target_file:
            return err(i18n.t(f"{I18N_Prefix}.warning_target_file_required"))

        return ok({
            "reference_file": reference_file,
            "target_file": target_file,
        })



    def on_run_clicked(self) -> None:
        if self._active_runner_id:
            return

        self.run_button.setEnabled(False)
        self.offset_label.setText("")
        self.offset_label.hide()

        try:
            res = self._parse_inputs()
            if not res.is_ok:
                show_notify_dialog(i18n.t(f"{I18N_Simply_Align_Prefix}.dialog_title"), res.error_msg)
                return

            data = res.value
            cmd = build_cmd_head_python_exe(PathManage.AUDIO_ALIGN_WORKER_PATH)
            cmd.extend([
                "true",  # is_simply_align
                str(data["reference_file"]),
                str(data["target_file"]),
            ])

            self.output_widget.append_text(i18n.t(f"{I18N_Prefix}.notice_run_start"))

            result = process_manager_api.start(cmd)
            if not result.is_ok:
                show_notify_dialog(
                    i18n.t(f"{I18N_Simply_Align_Prefix}.dialog_title"),
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
        self._try_parse_offset()



    def _try_parse_offset(self) -> None:
        offset_ms = None
        recent_output = self.output_widget.get_recent_lines(6)

        for line in reversed(recent_output.splitlines()):
            line = line.strip()
            if not line:
                continue

            if line == "Audio files are perfectly aligned (offset < 10 ms)":
                offset_ms = 0
                break

            if line.startswith("Target file needs trim ") and line.endswith(" ms"):
                value_text = line[len("Target file needs trim "):-len(" ms")].strip()
                try:
                    offset_ms = "trim " + value_text
                    break
                except Exception:
                    continue

            if line.startswith("Target file needs delay ") and line.endswith(" ms"):
                value_text = line[len("Target file needs delay "):-len(" ms")].strip()
                try:
                    offset_ms = "delay " + value_text
                    break
                except Exception:
                    continue

        if offset_ms is None:
            self.output_widget.append_text("ui: failed to parse offset from output")
            self.offset_label.hide()
            return

        self.offset_label.setText(f"  Offset: {offset_ms} ms ")
        self.offset_label.show()
