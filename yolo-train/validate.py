"""
YOLO音符检测验证脚本
用于验证训练好的模型效果
"""

from ultralytics import YOLO
import os

def main():
    # 模型路径（训练完成后会生成）
    model_path = "runs/train/note_detection/weights/best.pt"
    
    if not os.path.exists(model_path):
        print(f"错误: 未找到训练好的模型 {model_path}")
        print("请先运行 train.py 进行训练")
        return
    
    # 加载训练好的模型
    model = YOLO(model_path)
    
    # 在验证集上评估
    print("开始验证...")
    results = model.val(
        data="datasets/data.yaml",
        split="val",
        save_json=True,
        save_hybrid=True
    )
    
    print(f"验证完成！")
    print(f"mAP50: {results.box.map50:.4f}")
    print(f"mAP50-95: {results.box.map:.4f}")

if __name__ == "__main__":
    main()
