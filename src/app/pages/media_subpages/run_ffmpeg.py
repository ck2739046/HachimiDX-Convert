import os
from ..base_tool_page import BaseToolPage
from ...ui_style import UI_Style
from ...widgets import *
from src.services import MediaType
from src.core.tools import FFprobeInspect, FFprobeInspectResult
from src.core.tools import show_confirm_dialog, show_notify_dialog
from src.services.pydantic_models import get_ffmpeg_options, build_full_output_path, RunFFmpegBase, RunFFmpegAudio, RunFFmpegVideoWithAudio, RunFFmpegVideoWithoutAudio
import i18n

class RunFFmpegPage(BaseToolPage):

    def setup_content(self):

        # 需要用到的公共变量
        self.input_file_path_display = None
        self.probe_result_display = None
        self.audio_options_dict = None
        self.selected_file_duration = None
        self.selected_file_type = MediaType.UNKNOWN

        # common widgets
        self.common_pad_start_sec_line_edit = None
        self.common_start_sec_line_edit = None
        self.common_end_sec_line_edit = None
        self.common_clear_metadata_check_box = None
        self.output_filename_line_edit = None
        self.output_full_path_display = None
        self.taskname_line_edit = None
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
        
        # 参数调整区域
        self.init_ffmpeg_widgets()

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
        pad_start_sec_label = create_label(i18n.t("app.media_subpages.run_ffmpeg.ui_pad_start_sec_label"))
        start_end_label = create_label(i18n.t("app.media_subpages.run_ffmpeg.ui_start_end_label"))
        start_end_label_between = create_label("→")  # between start and end
        clear_metadata_label = create_label(i18n.t("app.media_subpages.run_ffmpeg.ui_clear_metadata_label"))
        # help icons
        pad_start_sec_help = create_help_icon(i18n.t("app.media_subpages.run_ffmpeg.ui_pad_start_sec_help"))
        start_end_help = create_help_icon(i18n.t("app.media_subpages.run_ffmpeg.ui_start_end_help"))
        clear_metadata_help = create_help_icon(i18n.t("app.media_subpages.run_ffmpeg.ui_clear_metadata_help"))
        # create rows
        self.create_row(pad_start_sec_label, self.common_pad_start_sec_line_edit, pad_start_sec_help,
                        start_end_label, self.common_start_sec_line_edit, start_end_label_between, self.common_end_sec_line_edit, start_end_help,
                        clear_metadata_label, self.common_clear_metadata_check_box, clear_metadata_help,
                        add_stretch=True)

        # 第六行: 输出文件名+完整输出路径显示
        output_filename_label = create_label(i18n.t("app.media_subpages.run_ffmpeg.ui_output_filename_label"))
        self.output_filename_line_edit = create_line_edit(length=280)
        self.output_filename_line_edit.textChanged.connect(self.on_output_filename_changed)
        output_filename_help = create_help_icon(i18n.t("app.media_subpages.run_ffmpeg.ui_output_filename_help"))
        self.output_full_path_display = create_path_display()
        self.create_row(output_filename_label,
                        self.output_filename_line_edit,
                        output_filename_help,
                        self.output_full_path_display)
        
        # 第七行：submit按钮 + taskname输入框
        self.taskname_line_edit = create_line_edit(
            length=200, placeholder=i18n.t("app.media_subpages.run_ffmpeg.ui_taskname_placeholder"))
        submit_button = create_button(i18n.t("app.media_subpages.run_ffmpeg.ui_submit_button"), isbig=True)
        self.content_layout.addSpacing(UI_Style.widget_spacing)
        self.create_row(submit_button, self.taskname_line_edit, add_stretch=True)
        




    def on_input_file_selected(self, selected_file_path: str):
        """选择文件后检测媒体信息并显示结果"""
        result = FFprobeInspect.inspect_media(selected_file_path)
        if not result.ok:
            error_msg = i18n.t("app.media_subpages.run_ffmpeg.warning_ffprobe_inspect_failed", error_msg=result.error_msg, raw_output=result.raw)
            self.output_widget.append_text(error_msg)
            self.probe_result_display.setText(result.media_type.name)
            return
        # 更新公共变量
        self.selected_file_duration = result.duration
        self.selected_file_type = result.media_type
        # 更新音频codec/bitrate可选项
        self.update_audio_codec_bitrate_options()
        # 显示检测结果
        display_text = self.build_probe_result_text(result)
        self.probe_result_display.setText(display_text)
        # self.output_widget.append_text(str(result.raw))



    def build_probe_result_text(self, result: FFprobeInspectResult) -> str:
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



    def init_ffmpeg_widget(self, dictt: dict, widget_type: str, param_name: str, length: int = None):
        if widget_type == "combo_box":
            opts = dictt[param_name]["opts"]
            default = dictt[param_name]["default"]
            default_index = opts.index(default)
            combo_box = create_combo_box(length = length,
                                         items = opts,
                                         default_index = default_index)
            return combo_box
        
        elif widget_type == "check_box":
            default = dictt[param_name]
            check_box = create_check_box(default_checked=default)
            return check_box
        
        return None # 不应该发生
            


    def init_ffmpeg_widgets(self):

        common_dict, video_dict, audio_dict = get_ffmpeg_options()
        self.audio_options_dict = audio_dict  # 保存音频参数字典以便后续使用

        # common pad_start_sec line edit
        self.common_pad_start_sec_line_edit = create_line_edit(
            length=70, validator='float')
        # common start_sec line edit
        self.common_start_sec_line_edit = create_line_edit(
            length=70, validator='float')
        # common end_sec line edit
        self.common_end_sec_line_edit = create_line_edit(
            length=70, validator='float')
        # common clear_metadata check box
        self.common_clear_metadata_check_box = self.init_ffmpeg_widget(
            common_dict, widget_type="check_box", param_name="clear_metadata")
        
        # video crf combo box
        self.video_crf_combo_box = self.init_ffmpeg_widget(
            video_dict, widget_type="combo_box", param_name="video_crf", length=50)
        # video resolution combo box
        self.video_resolution_combo_box = self.init_ffmpeg_widget(
            video_dict, widget_type="combo_box", param_name="video_resolution", length=102)
        # video fps combo box
        self.video_fps_combo_box = self.init_ffmpeg_widget(
            video_dict, widget_type="combo_box", param_name="video_fps", length=70)
        # gop_optimize check box
        self.video_gop_optimize_check_box = self.init_ffmpeg_widget(
            video_dict, widget_type="check_box", param_name="video_gop_optimize")
        # video mute check box
        self.video_mute_check_box = self.init_ffmpeg_widget(
            video_dict, widget_type="check_box", param_name="video_mute")
        
        # audio format combo box
        self.audio_format_combo_box = create_combo_box(length=62)
        self.audio_format_combo_box.currentIndexChanged.connect(self.on_audio_format_changed)
        # audio bitrate combo box
        self.audio_bitrate_combo_box = create_combo_box(length=105)
        # audio sample_rate combo box
        self.audio_sample_rate_combo_box = self.init_ffmpeg_widget(
            audio_dict, widget_type="combo_box", param_name="audio_sample_rate", length=70)
        # audio volume line edit
        min, max, default = audio_dict["audio_volume"]
        self.audio_volume_line_edit = create_line_edit(
            default_text=str(default), placeholder=f"{min}~{max}", length=60, validator='int')


    def update_audio_codec_bitrate_options(self):

        media_type = self.selected_file_type
        audio_dict = self.audio_options_dict

        # 更新音频格式选项
        self.audio_format_combo_box.blockSignals(True)
        self.audio_format_combo_box.clear()

        if media_type == MediaType.VIDEO_WITH_AUDIO or media_type == MediaType.VIDEO_WITHOUT_AUDIO:
            opts = audio_dict["audio_format_video"]["opts"]
            default = audio_dict["audio_format_video"]["default"]
        elif media_type == MediaType.AUDIO:
            opts = audio_dict["audio_format_audio"]["opts"]
            default = audio_dict["audio_format_audio"]["default"]
        else:
            self.audio_format_combo_box.blockSignals(False)
            return

        self.audio_format_combo_box.addItems(opts)
        self.audio_format_combo_box.setCurrentText(default)
        self.on_audio_format_changed() # 触发码率更新
        self.audio_format_combo_box.blockSignals(False)



    def on_audio_format_changed(self):
        """当音频格式改变时，同步更新码率可选项"""
        current_format = self.audio_format_combo_box.currentText()

        self.audio_bitrate_combo_box.clear()

        if not current_format:
            return

        audio_dict = self.audio_options_dict
        if not audio_dict:
            return
            
        key = f"audio_bitrate_{current_format}"
        if key in audio_dict:
            opts = audio_dict[key]["opts"]
            default = audio_dict[key]["default"]
            
            self.audio_bitrate_combo_box.blockSignals(True)
            self.audio_bitrate_combo_box.clear()
            self.audio_bitrate_combo_box.addItems(opts)
            if default in opts:
                self.audio_bitrate_combo_box.setCurrentText(default)
            self.audio_bitrate_combo_box.blockSignals(False)

        self.on_output_filename_changed() # 触发输出路径更新



    def on_output_filename_changed(self):
        """当输出文件名改变时，更新完整输出路径显示"""
        # 默认清空完整输出路径显示
        self.output_full_path_display.setText("")

        input_path = self.input_file_path_display.text().strip()
        input_path = os.path.normpath(os.path.abspath(input_path))
        if not input_path:
            return
        
        output_filename = self.output_filename_line_edit.text().strip()
        if not output_filename:
            output_filename = None  # 空文件名视为 None
        input_filename = os.path.splitext(os.path.basename(input_path))[0]
        if output_filename == input_filename:
            show_notify_dialog("app.media_subpages.run_ffmpeg", i18n.t("app.media_subpages.run_ffmpeg.warning_output_filename_same_as_input"))
            return  # 与输入文件名相同则不更新显示

        if (self.selected_file_type == MediaType.VIDEO_WITH_AUDIO or
            self.selected_file_type == MediaType.VIDEO_WITHOUT_AUDIO):
            output_extension = ".mp4"
        elif self.selected_file_type == MediaType.AUDIO:
            format = self.audio_format_combo_box.currentText().strip()
            if not format: return
            output_extension = f".{format}"
        else: 
            return
        
        ok, output_path, error_msg = build_full_output_path(input_path, output_filename, output_extension)
        if not ok:
            show_notify_dialog("app.media_subpages.run_ffmpeg", error_msg)
            return

        # 更新完整输出路径显示
        self.output_full_path_display.setText(os.path.normpath(os.path.abspath(str(output_path))))
