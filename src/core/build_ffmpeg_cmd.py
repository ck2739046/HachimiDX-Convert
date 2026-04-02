import math
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

    # start/end 在滤镜中使用 trim/atrim 处理
    # 不知道 -ss/-to 的 seek 行为是否会有误差，反正先用滤镜处理
    # pad_start 也在滤镜中处理
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
        pad = data.pad_start,
        start = data.start,
        end = data.end,
        scale_x = data.video_scale_x,
        scale_y = data.video_scale_y,
        x_rot_deg = data.video_x_rot_deg,
        y_rot_deg = data.video_y_rot_deg,
        video_width = data.video_width,
        video_height = data.video_height,
    )
    if vf:
        args.extend(["-vf", vf])

    # video_mute 在 audio 部分处理

    return ok(args)



def _build_video_filter(size: Optional[int],
                        crop: tuple[Optional[int], Optional[int], Optional[int], Optional[int]],
                        pad: Optional[float],
                        start: Optional[float],
                        end: Optional[float],
                        scale_x: Optional[float] = None,
                        scale_y: Optional[float] = None,
                        x_rot_deg: Optional[float] = None,
                        y_rot_deg: Optional[float] = None,
                        video_width: Optional[int] = None,
                        video_height: Optional[int] = None
                       ) -> Optional[str]:
    """构建视频滤镜"""

    filters = []

    # trim (decode-time cut, not keyframe dependent)
    if start is not None or end is not None:
        trim_kv = []
        if start is not None:
            trim_kv.append(f"start={start}")
        if end is not None:
            trim_kv.append(f"end={end}")
        filters.append(f"trim={':'.join(trim_kv)}")
        filters.append("setpts=PTS-STARTPTS")

    perspective_filter = _build_axis_rotation_perspective_filter(
        x_rot_deg=x_rot_deg,
        y_rot_deg=y_rot_deg,
        video_width=video_width,
        video_height=video_height,
    )
    if perspective_filter:
        filters.append(perspective_filter)

    # Crop (支持越界，超出部分用黑色填充)
    if all(v is not None for v in crop):
        w, h, x, y = crop
        
        # 计算是否需要扩展画布以容纳整个 crop 区域
        # crop 区域范围: [x, x+w] 水平方向, [y, y+h] 垂直方向
        # 原视频范围: [0, iw] 水平方向, [0, ih] 垂直方向
        
        # 向左/上偏移量（当 x<0 或 y<0 时）
        left_pad = abs(min(x, 0))  # 如果 x<0, left_pad=-x; 否则为 0
        top_pad = abs(min(y, 0))   # 如果 y<0, top_pad=-y; 否则为 0
        
        # 构建 FFmpeg 表达式来处理动态边界计算
        # 向右扩展量 = max(0, x + w - iw)  当 x>=0
        # 向右扩展量 = max(0, x + w - iw + left_pad) 当 x<0 (因为 iw 在新画布中是 iw+left_pad，相对位置变了)
        # 实际上更简单：计算 crop 区域右边界超出原视频右边界的量
        # 新画布中，原视频位于 (left_pad, top_pad)，右边界是 left_pad + iw
        # crop 区域右边界是 left_pad + x + w
        # 超出量 = max(0, left_pad + x + w - (left_pad + iw)) = max(0, x + w - iw)
        right_pad_expr = f"max(0\,{x}+{w}-iw)"
        bottom_pad_expr = f"max(0\,{y}+{h}-ih)"
        
        # 计算 pad 后的画布大小
        pad_w_expr = f"{left_pad}+iw+{right_pad_expr}"
        pad_h_expr = f"{top_pad}+ih+{bottom_pad_expr}"
        
        # 原视频在新画布中的位置
        pad_x = left_pad
        pad_y = top_pad
        
        # 添加 pad 滤镜（使用表达式动态计算）
        filters.append(f"pad={pad_w_expr}:{pad_h_expr}:{pad_x}:{pad_y}:black")
        
        # 调整 crop 坐标到新画布坐标系
        x = x + left_pad
        y = y + top_pad
        
        filters.append(f"crop={w}:{h}:{x}:{y}")


    # Resize
    if size:
        # 检查是否应用了 X/Y 缩放
        scale_applied = (scale_x is not None and abs(scale_x - 1.0) > 1e-9) or (scale_y is not None and abs(scale_y - 1.0) > 1e-9)
        if scale_applied:
            # 如果应用了缩放，直接拉伸到正方形（不保持宽高比）
            filters.append(f"scale={size}:{size}")
        else:
            # Scale while keeping aspect ratio
            # Pad to square with black borders
            scale_expr = f"if(gt(iw,ih),{size},-1):if(gt(iw,ih),-1,{size})".replace(",", r"\,") # 对逗号转义
            pad_expr = f"{size}:{size}:(ow-iw)/2:(oh-ih)/2:black"
            filters.append(f"scale={scale_expr},pad={pad_expr}")

    # 有些神秘视频像素宽高比居然不是1:1
    # 此处强制设置为1:1
    if size:
        filters.append("setsar=1")

    # Pad start
    if pad:
        filters.append(f"tpad=start_duration={pad}:color=black")

    return ",".join(filters) if filters else None


