"""
FFmpeg 工具模块
提供统一的 FFmpeg/FFprobe 命令执行和媒体文件信息获取功能
"""
import os
import sys
import subprocess
import json
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
