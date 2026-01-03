"""Media task launcher: start FFmpeg via QProcess.

This module is designed to work in two modes:
- TaskScheduler mode: scheduler passes in its managed QProcess.
- Standalone mode: caller creates its own QProcess (allowing parallel runs).

Rules implemented (per requirements):
- Output channel is merged (stdout/stderr), so QProcess uses MergedChannels.
- Two arg builders:
  - Audio builder
  - Video builder (shared for video_with_audio and video_without_audio)
- Audio always forces stereo: -ac 2
- video_without_audio always uses -an
- video_with_audio with mute=True is treated as video_without_audio (-an)
- Video always uses: -pix_fmt yuv420p and libx264
- If resolution/fps is "origin", do not add related args
- Common pad/trim follow legacy patterns:
  - trim_start_sec -> -ss
  - trim_end_sec (resolved) -> -to
  - pad_start_sec -> audio: adelay, video: tpad start_duration
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from PyQt6.QtCore import QProcess

from .path_manage import PathManage
import i18n
from .pydantic_models.run_ffmpeg_models import (
    RunFfmpegAudio,
    RunFfmpegBase,
    RunFfmpegVideoWithAudio,
    RunFfmpegVideoWithoutAudio,
)


def start_ffmpeg_for_media_task(process: QProcess, config: Any) -> tuple[bool, str]:
    """Start FFmpeg for a media task.

    Args:
        process: The QProcess to use (can be scheduler-owned or caller-owned).
        config: One of the run_ffmpeg_* pydantic models.

    Returns:
        (ok, message)
    """
    if not isinstance(
        config,
        (RunFfmpegAudio, RunFfmpegVideoWithAudio, RunFfmpegVideoWithoutAudio),
    ):
        return False, i18n.t("media_task_launcher.error_unsupported_config")

    ffmpeg_exe = str(PathManage.FFMPEG_EXE_PATH)
    if not os.path.isfile(ffmpeg_exe):
        return False, i18n.t("media_task_launcher.error_ffmpeg_not_found", path=ffmpeg_exe)

    # Always merged output.
    process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)

    try:
        input_path = str(Path(config.input_path))
        output_path = str(Path(config.output_path))
    except Exception as e:
        return False, i18n.t("media_task_launcher.error_invalid_io_path", error=str(e))

    # Ensure output dir exists.
    try:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return False, i18n.t("media_task_launcher.error_failed_create_output_dir", error=str(e))

    # Remove existing output file if exists.
    try:
        if os.path.exists(output_path):
            os.remove(output_path)
    except Exception as e:
        return False, i18n.t("media_task_launcher.error_failed_remove_existing_output", error=str(e))

    try:
        args = _build_common_base_args(input_path)
        _apply_common_timing_args(args, config)

        if isinstance(config, RunFfmpegAudio):
            _apply_audio_args(args, config)
        else:
            _apply_video_args(args, config)

        if config.clear_metadata:
            args.extend(["-map_metadata", "-1"])

        args.append(output_path)

    except Exception as e:
        return False, i18n.t("media_task_launcher.error_invalid_media_config", error=str(e))

    process.setProgram(ffmpeg_exe)
    process.setArguments(args)
    process.start()

    full_command = f'"{ffmpeg_exe}" ' + " ".join(f'"{arg}"' for arg in args)
    return True, i18n.t("media_task_launcher.notice_ffmpeg_started", command=full_command)


# ===== Common =====

def _build_common_base_args(input_path: str) -> list[str]:
    return [
        "-y",
        "-hide_banner",
        "-stats",
        "-loglevel",
        "error",
        "-i",
        input_path,
    ]


def _apply_common_timing_args(args: list[str], cfg: RunFfmpegBase) -> None:
    # Trim start/end (legacy style: after -i)
    if cfg.trim_start_sec is not None:
        args.extend(["-ss", f"{float(cfg.trim_start_sec)}"])

    to_sec = cfg.resolved_trim_end_sec()
    if to_sec is not None:
        args.extend(["-to", f"{float(to_sec)}"])


def _get_volume_filter(volume_percent: int) -> Optional[str]:
    if int(volume_percent) == 100:
        return None
    return f"volume={int(volume_percent) / 100.0:.2f}"


def _build_audio_filters(*, volume: int, pad_start_sec: Optional[float]) -> Optional[str]:
    filters: list[str] = []

    # Start padding: adelay in ms. "delays|delays" for stereo.
    if pad_start_sec is not None and float(pad_start_sec) > 0:
        delay_ms = int(round(float(pad_start_sec) * 1000.0))
        filters.append(f"adelay={delay_ms}|{delay_ms}")

    vol = _get_volume_filter(int(volume))
    if vol:
        filters.append(vol)

    if not filters:
        return None
    return ",".join(filters)


def _build_video_filters(
    *,
    resolution: str,
    crop: Optional[str],
    pad_start_sec: Optional[float],
) -> Optional[str]:
    filters: list[str] = []

    # Crop first (if any): expects "w:h:x:y"
    if crop:
        filters.append(f"crop={crop}")

    if resolution != "origin":
        # Scale while keeping aspect ratio, then pad to square with black borders.
        # Reference:
        #   scale_expr = if(gt(iw,ih),R,-1):if(gt(iw,ih),-1,R)
        #   pad_expr   = R:R:(ow-iw)/2:(oh-ih)/2:black
        size_str = resolution.split("x", 1)[0]
        size = int(size_str)
        scale_expr = f"if(gt(iw,ih),{size},-1):if(gt(iw,ih),-1,{size})".replace(",", r"\,") # 对逗号转义
        pad_expr = f"{size}:{size}:(ow-iw)/2:(oh-ih)/2:black"
        filters.append(f"scale={scale_expr},pad={pad_expr}")

    if pad_start_sec is not None and float(pad_start_sec) > 0:
        filters.append(f"tpad=start_duration={float(pad_start_sec)}:color=black")

    if not filters:
        return None
    return ",".join(filters)








# ===== Audio =====

def _apply_audio_args(args: list[str], cfg: RunFfmpegAudio) -> None:
    # codec
    if cfg.format == "mp3":
        args.extend(["-c:a", "libmp3lame"])
        q = _map_mp3_vbr_to_q(cfg.bitrate)
        args.extend(["-q:a", str(q)])
    elif cfg.format == "ogg":
        args.extend(["-c:a", "libvorbis"])
        q = _map_ogg_vbr_to_q(cfg.bitrate)
        args.extend(["-q:a", str(q)])
    else:
        raise ValueError(f"unsupported audio format: {cfg.format}")

    args.extend(["-ar", str(cfg.sample_rate)])

    # Always force stereo
    args.extend(["-ac", "2"])

    af = _build_audio_filters(volume=int(cfg.volume), pad_start_sec=cfg.pad_start_sec)
    if af:
        args.extend(["-af", af])


def _map_ogg_vbr_to_q(bitrate_label: Optional[str]) -> int:
    mapping = {
        "vbr 8 (256k)": 8,
        "vbr 7 (224k)": 7,
        "vbr 6 (191k)": 6,
    }
    if bitrate_label is None:
        return 7
    if bitrate_label not in mapping:
        raise ValueError(f"invalid ogg bitrate: {bitrate_label}")
    return mapping[bitrate_label]


def _map_mp3_vbr_to_q(bitrate_label: Optional[str]) -> int:
    mapping = {
        "vbr 0 (245k)": 0,
        "vbr 1 (225k)": 1,
        "vbr 2 (190k)": 2,
    }
    if bitrate_label is None:
        return 1
    if bitrate_label not in mapping:
        raise ValueError(f"invalid mp3 bitrate: {bitrate_label}")
    return mapping[bitrate_label]








# ===== Video (shared) =====

def _apply_video_args(args: list[str], cfg: RunFfmpegVideoWithAudio | RunFfmpegVideoWithoutAudio) -> None:
    treat_as_muted = isinstance(cfg, RunFfmpegVideoWithoutAudio) or (
        isinstance(cfg, RunFfmpegVideoWithAudio) and bool(cfg.mute)
    )

    vf = _build_video_filters(
        resolution=str(cfg.resolution),
        crop=getattr(cfg, "crop", None),
        pad_start_sec=cfg.pad_start_sec,
    )
    if vf:
        args.extend(["-vf", vf])

    # Video encoder (fixed)
    args.extend(["-pix_fmt", "yuv420p"])
    args.extend(["-c:v", "libx264"])
    args.extend(["-crf", str(int(cfg.crf))])

    if str(cfg.fps) != "origin":
        args.extend(["-r", str(cfg.fps)])

    if bool(cfg.gop_optimize):
        args.extend(["-g", "30"])

    if treat_as_muted:
        args.append("-an")
        return

    # Audio for video_with_audio
    if not isinstance(cfg, RunFfmpegVideoWithAudio):
        # Should not happen due to treat_as_muted logic.
        args.append("-an")
        return

    args.extend(["-c:a", "aac"])
    args.extend(["-b:a", _map_aac_bitrate(cfg.audio_bitrate)])
    args.extend(["-ar", str(cfg.audio_sample_rate)])

    af = _build_audio_filters(volume=int(cfg.volume), pad_start_sec=cfg.pad_start_sec)

    # Keep A/V stable on some inputs (legacy behavior)
    if af:
        af = af + ",aresample=async=1"
    else:
        af = "aresample=async=1"

    args.extend(["-af", af])


def _map_aac_bitrate(label: Optional[str]) -> str:
    mapping = {
        "cbr 224k": "224k",
        "cbr 192k": "192k",
        "cbr 160k": "160k",
    }
    if label is None:
        return "192k"
    if label not in mapping:
        raise ValueError(f"invalid aac bitrate: {label}")
    return mapping[label]
