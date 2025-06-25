"""
YOLO音符检测训练脚本 - 内存优化版本
针对40GB RAM进行优化，最大化利用系统资源
"""

from ultralytics import YOLO
import os
import yaml
import torch
import psutil
import gc

def get_optimal_config():
    """根据系统资源自动配置最优参数"""
    # 获取系统信息
    total_ram = psutil.virtual_memory().total / (1024**3)  # GB
    available_ram = psutil.virtual_memory().available / (1024**3)  # GB
    cpu_count = os.cpu_count()
    
    print(f"系统RAM: {total_ram:.1f}GB (可用: {available_ram:.1f}GB)")
    print(f"CPU核心数: {cpu_count}")
    
    config = {}
    
    # 根据内存大小配置参数
    if total_ram >= 16:  # 中等内存
        config['batch_size_gpu'] = 16
        config['batch_size_cpu'] = 12
        config['workers'] = min(12, cpu_count)
        config['cache_mode'] = 'ram'
        config['prefetch_factor'] = 2
    else:  # 小内存系统
        config['batch_size_gpu'] = 16
        config['batch_size_cpu'] = 4
        config['workers'] = min(4, cpu_count)
        config['cache_mode'] = True
        config['prefetch_factor'] = 2
    
    return config

def optimize_memory():
    """内存优化设置"""
    # 启用内存映射
    torch.backends.cudnn.benchmark = True
    
    # 清理缓存
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    gc.collect()
    
    # 设置内存分配策略
    os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'max_split_size_mb:512'

def main():
    print("=== YOLO训练 - 大内存优化版本 ===")
    
    # 内存优化
    optimize_memory()
    
    # 获取最优配置
    config = get_optimal_config()
    
    # 检查GPU可用性
    if torch.cuda.is_available():
        device = 0
        gpu_name = torch.cuda.get_device_name(0)
        gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        print(f"使用GPU训练: {gpu_name}")
        print(f"GPU内存: {gpu_memory:.1f}GB")
        batch_size = config['batch_size_gpu']
    else:
        device = 'cpu'
        print("GPU不可用，使用CPU训练")
        batch_size = config['batch_size_cpu']
    
    print(f"优化配置: batch_size={batch_size}, workers={config['workers']}, cache={config['cache_mode']}")
    
    # 检查数据集配置
    data_config = "D:\\git\\mai-chart-analyse\\yolo-train\\datasets\\data.yaml"
    if not os.path.exists(data_config):
        print(f"错误: 未找到数据集配置文件 {data_config}")
        return
    
    # 加载预训练模型
    print("加载YOLOv11s预训练模型...")
    model = YOLO('yolo11s.pt')
    
    # 开始训练
    print("开始训练...")
    results = model.train(
        data=data_config,
        epochs=100,
        imgsz=640,
        batch=batch_size,
        lr0=0.01,
        patience=20,
        save_period=10,
        workers=config['workers'],
        device=device,
        project="runs/train",
        name="note_detection_optimized",
        amp=True if device != 'cpu' else False,
        cache=config['cache_mode'],  # 缓存策略
        verbose=True,
        rect=True,           # 矩形训练
        mosaic=1.0,          # 马赛克增强
        mixup=0.2,           # mixup增强
        copy_paste=0.3,      # copy-paste增强
        hsv_h=0.015,         # HSV色调增强
        hsv_s=0.7,           # HSV饱和度增强
        hsv_v=0.4,           # HSV明度增强
        degrees=10.0,        # 旋转增强
        translate=0.1,       # 平移增强
        scale=0.5,           # 缩放增强
        shear=2.0,           # 剪切增强
        perspective=0.0001,  # 透视增强
        flipud=0.5,          # 垂直翻转
        fliplr=0.5,          # 水平翻转
        # 内存优化参数
        close_mosaic=10,     # 最后10个epoch关闭mosaic
        max_det=300,         # 最大检测数量
        
        # 高级优化
        optimizer='AdamW',   # 使用AdamW优化器
        cos_lr=True,         # 余弦学习率调度
        warmup_epochs=3,     # 预热轮数
        warmup_momentum=0.8, # 预热动量
        warmup_bias_lr=0.1,  # 预热偏置学习率
        box=7.5,             # 边界框损失权重
        cls=0.5,             # 分类损失权重
        dfl=1.5,             # DFL损失权重
        pose=12.0,           # 姿态损失权重
        kobj=2.0,            # 关键点损失权重
        label_smoothing=0.0, # 标签平滑
        nbs=64,              # 名义批次大小
        overlap_mask=True,   # 重叠掩码
        mask_ratio=4,        # 掩码比率
        dropout=0.0,         # Dropout率
    )
    
    print("训练完成！")
    print(f"最佳模型保存在: {results.save_dir}")
    
    # 显示内存使用情况
    if torch.cuda.is_available():
        print(f"GPU内存使用: {torch.cuda.memory_allocated()/1024**3:.2f}GB")
        print(f"GPU内存缓存: {torch.cuda.memory_reserved()/1024**3:.2f}GB")
    
    ram_usage = psutil.virtual_memory()
    print(f"RAM使用: {(ram_usage.total - ram_usage.available)/1024**3:.2f}GB / {ram_usage.total/1024**3:.2f}GB")

if __name__ == "__main__":
    main()
