"""Media task launcher: start FFmpeg via QProcess.

This module is designed to work in two modes:
- TaskScheduler mode: scheduler passes in its managed QProcess.
- Standalone mode: caller creates its own QProcess (allowing parallel runs).

IMPORTANT CONTRACT (no defensive programming by design)
=====================================================
This launcher assumes the caller has already validated and normalized the
config using the pydantic models in src.services.pydantic_models.run_ffmpeg_models.
In particular:
- Field names and semantics follow run_ffmpeg_models strictly (no legacy fields).
- Timing fields are already normalized: 0 -> None, max 3 decimals.
- If end_sec was provided, it has already been resolved to a positive timestamp
    by the model validator, so this launcher does NOT need input_duration_sec.
- pad_start_sec and start_sec are mutually exclusive (not both set).
- Optional bitrate fields have already been filled with defaults by validators.

Output overwrite behavior
------------------------
This launcher ALWAYS overwrites the output file:
- Uses "-y".
- Removes existing output_path before starting ffmpeg.
This means any output-path confirmation logic must be handled before calling
this launcher.

Rules implemented:
- Output channel is merged (stdout/stderr), so QProcess uses MergedChannels.
- Two arg builders:
    - Audio builder
    - Video builder (shared for video_with_audio and video_without_audio)
- Audio always forces stereo: -ac 2
- video_without_audio always uses -an
- video_with_audio with video_mute=True uses -an
- Video always uses: -pix_fmt yuv420p and libx264
- If video_resolution/video_fps is "origin", do not add related args
- Handle pad/trim args:
    - start_sec -> -ss
    - end_sec (already resolved) -> -to
    - pad_start_sec -> audio: adelay, video: tpad start_duration
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from PyQt6.QtCore import QProcess

from .path_manage import PathManage
import i18n
from .pydantic_models import (
    RunFFmpegAudio,
    RunFFmpegBase,
    RunFFmpegVideoWithAudio,
    RunFFmpegVideoWithoutAudio,
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
        (RunFFmpegAudio, RunFFmpegVideoWithAudio, RunFFmpegVideoWithoutAudio),
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

        if isinstance(config, RunFFmpegAudio):
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

    full_command = f'"{ffmpeg_exe}" ' + " ".join(f'"{arg}"' for arg in args) + '\n-\n'
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


def _apply_common_timing_args(args: list[str], cfg: RunFFmpegBase) -> None:
    # Trim start/end (legacy style: after -i)
    if cfg.start_sec is not None and float(cfg.start_sec) > 0:
        args.extend(["-ss", f"{float(cfg.start_sec)}"])

    if cfg.end_sec is not None and float(cfg.end_sec) > 0:
        args.extend(["-to", f"{float(cfg.end_sec)}"])


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


def _build_video_filters(*,
                         resolution: str,
                         crop: Optional[tuple[int, int, int, int]],
                         pad_start_sec: Optional[float],
                        ) -> Optional[str]:
    
    filters: list[str] = []

    # Crop first (if any): expects tuple(w, h, x, y)
    if crop:
        w, h, x, y = crop
        filters.append(f"crop={w}:{h}:{x}:{y}")

    if resolution != "origin":
        # Scale while keeping aspect ratio, then pad to square with black borders.
        # Reference:
        #   scale_expr = if(gt(iw,ih),R,-1):if(gt(iw,ih),-1,R)
        #   pad_expr   = R:R:(ow-iw)/2:(oh-ih)/2:black
        size_str = resolution.split("×", 1)[0]
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

def _apply_audio_args(args: list[str], cfg: RunFFmpegAudio) -> None:
    # codec
    if cfg.audio_format == "mp3":
        args.extend(["-c:a", "libmp3lame"])
        q = _map_mp3_vbr_to_q(cfg.audio_bitrate)
        args.extend(["-q:a", str(q)])
    elif cfg.audio_format == "ogg":
        args.extend(["-c:a", "libvorbis"])
        q = _map_ogg_vbr_to_q(cfg.audio_bitrate)
        args.extend(["-q:a", str(q)])
    else:
        raise ValueError(f"unsupported audio format: {cfg.audio_format}")

    args.extend(["-ar", str(cfg.audio_sample_rate)])

    # Always force stereo
    args.extend(["-ac", "2"])

    af = _build_audio_filters(volume=int(cfg.audio_volume), pad_start_sec=cfg.pad_start_sec)
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

def _apply_video_args(args: list[str], cfg: RunFFmpegVideoWithAudio | RunFFmpegVideoWithoutAudio) -> None:
    # 1. Video part
    vf = _build_video_filters(
        resolution=str(cfg.video_resolution),
        crop=getattr(cfg, "video_crop", None),
        pad_start_sec=cfg.pad_start_sec,
    )
    if vf:
        args.extend(["-vf", vf])

    # Video encoder (fixed)
    args.extend(["-pix_fmt", "yuv420p"])
    args.extend(["-c:v", "libx264"])
    args.extend(["-crf", str(int(cfg.video_crf))])

    if str(cfg.video_fps) != "origin":
        args.extend(["-r", str(cfg.video_fps)])

    if bool(cfg.video_gop_optimize):
        args.extend(["-g", "30"])

    # 2. Audio part
    if isinstance(cfg, RunFFmpegVideoWithoutAudio):
        args.append("-an")
        return

    if bool(cfg.video_mute):
        args.append("-an")
        return

    args.extend(["-c:a", "aac"])
    args.extend(["-b:a", _map_aac_bitrate(cfg.audio_bitrate)])
    args.extend(["-ar", str(cfg.audio_sample_rate)])

    af = _build_audio_filters(volume=int(cfg.audio_volume), pad_start_sec=cfg.pad_start_sec)

    # Keep A/V stable on some inputs
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
