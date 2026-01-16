import os
import traceback
from PyQt6.QtWidgets import QVBoxLayout

from ..base_output_page import BaseOutputPage
from ...ui_style import UI_Style
from ...widgets import *
from src.services import process_manager_api
from src.services.pipeline import MediaPipeline
from src.core.tools import FFprobeInspect, FFprobeInspectResult
from src.core.tools import show_notify_dialog
from src.core.schemas.op_result import OpResult, ok, err, print_op_result
from src.core.schemas.media_config import MediaType, MediaConfig_Definition
from src.core.schemas.media_config import MediaConfig_Definitions as M_Defs
import i18n



class RunFFmpegPage(BaseOutputPage):

    def setup_content(self):

        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(10, 10, 10, 10)

        # 需要用到的公共变量
        self.input_file_path_display = None
        self.probe_result_display = None
        self.selected_file_duration = None
        self.selected_file_type = MediaType.UNKNOWN

        # video widgets
        self.video_crf_combo_box = None
        self.video_resolution_combo_box = None
        self.video_fps_combo_box = None
        self.video_gop_optimize_check_box = None
        self.video_mute_check_box = None
        # audio widgets
        self.audio_format_combo_box = None
        self.audio_bitrate_combo_box = None
        self.audio_sample_rate_combo_box = None
        self.audio_volume_line_edit = None
        # common widgets
        self.common_pad_start_line_edit = None
        self.common_start_line_edit = None
        self.common_end_line_edit = None
        self.common_clear_metadata_check_box = None

        self.output_filename_line_edit = None
        self.output_full_path_display = None

        self.taskname_line_edit = None
        self.submit_button = None





        # 第一行: 输入文件选择
        file_select_divider = create_divider(i18n.t("app.media_subpages.run_ffmpeg.ui_select_file_divider"))
        self.content_layout.addWidget(file_select_divider)
        input_file_select_button, self.input_file_path_display, _ = create_file_selection_row(
            button_text=i18n.t("app.media_subpages.run_ffmpeg.ui_select_input_file_button"),
            on_button_clicked_handler=self.on_input_file_selected)
        self.create_row(input_file_select_button,
                        self.input_file_path_display)
        



        # 第二行: 媒体文件检测结果显示
        probe_result_display_prefix = create_label(text=i18n.t("app.media_subpages.run_ffmpeg.probe_result_display.ui_ffprobe_inspect_prefix"))
        probe_result_display_help = create_help_icon(i18n.t("app.media_subpages.run_ffmpeg.probe_result_display.ui_ffprobe_inspect_help"))
        self.probe_result_display = create_label(expand=True)
        self.create_row(probe_result_display_prefix,
                        probe_result_display_help,
                        self.probe_result_display)
        



        self.init_ffmpeg_widgets() # 3-5行: 参数调整区域
        



        # 第三行: video 参数
        video_divider = create_divider(i18n.t("app.media_subpages.run_ffmpeg.ui_video_divider"))
        self.content_layout.addWidget(video_divider)
        # labels
        video_crf_label = create_label(i18n.t("app.media_subpages.run_ffmpeg.ui_video_crf_label"))
        video_resolution_label = create_label(i18n.t("app.media_subpages.run_ffmpeg.ui_video_resolution_label"))
        video_fps_label = create_label(i18n.t("app.media_subpages.run_ffmpeg.ui_video_fps_label"))
        video_gop_optimize_label = create_label(i18n.t("app.media_subpages.run_ffmpeg.ui_video_gop_optimize_label"))
        video_mute_label = create_label(i18n.t("app.media_subpages.run_ffmpeg.ui_video_mute_label"))
        # help icons
        video_crf_help = create_help_icon(i18n.t("app.media_subpages.run_ffmpeg.ui_video_crf_help"))
        video_resolution_help = create_help_icon(i18n.t("app.media_subpages.run_ffmpeg.ui_video_resolution_help"))
        video_fps_help = create_help_icon(i18n.t("app.media_subpages.run_ffmpeg.ui_video_fps_help"))
        video_gop_optimize_help = create_help_icon(i18n.t("app.media_subpages.run_ffmpeg.ui_video_gop_optimize_help"))
        video_mute_help = create_help_icon(i18n.t("app.media_subpages.run_ffmpeg.ui_video_mute_help"))
        # create rows
        self.create_row(video_crf_label, self.video_crf_combo_box, video_crf_help,
                        video_resolution_label, self.video_resolution_combo_box, video_resolution_help,
                        video_fps_label, self.video_fps_combo_box, video_fps_help,
                        video_gop_optimize_label, self.video_gop_optimize_check_box, video_gop_optimize_help,
                        video_mute_label, self.video_mute_check_box, video_mute_help,
                        add_stretch=True)
        
        # 第四行: audio 参数
        audio_divider = create_divider(i18n.t("app.media_subpages.run_ffmpeg.ui_audio_divider"))
        self.content_layout.addWidget(audio_divider)
        # labels
        audio_format_label = create_label(i18n.t("app.media_subpages.run_ffmpeg.ui_audio_format_label"))
        audio_bitrate_label = create_label(i18n.t("app.media_subpages.run_ffmpeg.ui_audio_bitrate_label"))
        audio_sample_rate_label = create_label(i18n.t("app.media_subpages.run_ffmpeg.ui_audio_sample_rate_label"))
        audio_volume_label = create_label(i18n.t("app.media_subpages.run_ffmpeg.ui_audio_volume_label"))
        # help icons
        audio_format_help = create_help_icon(i18n.t("app.media_subpages.run_ffmpeg.ui_audio_format_help"))
        audio_bitrate_help = create_help_icon(i18n.t("app.media_subpages.run_ffmpeg.ui_audio_bitrate_help"))
        audio_sample_rate_help = create_help_icon(i18n.t("app.media_subpages.run_ffmpeg.ui_audio_sample_rate_help"))
        audio_volume_help = create_help_icon(i18n.t("app.media_subpages.run_ffmpeg.ui_audio_volume_help"))
        # create rows
        self.create_row(audio_format_label, self.audio_format_combo_box, audio_format_help,
                        audio_bitrate_label, self.audio_bitrate_combo_box, audio_bitrate_help,
                        audio_sample_rate_label, self.audio_sample_rate_combo_box, audio_sample_rate_help,
                        audio_volume_label, self.audio_volume_line_edit, audio_volume_help,
                        add_stretch=True)
        
        # 第五行: common 参数
        common_divider = create_divider(i18n.t("app.media_subpages.run_ffmpeg.ui_common_divider"))
        self.content_layout.addWidget(common_divider)
        # labels
        pad_start_label = create_label(i18n.t("app.media_subpages.run_ffmpeg.ui_pad_start_sec_label"))
        start_end_label = create_label(i18n.t("app.media_subpages.run_ffmpeg.ui_start_end_label"))
        start_end_label_between = create_label("→")  # between start and end
        clear_metadata_label = create_label(i18n.t("app.media_subpages.run_ffmpeg.ui_clear_metadata_label"))
        # help icons
        pad_start_help = create_help_icon(i18n.t("app.media_subpages.run_ffmpeg.ui_pad_start_sec_help"))
        start_end_help = create_help_icon(i18n.t("app.media_subpages.run_ffmpeg.ui_start_end_help"))
        clear_metadata_help = create_help_icon(i18n.t("app.media_subpages.run_ffmpeg.ui_clear_metadata_help"))
        # create rows
        self.create_row(pad_start_label, self.common_pad_start_line_edit, pad_start_help,
                        start_end_label, self.common_start_line_edit, start_end_label_between, self.common_end_line_edit, start_end_help,
                        clear_metadata_label, self.common_clear_metadata_check_box, clear_metadata_help,
                        add_stretch=True)




        # 第六行: 输出文件名+完整输出路径显示
        output_filename_label = create_label(i18n.t("app.media_subpages.run_ffmpeg.ui_output_filename_label"))
        self.output_filename_line_edit = create_line_edit(length=280)
        output_filename_help = create_help_icon(i18n.t("app.media_subpages.run_ffmpeg.ui_output_filename_help"))
        self.output_full_path_display = create_path_display()
        self.create_row(output_filename_label,
                        self.output_filename_line_edit,
                        output_filename_help,
                        self.output_full_path_display)




        # 第七行：submit按钮 + taskname输入框
        self.taskname_line_edit = create_line_edit(
            length=200, placeholder=i18n.t("app.media_subpages.run_ffmpeg.ui_taskname_placeholder"))
        self.submit_button = create_stated_button(i18n.t("app.media_subpages.run_ffmpeg.ui_submit_button"), isbig=True)
        self.content_layout.addSpacing(UI_Style.widget_spacing)
        self.create_row(self.submit_button, self.taskname_line_edit, add_stretch=True)



        
        self.audio_format_combo_box.currentIndexChanged.connect(self.update_audio_bitrate_combo_box)

        self.output_filename_line_edit.textChanged.connect(self.update_output_full_path_display)

        self.submit_button.clicked.connect(self.on_submit_clicked)
        
        # Connect runner output signals to our output widget
        process_manager_api.get_signals().runner_output.connect(self.output_widget.handle_process_output)
        process_manager_api.get_signals().runner_ended.connect(self.output_widget.handle_process_ended)

        self.content_layout.addStretch()  # 添加弹性空间，使内容从顶部开始显示









    def on_input_file_selected(self, selected_file_path: str) -> None:
        """
        第一行. 文件选择按钮 on clicked hanlder
        选择文件后检测媒体信息并显示结果
        """
        result = FFprobeInspect.inspect_media(selected_file_path)
        if not result.is_ok:
            error_msg = i18n.t("app.media_subpages.run_ffmpeg.warning_ffprobe_inspect_failed", error_msg=print_op_result(result))
            show_notify_dialog("app.media_subpages.run_ffmpeg", error_msg)
            self.probe_result_display.setText(MediaType.UNKNOWN.name)
            return
        ffprobe_result = result.value
        # 更新公共变量
        self.selected_file_duration = ffprobe_result.duration
        self.selected_file_type = ffprobe_result.media_type
        # 显示检测结果
        display_text = self._build_probe_result_text(ffprobe_result)
        self.probe_result_display.setText(display_text)
        # 更新音频codec/bitrate可选项
        self.update_audio_format_combo_box()
        # 更新完整输出路径显示
        self.update_output_full_path_display()

    
    def _build_probe_result_text(self, result: FFprobeInspectResult) -> str:
        """根据 FFprobe 检测结果构建显示文本"""

        video_info = result.video_stream.get("info_str", "")
        if video_info:
            video_line = i18n.t("app.media_subpages.run_ffmpeg.probe_result_display.ui_video_stream_info_prefix") + video_info
        else:
            video_line = i18n.t("app.media_subpages.run_ffmpeg.probe_result_display.ui_no_video_stream_info")
        
        audio_info = result.audio_stream.get("info_str", "")
        if audio_info:
            audio_line = i18n.t("app.media_subpages.run_ffmpeg.probe_result_display.ui_audio_stream_info_prefix") + audio_info
        else:
            audio_line = i18n.t("app.media_subpages.run_ffmpeg.probe_result_display.ui_no_audio_stream_info")

        return "\n".join([video_line, audio_line])





            


    def init_ffmpeg_widgets(self):

        # video crf combo box
        self.video_crf_combo_box = self._create_ffmpeg_widget(
            widget_type="combo_box", param=M_Defs.video_crf, length=50)
        # video resolution combo box
        self.video_resolution_combo_box = self._create_ffmpeg_widget(
            widget_type="combo_box", param=M_Defs.video_side_resolution, length=102, transfer_fn=self.transfer_res)
        # video fps combo box
        self.video_fps_combo_box = self._create_ffmpeg_widget(
            widget_type="combo_box", param=M_Defs.video_fps, length=80, transfer_fn=self.transfer_fps)
        # gop_optimize check box
        self.video_gop_optimize_check_box = self._create_ffmpeg_widget(
            widget_type="check_box", param=M_Defs.video_gop_optimize)
        # video mute check box
        self.video_mute_check_box = self._create_ffmpeg_widget(
            widget_type="check_box", param=M_Defs.video_mute)
        

        # audio format combo box
        self.audio_format_combo_box = create_combo_box(length=62)

        # audio bitrate combo box
        self.audio_bitrate_combo_box = create_combo_box(length=105)

        # audio sample_rate combo box
        self.audio_sample_rate_combo_box = self._create_ffmpeg_widget(
            widget_type="combo_box", param=M_Defs.audio_sample_rate, length=72)
        
        # audio volume line edit
        min, max, default = (
            M_Defs.audio_volume.constraints["ge"],
            M_Defs.audio_volume.constraints["le"],
            M_Defs.audio_volume.default)
        self.audio_volume_line_edit = create_line_edit(
            default_text=str(default), placeholder=f"{min}~{max}", length=60, validator='int')


        # common pad_start line edit
        self.common_pad_start_line_edit = create_line_edit(
            length=70, validator='float')
        # common start line edit
        self.common_start_line_edit = create_line_edit(
            length=70, validator='float')
        # common end line edit
        self.common_end_line_edit = create_line_edit(
            length=70, validator='float')
        # common clear_metadata check box
        self.common_clear_metadata_check_box = self._create_ffmpeg_widget(
            widget_type="check_box", param=M_Defs.clear_metadata)
        

    def _create_ffmpeg_widget(self,
                           widget_type: str,
                           param: MediaConfig_Definition,
                           length: int = None,
                           transfer_fn = None):

        if widget_type == "combo_box":
            options = param.constraints["options"]
            default = param.default
            default_index = options.index(default)
            if transfer_fn:
                options = transfer_fn(options)
                default = transfer_fn(default)
            combo_box = create_combo_box(length = length,
                                         items = options,
                                         default_index = default_index)
            return combo_box
        
        elif widget_type == "check_box":
            default = param.default
            check_box = create_check_box(default_checked = default)
            return check_box
        
        return None # 不应该发生
        






    def update_audio_format_combo_box(self) -> None:
        """根据媒体类型，更新音频格式"""

        media_type = self.selected_file_type
        self.audio_format_combo_box.blockSignals(True)
        self.audio_format_combo_box.clear()

        result = M_Defs.get_audio_format_by_media_type(media_type)
        if not result.is_ok:
            show_notify_dialog("app.media_subpages.run_ffmpeg", result.error_msg)
            self.audio_format_combo_box.blockSignals(False)
            return
        
        default, options = result.value
        self.audio_format_combo_box.addItems(options)
        self.audio_format_combo_box.setCurrentText(default)
        self.update_audio_bitrate_combo_box() # 手动触发码率更新
        self.audio_format_combo_box.blockSignals(False)


    def update_audio_bitrate_combo_box(self) -> None:
        """根据音频格式，更新音频码率"""

        audio_format = self.audio_format_combo_box.currentText()
        self.audio_bitrate_combo_box.blockSignals(True)
        self.audio_bitrate_combo_box.clear()

        result = M_Defs.get_audio_bitrate_by_audio_format(audio_format)
        if not result.is_ok:
            show_notify_dialog("app.media_subpages.run_ffmpeg", result.error_msg)
            self.audio_bitrate_combo_box.blockSignals(False)
            return
        
        default, options = result.value
        self.audio_bitrate_combo_box.addItems(options)
        self.audio_bitrate_combo_box.setCurrentText(default)
        self.audio_bitrate_combo_box.blockSignals(False)


    def update_output_full_path_display(self) -> OpResult[None]:
        """根据输出文件名，更新完整输出路径显示"""

        output_filename = self.output_filename_line_edit.text().strip()

        result = M_Defs.build_full_output_path(
            input_path = str(self.input_file_path_display.text()).strip(),
            output_filename = output_filename,
            audio_format = self.audio_format_combo_box.currentText()
        )
        if not result.is_ok:
            show_notify_dialog("app.media_subpages.run_ffmpeg", result.error_msg)
            self.output_full_path_display.setText("")
            return err(result.error_msg, inner = result)
        
        self.output_full_path_display.setText(str(result.value))
        return ok()


    def transfer_res(self, input_data):

        if str(input_data) == '0':
            return "original"
        if str(input_data) == "original":
            return 0
        if "×" in str(input_data):
            return str(input_data).split("×")[0]
        
        if isinstance(input_data, list):
            output_data = []
            for text in input_data:
                if str(text) == '0':
                    output_data.append("original")
                else:
                    output_data.append(f"{text}×{text}")
            
            return output_data
        
        return input_data
    

    def transfer_fps(self, input_data):

        if str(input_data) == '0':
            return "original"
        if str(input_data) == "original":
            return 0
        
        if isinstance(input_data, list):
            output_data = []
            for text in input_data:
                if str(text) == '0':
                    output_data.append("original")
                else:
                    output_data.append(str(text))

            return output_data
        
        return input_data
                






    def on_submit_clicked(self) -> None:
        """
        submit button on clicked handler
        收集数据，提交任务到调度器
        """

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

            # 手动触发完整输出路径更新
            result = self.update_output_full_path_display()
            if not result.is_ok:
                return

            raw_data: dict = {
                # common
                M_Defs.media_type.key: self.selected_file_type,
                M_Defs.input_path.key: self.input_file_path_display.text().strip() or "",
                M_Defs.output_path.key: self.output_full_path_display.text().strip() or "",
                # video stream
                M_Defs.video_crf.key: try_int(self.video_crf_combo_box.currentText().strip()),
                M_Defs.video_side_resolution.key: self.transfer_res(self.video_resolution_combo_box.currentText().strip()),
                M_Defs.video_fps.key: self.transfer_fps(self.video_fps_combo_box.currentText().strip()),
                M_Defs.video_gop_optimize.key: self.video_gop_optimize_check_box.isChecked(),
                M_Defs.video_mute.key: self.video_mute_check_box.isChecked(),
                # audio stream
                M_Defs.audio_format.key: self.audio_format_combo_box.currentText().strip(),
                M_Defs.audio_bitrate.key: self.audio_bitrate_combo_box.currentText().strip(),
                M_Defs.audio_sample_rate.key: try_int(self.audio_sample_rate_combo_box.currentText().strip()),
                M_Defs.audio_volume.key: try_int(self.audio_volume_line_edit.text().strip()),
                # common
                M_Defs.clear_metadata.key: self.common_clear_metadata_check_box.isChecked(),
                M_Defs.duration.key: try_float(self.selected_file_duration),
                M_Defs.pad_start.key: try_float(self.common_pad_start_line_edit.text().strip()),
                M_Defs.start.key: try_float(self.common_start_line_edit.text().strip()),
                M_Defs.end.key: try_float(self.common_end_line_edit.text().strip()),
            }

            task_name = self.taskname_line_edit.text().strip()
            result = MediaPipeline.submit_task(raw_data, task_name)
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
            show_notify_dialog("app.media_subpages.run_ffmpeg",
                i18n.t("app.media_subpages.run_ffmpeg.warning_unexpected_submit_error", error=traceback.format_exc()))
        finally:
            self.submit_button.setEnabled(True)
