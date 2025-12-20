import os
import sys
import subprocess
import json
from typing import Tuple, Dict, Any, Optional
import cv2
import io
import tkinter as tk
from tkinter import messagebox

root = os.path.normpath(os.path.abspath(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root not in sys.path:
    sys.path.insert(0, root)
import tools.path_config
import tools.ffmpeg_utils as ffmpeg_utils


# 解决 Windows 控制台 Unicode 编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def detect_video_params(input_file: str) -> Optional[Dict[str, Any]]:
    """
    使用 ffprobe 检测视频参数
    
    Args:
        input_file: 输入文件路径
        
    Returns:
        视频参数字典，如果不是视频则返回 None
    """
    try:
        file_type, streams = ffmpeg_utils.get_file_info(input_file)
        
        if file_type not in ['video', 'video_muted']:
            return None
        
        # 查找视频流
        video_stream = next((s for s in streams if s.get('codec_type') == 'video'), None)
        if not video_stream:
            return None
        
        # 解析 FPS
        fps_str = video_stream.get('avg_frame_rate', '0/0')
        if '/' in fps_str:
            num, den = map(int, fps_str.split('/'))
            fps = num / den if den != 0 else 0
        else:
            fps = float(fps_str)
        
        if fps <= 0:
            raise Exception("Cannot determine FPS of the video")
        
        duration = float(video_stream.get('duration', 0))
        width = int(video_stream.get('width', 0))
        height = int(video_stream.get('height', 0))
        
        if width > 0 and height > 0:
            return {
                'width': width,
                'height': height,
                'fps': fps,
                'duration': duration
            }
    except Exception:
        pass
    
    return None


def detect_audio_params(input_file: str) -> Optional[Dict[str, Any]]:
    """
    使用 ffprobe 检测音频参数
    
    Args:
        input_file: 输入文件路径
        
    Returns:
        音频参数字典，如果没有音频则返回 None
    """
    try:
        file_type, streams = ffmpeg_utils.get_file_info(input_file)
        
        # 查找音频流
        audio_stream = next((s for s in streams if s.get('codec_type') == 'audio'), None)
        if not audio_stream:
            return None
        
        channel_layout = audio_stream.get('channel_layout', '')
        if not channel_layout:
            channels = audio_stream.get('channels', 2)
            channel_layout = 'mono' if channels == 1 else 'stereo'
        
        return {
            'sample_rate': int(audio_stream.get('sample_rate', 44100)),
            'channels': channel_layout,
            'duration': float(audio_stream.get('duration', 0))
        }
    except Exception:
        return None


def detect_media_info(input_file: str) -> Tuple[str, Dict[str, Any]]:
    """
    检测媒体文件类型和参数
    
    Args:
        input_file: 输入文件路径
        
    Returns:
        (file_type, params)
        file_type: 'audio' 或 'video'
        params: 参数字典
    """
    try:
        # 尝试检测视频
        video_params = detect_video_params(input_file)
        if video_params:
            # 是视频文件，补充音频信息
            audio_params = detect_audio_params(input_file)
            if audio_params:
                video_params['has_audio'] = True
                video_params['sample_rate'] = audio_params['sample_rate']
                video_params['channels'] = audio_params['channels']
            else:
                video_params['has_audio'] = False
            
            return 'video', video_params
        
        # 不是视频，检测音频
        audio_params = detect_audio_params(input_file)
        if audio_params:
            return 'audio', audio_params
        
        raise Exception("Unsupported file type: no audio or video streams found")
            
    except Exception as e:
        raise Exception(f"Error detecting media info: {e}")


def generate_output_path(input_file: str, offset_ms: float) -> str:
    """
    生成输出文件路径
    
    Args:
        input_file: 输入文件路径
        offset_ms: 偏移量（毫秒）
        
    Returns:
        输出文件路径
    """
    try:
        dir_name = os.path.dirname(input_file)
        base_name = os.path.basename(input_file)
        name, ext = os.path.splitext(base_name)
        
        # 生成后缀
        if offset_ms >= 0:
            suffix = f"_trim_{offset_ms:.3f}ms"
        else:
            suffix = f"_pad_{abs(offset_ms):.3f}ms"
        
        output_file = os.path.join(dir_name, f"{name}{suffix}{ext}")
        
        # 如果文件已存在，添加数字后缀
        counter = 1
        while os.path.exists(output_file):
            output_file = os.path.join(dir_name, f"{name}{suffix}_{counter}{ext}")
            counter += 1

        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        return output_file
        
    except Exception as e:
        raise Exception(f"Error generating output path: {e}")


def build_trim_command(file_type: str, params: Dict[str, Any], offset_ms: float, 
                       input_file: str, output_file: str) -> list:
    """
    构建 FFmpeg 修剪命令参数
    
    Args:
        file_type: 文件类型 ('audio' 或 'video')
        params: 媒体参数字典
        offset_ms: 偏移量（毫秒）
        input_file: 输入文件路径
        output_file: 输出文件路径
        
    Returns:
        FFmpeg 命令参数列表（不包含 ffmpeg 可执行文件路径）
    """
    cmd = ['-y', '-hide_banner', '-stats', '-loglevel', 'error']
    
    if offset_ms >= 0:
        # 正偏移：裁剪开头
        cmd.extend(['-ss', f'{offset_ms}ms'])
        cmd.extend(['-i', input_file])
    else:
        # 负偏移：添加静音/黑屏
        abs_offset = abs(offset_ms)
        duration_sec = abs_offset / 1000.0
        
        if file_type == 'audio':
            # 音频填充
            cmd.extend(['-f', 'lavfi', '-i', f'anullsrc=r={params["sample_rate"]}:cl={params["channels"]}:d={duration_sec}'])
            cmd.extend(['-i', input_file])
            cmd.extend(['-filter_complex', '[0:a][1:a]concat=n=2:v=0:a=1[a]'])
            cmd.extend(['-map', '[a]'])
            cmd.extend(['-c:a', 'libmp3lame', '-b:a', '192k'])
        else:
            # 视频填充
            if params['has_audio']:
                # 视频 + 音频
                cmd.extend(['-f', 'lavfi', '-i', f'color=black:s={params["width"]}x{params["height"]}:r={params["fps"]}:d={duration_sec}'])
                cmd.extend(['-f', 'lavfi', '-i', f'anullsrc=r={params["sample_rate"]}:cl={params["channels"]}:d={duration_sec}'])
                cmd.extend(['-i', input_file])
                cmd.extend(['-filter_complex', '[0:v][2:v]concat=n=2:v=1:a=0[v];[1:a][2:a]concat=n=2:v=0:a=1[a]'])
                cmd.extend(['-map', '[v]', '-map', '[a]'])
                cmd.extend(['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23', '-pix_fmt', 'yuv420p'])
                cmd.extend(['-af', 'aresample=async=1']) # 确保音视频同步
                cmd.extend(['-c:a', 'aac', '-b:a', '192k'])
            else:
                # 仅视频
                cmd.extend(['-f', 'lavfi', '-i', f'color=black:s={params["width"]}x{params["height"]}:r={params["fps"]}:d={duration_sec}'])
                cmd.extend(['-i', input_file])
                cmd.extend(['-filter_complex', '[0:v][1:v]concat=n=2:v=1:a=0[v]'])
                cmd.extend(['-map', '[v]'])
                cmd.extend(['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23', '-pix_fmt', 'yuv420p'])
    
    cmd.append(output_file)
    return cmd


def trim_media(input_file: str, offset_ms: float, output_file: str = None) -> str:
    """
    修剪媒体文件
    
    Args:
        input_file: 输入文件路径
        offset_ms: 偏移量（毫秒），正数裁剪开头，负数添加静音/黑屏
        output_file: 输出文件路径（可选）
        
    Returns:
        输出文件路径
    """
    try:
        if not os.path.exists(input_file):
            raise Exception(f"Input file not found: {input_file}")
        
        # 检测文件类型和参数
        file_type, params = detect_media_info(input_file)
        print(f"Detected {file_type} file: {input_file}")
        
        # 设置输出路径
        if output_file is None:
            output_file = generate_output_path(input_file, offset_ms)
        
        # 构建并执行命令
        action = "Trimming" if offset_ms >= 0 else "Adding padding to"
        print(f"{action} {file_type}: {abs(offset_ms)}ms")
        
        # 显示确认弹窗
        root = tk.Tk()
        root.withdraw()  # 隐藏主窗口
        
        # 根据文件类型和偏移量生成确认消息
        if file_type == 'video':
            if offset_ms >= 0:
                message = f"确认裁剪视频开头 {abs(offset_ms):.2f} ms ?"
            else:
                message = f"确认为视频开头添加 {abs(offset_ms):.2f} ms 黑屏片段？"
        else:
            if offset_ms >= 0:
                message = f"确认裁剪音频开头 {abs(offset_ms):.2f} ms ?"
            else:
                message = f"确认为音频开头添加 {abs(offset_ms):.2f} ms 静音片段？"
        
        # 显示确认对话框
        confirmed = messagebox.askyesno("确认操作", message)
        root.destroy()
        
        if not confirmed:
            print("已取消")
            return
        
        cmd = build_trim_command(file_type, params, offset_ms, input_file, output_file)
        print(f"Using FFmpeg command: ffmpeg {' '.join(cmd)}")
        
        # 执行命令
        result = ffmpeg_utils.run_ffmpeg(cmd)
        if result.returncode != 0:
            raise Exception(f"FFmpeg processing failed with return code {result.returncode}")
        
        print(f"Trim completed successfully: {output_file}")
        return
        
    except Exception as e:
        raise Exception(f"Error in trim_media: {e}")


def main():
    """主函数，用于命令行调用"""
    try:
        if len(sys.argv) < 3:
            print("Usage: python trim.py <input_file> <offset_ms> [output_file]")
            print("  offset_ms: 偏移量（毫秒），正数裁剪开头，负数添加静音/黑屏")
            print("  Examples:")
            print("    python trim.py input.mp4 -3000         # 在开头添加3秒静音/黑屏")
            print("    python trim.py input.mp3 123.45        # 裁剪掉前123.45毫秒")
            sys.exit(1)
        
        input_file = sys.argv[1]
        offset_ms = float(sys.argv[2])
        output_file = sys.argv[3] if len(sys.argv) > 3 else None
        
        trim_media(input_file, offset_ms, output_file)
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
