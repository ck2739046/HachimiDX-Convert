from collections import defaultdict
import os
import cv2
import numpy as np
import math
import traceback
from math import gcd

from ..detect.note_definition import *
from ..detect.track import _load_track_results



class NoteAnalyzer:
    def __init__(self):

        # 速度常数
        self.note_DefaultMsec = 0
        self.note_OptionNotespeed = 0
        self.touch_DefaultMsec = 0
        self.touch_OptionNotespeed = 0

        # 常用变量
        self.video_size = 0
        self.fps = 0
        self.screen_cx = 0
        self.screen_cy = 0
        self.judgeline_start = 0
        self.judgeline_end = 0
        self.note_travel_dist = 0
        self.touch_travel_dist = 0
        self.touch_hold_travel_dist = 0
        self.touch_areas = {}
        self.track_data = ()
        self.video_path = ""







    def main(self, main_folder: str, bpm: float, chart_lv: int, base_denominator: int, duration_denominator: int):
        try:
            # 在文件夹查找视频文件
            for root, _, files in os.walk(main_folder):
                for fn in files:
                    if fn.lower().endswith('standardized.mp4'):
                        self.video_path = os.path.join(root, fn)
                        break
            if not self.video_path:
                raise Exception(f"No standardized.mp4 file found under {main_folder}")
            
            # 获取视频信息
            cap = cv2.VideoCapture(self.video_path)
            self.video_size = round(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.fps = round(cap.get(cv2.CAP_PROP_FPS))
            #total_frames = round(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.release()

            # 定义一些常数
            self.screen_cx = self.video_size // 2
            self.screen_cy = self.screen_cx
            # 1080p下，音符从120出现480结束
            self.judgeline_start = self.video_size * 120 / 1080
            self.judgeline_end = self.video_size * 480 / 1080
            self.note_travel_dist = self.judgeline_end - self.judgeline_start
            self.touch_travel_dist = 34 * self.video_size / 1080        # 1080p下，touch移动距离为34像素
            self.touch_hold_travel_dist = 30 * self.video_size / 1080   # 1080p下，touch_hold移动距离为30像素
            self.touch_areas = self.get_touch_areas()
            self.noteDetector = NoteDetect.NoteDetector()
            self.track_data = self.noteDetector._load_track_results(main_folder)


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

        except Exception as e:
            raise Exception(f"Error in NoteAnalyzer.main: {e}")
        

