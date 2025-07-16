from ultralytics import YOLO
import os
import cv2
import sys
import glob
from pathlib import Path
import time
import torch

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
    main()
