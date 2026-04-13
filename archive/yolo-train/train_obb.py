from ultralytics import YOLO
from ultralytics.models.yolo.obb import OBBTrainer
from ultralytics.utils.loss import VarifocalLoss
import os
#import random_dataset


class CustomOBBTrainer(OBBTrainer):
    """自定义 OBB 训练器，使用 VarifocalLoss 处理数据集不平衡问题"""
    
    def get_model(self, cfg=None, weights=None, verbose=True):
        """获取模型并设置自定义损失函数"""
        model = super().get_model(cfg, weights, verbose)
        # 使用 VarifocalLoss 替换默认损失函数
        # gamma: 调节难易样本的权重，越大越关注难样本（默认2.0）
        # alpha: 平衡因子，用于处理类别不平衡（默认0.75）
        if hasattr(model.model[-1], 'loss_fn'):
            model.model[-1].loss_fn = VarifocalLoss(gamma=2.0, alpha=0.75)
        return model


def train(model_name=None):

    # 检查数据集配置
    data_config = os.path.join('/root/autodl-tmp', 'dataset', 'data_obb.yaml')
    if not os.path.exists(data_config):
        print(f"错误: 未找到数据集配置文件 {data_config}")
        return
    
    # 加载预训练模型
    model = YOLO('yolo26s-obb.pt')

    project_path = os.path.join(os.path.dirname(__file__), 'result')

    if model_name is None:
        model_name = 'note_unknown'

    # 参数
    workers_num = 25
    
    # 开始训练（使用自定义的 VarifocalLoss 训练器）
    print("开始训练（使用 VarifocalLoss 处理数据集不平衡）...")
    results = model.train(
        trainer=CustomOBBTrainer,  # 使用自定义 OBB 训练器
        data=data_config,
        epochs=18,     
        imgsz=960,        
        batch=0.8,       
        patience=5,
        save_period=1,
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

        optimizer='auto',

        hsv_h=0.03,         # HSV色调增强，适应不同光照
        hsv_s=0.2,          # HSV饱和度增强
        hsv_v=0.3           # HSV亮度增强
    )
    
    print("训练完成！")
    print(f"最佳模型保存在: {results.save_dir}")

    return results


def main():
    # 准备数据集
    #random_dataset.move_back_to_train()
    #random_dataset.move_samples_to_valid_advanced(0.2)
    
    # 开始训练
    results = train('note_obb_v2')
    
    # 打印训练结果
    if results:
        best_model_path = os.path.join(results.save_dir, 'weights', 'best.pt')
        print(f"\n训练完成！最佳模型路径: {best_model_path}")


if __name__ == "__main__":
    main()
