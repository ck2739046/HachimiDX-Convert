from ultralytics import YOLO
from ultralytics.trackers import BOTSORT
import os
import cv2
import time
import numpy as np
from collections import defaultdict
from types import SimpleNamespace
from ultralytics.engine.results import OBB
from ultralytics.utils import LOGGER
import logging
import subprocess
import shutil
import traceback
import math
import sys
from typing import Tuple
from pathlib import Path

from .main import *
from src.services import PathManage
from ...schemas.op_result import OpResult, ok, err, print_op_result
from .note_definition import *

# debug
def track_module(self, detect_results, std_video_path):
    try:
        # 获取视频信息
        cap = cv2.VideoCapture(std_video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = round(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_size = round(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        cap.release()

        # 初始化tracker
        tracker_args = SimpleNamespace(
            tracker_type='botsort',
            track_high_thresh=0.25, # 默认，宽容
            track_low_thresh=0.1,   # 默认，宽容
            new_track_thresh=0.25,  # 默认，高敏感度，容易视为新的轨迹ID
            track_buffer=10,        # real buffer = fps / 30 * track_buffer
            match_thresh=0.85,      # 高iou，允许音符移动较大距离后还能匹配上
            fuse_score=True,        # 默认，综合考虑conf和iou
            gmc_method='none',      # 画面十分稳定，不需要gmc
            proximity_thresh=273,
            appearance_thresh=478,
            with_reid=False,        # 不使用ReID特征
            model='HachimiDX'
        )
        tracker = BOTSORT(tracker_args, frame_rate=fps)

        # 按帧号重新组织detect_results
        detections_by_frame = defaultdict(list)
        for detection in detect_results:
            detections_by_frame[detection['frame']].append(detection)

        # 定义一些变量
        counter = 0
        last_counter = 0
        start_time = time.time()
        last_time = start_time
        frame_shape = np.empty((video_size, video_size, 3), dtype=np.uint8)
        # final_tracked_results should be a dict mapping track_id -> {'class_id':..., 'path':[...]}
        final_tracked_results = defaultdict(lambda: {'class_id': None, 'path': []})

        print("开始追踪模块...")

        # 遍历每一帧
        for frame_number in range(total_frames):

            # 获取当前帧的检测结果
            single_frame_detections = detections_by_frame.get(frame_number, [])
            # 转换为tracker需要的数据格式
            # 就算没有检测框，也要传个空对象给tracker以更新时间
            tracker_input = self._convert_detections_to_tracker_format(single_frame_detections, frame_shape)
            # 交给tracker追踪
            track_result = tracker.update(tracker_input)
            if track_result is None or len(track_result) == 0:
                continue
            # 解析追踪结果
            parsed_track_results = self._parse_track_results(track_result, single_frame_detections)
            # 写入最终结果
            for track_id, original_detection in parsed_track_results:
                final_tracked_results[track_id]['class_id'] = self.get_specific_class_id(original_detection['main_class_id'])
                final_tracked_results[track_id]['path'].append({
                    'frame': frame_number,
                    'x1': original_detection['x1'],
                    'y1': original_detection['y1'],
                    'x2': original_detection['x2'],
                    'y2': original_detection['y2'],
                    'x3': original_detection['x3'],
                    'y3': original_detection['y3'],
                    'x4': original_detection['x4'],
                    'y4': original_detection['y4'],
                    'r': original_detection['r']
                })
            
            # 打印进度
            counter += 1
            if counter % 200 == 0:
                last_time, last_counter = self.print_progress('追踪', 'fps', counter, total_frames, last_time, last_counter)   
                        
        # 结束
        finish_time = time.time()
        print(f"追踪模块完成, 耗时{finish_time - start_time:.1f}s, 平均{total_frames / (finish_time - start_time):.1f}fps          ")
        return final_tracked_results

    except Exception as e:
        print(f"Error in track_module: {e}")
        print(traceback.format_exc())
        return None



def _convert_detections_to_tracker_format(self, detections, frame_shape):
    # 如果没有检测结果，返回空对象
    if not detections or len(detections) == 0:
        return OBB(np.empty((0, 7), dtype=np.float32), frame_shape)
    # 从xyxyxyxy转换为xywhr
    n = len(detections)
    data = np.zeros((n, 7), dtype=np.float32)
    for i, box in enumerate(detections):
        if box['r'] - 1 < -273:
            # detect数据
            cx = (box['x1'] + box['x3']) / 2.0
            cy = (box['y1'] + box['y3']) / 2.0
            w = abs(box['x1'] - box['x3'])
            h = abs(box['y1'] - box['y3'])
            r = 0.0
        else:
            # obb数据
            cx = (box['x1'] + box['x2'] + box['x3'] + box['x4']) / 4.0
            cy = (box['y1'] + box['y2'] + box['y3'] + box['y4']) / 4.0
            w = math.sqrt((box['x2'] - box['x1'])**2 + (box['y2'] - box['y1'])**2)
            h = math.sqrt((box['x3'] - box['x2'])**2 + (box['y3'] - box['y2'])**2)
            r = box['r']
        # 填充数据
        data[i] = [cx, cy, w, h, r, box['confidence'], box['main_class_id']]
    # 封装为OBB对象
    return OBB(data, frame_shape)



def _parse_track_results(self, track_result, detections):
    # 利用 idx 建立映射
    id_map = {}
    for result in track_result:
        cx, cy, w, h, r, track_id, score, main_class_id, idx = result
        # 此处idx是tracker_input的索引
        # 利用这个可以轻松找到对应的原始检测框
        id_map[int(idx)] = int(track_id)
    # 生成最终结果
    parsed_track_results = []
    for i, detection in enumerate(detections):
        if i in id_map:
            track_id = id_map[i]
            parsed_track_results.append((track_id, detection))
    # return
    return parsed_track_results



def _save_track_results(self, tracks, output_dir, is_cls):

    track_result_path = os.path.join(output_dir, "track_result.txt")
    
    with open(track_result_path, 'w', encoding='utf-8') as f:
        for track_id, track_data in tracks.items():
            if track_data['class_id'] is not None and len(track_data['path']) > 0:
                # 写入轨迹头
                f.write(f"track_id: {track_id}, class_id: {track_data['class_id']}\n")
                
                # 写入轨迹路径
                for point in track_data['path']:
                    data = [
                        f"{point['frame']}",
                        f"{point['x1']:.4f}", f"{point['y1']:.4f}",
                        f"{point['x2']:.4f}", f"{point['y2']:.4f}",
                        f"{point['x3']:.4f}", f"{point['y3']:.4f}",
                        f"{point['x4']:.4f}", f"{point['y4']:.4f}",
                        f"{point['r']:.4f}"
                    ]
                    f.write(', '.join(data) + '\n')

                f.write('\n')  # track_id之间空行分隔
    
    prefix = "分类后的" if is_cls else "未分类的"
    print(f"{prefix}追踪结果已保存到: {track_result_path}")



def _load_track_results(self, output_dir):

    track_result_path = os.path.join(output_dir, "track_result.txt")
    tracks = defaultdict(lambda: {'class_id': None, 'path': []})
    
    with open(track_result_path, 'r', encoding='utf-8') as f:
        current_track_id = -1
        current_class_id = -1
        
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            if line.startswith('track_id:'):
                # 解析轨迹头
                parts = line.split(',')
                if len(parts) == 2:
                    current_track_id = int(parts[0].split(':')[1].strip())
                    current_class_id = int(parts[1].split(':')[1].strip())
                    tracks[current_track_id]['class_id'] = current_class_id
            else:
                # 解析轨迹点数据
                parts = line.split(',')
                if len(parts) == 10:
                    point = {
                        'frame': int(parts[0].strip()),
                        'x1': float(parts[1].strip()),
                        'y1': float(parts[2].strip()),
                        'x2': float(parts[3].strip()),
                        'y2': float(parts[4].strip()),
                        'x3': float(parts[5].strip()),
                        'y3': float(parts[6].strip()),
                        'x4': float(parts[7].strip()),
                        'y4': float(parts[8].strip()),
                        'r': float(parts[9].strip())
                    }
                    tracks[current_track_id]['path'].append(point)
    
    return tracks

