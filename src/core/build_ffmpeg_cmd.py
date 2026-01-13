from typing import Optional
from src.services.path_manage import PathManage
from .schemas.media_config import MediaType
from .schemas.media_model import MediaModel
from src.core.schemas.op_result import OpResult, ok, err





def build_ffmpeg_cmd(data: MediaModel) -> OpResult[list[str]]:
    """
    主入口: 构建 FFmpeg 命令行参数列表

    输入:
        data (MediaModel)

    输出:
        OpResult[list[str]]: FFmpeg 命令行参数列表
    """

    result = _build_constant_args()
    if not result.is_ok:
        return err(
            error_msg = "Failed to build constant FFmpeg arguments.",
            inner = result
        )
    args = result.value

    result = _build_common_args(data)
    if not result.is_ok:
        return err(
            error_msg = "Failed to build common FFmpeg arguments.",
            inner = result
        )
    args.extend(result.value)

    result = _build_video_args(data)
    if not result.is_ok:
        return err(
            error_msg = "Failed to build video FFmpeg arguments.",
            inner = result
        )
    args.extend(result.value)

    result = _build_audio_args(data)
    if not result.is_ok:
        return err(
            error_msg = "Failed to build audio FFmpeg arguments.",
            inner = result
        )
    args.extend(result.value)

    # 最后添加输出文件路径
    args.append(str(data.output_path))

    return ok(args)





def _build_constant_args() -> OpResult[list[str]]:
    """构建 FFmpeg 固定的参数部分"""

    ffmpeg_exe = PathManage.FFMPEG_EXE_PATH
    if not ffmpeg_exe.is_file():
        return err(f"FFmpeg executable not found at: {ffmpeg_exe}")
    
    args = [
        str(ffmpeg_exe),
        "-y",                 # 覆盖输出文件
        "-hide_banner",       # 隐藏横幅信息
        "-stats",             # 显示进度统计信息
        "-loglevel", "error"  # 只显示错误信息
    ]

    return ok(args)




def _build_common_args(data: MediaModel) -> OpResult[list[str]]:
    """构建 FFmpeg 通用参数部分"""

    args = []

    # 输入文件
    args.extend(["-i", str(data.input_path)])

    # clear metadata
    if data.clear_metadata:
        args.extend(["-map_metadata", "-1"])

    # start
    if data.start:
        args.extend(["-ss", str(data.start)])

    # end
    if data.end:
        args.extend(["-to", str(data.end)])

    # pad_start 要在音频/视频滤镜中处理
    # output_path 要加在最后
    
    return ok(args)




def _build_video_args(data: MediaModel) -> OpResult[list[str]]:
    """构建 FFmpeg 视频参数部分"""

    args = []

    if not(data.media_type == MediaType.VIDEO_WITH_AUDIO or \
           data.media_type == MediaType.VIDEO_WITHOUT_AUDIO):
        return ok(args)  # 非视频类型，无需视频参数
    
    args.extend(["-pix_fmt", "yuv420p"])
    args.extend(["-c:v", "libx264"])
    args.extend(["-crf", str(data.video_crf)])

    if data.video_fps:
        args.extend(["-r", str(data.video_fps)])

    if data.video_gop_optimize:
        args.extend(["-g", "30"])

    vf = _build_video_filter(
        size = data.video_side_resolution,
        crop = (data.video_crop_w, data.video_crop_h, data.video_crop_x, data.video_crop_y),
        pad = data.pad_start
    )
    if vf:
        args.extend(["-vf", vf])

    # video_mute 在 audio 部分处理

    return ok(args)



def _build_video_filter(size: Optional[int],
                        crop: tuple[Optional[int], Optional[int], Optional[int], Optional[int]],
                        pad: Optional[float]
                       ) -> Optional[str]:
    """构建视频滤镜"""

    filters = []

    # Crop
    if all(v is not None for v in crop):
        w, h, x, y = crop
        filters.append(f"crop={w}:{h}:{x}:{y}")

    # Resize
    if size:
        # Scale while keeping aspect ratio
        # Pad to square with black borders
        scale_expr = f"if(gt(iw,ih),{size},-1):if(gt(iw,ih),-1,{size})".replace(",", r"\,") # 对逗号转义
        pad_expr = f"{size}:{size}:(ow-iw)/2:(oh-ih)/2:black"
        filters.append(f"scale={scale_expr},pad={pad_expr}")

    # Pad start
    if pad:
        filters.append(f"tpad=start_duration={pad}:color=black")

    return ",".join(filters) if filters else None







def _build_audio_args(data: MediaModel) -> OpResult[list[str]]:
    """构建 FFmpeg 音频参数部分"""

    args = []

    if not(data.media_type == MediaType.AUDIO or \
           data.media_type == MediaType.VIDEO_WITH_AUDIO or \
           data.video_mute == False):
        
        args.extend(["-an"])  # 无音频输出
        return ok(args)
    
    # audio_format
    if data.audio_format == "mp3":
        args.extend(["-c:a", "libmp3lame"])
    elif data.audio_format == "aac":
        args.extend(["-c:a", "aac"])
    elif data.audio_format == "ogg":
        args.extend(["-c:a", "libvorbis"])
    else:
        return err(f"Unsupported audio format: {data.audio_format}")
    
    # audio_bitrate
    mode, num = data.audio_bitrate.split(" ")[:2]
    if mode == "vbr":
        args.extend(["-q:a", str(num)])
    elif mode == "cbr":
        args.extend(["-b:a", str(num)])
    else:
        return err(f"Unsupported audio bitrate mode: {mode}")
    
    # sample_rate
    if data.audio_sample_rate:
        args.extend(["-ar", str(data.audio_sample_rate)])

    # always force stereo
    args.extend(["-ac", "2"])

    # audio filter
    af = _build_audio_filters(volume=data.audio_volume,
                              pad=data.pad_start,
                              media_type=data.media_type,
                              mute=data.video_mute)
    if af:
        args.extend(["-af", af])

    return ok(args)




def _build_audio_filters(volume: Optional[int],
                         pad: Optional[float],
                         media_type: MediaType,
                         mute: Optional[bool]
                        ) -> Optional[str]:
    """构建音频滤镜"""

    filters = []

    # pad start
    if pad:
        pad_ms = int(round(pad * 1000.0))
        filters.append(f"adelay={pad_ms}|{pad_ms}") # "ms|ms" for stereo

    # volume
    if volume and volume != 100:
        filters.append(f"volume={(volume / 100.0):.2f}")

    # 音频同步
    if media_type == MediaType.VIDEO_WITH_AUDIO and not mute:
        filters.append("aresample=async=1")

    return ",".join(filters) if filters else None
