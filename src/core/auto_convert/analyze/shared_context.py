from dataclasses import dataclass
from pathlib import Path
import cv2
from typing import Tuple, Dict, Any

from ..detect.track import _load_track_results




@dataclass
class SharedContext:

    std_video_path: Path
    std_video_size: int
    std_video_fps: int
    
    std_video_cx: int
    std_video_cy: int
    
    judgeline_start: float
    judgeline_end: float
    
    note_travel_dist: float
    touch_travel_dist: float
    touch_hold_travel_dist: float
    
    # 速度常数
    tap_DefaultMsec: float = 0.0
    tap_OptionNotespeed: float = 0.0
    touch_DefaultMsec: float = 0.0
    touch_OptionNotespeed: float = 0.0
    
    # 预计算数据
    touch_areas: Dict[str, Tuple[int, int]] = None
    track_data: Dict[Any, Any] = None




def create_shared_context(std_video_path: Path) -> SharedContext:

    # 获取视频信息
    cap = cv2.VideoCapture(str(std_video_path))
    std_video_size = round(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    std_video_fps = round(cap.get(cv2.CAP_PROP_FPS))
    cap.release()
    
    std_video_cx = std_video_size // 2
    std_video_cy = std_video_cx
    
    # 1080p下，音符从120出现480结束
    judgeline_start = std_video_size * 120 / 1080
    judgeline_end = std_video_size * 480 / 1080
    
    note_travel_dist = judgeline_end - judgeline_start
    touch_travel_dist = 34 * std_video_size / 1080       # 1080p下，touch移动距离为34像素
    touch_hold_travel_dist = 30 * std_video_size / 1080  # 1080p下，touch_hold移动距离为30像素
    
    touch_areas = get_touch_areas(std_video_size, std_video_cx, std_video_cy)
    track_data = _load_track_results(std_video_path.parent)
    
    return SharedContext(
        std_video_path=std_video_path,
        std_video_size=std_video_size,
        std_video_fps=std_video_fps,

        std_video_cx=std_video_cx,
        std_video_cy=std_video_cy,

        judgeline_start=judgeline_start,
        judgeline_end=judgeline_end,

        note_travel_dist=note_travel_dist,
        touch_travel_dist=touch_travel_dist,
        touch_hold_travel_dist=touch_hold_travel_dist,

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
