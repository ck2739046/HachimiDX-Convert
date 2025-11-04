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
import sys

root = os.path.abspath(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if root not in sys.path: sys.path.insert(0, root)
import tools.path_config




original_level = LOGGER.level
LOGGER.setLevel(logging.ERROR) # 只显示错误信息，忽略 Warning

class NoteDetector:
    def __init__(self):

        # 每个大类的id范围
        # tap 0-4, slide 5-9, touch 10-14, hold 15-19, touch-hold 20+
        self.main_class_id = [0, 5, 10, 15, 20]

        # 定义具体id对应的名称
        self.class_label = {
            # tap
            0: 'Tap',
            1: 'Tap-B',
            2: 'Tap-X',
            3: 'Tap-BX',
            # slide
            5: 'Slide',
            6: 'Slide-B',
            7: 'Slide-X',
            8: 'Slide-BX',
            # touch
            10: 'Touch',
            # hold
            15: 'Hold',
            16: 'Hold-B',
            17: 'Hold-X',
            18: 'Hold-BX',
            # touch-hold
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
        
    def get_specific_class_id(self, id, isEx, isBreak):
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
        
    def get_main_class_id_from_model_output(self, model, index):
        if model == 'obb':
            if index == 0: return 3 # Hold
        else: # detect
            if index == 0: return 0 # Tap
            if index == 1: return 1 # Slide
            if index == 2: return 2 # Touch
            if index == 3: return 5 # Touch-Hold
        
    def is_obb(self, id, id_type):
        # 先从具体id转为大类id
        if id_type == 'specific':
            id = self.get_main_class_id(id)
        # 只有 Hold 是 OBB
        return id == 3

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
            cls = boxes.cls      # shape: (N, 1)
            # 批量构建字典列表
            boxes_list = [
                {
                    'frame': frame_number,
                    'class_id': int(cls[i]),
                    'x1': float(xyxy[i, 0]),  # 左上角x
                    'y1': float(xyxy[i, 1]),  # 左上角y
                    'x2': float(xyxy[i, 2]),  # 右上角x
                    'y2': float(xyxy[i, 1]),  # 右上角y
                    'x3': float(xyxy[i, 2]),  # 右下角x
                    'y3': float(xyxy[i, 3]),  # 右下角y
                    'x4': float(xyxy[i, 0]),  # 左下角x
                    'y4': float(xyxy[i, 3]),  # 左下角y
                    'r': 0.0,
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
            cls = obb.cls            # (N, 1)
            # 批量构建字典列表
            boxes_list = [
                {
                    'frame': frame_number,
                    'class_id': int(cls[i]),
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
                    f"{detection['class_id']}",
                    f"{detection['x1']:.4f}", f"{detection['y1']:.4f}",
                    f"{detection['x2']:.4f}", f"{detection['y2']:.4f}",
                    f"{detection['x3']:.4f}", f"{detection['y3']:.4f}",
                    f"{detection['x4']:.4f}", f"{detection['y4']:.4f}",
                    f"{detection['r']:.4f}",
                    f"{detection['confidence']:.4f}"
                ]
                f.write(', '.join(datas) + '\n')

        print(f"检测结果已保存到: {detect_result_path}")
    


    def _load_detect_results(self, output_dir):

        detect_result_path = os.path.join(output_dir, "detect_result.txt")
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
                            'class_id': int(parts[0].strip()),
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
