from dataclasses import dataclass
from pathlib import Path
import cv2
from typing import Tuple, Dict, Any

from ..detect.track import _load_track_results
from ...tools.media_ffprobe_inspect import FFprobeInspect
from ...schemas.op_result import print_op_result




@dataclass
class SharedContext:

    std_video_path: Path
    std_video_size: int
    std_video_fps: int
    frame_timestamps_msec: list[float]
    
    std_video_cx: int
    std_video_cy: int
    
    judgeline_start: float
    judgeline_end: float
    
    note_travel_dist: float
    touch_travel_dist: float
    touch_outer_size: float
    touch_hold_travel_dist: float
    touch_hold_max_size: float
    
    # 速度常数
    note_DefaultMsec: float = 0.0
    note_OptionNotespeed: float = 0.0
    touch_DefaultMsec: float = 0.0
    touch_OptionNotespeed: float = 0.0
    
    # 预计算数据
    touch_areas: Dict[str, Tuple[int, int]] = None
    track_data: Dict[Any, Any] = None

    def frame_to_msec(self, frame_idx: int) -> float:
        if frame_idx < 0:
            raise ValueError(f"frame index must be >= 0, got: {frame_idx}")
        if frame_idx >= len(self.frame_timestamps_msec):
            raise IndexError(
                f"frame index out of range, frame={frame_idx}, timestamps={len(self.frame_timestamps_msec)}"
            )
        return self.frame_timestamps_msec[frame_idx]

    def frame_delta_msec(self, start_frame: int, end_frame: int) -> float:
        if end_frame == start_frame:
            return 0.0
        return abs(self.frame_to_msec(end_frame) - self.frame_to_msec(start_frame))




def create_shared_context(std_video_path: Path, is_big_touch: bool) -> SharedContext:

    # 获取视频信息
    cap = cv2.VideoCapture(str(std_video_path))
    std_video_size = round(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    std_video_fps = round(cap.get(cv2.CAP_PROP_FPS))
    cap.release()

    result = FFprobeInspect.inspect_video_frame_timestamps_msec(str(std_video_path))
    if not result.is_ok:
        raise ValueError(
            "Failed to load frame timestamps for analyze. "
            f"Please rerun detect/analyze with a valid video.\n{print_op_result(result)}"
        )
    frame_timestamps_msec = result.value
    
    std_video_cx = std_video_size // 2
    std_video_cy = std_video_cx
    
    # 1080p下，音符从120出现480结束
    judgeline_start = std_video_size * 120 / 1080
    judgeline_end = std_video_size * 480 / 1080
    
    note_travel_dist = judgeline_end - judgeline_start
    touch_travel_dist = 34 * std_video_size / 1080       # 1080p下，touch移动距离为34像素
    touch_outer_size = 54 * std_video_size / 1080        # 1080p下，touch外部尺寸为54
    touch_hold_travel_dist = 31 * std_video_size / 1080  # 1080p下，touch_hold移动距离为31像素
    touch_hold_max_size = 200 * std_video_size / 1080    # 1080p下，touch_hold最大尺寸约为200
    if is_big_touch:
        touch_travel_dist = touch_travel_dist * 1.3
        touch_outer_size = touch_outer_size * 1.3
        touch_hold_travel_dist = touch_hold_travel_dist * 1.3
        touch_hold_max_size = touch_hold_max_size * 1.3
    
    touch_areas = get_touch_areas(std_video_size, std_video_cx, std_video_cy)
    track_data = _load_track_results(std_video_path.parent)

    # 验证track_data中的frame索引不超过视频帧数
    max_track_frame = None
    for points in track_data.values():
        for point in points:
            frame_num = int(point.frame)
            if max_track_frame is None or frame_num > max_track_frame:
                max_track_frame = frame_num
    if max_track_frame is not None and max_track_frame >= len(frame_timestamps_msec):
        raise ValueError(
            "Track frame index exceeds available frame timestamps. "
            f"max_track_frame={max_track_frame}, timestamp_count={len(frame_timestamps_msec)}"
        )
    
    return SharedContext(
        std_video_path=std_video_path,
        std_video_size=std_video_size,
        std_video_fps=std_video_fps,
        frame_timestamps_msec=frame_timestamps_msec,

        std_video_cx=std_video_cx,
        std_video_cy=std_video_cy,

        judgeline_start=judgeline_start,
        judgeline_end=judgeline_end,

        note_travel_dist=note_travel_dist,
        touch_travel_dist=touch_travel_dist,
        touch_outer_size=touch_outer_size,
        touch_hold_travel_dist=touch_hold_travel_dist,
        touch_hold_max_size=touch_hold_max_size,

        touch_areas=touch_areas,
        track_data=track_data,
    )



def get_touch_areas(std_video_size, std_video_cx, std_video_cy) -> dict:
    # 1080p的触摸区域中心坐标
    std_touch_areas = {
        # A
        'A1': (693, 171), 'A2': (909, 388), 'A3': (908, 693), 'A4': (692, 910),
        'A5': (387, 909), 'A6': (170, 694), 'A7': (170, 388), 'A8': (386, 170),
        # B
        'B1': (624, 336), 'B2': (745, 456), 'B3': (744, 626), 'B4': (624, 745),
        'B5': (455, 745), 'B6': (335, 626), 'B7': (335, 456), 'B8': (454, 336),
        # C
        'C1': (540, 540),
        # D
        'D1': (540, 117), 'D2': (840, 241), 'D3': (963, 542), 'D4': (839, 840),
        'D5': (540, 964), 'D6': (241, 840), 'D7': (116, 540), 'D8': (239, 241),
        # E
        'E1': (540, 229), 'E2': (760, 320), 'E3': (852, 540), 'E4': (760, 761),
        'E5': (539, 853), 'E6': (319, 760), 'E7': (228, 540), 'E8': (319, 321),
    }
    new_touch_areas = {}
    for area_label, (x, y) in std_touch_areas.items():
        scaled_x = round((x - 540) * std_video_size / 1080 + std_video_cx)
        scaled_y = round((y - 540) * std_video_size / 1080 + std_video_cy)
        new_touch_areas[area_label] = (scaled_x, scaled_y)
    return new_touch_areas
