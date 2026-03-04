from dataclasses import dataclass
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
import shutil
import traceback
import math


def classification_module(self, track_results, std_video_path,
                            batch_cls, inference_device,
                            cls_ex_model_path, cls_break_model_path):
    try:
        print("开始分类模块...")
        start_time = time.time()

        cap = cv2.VideoCapture(std_video_path)

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
            # 尽量选择早期的点，避免在后续长条hold时被闪烁特效干扰
            # 间距不同(2-7)，防止周期性闪烁全部采样到同一位置
            sample_positions = [10, 12, 15, 19, 24, 30, 37]
        else:
            # detect 模型，间距(7-12)
            sample_positions = [20, 27, 35, 44, 54, 65, 77]

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
                'sample_position': sample_position,
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
