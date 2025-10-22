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
        # 大类的id范围
        # tap 0-4, slide 5-9, touch 10-14, hold 15-19, touch-hold 20+
        self.main_class_id = [0, 5, 10, 15, 20]
        # 定义具体id对应的名称
        self.class_label = {
            0: 'Tap',
            1: 'Tap-B',
            2: 'Tap-X',
            3: 'Tap-BX',

            5: 'Slide',
            6: 'Slide-B',
            7: 'Slide-X',
            8: 'Slide-BX',

            10: 'Touch',

            15: 'Hold',
            16: 'Hold-B',
            17: 'Hold-X',
            18: 'Hold-BX',

            20: 'Touch-hold'
        }

    def get_main_class_id(self, id):
        # 映射class_id到大类
        if id >= self.main_class_id[-1]:
            return 4  # touch-hold
        elif id >= self.main_class_id[-2]:
            return 3  # hold
        elif id >= self.main_class_id[-3]:
            return 2  # touch
        elif id >= self.main_class_id[-4]:
            return 1  # slide
        else:
            return 0  # tap
        
    def is_obb(self, id):
        if self.get_main_class_id(id) in [3, 4]:  # hold, touch-hold
            return True
        else:
            return False
        
    def get_sub_class_id(self, id, isEx, isBreak):
        # Tap
        if id == 0:
            if isEx and isBreak:
                return 3  # Tap-BX
            elif isEx:
                return 2  # Tap-X
            elif isBreak:
                return 1  # Tap-B
            else:
                return 0  # Tap
        # Slide    
        elif id == 1:
            if isEx and isBreak:
                return 8  # Slide-BX
            elif isEx:
                return 7  # Slide-X
            elif isBreak:
                return 6  # Slide-B
            else:
                return 5  # Slide
        # Hold    
        elif id == 3:
            if isEx and isBreak:
                return 18  # Hold-BX
            elif isEx:
                return 17  # Hold-X
            elif isBreak:
                return 16  # Hold-B
            else:
                return 15  # Hold
        else:
            return id  # Touch and Touch-hold 没有子分类
        








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
                    max_det=50,
                    imgsz=960
                )
                
                obb_results = obb_model.predict(
                    source=frame,
                    conf=0.6,
                    iou=0.7,
                    verbose=False,
                    device='cuda' if torch.cuda.is_available() else 'cpu',
                    max_det=50,
                    imgsz=960
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
        
        # 处理YOLO检测结果
        if len(detect_results) > 0 and detect_results[0].boxes is not None:
            all_boxes = detect_results[0].boxes.data.cpu().numpy()
            
            for box in all_boxes:
                x1, y1, x2, y2, conf, class_id = box[:6]
                class_id = int(class_id)

                # 0 = Tap = 0, 1 = Slide = 5 , 2 = Touch = 10
                mapped_class_id = self.main_class_id[class_id]
                
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
        
        # 处理OBB检测结果
        if len(obb_results) > 0 and obb_results[0].obb is not None:
            obb_data = obb_results[0].obb
            xyxyxyxy = obb_data.xyxyxyxy.cpu().numpy()
            cls = obb_data.cls.cpu().numpy()
            conf = obb_data.conf.cpu().numpy()
            
            for i in range(len(xyxyxyxy)):
                points = xyxyxyxy[i]
                class_id = int(cls[i])
                
                # 3 = Hold = 15, 4 = Touch-Hold = 20
                mapped_class_id = self.main_class_id[class_id+3]
                
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
            fps = round(cap.get(cv2.CAP_PROP_FPS))
            total_frames = round(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            # 初始化跟踪器 (每个大类一个tracker)
            trackers = []
            thresholds = [0.8, 0.9, 0.8, 0.8, 0.8]  # tap, slide, touch, hold, touch_hold
            if fps>=119: track_buffer = 10
            else: track_buffer = 5
            
            for thresh in thresholds:
                tracker_args = SimpleNamespace(
                    tracker_type='botsort',
                    track_high_thresh=0.25,
                    track_low_thresh=0.1,
                    new_track_thresh=0.25,
                    track_buffer=track_buffer,
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
                    tracker_idx = self.get_main_class_id(class_id)
                    
                    # 对于hold和touch-hold，将OBB转换为外接矩形
                    if self.is_obb(class_id):
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
                                if self.get_main_class_id(detection['class_id']) == tracker_idx:
                                    # 计算中心点：OBB 使用四点平均，其他类型使用矩形中心
                                    if self.is_obb(detection['class_id']):
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
                                # 添加到最终轨迹数据，使用原始检测结果的class_id
                                final_tracks[track_id]['class_id'] = original_detection['class_id']
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
                if frame_number % 300 == 0:
                    progress = (frame_number / total_frames) * 100
                    elapsed_time = time.time() - start_time
                    fps_rate = frame_number / elapsed_time if elapsed_time > 0 else 0
                    print(f"追踪进度: {frame_number}/{total_frames} ({progress:.1f}%) {fps_rate:.1f}fps", end="\r", flush=True)
            
            cap.release()
            
            elapsed_time = time.time() - start_time
            average_fps = total_frames / elapsed_time if elapsed_time > 0 else 0
            print(f"追踪完成，平均FPS: {average_fps:.2f}")
            
            # 返回final_tracks用于后续分类处理
            return final_tracks
            
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





























    def _process_single_track(self, track_id, track_data, cap):
        """处理单个track_id：收集三个采样点的图像"""
        main_class_id = self.get_main_class_id(track_data['class_id'])
        
        # 只对tap, hold, slide进行分类 (main_class_id: 0, 1, 3)
        if main_class_id not in [0, 1, 3]:  # 0=tap, 1=slide, 3=hold
            return None, None
            
        # 选择25%, 50%, 75%三个采样点
        path_length = len(track_data['path'])
        sample_indices = [
            int(path_length * 0.25),
            int(path_length * 0.50),
            int(path_length * 0.75)
        ]
        
        # 收集三个采样点的图像
        crops = []
        for sample_idx in sample_indices:
            if sample_idx >= path_length:
                continue

            point = track_data['path'][sample_idx]
            frame_number = point['frame']

            # 读取对应帧
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ret, frame = cap.read()
            if not ret:
                continue

            # 提取图像区域
            cropped_image = self._extract_note_image(frame, point, track_data['class_id'])
            if cropped_image is None:
                continue

            crops.append(cropped_image)
        
        return crops, main_class_id



    def _determine_final_class_id(self, sample_classifications, track_data, track_id):
        """根据三个采样点的分类结果确定最终的class_id"""
        if len(sample_classifications) >= 2:
            # 选择多数
            counts = {}
            for class_id in sample_classifications:
                counts[class_id] = counts.get(class_id, 0) + 1
            
            max_count = max(counts.values())
            most_common = [k for k, v in counts.items() if v == max_count]
            
            if len(most_common) == 1:
                # 有明确的多数
                final_class_id = most_common[0]
            else:
                # 没有明确的多数，使用原本的大类class_id
                final_class_id = track_data['class_id']
                print(f"警告: 轨迹 {track_id} 的三个采样点分类结果不一致，使用原本的大类class_id: {final_class_id}")
        else:
            # 采样点不足，使用原本的大类class_id
            final_class_id = track_data['class_id']
            print(f"警告: 轨迹 {track_id} 的有效采样点不足，使用原本的大类class_id: {final_class_id}")
        
        return final_class_id



    def _process_track_batch(self, batch_track_ids, tracks, cap, cls_ex_model, cls_break_model):
        """处理一批track_id"""
        batch_images = []
        batch_track_info = []  # 存储(track_id, main_class_id)信息
        
        # 收集当前批次的所有图像
        for track_id in batch_track_ids:
            track_data = tracks[track_id]
            if track_data['class_id'] is None or len(track_data['path']) == 0:
                continue
                
            crops, main_class_id = self._process_single_track(track_id, track_data, cap)
            if crops is not None and len(crops) > 0:
                batch_images.extend(crops)
                # 为每个图像记录对应的track_id和main_class_id
                for _ in range(len(crops)):
                    batch_track_info.append((track_id, main_class_id))
        
        # 初始化track_classifications，确保即使没有图像也能正常工作
        track_classifications = defaultdict(list)
        
        # 批量分类当前批次的所有图像
        if len(batch_images) > 0:
            ex_flags, break_flags = self._classify_notes_batch(batch_images, cls_ex_model, cls_break_model)
            
            # 按track_id分组分类结果
            for i, (track_id, main_class_id) in enumerate(batch_track_info):
                if i < len(ex_flags) and i < len(break_flags):
                    is_ex = ex_flags[i]
                    is_break = break_flags[i]
                    specific_class_id = self.get_sub_class_id(main_class_id, is_ex, is_break)
                    track_classifications[track_id].append(specific_class_id)
        
        # 为每个track_id确定最终的class_id
        for track_id in batch_track_ids:
            if track_id not in track_classifications:
                continue
                
            sample_classifications = track_classifications[track_id]
            track_data = tracks[track_id]
            
            final_class_id = self._determine_final_class_id(sample_classifications, track_data, track_id)
            
            # 更新轨迹的class_id
            tracks[track_id]['class_id'] = final_class_id
        


    def classification_module(self, input_path, tracks, output_dir, cls_ex_model_path, cls_break_model_path, batch_size=20):
        """分类模块：对tap, hold, slide音符进行细分类"""
        print("开始分类模块...")
        
        try:
            # 加载分类模型
            cls_ex_model = YOLO(cls_ex_model_path)
            cls_break_model = YOLO(cls_break_model_path)
            if torch.cuda.is_available():
                cls_ex_model.to('cuda')
                cls_break_model.to('cuda')
                print(f"使用GPU: {torch.cuda.get_device_name(0)}")
            
            # 获取视频信息
            cap = cv2.VideoCapture(input_path)
            
            # 处理轨迹
            start_time = time.time()
            last_start_time = start_time
            last_processed_tracks = 0
            processed_tracks = 0
            total_tracks = len(tracks)
            
            # 批量处理：每batch_size个track_id为一组
            track_ids = list(tracks.keys())
            
            for batch_start in range(0, len(track_ids), batch_size):
                batch_end = min(batch_start + batch_size, len(track_ids))
                batch_track_ids = track_ids[batch_start:batch_end]
                
                # 处理当前批次
                self._process_track_batch(batch_track_ids, tracks, cap, cls_ex_model, cls_break_model)
                # 始终将已处理数字直接加上整个batch size
                processed_tracks += len(batch_track_ids)
                
                # 每处理一个batch后就更新速度显示
                progress = (processed_tracks / total_tracks) * 100
                end_time = time.time()
                elapsed_time = end_time - last_start_time
                elapsed_tracks = processed_tracks - last_processed_tracks
                last_start_time = end_time # 重置时间给下一轮
                last_processed_tracks = processed_tracks # 重置轨迹数给下一轮
                tracks_per_sec = elapsed_tracks / elapsed_time if elapsed_time > 0 else 0
                print(f"分类进度: {processed_tracks}/{total_tracks} ({progress:.1f}%) {tracks_per_sec:.1f}tracks/s", end="\r", flush=True)
            
            cap.release()

            # 保存追踪分类结果到文件
            self._save_track_results(tracks, output_dir)
            
            elapsed_time = time.time() - start_time
            average_fps = processed_tracks / elapsed_time if elapsed_time > 0 else 0
            print(f"检测完成，平均FPS: {average_fps:.2f}")

            return tracks
            
        except Exception as e:
            raise Exception(f"分类模块错误: {e}")
    


    def _extract_note_image(self, frame, point, class_id):
        """提取音符图像区域"""
        try:
            if self.is_obb(class_id):
                # 对于OBB，需要旋转到水平
                return self._extract_obb_image(frame, point)
            else:
                # 对于普通矩形框，直接裁剪
                x1, y1, x2, y2 = int(point['x1']), int(point['y1']), int(point['x2']), int(point['y2'])
                
                # 确保坐标在图像范围内
                x1 = max(0, x1)
                y1 = max(0, y1)
                x2 = min(frame.shape[1], x2)
                y2 = min(frame.shape[0], y2)
                
                if x1 >= x2 or y1 >= y2:
                    return None
                    
                cropped = frame[y1:y2, x1:x2]
                return cropped
                
        except Exception as e:
            print(f"提取图像错误: {e}")
            return None
    


    def _extract_obb_image(self, frame, point):
        """提取OBB图像区域并旋转到水平"""
        try:
            # 获取四个点坐标
            points = np.array([
                [point['x1'], point['y1']],
                [point['x2'], point['y2']],
                [point['x3'], point['y3']],
                [point['x4'], point['y4']]
            ], dtype=np.float32)
            
            # 计算旋转角度
            dx = point['x2'] - point['x1']
            dy = point['y2'] - point['y1']
            angle = np.arctan2(dy, dx) * 180 / np.pi
            
            # 计算旋转中心
            center_x = np.mean(points[:, 0])
            center_y = np.mean(points[:, 1])
            
            # 获取旋转矩阵
            rotation_matrix = cv2.getRotationMatrix2D((center_x, center_y), angle, 1.0)
            
            # 旋转整个图像
            rotated_frame = cv2.warpAffine(frame, rotation_matrix, (frame.shape[1], frame.shape[0]))
            
            # 旋转四个点
            rotated_points = cv2.transform(points.reshape(1, -1, 2), rotation_matrix).reshape(-1, 2)
            
            # 计算旋转后的边界框
            x_coords = rotated_points[:, 0]
            y_coords = rotated_points[:, 1]
            x1, y1 = int(np.min(x_coords)), int(np.min(y_coords))
            x2, y2 = int(np.max(x_coords)), int(np.max(y_coords))
            
            # 确保坐标在图像范围内
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(rotated_frame.shape[1], x2)
            y2 = min(rotated_frame.shape[0], y2)
            
            if x1 >= x2 or y1 >= y2:
                return None
                
            cropped = rotated_frame[y1:y2, x1:x2]
            return cropped
            
        except Exception as e:
            print(f"提取OBB图像错误: {e}")
            return None



    def _classify_notes_batch(self, images, cls_ex_model, cls_break_model):
        """对一组音符图像进行批量分类，返回两个列表：ex_flags, break_flags

        inputs:
            images: list of np.ndarray BGR images
            cls_ex_model, cls_break_model: ultralytics YOLO model instances

        returns:
            ex_flags: list of bool
            break_flags: list of bool
        """
        try:
            ex_flags = []
            break_flags = []

            # 使用ultralytics model 的 predict 支持批量输入（传入 list 或 numpy array）
            ex_results = cls_ex_model.predict(
                source=images,
                conf=0.5,
                verbose=False,
                device='cuda' if torch.cuda.is_available() else 'cpu',
                imgsz=224
            )

            break_results = cls_break_model.predict(
                source=images,
                conf=0.5,
                verbose=False,
                device='cuda' if torch.cuda.is_available() else 'cpu',
                imgsz=224
            )

            # 解析批量结果；ultralytics 返回的 results 对象按输入顺序对应
            for res in ex_results:
                is_ex = False
                if hasattr(res, 'probs') and res.probs is not None:
                    ex_probs = res.probs.data.cpu().numpy()
                    if len(ex_probs) >= 2: # 第一个是"no"，第二个是"yes"
                        is_ex = ex_probs[1] > ex_probs[0]
                ex_flags.append(bool(is_ex))

            for res in break_results:
                is_break = False
                if hasattr(res, 'probs') and res.probs is not None:
                    break_probs = res.probs.data.cpu().numpy()
                    if len(break_probs) >= 2: # 第一个是"no"，第二个是"yes"
                        is_break = break_probs[1] > break_probs[0]
                break_flags.append(bool(is_break))

            return ex_flags, break_flags

        except Exception as e:
            print(f"批量分类错误: {e}")
            # 返回全False以保证健壮性
            return [False] * len(images), [False] * len(images)


















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
                    if self.is_obb(class_id):
                        points = np.array([
                            [track['x1'], track['y1']],
                            [track['x2'], track['y2']],
                            [track['x3'], track['y3']],
                            [track['x4'], track['y4']]
                        ], dtype=np.int32)
                        cv2.polylines(frame, [points], True, color, 2)
                    else:
                        x1, y1, x2, y2 = int(track['x1']), int(track['y1']), int(track['x2']), int(track['y2'])
                        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                    
                    # 绘制标签
                    class_name = self.class_label.get(class_id, f'unknown-{class_id}')
                    label = f'{class_name} ID:{track_id}'
                    label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
                    
                    if self.is_obb(class_id):
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
                    if self.is_obb(class_id):
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



    def main(self, video_path, detect_model_path, obb_model_path, output_dir, cls_ex_model_path, cls_break_model_path, detect=True):
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
            # 分类模块
            classified_tracks = self.classification_module(video_path, track_results, output_dir, cls_ex_model_path, cls_break_model_path)
            # 从内存中删除追踪结果以节省空间
            del track_results
            del classified_tracks
            
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
    cls_ex_model_path = r"C:\Users\ck273\Desktop\cls-ex.pt"
    cls_break_model_path = r"C:\Users\ck273\Desktop\cls-break.pt"
    output_dir = r"D:\git\mai-chart-analyze\yolo-train\runs\detect"
    detect = True  # 是否执行检测模块
    
    detector = NoteDetector()
    final_output_path = detector.main(
        video_path, 
        detect_model_path, 
        obb_model_path, 
        output_dir,
        cls_ex_model_path,
        cls_break_model_path,
        detect=detect
    )
