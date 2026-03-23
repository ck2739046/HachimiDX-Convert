from PyQt6.QtWidgets import QVBoxLayout, QMessageBox
import i18n

from .base_output_page import BaseOutputPage, _create_row
from ..widgets import *
from src.core.schemas.settings_config import SettingsConfig_Definitions as S_Defs
from src.core.schemas.op_result import print_op_result
from src.core.tools import show_notify_dialog
from src.services import SettingsManage

I18N_Prefix = "app.settings_page"


class SettingsPage(BaseOutputPage):

    def setup_content(self):

        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(10, 10, 10, 10)

        self.model_backend_combo_box = None

        self.ffmpeg_vp9_combo_box = None
        self.ffmpeg_h264_combo_box = None

        self.language_combo_box = None
        self.main_output_dir_name_line_edit = None

        self.init_width_line_edit = None
        self.init_height_line_edit = None
        self.min_width_line_edit = None
        self.min_height_line_edit = None

        self.save_button = None
        self.reset_button = None

        self._save_order_keys = [
            S_Defs.model_backend.key,
            S_Defs.ffmpeg_hw_accel_vp9.key,
            S_Defs.ffmpeg_hw_accel_h264.key,
            S_Defs.language.key,
            S_Defs.main_output_dir_name.key,
            S_Defs.main_app_init_size.key,
            S_Defs.main_app_min_size.key,
        ]

        self._build_model_section()
        self._build_ffmpeg_section()
        self._build_common_section()
        self._build_window_section()
        self._build_actions()

        self.content_layout.addStretch()
        self._load_settings_to_ui()




    def _build_model_section(self) -> None:
        self.content_layout.addWidget(create_divider(i18n.t(f"{I18N_Prefix}.ui_model_divider")))

        backend_label = create_label(i18n.t(f"{I18N_Prefix}.ui_model_backend_label"))
        self.model_backend_combo_box = self._create_combo_from_definition(S_Defs.model_backend, length=100)

        row = _create_row(backend_label, self.model_backend_combo_box, add_stretch=True)
        self.content_layout.addWidget(row)




    def _build_ffmpeg_section(self) -> None:
        self.content_layout.addWidget(create_divider(i18n.t(f"{I18N_Prefix}.ui_ffmpeg_divider")))

        vp9_label = create_label(i18n.t(f"{I18N_Prefix}.ui_ffmpeg_vp9_label"))
        self.ffmpeg_vp9_combo_box = self._create_combo_from_definition(S_Defs.ffmpeg_hw_accel_vp9, length=80)

        h264_label = create_label(i18n.t(f"{I18N_Prefix}.ui_ffmpeg_h264_label"))
        self.ffmpeg_h264_combo_box = self._create_combo_from_definition(S_Defs.ffmpeg_hw_accel_h264, length=80)

        row = _create_row(
            vp9_label,
            self.ffmpeg_vp9_combo_box,
            h264_label,
            self.ffmpeg_h264_combo_box,
            add_stretch=True,
        )
        self.content_layout.addWidget(row)




    def _build_common_section(self) -> None:
        self.content_layout.addWidget(create_divider(i18n.t(f"{I18N_Prefix}.ui_general_divider")))

        language_label = create_label(i18n.t(f"{I18N_Prefix}.ui_language_label"))
        self.language_combo_box = self._create_combo_from_definition(S_Defs.language, length=80)

        output_dir_label = create_label(i18n.t(f"{I18N_Prefix}.ui_output_dir_label"))
        self.main_output_dir_name_line_edit = create_line_edit(length=240)

        row = _create_row(
            language_label,
            self.language_combo_box,
            output_dir_label,
            self.main_output_dir_name_line_edit,
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




    def _set_combo_value(self, combo_box, value: str) -> None:
        idx = combo_box.findText(str(value))
        if idx >= 0:
            combo_box.setCurrentIndex(idx)




    def _load_settings_to_ui(self) -> None:
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

        self._set_combo_value(self.model_backend_combo_box, settings[S_Defs.model_backend.key])
        self._set_combo_value(self.ffmpeg_vp9_combo_box, settings[S_Defs.ffmpeg_hw_accel_vp9.key])
        self._set_combo_value(self.ffmpeg_h264_combo_box, settings[S_Defs.ffmpeg_hw_accel_h264.key])
        self._set_combo_value(self.language_combo_box, settings[S_Defs.language.key])
        self.main_output_dir_name_line_edit.setText(str(settings[S_Defs.main_output_dir_name.key]))

        init_size = settings[S_Defs.main_app_init_size.key]
        min_size = settings[S_Defs.main_app_min_size.key]

        self.init_width_line_edit.setText(str(init_size[0]))
        self.init_height_line_edit.setText(str(init_size[1]))
        self.min_width_line_edit.setText(str(min_size[0]))
        self.min_height_line_edit.setText(str(min_size[1]))




    def _collect_form_data(self) -> dict:

        return {
            S_Defs.model_backend.key: self.model_backend_combo_box.currentText().strip(),
            S_Defs.ffmpeg_hw_accel_vp9.key: self.ffmpeg_vp9_combo_box.currentText().strip(),
            S_Defs.ffmpeg_hw_accel_h264.key: self.ffmpeg_h264_combo_box.currentText().strip(),
            S_Defs.language.key: self.language_combo_box.currentText().strip(),
            S_Defs.main_output_dir_name.key: self.main_output_dir_name_line_edit.text().strip(),
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
