import os
from ultralytics import YOLO

def main(model_list):

    for model_path, imgsz in model_list:
        # 检查pt文件是否存在
        model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), model_path)
        if not os.path.exists(model_path):
            print(f"跳过: {model_path} 不存在")
            continue
        
        # 导出ONNX文件
        print(f"\n--正在转换: {model_path}")
        
        # 加载并导出模型
        model = YOLO(model_path)
        result_path = model.export(
            format='onnx',
            imgsz=imgsz,
            simplify=True,
            half=True,
            device=0 # gpu
        )

        print(f"\n--完成: {result_path}")

if __name__ == "__main__":
    model_list = [
        ('pt/detect.pt', 960),
        ('pt/obb.pt', 960),
        ('pt/cls-ex.pt', 224),
        ('pt/cls-break.pt', 224)
    ]
    main(model_list)
