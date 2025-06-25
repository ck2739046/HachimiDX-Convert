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

try:
    from NoteDetector import NoteDetector
except ImportError as e:
    print(f"无法导入NoteDetector: {e}")
    print("请确保NoteDetector.py在ca_modules目录中")
    sys.exit(1)

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


def convert_note_to_yolo_format(note, note_type, img_width, img_height):
    """
    将NoteDetector检测到的音符转换为YOLO格式
    
    Args:
        note: 音符字典，包含bbox或box_points等信息
        note_type: 音符类型 (0: tap, 1: slide, 2: hold, 3: touch)
        img_width: 图像宽度
        img_height: 图像高度
    
    Returns:
        tuple: (class_id, center_x_rel, center_y_rel, width_rel, height_rel)
    """
    if note_type in [0, 1]:  # tap_note, slide_note
        # 使用bbox格式: (x1, y1, x2, y2)
        bbox = note['bbox']
        x1, y1, x2, y2 = bbox
        
    elif note_type == 2:  # hold_note
        # 使用box_points格式，计算外接矩形
        box_points = note['box_points']
        x_coords = [point[0] for point in box_points]
        y_coords = [point[1] for point in box_points]
        x1, y1 = min(x_coords), min(y_coords)
        x2, y2 = max(x_coords), max(y_coords)
        
    elif note_type == 3:  # touch_note
        # 使用bbox格式: (x1, y1, x2, y2)
        bbox = note['bbox']
        x1, y1, x2, y2 = bbox
    
    # 转换为YOLO格式 (相对坐标)
    center_x_rel, center_y_rel, width_rel, height_rel = convert_bbox_to_yolo(
        (x1, y1, x2, y2), img_width, img_height
    )
    
    return note_type, center_x_rel, center_y_rel, width_rel, height_rel

