from ultralytics import YOLO
import os
import cv2
import time
import numpy as np
from pathlib import Path

from ...schemas.op_result import OpResult, ok, err
from .note_definition import *


def main(std_video_path: Path,
         total_frames: int,
         batch_detect: int,
         inference_device: str,
         detect_model_path: str,
         obb_model_path: str
        ) -> OpResult[None]:
    
    """
    输入:
    - std_video_path
    - batch_detect: yolo predict batch size
    - inference_device
    - detect_model_path
    - obb_model_path

    返回:
    - OpResult[None]
    """

    try:
        final_results = []
        print("Start detection...")

        for model_path, name in [(detect_model_path, 'detect'), (obb_model_path, 'obb')]:
            counter = 0
            last_counter = 0
            start_time = time.time()
            last_time = start_time

            # 模型推理
            model = YOLO(model_path, task=name)
            imgsz = get_imgsz(name)
            yolo_results_generator = model.predict(
                source=std_video_path,
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
                note_geometrys = _parse_detections_to_note_geometrys(result, counter, name)
                # 解决神秘 touch_hold 重叠问题
                # 同样的数据集训 yolo11 就不会这样
                # 可能是 yolo26 移除了 nms 导致的
                # 此处自己实现 nms 过滤
                note_geometrys = _apply_touch_hold_nms(note_geometrys)
                # 添加结果
                final_results.extend(note_geometrys)
                # 打印进度
                counter += 1
                if counter % 40 == 0:
                    last_time, last_counter = print_progress(name, 'fps', counter, total_frames, last_time, last_counter)
            
            # 结束
            finish_time = time.time()
            processed_frames = max(counter, 1)
            print(f"{name} done, time: {finish_time - start_time:.1f}s, average: {processed_frames / (finish_time - start_time):.1f}fps          ")

        # 保存到文件
        _save_detect_results(final_results, std_video_path.parent)
        return ok()

    except Exception as e:
        return err("Unexcepted error in auto_convert > detect > detect", e)



def _parse_detections_to_note_geometrys(result, frame_number, model_name):
    if model_name == 'detect':
        # 转换detect模型结果
        if result.boxes is None or len(result.boxes) == 0:
            return []
        # 转换为numpy批量获取数据
        boxes = result.boxes.cpu().numpy()
        xyxy = boxes.xyxy    # shape: (N, 4)
        xywh = boxes.xywh    # shape: (N, 4)
        conf = boxes.conf    # shape: (N, 1)
        raw_cls = boxes.cls  # shape: (N, 1)
        # 批量构建字典列表

        note_geometry_list = [
            Note_Geometry(
                frame=frame_number,
                note_type=map_model_class_to_note_type(model_name, int(raw_cls[i])),
                note_variant=NoteVariant.NORMAL, # 默认 normal
                conf=float(conf[i]),
                x1=float(xyxy[i, 0]),  # 左上角x
                y1=float(xyxy[i, 1]),  # 左上角y
                x2=float(xyxy[i, 2]),  # 右上角x
                y2=float(xyxy[i, 1]),  # 右上角y
                x3=float(xyxy[i, 2]),  # 右下角x
                y3=float(xyxy[i, 3]),  # 右下角y
                x4=float(xyxy[i, 0]),  # 左下角x
                y4=float(xyxy[i, 3]),  # 左下角y
                cx=float(xywh[i, 0]),
                cy=float(xywh[i, 1]),
                w=float(xywh[i, 2]),
                h=float(xywh[i, 3]),
                r=0.0
            )
            for i in range(len(boxes))
        ]
        return note_geometry_list
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
        note_geometry_list = [
            Note_Geometry(
                frame=frame_number,
                note_type=map_model_class_to_note_type(model_name, int(raw_cls[i])),
                note_variant=NoteVariant.NORMAL, # 默认 normal
                conf=float(conf[i]),
                x1=float(xyxyxyxy[i, 0, 0]),  # 第1个点的x坐标
                y1=float(xyxyxyxy[i, 0, 1]),  # 第1个点的y坐标
                x2=float(xyxyxyxy[i, 1, 0]),  # 第2个点的x坐标
                y2=float(xyxyxyxy[i, 1, 1]),  # 第2个点的y坐标
                x3=float(xyxyxyxy[i, 2, 0]),  # 第3个点的x坐标
                y3=float(xyxyxyxy[i, 2, 1]),  # 第3个点的y坐标
                x4=float(xyxyxyxy[i, 3, 0]),  # 第4个点的x坐标
                y4=float(xyxyxyxy[i, 3, 1]),  # 第4个点的y坐标
                cx=float(xywhr[i, 0]),
                cy=float(xywhr[i, 1]),
                w=float(xywhr[i, 2]),
                h=float(xywhr[i, 3]),
                r=float(xywhr[i, 4]),         # rotation
            )
            for i in range(len(obb))
        ]
        return note_geometry_list



def _save_detect_results(detections, output_dir):

    detections = sorted(detections, key=lambda x: x.frame) # 按帧号排序
    detect_result_path = os.path.join(output_dir, "detect_result.txt")
    
    with open(detect_result_path, 'w', encoding='utf-8') as f:
        current_frame = -1
        for detection in detections:
            # 写入新的帧号
            if detection.frame != current_frame:
                f.write(f"frame: {detection.frame}\n")
                current_frame = detection.frame
            # 写入音符数据
            data = [
                f"{detection.frame}",
                f"{detection.note_type.value}",
                f"{detection.note_variant.value}",
                f"{detection.conf:.4f}",
                f"{detection.x1:.4f}", f"{detection.y1:.4f}",
                f"{detection.x2:.4f}", f"{detection.y2:.4f}",
                f"{detection.x3:.4f}", f"{detection.y3:.4f}",
                f"{detection.x4:.4f}", f"{detection.y4:.4f}",
                f"{detection.cx:.4f}", f"{detection.cy:.4f}",
                f"{detection.w:.4f}", f"{detection.h:.4f}",
                f"{detection.r:.4f}"
            ]
            f.write(', '.join(data) + '\n')

    print(f"检测结果已保存到: {detect_result_path}")



def _load_detect_results(output_dir):

    detections = []
    detect_result_path = os.path.join(output_dir, "detect_result.txt")
    if not os.path.exists(detect_result_path):
        raise FileNotFoundError(f"文件不存在: {detect_result_path}")
    
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
                if len(parts) == 17:  # 有17个字段
                    detection = Note_Geometry(
                        frame=current_frame,
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
                    detections.append(detection)
    
    return detections


def _compute_iou(box1: Note_Geometry, box2: Note_Geometry) -> float:
    """
    计算两个矩形框的 IOU (Intersection over Union)
    使用水平包围框 (xyxy) 进行计算
    """
    # 提取边界框坐标
    x1_min, y1_min = min(box1.x1, box1.x4), min(box1.y1, box1.y2)
    x1_max, y1_max = max(box1.x2, box1.x3), max(box1.y3, box1.y4)
    
    x2_min, y2_min = min(box2.x1, box2.x4), min(box2.y1, box2.y2)
    x2_max, y2_max = max(box2.x2, box2.x3), max(box2.y3, box2.y4)
    
    # 计算交集区域
    inter_x_min = max(x1_min, x2_min)
    inter_y_min = max(y1_min, y2_min)
    inter_x_max = min(x1_max, x2_max)
    inter_y_max = min(y1_max, y2_max)
    
    # 检查是否有交集
    if inter_x_max <= inter_x_min or inter_y_max <= inter_y_min:
        return 0.0
    
    inter_area = (inter_x_max - inter_x_min) * (inter_y_max - inter_y_min)
    
    # 计算两个框的面积
    box1_area = (x1_max - x1_min) * (y1_max - y1_min)
    box2_area = (x2_max - x2_min) * (y2_max - y2_min)
    
    # 计算 IOU
    union_area = box1_area + box2_area - inter_area
    if union_area <= 0:
        return 0.0
    
    return inter_area / union_area


def _apply_touch_hold_nms(note_geometrys: list[Note_Geometry]) -> list[Note_Geometry]:
    """
    对同一帧中的 touch_hold 应用 NMS 过滤
    IOU > threshold 的重叠框中，只保留置信度最高的框
    
    Args:
        note_geometrys: 当前帧检测到的所有音符几何信息
    
    Returns:
        过滤后的音符几何信息列表
    """
    iou_threshold = 0.9

    if not note_geometrys or iou_threshold >= 1.0:
        return note_geometrys
    
    # 分离 touch_hold 和其他类型
    touch_holds = [n for n in note_geometrys if n.note_type == NoteType.TOUCH_HOLD]
    others = [n for n in note_geometrys if n.note_type != NoteType.TOUCH_HOLD]
    
    if len(touch_holds) <= 1:
        return note_geometrys
    
    # 按置信度降序排序
    touch_holds = sorted(touch_holds, key=lambda x: x.conf, reverse=True)
    
    # NMS 过滤：保留置信度最高的框，移除与之重叠的其他框
    kept_boxes = []
    suppressed = [False] * len(touch_holds)
    
    for i in range(len(touch_holds)):
        if suppressed[i]:
            continue
        
        # 保留当前框（置信度最高）
        kept_boxes.append(touch_holds[i])
        
        # 标记所有与当前框重叠的框为已抑制
        for j in range(i + 1, len(touch_holds)):
            if suppressed[j]:
                continue
            
            iou = _compute_iou(touch_holds[i], touch_holds[j])
            if iou > iou_threshold:
                suppressed[j] = True
    
    # 合并结果
    return others + kept_boxes

