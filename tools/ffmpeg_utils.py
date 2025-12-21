"""
FFmpeg 工具模块
提供统一的 FFmpeg/FFprobe 命令执行和媒体文件信息获取功能
"""
import os
import sys
import subprocess
import json
import traceback
from typing import List, Dict, Any, Tuple, Optional

root = os.path.normpath(os.path.abspath(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root not in sys.path:
    sys.path.insert(0, root)
import tools.path_config


def run_ffmpeg(args: List[str]) -> subprocess.CompletedProcess:
    """
    执行 FFmpeg 命令
    
    Args:
        args: FFmpeg 命令参数列表（不包含 ffmpeg 可执行文件路径） 
        
    Returns:
        subprocess.CompletedProcess 对象
        
    Example:
        result = run_ffmpeg(['-i', 'input.mp4', '-c:v', 'copy', 'output.mp4'])
    """
    ffmpeg_path = os.path.normpath(os.path.abspath(tools.path_config.ffmpeg_exe))
    cmd = [ffmpeg_path] + args
    
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
        
    return result


def _construct_audio_filter_chain(volume: int, need_start_padding: bool, padding_duration_ms: float) -> Optional[str]:
    filters = []
    
    # Start padding (adelay)
    if need_start_padding:
        # adelay works in milliseconds. "delays | delays" for stereo.
        delay_val = f"{padding_duration_ms}"
        filters.append(f"adelay={delay_val}|{delay_val}")
        
    # Volume
    if volume != 100:
        vol_val = volume / 100.0
        filters.append(f"volume={vol_val:.2f}")
        
    if not filters:
        return None
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
    # TODO: Implement video args construction
    return []

def _construct_video_muted_args(params: Dict[str, Any]) -> List[str]:
    # TODO: Implement muted video args construction
    return []



# debug
# ========== 统一入口 ==========

def construct_args_and_run_ffmpeg(json_path: str):
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
    
    construct_args_and_run_ffmpeg(sys.argv[1])
