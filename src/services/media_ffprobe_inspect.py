"""Single-file media inspection using ffprobe.

Public API:
- inspect_media(input_path) -> FFprobeInspectResult

Notes:
- Uses subprocess.run (not QProcess).
- Parses ffprobe JSON output.
- If multiple video/audio streams exist, selects the FIRST of each.
- Does not parse rationals; stream dicts are returned as-is.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Union

from .path_manage import PathManage
from .task_contract import MediaType


_STREAM_ENTRIES = (
    "stream=index,codec_type,codec_name,width,height,avg_frame_rate, \
     duration,bit_rate,nb_frames,sample_rate,channels,channel_layout"
)


@dataclass(slots=True)
class FFprobeInspectResult:
    ok: bool
    media_type: MediaType
    video_stream: Dict[str, Any]
    audio_stream: Dict[str, Any]
    duration: str
    error_msg: str
    raw: Dict[str, Any]


def inspect_media(input_path: Union[str, Path]) -> FFprobeInspectResult:
    """Inspect one media file using ffprobe.

    Args:
        input_path: Path to a single media file.

    Returns:
        FFprobeInspectResult
    """
    file_path = os.path.normpath(os.path.abspath(str(input_path)))

    if not os.path.exists(file_path):
        return FFprobeInspectResult(
            ok=False,
            media_type=MediaType.UNKNOWN,
            video_stream={},
            audio_stream={},
            duration="",
            error_msg=f"File not found: {file_path}",
            raw={},
        )

    ffprobe_exe = str(PathManage.FFPROBE_EXE_PATH)
    if not os.path.isfile(ffprobe_exe):
        return FFprobeInspectResult(
            ok=False,
            media_type=MediaType.UNKNOWN,
            video_stream={},
            audio_stream={},
            duration="",
            error_msg=f"ffprobe not found: {ffprobe_exe}",
            raw={},
        )

    args = [
        "-v",
        "error",
        "-show_entries",
        _STREAM_ENTRIES,
        "-of",
        "json",
        file_path,
    ]

    try:
        result = subprocess.run(
            [ffprobe_exe] + args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except Exception as e:
        return FFprobeInspectResult(
            ok=False,
            media_type=MediaType.UNKNOWN,
            video_stream={},
            audio_stream={},
            duration="",
            error_msg=f"ffprobe launch failed: {e}",
            raw={},
        )

    if result.returncode != 0:
        err = (result.stderr or "").strip()
        msg = f"ffprobe failed: {err}" if err else f"ffprobe failed: exit_code={result.returncode}"
        return FFprobeInspectResult(
            ok=False,
            media_type=MediaType.UNKNOWN,
            video_stream={},
            audio_stream={},
            duration="",
            error_msg=msg,
            raw={},
        )

    try:
        raw = json.loads(result.stdout)
    except Exception as e:
        return FFprobeInspectResult(
            ok=False,
            media_type=MediaType.UNKNOWN,
            video_stream={},
            audio_stream={},
            duration="",
            error_msg=f"ffprobe JSON parse failed: {e}",
            raw={},
        )

    streams = raw.get("streams", [])
    if not isinstance(streams, list):
        return FFprobeInspectResult(
            ok=False,
            media_type=MediaType.UNKNOWN,
            video_stream={},
            audio_stream={},
            duration="",
            error_msg="ffprobe JSON missing 'streams' list",
            raw={},
        )

    video_stream = _first_stream_of_type(streams, "video") or {}
    audio_stream = _first_stream_of_type(streams, "audio") or {}

    has_video = bool(video_stream)
    has_audio = bool(audio_stream)

    if has_video and has_audio:
        media_type = MediaType.VIDEO_WITH_AUDIO
    elif has_video and not has_audio:
        media_type = MediaType.VIDEO_WITHOUT_AUDIO
    elif not has_video and has_audio:
        media_type = MediaType.AUDIO
    else:
        media_type = MediaType.UNKNOWN

    duration = _pick_duration(video_stream, audio_stream)

    return FFprobeInspectResult(
        ok=True,
        media_type=media_type,
        video_stream=video_stream,
        audio_stream=audio_stream,
        duration=duration,
        error_msg="",
        raw=raw,
    )


def _first_stream_of_type(streams: list[dict], codec_type: str) -> Optional[dict]:
    for s in streams:
        if isinstance(s, dict) and s.get("codec_type") == codec_type:
            return s
    return None


def _pick_duration(video_stream: Dict[str, Any], audio_stream: Dict[str, Any]) -> str:
    # Prefer video duration, fallback to audio.
    v = video_stream.get("duration")
    if isinstance(v, str) and v.strip():
        return v.strip()
    a = audio_stream.get("duration")
    if isinstance(a, str) and a.strip():
        return a.strip()
    return ""


@staticmethod
def print_ffprobe_result(result):
    """
    格式化打印FFprobeInspectResult数据
    Args: FFprobeInspectResult对象
    """

    if not result.ok:
        print("❌ FFprobe检查失败:")
        print(f"   错误信息: {result.error_msg}")
        return
    
    print("✅ FFprobe检查结果:")
    print(f"   媒体类型: {result.media_type.value}")
    print(f"   总时长: {result.duration}秒")
    
    # 视频流信息
    if result.video_stream:
        print("\n视频流信息:")
        video = result.video_stream
        print(f"   索引: {video.get('index', 'N/A')}")
        print(f"   编码: {video.get('codec_name', 'N/A')}")
        print(f"   分辨率: {video.get('width', 'N/A')}x{video.get('height', 'N/A')}")
        print(f"   帧率: {video.get('avg_frame_rate', 'N/A')}")
        print(f"   时长: {video.get('duration', 'N/A')}秒")
        print(f"   比特率: {video.get('bit_rate', 'N/A')} bps")
        print(f"   总帧数: {video.get('nb_frames', 'N/A')}")
    
    # 音频流信息
    if result.audio_stream:
        print("\n音频流信息:")
        audio = result.audio_stream
        print(f"   索引: {audio.get('index', 'N/A')}")
        print(f"   编码: {audio.get('codec_name', 'N/A')}")
        print(f"   采样率: {audio.get('sample_rate', 'N/A')} Hz")
        print(f"   声道: {audio.get('channels', 'N/A')}")
        print(f"   声道布局: {audio.get('channel_layout', 'N/A')}")
        print(f"   时长: {audio.get('duration', 'N/A')}秒")
        print(f"   比特率: {audio.get('bit_rate', 'N/A')} bps")
        print(f"   总帧数: {audio.get('nb_frames', 'N/A')}")
    
    # 原始数据信息
    print(f"\n原始数据包含:")
    if 'streams' in result.raw:
        print(f"   流数量: {len(result.raw.get('streams', []))}")
    if 'programs' in result.raw:
        print(f"   节目数量: {len(result.raw.get('programs', []))}")
    if 'stream_groups' in result.raw:
        print(f"   流组数量: {len(result.raw.get('stream_groups', []))}")
