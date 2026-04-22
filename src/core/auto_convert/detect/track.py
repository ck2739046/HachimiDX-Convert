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
from .detect import _load_detect_results
from .oc_sort import OCSort


TRACKER_NOTE_TYPES = [
    NoteType.TAP,
    NoteType.SLIDE,
    NoteType.TOUCH,
    NoteType.HOLD,
    NoteType.TOUCH_HOLD,
]



def _build_botsort_tracker(fps: float) -> BOTSORT:
    tracker_args = SimpleNamespace(
        tracker_type='botsort',

        # 优先匹配的 conf 阈值
        # 置信度大于此值的检测框，会被用于匹配轨迹
        track_high_thresh=0.5,

        # 如果 low_thresh < conf < high_thresh 也会被匹配，但是优先级更低
        # 置信度大于此值的检测框，会被用于匹配轨迹
        track_low_thresh=0.25,

        # 如果一个框无法匹配，且其置信度 ≥ 此值，会被创建为新轨迹
        # 值越高，越不容易视为新 id
        new_track_thresh=0.5,

        # 当一个轨迹在连续若干帧未匹配到检测框时，不会立即删除，而是保留最多 track_buffer 帧
        # 值越高，越不容易视为新 id
        # real buffer frames = fps / 30 * track_buffer
        # 由于传入了视频 fps，此处 10 固定等于 10/30 秒
        track_buffer=10,

        # 计算: 阈值 = 1-IOU
        # 值越高，越宽松，允许较大位移 (低iou) 也匹配上，越不容易视为新 id
        # 值越低, 越严格，仅允许较小位移 (高iou) 匹配上, 可能会被视为新 id
        match_thresh=0.8, # 默认

        # 融合阈值，默认开启
        fuse_score=True,

        # 画面稳定，不需要 gmc 全局运动补偿
        gmc_method='none',

        # 是否启用 ReID
        # 不想传入视频帧，所以不开
        with_reid=False,
        model='HachimiDX',
        # 开启 reid 的最小 iou 阈值
        # 只有两个框的 iou ≥ reid_iou_thresh 时，才会启用 reid 特征进行匹配
        # 值越高，越不容易启用 reid
        # 值越低，越容易启用 reid，越不容易视为新 id
        proximity_thresh=273,
        # 外观相似度
        # 值越低，外观就不需要那么相似也能匹配上，越不容易视为新 id
        appearance_thresh=478,
    )
    return BOTSORT(tracker_args, frame_rate=fps)


def _build_ocsort_tracker(fps: float) -> OCSort:

    # 仅用于 SLIDE；参数按 OC-SORT 原生语义硬编码
    return OCSort(
        # 第一阶段高分框阈值：score > det_thresh 才进入主匹配
        # 与 bot-sort 的 track_high_thresh 差不多
        # 值越大，越严格，越容易视为新 id
        det_thresh=0.5,

        # 轨迹最大失配帧数：超过后删除该轨迹
        # 与 bot-sort 的 track_buffer 类似
        # 取 0.2 秒
        max_age=round(fps * 0.2),

        # 轨迹最小命中次数：达到后才稳定输出（前 min_hits 帧会放宽）
        # 设置为 1，表示新轨迹一出现就输出，不需要等待稳定，适合追踪短命的 note
        min_hits=1,

        # IoU 匹配阈值：主匹配/补匹配都使用该阈值过滤低质量关联
        # 值越大，越严格，越容易视为新 id
        # 值越小，越宽松，允许较大位移 (低iou) 也匹配上，越不容易视为新 id
        iou_threshold=0.1,

        # 速度方向估计窗口：用于 OCR/VDC 角度代价中的历史观测回看步长
        # 0.1s, 但不超过10帧
        delta_t=min(10, round(fps*0.1)),  

        # 方向一致性代价权重：越大越偏好“运动方向一致”的匹配
        # slide 运动比较规律，调高权重
        inertia=0.6,

        # 启用 BYTE 二阶段低分框补匹配（0.1 < score < det_thresh）
        use_byte=True,
    )





