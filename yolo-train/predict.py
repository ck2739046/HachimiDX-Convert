"""
YOLO音符检测推理脚本
用于对新视频进行音符检测
"""

from ultralytics import YOLO
import os
import cv2

def main():
    # 模型路径
    model_path = "runs/train/note_detection/weights/best.pt"
    
    if not os.path.exists(model_path):
        print(f"错误: 未找到训练好的模型 {model_path}")
        print("请先运行 train.py 进行训练")
        return
    
    # 加载模型
    model = YOLO(model_path)
    
    # 输入视频路径（请修改为您的视频路径）
    input_video = "input/test_video.mp4"
    
    if not os.path.exists(input_video):
        print(f"错误: 未找到输入视频 {input_video}")
        print("请将测试视频放入 input/ 目录")
        return
    
    # 开始推理
    print("开始检测...")
    results = model.predict(
        source=input_video,
        conf=0.5,           # 置信度阈值
        iou=0.7,            # NMS IoU阈值
        save=True,          # 保存结果
        save_txt=True,      # 保存检测坐标
        save_conf=True,     # 保存置信度
        project="runs/detect",  # 输出目录
        name="note_detection"   # 实验名称
    )
    
    print("检测完成！")
    print("结果保存在: runs/detect/note_detection/")

if __name__ == "__main__":
    main()
