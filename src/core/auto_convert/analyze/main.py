from collections import defaultdict
import os
import cv2
import numpy as np
import math
import traceback
from math import gcd
from pathlib import Path

from ..detect.note_definition import *
from ..detect.track import _load_track_results
from ...schemas.op_result import OpResult, ok, err
from .tool import *
from .shared_context import *




def __init__(self):

    # 速度常数
    self.note_DefaultMsec = 0
    self.note_OptionNotespeed = 0
    self.touch_DefaultMsec = 0
    self.touch_OptionNotespeed = 0

    # 常用变量
    self.std_video_size = 0
    self.std_video_fps = 0

    self.std_video_cx = 0
    self.std_video_cy = 0

    self.judgeline_start = 0
    self.judgeline_end = 0

    self.note_travel_dist = 0
    self.touch_travel_dist = 0
    self.touch_hold_travel_dist = 0

    self.touch_areas = {}
    self.track_data = ()
    self.std_video_path = ""




def main(self,
         std_video_path: Path,
         bpm: float,
         chart_lv: int,
         base_denominator: int,
         duration_denominator: int
        ) -> OpResult[None]:
    
    try:
        shared_context = create_shared_context(std_video_path)

        # tap
        tap_info = {}
        tap_data = self.preprocess_tap_data()
        if tap_data:
            self.note_DefaultMsec, self.note_OptionNotespeed = self.estimate_note_DefaultMsec(tap_data)
            tap_info = self.analyze_tap_reach_time(tap_data)

        # touch
        touch_info = {}
        touch_data = self.preprocess_touch_data()
        if touch_data:
            self.touch_DefaultMsec, self.touch_OptionNotespeed = self.estimate_touch_DefaultMsec(touch_data)
            touch_info = self.analyze_touch_reach_time(touch_data)

        # hold
        hold_info = {}
        hold_data = self.preprocess_hold_data()
        if hold_data:
            hold_info = self.analyze_hold_reach_time(hold_data)

        # touch-hold
        touch_hold_info = {}
        touch_hold_data = self.preprocess_touch_hold_data()
        if touch_hold_data:
            touch_hold_info = self.analyze_touch_hold_reach_time(touch_hold_data)

        # slide
        # 处理星星头，视为 tap 处理
        slide_head_info = {}
        slide_head_data = self.preprocess_slide_head_data()
        if slide_head_data:
            slide_head_info = self.analyze_tap_reach_time(slide_head_data)
        # 处理星星尾
        slide_tail_info = {}
        slide_tail_data = self.preprocess_slide_tail_data()
        if slide_tail_data:
            slide_tail_info = self.analyze_slide_tail(slide_tail_data)
        # 合并slide信息
        slide_info = self.merge_slide_info(slide_head_info, slide_tail_info, bpm)

        # analyze all notes info
        self.analyze_all_notes_info(bpm, chart_lv, base_denominator, duration_denominator, tap_info, slide_info, touch_info, hold_info, touch_hold_info)

        return ok()
    
    except Exception as e:
        return err(f"Unexpected error in auto_convert > analyze > main", e)

