from ultralytics import YOLO
from ultralytics.trackers import BOTSORT
import os
import cv2
import time
import torch
import numpy as np
from collections import defaultdict
from types import SimpleNamespace
from ultralytics.engine.results import OBB
from ultralytics.utils import LOGGER
import logging
import subprocess
import shutil
import traceback
import sys
import math

root = os.path.abspath(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if root not in sys.path: sys.path.insert(0, root)
import tools.path_config




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
            21: 'Slide',
            22: 'Slide-B',
            23: 'Slide-X',
            24: 'Slide-BX',
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
        

    def get_specific_class_id(self, main_class_id, isEx=False, isBreak=False):
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
    def track_module(self, detect_results, std_video_path, output_dir):
        try:
            # 获取视频信息
            cap = cv2.VideoCapture(std_video_path)
            fps = round(cap.get(cv2.CAP_PROP_FPS))
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
                    final_tracked_results[track_id]['class_id'] = original_detection['main_class_id']
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
    


    def _save_track_results(self, tracks, output_dir):

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
        
        print(f"追踪结果已保存到: {track_result_path}")



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
            if inference_device.lower() not in ['cpu', 'gpu', '0', '1', '2']:
                raise ValueError(f"inference_device 参数无效, 必须是 cpu/gpu/0/1/2: inference_device={inference_device}")


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
            track_results = self.track_module(detect_results, std_video_path, output_dir)


            # # 分类模块 (覆盖track_results)
            # if not skip_cls:
            #     track_results = self.classification_module(track_results,
            #                                                std_video_path, output_dir,
            #                                                batch_cls, inference_device,
            #                                                cls_ex_model_path, cls_break_model_path)
            # else:
            #     print("跳过分类模块")
            

            # # 导出追踪视频模块
            # if not skip_export_tracked_video:
            #     self.export_video_module(track_results, std_video_path, output_dir, video_name)
            # else:
            #     print("跳过导出视频模块")


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
