import os
import traceback
from pathlib import Path
from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QWidget

from .base_output_page import BaseOutputPage
from ..ui_style import UI_Style
from ..widgets import *
from src.services import process_manager_api
from src.services.pipeline import AutoConvertPipeline
from src.core.tools import show_notify_dialog
from src.core.schemas.op_result import OpResult, ok, err, print_op_result
from src.core.schemas.auto_convert_config import AutoConvertConfig_Definitions as AC_Defs
import i18n


class AutoConvertPage(BaseOutputPage):

    def setup_content(self):

        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(10, 10, 10, 10)

        # 1 & 2. Shared Input File Select & Probe Result View
        self.std_media_input = MediaInputProbeWidget(
            i18n.t("placeholder"))
        self.std_media_input.media_loaded.connect(self.on_std_input_selected)
        self.content_layout.addWidget(self.std_media_input)

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
        self._build_standardize_panel()
        self._build_detect_panel()
        self._build_analyze_panel()
        self._build_bottom_controls()

        # ------------------- 业务事件绑定 -------------------
        self.enable_standardize_cb.stateChanged.connect(self._update_panels_visibility)
        self.enable_detect_cb.stateChanged.connect(self._update_panels_visibility)
        self.enable_analyze_cb.stateChanged.connect(self._update_panels_visibility)
        
        self.submit_button.clicked.connect(self.on_submit_clicked)

        process_manager_api.get_signals().runner_output.connect(self.output_widget.handle_process_output)
        process_manager_api.get_signals().runner_ended.connect(self.output_widget.handle_process_ended)

        # 初始化显示状态
        self._update_panels_visibility()

        self.content_layout.addStretch()


    def _create_panel_row(self, layout: QVBoxLayout, *widgets, add_stretch=False) -> QWidget:
        """为特定 panel 的内部 layout 创建横向排布行"""
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setSpacing(10)
        row_layout.setContentsMargins(0, 0, 0, 0)

        for widget in widgets:
            row_layout.addWidget(widget)

        if add_stretch:
            row_layout.addStretch()

        layout.addWidget(row)
        return row


    def _create_config_widget(self, widget_type: str, param, length: int = None):
        if widget_type == "combo_box":
            options = param.constraints["options"]
            default_val = param.default
            default_index = options.index(default_val) if default_val in options else 0
            opts_str = [str(opt) for opt in options]
            return create_combo_box(length=length, items=opts_str, default_index=default_index)
        elif widget_type == "check_box":
            return create_check_box(default_checked=param.default)
        return None


    def _build_standardize_panel(self):
        self.standardize_panel = QWidget()
        layout = QVBoxLayout(self.standardize_panel)
        layout.setContentsMargins(0, 0, 0, 0)
        
        divider = create_divider(i18n.t("app.auto_convert.standardize_divider", fallback="Standardize Settings"))
        layout.addWidget(divider)
        
        # 3. Settings Row 1
        song_name_label = create_label(i18n.t("app.auto_convert.song_name_label", fallback="Song Name"))
        self.song_name_line_edit = create_line_edit(length=180)
        
        video_mode_label = create_label(i18n.t("app.auto_convert.video_mode_label", fallback="Video Mode"))
        self.video_mode_combo_box = self._create_config_widget("combo_box", AC_Defs.video_mode, length=120)

        self._create_panel_row(layout, 
            song_name_label, self.song_name_line_edit,
            video_mode_label, self.video_mode_combo_box,
            add_stretch=True)

        # 4. Settings Row 2
        start_sec_label = create_label(i18n.t("app.auto_convert.start_sec_label", fallback="Start (s)"))
        self.start_sec_line_edit = create_line_edit(length=60, validator='float')
        
        end_sec_label = create_label(i18n.t("app.auto_convert.end_sec_label", fallback="End (s)"))
        self.end_sec_line_edit = create_line_edit(length=60, validator='float')

        target_res_label = create_label(i18n.t("app.auto_convert.target_res_label", fallback="Target Res"))
        self.target_res_combo_box = create_combo_box(length=80, items=["720", "1080", "1440", "2160"], default_index=1)
        
        skip_detect_rect_label = create_label(i18n.t("app.auto_convert.skip_detect_circle_label", fallback="Skip Circle Detect"))
        self.skip_detect_circle_check_box = self._create_config_widget("check_box", AC_Defs.skip_detect_circle)

        self._create_panel_row(layout,
            start_sec_label, self.start_sec_line_edit,
            end_sec_label, self.end_sec_line_edit,
            target_res_label, self.target_res_combo_box,
            skip_detect_rect_label, self.skip_detect_circle_check_box,
            add_stretch=True)

        self.content_layout.addWidget(self.standardize_panel)



    def _build_detect_panel(self):
        self.detect_panel = QWidget()
        layout = QVBoxLayout(self.detect_panel)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(create_divider(i18n.t("app.auto_convert.detect_divider", fallback="Detect Settings")))

        # Settings
        skip_det_label = create_label(i18n.t("app.auto_convert.skip_detect_label", fallback="Skip Detect"))
        self.skip_detect_check_box = self._create_config_widget("check_box", AC_Defs.skip_detect)

        skip_cls_label = create_label(i18n.t("app.auto_convert.skip_cls_label", fallback="Skip Classify"))
        self.skip_cls_check_box = self._create_config_widget("check_box", AC_Defs.skip_cls)

        skip_export_label = create_label(i18n.t("app.auto_convert.skip_export_tracked_label", fallback="Skip Export Tracked"))
        self.skip_export_tracked_check_box = self._create_config_widget("check_box", AC_Defs.skip_export_tracked_video)

        self._create_panel_row(layout,
            skip_det_label, self.skip_detect_check_box,
            skip_cls_label, self.skip_cls_check_box,
            skip_export_label, self.skip_export_tracked_check_box,
            add_stretch=True)

        self.content_layout.addWidget(self.detect_panel)



    def _build_analyze_panel(self):
        self.analyze_panel = QWidget()
        layout = QVBoxLayout(self.analyze_panel)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(create_divider(i18n.t("app.auto_convert.analyze_divider", fallback="Analyze Settings")))

        # Settings
        bpm_label = create_label(i18n.t("app.auto_convert.bpm_label", fallback="BPM (*)"))
        self.bpm_line_edit = create_line_edit(length=60, validator='float')

        chart_lv_label = create_label(i18n.t("app.auto_convert.chart_lv_label", fallback="Chart Level"))
        self.chart_lv_combo_box = self._create_config_widget("combo_box", AC_Defs.chart_lv, length=60)

        bd_label = create_label(i18n.t("app.auto_convert.base_denominator_label", fallback="Base Denominator"))
        self.base_denominator_combo_box = self._create_config_widget("combo_box", AC_Defs.base_denominator, length=60)
        
        dd_label = create_label(i18n.t("app.auto_convert.duration_denominator_label", fallback="Duration Denominator"))
        self.duration_denominator_combo_box = self._create_config_widget("combo_box", AC_Defs.duration_denominator, length=60)

        self._create_panel_row(layout,
            bpm_label, self.bpm_line_edit,
            chart_lv_label, self.chart_lv_combo_box,
            bd_label, self.base_denominator_combo_box,
            dd_label, self.duration_denominator_combo_box,
            add_stretch=True)

        self.content_layout.addWidget(self.analyze_panel)



    def _build_bottom_controls(self):
        
        layout = self.content_layout
        layout.addSpacing(UI_Style.widget_spacing * 2)

        # Enable flags row
        self.enable_standardize_cb = create_check_box(default_checked=AC_Defs.is_standardize_enabled.default)
        en_std_label = create_label(i18n.t("app.auto_convert.en_standardize_label", fallback="Enable Standardize"))

        self.enable_detect_cb = create_check_box(default_checked=AC_Defs.is_detect_enabled.default)
        en_det_label = create_label(i18n.t("app.auto_convert.en_detect_label", fallback="Enable Detect"))

        self.enable_analyze_cb = create_check_box(default_checked=AC_Defs.is_analyze_enabled.default)
        en_ana_label = create_label(i18n.t("app.auto_convert.en_analyze_label", fallback="Enable Analyze"))

        self.create_row(
            en_std_label, self.enable_standardize_cb,
            en_det_label, self.enable_detect_cb,
            en_ana_label, self.enable_analyze_cb,
            add_stretch=True
        )

        layout.addSpacing(UI_Style.widget_spacing)

        # Submit row
        self.submit_button = create_stated_button(i18n.t("app.auto_convert.submit_button", fallback="Submit Auto Convert"), isbig=True)
        self.taskname_line_edit = create_line_edit(length=200, placeholder=i18n.t("app.auto_convert.taskname_placeholder", fallback="Optional Task Name (or use Song Name)"))
        
        self.create_row(self.submit_button, self.taskname_line_edit, add_stretch=True)


    def _update_panels_visibility(self):
        """根据启用的模块复选框更新 UI 区块的可见性。"""
        std_enabled = self.enable_standardize_cb.isChecked()
        det_enabled = self.enable_detect_cb.isChecked()
        ana_enabled = self.enable_analyze_cb.isChecked()




    def on_std_input_selected(self, error_msg: str) -> None:
        """Standardize 视频选择回调"""

        if len(error_msg) > 0:
            show_notify_dialog("app.auto_convert", error_msg)
            return

        # 补全 Song Name
        if not self.song_name_line_edit.text().strip():
            self.song_name_line_edit.setText(Path(self.std_media_input.get_path()).stem)


    def on_submit_clicked(self) -> None:
        """收集数据提交转档任务"""
        
        def try_float(val):
            return float(val) if val else None
            
        def try_int(val):
            return int(val) if val else None

        try:
            self.submit_button.setEnabled(False)

            raw_data = {
                # common
                AC_Defs.is_standardize_enabled.key: self.enable_standardize_cb.isChecked(),
                AC_Defs.is_detect_enabled.key:      self.enable_detect_cb.isChecked(),
                AC_Defs.is_analyze_enabled.key:     self.enable_analyze_cb.isChecked(),
            }

            if raw_data[AC_Defs.is_standardize_enabled.key]:
                raw_data.update({
                    AC_Defs.standardize_input_video_path.key: self.std_media_input.get_path() or None,
                    AC_Defs.song_name.key: self.song_name_line_edit.text().strip() or None,
                    AC_Defs.video_mode.key: self.video_mode_combo_box.currentText().strip() or None,
                    AC_Defs.start_sec.key: try_float(self.start_sec_line_edit.text().strip()),
                    AC_Defs.end_sec.key: try_float(self.end_sec_line_edit.text().strip()),
                    AC_Defs.target_res.key: try_int(self.target_res_combo_box.currentText()),
                    AC_Defs.skip_detect_circle.key: self.skip_detect_circle_check_box.isChecked(),
                    AC_Defs.duration.key: try_float(self.std_media_input.selected_file_duration),
                    AC_Defs.media_type.key: self.std_media_input.selected_file_type
                })

            if raw_data[AC_Defs.is_detect_enabled.key]:
                if not raw_data[AC_Defs.is_standardize_enabled.key]:
                    raw_data[AC_Defs.std_video_path_detect.key] = self.std_media_input.get_path() or None
                raw_data.update({
                    AC_Defs.skip_detect.key: self.skip_detect_check_box.isChecked(),
                    AC_Defs.skip_cls.key: self.skip_cls_check_box.isChecked(),
                    AC_Defs.skip_export_tracked_video.key: self.skip_export_tracked_check_box.isChecked(),
                })
                
            if raw_data[AC_Defs.is_analyze_enabled.key]:
                if not raw_data[AC_Defs.is_standardize_enabled.key]:
                    raw_data[AC_Defs.std_video_path_analyze.key] = self.std_media_input.get_path() or None
                raw_data.update({
                    AC_Defs.bpm.key: try_float(self.bpm_line_edit.text().strip()),
                    AC_Defs.chart_lv.key: try_int(self.chart_lv_combo_box.currentText()),
                    AC_Defs.base_denominator.key: try_int(self.base_denominator_combo_box.currentText()),
                    AC_Defs.duration_denominator.key: try_int(self.duration_denominator_combo_box.currentText()),
                })

            task_name = self.taskname_line_edit.text().strip()
            # 如果task_name为空并且启动了standardize，可以用歌曲名代偿一下
            if not task_name and raw_data.get(AC_Defs.is_standardize_enabled.key):
                task_name = self.song_name_line_edit.text().strip()

            result = AutoConvertPipeline.submit_task(raw_data, task_name)
            if not result.is_ok:
                reason = print_op_result(result) 
                try:
                    # 获取内部原始错误消息
                    if result.inner and hasattr(result.inner, 'inner') and result.inner.inner:
                        root_result = result.inner.inner
                        if "validate_pydantic()" in root_result.source.lower() and \
                           "pydantic validation failed" in root_result.error_msg.lower():
                            reason = root_result.error_raw
                except Exception:
                    pass
                show_notify_dialog("app.auto_convert", f"Task Submission Failed:\n{reason}")
                return

            runner_id, cmd_list = result.value
            self.output_widget.bind_current_runner_id(runner_id)
            
            # 显示成功通知
            message = i18n.t("app.auto_convert.notice_submit_success", fallback=f"Auto Convert Task Submitted: {runner_id}", task_id=runner_id)
            create_floating_notification(message, self.window())

        except Exception as e:
            show_notify_dialog("app.auto_convert", f"Unexpected Error:\n{traceback.format_exc()}")
        finally:
            self.submit_button.setEnabled(True)




