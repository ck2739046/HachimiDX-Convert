from ultralytics import YOLO
from ultralytics.models.yolo.classify import ClassificationTrainer
from ultralytics.utils.loss import FocalLoss
import os


class CustomClassificationTrainer(ClassificationTrainer):
    """自定义分类训练器，使用 Focal Loss 处理类别不平衡"""
    
    def get_model(self, cfg=None, weights=None, verbose=True):
        """获取模型并设置自定义损失函数"""
        model = super().get_model(cfg, weights, verbose)
        # 使用 Focal Loss 替换默认损失函数
        # gamma: 聚焦参数，通常设置为 2.0
        # alpha: 类别平衡参数，通常设置为 0.25
        if hasattr(model, 'criterion'):
            model.criterion = FocalLoss(gamma=2.5, alpha=0.25)
        return model


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
    yolo_path = os.path.join(os.path.dirname(__file__), 'yolo11s-cls.pt')
    if os.path.exists(yolo_path):
        model = YOLO(yolo_path)
    else:
        print(f"错误: 未找到本地模型文件 {yolo_path}")
        model = YOLO('yolo11s-cls.pt')
    
    # 设置项目路径
    project_path = os.path.join(os.path.dirname(__file__), 'runs', 'classify')
    
    if model_name is None:
        print("未指定模型名称")
        return
    
    # 训练参数
    workers_num = 10
    batch_num = 64
    
    print("使用 Focal Loss (gamma=2.0, alpha=0.25)")
    
    # 开始训练
    print("开始训练...")
    results = model.train(
        trainer=CustomClassificationTrainer,  # 始终使用自定义训练器
        data=dataset_path,
        epochs=20,
        imgsz=224,
        batch=batch_num,
        patience=10,
        workers=workers_num,
        device=0,
        project=project_path,
        name=model_name,
        amp=True,
        cache=False,
        verbose=True,
        plots=False,
        save_period=1,

        augment=True,
        compile=False,  # 本地电脑好像没法编译优化

        optimizer='AdamW',
        lr0=0.001,
        weight_decay=0.0005
    )
    
    print("训练完成！")
    print(f"最佳模型保存在: {results.save_dir}")
    
    return results


def main():

    model_name = 'break-cls'
    dataset_name = 'dataset_break_cls'

    train(model_name, dataset_name)


if __name__ == "__main__":
    main()
