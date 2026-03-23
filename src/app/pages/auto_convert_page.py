import os
import traceback
from pathlib import Path
from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QWidget

from .base_output_page import BaseOutputPage, _create_row
from ..ui_style import UI_Style
from ..widgets import *
from src.services import process_manager_api
from src.services.pipeline import AutoConvertPipeline
from src.core.tools import show_notify_dialog
from src.core.schemas.op_result import OpResult, ok, err, print_op_result
from src.core.schemas.auto_convert_config import AutoConvertConfig_Definitions as AC_Defs
import i18n

I18N_Prefix = "app.auto_convert_page"


class AutoConvertPage(BaseOutputPage):

    def setup_content(self):

        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(10, 10, 10, 10)

        # panels
        self.standardize_panel = None
        self.std_overlay = None
        self.detect_panel = None
        self.det_overlay = None
        self.analyze_panel = None
        self.ana_overlay = None

        # Standardize
        self.song_name_line_edit = None
        self.video_mode_combo_box = None
        self.start_sec_line_edit = None
        self.end_sec_line_edit = None
        self.skip_detect_circle_check_box = None
        # target_res 暂时不设置

        # Detect
        self.skip_detect_check_box = None
        self.skip_cls_check_box = None
        self.skip_export_tracked_check_box = None

        # Analyze
        self.bpm_line_edit = None
        self.chart_lv_combo_box = None
        self.base_denominator_combo_box = None
        self.duration_denominator_combo_box = None

        # Common
        self.media_file_input = None
        self.enable_standardize_check_box = None
        self.enable_detect_check_box = None
        self.enable_analyze_check_box = None
        self.taskname_line_edit = None
        self.submit_button = None



        # ------------------- UI builders -------------------

        # Shared Input File Select & Probe Result View
        file_select_divider = create_divider(i18n.t(f"{I18N_Prefix}.ui_select_file_divider"))
        self.content_layout.addWidget(file_select_divider)
        self.media_file_input = MediaInputProbeWidget("placeholder")
        self.content_layout.addWidget(self.media_file_input)

        self._build_standardize_panel()
        self._build_detect_panel()
        self._build_analyze_panel()
        self._build_common_controls()



        # ------------------- 业务事件绑定 -------------------
        self.media_file_input.media_loaded.connect(self.on_std_input_selected)

        self.enable_standardize_check_box.stateChanged.connect(self._update_panels_visibility)
        self.enable_detect_check_box.stateChanged.connect(self._update_panels_visibility)
        self.enable_analyze_check_box.stateChanged.connect(self._update_panels_visibility)
        
        self.submit_button.clicked.connect(self.on_submit_clicked)

        process_manager_api.get_signals().runner_output.connect(self.output_widget.handle_process_output)
        process_manager_api.get_signals().runner_ended.connect(self.output_widget.handle_process_ended)

        # 初始化显示状态
        self._update_panels_visibility()

        self.content_layout.addStretch()







    
    def _create_combobox_with_options(self, param, length = None, transfer_fn = None):
        options = param.constraints["options"]
        default_val = param.default
        default_index = options.index(default_val)
        if transfer_fn:
            options = transfer_fn(options)
        return create_combo_box(length=length, items=options, default_index=default_index)


    def _transfer_base_denominator(self, input):

        if "(12)" in str(input):
            return input.replace(" (12)", "").strip()
        
        if isinstance(input, list):
            output = []
            for item in input:
                if int(item) >= 12:
                    output.append(f"{item} (12)")
                else:
                    output.append(item)
            return output

        return input



    def _build_standardize_panel(self):

        self.standardize_panel = QWidget()
        layout = QVBoxLayout(self.standardize_panel)
        layout.setContentsMargins(0, 0, 0, 0)
        
        divider = create_divider(i18n.t(f"{I18N_Prefix}.ui_standardize_divider"))
        layout.addWidget(divider)
        
        # Row 1
        song_name_label = create_label(i18n.t(f"{I18N_Prefix}.ui_song_name_label"))
        self.song_name_line_edit = create_line_edit()

        row = _create_row(song_name_label, self.song_name_line_edit)
        layout.addWidget(row)

        # Row 2
        video_mode_label = create_label(i18n.t(f"{I18N_Prefix}.ui_video_mode_label"))
        self.video_mode_combo_box = self._create_combobox_with_options(AC_Defs.video_mode, length=125)
        video_mode_help = create_help_icon(i18n.t(f"{I18N_Prefix}.ui_video_mode_help"))

        start_end_label = create_label(i18n.t("app.media_subpages.run_ffmpeg.ui_start_end_label"))
        start_end_label_between = create_label("→")  # between start and end
        self.start_sec_line_edit = create_line_edit(length=60, validator='float')
        self.end_sec_line_edit = create_line_edit(length=60, validator='float')
        start_end_help = create_help_icon(i18n.t("app.media_subpages.run_ffmpeg.ui_start_end_help"))

        skip_detect_rect_label = create_label(i18n.t(f"{I18N_Prefix}.ui_skip_detect_circle_label"))
        self.skip_detect_circle_check_box = create_check_box(AC_Defs.skip_detect_circle.default)
        skip_detect_rect_help = create_help_icon(i18n.t(f"{I18N_Prefix}.ui_skip_detect_circle_help"))

        row = _create_row(video_mode_label,
                          self.video_mode_combo_box,
                          video_mode_help,

                          start_end_label,
                          self.start_sec_line_edit,
                          start_end_label_between,
                          self.end_sec_line_edit,
                          start_end_help,

                          skip_detect_rect_label,
                          self.skip_detect_circle_check_box,
                          skip_detect_rect_help,

                          add_stretch=True)
        layout.addWidget(row)

        self.content_layout.addWidget(self.standardize_panel)
        self.std_overlay = OverlayWidget(self.standardize_panel)






    def _build_detect_panel(self):

        self.detect_panel = QWidget()
        layout = QVBoxLayout(self.detect_panel)
        layout.setContentsMargins(0, 0, 0, 0)

        divider = create_divider(i18n.t(f"{I18N_Prefix}.ui_detect_divider"))
        layout.addWidget(divider)

        # Settings
        skip_det_label = create_label(i18n.t(f"{I18N_Prefix}.ui_skip_detect_label"))
        self.skip_detect_check_box = create_check_box(AC_Defs.skip_detect.default)
        skip_det_help = create_help_icon(i18n.t(f"{I18N_Prefix}.ui_skip_detect_help"))

        skip_cls_label = create_label(i18n.t(f"{I18N_Prefix}.ui_skip_cls_label"))
        self.skip_cls_check_box = create_check_box(AC_Defs.skip_cls.default)
        skip_cls_help = create_help_icon(i18n.t(f"{I18N_Prefix}.ui_skip_cls_help"))

        skip_export_label = create_label(i18n.t(f"{I18N_Prefix}.ui_skip_export_tracked_label"))
        self.skip_export_tracked_check_box = create_check_box(AC_Defs.skip_export_tracked_video.default)
        skip_export_help = create_help_icon(i18n.t(f"{I18N_Prefix}.ui_skip_export_tracked_help"))

        row = _create_row(skip_det_label, self.skip_detect_check_box, skip_det_help,
                          skip_cls_label, self.skip_cls_check_box, skip_cls_help,
                          skip_export_label, self.skip_export_tracked_check_box, skip_export_help,
                          add_stretch=True)
        layout.addWidget(row)

        self.content_layout.addWidget(self.detect_panel)
        self.det_overlay = OverlayWidget(self.detect_panel)






    def _build_analyze_panel(self):

        self.analyze_panel = QWidget()
        layout = QVBoxLayout(self.analyze_panel)
        layout.setContentsMargins(0, 0, 0, 0)

        divider = create_divider(i18n.t(f"{I18N_Prefix}.ui_analyze_divider"))
        layout.addWidget(divider)

        # Settings
        bpm_label = create_label(i18n.t(f"{I18N_Prefix}.ui_bpm_label"))
        self.bpm_line_edit = create_line_edit(length=70, validator='float')
        bpm_help = create_help_icon(i18n.t(f"{I18N_Prefix}.ui_bpm_help"))

        chart_lv_label = create_label(i18n.t(f"{I18N_Prefix}.ui_chart_lv_label"))
        self.chart_lv_combo_box = self._create_combobox_with_options(AC_Defs.chart_lv, length=45)
        chart_lv_help = create_help_icon(i18n.t(f"{I18N_Prefix}.ui_chart_lv_help"))

        bd_label = create_label(i18n.t(f"{I18N_Prefix}.ui_base_denominator_label"))
        self.base_denominator_combo_box = self._create_combobox_with_options(AC_Defs.base_denominator, length=75, transfer_fn=self._transfer_base_denominator)
        bd_help = create_help_icon(i18n.t(f"{I18N_Prefix}.ui_base_denominator_help"))

        dd_label = create_label(i18n.t(f"{I18N_Prefix}.ui_duration_denominator_label"))
        self.duration_denominator_combo_box = self._create_combobox_with_options(AC_Defs.duration_denominator, length=45)
        dd_help = create_help_icon(i18n.t(f"{I18N_Prefix}.ui_duration_denominator_help"))

        row = _create_row(bpm_label, self.bpm_line_edit, bpm_help,
                          chart_lv_label, self.chart_lv_combo_box, chart_lv_help,
                          bd_label, self.base_denominator_combo_box, bd_help,
                          dd_label, self.duration_denominator_combo_box, dd_help,
                          add_stretch=True)
        layout.addWidget(row)

        self.content_layout.addWidget(self.analyze_panel)
        self.ana_overlay = OverlayWidget(self.analyze_panel)





    def _build_common_controls(self):

        divider = create_divider(i18n.t(f"{I18N_Prefix}.ui_common_divider"))
        self.content_layout.addWidget(divider)

        # Row 1: Enable Modules
        en_std_label = create_label(i18n.t(f"{I18N_Prefix}.ui_enable_standardize_label"))
        self.enable_standardize_check_box = create_check_box(default_checked=AC_Defs.is_standardize_enabled.default)
        en_std_help = create_help_icon(i18n.t(f"{I18N_Prefix}.ui_enable_standardize_help"))
        
        en_det_label = create_label(i18n.t(f"{I18N_Prefix}.ui_enable_detect_label"))
        self.enable_detect_check_box = create_check_box(default_checked=AC_Defs.is_detect_enabled.default)
        en_det_help = create_help_icon(i18n.t(f"{I18N_Prefix}.ui_enable_detect_help"))

        en_ana_label = create_label(i18n.t(f"{I18N_Prefix}.ui_enable_analyze_label"))
        self.enable_analyze_check_box = create_check_box(default_checked=AC_Defs.is_analyze_enabled.default)
        en_ana_help = create_help_icon(i18n.t(f"{I18N_Prefix}.ui_enable_analyze_help"))

        self.create_row(
            en_std_label, self.enable_standardize_check_box, en_std_help,
            en_det_label, self.enable_detect_check_box, en_det_help,
            en_ana_label, self.enable_analyze_check_box, en_ana_help,
            add_stretch=True
        )

        # Row 2: Submit Button + Task Name Input
        self.taskname_line_edit = create_line_edit(
            length=200, placeholder=i18n.t("app.media_subpages.run_ffmpeg.ui_taskname_placeholder"))
        self.submit_button = create_stated_button(i18n.t("app.media_subpages.run_ffmpeg.ui_submit_button"), isbig=True)
        self.create_row(self.submit_button, self.taskname_line_edit, add_stretch=True)





    def _update_panels_visibility(self):
        """根据启用的模块复选框更新 UI 区块的可见性。"""
        std_enabled = self.enable_standardize_check_box.isChecked()
        det_enabled = self.enable_detect_check_box.isChecked()
        ana_enabled = self.enable_analyze_check_box.isChecked()

        self.std_overlay.setVisible(not std_enabled)
        self.det_overlay.setVisible(not det_enabled)
        self.ana_overlay.setVisible(not ana_enabled)




    def on_std_input_selected(self, error_msg: str) -> None:
        """Standardize 视频选择回调"""
        # Show error in popup window
        if len(error_msg) > 0:
            show_notify_dialog("app.auto_convert", error_msg)
            return
        # 更新 Song Name
        self.song_name_line_edit.setText(Path(self.media_file_input.get_path()).stem)




    def on_submit_clicked(self) -> None:
        """收集数据提交转档任务"""

        def try_int(value) -> int | None:
            if value is None: return None
            try: return int(round(float(value)))
            except: return None
            
        def try_float(value) -> float | None:
            if value is None: return None
            try: return float(value)
            except: return None

        try:
            self.submit_button.setEnabled(False)

            raw_data = {
                # common
                AC_Defs.is_standardize_enabled.key: self.enable_standardize_check_box.isChecked(),
                AC_Defs.is_detect_enabled.key:      self.enable_detect_check_box.isChecked(),
                AC_Defs.is_analyze_enabled.key:     self.enable_analyze_check_box.isChecked(),
            }

            if raw_data[AC_Defs.is_standardize_enabled.key]:
                raw_data.update({
                    AC_Defs.standardize_input_video_path.key: self.media_file_input.get_path() or None,
                    AC_Defs.song_name.key: self.song_name_line_edit.text().strip() or None,
                    AC_Defs.video_mode.key: self.video_mode_combo_box.currentText().strip(),
                    AC_Defs.start_sec.key: try_float(self.start_sec_line_edit.text().strip()),
                    AC_Defs.end_sec.key: try_float(self.end_sec_line_edit.text().strip()),
                    AC_Defs.target_res.key: 1080, # 暂时不修改
                    AC_Defs.skip_detect_circle.key: self.skip_detect_circle_check_box.isChecked(),
                    AC_Defs.duration.key: try_float(self.media_file_input.selected_file_duration),
                    AC_Defs.media_type.key: self.media_file_input.selected_file_type
                })

            if raw_data[AC_Defs.is_detect_enabled.key]:
                if not raw_data[AC_Defs.is_standardize_enabled.key]:
                    raw_data[AC_Defs.std_video_path_detect.key] = self.media_file_input.get_path() or None
                raw_data.update({
                    AC_Defs.skip_detect.key: self.skip_detect_check_box.isChecked(),
                    AC_Defs.skip_cls.key: self.skip_cls_check_box.isChecked(),
                    AC_Defs.skip_export_tracked_video.key: self.skip_export_tracked_check_box.isChecked(),
                })
                
            if raw_data[AC_Defs.is_analyze_enabled.key]:
                if not raw_data[AC_Defs.is_standardize_enabled.key]:
                    raw_data[AC_Defs.std_video_path_analyze.key] = self.media_file_input.get_path() or None
                raw_data.update({
                    AC_Defs.bpm.key: try_float(self.bpm_line_edit.text().strip()),
                    AC_Defs.chart_lv.key: try_int(self.chart_lv_combo_box.currentText()),
                    AC_Defs.base_denominator.key: try_int(self._transfer_base_denominator(self.base_denominator_combo_box.currentText())),
                    AC_Defs.duration_denominator.key: try_int(self.duration_denominator_combo_box.currentText()),
                })

            task_name = self.taskname_line_edit.text().strip()
            result = AutoConvertPipeline.submit_task(raw_data, task_name)
            if not result.is_ok:
                reason = print_op_result(result) # 保底
                # 尝试直接访问普通 pydantic 错误
                try:
                    root_result = result.inner.inner
                    if "validate_pydantic()" in root_result.source.lower() and \
                       "pydantic validation failed" in root_result.error_msg.lower():
                        reason = root_result.error_raw
                except Exception:
                    pass
                error_msg = i18n.t("app.media_subpages.run_ffmpeg.warning_task_submit_failed", error = reason)
                show_notify_dialog("app.media_subpages.run_ffmpeg", error_msg)
                return

            runner_id, cmd_list = result.value
            self.output_widget.bind_current_runner_id(runner_id)
            
            # 显示悬浮通知
            message = i18n.t("app.media_subpages.run_ffmpeg.notice_task_submit_success", task_id=runner_id)
            create_floating_notification(message, self.window())

        except Exception as e:
            show_notify_dialog("app.auto_convert_page",
                i18n.t("app.media_subpages.run_ffmpeg.warning_unexpected_submit_error", error=traceback.format_exc()))
        finally:
            self.submit_button.setEnabled(True)

