from __future__ import annotations

"""ffprobe_launcher

This script is intended to be executed via QProcess (QuickActionButton).

Contract:
- It MUST print exactly one line of JSON to stdout.
- It MUST NOT print anything else (stdout or stderr), otherwise UI-side JSON
  parsing will fail because the QProcess uses merged channels.

Output JSON shape:
{
  "ok": bool,
  "file_type": "video" | "video_muted" | "audio" | "unknown",
  "streams": [ {..ffprobe stream dict..}, ... ],
  "error": str | null
}

It uses the same ffprobe -show_entries filtering as legacy/tools/ffmpeg_utils.py.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Ensure project root is importable when executed as a script.
_ROOT = str(Path(__file__).resolve().parents[2])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from settings import SettingsManage


_STREAM_ENTRIES = (
    "stream=index,codec_type,codec_name,width,height,avg_frame_rate,"
    "duration,bit_rate,nb_frames,sample_rate,channels,channel_layout"
)


def _determine_file_type(streams: List[Dict[str, Any]]) -> str:
    has_video = any(s.get("codec_type") == "video" for s in streams)
    has_audio = any(s.get("codec_type") == "audio" for s in streams)

    if has_video and has_audio:
        return "video"
    if has_video and not has_audio:
        return "video_muted"
    if not has_video and has_audio:
        return "audio"
    return "unknown"


def _run_ffprobe(file_path: str) -> Tuple[bool, str | None, List[Dict[str, Any]]]:
    ffprobe_exe, ok, msg = SettingsManage.get_path("ffprobe_exe")
    if not ok or not ffprobe_exe:
        return False, f"ffprobe_exe path not available: {msg}", []

    args = [
        "-v",
        "error",
        "-show_entries",
        _STREAM_ENTRIES,
        "-of",
        "json",
        file_path,
    ]

    result = subprocess.run(
        [ffprobe_exe] + args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if result.returncode != 0:
        # Keep error compact; UI can print it in OutputLogWidget if desired.
        err = (result.stderr or "").strip()
        return False, f"ffprobe failed: {err}" if err else f"ffprobe failed: exit_code={result.returncode}", []

    try:
        data = json.loads(result.stdout)
        streams = data.get("streams", [])
        if not isinstance(streams, list):
            return False, "ffprobe JSON missing 'streams' list", []
        return True, None, streams
    except Exception as e:
        return False, f"ffprobe JSON parse failed: {e}", []


def main(argv: List[str]) -> int:
    # Always output JSON (single line) and exit.
    try:
        def _emit(payload: Dict[str, Any]) -> None:
            sys.stdout.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")

        if len(argv) < 2:
            _emit({"ok": False, "file_type": "unknown", "streams": [], "error": "No input file"})
            return 2

        file_path = os.path.normpath(os.path.abspath(argv[1]))
        if not os.path.exists(file_path):
            _emit({"ok": False, "file_type": "unknown", "streams": [], "error": f"File not found: {file_path}"})
            return 2

        ok, err, streams = _run_ffprobe(file_path)
        file_type = _determine_file_type(streams) if ok else "unknown"

        _emit({"ok": ok, "file_type": file_type, "streams": streams, "error": err})
        return 0 if ok else 1

    except Exception as e:
        sys.stdout.write(
            json.dumps(
                {"ok": False, "file_type": "unknown", "streams": [], "error": f"launcher error: {e}"},
                ensure_ascii=False,
                separators=(",", ":"),
            )
            + "\n"
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
