from ..base_tool_page import BaseToolPage
from ...widgets import *
from src.services import FFprobeInspect, FFprobeInspectResult, MediaType
from src.services.pydantic_models import get_ffmpeg_options, RunFFmpegBase, RunFFmpegAudio, RunFFmpegVideoWithAudio, RunFFmpegVideoWithoutAudio
import i18n

class RunFFmpegPage(BaseToolPage):

    def setup_content(self):

        # 需要用到的公共变量
        self.input_file_path_display = None
        self.probe_result_display = None
        self.selected_file_duration = None
        self.selected_file_type = MediaType.UNKNOWN

        # common widgets
        self.common_pad_start_sec_line_edit = None
        self.common_start_sec_line_edit = None
        self.common_end_sec_line_edit = None
        self.common_clear_metadata_check_box = None
        self.common_no_video_check_box = None
        self.common_no_audio_check_box = None
        # video widgets
        self.video_crf_combo_box = None
        self.video_resolution_combo_box = None
        self.video_fps_combo_box = None
        self.video_gop_optimize_check_box = None
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
        # help icons
        video_crf_help = create_help_icon(i18n.t("app.media_subpages.run_ffmpeg.ui_video_crf_help"))
        video_resolution_help = create_help_icon(i18n.t("app.media_subpages.run_ffmpeg.ui_video_resolution_help"))
        video_fps_help = create_help_icon(i18n.t("app.media_subpages.run_ffmpeg.ui_video_fps_help"))
        video_gop_optimize_help = create_help_icon(i18n.t("app.media_subpages.run_ffmpeg.ui_video_gop_optimize_help"))
        # create rows
        self.create_row(video_crf_label, self.video_crf_combo_box, video_crf_help,
                        video_resolution_label, self.video_resolution_combo_box, video_resolution_help,
                        video_fps_label, self.video_fps_combo_box, video_fps_help,
                        video_gop_optimize_label, self.video_gop_optimize_check_box, video_gop_optimize_help,
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
        start_end_label_between = create_label("~")  # between start and end
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

        # 第六行: submit 按钮 + no_video/no_audio checkboxes
        no_video_label = create_label(i18n.t("app.media_subpages.run_ffmpeg.ui_no_video_label"))
        no_audio_label = create_label(i18n.t("app.media_subpages.run_ffmpeg.ui_no_audio_label"))
        no_video_audio_help = create_help_icon(i18n.t("app.media_subpages.run_ffmpeg.ui_no_video_audio_help"))

        self.create_row(no_video_label, self.common_no_video_check_box,
                        no_audio_label, self.common_no_audio_check_box, no_video_audio_help,
                        add_stretch=True)
        




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
        # common no_video check box
        self.common_no_video_check_box = self.init_ffmpeg_widget(
            common_dict, widget_type="check_box", param_name="no_video")
        # common no_audio check box
        self.common_no_audio_check_box = self.init_ffmpeg_widget(
            common_dict, widget_type="check_box", param_name="no_audio")
        
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
        
        # audio format combo box
        self.audio_format_combo_box = create_combo_box(length=100)
        # audio bitrate combo box
        self.audio_bitrate_combo_box = create_combo_box(length=100)
        # audio sample_rate combo box
        self.audio_sample_rate_combo_box = self.init_ffmpeg_widget(
            audio_dict, widget_type="combo_box", param_name="audio_sample_rate", length=70)
        # audio volume line edit
        min, max, default = audio_dict["audio_volume"]
        self.audio_volume_line_edit = create_line_edit(
            default_text=str(default), placeholder=f"{min}~{max}", length=60, validator='int')