def _build_axis_rotation_perspective_filter(x_rot_deg: Optional[float],
                                            y_rot_deg: Optional[float],
                                            video_width: Optional[int],
                                            video_height: Optional[int]
                                           ) -> Optional[str]:
    """将 x/y 轴旋转角转换为 FFmpeg perspective 滤镜参数。"""

    x_rot_deg = float(x_rot_deg or 0.0)
    y_rot_deg = float(y_rot_deg or 0.0)

    if abs(x_rot_deg) < 1e-6 and abs(y_rot_deg) < 1e-6:
        return None

    if video_width is None or video_height is None:
        return None
    if video_width <= 1 or video_height <= 1:
        return None

    width = float(video_width)
    height = float(video_height)

    cx = (width - 1.0) / 2.0
    cy = (height - 1.0) / 2.0
    corners = [
        (-cx, -cy, 0.0),
        (cx, -cy, 0.0),
        (cx, cy, 0.0),
        (-cx, cy, 0.0),
    ]

    x_rad = math.radians(x_rot_deg)
    y_rad = math.radians(y_rot_deg)

    cos_x = math.cos(x_rad)
    sin_x = math.sin(x_rad)
    cos_y = math.cos(y_rad)
    sin_y = math.sin(y_rad)

    focal = max(width, height) * 1.2
    distance = max(width, height) * 1.5

    projected = []
    for x, y, z in corners:
        y1 = y * cos_x - z * sin_x
        z1 = y * sin_x + z * cos_x

        x2 = x * cos_y + z1 * sin_y
        y2 = y1
        z2 = -x * sin_y + z1 * cos_y

        z_cam = z2 + distance
        if abs(z_cam) < 1e-6:
            z_cam = 1e-6

        u = focal * x2 / z_cam + cx
        v = focal * y2 / z_cam + cy
        projected.append((u, v))

    min_x = min(p[0] for p in projected)
    max_x = max(p[0] for p in projected)
    min_y = min(p[1] for p in projected)
    max_y = max(p[1] for p in projected)

    span_x = max(max_x - min_x, 1e-6)
    span_y = max(max_y - min_y, 1e-6)

    dst = []
    for u, v in projected:
        out_x = (u - min_x) * (width - 1.0) / span_x
        out_y = (v - min_y) * (height - 1.0) / span_y
        dst.append((out_x, out_y))

    tl = dst[0]
    tr = dst[1]
    bl = dst[3]
    br = dst[2]

    # perspective 参数顺序为: tl, tr, bl, br
    return (
        "perspective="
        f"{tl[0]:.6f}:{tl[1]:.6f}:"
        f"{tr[0]:.6f}:{tr[1]:.6f}:"
        f"{bl[0]:.6f}:{bl[1]:.6f}:"
        f"{br[0]:.6f}:{br[1]:.6f}:sense=destination"
    )







def _build_audio_args(data: MediaModel) -> OpResult[list[str]]:
    """构建 FFmpeg 音频参数部分"""

    args = []

    # 有音频考虑 video mute
    if data.media_type == MediaType.VIDEO_WITH_AUDIO:
        if data.video_mute:
            args.extend(["-an"])  # 无音频输出
            return ok(args)
    
    # 没音频直接静音
    if data.media_type in [MediaType.VIDEO_WITHOUT_AUDIO]:
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
                              media_type=data.media_type,
                              mute=data.video_mute,
                              pad=data.pad_start,
                              start=data.start,
                              end=data.end)
    if af:
        args.extend(["-af", af])

    return ok(args)




def _build_audio_filters(volume: Optional[int],
                         media_type: MediaType,
                         mute: Optional[bool],
                         pad: Optional[float],
                         start: Optional[float],
                         end: Optional[float]
                        ) -> Optional[str]:
    """构建音频滤镜"""

    filters = []

    # trim (decode-time cut, not keyframe dependent)
    if start is not None or end is not None:
        atrim_kv = []
        if start is not None:
            atrim_kv.append(f"start={start}")
        if end is not None:
            atrim_kv.append(f"end={end}")
        filters.append(f"atrim={':'.join(atrim_kv)}")
        filters.append("asetpts=PTS-STARTPTS")

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
