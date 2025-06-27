from ultralytics import YOLO
import os
import cv2
import sys
import glob
from pathlib import Path
import time
import torch

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
    if not model_path:
        print(f"错误: 未找到训练好的模型 {model_path}")
        return
    print(f"使用模型: {model_path}")
    
    # 加载模型
    model = YOLO(model_path)
    if torch.cuda.is_available():
        model.to('cuda')
        #print(f"使用GPU: {torch.cuda.get_device_name(0)}")

    # 加载视频
    video_path = os.path.join(os.path.dirname(__file__), "input", f'{input_video}.mp4')
    output_path = os.path.join(os.path.dirname(__file__), "runs/detect")
    if not os.path.exists(video_path):
        print(f"错误: 未找到输入视频 {video_path}")
        return
    
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    fps_counter = 0
    start_time = time.time()
    fps = 0
    frame_count = 0
    batch_num = 40

    print(input_video)

    results = model.predict(
        source=video_path,
        conf=0.5,           # 置信度阈值
        iou=0.7,            # NMS IoU阈值
        save=True,          # 保存结果
        save_txt=True,      # 保存检测坐标
        save_conf=True,     # 保存置信度
        project=output_path,  # 输出目录
        name=input_video,   # 实验名称
        verbose=False,      # 关闭详细输出
        stream=True,        # 启用流式处理，可以逐帧处理
        device='cuda' if torch.cuda.is_available() else 'cpu',  # 使用GPU或CPU
        batch=batch_num,
        max_det=50,
        rect=True          # 启用矩形推理
    )

    for result in results:

        frame_count += 1
        fps_counter += 1

        if fps_counter < batch_num:
            continue

        progress = (frame_count / total_frames) * 100

        # 计算fps
        current_time = time.time()
        fps = fps_counter / (current_time - start_time)
        start_time = current_time
        fps_counter = 0

        if total_frames - frame_count < batch_num:
            print(f"\r进度: {total_frames}/{total_frames} (100.0%) {fps:.1f}fps", flush=True)
        else:
            print(f"\r进度: {frame_count}/{total_frames} ({progress:.1f}%) {fps:.1f}fps", end="", flush=True)

    print("检测完成")


def main():
    path = os.path.join(os.path.dirname(__file__), 'input')
    for file in os.listdir(path):
        if file.endswith(".mp4"):
            input_video = file[:-4]
            predict(input_video)

if __name__ == "__main__":
    input_video = "天蓋"
    #main(input_video)
    main()
