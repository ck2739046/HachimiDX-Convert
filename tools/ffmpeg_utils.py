"""
FFmpeg 工具模块
提供统一的 FFmpeg/FFprobe 命令执行和媒体文件信息获取功能
"""
import os
import sys
import subprocess
import json
import traceback
import io
from typing import List, Dict, Any, Tuple, Optional

root = os.path.normpath(os.path.abspath(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root not in sys.path:
    sys.path.insert(0, root)
import tools.path_config
import tools.config_manager

# 解决 Windows 控制台 Unicode 编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')



def run_ffmpeg(args: List[str]) -> subprocess.CompletedProcess:
    """
    执行 FFmpeg 命令
    
    Args:
        args: FFmpeg 命令参数列表（不包含 ffmpeg 可执行文件路径） 
        
    Returns:
        subprocess.CompletedProcess 对象
    """
    ffmpeg_path = os.path.normpath(os.path.abspath(tools.path_config.ffmpeg_exe))
    cmd = [ffmpeg_path] + args

    print("Running FFmpeg command:", " ".join(cmd))
    
    result = subprocess.run(
        cmd,
        capture_output=False,
        text=True,
        encoding='utf-8'
    )
    
    return result


def run_ffprobe(args: List[str]) -> subprocess.CompletedProcess:
    """
    执行 FFprobe 命令
    
    Args:
        args: FFprobe 命令参数列表（不包含 ffprobe 可执行文件路径）
        
    Returns:
        subprocess.CompletedProcess 对象
        
    Example:
        result = run_ffprobe(['-v', 'error', '-show_format', '-of', 'json', 'input.mp4'])
    """
    ffprobe_path = os.path.normpath(os.path.abspath(tools.path_config.ffprobe_exe))
    cmd = [ffprobe_path] + args
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding='utf-8'
    )
    
    return result


def get_file_info(file_path: str) -> Tuple[str, List[Dict[str, Any]]]:
    """
    获取媒体文件详细信息
    
    Args:
        file_path: 文件路径
        
    Returns:
        (file_type, streams)
        file_type: "video" / "video_muted" / "audio" / "unknown"
        streams: 流信息字典列表
        
    Raises:
        FileNotFoundError: 文件不存在
        Exception: FFprobe 执行失败或 JSON 解析失败
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    args = [
        '-v', 'error',
        '-show_entries',
        'stream=index,codec_type,codec_name,width,height,avg_frame_rate,duration,bit_rate,nb_frames,sample_rate,channels,channel_layout',
        '-of', 'json',
        file_path
    ]
    
    result = run_ffprobe(args)
    
    if result.returncode != 0:
        raise Exception(f"FFprobe 执行失败: {result.stderr}")
    
    try:
        data = json.loads(result.stdout)
        streams = data.get('streams', [])
    except json.JSONDecodeError as e:
        raise Exception(f"JSON 解析失败: {e}")
    
    # 判断文件类型
    file_type = _determine_file_type(streams)
    
    return file_type, streams


def _determine_file_type(streams: List[Dict[str, Any]]) -> str:
    """
    根据流信息判断文件类型
    
    Args:
        streams: 流信息列表
        
    Returns:
        "video" / "video_muted" / "audio" / "unknown"
    """
    has_video = any(s.get('codec_type') == 'video' for s in streams)
    has_audio = any(s.get('codec_type') == 'audio' for s in streams)
    
    if has_video and has_audio:
        return "video"
    elif has_video and not has_audio:
        return "video_muted"
    elif not has_video and has_audio:
        return "audio"
    else:
        return "unknown"









# debug
# ========== 参数构建辅助函数 ==========

def _get_audio_codec(format_str: str) -> str:
    if format_str == 'mp3':
        return 'libmp3lame'
    elif format_str == 'ogg':
        return 'libvorbis'
    
    raise ValueError(f"Unsupported audio format: {format_str}. Only 'mp3' and 'ogg' are supported.")


def _get_audio_quality_args(format_str: str, audio_quality: int) -> List[str]:
    if audio_quality not in [0, 1, 2]:
        raise ValueError(f"Invalid quality: {audio_quality}. Must be 0, 1, or 2.")

    if format_str == 'mp3':
        # 0 -> vbr -q:a 0 (245)
        # 1 -> vbr -q:a 1 (225)
        # 2 -> vbr -q:a 2 (190)
        return ['-q:a', str(audio_quality)]
    elif format_str == 'ogg':
        # 0 -> vbr -q:a 8 (256)
        # 1 -> vbr -q:a 7 (224)
        # 2 -> vbr -q:a 6 (192)
        mapping = {0: '8', 1: '7', 2: '6'}
        return ['-q:a', mapping[audio_quality]]
    elif format_str == 'aac':
        # 0 -> cbr 224k
        # 1 -> cbr 192k
        # 2 -> cbr 160k
        mapping = {0: '224k', 1: '192k', 2: '160k'}
        return ['-b:a', mapping[audio_quality]]
    
    raise ValueError(f"Unsupported audio format for audio_quality args: {format_str}")


def _handle_audio_timing(start_time: float, end_time: float) -> Dict[str, Any]:
    result = {
        'need_trim_start': False,
        'trim_start_ms': 0.0,
        'need_start_padding': False,
        'padding_duration_ms': 0.0,
        'need_trim_end': False,
        'trim_end_ms': 0.0
    }
    
    if start_time > 0:
        result['need_trim_start'] = True
        result['trim_start_ms'] = start_time
    elif start_time < 0:
        result['need_start_padding'] = True
        result['padding_duration_ms'] = abs(start_time)

    if end_time > 0:
        result['need_trim_end'] = True
        result['trim_end_ms'] = end_time
    elif end_time < 0:
        raise ValueError("end_time cannot be negative")

    # start_time == 0 and end_time == 0 means no trimming or padding
        
    return result


def _construct_audio_filter_chain(volume: int, need_start_padding: bool, padding_duration_ms: float) -> Optional[str]:
    filters = []
    
    # Start padding (adelay)
    if need_start_padding:
        # adelay works in milliseconds. "delays | delays" for stereo.
        delay_val = f"{padding_duration_ms}"
        filters.append(f"adelay={delay_val}|{delay_val}")
        
    # Volume
    if volume < 0 or volume > 200:
        raise ValueError(f"Invalid volume: {volume}. Must be between 0 and 200.")
    if volume != 100:
        vol_val = volume / 100.0
        filters.append(f"volume={vol_val:.2f}")
        
    if not filters:
        return None
    
    return ",".join(filters)


def _get_h264_hw_accel_config() -> str:
    try:
        # call config manager
        hw_accel = tools.config_manager.get_config("ffmpeg_hw_acceleration_h264")
        if not hw_accel:
            raise ValueError("ffmpeg_hw_acceleration_h264 config not found")
        if hw_accel not in ['h264_cpu', 'h264_nvidia']:
            raise ValueError(f"Invalid hw_acceleration config: {hw_accel}, must be 'h264_cpu' or 'h264_nvidia'")
        
        return hw_accel
    except Exception as e:
        raise RuntimeError(f"Failed to get H264 HW acceleration config: {e}")


def _get_video_encoder_args(hw_accel: str, quality: int, fps: float, optimize_gop: bool, resolution: int) -> List[str]:
    args = ["-pix_fmt", "yuv420p"]
    
    # GOP optimization
    if optimize_gop:
        args.extend(["-g", str(int(fps))])
        
    # Frame rate
    args.extend(["-r", str(fps)])

    if hw_accel == 'h264_cpu':
        args.extend(["-c:v", "libx264"])
        args.extend(["-crf", str(quality)])
        
    elif hw_accel == 'h264_nvidia':
        # Dynamic bitrate calculation
        # Formula: resolution * resolution * fps * 0.3 (bits)
        # Example: 1080 * 1080 * 60 * 0.3 = ~21 Mbps
        bitrate_bits = resolution * resolution * fps * 0.3
        maxrate_mb = int(bitrate_bits / 1_000_000)
        bufsize_mb = maxrate_mb * 2
        
        args.extend(["-c:v", "h264_nvenc"])
        args.extend(["-rc", "vbr"])
        args.extend(["-cq", str(quality - 1)]) # User requested -1
        args.extend(["-b:v", "0"])
        args.extend(["-maxrate", f"{maxrate_mb}M"])
        args.extend(["-bufsize", f"{bufsize_mb}M"])
        
    else:
        raise ValueError(f"Unsupported hw_acceleration: {hw_accel}")
        
    return args


def _construct_video_filter_chain(resolution: int, need_start_padding: bool, padding_duration_ms: float, crop_params: Optional[Dict[str, int]] = None) -> str:
    filters = []
    
    # Crop (if provided)
    # crop_params: {'x': int, 'y': int, 'width': int, 'height': int}
    if crop_params:
        crop_w = crop_params['width']
        crop_h = crop_params['height']
        crop_x = crop_params['x']
        crop_y = crop_params['y']
        filters.append(f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y}")

    # Scale and Pad to square resolution
    # Scale: maintain aspect ratio, fit within resolution x resolution
    # Pad: center the result in resolution x resolution black box

    scale_expr = f"if(gt(iw,ih),{resolution},-1):if(gt(iw,ih),-1,{resolution})"
    pad_expr = f"{resolution}:{resolution}:(ow-iw)/2:(oh-ih)/2:black"
    
    filters.append(f"scale={scale_expr},pad={pad_expr}")
    
    # Start padding (tpad)
    if need_start_padding:
        filters.append(f"tpad=start_duration={padding_duration_ms}ms:color=black")
        
    return ",".join(filters)







# debug
# ========== 核心构建函数 ==========

def _construct_audio_args(params: Dict[str, Any]) -> List[str]:
    # Extract params
    input_file = params['input_file']
    output_file = params['output_file']
    fmt = params['format']
    sample_rate = params['sample_rate']
    audio_quality = params['audio_quality']
    volume = params['volume']
    clear_metadata = params['clear_metadata']
    start_time = params['start_time']
    end_time = params['end_time']
    
    if sample_rate not in [44100, 48000]:
        raise ValueError(f"Invalid sample_rate: {sample_rate}. Must be 44100 or 48000.")
    
    args = ["-y", "-hide_banner", "-stats", "-loglevel", "error"]
    
    timing = _handle_audio_timing(start_time, end_time)
    
    args.extend(["-i", input_file])
    
    # Input seeking (-ss)
    if timing['need_trim_start']:
        args.extend(["-ss", f"{timing['trim_start_ms']/1000.0}"])
        
    # Output seeking (-to)
    if timing['need_trim_end']:
        args.extend(["-to", f"{timing['trim_end_ms']/1000.0}"])
        
    # Codec
    args.extend(["-c:a", _get_audio_codec(fmt)])
    
    # Audio Quality
    args.extend(_get_audio_quality_args(fmt, audio_quality))
    
    # Sample rate
    args.extend(["-ar", str(sample_rate)])
    
    # Channels (Force Stereo)
    args.extend(["-ac", "2"])
    
    # Filters
    filter_chain = _construct_audio_filter_chain(volume, timing['need_start_padding'], timing['padding_duration_ms'])
    if filter_chain:
        args.extend(["-af", filter_chain])
        
    # Metadata
    if clear_metadata:
        args.extend(["-map_metadata", "-1"])
        
    # Output
    args.append(output_file)
    
    return args



def _construct_video_args(params: Dict[str, Any]) -> List[str]:
    # Extract params
    input_file = params['input_file']
    output_file = params['output_file']
    start_time = params['start_time']
    end_time = params['end_time']
    clear_metadata = params['clear_metadata']
    video_quality = params['video_quality']
    fps = params['fps']
    optimize_gop = params['optimize_GOP']
    resolution = params['resolution']
    crop_params = params.get('crop') # Optional: {'x': int, 'y': int, 'width': int, 'height': int}

    # Audio-specific params
    sample_rate = params['sample_rate']
    audio_quality = params['audio_quality']
    volume = params['volume']

    if sample_rate not in [44100, 48000]:
        raise ValueError(f"Invalid sample_rate: {sample_rate}. Must be 44100 or 48000.")

    # Get HW acceleration config
    hw_accel = _get_h264_hw_accel_config()

    args = ["-y", "-hide_banner", "-stats", "-loglevel", "error"]

    timing = _handle_audio_timing(start_time, end_time)

    args.extend(["-i", input_file])

    # Input seeking (-ss)
    if timing['need_trim_start']:
        args.extend(["-ss", f"{timing['trim_start_ms']/1000.0}"])

    # Output seeking (-to)
    if timing['need_trim_end']:
        args.extend(["-to", f"{timing['trim_end_ms']/1000.0}"])

    # Video Filters (crop + scale/pad + optional tpad)
    filter_chain = _construct_video_filter_chain(resolution, timing['need_start_padding'], timing['padding_duration_ms'], crop_params)
    args.extend(["-vf", filter_chain])

    # Audio: force AAC, sample rate, stereo, quality (bitrate)
    args.extend(["-c:a", "aac"])
    args.extend(_get_audio_quality_args('aac', audio_quality))
    args.extend(["-ar", str(sample_rate)])
    args.extend(["-ac", "2"])

    # Audio filters (volume / adelay / aresample)
    audio_filters = []
    
    # Volume / Adelay
    base_audio_filter = _construct_audio_filter_chain(volume, timing['need_start_padding'], timing['padding_duration_ms'])
    if base_audio_filter:
        audio_filters.append(base_audio_filter)
        
    # Force async resample
    audio_filters.append("aresample=async=1")
    
    args.extend(["-af", ",".join(audio_filters)])

    # Video encoder args
    encoder_args = _get_video_encoder_args(hw_accel, video_quality, fps, optimize_gop, resolution)
    args.extend(encoder_args)

    # Metadata
    if clear_metadata:
        args.extend(["-map_metadata", "-1"])

    # Output
    args.append(output_file)

    return args



def _construct_video_muted_args(params: Dict[str, Any]) -> List[str]:
    # Extract params
    input_file = params['input_file']
    output_file = params['output_file']
    start_time = params['start_time']
    end_time = params['end_time']
    clear_metadata = params['clear_metadata']
    video_quality = params['video_quality']
    fps = params['fps']
    optimize_gop = params['optimize_GOP']
    resolution = params['resolution']
    crop_params = params.get('crop') # Optional: {'x': int, 'y': int, 'width': int, 'height': int}
    
    # Get HW acceleration config
    hw_accel = _get_h264_hw_accel_config()
    
    args = ["-y", "-hide_banner", "-stats", "-loglevel", "error"]
    
    timing = _handle_audio_timing(start_time, end_time)
    
    args.extend(["-i", input_file])

    # Input seeking (-ss)
    if timing['need_trim_start']:
        args.extend(["-ss", f"{timing['trim_start_ms']/1000.0}"])
    
    # Output seeking (-to)
    if timing['need_trim_end']:
        args.extend(["-to", f"{timing['trim_end_ms']/1000.0}"])
        
    # Mute audio
    args.append("-an")
    
    # Filters (Crop, Scale, Pad, Tpad)
    filter_chain = _construct_video_filter_chain(resolution, timing['need_start_padding'], timing['padding_duration_ms'], crop_params)
    args.extend(["-vf", filter_chain])
    
    # Video Encoder Args
    encoder_args = _get_video_encoder_args(hw_accel, video_quality, fps, optimize_gop, resolution)
    args.extend(encoder_args)
    
    # Metadata
    if clear_metadata:
        args.extend(["-map_metadata", "-1"])
        
    # Output
    args.append(output_file)
    
    return args






# debug
# ========== 统一入口 ==========


def _handle_json(json_path: str):
    try:
        if not os.path.exists(json_path):
            print(f"Error: JSON file does not exist: {json_path}")
            sys.exit(1)
            
        with open(json_path, 'r', encoding='utf-8') as f:
            params = json.load(f)
            
        try:
            os.remove(json_path)
        except:
            pass

        construct_args_and_run_ffmpeg(params)
    
    except Exception:
        traceback.print_exc()
        sys.exit(1)


def construct_args_and_run_ffmpeg(params: Dict[str, Any]):
    try:
        media_type = params.get('type')
        
        if media_type == 'audio':
            args = _construct_audio_args(params)
        elif media_type == 'video':
            args = _construct_video_args(params)
        elif media_type == 'video_muted':
            args = _construct_video_muted_args(params)
        else:
            print(f"Error: Unknown media type: {media_type}")
            sys.exit(1)

        # 等参数构建完成后，检查如果output_file存在，删除
        output_file = params.get('output_file')
        if os.path.exists(output_file):
            os.remove(output_file)
            print(f"Existing output file removed: {output_file}")
            
        result = run_ffmpeg(args)
        
        if result.returncode != 0:
            print(result.stderr)
            sys.exit(1)
            
    except Exception:
        traceback.print_exc()
        sys.exit(1)




if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Error: No JSON file provided")
        sys.exit(1)
    
    _handle_json(sys.argv[1])
