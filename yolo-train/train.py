"""
YOLO音符检测训练脚本
基于YOLOv11预训练模型进行音符检测的微调训练
"""

from ultralytics import YOLO
import os
import yaml

def main():
    # 检查数据集配置
    data_config = "datasets/data.yaml"
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
        batch=16,           # 批次大小，根据GPU内存调整
        lr0=0.01,           # 初始学习率
        patience=20,        # 早停耐心值
        save_period=10,     # 每10轮保存一次
        workers=4,          # 数据加载进程数
        device=0,           # GPU设备（如果有）
        project="runs/train",  # 保存路径
        name="note_detection"  # 实验名称
    )
    
    print("训练完成！")
    print(f"最佳模型保存在: {results.save_dir}")

if __name__ == "__main__":
    main()
