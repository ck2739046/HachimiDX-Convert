from ultralytics import YOLO
from ultralytics.trackers import BOTSORT
import os
import cv2
import time
import torch
import numpy as np
from collections import defaultdict
from types import SimpleNamespace
from ultralytics.engine.results import Boxes
from ultralytics.utils import LOGGER
import logging
import subprocess
import shutil
import traceback

original_level = LOGGER.level
LOGGER.setLevel(logging.ERROR) # 只显示错误信息，忽略 Warning


class NoteDetector:
    def __init__(self):
        pass


    def detect_module(self, input_path, detect_model_path, obb_model_path, output_dir):
        """检测模块：逐帧识别音符"""
        print("开始检测模块...")
        
        try:
            # 获取视频信息
            cap = cv2.VideoCapture(input_path)
            total_frames = round(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            # 加载模型
            detect_model = YOLO(detect_model_path)
            obb_model = YOLO(obb_model_path)
            if torch.cuda.is_available():
                detect_model.to('cuda')
                obb_model.to('cuda')
                print(f"使用GPU: {torch.cuda.get_device_name(0)}")
            
            # 存储检测结果
            all_detections = []
            
            # 逐帧处理
            frame_count = 0
            start_time = time.time()
            last_start_time = start_time
            last_frame_number = 0
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # 使用两个模型预测当前帧
                detect_results = detect_model.predict(
                    source=frame,
                    conf=0.6,
                    iou=0.7,
                    verbose=False,
                    device='cuda' if torch.cuda.is_available() else 'cpu',
                    max_det=50
                )
                
                obb_results = obb_model.predict(
                    source=frame,
                    conf=0.6,
                    iou=0.7,
                    verbose=False,
                    device='cuda' if torch.cuda.is_available() else 'cpu',
                    max_det=50
                )
                
                # 合并检测结果
                frame_detections = self._merge_detections(detect_results, obb_results, frame_count)
                all_detections.extend(frame_detections)
                
                # 显示进度
                if frame_count % 30 == 0:
                    progress = (frame_count / total_frames) * 100
                    end_time = time.time()
                    elapsed_time = end_time - last_start_time
                    elapsed_frame = frame_count - last_frame_number
                    last_start_time = end_time # 重置时间给下一轮
                    last_frame_number = frame_count # 重置帧数给下一轮
                    fps_rate = elapsed_frame / elapsed_time if elapsed_time > 0 else 0
                    print(f"检测进度: {frame_count}/{total_frames} ({progress:.1f}%) {fps_rate:.1f}fps", end="\r", flush=True)
                
                frame_count += 1
            
            cap.release()
            
            # 保存检测结果到文件
            self._save_detect_results(all_detections, output_dir)
            
            elapsed_time = time.time() - start_time
            average_fps = frame_count / elapsed_time if elapsed_time > 0 else 0
            print(f"检测完成，平均FPS: {average_fps:.2f}")
            
            return all_detections
            
        except Exception as e:
            raise Exception(f"检测模块错误: {e}")
    
    def _merge_detections(self, detect_results, obb_results, frame_number):
        """合并YOLO和OBB检测结果"""
        frame_detections = []
        
        # 处理YOLO检测结果 (class_id: 0,1,2 -> 0,5,10)
        if len(detect_results) > 0 and detect_results[0].boxes is not None:
            all_boxes = detect_results[0].boxes.data.cpu().numpy()
            
            for box in all_boxes:
                x1, y1, x2, y2, conf, class_id = box[:6]
                class_id = int(class_id)
                
                # 映射class_id: tap=0, slide=5, touch=10
                if class_id == 0:  # tap
                    mapped_class_id = 0
                elif class_id == 1:  # slide
                    mapped_class_id = 5
                elif class_id == 2:  # touch
                    mapped_class_id = 10
                else:
                    continue
                
                # 对于普通检测框，使用边界框的四个角点
                x1, y1, x2, y2 = float(x1), float(y1), float(x2), float(y2)
                detection = {
                    'frame': frame_number,
                    'class_id': mapped_class_id,
                    'x1': x1, 'y1': y1,
                    'x2': x2, 'y2': y2,
                    'x3': x1, 'y3': y2,
                    'x4': x2, 'y4': y1,
                    'confidence': float(conf)
                }
                frame_detections.append(detection)
        
        # 处理OBB检测结果 (class_id: 0,1 -> 15,20)
        if len(obb_results) > 0 and obb_results[0].obb is not None:
            obb_data = obb_results[0].obb
            xyxyxyxy = obb_data.xyxyxyxy.cpu().numpy()
            cls = obb_data.cls.cpu().numpy()
            conf = obb_data.conf.cpu().numpy()
            
            for i in range(len(xyxyxyxy)):
                points = xyxyxyxy[i]
                class_id = int(cls[i])
                
                # 映射class_id: hold=15, touch-hold=20
                if class_id == 0:  # hold
                    mapped_class_id = 15
                elif class_id == 1:  # touch-hold
                    mapped_class_id = 20
                else:
                    continue
                
                # 对于OBB，使用原始四个点坐标
                x1, y1 = float(points[0][0]), float(points[0][1])
                x2, y2 = float(points[1][0]), float(points[1][1])
                x3, y3 = float(points[2][0]), float(points[2][1])
                x4, y4 = float(points[3][0]), float(points[3][1])
                
                detection = {
                    'frame': frame_number,
                    'class_id': mapped_class_id,
                    'x1': x1, 'y1': y1,
                    'x2': x2, 'y2': y2,
                    'x3': x3, 'y3': y3,
                    'x4': x4, 'y4': y4,
                    'confidence': float(conf[i])
                }
                frame_detections.append(detection)
        
        return frame_detections
    
    def _save_detect_results(self, detections, output_dir):
        """保存检测结果到txt文件"""
        detect_result_path = os.path.join(output_dir, "detect_result.txt")
        
        with open(detect_result_path, 'w', encoding='utf-8') as f:
            current_frame = -1
            for detection in detections:
                if detection['frame'] != current_frame:
                    if current_frame != -1:
                        f.write('\n')  # 帧之间空行分隔
                    f.write(f"frame: {detection['frame']}\n")
                    current_frame = detection['frame']
                
                # 写入音符数据
                f.write(f"{detection['class_id']}, {detection['x1']:.2f}, {detection['y1']:.2f}, "
                       f"{detection['x2']:.2f}, {detection['y2']:.2f}, {detection['x3']:.2f}, {detection['y3']:.2f}, "
                       f"{detection['x4']:.2f}, {detection['y4']:.2f}, {detection['confidence']:.4f}\n")
        
        print(f"检测结果已保存到: {detect_result_path}")
    
    def _load_detect_results(self, output_dir):
        """从txt文件加载检测结果"""
        detect_result_path = os.path.join(output_dir, "detect_result.txt")
        detections = []
        
        with open(detect_result_path, 'r', encoding='utf-8') as f:
            current_frame = -1
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                if line.startswith('frame:'):
                    current_frame = int(line.split(':')[1].strip())
                else:
                    # 解析音符数据
                    parts = line.split(',')
                    if len(parts) == 10:
                        detection = {
                            'frame': current_frame,
                            'class_id': int(parts[0].strip()),
                            'x1': float(parts[1].strip()),
                            'y1': float(parts[2].strip()),
                            'x2': float(parts[3].strip()),
                            'y2': float(parts[4].strip()),
                            'x3': float(parts[5].strip()),
                            'y3': float(parts[6].strip()),
                            'x4': float(parts[7].strip()),
                            'y4': float(parts[8].strip()),
                            'confidence': float(parts[9].strip())
                        }
                        detections.append(detection)
        
        return detections

    def track_module(self, input_path, output_dir):
        """追踪模块：追踪音符轨迹"""
        print("开始追踪模块...")
        
        try:
            # 加载检测结果
            detect_results = self._load_detect_results(output_dir)
            
            # 获取视频信息
            cap = cv2.VideoCapture(input_path)
            video_width = round(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            video_height = round(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = round(cap.get(cv2.CAP_PROP_FPS))
            total_frames = round(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            # 初始化跟踪器 (每个class_id一个tracker)
            trackers = []
            thresholds = [0.8, 0.9, 0.8, 0.8, 0.8]  # tap(0), slide(5), touch(10), hold(15), touch_hold(20)
            
            for thresh in thresholds:
                tracker_args = SimpleNamespace(
                    tracker_type='botsort',
                    track_high_thresh=0.25,
                    track_low_thresh=0.1,
                    new_track_thresh=0.25,
                    track_buffer=10,
                    match_thresh=thresh,
                    fuse_score=True,
                    gmc_method='none',
                    proximity_thresh=0.5,
                    appearance_thresh=0.8,
                    with_reid=False,
                    model="auto"
                )
                trackers.append(BOTSORT(args=tracker_args, frame_rate=fps))
            
            # 存储追踪结果
            track_history = defaultdict(list)
            track_last_seen = defaultdict(int)
            hidden_tracks = defaultdict(lambda: {'history': [], 'last_seen': 0})
            track_status = defaultdict(lambda: 'active')
            final_tracks = defaultdict(lambda: {'class_id': None, 'path': []})
            
            # 按帧号分组检测结果
            frame_detections = defaultdict(list)
            for detection in detect_results:
                frame_detections[detection['frame']].append(detection)
            
            # 逐帧处理
            start_time = time.time()
            
            for frame_number in range(total_frames):
                ret, frame = cap.read()
                if not ret:
                    break
                
                # 获取当前帧的检测结果
                current_detections = frame_detections.get(frame_number, [])
                
                # 按class_id分组检测结果
                candidates = {0: np.empty((0, 6)), 1: np.empty((0, 6)), 2: np.empty((0, 6)), 3: np.empty((0, 6)), 4: np.empty((0, 6))}
                
                for detection in current_detections:
                    class_id = detection['class_id']
                    
                    # 映射class_id到tracker索引
                    if class_id == 0:  # tap
                        tracker_idx = 0
                    elif class_id == 5:  # slide
                        tracker_idx = 1
                    elif class_id == 10:  # touch
                        tracker_idx = 2
                    elif class_id == 15:  # hold
                        tracker_idx = 3
                    elif class_id == 20:  # touch-hold
                        tracker_idx = 4
                    else:
                        continue
                    
                    # 对于hold和touch-hold，将OBB转换为外接矩形
                    if class_id in [15, 20]:
                        x_coords = [detection['x1'], detection['x2'], detection['x3'], detection['x4']]
                        y_coords = [detection['y1'], detection['y2'], detection['y3'], detection['y4']]
                        x1 = min(x_coords)
                        y1 = min(y_coords)
                        x2 = max(x_coords)
                        y2 = max(y_coords)
                    else:
                        x1, y1, x2, y2 = detection['x1'], detection['y1'], detection['x2'], detection['y2']
                    
                    # 添加到候选框，使用tracker索引作为class_id传递给tracker
                    box_data = np.array([[x1, y1, x2, y2, detection['confidence'], tracker_idx]])
                    candidates[tracker_idx] = np.vstack([candidates[tracker_idx], box_data]) if candidates[tracker_idx].size > 0 else box_data
                
                # 执行追踪
                track_results = []
                orig_shape = frame.shape[:2]
                
                for i in range(len(trackers)):
                    if candidates[i].size > 0:
                        boxes = Boxes(candidates[i], orig_shape)
                        track_result = trackers[i].update(boxes, frame)
                        track_results.append(track_result)
                    else:
                        track_results.append([])
                
                # 处理追踪结果
                current_track_ids = set()
                
                for tracker_idx, track_result in enumerate(track_results):
                    if track_result is not None and len(track_result) > 0:
                        for track in track_result:
                            if len(track) < 7:
                                continue
                            x1, y1, x2, y2, track_id, conf, class_id = track[:7]
                            x1, y1, x2, y2, track_id, class_id = round(x1), round(y1), round(x2), round(y2), round(track_id), round(class_id)
                            
                            # 根据tracker索引映射回正确的class_id
                            if tracker_idx == 0:  # tap
                                mapped_class_id = 0
                            elif tracker_idx == 1:  # slide
                                mapped_class_id = 5
                            elif tracker_idx == 2:  # touch
                                mapped_class_id = 10
                            elif tracker_idx == 3:  # hold
                                mapped_class_id = 15
                            elif tracker_idx == 4:  # touch-hold
                                mapped_class_id = 20
                            else:
                                continue
                            
                            # 记录当前帧中存在的轨迹ID
                            current_track_ids.add(track_id)
                            
                            # 找到对应的原始检测结果作为OBB坐标
                            original_detection = None
                            min_distance = float('inf')
                            # 获取当前追踪框的中心点
                            track_center_x = (x1 + x2) / 2
                            track_center_y = (y1 + y2) / 2
                            # 找到中心点相距最小的音符
                            for detection in current_detections:
                                if detection['class_id'] == mapped_class_id:
                                    # 计算中心点：OBB 使用四点平均，其他类型使用矩形中心
                                    if mapped_class_id in [15, 20]:
                                        detection_center_x = (detection['x1'] + detection['x2'] + detection['x3'] + detection['x4']) / 4
                                        detection_center_y = (detection['y1'] + detection['y2'] + detection['y3'] + detection['y4']) / 4
                                    else:
                                        detection_center_x = (detection['x1'] + detection['x2']) / 2
                                        detection_center_y = (detection['y1'] + detection['y2']) / 2
                                    # 计算中心点距离
                                    distance = np.sqrt((track_center_x - detection_center_x)**2 + (track_center_y - detection_center_y)**2)
                                    # 选择距离最近的检测结果
                                    if distance < min_distance:
                                        min_distance = distance
                                        original_detection = detection
                            
                            # 如果找到匹配的检测结果，且距离在合理范围内
                            if original_detection and min_distance < video_width / 10:  # 最大允许距离
                                # 添加到最终轨迹数据
                                final_tracks[track_id]['class_id'] = mapped_class_id
                                final_tracks[track_id]['path'].append({
                                    'frame': frame_number,
                                    'x1': original_detection['x1'],
                                    'y1': original_detection['y1'],
                                    'x2': original_detection['x2'],
                                    'y2': original_detection['y2'],
                                    'x3': original_detection['x3'],
                                    'y3': original_detection['y3'],
                                    'x4': original_detection['x4'],
                                    'y4': original_detection['y4']
                                })
                            
                            # 更新轨迹状态
                            if track_status[track_id] == 'hidden':
                                track_history[track_id] = hidden_tracks[track_id]['history'].copy()
                                track_status[track_id] = 'active'
                                del hidden_tracks[track_id]
                            
                            track_last_seen[track_id] = frame_number
                            track_status[track_id] = 'active'
                            
                            # 存储轨迹点
                            center_x = (x1 + x2) // 2
                            center_y = (y1 + y2) // 2
                            track_history[track_id].append((center_x, center_y))
                            
                            if len(track_history[track_id]) > 512:
                                track_history[track_id].pop(0) # 限制历史长度，节约内存
                
                # 显示进度
                if frame_number % 30 == 0:
                    progress = (frame_number / total_frames) * 100
                    elapsed_time = time.time() - start_time
                    fps_rate = frame_number / elapsed_time if elapsed_time > 0 else 0
                    print(f"追踪进度: {frame_number}/{total_frames} ({progress:.1f}%) {fps_rate:.1f}fps", end="\r", flush=True)
            
            cap.release()
            
            # 保存追踪结果到文件
            self._save_track_results(final_tracks, output_dir)
            
            elapsed_time = time.time() - start_time
            average_fps = total_frames / elapsed_time if elapsed_time > 0 else 0
            print(f"追踪完成，平均FPS: {average_fps:.2f}")
            
            # 返回track_id到class_id的映射，用于后续处理
            track_info = {track_id: data['class_id'] for track_id, data in final_tracks.items() if data['class_id'] is not None}
            return track_info
            
        except Exception as e:
            raise Exception(f"追踪模块错误: {e}")
    
    def _save_track_results(self, tracks, output_dir):
        """保存追踪结果到txt文件"""
        track_result_path = os.path.join(output_dir, "track_result.txt")
        
        with open(track_result_path, 'w', encoding='utf-8') as f:
            for track_id, track_data in tracks.items():
                if track_data['class_id'] is not None and len(track_data['path']) > 0:
                    # 写入轨迹头
                    f.write(f"track_id: {track_id}, class_id: {track_data['class_id']}\n")
                    
                    # 写入轨迹路径
                    for point in track_data['path']:
                        f.write(f"{point['frame']}, {point['x1']:.2f}, {point['y1']:.2f}, "
                               f"{point['x2']:.2f}, {point['y2']:.2f}, {point['x3']:.2f}, {point['y3']:.2f}, "
                               f"{point['x4']:.2f}, {point['y4']:.2f}\n")
                    
                    f.write('\n')  # 轨迹之间空行分隔
        
        print(f"追踪结果已保存到: {track_result_path}")
    
    def _load_track_results(self, output_dir):
        """从txt文件加载追踪结果"""
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
                    if len(parts) == 9:
                        point = {
                            'frame': int(parts[0].strip()),
                            'x1': float(parts[1].strip()),
                            'y1': float(parts[2].strip()),
                            'x2': float(parts[3].strip()),
                            'y2': float(parts[4].strip()),
                            'x3': float(parts[5].strip()),
                            'y3': float(parts[6].strip()),
                            'x4': float(parts[7].strip()),
                            'y4': float(parts[8].strip())
                        }
                        tracks[current_track_id]['path'].append(point)
        
        return tracks

    def export_video_module(self, input_path, output_dir):
        """导出视频模块：绘制轨迹线并导出视频"""
        print("开始导出视频模块...")
        
        try:
            # 加载追踪结果
            track_results = self._load_track_results(output_dir)
            
            # 获取视频信息
            cap = cv2.VideoCapture(input_path)
            video_width = round(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            video_height = round(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = round(cap.get(cv2.CAP_PROP_FPS))
            total_frames = round(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            # 输出视频设置
            video_name = os.path.basename(input_path).rsplit('.', 1)[0]
            output_path = os.path.join(output_dir, f'{video_name}_tracked.mp4')
            if os.path.exists(output_path):
                os.remove(output_path)
            
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, (video_width, video_height))
            
            # 为不同ID生成不同颜色
            def get_color_for_id(track_id):
                color_pool = [
                    (0, 255, 255), (255, 0, 255), (255, 255, 0),
                    (128, 255, 255), (255, 128, 255), (255, 255, 128),
                    (255, 0, 0), (0, 255, 0), (0, 0, 255),
                    (255, 128, 128), (128, 255, 128), (128, 128, 255),
                    (128, 128, 128)
                ]
                # 使用track_id对颜色池长度取模来选择颜色
                color_index = track_id % len(color_pool)
                return color_pool[color_index]
            
            # 按帧号组织轨迹点
            frame_tracks = defaultdict(list)
            for track_id, track_data in track_results.items():
                if track_data['class_id'] is not None:
                    for point in track_data['path']:
                        frame_tracks[point['frame']].append({
                            'track_id': track_id,
                            'class_id': track_data['class_id'],
                            'x1': point['x1'],
                            'y1': point['y1'],
                            'x2': point['x2'],
                            'y2': point['y2'],
                            'x3': point['x3'],
                            'y3': point['y3'],
                            'x4': point['x4'],
                            'y4': point['y4']
                        })
            
            # 存储轨迹历史用于绘制轨迹线
            track_history = defaultdict(list)
            track_last_seen = defaultdict(int)  # 记录轨迹最后出现的帧号
            
            # 逐帧处理
            start_time = time.time()
            last_start_time = start_time
            last_frame_number = 0
            
            for frame_number in range(total_frames):
                ret, frame = cap.read()
                if not ret:
                    break
                
                # 获取当前帧的轨迹点
                current_tracks = frame_tracks.get(frame_number, [])
                
                # 更新当前帧中存在的轨迹
                current_track_ids = set()
                
                # 绘制当前帧的音符
                for track in current_tracks:
                    track_id = track['track_id']
                    class_id = track['class_id']
                    color = get_color_for_id(track_id)
                    
                    # 记录当前帧中存在的轨迹
                    current_track_ids.add(track_id)
                    
                    # 根据class_id绘制不同类型的音符
                    if class_id in [15, 20]:  # hold, touch-hold: 绘制OBB
                        points = np.array([
                            [track['x1'], track['y1']],
                            [track['x2'], track['y2']],
                            [track['x3'], track['y3']],
                            [track['x4'], track['y4']]
                        ], dtype=np.int32)
                        cv2.polylines(frame, [points], True, color, 2)
                    else:  # tap, slide, touch: 绘制矩形
                        x1, y1, x2, y2 = int(track['x1']), int(track['y1']), int(track['x2']), int(track['y2'])
                        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                    
                    # 绘制标签
                    class_names = {0: 'tap', 5: 'slide', 10: 'touch', 15: 'hold', 20: 'touch-hold'}
                    class_name = class_names.get(class_id, 'unknown')
                    label = f'{class_name} ID:{track_id}'
                    label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
                    
                    if class_id in [15, 20]:
                        # 找到OBB四个点中最上方的点作为标签位置；若y相同则选择x最小
                        points = [
                            (int(track['x1']), int(track['y1'])),
                            (int(track['x2']), int(track['y2'])),
                            (int(track['x3']), int(track['y3'])),
                            (int(track['x4']), int(track['y4']))
                        ]
                        label_x, label_y = min(points, key=lambda p: (p[1], p[0])) # 先选y最小，再选x最小
                    else:
                        label_x = x1
                        label_y = y1
                    
                    cv2.rectangle(frame, (label_x, label_y - label_size[1] - 10), 
                                (label_x + label_size[0], label_y), color, -1)
                    cv2.putText(frame, label, (label_x, label_y - 5), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                    
                    # 更新轨迹历史
                    # 计算中心点：OBB 使用四点平均，其他类型使用矩形中心
                    if class_id in [15, 20]:
                        center_x = int(round((track['x1'] + track['x2'] + track['x3'] + track['x4']) / 4.0))
                        center_y = int(round((track['y1'] + track['y2'] + track['y3'] + track['y4']) / 4.0))
                    else:
                        center_x = int(round((track['x1'] + track['x2']) / 2.0))
                        center_y = int(round((track['y1'] + track['y2']) / 2.0))

                    track_history[track_id].append((center_x, center_y))
                    track_last_seen[track_id] = frame_number
                    
                    if len(track_history[track_id]) > 512:
                        track_history[track_id].pop(0)
                
                # 清理过期的轨迹（超过30帧未出现）
                tracks_to_remove = []
                for track_id in list(track_history.keys()):
                    if track_id not in current_track_ids:
                        frames_since_last_seen = frame_number - track_last_seen.get(track_id, frame_number)
                        if frames_since_last_seen > 30:  # 超过30帧未出现，清理轨迹
                            tracks_to_remove.append(track_id)
                
                for track_id in tracks_to_remove:
                    if track_id in track_history:
                        del track_history[track_id]
                    if track_id in track_last_seen:
                        del track_last_seen[track_id]
                
                # 绘制轨迹线
                for track_id, points in track_history.items():
                    if len(points) > 1:
                        color = get_color_for_id(track_id)
                        for i in range(1, len(points)):
                            cv2.line(frame, points[i-1], points[i], color, 3)
                        
                        # 在轨迹起点绘制小圆点
                        if points:
                            cv2.circle(frame, points[0], 3, color, -1)
                
                # 写入输出视频
                out.write(frame)
                
                # 显示进度
                if frame_number % 30 == 0:
                    progress = (frame_number / total_frames) * 100
                    end_time = time.time()
                    elapsed_time = end_time - last_start_time
                    elapsed_frame = frame_number - last_frame_number
                    last_start_time = end_time # 重置时间给下一轮
                    last_frame_number = frame_number # 重置帧数给下一轮
                    fps_rate = elapsed_frame / elapsed_time if elapsed_time > 0 else 0
                    print(f"导出进度: {frame_number}/{total_frames} ({progress:.1f}%) {fps_rate:.1f}fps", end="\r", flush=True)
            
            cap.release()
            out.release()
            
            # 使用ffmpeg添加音频
            final_output_path = output_path.replace('.mp4', '_with_audio.mp4')
            if os.path.exists(final_output_path):
                os.remove(final_output_path)
            # 构建ffmpeg命令来合并视频和音频
            audio_cmd = [
                'ffmpeg', '-y',
                '-i', output_path, # 无声的跟踪视频
                '-i', input_path,  # 原始视频（有音频）
                '-c:v', 'copy',    # 复制视频流
                '-c:a', 'copy',    # 复制音频流
                '-map', '0:v:0',   # 使用第一个输入的视频流
                '-map', '1:a:0',   # 使用第二个输入的音频流
                '-shortest',       # 以最短的流为准
                final_output_path
            ]
            
            try:
                result = subprocess.run(audio_cmd, capture_output=True, text=True, encoding='utf-8')
                if result.returncode == 0:
                    os.remove(output_path)
                else:
                    raise Exception(result.stderr)
            except Exception as e:
                print(f"Warning: Error adding audio - {e}")
                os.rename(output_path, final_output_path)
            
            # 复制原始视频到输出目录
            original_video_path = os.path.join(output_dir, f'{video_name}.mp4')
            if os.path.exists(original_video_path):
                os.remove(original_video_path)
            shutil.copy(input_path, original_video_path)
            
            elapsed_time = time.time() - start_time
            average_fps = total_frames / elapsed_time if elapsed_time > 0 else 0
            print(f"视频导出完成，平均FPS: {average_fps:.2f}               ")
            print(f"视频文件已保存到：{final_output_path}")
            
            return final_output_path
            
        except Exception as e:
            raise Exception(f"视频导出模块错误: {e}")

    def main(self, video_path, detect_model_path, obb_model_path, output_dir, detect=True):
        """主函数：协调各个模块的执行"""
        try:
            # 检查输入文件是否存在
            if not os.path.exists(video_path):
                raise FileNotFoundError(f"视频文件不存在: {video_path}")
            
            # 检查输出目录
            os.makedirs(output_dir, exist_ok=True)
            
            # 获取视频名称
            video_name = os.path.basename(video_path).rsplit('.', 1)[0]
            output_dir = os.path.join(output_dir, video_name)
            os.makedirs(output_dir, exist_ok=True)
            
            # 检测模块
            if detect:
                detect_results = self.detect_module(video_path, detect_model_path, obb_model_path, output_dir)
                # 从内存中删除检测结果以节省空间
                del detect_results
            else:
                # 检查是否存在检测结果文件
                detect_result_path = os.path.join(output_dir, "detect_result.txt")
                if not os.path.exists(detect_result_path):
                    raise FileNotFoundError(f"检测结果文件不存在: {detect_result_path}")
                print("跳过检测模块，使用已有检测结果...")
                detect_results = self._load_detect_results(output_dir)
            
            # 追踪模块
            track_results = self.track_module(video_path, output_dir)
            # 从内存中删除追踪结果以节省空间
            del track_results
            
            # 导出视频模块
            final_output_path = self.export_video_module(video_path, output_dir)
            
            return final_output_path
            
        except KeyboardInterrupt:
            print("\n中断")
        except Exception as e:
            print(f"Error in main: {e}")
            print(traceback.format_exc())


if __name__ == "__main__":
    video_path = r"D:\git\mai-chart-analyze\yolo-train\temp\DEICIDE_standardized.mp4"
    detect_model_path = r"C:\Users\ck273\Desktop\detect_varifocalloss.pt"
    obb_model_path = r"C:\Users\ck273\Desktop\obb.pt"
    output_dir = r"D:\git\mai-chart-analyze\yolo-train\runs\detect"
    detect = False  # 是否执行检测模块
    
    detector = NoteDetector()
    final_output_path = detector.main(
        video_path, 
        detect_model_path, 
        obb_model_path, 
        output_dir,
        detect=detect
    )
