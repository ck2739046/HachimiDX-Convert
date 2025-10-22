import os
from ultralytics import YOLO
import torch


def convert_models(model_paths, fp16=True, int8=False, workspace=4):
    """
    批量转换模型为TensorRT格式
    
    Args:
        model_paths (list): 要转换的模型文件路径列表
        fp16 (bool): 是否使用FP16精度
        int8 (bool): 是否使用INT8精度
        workspace (int): TensorRT工作空间大小（GB）
    """
    
    # 检查CUDA可用性
    if not torch.cuda.is_available():
        print("警告: 未检测到CUDA设备，TensorRT需要NVIDIA GPU支持")
        return

    # 检查模型文件
    valid_models = []
    for model_path in model_paths:
        if os.path.exists(model_path):
            valid_models.append(model_path)
        else:
            print(f"警告: 模型文件不存在: {model_path}")
    
    if not valid_models:
        print("错误: 没有有效的模型文件")
        return
    
    print(f"找到 {len(valid_models)} 个有效模型文件")
    
    # 转换每个模型
    for i, model_path in enumerate(valid_models, 1):
        print(f"\n[{i}/{len(valid_models)}] 处理: {os.path.basename(model_path)}")
        
        # 加载模型
        model = YOLO(model_path)
        # 设置TensorRT导出参数
        export_kwargs = {
            'format': 'engine',
            'workspace': workspace,  # 工作空间大小（GB）
            'verbose': False
        }
        # 设置精度选项
        if fp16:
            export_kwargs['half'] = True
            print("使用FP16精度")
        if int8:
            export_kwargs['int8'] = True
            print("使用INT8精度")
        # 导出为TensorRT格式
        model.export(**export_kwargs)



if __name__ == "__main__":
    # 在这里直接设置参数
    model_paths = [
        r"C:\Users\ck273\Desktop\detect_varifocalloss.pt",
        r"C:\Users\ck273\Desktop\obb.pt", 
        r"C:\Users\ck273\Desktop\cls-ex.pt",
        r"C:\Users\ck273\Desktop\cls-break.pt"
    ]
    
    fp16 = True      # 使用FP16精度
    int8 = False     # 不使用INT8精度
    workspace = 4    # TensorRT工作空间大小 GB (显存)
    
    # 执行转换
    convert_models(
        model_paths=model_paths,
        fp16=fp16,
        int8=int8,
        workspace=workspace
    )
