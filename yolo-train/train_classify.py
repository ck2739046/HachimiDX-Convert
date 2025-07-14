from ultralytics import YOLO
import os

def train(model_name=None, dataset_name=None):

    # 设置数据集
    if dataset_name is None:
        print("未指定数据集名称")
        return
    dataset_path = os.path.join(os.path.dirname(__file__), dataset_name)
    if not os.path.exists(dataset_path):
        print(f"错误: 未找到数据集路径 {dataset_path}")
        return
    
    valid_path = os.path.join(dataset_path, 'valid')
    val_path = os.path.join(dataset_path, 'val')
    if not os.path.exists(val_path):
        if os.path.exists(valid_path):
            os.rename(valid_path, val_path)
        else:
            print(f"错误: 未找到验证集路径")
            return

    # 加载模型
    yolo_path = os.path.join(os.path.dirname(__file__), 'yolo11n-cls.pt')
    if os.path.exists(yolo_path):
        model = YOLO(yolo_path)
    else:
        print(f"错误: 未找到本地模型文件 {yolo_path}")
        model = YOLO('yolo11n-cls.pt')
    
    # 设置项目路径
    project_path = os.path.join(os.path.dirname(__file__), 'runs', 'classify')
    
    if model_name is None:
        print("未指定模型名称")
        return
    
    # 训练参数
    workers_num = 16
    batch_num = 16
    
    # 开始训练
    print("开始训练...")
    results = model.train(
        data=dataset_path,
        epochs=100,
        imgsz=224,
        batch=batch_num,
        lr0=0.01,
        patience=10,
        save_period=50,
        workers=workers_num,
        device=0,
        project=project_path,
        name=model_name,
        amp=True,
        cache=True,
        verbose=True,
        plots=False
    )
    
    print("训练完成！")
    print(f"最佳模型保存在: {results.save_dir}")
    
    return results


def main():

    model_name = 'touch_scale_classify_each'
    dataset_name = 'dataset-classify-touch-each'

    train(model_name, dataset_name)


if __name__ == "__main__":
    main()
