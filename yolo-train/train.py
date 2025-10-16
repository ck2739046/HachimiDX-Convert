from ultralytics import YOLO
from ultralytics.models.yolo.detect import DetectionTrainer
from ultralytics.utils.loss import FocalLoss
import os
#import random_dataset


class CustomDetectionTrainer(DetectionTrainer):
    """自定义检测训练器，使用FocalLoss处理数据集不平衡问题"""
    def get_model(self, cfg, weights):
        model = super().get_model(cfg, weights)
        # 使用FocalLoss替换默认损失函数
        # gamma: 调节难易样本的权重，越大越关注难样本
        # alpha: 调节正负样本的权重，用于处理类别不平衡
        # alpha 可以为 float 或者 list
        # 在 list时，需要为每个类别指定权重。
        # 此处例子：tap占80%, slide占15%，touch占5%
        # 权重 = 1/80%, 1/15%, 1/5% = [1.25, 6.67, 20]
        # 归一化 (三者之和为1) -> 1.25/(1.25+6.67+20), 6.67/(1.25+6.67+20), 20/(1.25+6.67+20)
        # 约等于 [0.05, 0.25, 0.7]
        model.model[-1].loss_fn = FocalLoss(gamma=2.0, alpha=[0.05, 0.25, 0.7])
        return model


def train(model_name=None):

    # 检查数据集配置
    data_config = os.path.join(os.path.dirname(__file__), 'dataset_detect', 'data.yaml')
    if not os.path.exists(data_config):
        print(f"错误: 未找到数据集配置文件 {data_config}")
        return
    
    # 加载预训练模型
    yolo_path = os.path.join(os.path.dirname(__file__), 'yolo11m.pt')
    model = YOLO(yolo_path)

    project_path = os.path.join(os.path.dirname(__file__), 'runs', 'train')

    if model_name is None:
        model_name = 'note_detect_v1'

    # 参数
    workers_num = 8
    batch_num = 4
    
    # 开始训练（使用自定义的FocalLoss训练器）
    print("开始训练（使用FocalLoss处理数据集不平衡）...")
    results = model.train(
        trainer=CustomDetectionTrainer,  # 使用自定义训练器
        data=data_config,
        epochs=100,     
        imgsz=960,        
        batch=batch_num,        
        patience=10,           
        workers=workers_num,    
        device=0,        
        project=project_path,
        name=model_name,    # 使用指定的模型名称
        amp=True,      
        cache=False,        
        verbose=True,
        plots=False,

        augment=True,
        compile=True,

        optimizer='AdamW',
        lr0=0.001,
        weight_decay=0.0005,

        rect=True,          # 启用矩形训练以提高效率
        mosaic=0.6,         # 启用马赛克增强

        hsv_h=0.02,         # HSV色调增强，适应不同光照
        hsv_s=0.2,          # HSV饱和度增强
        hsv_v=0.2           # HSV亮度增强
    )
    
    print("训练完成！")
    print(f"最佳模型保存在: {results.save_dir}")

    return results


def main():
    # 准备数据集
    #random_dataset.move_back_to_train()
    #random_dataset.move_samples_to_valid_advanced(0.2)
    
    # 开始训练
    results = train('note_detection1080_v4')
    
    # 打印训练结果
    if results:
        best_model_path = os.path.join(results.save_dir, 'weights', 'best.pt')
        print(f"\n训练完成！最佳模型路径: {best_model_path}")


if __name__ == "__main__":
    main()
