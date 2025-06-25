"""
YOLO音符检测推理脚本
用于对新视频进行音符检测
"""

from ultralytics import YOLO
import os
import cv2
import sys
import glob
from pathlib import Path

def find_latest_model():
    """
    自动找到最新的训练模型
    """
    # 查找所有匹配的训练目录
    train_dirs = glob.glob("runs/train/note_detection_optimized*")
    
    if not train_dirs:
        return None
    
    # 按修改时间排序，获取最新的
    latest_dir = max(train_dirs, key=os.path.getmtime)
    model_path = os.path.join(latest_dir, "weights", "best.pt")
    
    if os.path.exists(model_path):
        return model_path
    else:
        return None

def main():
    # 自动找到最新的模型
    model_path = find_latest_model()
    
    if not model_path:
        print("错误: 未找到训练好的模型")
        print("请先运行 train.py 进行训练")
        print("查找路径: runs/train/note_detection_optimized*")
        return
    
    print(f"使用模型: {model_path}")
    
    # 加载模型
    model = YOLO(model_path)
    
    # 输入视频路径（请修改为您的视频路径）
    input_video = "input/deicide.mp4"
    
    if not os.path.exists(input_video):
        print(f"错误: 未找到输入视频 {input_video}")
        print("请将测试视频放入 input/ 目录")
        return
    
    # 开始推理
    print("开始检测...")
    
    # 获取视频总帧数用于显示进度
    cap = cv2.VideoCapture(input_video)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    print(f"视频总帧数: {total_frames}")
    
    results = model.predict(
        source=input_video,
        conf=0.5,           # 置信度阈值
        iou=0.7,            # NMS IoU阈值
        save=True,          # 保存结果
        save_txt=True,      # 保存检测坐标
        save_conf=True,     # 保存置信度
        project="runs/detect",  # 输出目录
        name="note_detection_optimized_pred",   # 实验名称
        verbose=False,      # 关闭详细输出
        stream=True         # 启用流式处理，可以逐帧处理
    )
    
    # 显示进度
    frame_count = 0
    for result in results:
        frame_count += 1
        progress = (frame_count / total_frames) * 100
        detections = len(result.boxes) if result.boxes is not None else 0
        
        # 在同一行显示进度信息
        print(f"\r进度: {frame_count}/{total_frames} ({progress:.1f}%) - 检测到 {detections} 个目标", end="", flush=True)
    
    print()  # 换行
    print("检测完成！")
    print(f"结果保存在: runs/detect/note_detection_optimized_pred/")

if __name__ == "__main__":
    main()
