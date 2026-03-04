from ultralytics.trackers import BOTSORT
import os
import cv2
import time
import numpy as np
from collections import defaultdict
from types import SimpleNamespace
from ultralytics.engine.results import OBB
from pathlib import Path

from ...schemas.op_result import OpResult, ok, err
from .note_definition import *


def main(detect_results: list, std_video_path: Path) -> OpResult[Path]:
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
            track_buffer=15,        # real buffer frames = fps / 30 * track_buffer
                                    # 此处 15 = 0.5s
            match_thresh=0.85,      # 高iou，允许音符移动较大距离后还能匹配上
            fuse_score=True,        # 默认，综合考虑conf和iou
            gmc_method='none',      # 画面稳定，不需要gmc补偿

            proximity_thresh=273,
            appearance_thresh=478,
            with_reid=False,        # 不使用ReID特征
            model='HachimiDX'
        )
        tracker = BOTSORT(tracker_args, frame_rate=fps)

        # 按帧号重新组织detect_results
        detections_by_frame = defaultdict(list)
        for detection in detect_results:
            detections_by_frame[detection.frame].append(detection)

        # 定义一些变量
        counter = 0
        last_counter = 0
        start_time = time.time()
        last_time = start_time
        frame_shape = np.empty((video_size, video_size, 3), dtype=np.uint8)
        # final_tracked_results should be a dict
        # (track_id, note_type) -> list of note_geometry
        final_tracked_results = defaultdict(list)

        print("开始追踪模块...")

        # 遍历每一帧
        for frame_number in range(total_frames):

            # 获取当前帧的检测结果
            single_frame_detections = detections_by_frame.get(frame_number, [])
            # 转换为tracker需要的数据格式
            # 就算没有检测框，也要传个空对象给tracker以更新时间
            tracker_input = _convert_detections_to_tracker_format(single_frame_detections, frame_shape)
            # 交给tracker追踪
            track_result = tracker.update(tracker_input)
            if track_result is None or len(track_result) == 0:
                continue
            # 解析追踪结果
            parsed_track_results = _parse_track_results(track_result, single_frame_detections)
            # 写入最终结果
            for track_id, original_note_geometry in parsed_track_results:
                key = (track_id, original_note_geometry.note_type)
                value = original_note_geometry
                final_tracked_results[key].append(value)
            
            # 打印进度
            counter += 1
            if counter % 200 == 0:
                last_time, last_counter = print_progress('追踪', 'fps', counter, total_frames, last_time, last_counter)   
                        
        # 结束
        finish_time = time.time()
        print(f"追踪模块完成, 耗时{finish_time - start_time:.1f}s, 平均{total_frames / (finish_time - start_time):.1f}fps          ")
        
        # 保存到文件
        output_dir = std_video_path.parent
        _save_track_results(final_tracked_results, output_dir, is_cls=False)
        return ok(output_dir)

    except Exception as e:
        return err(e)



def _convert_detections_to_tracker_format(detections, frame_shape):

    # 如果没有检测结果，返回空对象
    if not detections or len(detections) == 0:
        return OBB(np.empty((0, 7), dtype=np.float32), frame_shape)
    
    # 创建空白数据结构
    n = len(detections)
    data = np.zeros((n, 7), dtype=np.float32)

    # 填充数据: xywhr + conf + class_id(note_type enum int)
    for i, note_geometry in enumerate(detections):
        cx = note_geometry.cx
        cy = note_geometry.cy
        w = note_geometry.w
        h = note_geometry.h
        r = note_geometry.r
        conf = note_geometry.conf
        class_id = note_geometry.note_type.value
        # 填充数据
        data[i] = [cx, cy, w, h, r, conf, class_id]

    # 封装为OBB对象
    return OBB(data, frame_shape)



def _parse_track_results(track_result, detections):
    # 利用 idx 建立映射
    id_map = {}
    for result in track_result:
        cx, cy, w, h, r, track_id, score, class_id, idx = result
        # 此处idx是tracker_input的索引
        # 利用这个可以轻松找到对应的原始检测框
        id_map[int(idx)] = int(track_id)
    # 生成最终结果
    parsed_track_results = []
    for i, note_geometry in enumerate(detections):
        if i in id_map:
            track_id = id_map[i]
            parsed_track_results.append((track_id, note_geometry))
    # return
    return parsed_track_results



def _save_track_results(tracks, output_dir, is_cls):

    track_result_path = os.path.join(output_dir, "track_result.txt")
    
    with open(track_result_path, 'w', encoding='utf-8') as f:
        for key, value in tracks.items():
            track_id, note_type = key
            note_geometry_list = sorted(value, key=lambda x: x.frame) # 按帧号排序

            if len(note_geometry_list) > 0:
                # 写入轨迹头
                f.write(f"track_id: {track_id}, note_type: {note_type.name}\n")
                # 写入轨迹路径
                for note in note_geometry_list:
                    data = [
                        f"{note.frame}",
                        f"{note.note_type.name}",
                        f"{note.note_variant.name}",
                        f"{note.conf:.4f}",
                        f"{note.x1:.4f}", f"{note.y1:.4f}",
                        f"{note.x2:.4f}", f"{note.y2:.4f}",
                        f"{note.x3:.4f}", f"{note.y3:.4f}",
                        f"{note.x4:.4f}", f"{note.y4:.4f}",
                        f"{note.cx:.4f}", f"{note.cy:.4f}",
                        f"{note.w:.4f}", f"{note.h:.4f}",
                        f"{note.r:.4f}"
                    ]
                    f.write(', '.join(data) + '\n')

                f.write('\n')  # track_id 之间空行分隔
    
    prefix = "分类后的" if is_cls else "未分类的"
    print(f"{prefix}追踪结果已保存到: {track_result_path}")



def _load_track_results(output_dir):

    track_result_path = os.path.join(output_dir, "track_result.txt")
    tracks = defaultdict(list)
    
    with open(track_result_path, 'r', encoding='utf-8') as f:
        current_track_id = -1
        current_note_type = -1
        
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            if line.startswith('track_id:'):
                # 解析轨迹头
                parts = line.split(',')
                if len(parts) == 2:
                    current_track_id = int(parts[0].split(':')[1].strip())
                    current_note_type = NoteType(parts[1].split(':')[1].strip())
                    key = (current_track_id, current_note_type)
                    if key not in tracks:
                        tracks[key] = []
            else:
                # 解析轨迹点数据
                parts = line.split(',')
                if len(parts) == 17:  # 有17个字段
                    point = Note_Geometry(
                        frame=int(parts[0].strip()),
                        note_type=NoteType(parts[1].strip()),
                        note_variant=NoteVariant(parts[2].strip()),
                        conf=float(parts[3].strip()),
                        x1=float(parts[4].strip()),
                        y1=float(parts[5].strip()),
                        x2=float(parts[6].strip()),
                        y2=float(parts[7].strip()),
                        x3=float(parts[8].strip()),
                        y3=float(parts[9].strip()),
                        x4=float(parts[10].strip()),
                        y4=float(parts[11].strip()),
                        cx=float(parts[12].strip()),
                        cy=float(parts[13].strip()),
                        w=float(parts[14].strip()),
                        h=float(parts[15].strip()),
                        r=float(parts[16].strip())
                    )
                    tracks[(current_track_id, current_note_type)].append(point)
    
    return tracks

