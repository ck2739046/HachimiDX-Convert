from ..base_tool_page import BaseToolPage
from ...widgets import *
from src.services import FFprobeInspect, FFprobeInspectResult, MediaType
import i18n

class RunFfmpegPage(BaseToolPage):

    def setup_content(self):

        # 需要用到的公共变量
        self.input_file_path_display = None
        self.probe_result_display = None
        self.selected_file_duration = None
        self.selected_file_type = MediaType.UNKNOWN

        # 第一行: 输入文件选择
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
        
        # 第三行: video 参数
        video_divider = create_divider(i18n.t("app.media_subpages.run_ffmpeg.ui_video_divider"))
        self.content_layout.addWidget(video_divider)
        


        

    def on_input_file_selected(self, selected_file_path: str):
        """选择文件后检测媒体信息并显示结果"""
        result = FFprobeInspect.inspect_media(selected_file_path)
        if not result.ok:
            error_msg = i18n.t("app.media_subpages.run_ffmpeg.warning_ffprobe_inspect_failed", error_msg=result.error_msg, raw_output=result.raw)
            self.output_widget.append_text(error_msg)
            self.probe_result_display.setText(result.media_type.name)
            return
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
