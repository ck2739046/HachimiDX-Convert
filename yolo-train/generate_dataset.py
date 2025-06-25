"""
数据集生成工具
使用现有的NoteDetector生成YOLO训练数据
"""

import cv2
import os
import sys
import numpy as np
from pathlib import Path

# 添加父目录到路径，以便导入NoteDetector
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'ca_modules'))

def convert_bbox_to_yolo(bbox, img_width, img_height):
    """
    将边界框转换为YOLO格式
    bbox: (x1, y1, x2, y2) - 绝对坐标
    返回: (center_x, center_y, width, height) - 相对坐标 (0-1)
    """
    x1, y1, x2, y2 = bbox
    
    # 计算中心点和宽高
    center_x = (x1 + x2) / 2
    center_y = (y1 + y2) / 2
    width = x2 - x1
    height = y2 - y1
    
    # 转换为相对坐标
    center_x_rel = center_x / img_width
    center_y_rel = center_y / img_height
    width_rel = width / img_width
    height_rel = height / img_height
    
    return center_x_rel, center_y_rel, width_rel, height_rel

def process_video_to_dataset(video_path, output_dir, max_frames=1000):
    """
    处理视频生成数据集
    """
    print(f"处理视频: {video_path}")
    print(f"输出目录: {output_dir}")
    
    # 创建输出目录
    images_dir = Path(output_dir) / "images" / "train"
    labels_dir = Path(output_dir) / "labels" / "train"
    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)
    
    # 打开视频
    cap = cv2.VideoCapture(video_path)
    frame_count = 0
    saved_count = 0
    
    # TODO: 在这里集成您的NoteDetector
    # from NoteDetector import NoteDetector
    # detector = NoteDetector()
    
    while cap.read()[0] and saved_count < max_frames:
        ret, frame = cap.read()
        if not ret:
            break
            
        frame_count += 1
        
        # 每隔几帧处理一次（避免数据过于相似）
        if frame_count % 5 != 0:
            continue
            
        # TODO: 使用NoteDetector检测音符
        # detections = detector.detect(frame)
        
        # 示例：手动创建一些假检测数据用于测试框架
        # 实际使用时请替换为您的检测结果
        detections = []  # 格式: [(class_id, x1, y1, x2, y2), ...]
        
        # 如果检测到音符，保存图片和标注
        if len(detections) > 0:
            # 保存图片
            img_filename = f"frame_{saved_count:06d}.jpg"
            img_path = images_dir / img_filename
            cv2.imwrite(str(img_path), frame)
            
            # 保存标注
            label_filename = f"frame_{saved_count:06d}.txt"
            label_path = labels_dir / label_filename
            
            img_height, img_width = frame.shape[:2]
            
            with open(label_path, 'w') as f:
                for detection in detections:
                    class_id, x1, y1, x2, y2 = detection
                    center_x, center_y, width, height = convert_bbox_to_yolo(
                        (x1, y1, x2, y2), img_width, img_height
                    )
                    f.write(f"{class_id} {center_x:.6f} {center_y:.6f} {width:.6f} {height:.6f}\n")
            
            saved_count += 1
            if saved_count % 100 == 0:
                print(f"已处理 {saved_count} 帧")
    
    cap.release()
    print(f"完成！共生成 {saved_count} 个训练样本")

def main():
    # 配置
    video_path = "../input_video.mp4"  # 请修改为您的视频路径
    output_dir = "datasets"
    max_frames = 1000
    
    if not os.path.exists(video_path):
        print(f"错误: 未找到视频文件 {video_path}")
        print("请将视频文件放在正确位置或修改路径")
        return
    
    process_video_to_dataset(video_path, output_dir, max_frames)

if __name__ == "__main__":
    main()
