from ultralytics import YOLO
import os
import cv2
import sys
import glob
from pathlib import Path
import time
import torch
import numpy as np
from collections import defaultdict
import random

def crop_video_to_square(input_path, output_path):
    """
    将视频裁剪成正方形
    如果视频不是正方形，则从中心裁剪两边，保持较短的边长
    """
    cap = cv2.VideoCapture(input_path)
    
    # 获取视频属性
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # 如果已经是正方形，直接返回原路径
    if width == height:
        cap.release()
        return input_path
    
    # 计算裁剪尺寸和位置
    crop_size = min(width, height)
    x_offset = (width - crop_size) // 2
    y_offset = (height - crop_size) // 2
    
    print(f"视频尺寸: {width}x{height}, 裁剪为: {crop_size}x{crop_size}")
    
    # 设置输出路径
    temp_dir = os.path.dirname(output_path)
    os.makedirs(temp_dir, exist_ok=True)
    
    # 设置视频编码器
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (crop_size, crop_size))
    
    frame_count = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        # 裁剪帧
        cropped_frame = frame[y_offset:y_offset + crop_size, x_offset:x_offset + crop_size]
        out.write(cropped_frame)
        
        frame_count += 1
        if frame_count % 50 == 0:
            progress = (frame_count / total_frames) * 100
            print(f"\r裁剪: {frame_count}/{total_frames} ({progress:.1f}%)", end="", flush=True)

    print(f"\r裁剪: {frame_count}/{total_frames} (100.0%) 完成", flush=True)
    print(f"\n裁剪完成: {output_path}")
    
    cap.release()
    out.release()
    
    return output_path

def find_latest_model():

    # 查找所有匹配的训练目录
    yolo_path = os.path.join(os.path.dirname(__file__), 'runs/train/note_detection*')
    train_dirs = glob.glob(yolo_path)
    
    if not train_dirs:
        return None
    
    # 按修改时间排序，获取最新的
    latest_dir = max(train_dirs, key=os.path.getmtime)
    model_path = os.path.join(latest_dir, "weights", "best.pt")
    
    if os.path.exists(model_path):
        return model_path
    else:
        return None

