import cv2
import argparse
import os
import sys

def trim_video(input_path, output_path, start_frame, end_frame):
    """
    剪辑视频指定帧范围
    
    Args:
        input_path (str): 输入视频路径
        output_path (str): 输出视频路径
        start_frame (int): 开始帧数
        end_frame (int): 结束帧数
    """
    # 检查输入文件是否存在
    if not os.path.exists(input_path):
        print(f"错误: 输入文件 '{input_path}' 不存在")
        return False
    
    # 打开输入视频
    cap = cv2.VideoCapture(input_path)
    
    if not cap.isOpened():
        print(f"错误: 无法打开视频文件 '{input_path}'")
        return False
    
    # 获取视频属性
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    print(f"视频信息: {width}x{height}, {fps}fps, 总帧数: {total_frames}")
    
    # 验证帧范围
    if start_frame < 0 or end_frame >= total_frames or start_frame >= end_frame:
        print(f"错误: 帧范围无效 (开始:{start_frame}, 结束:{end_frame}, 总帧数:{total_frames})")
        cap.release()
        return False
    
    # 设置输出视频编码器
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    
    if not out.isOpened():
        print(f"错误: 无法创建输出文件 '{output_path}'")
        cap.release()
        return False
    
    # 跳转到开始帧
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    
    current_frame = start_frame
    frames_written = 0
    
    print(f"开始剪辑: 第{start_frame}帧到第{end_frame}帧")
    
    while current_frame <= end_frame:
        ret, frame = cap.read()
        
        if not ret:
            print(f"警告: 在第{current_frame}帧无法读取数据")
            break
        
        out.write(frame)
        frames_written += 1
        current_frame += 1
        
        # 显示进度
        if frames_written % 30 == 0:
            progress = (current_frame - start_frame) / (end_frame - start_frame + 1) * 100
            print(f"进度: {progress:.1f}% ({frames_written}帧已写入)", end='\r')
    
    # 释放资源
    cap.release()
    out.release()
    
    print(f"剪辑完成! 输出文件: '{output_path}'")
    print(f"共处理 {frames_written} 帧")
    
    return True

def main():

    input_path = r"D:\git\mai-chart-analyse\yolo-train\input\deicide_cropped.mp4"
    output_path = r"D:\git\mai-chart-analyse\yolo-train\input\deicide_trim.mp4"
    start = 400
    end = 3000

    # 执行视频剪辑
    success = trim_video(input_path, output_path, start, end)
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()