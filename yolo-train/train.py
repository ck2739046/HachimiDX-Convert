"""
YOLO音符检测训练脚本
基于YOLOv11预训练模型进行音符检测的微调训练
"""

from ultralytics import YOLO
import os
import yaml
import torch

def main():
    # 检查GPU可用性和内存配置
    if torch.cuda.is_available():
        device = 0  # 使用第一个GPU
        print(f"使用GPU训练: {torch.cuda.get_device_name(0)}")
        # 利用大内存，可以使用更大的batch size
        batch_size = 32  # 增大batch size以利用40GB RAM
        print("检测到大内存(40GB)，使用优化的batch size")
    else:
        device = 'cpu'
        print("GPU不可用，使用CPU训练")
        batch_size = 8   # 即使CPU模式也可以增大batch size
    
    # 检查数据集配置
    data_config = "D:\\git\\mai-chart-analyse\\yolo-train\\datasets\\data.yaml"
    if not os.path.exists(data_config):
        print(f"错误: 未找到数据集配置文件 {data_config}")
        return
    
    # 加载预训练模型
    print("加载YOLOv11s预训练模型...")
    model = YOLO('yolo11s.pt')  # 自动下载预训练模型
    
    # 开始训练
    print("开始训练...")
    results = model.train(
        data=data_config,
        epochs=100,          # 训练轮数
        imgsz=640,          # 图像尺寸
        batch=batch_size,   # 批次大小，利用大内存
        lr0=0.01,           # 初始学习率
        patience=20,        # 早停耐心值
        save_period=10,     # 每10轮保存一次
        workers=8,          # 增加数据加载进程数以利用多核CPU和大内存
        device=device,      # 自动选择设备
        project="runs/train",  # 保存路径
        name="note_detection",  # 实验名称
        amp=True if device != 'cpu' else False,  # 在GPU上启用AMP以加速训练
        cache='ram',        # 将整个数据集缓存到RAM中以加速训练
        verbose=True,       # 详细输出
        rect=True,          # 启用矩形训练以提高效率
        mosaic=1.0,         # 启用马赛克增强
        mixup=0.2,          # 启用mixup增强
        copy_paste=0.3      # 启用copy-paste增强
    )
    
    print("训练完成！")
    print(f"最佳模型保存在: {results.save_dir}")

if __name__ == "__main__":
    main()