def predict(input_video):

    # 自动找到最新的模型
    model_path = find_latest_model()

    # 加载视频
    original_video_path = os.path.join(os.path.dirname(__file__), "input", f'{input_video}.mp4')
    output_path = os.path.join(os.path.dirname(__file__), "runs/detect")
    
    if not os.path.exists(original_video_path):
        print(f"错误: 未找到输入视频 {original_video_path}")
        return
    
    # 检查视频尺寸，如果不是正方形则进行裁剪
    cap = cv2.VideoCapture(original_video_path)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()
    
    # 确定最终使用的视频路径
    if width != height:
        print(f"检测到非正方形视频 ({width}x{height})，正在裁剪...")
        cropped_video_path = os.path.join(os.path.dirname(__file__), "temp", f'{input_video}_cropped.mp4')
        video_path = crop_video_to_square(original_video_path, cropped_video_path)
    else:
        print(f"视频已是正方形 ({width}x{height})")
        video_path = original_video_path

    if not model_path:
        print(f"错误: 未找到训练好的模型 {model_path}")
        return
    print(f"使用模型: {model_path}")
    
    # 加载模型
    model = YOLO(model_path)
    if torch.cuda.is_available():
        model.to('cuda')
        #print(f"使用GPU: {torch.cuda.get_device_name(0)}")

    # 创建输出目录
    track_output_dir = os.path.join(output_path, f'{input_video}_temp')
    os.makedirs(track_output_dir, exist_ok=True)
    
    # 输出视频设置
    output_video_path = os.path.join(track_output_dir, f'{input_video}_tracked.mp4')
    
    # 重新获取视频信息（可能使用裁剪后的视频）
    cap = cv2.VideoCapture(video_path)
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    
    # 设置视频编码器
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_video_path, fourcc, fps, (frame_width, frame_height))
    
    # 存储轨迹信息
    track_history = defaultdict(list)
    # 存储每个轨迹最后出现的帧数
    track_last_seen = defaultdict(int)
    
    # 为不同ID生成不同颜色
    def get_color_for_id(track_id):
        # 使用track_id作为种子生成固定的颜色
        random.seed(track_id)
        return (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
    
    fps_counter = 0
    start_time = time.time()
    frame_count = 0

    print(input_video)

    # 使用track方法替代predict
    results = model.track(
        source=video_path,
        conf=0.5,           # 置信度阈值
        iou=0.7,            # NMS IoU阈值
        save=False,         # 不保存原始结果，我们自己处理
        save_txt=True,      # 保存检测坐标
        save_conf=True,     # 保存置信度
        project=output_path,  # 输出目录
        name=input_video,   # 实验名称
        verbose=False,      # 关闭详细输出
        stream=True,        # 启用流式处理
        device='cuda' if torch.cuda.is_available() else 'cpu',
        tracker="bytetrack.yaml",  # 使用ByteTrack跟踪器
        persist=True,       # 持续跟踪
        max_det=50
    )

    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # 重置到开始
    
    for result in results:
        ret, frame = cap.read()
        if not ret:
            break
            
        frame_count += 1
        fps_counter += 1

        # 处理跟踪结果
        current_track_ids = set()  # 当前帧中存在的轨迹ID
        
        if result.boxes is not None and result.boxes.id is not None:
            boxes = result.boxes.xywh.cpu()  # 获取边界框
            track_ids = result.boxes.id.int().cpu().tolist()  # 获取跟踪ID
            confidences = result.boxes.conf.float().cpu().tolist()  # 获取置信度
            
            # 绘制检测框和轨迹
            for box, track_id, conf in zip(boxes, track_ids, confidences):
                x, y, w, h = box
                
                # 计算中心点
                center_x, center_y = int(x), int(y)
                
                # 记录当前帧中存在的轨迹ID
                current_track_ids.add(track_id)
                
                # 更新轨迹最后出现的帧数
                track_last_seen[track_id] = frame_count
                
                # 存储轨迹点
                track_history[track_id].append((center_x, center_y))
                
                # 限制轨迹长度，避免内存过多
                if len(track_history[track_id]) > 30:
                    track_history[track_id].pop(0)
                
                # 获取颜色
                color = get_color_for_id(track_id)
                
                # 绘制边界框
                x1, y1 = int(x - w/2), int(y - h/2)
                x2, y2 = int(x + w/2), int(y + h/2)
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                
                # 绘制ID和置信度
                label = f'ID:{track_id} {conf:.2f}'
                label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
                cv2.rectangle(frame, (x1, y1 - label_size[1] - 10), 
                             (x1 + label_size[0], y1), color, -1)
                cv2.putText(frame, label, (x1, y1 - 5), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        
        # 清理超过10帧未出现的轨迹
        expired_tracks = []
        for track_id in list(track_history.keys()):
            if track_id not in current_track_ids:
                # 如果轨迹超过10帧未出现，则标记为过期
                if frame_count - track_last_seen.get(track_id, frame_count) > 10:
                    expired_tracks.append(track_id)
        
        # 删除过期的轨迹
        for track_id in expired_tracks:
            if track_id in track_history:
                del track_history[track_id]
            if track_id in track_last_seen:
                del track_last_seen[track_id]
        
        # 绘制所有物体的轨迹线
        for track_id, points in track_history.items():
            if len(points) > 1:
                color = get_color_for_id(track_id)
                # 绘制轨迹线
                for i in range(1, len(points)):
                    cv2.line(frame, points[i-1], points[i], color, 2)
                
                # 在轨迹起点绘制小圆点
                if points:
                    cv2.circle(frame, points[0], 3, color, -1)
        
        # 写入输出视频
        out.write(frame)

        # 显示进度
        if fps_counter >= 30:  # 每30帧更新一次进度
            progress = (frame_count / total_frames) * 100
            
            # 计算fps
            current_time = time.time()
            fps_rate = fps_counter / (current_time - start_time)
            start_time = current_time
            fps_counter = 0
            
            if total_frames - frame_count < 30:
                print(f"\r进度: {total_frames}/{total_frames} (100.0%) {fps_rate:.1f}fps", flush=True)
            else:
                print(f"\r进度: {frame_count}/{total_frames} ({progress:.1f}%) {fps_rate:.1f}fps", end="", flush=True)

    print(f"\n跟踪完成，输出视频: {output_video_path}")
    print(f"检测到 {len(track_history)} 个独特的物体轨迹")
    
    # 释放资源
    cap.release()
    out.release()
    
    # 如果使用了裁剪的临时文件，删除它以节省空间
    if video_path != original_video_path and os.path.exists(video_path):
        try:
            os.remove(video_path)
            print(f"已清理临时文件: {video_path}")
            # 清理空文件夹
            temp_dir = os.path.dirname(video_path)
            if not os.listdir(temp_dir):
                os.rmdir(temp_dir)
        except Exception as e:
            print(f"清理临时文件失败: {e}")

    # 移动tracked_video到最终输出目录
    final_output_path = os.path.join(output_path, input_video, f'{input_video}_tracked.mp4')
    os.rename(output_video_path, final_output_path)
    # 删除临时目录
    if os.path.exists(track_output_dir):
        try:
            os.rmdir(track_output_dir)
            print(f"已清理临时目录: {track_output_dir}")
        except Exception as e:
            print(f"清理临时目录失败: {e}")
    

def main(single_video=None):
    if single_video:
        predict(single_video)
        return
    path = os.path.join(os.path.dirname(__file__), 'input')
    for file in os.listdir(path):
        if file.endswith(".mp4"):
            input_video = file[:-4]
            predict(input_video)
            print()

if __name__ == "__main__":
    main('deicide_cropped')