def main(std_video_path: Path,
         total_frames: int,
        ) -> OpResult[None]:
    try:
        # 读取检测结果
        detect_results = _load_detect_results(std_video_path.parent)

        # 获取视频信息
        cap = cv2.VideoCapture(std_video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        video_size = round(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        cap.release()

        # 初始化5个独立tracker: 每个note_type一个实例
        # slide -> oc-sort
        # other -> bot-sort
        trackers_by_type = {}
        for note_type in TRACKER_NOTE_TYPES:
            if note_type == NoteType.SLIDE:
                trackers_by_type[note_type] = _build_ocsort_tracker(fps)
            else:
                trackers_by_type[note_type] = _build_botsort_tracker(fps)

        # 按帧号重新组织detect_results
        detections_by_frame = defaultdict(list)
        for detection in detect_results:
            detections_by_frame[detection.frame].append(detection)

        # 定义一些变量
        counter = 0
        last_counter = 0
        start_time = time.time()
        last_time = start_time
        # 维护 local tracker id 到全局连续 id 的映射
        local_to_global_id = {}
        next_global_id = [0]
        frame_shape = np.empty((video_size, video_size, 3), dtype=np.uint8)
        # final_tracked_results should be a dict
        # (track_id, note_type) -> list of note_geometry
        final_tracked_results = defaultdict(list)

        print("开始追踪模块...")

        # 遍历每一帧
        for frame_number in range(total_frames):

            # 获取当前帧的检测结果
            single_frame_detections = detections_by_frame.get(frame_number, [])

            # 按note_type分流到各自tracker
            detections_by_note_type = defaultdict(list)
            for note_geometry in single_frame_detections:
                detections_by_note_type[note_geometry.note_type].append(note_geometry)

            for note_type in TRACKER_NOTE_TYPES:
                type_detections = detections_by_note_type.get(note_type, [])
                # 转换为tracker需要的数据格式
                # 就算没有检测框，也要传个空对象给tracker以更新时间
                if note_type == NoteType.SLIDE:
                    tracker_input = _convert_detections_to_ocsort_format(type_detections)
                else:
                    tracker_input = _convert_detections_to_botsort_format(type_detections, frame_shape)
                # 交给tracker追踪
                track_result = trackers_by_type[note_type].update(tracker_input)
                if track_result is None or len(track_result) == 0:
                    continue
                # 解析追踪结果
                parsed_track_results = _parse_track_results(
                    track_result,
                    type_detections,
                    note_type,
                    frame_number,
                    detections_by_frame,
                )
                # 写入最终结果
                for local_track_id, original_note_geometry in parsed_track_results:
                    global_track_id = _get_or_assign_global_track_id(
                        note_type,
                        local_track_id,
                        local_to_global_id,
                        next_global_id,
                    )
                    key = (global_track_id, original_note_geometry.note_type)
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
        _save_track_results(final_tracked_results, std_video_path.parent, is_cls=False)
        return ok()

    except Exception as e:
        return err("Unexcepted error in auto_convert > detect > track", e)



def _convert_detections_to_botsort_format(detections, frame_shape):

    # 如果没有检测结果，返回空对象
    if not detections or len(detections) == 0:
        return OBB(np.empty((0, 7), dtype=np.float32), frame_shape)
    
    # 创建空白数据结构
    n = len(detections)
    data = np.zeros((n, 7), dtype=np.float32)

    # 填充数据: xywhr + conf + class_id(note_type to int)
    for i, note_geometry in enumerate(detections):
        cx = note_geometry.cx
        cy = note_geometry.cy
        w = note_geometry.w
        h = note_geometry.h
        r = note_geometry.r
        conf = note_geometry.conf
        class_id = map_note_type_to_class_id(note_geometry.note_type)
        # 填充数据
        data[i] = [cx, cy, w, h, r, conf, class_id]

    # 封装为OBB对象
    return OBB(data, frame_shape)



def _convert_detections_to_ocsort_format(detections):

    # 仅用于 slide：输入为普通 box 框，暂时不考虑 OBB
    if not detections or len(detections) == 0:
        return np.empty((0, 7), dtype=np.float32)

    data = np.zeros((len(detections), 7), dtype=np.float32)
    for i, note_geometry in enumerate(detections):
        data[i] = [
            note_geometry.x1,
            note_geometry.y1,
            note_geometry.x3,
            note_geometry.y3,
            note_geometry.conf,
            float(map_note_type_to_class_id(note_geometry.note_type)),
            float(i),
        ]
    return data



def _parse_track_results(track_result, detections, note_type, frame_number, detections_by_frame):
    parsed_track_results = []

    # 当前帧按 idx 快速回查
    current_idx_to_note = {i: note_geometry for i, note_geometry in enumerate(detections)}

    for result in track_result:
        # 兼容两种输出:
        # 1) 9列: [cx, cy, w, h, r, track_id, score, class_id, idx]
        # 2) 10列: 在末尾增加 frame_offset（head-padding 用）
        if len(result) < 9:
            continue

        track_id = int(result[5])
        idx = int(result[8])
        frame_offset = int(result[9]) if len(result) >= 10 else 0

        if frame_offset == 0:
            if idx in current_idx_to_note:
                parsed_track_results.append((track_id, current_idx_to_note[idx]))
            continue

        # head-padding: 回查历史帧对应 note_type 的检测列表
        src_frame = frame_number + frame_offset
        if src_frame < 0:
            continue

        src_detections = detections_by_frame.get(src_frame, [])
        src_type_detections = [d for d in src_detections if d.note_type == note_type]
        if 0 <= idx < len(src_type_detections):
            parsed_track_results.append((track_id, src_type_detections[idx]))

    return parsed_track_results



def _save_track_results(tracks, output_dir, is_cls):

    track_result_path = os.path.join(output_dir, "track_result.txt")
    
    with open(track_result_path, 'w', encoding='utf-8') as f:
        for key, value in tracks.items():
            track_id, note_type = key
            note_geometry_list = sorted(value, key=lambda x: x.frame) # 按帧号排序

            if len(note_geometry_list) > 0:
                # 写入轨迹头
                f.write(f"track_id: {track_id}, note_type: {note_type.value}\n")
                # 写入轨迹路径
                for note in note_geometry_list:
                    data = [
                        f"{note.frame}",
                        f"{note.note_type.value}",
                        f"{note.note_variant.value}",
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



def _get_or_assign_global_track_id(note_type, local_track_id, id_mapping, next_id_holder):
    """将 (note_type, local_track_id) 映射为全局连续 ID"""
    key = (note_type, int(local_track_id))
    if key not in id_mapping:
        id_mapping[key] = next_id_holder[0]
        next_id_holder[0] += 1
    return id_mapping[key]