def process_video_to_dataset(video_path, output_dir, max_frames=1000, chart_start=0, state_config=None):
    """
    处理视频生成数据集
    
    Args:
        video_path: 视频文件路径
        output_dir: 输出目录
        max_frames: 最大处理帧数
        chart_start: 谱面开始帧数
        state_config: NoteDetector需要的状态配置
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
    if not cap.isOpened():
        raise Exception(f"无法打开视频文件: {video_path}")
    
    # 获取视频信息
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    video_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    video_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    print(f"视频信息: {video_width}x{video_height}, 总帧数: {total_frames}")
    
    # 默认状态配置 (请根据实际视频调整这些参数)
    state_config = {
        'chart_start': chart_start,
        'total_frames': total_frames,
        'circle_center': state_config.get('circle_center', (video_width // 2, video_height // 2)),  # 默认圆心
        'circle_radius': state_config.get('circle_radius', min(video_width, video_height) // 4),    # 默认半径
        'video_height': video_height,
        'video_width': video_width,
        'debug': False,
        'touch_areas': state_config.get('touch_areas', {})  # 默认触摸区域
    }
    
    # 初始化NoteDetector
    print("初始化NoteDetector...")
    detector = NoteDetector()
    
    # 限制处理帧数
    limit_frame = min(chart_start + max_frames, total_frames)
    
    # 运行NoteDetector处理
    print("开始检测音符...")
    detector.process(cap, state_config, limit_frame)
    
    # 提取检测结果并生成数据集
    print("生成训练数据...")
    saved_count = 0
    
    # 设置帧采样间隔 (避免数据过于相似)
    frame_interval = 2  # 每2帧采样1帧
    
    for frame_counter in range(chart_start, limit_frame, frame_interval):
        # 重新读取这一帧的图像
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_counter)
        ret, frame = cap.read()
        if not ret:
            continue
        
        # 收集该帧的所有音符检测结果
        all_detections = []
        
        # Tap notes (类别 0)
        tap_notes = detector.tap_notes.get(frame_counter, [])
        for note in tap_notes:
            detection = convert_note_to_yolo_format(note, 0, video_width, video_height)
            all_detections.append(detection)
        
        # Slide notes (类别 1)  
        slide_notes = detector.slide_notes.get(frame_counter, [])
        for note in slide_notes:
            detection = convert_note_to_yolo_format(note, 1, video_width, video_height)
            all_detections.append(detection)
        
        # Hold notes (类别 2)
        hold_notes = detector.hold_notes.get(frame_counter, [])
        for note in hold_notes:
            detection = convert_note_to_yolo_format(note, 2, video_width, video_height)
            all_detections.append(detection)
        
        # Touch notes (类别 3)
        touch_notes = detector.touch_notes.get(frame_counter, [])
        for note in touch_notes:
            detection = convert_note_to_yolo_format(note, 3, video_width, video_height)
            all_detections.append(detection)
        
        # 只保存有音符的帧
        if len(all_detections) > 0:
            # 保存图片
            img_filename = f"frame_{saved_count:06d}.jpg"
            img_path = images_dir / img_filename
            cv2.imwrite(str(img_path), frame)
            
            # 保存标注
            label_filename = f"frame_{saved_count:06d}.txt"
            label_path = labels_dir / label_filename
            
            with open(label_path, 'w') as f:
                for detection in all_detections:
                    class_id, center_x, center_y, width, height = detection
                    # 确保坐标在有效范围内
                    center_x = max(0, min(1, center_x))
                    center_y = max(0, min(1, center_y))
                    width = max(0, min(1, width))
                    height = max(0, min(1, height))
                    
                    f.write(f"{class_id} {center_x:.6f} {center_y:.6f} {width:.6f} {height:.6f}\n")
            
            saved_count += 1
            if saved_count % 20 == 0:
                print(f"已生成 {saved_count} 个训练样本", end='\r')
    
    cap.release()
    print(f"完成！共生成 {saved_count} 个训练样本")
    print(f"图片保存在: {images_dir}")
    print(f"标注保存在: {labels_dir}")
    
    return saved_count

def create_data_splits(output_dir, train_ratio=0.8, val_ratio=0.15):
    """
    将训练数据分割为训练集、验证集和测试集
    
    Args:
        output_dir: 数据集目录
        train_ratio: 训练集比例
        val_ratio: 验证集比例
    """
    import shutil
    import random
    
    # 获取所有训练数据
    train_images_dir = Path(output_dir) / "images" / "train"
    train_labels_dir = Path(output_dir) / "labels" / "train"
    
    # 创建验证和测试目录
    val_images_dir = Path(output_dir) / "images" / "val"
    val_labels_dir = Path(output_dir) / "labels" / "val"
    test_images_dir = Path(output_dir) / "images" / "test"
    test_labels_dir = Path(output_dir) / "labels" / "test"
    
    for dir_path in [val_images_dir, val_labels_dir, test_images_dir, test_labels_dir]:
        dir_path.mkdir(parents=True, exist_ok=True)
    
    # 获取所有图片文件
    image_files = list(train_images_dir.glob("*.jpg"))
    random.shuffle(image_files)
    
    total_files = len(image_files)
    train_count = int(total_files * train_ratio)
    val_count = int(total_files * val_ratio)
    
    print(f"数据集分割: 训练集({train_count}) 验证集({val_count}) 测试集({total_files - train_count - val_count})")
    
    # 移动验证集文件
    for i in range(train_count, train_count + val_count):
        if i < total_files:
            img_file = image_files[i]
            label_file = train_labels_dir / (img_file.stem + ".txt")
            
            # 移动图片和标注
            shutil.move(str(img_file), str(val_images_dir / img_file.name))
            if label_file.exists():
                shutil.move(str(label_file), str(val_labels_dir / label_file.name))
    
    # 移动测试集文件
    for i in range(train_count + val_count, total_files):
        img_file = image_files[i]
        label_file = train_labels_dir / (img_file.stem + ".txt")
        
        # 移动图片和标注
        shutil.move(str(img_file), str(test_images_dir / img_file.name))
        if label_file.exists():
            shutil.move(str(label_file), str(test_labels_dir / label_file.name))


def main():
    # 配置参数 - 请根据您的实际情况修改
    video_path = "deicide.mp4"  # 视频文件路径
    output_dir = "yolo-train/datasets"              # 输出目录
    max_frames = 8000                    # 最大处理帧数
    chart_start = 500                      # 谱面开始帧 (请根据实际情况调整)
    touch_areas = {
        'C1': {'center': (958, 540)},
        'B1': {'center': (1043, 335)},
        'B2': {'center': (1163, 455)},
        'B3': {'center': (1163, 625)},
        'B4': {'center': (1043, 744)},
        'B5': {'center': (874, 744)},
        'B6': {'center': (754, 625)},
        'B7': {'center': (754, 455)},
        'B8': {'center': (874, 336)},
        'E1': {'center': (959, 229)},
        'E2': {'center': (1179, 320)},
        'E3': {'center': (1270, 540)},
        'E4': {'center': (1179, 759)},
        'E5': {'center': (958, 851)},
        'E6': {'center': (739, 759)},
        'E7': {'center': (648, 539)},
        'E8': {'center': (739, 320)},
        'A1': {'center': (1111, 170)},
        'A2': {'center': (1327, 387)},
        'A3': {'center': (1326, 693)},
        'A4': {'center': (1110, 908)},
        'A5': {'center': (806, 907)},
        'A6': {'center': (590, 692)},
        'A7': {'center': (589, 387)},
        'A8': {'center': (805, 170)},
        'D1': {'center': (959, 116)},
        'D2': {'center': (1258, 240)},
        'D3': {'center': (1381, 541)},
        'D4': {'center': (1257, 838)},
        'D5': {'center': (958, 962)},
        'D6': {'center': (660, 838)},
        'D7': {'center': (536, 540)},
        'D8': {'center': (659, 241)}
    }
    
    # NoteDetector状态配置 - 请根据您的视频调整这些参数
    state_config = {
        'chart_start': chart_start,
        'circle_center': (959, 539),     # 请根据实际视频中的圆圈中心调整
        'circle_radius': 474,            # 请根据实际视频中的圆圈半径调整
        'debug': False,
        'touch_areas': touch_areas
    }
    
    # 检查视频文件是否存在
    video_path = os.path.join("D:\\git\\mai-chart-analyse\\yolo-train\\input", video_path)
    if not os.path.exists(video_path):
        print(f"错误: 未找到视频文件 {video_path}")
        print("请将视频文件放在 input/ 目录中，或修改 video_path 参数")
        print("\n使用说明:")
        print("1. 将maimai视频文件放在 input/ 目录中")
        print("2. 根据视频调整 state_config 中的参数:")
        print("   - chart_start: 谱面开始的帧数")
        print("   - circle_center: 游戏圆圈的中心坐标 (x, y)")
        print("   - circle_radius: 游戏圆圈的半径")
        print("3. 运行脚本生成数据集")
        return
    
    try:
        # 生成数据集
        saved_count = process_video_to_dataset(
            video_path, output_dir, max_frames, chart_start, state_config
        )
        
        if saved_count > 0:
            print("\n正在分割数据集...")
            # 将数据分割为训练/验证/测试集
            create_data_splits(output_dir)
            print("数据集生成完成！")
            print(f"数据集位置: {output_dir}")
            print("现在可以运行 train.py 开始训练模型")
        else:
            print("未生成任何训练样本，请检查视频和配置参数")
            
    except Exception as e:
        print(f"生成数据集时出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
