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




original_level = LOGGER.level
LOGGER.setLevel(logging.ERROR) # 只显示错误信息，忽略 Warning

class NoteDetector:
    def __init__(self):
        
        # 每个类型的音符可以有10个子类
        self.class_id_map = {
            # main class
            1: 'Tap',
            2: 'Slide',
            3: 'Touch',
            4: 'Hold',
            5: 'Touch-hold',
            # specific tap
            10: 'Tap',
            11: 'Tap-B',
            12: 'Tap-X',
            13: 'Tap-BX',
            # specific slide
            20: 'Slide',
            21: 'Slide-B',
            22: 'Slide-X',
            23: 'Slide-BX',
            # specific touch
            30: 'Touch',
            # specific hold
            40: 'Hold',
            41: 'Hold-B',
            42: 'Hold-X',
            43: 'Hold-BX',
            # specific touch-hold
            50: 'Touch-hold'
        }


    def get_main_class_id(self, id):
        # main class
        if 0 <= id <= 9:
            result = id
        # tap
        elif 10 <= id <= 19:
            result = 1
        # slide
        elif 20 <= id <= 29:
            result = 2
        # touch
        elif 30 <= id <= 39:
            result = 3
        # hold
        elif 40 <= id <= 49:
            result = 4
        # touch-hold
        elif 50 <= id <= 59:
            result = 5
        else:
            result = -1  # unknown

        if result != -1 and id in self.class_id_map.keys():
            return result
        else:
            return -1
        

    def get_specific_class_id(self, class_id, isEx=False, isBreak=False):
        main_class_id = self.get_main_class_id(class_id)
        # Tap
        if main_class_id == 1:
            if isEx and isBreak:
                return 13  # Tap-BX
            elif isEx:
                return 12  # Tap-X
            elif isBreak:
                return 11  # Tap-B
            else:
                return 10  # Tap
        # Slide    
        elif main_class_id == 2:
            if isEx and isBreak:
                return 23  # Slide-BX
            elif isEx:
                return 22  # Slide-X
            elif isBreak:
                return 21  # Slide-B
            else:
                return 20  # Slide
        # Touch
        elif main_class_id == 3:
            return 30  # Touch 没有子类
        # Hold    
        elif main_class_id == 4:
            if isEx and isBreak:
                return 43  # Hold-BX
            elif isEx:
                return 42  # Hold-X
            elif isBreak:
                return 41  # Hold-B
            else:
                return 40  # Hold
        elif main_class_id == 5:
            return 50  # Touch-hold 没有子类
        else:
            return -1  # unknown
        

    def get_main_class_id_from_model_output(self, model, index):
        if model == 'obb':
            if index == 0: return 4 # Hold
        else: # detect
            if index == 0: return 1 # Tap
            if index == 1: return 2 # Slide
            if index == 2: return 3 # Touch
            if index == 3: return 5 # Touch-Hold
        

    def is_obb(self, id):
        id = self.get_main_class_id(id)
        return id == 4 # 只有 Hold 是 OBB
    

    def need_cls(self, id):
        id = self.get_main_class_id(id)
        return id in [1, 2, 4]  # Tap, Slide, Hold 需要分类


    def get_imgsz(self, model_type):
        if model_type == 'detect' or model_type == 'obb':
            return 960
        else:
            return 224 # cls-ex, cls-break


    def print_progress(self, name, speed_unit, counter, total, last_time, last_counter):
        # 计算即时fps
        current_time = time.time()
        elapsed_time = current_time - last_time + 1e-6
        elapsed_counter = counter - last_counter
        speed = elapsed_counter / elapsed_time
        # 打印进度
        progress = (counter / total) * 100
        print(f"{name}进度: {counter}/{total} ({progress:.1f}%), {speed:.1f}{speed_unit}  ", end="\r", flush=True)
        return current_time, counter






    # debug
    def detect_module(self, std_video_path, output_dir,
                      batch_detect, inference_device,
                      detect_model_path, obb_model_path):
        try:
            # 获取视频信息
            cap = cv2.VideoCapture(std_video_path)
            total_frames = round(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.release()
            final_results = []
            print("开始检测模块...")

            for model_path, name in [(detect_model_path, 'detect'), (obb_model_path, 'obb')]:
                counter = 0
                last_counter = 0
                start_time = time.time()
                last_time = start_time
                # 模型推理
                model = YOLO(model_path)
                imgsz = self.get_imgsz(name)
                yolo_results_generator = model.predict(
                    source=std_video_path,
                    task=name,
                    stream=True,
                    batch=batch_detect,
                    device=inference_device,
                    imgsz=imgsz,
                    max_det=50,
                    verbose=False,
                    half=True
                )
                # 流式输出后处理
                for result in yolo_results_generator:
                    # 转换数据格式并保存
                    converted_detections = self._convert_detections(result, counter, name)
                    final_results.extend(converted_detections)
                    # 打印进度
                    counter += 1
                    if counter % 40 == 0:
                        last_time, last_counter = self.print_progress(f'{name}模型', 'fps', counter, total_frames, last_time, last_counter)
                # 结束
                finish_time = time.time()
                print(f"{name}模型完成, 耗时{finish_time - start_time:.1f}s, 平均{total_frames / (finish_time - start_time):.1f}fps          ")

            # 保存到文件
            final_results = sorted(final_results, key=lambda x: x['frame'])
            self._save_detect_results(final_results, output_dir)
            return final_results

        except Exception as e:
            print(f"Error in detect_module: {e}")
            print(traceback.format_exc())
            return None



    def _convert_detections(self, result, frame_number, model_name):
        if model_name == 'detect':
            # 转换detect模型结果
            if result.boxes is None or len(result.boxes) == 0:
                return []
            # 转换为numpy批量获取数据
            boxes = result.boxes.cpu().numpy()
            xyxy = boxes.xyxy    # shape: (N, 4) 
            conf = boxes.conf    # shape: (N, 1)
            raw_cls = boxes.cls  # shape: (N, 1)
            # 批量构建字典列表
            boxes_list = [
                {
                    'frame': frame_number,
                    'main_class_id': self.get_main_class_id_from_model_output(model_name, raw_cls[i]),
                    'x1': float(xyxy[i, 0]),  # 左上角x
                    'y1': float(xyxy[i, 1]),  # 左上角y
                    'x2': float(xyxy[i, 2]),  # 右上角x
                    'y2': float(xyxy[i, 1]),  # 右上角y
                    'x3': float(xyxy[i, 2]),  # 右下角x
                    'y3': float(xyxy[i, 3]),  # 右下角y
                    'x4': float(xyxy[i, 0]),  # 左下角x
                    'y4': float(xyxy[i, 3]),  # 左下角y
                    'r': -273,                # 占位符
                    'confidence': float(conf[i])  # 置信度
                }
                for i in range(len(boxes))
            ]
            return boxes_list
        else:
            # 转换obb模型结果
            if result.obb is None or len(result.obb) == 0:
                return [] 
            # 转换为numpy批量获取数据
            obb = result.obb.cpu().numpy()
            xyxyxyxy = obb.xyxyxyxy  # (N, 4, 2) -> N个框，每个框4个点，每个点(x,y)
            xywhr = obb.xywhr        # (N, 5)    -> N个框，每个框(x_center, y_center, w, h, r)
            conf = obb.conf          # (N, 1)
            raw_cls = obb.cls        # (N, 1)
            # 批量构建字典列表
            boxes_list = [
                {
                    'frame': frame_number,
                    'main_class_id': self.get_main_class_id_from_model_output(model_name, raw_cls[i]),
                    'x1': float(xyxyxyxy[i, 0, 0]),  # 第1个点的x坐标
                    'y1': float(xyxyxyxy[i, 0, 1]),  # 第1个点的y坐标
                    'x2': float(xyxyxyxy[i, 1, 0]),  # 第2个点的x坐标
                    'y2': float(xyxyxyxy[i, 1, 1]),  # 第2个点的y坐标
                    'x3': float(xyxyxyxy[i, 2, 0]),  # 第3个点的x坐标
                    'y3': float(xyxyxyxy[i, 2, 1]),  # 第3个点的y坐标
                    'x4': float(xyxyxyxy[i, 3, 0]),  # 第4个点的x坐标
                    'y4': float(xyxyxyxy[i, 3, 1]),  # 第4个点的y坐标
                    'r': float(xywhr[i, 4]),         # xywhr的第五个值
                    'confidence': float(conf[i])
                }
                for i in range(len(obb))
            ]
            return boxes_list



    def _save_detect_results(self, detections, output_dir):
        detect_result_path = os.path.join(output_dir, "detect_result.txt")
        
        with open(detect_result_path, 'w', encoding='utf-8') as f:
            current_frame = -1
            for detection in detections:
                # 写入新的帧号
                if detection['frame'] != current_frame:
                    f.write(f"frame: {detection['frame']}\n")
                    current_frame = detection['frame']
                # 写入音符数据
                datas = [
                    f"{detection['main_class_id']}",
                    f"{detection['x1']:.4f}", f"{detection['y1']:.4f}",
                    f"{detection['x2']:.4f}", f"{detection['y2']:.4f}",
                    f"{detection['x3']:.4f}", f"{detection['y3']:.4f}",
                    f"{detection['x4']:.4f}", f"{detection['y4']:.4f}",
                    f"{detection['r']:.4f}",
                    f"{detection['confidence']:.4f}"
                ]
                f.write(', '.join(datas) + '\n')

        print(f"检测结果已保存到: {detect_result_path}")
    


    def _load_detect_results(self, detect_result_path):

        detections = []
        
        with open(detect_result_path, 'r', encoding='utf-8') as f:
            current_frame = -1
            for line in f:
                line = line.strip()
                if not line: continue
                
                if line.startswith('frame:'):
                    current_frame = int(line.split(':')[1].strip())
                else:
                    # 解析音符数据
                    parts = line.split(',')
                    if len(parts) == 11:
                        detection = {
                            'frame': current_frame,
                            'main_class_id': int(parts[0].strip()),
                            'x1': float(parts[1].strip()),
                            'y1': float(parts[2].strip()),
                            'x2': float(parts[3].strip()),
                            'y2': float(parts[4].strip()),
                            'x3': float(parts[5].strip()),
                            'y3': float(parts[6].strip()),
                            'x4': float(parts[7].strip()),
                            'y4': float(parts[8].strip()),
                            'r': float(parts[9].strip()),
                            'confidence': float(parts[10].strip())
                        }
                        detections.append(detection)
        
        return detections








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
                track_buffer=2,         # real buffer = fps / 30 * track_buffer
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












    # debug
    def classification_module(self, track_results, std_video_path,
                              batch_cls, inference_device,
                              cls_ex_model_path, cls_break_model_path):
        try:
            print("开始分类模块...")
            start_time = time.time()

            # 构建采样计划，这样后续读取视频时，就知道当前帧要裁剪哪些图像
            sampling_plan, total_cls_quantity = self._build_sampling_plan(track_results)
            if not sampling_plan:
                print("没有需要分类的轨迹")
                return None
            
            # 准备变量
            counter = 0
            last_counter = 0
            last_time = start_time

            cls_results_all = []
            images_batch_buffer = []

            cls_ex_model = YOLO(cls_ex_model_path)
            cls_break_model = YOLO(cls_break_model_path)
            imgsz = self.get_imgsz('cls')

            cap = cv2.VideoCapture(std_video_path)
            total_frames = round(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            crop_border = round(cap.get(cv2.CAP_PROP_FRAME_WIDTH) * 0.003)

            # 按帧读取视频，提取图像并分类
            for frame_number in range(total_frames):
                # 读取当前帧
                ret, frame = cap.read()
                if not ret: break
                # 获取当前帧的采样计划
                if frame_number not in sampling_plan.keys():
                    continue # skip
                this_frame_sample_plan = sampling_plan[frame_number]
                # 提取当前帧的所有采样图像
                cropped_images = self._extract_note_images_in_frame(frame, this_frame_sample_plan, frame_number, crop_border)
                if cropped_images is None:
                    continue
                # 写入batch
                images_batch_buffer.extend(cropped_images)

                # 如果凑满一个batch，就进行分类
                while len(images_batch_buffer) >= batch_cls:
                    # 从buffer中取出一个batch
                    consumed_batch = images_batch_buffer[:batch_cls]
                    images_batch_buffer = images_batch_buffer[batch_cls:]
                    # 分类
                    cls_results = self._classify_image_batch(consumed_batch,
                                                             cls_ex_model, cls_break_model,
                                                             inference_device, imgsz)
                    cls_results_all.extend(cls_results)
                    # 打印进度
                    counter += len(cls_results)
                    last_time, last_counter = self.print_progress('分类', ' images/s', counter, total_cls_quantity, last_time, last_counter)

                # end of frame loop


            # 视频读取完毕后，batch buffer可能有剩余的未分类图像
            if images_batch_buffer:
                cls_results = self._classify_image_batch(images_batch_buffer,
                                                         cls_ex_model, cls_break_model,
                                                         inference_device, imgsz)
                cls_results_all.extend(cls_results)

            # 根据分类结果，更新track_results
            track_results = self._merge_cls_into_track_results(track_results, cls_results_all)

            # 结束
            finish_time = time.time()
            print(f"分类模块完成, 耗时{finish_time - start_time:.1f}s                       ")
            return track_results
            
        except Exception as e:
            print(f"Error in classification_module: {e}")
            print(traceback.format_exc())
            return None
        finally:
            cap.release()



    def _build_sampling_plan(self, track_results):

        sampling_plan = defaultdict(list)
        counter = 0
        
        for track_id, track_data in track_results.items():
            # 获取class_id
            class_id = track_data.get('class_id', None)
            if class_id is None or len(track_data['path']) == 0: continue
            # 确保是main_class_id
            class_id = self.get_main_class_id(class_id)
            # 跳过不需要分类的音符
            if not self.need_cls(class_id): continue

            # 从一个音符的轨迹中选取采样点
            path_length = len(track_data['path'])
            if self.is_obb(class_id):
                sample_positions = [10, 15, 20] # 尽量选择早期的点，避免在后续长条hold时被闪烁特效干扰
            else:
                sample_positions = [25, 50, 75] # detect

            for sample_position in sample_positions:
                sample_idx = int(path_length * sample_position / 100.0)
                if sample_idx >= path_length:
                    continue
                # 获取采样点信息
                box = track_data['path'][sample_idx]
                frame_number = box['frame']
                # 写入采样计划
                sampling_plan[frame_number].append({
                    'track_id': track_id,
                    'sample_position': sample_position,  # 25/50/75
                    'box': box,
                    'class_id': class_id
                })
                counter += 1
        
        return sampling_plan, counter
    


    def _extract_note_images_in_frame(self, frame, this_frame_sample_plan, frame_number, crop_border):
        try:
            cropped_images = []

            for sample_data in this_frame_sample_plan:

                track_id = sample_data['track_id']
                sample_position = sample_data['sample_position']
                box = sample_data['box']
                class_id = sample_data['class_id']

                # 对于普通矩形框，裁剪范围就是(x1, y1, x3, y3)
                if not self.is_obb(class_id):
                    x1, y1, x2, y2 = int(box['x1']), int(box['y1']), int(box['x3']), int(box['y3'])
                    target_frame = frame

                # obb需要先将检测框和图像旋转为水平
                else:
                    # 获取检测框四个点坐标
                    points = np.array([
                        [box['x1'], box['y1']],
                        [box['x2'], box['y2']],
                        [box['x3'], box['y3']],
                        [box['x4'], box['y4']]
                    ], dtype=np.float32)
                    # 计算旋转角度
                    angle = (box['r'] * 180 / np.pi) - 90
                    # dx = box['x2'] - box['x1']
                    # dy = box['y2'] - box['y1']
                    # angle = np.arctan2(dy, dx) * 180 / np.pi
                    # 计算旋转中心
                    cx = np.mean(points[:, 0])
                    cy = np.mean(points[:, 1])
                    # 获取旋转矩阵
                    rotation_matrix = cv2.getRotationMatrix2D((cx, cy), angle, 1.0)
                    # 旋转整个图像为水平
                    target_frame = cv2.warpAffine(frame, rotation_matrix, (frame.shape[1], frame.shape[0]))
                    # 旋转四个点为水平
                    rotated_points = cv2.transform(points.reshape(1, -1, 2), rotation_matrix).reshape(-1, 2)
                    # 计算旋转后的边界框
                    x_coords = rotated_points[:, 0]
                    y_coords = rotated_points[:, 1]
                    x1, y1 = int(np.min(x_coords)), int(np.min(y_coords))
                    x2, y2 = int(np.max(x_coords)), int(np.max(y_coords))

                # 稍微扩展一圈
                x1 -= crop_border
                y1 -= crop_border
                x2 += crop_border
                y2 += crop_border
                # 裁剪范围边界检查
                x1 = max(0, x1)
                y1 = max(0, y1)
                x2 = min(target_frame.shape[1], x2)
                y2 = min(target_frame.shape[0], y2)
                if x1 >= x2 or y1 >= y2:
                    print(f"无效的裁剪区域: {frame_number}: ({x1}, {y1}), ({x2}, {y2}), is_obb={self.is_obb(class_id)}")
                    return None
                # 裁剪图像
                cropped_image = target_frame[y1:y2, x1:x2]
                # 保存信息
                cropped_data = {
                    'frame': frame_number,
                    'track_id': track_id,
                    'sample_position': sample_position,
                    'class_id': class_id,
                    'cropped_image': cropped_image
                }
                cropped_images.append(cropped_data)

            return cropped_images

        except Exception as e:
            print(f"提取第{frame_number}帧的图像时出错: {e}")
            return None
        


    def _classify_image_batch(self, consumed_batch, cls_ex_model, cls_break_model, inference_device, imgsz):

        try:
            # extract images and info
            images = [item['cropped_image'] for item in consumed_batch]
            images_info = [(item['frame'], item['track_id'], item['sample_position'], item['class_id']) for item in consumed_batch]

            # 模型推理
            ex_results = cls_ex_model.predict(
                task='classify',
                source=images,
                conf=0.5,
                verbose=False,
                device=inference_device,
                imgsz=imgsz,
                half=True
            )
            break_results = cls_break_model.predict(
                task='classify',
                source=images,
                conf=0.5,
                verbose=False,
                device=inference_device,
                imgsz=imgsz,
                half=True
            )

            # 解析yolo结果
            ex_flags = []
            for res in ex_results:
                is_ex = False
                if hasattr(res, 'probs') and res.probs is not None:
                    ex_probs = res.probs.data.cpu().numpy()
                    if len(ex_probs) >= 2: # 第一个是"no"，第二个是"yes"
                        is_ex = ex_probs[1] > ex_probs[0]
                ex_flags.append(bool(is_ex))

            break_flags = []
            for res in break_results:
                is_break = False
                if hasattr(res, 'probs') and res.probs is not None:
                    break_probs = res.probs.data.cpu().numpy()
                    if len(break_probs) >= 2: # 第一个是"no"，第二个是"yes"
                        is_break = break_probs[1] > break_probs[0]
                break_flags.append(bool(is_break))

            # reformat results
            final_cls_results = []
            for i, (frame_number, track_id, sample_position, class_id) in enumerate(images_info):
                data = {
                    'track_id': track_id,
                    'is_ex': ex_flags[i],
                    'is_break': break_flags[i],
                    'frame': frame_number,
                    'sample_position': sample_position,
                    'class_id': class_id
                }
                final_cls_results.append(data)

            return final_cls_results

        except Exception as e:
            print(f"批量分类错误: {e}")
            return None



    def _merge_cls_into_track_results(self, track_results, cls_results_all):

        # 根据分类结果is_ex, is_break计算specific_id，按track_id分组
        class_ids_by_track = defaultdict(list)
        for cls_result in cls_results_all:
            track_id = cls_result['track_id']
            is_ex = cls_result['is_ex']
            is_break = cls_result['is_break']
            class_id = cls_result['class_id']
            specific_class_id = self.get_specific_class_id(class_id, is_ex, is_break)
            class_ids_by_track[track_id].append(specific_class_id)
        
        # 每个音符有多个候选点和分类结果，采用最多的类别作为最终结果
        for track_id, class_ids in class_ids_by_track.items():
            if track_id not in track_results:
                continue
            if len(class_ids) == 0:
                continue
            
            # 统计每个class_id的出现次数
            counts = {}
            for class_id in class_ids:
                counts[class_id] = counts.get(class_id, 0) + 1
            
            max_count = max(counts.values())
            most_common = [k for k, v in counts.items() if v == max_count]
            
            if len(most_common) == 1:
                # 有明确的一个最多数
                final_class_id = most_common[0]
            else:
                # 没有明确的多数，默认is_break=False, is_ex=False
                final_class_id = self.get_specific_class_id(most_common[0], False, False)
                print(f"警告: 轨迹 {track_id} 的采样点分类结果不一致，采用默认分类 {final_class_id}")

            # 更新track_results的class_id
            track_results[track_id]['class_id'] = final_class_id

        return track_results
    











    # debug
    def export_video_module(self, track_results, std_video_path, output_dir, video_name):

        print("开始导出视频模块...")
        
        try:
            # 获取视频信息
            cap = cv2.VideoCapture(std_video_path)
            video_width = round(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            video_height = round(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = round(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            # 输出视频设置
            temp_track_video_path = os.path.join(output_dir, f'{video_name}_tracked_temp.mp4')
            if os.path.exists(temp_track_video_path):
                os.remove(temp_track_video_path)

            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(temp_track_video_path, fourcc, fps, (video_width, video_height))

            # 为不同ID生成不同颜色
            def get_color_for_id(track_id):
                color_palette = [
                    (0, 0, 190),   # RED
                    (190, 0, 0),   # BLUE
                    (0, 170, 0),   # GREEN
                    (0, 100, 200), # ORANGE
                    (200, 0, 150), # PURPLE
                    (180, 130, 0), # TEAL
                    (160, 0, 210), # MAGENTA
                    (0, 150, 160), # OLIVE
                    (40, 80, 160)  # SIENNA
                ]
                # 使用track_id对颜色池长度取模来选择颜色
                color_index = track_id % len(color_palette)
                return color_palette[color_index]
            
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
                        x1, y1, x2, y2 = int(track['x1']), int(track['y1']), int(track['x3']), int(track['y3'])
                        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                    
                    # 绘制标签
                    class_name = self.class_id_map.get(class_id, f'unknown')
                    label = f'{class_name} ID:{track_id}'
                    label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
                    
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
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                    
                    # 更新轨迹历史
                    # 计算中心点：OBB 使用四点平均，其他类型使用矩形中心
                    if self.is_obb(class_id):
                        center_x = int(round((track['x1'] + track['x2'] + track['x3'] + track['x4']) / 4.0))
                        center_y = int(round((track['y1'] + track['y2'] + track['y3'] + track['y4']) / 4.0))
                    else:
                        center_x = int(round((track['x1'] + track['x3']) / 2.0))
                        center_y = int(round((track['y1'] + track['y3']) / 2.0))

                    track_history[track_id].append((center_x, center_y))
                    track_last_seen[track_id] = frame_number
                    
                    if len(track_history[track_id]) > 512:
                        track_history[track_id].pop(0)
                
                # 清理过期的轨迹（超过0.5秒未出现）
                tracks_to_remove = []
                timeout = fps // 2
                for track_id in list(track_history.keys()):
                    if track_id not in current_track_ids:
                        frames_since_last_seen = frame_number - track_last_seen.get(track_id, frame_number)
                        if frames_since_last_seen > timeout:  # 超过0.5秒未出现，清理轨迹
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

            elapsed_time = time.time() - start_time
            average_fps = total_frames / elapsed_time if elapsed_time > 0 else 0
            print(f"临时视频导出完成，耗时{elapsed_time:.1f}s, 平均{average_fps:.2f}fps               ")

            # 使用ffmpeg添加音频并且crf压缩
            final_track_video_path = temp_track_video_path.replace('_temp.mp4', '.mp4')
            if os.path.exists(final_track_video_path):
                os.remove(final_track_video_path)
            # 构建ffmpeg命令来合并视频和音频
            ffmpeg_cmd = [
                'ffmpeg', '-y', '-hide_banner', '-stats', '-loglevel', 'error',
                '-i', temp_track_video_path, # 无声的跟踪视频
                '-i', std_video_path,  # 原始视频（有音频）
                '-c:v', 'libx264', '-crf', '24', '-pix_fmt', 'yuv420p',
                '-c:a', 'copy',    # 复制音频流
                '-map', '0:v:0',   # 使用第一个输入的视频流
                '-map', '1:a:0',   # 使用第二个输入的音频流
                '-shortest',       # 以最短的流为准
                final_track_video_path
            ]
            
            try:
                result = subprocess.run(ffmpeg_cmd, capture_output=False, text=True, encoding='utf-8')
                if result.returncode == 0:
                    os.remove(temp_track_video_path)
                else:
                    raise Exception(result.stderr)
            except Exception as e:
                print(f"Warning: Error adding audio to temp_track_video - {e}")
                os.rename(temp_track_video_path, final_track_video_path)
            
            # 复制原始视频到输出目录
            new_std_video_path = os.path.join(output_dir, f'{video_name}_standardized.mp4')
            if os.path.exists(new_std_video_path):
                os.remove(new_std_video_path)
            shutil.copy(std_video_path, new_std_video_path)

            elapsed_time = time.time() - start_time
            print(f"追踪视频导出完成，总耗时{elapsed_time:.1f}s")
            print(f"追踪视频已保存到：{final_track_video_path}")

            return final_track_video_path

        except Exception as e:
            raise Exception(f"视频导出模块错误: {e}") 
 









    # debug
    def main(self, std_video_path, output_dir,
             batch_detect, batch_cls, inference_device,
             detect_model_path, obb_model_path, cls_ex_model_path, cls_break_model_path,
             skip_detect=False, skip_cls=False, skip_export_tracked_video=False):
        try:
            # 检查输入文件
            paths = []
            for path in [std_video_path, detect_model_path, obb_model_path, cls_ex_model_path, cls_break_model_path]:
                path = os.path.abspath(path)
                path = os.path.normpath(path)
                if not os.path.exists(path):
                    raise FileNotFoundError(f"模型不存在: {path}")
                paths.append(path)
            std_video_path, detect_model_path, obb_model_path, cls_ex_model_path, cls_break_model_path = paths 
            # 检查输出目录
            output_dir = os.path.abspath(output_dir)
            output_dir = os.path.normpath(output_dir)
            os.makedirs(output_dir, exist_ok=True)
            video_name = os.path.basename(output_dir) # 使用输出目录名作为视频名称
            # 检查模型配置
            if batch_detect <= 0 or batch_cls <= 0:
                raise ValueError(f"batch_detect 或 batch_cls 参数无效, 必须大于0: batch_detect={batch_detect}, batch_cls={batch_cls}")
            inference_device = str(inference_device)
            if inference_device.lower() == 'none':
                inference_device = None

            # 检测模块
            if not skip_detect:
                detect_results = self.detect_module(std_video_path, output_dir,
                                                    batch_detect, inference_device,
                                                    detect_model_path, obb_model_path)
            else:
                # 如果跳过检测，使用已有的检测结果
                detect_result_path = os.path.join(output_dir, "detect_result.txt")
                if not os.path.exists(detect_result_path):
                    raise FileNotFoundError(f"检测结果文件不存在: {detect_result_path}")
                print("跳过检测模块，使用已有检测结果...")
                detect_results = self._load_detect_results(detect_result_path)


            # 追踪模块
            track_results = self.track_module(detect_results, std_video_path)
            cls_track_results = track_results.copy()

            # 分类模块
            if not skip_cls:
                cls_track_results = self.classification_module(cls_track_results, std_video_path,
                                                               batch_cls, inference_device,
                                                               cls_ex_model_path, cls_break_model_path)
            else:
                print("跳过分类模块")


            # 保存最终追踪结果
            if not skip_cls and cls_track_results is not None:
                final_track_results = cls_track_results
                self._save_track_results(final_track_results, output_dir, True)
            else:
                final_track_results = track_results
                self._save_track_results(final_track_results, output_dir, False)
            

            # 导出追踪视频模块
            if not skip_export_tracked_video:
                self.export_video_module(final_track_results, std_video_path, output_dir, video_name)
            else:
                print("跳过导出视频模块")


            return output_dir
            
        except KeyboardInterrupt:
            print("\n中断")
        except Exception as e:
            print(f"Error in NoteDetector.main: {e}")
            print(traceback.format_exc())




if __name__ == "__main__":

    detector = NoteDetector()
    detector.main(
        r'd:\git\aaa-HachimiDX-Convert\src\temp\ニルヴの心臓 MASTER 14.3_standardized.mp4',
        r"D:\git\aaa-HachimiDX-Convert\aaa-result\ニルヴの心臓 MASTER 14.3",
        2,    # batch_detect
        16,   # batch_cls
        '0',  # inference_device
        r"D:\git\aaa-HachimiDX-Convert\src\models\detect.engine",
        r"D:\git\aaa-HachimiDX-Convert\src\models\obb.pt",
        r"D:\git\aaa-HachimiDX-Convert\src\models\cls-ex.pt",
        r"D:\git\aaa-HachimiDX-Convert\src\models\cls-break.pt",
        skip_detect=False,               # 是否跳过检测
        skip_cls=False,                  # 是否跳过分类
        skip_export_tracked_video=False  # 是否跳过导出视频
    )
