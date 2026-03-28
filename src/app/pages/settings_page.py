from PyQt6.QtWidgets import QVBoxLayout, QMessageBox
import i18n

from .base_output_page import BaseOutputPage, _create_row
from ..widgets import *
from src.core.schemas.settings_config import SettingsConfig_Definitions as S_Defs
from src.core.schemas.op_result import print_op_result, ok, err
from src.core.tools import show_notify_dialog
from src.core.build_worker_cmd import build_cmd_head_python_exe
from src.services import SettingsManage, process_manager_api
from src.services.path_manage import PathManage

I18N_Prefix = "app.settings_page"
 

class SettingsPage(BaseOutputPage):

    def setup_content(self):

        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(10, 10, 10, 10)

        self.model_backend_combo_box = None
        self.check_model_button = None
        self.convert_model_button = None
        self.cancel_convert_model_button = None

        self._active_check_runner_id = None
        self._active_convert_runner_id = None
        self._backend_snapshot = None

        # self.ffmpeg_vp9_combo_box = None
        # self.ffmpeg_h264_combo_box = None

        self.language_combo_box = None
        self.main_output_dir_line_edit = None
        self.main_output_dir_button = None

        self.init_width_line_edit = None
        self.init_height_line_edit = None
        self.min_width_line_edit = None
        self.min_height_line_edit = None

        self.save_button = None
        self.reset_button = None

        self._save_order_keys = [
            S_Defs.model_backend.key,
            # S_Defs.ffmpeg_hw_accel_vp9.key,
            #S_Defs.ffmpeg_hw_accel_h264.key,
            S_Defs.language.key,
            S_Defs.main_output_dir.key,
            S_Defs.main_app_init_size.key,
            S_Defs.main_app_min_size.key,
        ]

        self._build_model_section()
        # self._build_ffmpeg_section()
        self._build_common_section()
        self._build_window_section()
        self._build_actions()

        process_manager_api.get_signals().runner_output.connect(self.output_widget.handle_process_output)
        process_manager_api.get_signals().runner_ended.connect(self.output_widget.handle_process_ended)
        process_manager_api.get_signals().runner_ended.connect(self._on_runner_ended)

        self.content_layout.addStretch()
        self._load_settings_to_ui()




    def _build_model_section(self) -> None:
        self.content_layout.addWidget(create_divider(i18n.t(f"{I18N_Prefix}.ui_model_divider")))

        backend_label = create_label(i18n.t(f"{I18N_Prefix}.ui_model_backend_label"))
        self.model_backend_combo_box = self._create_combo_from_definition(S_Defs.model_backend, length=100)
        backend_help = create_help_icon(i18n.t(f"{I18N_Prefix}.ui_model_backend_help"))
        self.check_model_button = create_stated_button(i18n.t(f"{I18N_Prefix}.ui_check_model_button"))
        self.convert_model_button = create_stated_button(i18n.t(f"{I18N_Prefix}.ui_convert_model_button"), width=120)
        self.cancel_convert_model_button = create_stated_button(i18n.t(f"{I18N_Prefix}.ui_cancel_convert_model_button"))
        self.convert_model_button.setVisible(False)        # 默认隐藏
        self.cancel_convert_model_button.setVisible(False) # 默认隐藏

        row = _create_row(
            backend_label,
            self.model_backend_combo_box,
            backend_help,
            self.check_model_button,
            self.convert_model_button,
            self.cancel_convert_model_button,
            add_stretch=True,
        )
        self.content_layout.addWidget(row)

        self.check_model_button.clicked.connect(self.on_check_model_clicked)
        self.convert_model_button.clicked.connect(self.on_convert_model_clicked)
        self.cancel_convert_model_button.clicked.connect(self.on_cancel_convert_model_button_clicked)
        self.model_backend_combo_box.currentTextChanged.connect(
            lambda _text: self._refresh_model_buttons(reason="backend_changed"))




    # def _build_ffmpeg_section(self) -> None:
    #     self.content_layout.addWidget(create_divider(i18n.t(f"{I18N_Prefix}.ui_ffmpeg_divider")))

    #     vp9_label = create_label(i18n.t(f"{I18N_Prefix}.ui_ffmpeg_vp9_label"))
    #     self.ffmpeg_vp9_combo_box = self._create_combo_from_definition(S_Defs.ffmpeg_hw_accel_vp9, length=80)

    #     h264_label = create_label(i18n.t(f"{I18N_Prefix}.ui_ffmpeg_h264_label"))
    #     self.ffmpeg_h264_combo_box = self._create_combo_from_definition(S_Defs.ffmpeg_hw_accel_h264, length=80)

    #     row = _create_row(
    #         vp9_label,
    #         self.ffmpeg_vp9_combo_box,
    #         h264_label,
    #         self.ffmpeg_h264_combo_box,
    #         add_stretch=True,
    #     )
    #     self.content_layout.addWidget(row)




    def _build_common_section(self) -> None:
        self.content_layout.addWidget(create_divider(i18n.t(f"{I18N_Prefix}.ui_general_divider")))

        language_label = create_label(i18n.t(f"{I18N_Prefix}.ui_language_label"))
        self.language_combo_box = self._create_combo_from_definition(S_Defs.language, length=80)

        output_dir_label = create_label(i18n.t(f"{I18N_Prefix}.ui_output_dir_label"))
        self.main_output_dir_button, self.main_output_dir_line_edit, _ = create_directory_selection_row(
            button_text=i18n.t(f"{I18N_Prefix}.ui_output_dir_browse_button"), button_length=80)
        self.main_output_dir_line_edit.setFixedWidth(320)

        row = _create_row(
            language_label,
            self.language_combo_box,
            output_dir_label,
            self.main_output_dir_button,
            self.main_output_dir_line_edit,
            add_stretch=True,
        )
        self.content_layout.addWidget(row)




    def _build_window_section(self) -> None:
        self.content_layout.addWidget(create_divider(i18n.t(f"{I18N_Prefix}.ui_window_divider")))

        init_label = create_label(i18n.t(f"{I18N_Prefix}.ui_init_size_label"))
        self.init_width_line_edit = create_line_edit(length=60, validator="int")
        self.init_height_line_edit = create_line_edit(length=60, validator="int")

        min_label = create_label(i18n.t(f"{I18N_Prefix}.ui_min_size_label"))
        self.min_width_line_edit = create_line_edit(length=60, validator="int")
        self.min_height_line_edit = create_line_edit(length=60, validator="int")

        row = _create_row(
            init_label,
            self.init_width_line_edit,
            create_label("x"),
            self.init_height_line_edit,
            min_label,
            self.min_width_line_edit,
            create_label("x"),
            self.min_height_line_edit,
            add_stretch=True,
        )
        self.content_layout.addWidget(row)




    def _build_actions(self) -> None:
        self.content_layout.addWidget(create_divider(i18n.t(f"{I18N_Prefix}.ui_actions_divider")))

        self.save_button = create_stated_button(i18n.t(f"{I18N_Prefix}.ui_save_button"), isbig=True)
        self.reset_button = create_stated_button(i18n.t(f"{I18N_Prefix}.ui_reset_button"), isbig=True)

        row = _create_row(self.save_button, self.reset_button, add_stretch=True)
        self.content_layout.addWidget(row)

        self.save_button.clicked.connect(self.on_save_clicked)
        self.reset_button.clicked.connect(self.on_reset_clicked)




    def _create_combo_from_definition(self, definition, length: int):
        options = [str(item) for item in definition.constraints["options"]]
        default_value = str(definition.default)
        default_index = options.index(default_value)
        return create_combo_box(length=length, items=options, default_index=default_index)




    def _load_settings_to_ui(self) -> None:

        def _set_combo_value(combo_box, value: str) -> None:
            idx = combo_box.findText(str(value))
            if idx >= 0:
                combo_box.setCurrentIndex(idx)

        settings = {}

        for key in self._save_order_keys:
            result = SettingsManage.get(key)
            if not result.is_ok:
                show_notify_dialog(
                    i18n.t(f"{I18N_Prefix}.dialog_title"),
                    i18n.t(f"{I18N_Prefix}.warning_load_failed", item_key=key, error=result.error_msg),
                )
                return
            settings[key] = result.value

        _set_combo_value(self.model_backend_combo_box, settings[S_Defs.model_backend.key])
        self._refresh_model_buttons(reason="backend_changed")
        # _set_combo_value(self.ffmpeg_vp9_combo_box, settings[S_Defs.ffmpeg_hw_accel_vp9.key])
        # _set_combo_value(self.ffmpeg_h264_combo_box, settings[S_Defs.ffmpeg_hw_accel_h264.key])
        _set_combo_value(self.language_combo_box, settings[S_Defs.language.key])
        self.main_output_dir_line_edit.setText(str(settings[S_Defs.main_output_dir.key]))

        init_size = settings[S_Defs.main_app_init_size.key]
        min_size = settings[S_Defs.main_app_min_size.key]

        self.init_width_line_edit.setText(str(init_size[0]))
        self.init_height_line_edit.setText(str(init_size[1]))
        self.min_width_line_edit.setText(str(min_size[0]))
        self.min_height_line_edit.setText(str(min_size[1]))




    def _collect_form_data(self) -> dict:

        return {
            S_Defs.model_backend.key: self.model_backend_combo_box.currentText().strip(),
            # S_Defs.ffmpeg_hw_accel_vp9.key: self.ffmpeg_vp9_combo_box.currentText().strip(),
            # S_Defs.ffmpeg_hw_accel_h264.key: self.ffmpeg_h264_combo_box.currentText().strip(),
            S_Defs.language.key: self.language_combo_box.currentText().strip(),
            S_Defs.main_output_dir.key: self.main_output_dir_line_edit.text().strip(),
            S_Defs.main_app_init_size.key: (
                self.init_width_line_edit.text().strip(),
                self.init_height_line_edit.text().strip(),
            ),
            S_Defs.main_app_min_size.key: (
                self.min_width_line_edit.text().strip(),
                self.min_height_line_edit.text().strip(),
            ),
        }




    def on_save_clicked(self) -> None:
        data = self._collect_form_data()

        self.save_button.setEnabled(False)
        self.reset_button.setEnabled(False)

        try:
            for key in self._save_order_keys:
                result = SettingsManage.set(key, data[key])
                if not result.is_ok:
                    reason = print_op_result(result, only_parse_last=True)
                    show_notify_dialog(
                        i18n.t(f"{I18N_Prefix}.dialog_title"),
                        i18n.t(f"{I18N_Prefix}.warning_save_item_failed", item_key=key, error=reason),
                    )
                    return

            self.output_widget.append_text(i18n.t(f"{I18N_Prefix}.notice_save_success"))
            self._load_settings_to_ui()
        finally:
            self.save_button.setEnabled(True)
            self.reset_button.setEnabled(True)




    def on_reset_clicked(self) -> None:
        reply = QMessageBox.question(
            self,
            i18n.t(f"{I18N_Prefix}.ui_reset_confirm_title"),
            i18n.t(f"{I18N_Prefix}.ui_reset_confirm_text"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.save_button.setEnabled(False)
        self.reset_button.setEnabled(False)

        try:
            result = SettingsManage.reset()
            if not result.is_ok:
                reason = print_op_result(result, only_parse_last=True)
                show_notify_dialog(
                    i18n.t(f"{I18N_Prefix}.dialog_title"),
                    i18n.t(f"{I18N_Prefix}.warning_reset_failed", error=reason),
                )
                return

            self.output_widget.append_text(i18n.t(f"{I18N_Prefix}.notice_reset_success"))
            self._load_settings_to_ui()
        finally:
            self.save_button.setEnabled(True)
            self.reset_button.setEnabled(True)




        




    def _refresh_model_buttons(self, reason):
        if reason == "backend_changed":
            if not self._has_active_runner():
                self.convert_model_button.setVisible(False)
        
        if reason == "runner_state_changed":
            is_busy = self._has_active_runner()
            self.model_backend_combo_box.setEnabled(not is_busy)
            self.check_model_button.setEnabled(not is_busy)
            self.convert_model_button.setEnabled(not is_busy)
            self.save_button.setEnabled(not is_busy)
            self.reset_button.setEnabled(not is_busy)
            self.cancel_convert_model_button.setVisible(is_busy)
            self.cancel_convert_model_button.setEnabled(is_busy)


    def _has_active_runner(self) -> bool:
        return bool(self._active_check_runner_id or self._active_convert_runner_id)


    def _start_worker_cmd(self, cmd: list[str], worker_type: str, backend: str):

        if self._has_active_runner(): return
        if worker_type not in {"check", "convert"}: return

        result = process_manager_api.start(cmd)
        if not result.is_ok:
            show_notify_dialog(
                i18n.t(f"{I18N_Prefix}.dialog_title"),
                i18n.t(f"{I18N_Prefix}.warning_worker_start_failed", error=result.error_msg),
            )
            return None

        runner_id = result.value
        self.output_widget.bind_current_runner_id(runner_id)

        if worker_type == "check":
            self._active_check_runner_id = runner_id
        elif worker_type == "convert":
            self._active_convert_runner_id = runner_id

        self._backend_snapshot = backend # 备份

        self._refresh_model_buttons(reason="runner_state_changed")
        return




    def on_check_model_clicked(self) -> None:
        if self._has_active_runner():
            return
        self.convert_model_button.setVisible(False)
        backend = self.model_backend_combo_box.currentText().strip()
        self.output_widget.append_text(i18n.t(f"{I18N_Prefix}.notice_check_start", backend=backend))
        cmd = build_cmd_head_python_exe(PathManage.CHECK_DEVICE_WORKER_PATH)
        cmd.append(backend.lower())
        self._start_worker_cmd(cmd, "check", backend)




    def on_convert_model_clicked(self) -> None:
        if self._has_active_runner():
            return
        backend = self.model_backend_combo_box.currentText().strip()

        # 特例：cpu 不应该触发转换按钮
        if backend == "CPU": return

        detect_batch_result = SettingsManage.get(S_Defs.predict_batch_size_detect_obb.key)
        if not detect_batch_result.is_ok:
            show_notify_dialog(
                i18n.t(f"{I18N_Prefix}.dialog_title"),
                i18n.t(
                    f"{I18N_Prefix}.warning_load_failed",
                    item_key=S_Defs.predict_batch_size_detect_obb.key,
                    error=detect_batch_result.error_msg,
                ),
            )
            return

        cls_batch_result = SettingsManage.get(S_Defs.predict_batch_size_classify.key)
        if not cls_batch_result.is_ok:
            show_notify_dialog(
                i18n.t(f"{I18N_Prefix}.dialog_title"),
                i18n.t(
                    f"{I18N_Prefix}.warning_load_failed",
                    item_key=S_Defs.predict_batch_size_classify.key,
                    error=cls_batch_result.error_msg,
                ),
            )
            return

        detect_batch = detect_batch_result.value
        cls_batch = cls_batch_result.value

        self.output_widget.append_text(
            i18n.t(
                f"{I18N_Prefix}.notice_convert_start",
                backend=backend
            )
        )

        cmd = build_cmd_head_python_exe(PathManage.MODEL_CONVERT_WORKER_PATH)
        cmd.extend([str(backend), str(detect_batch), str(cls_batch)])
        self._start_worker_cmd(cmd, "convert", backend)




    def on_cancel_convert_model_button_clicked(self) -> None:
        runner_id = self._active_convert_runner_id or self._active_check_runner_id
        if not runner_id:
            return

        result = process_manager_api.cancel(runner_id)
        if not result.is_ok:
            show_notify_dialog(
                i18n.t(f"{I18N_Prefix}.dialog_title"),
                i18n.t(f"{I18N_Prefix}.warning_cancel_failed", error=result.error_msg),
            )
            return

        self.output_widget.append_text(i18n.t(f"{I18N_Prefix}.notice_cancel_requested"))




    def _on_runner_ended(self, runner_id: str, ended) -> None:

        backend = self._backend_snapshot

        if runner_id == self._active_check_runner_id:
            self._active_check_runner_id = None
            self._handle_check_runner_ended(backend, ended)
        if runner_id == self._active_convert_runner_id:
            self._active_convert_runner_id = None
            self._handle_convert_runner_ended(backend, ended)

        self._refresh_model_buttons(reason="runner_state_changed")




    def _handle_check_runner_ended(self, backend: str, ended) -> None:

        self.convert_model_button.setVisible(False)

        # 用户主动取消
        if getattr(ended, "cancelled", False):
            self.output_widget.append_text(i18n.t(f"{I18N_Prefix}.notice_check_cancelled", backend=backend))
            return

        # 进程异常结束
        failed = bool(getattr(ended, "crashed", False))
        exit_code = getattr(ended, "exit_code", None)
        if exit_code is None or exit_code != 0:
            failed = True

        if failed:
            self.output_widget.append_text(i18n.t(f"{I18N_Prefix}.warning_check_failed", backend=backend))
            return

        # 进程正常结束
        self.output_widget.append_text(i18n.t(f"{I18N_Prefix}.notice_check_pass", backend=backend))

        # 环境检查通过
        # 下一步，检查模型文件是否存在

        # 模型检查通过
        path_result = S_Defs.get_path_by_backend(backend)
        if path_result.is_ok:
            self.output_widget.append_text(i18n.t(f"{I18N_Prefix}.notice_model_ready", backend=backend))
            return

        # 模型检查失败
        self.output_widget.append_text(
            i18n.t(
                f"{I18N_Prefix}.warning_model_missing",
                backend=backend,
                error=path_result.error_msg,
            )
        )

        # 特例：cpu 不显示转换按钮，直接报错
        if backend == "CPU":
            show_notify_dialog(
                i18n.t(f"{I18N_Prefix}.dialog_title"),
                i18n.t(f"{I18N_Prefix}.warning_cpu_model_missing", error=path_result.error_msg),
            )
            return
        
        # 其他情况下，显示转换按钮，允许用户转换模型
        self.convert_model_button.setVisible(True)

        


    def _handle_convert_runner_ended(self, backend: str, ended) -> None:

        self.convert_model_button.setVisible(True)

        # 用户主动取消
        if getattr(ended, "cancelled", False):
            self.output_widget.append_text(i18n.t(f"{I18N_Prefix}.notice_convert_cancelled", backend=backend))
            return

        # 进程异常结束
        failed = bool(getattr(ended, "crashed", False))
        exit_code = getattr(ended, "exit_code", None)
        if exit_code is None or exit_code != 0:
            failed = True

        if failed:
            self.output_widget.append_text(i18n.t(f"{I18N_Prefix}.warning_convert_failed", backend=backend))
            return

        # 进程正常结束，二次复查模型文件是否存在
        path_result = S_Defs.get_path_by_backend(backend)
        if not path_result.is_ok:
            self.output_widget.append_text(
                i18n.t(
                    f"{I18N_Prefix}.warning_convert_incomplete",
                    backend=backend,
                    error=path_result.error_msg,
                )
            )
            return

        # 模型转换成功
        self.convert_model_button.setVisible(False)
        self.output_widget.append_text(i18n.t(f"{I18N_Prefix}.notice_convert_success", backend=backend))
