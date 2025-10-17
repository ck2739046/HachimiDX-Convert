from ultralytics import YOLO
from ultralytics.models.yolo.obb import OBBTrainer
from ultralytics.utils.loss import v8OBBLoss, VarifocalLoss
import torch
import os
#import random_dataset


class CustomOBBLoss(v8OBBLoss):
    """自定义 OBB 损失函数，使用 VarifocalLoss 替代 BCE"""
    
    def __init__(self, model):
        """初始化自定义 OBB 损失，使用 VarifocalLoss"""
        super().__init__(model)
        # 使用 VarifocalLoss 替换默认的 BCE 损失
        self.varifocal_loss = VarifocalLoss(gamma=2.0, alpha=0.75)
    
    def __call__(self, preds, batch):
        """计算损失，使用 VarifocalLoss 替代 BCE"""
        loss = torch.zeros(3, device=self.device)  # box, cls, dfl
        feats, pred_angle = preds if isinstance(preds[0], list) else preds[1]
        batch_size = pred_angle.shape[0]
        pred_distri, pred_scores = torch.cat([xi.view(feats[0].shape[0], self.no, -1) for xi in feats], 2).split(
            (self.reg_max * 4, self.nc), 1
        )

        # b, grids, ..
        pred_scores = pred_scores.permute(0, 2, 1).contiguous()
        pred_distri = pred_distri.permute(0, 2, 1).contiguous()
        pred_angle = pred_angle.permute(0, 2, 1).contiguous()

        dtype = pred_scores.dtype
        imgsz = torch.tensor(feats[0].shape[2:], device=self.device, dtype=dtype) * self.stride[0]
        anchor_points, stride_tensor = self.make_anchors(feats, self.stride, 0.5)

        # targets
        try:
            batch_idx = batch["batch_idx"].view(-1, 1)
            targets = torch.cat((batch_idx, batch["cls"].view(-1, 1), batch["bboxes"]), 1)
            targets = self.preprocess(targets, batch_size, scale_tensor=imgsz[[1, 0, 1, 0]])
            gt_labels, gt_bboxes = targets.split((1, 5), 2)  # cls, xywhr
            mask_gt = gt_bboxes.sum(2, keepdim=True).gt_(0.0)
        except RuntimeError as e:
            raise TypeError(
                "ERROR ❌ OBB dataset incorrectly formatted or not a OBB dataset.\n"
            ) from e

        # Pboxes
        pred_bboxes = self.bbox_decode(anchor_points, pred_distri, pred_angle)

        bboxes_for_assigner = pred_bboxes.clone().detach()
        bboxes_for_assigner[..., :4] *= stride_tensor
        _, target_bboxes, target_scores, fg_mask, target_labels = self.assigner(
            pred_scores.detach().sigmoid(),
            bboxes_for_assigner.type(gt_bboxes.dtype),
            anchor_points * stride_tensor,
            gt_labels,
            gt_bboxes,
            mask_gt,
        )

        target_scores_sum = max(target_scores.sum(), 1)

        # 使用 VarifocalLoss 替代 BCE
        loss[1] = self.varifocal_loss(pred_scores, target_scores.to(dtype), target_labels) / target_scores_sum

        # Bbox loss
        if fg_mask.sum():
            target_bboxes[..., :4] /= stride_tensor
            loss[0], loss[2] = self.bbox_loss(
                pred_distri, pred_bboxes, anchor_points, target_bboxes, target_scores, target_scores_sum, fg_mask
            )
        else:
            loss[0] += (pred_angle * 0).sum()

        loss[0] *= self.hyp.box  # box gain
        loss[1] *= self.hyp.cls  # cls gain
        loss[2] *= self.hyp.dfl  # dfl gain

        return loss.sum() * batch_size, loss.detach()

    def make_anchors(self, feats, strides, grid_cell_offset=0.5):
        """从特征图生成锚点"""
        from ultralytics.utils.tal import make_anchors
        return make_anchors(feats, strides, grid_cell_offset)


class CustomOBBTrainer(OBBTrainer):
    """自定义 OBB 训练器，使用 VarifocalLoss 处理数据集不平衡问题"""
    
    def get_model(self, cfg=None, weights=None, verbose=True):
        """获取模型并设置自定义损失函数"""
        model = super().get_model(cfg, weights, verbose)
        # 替换损失函数为自定义的 OBB 损失
        if hasattr(model, 'criterion'):
            model.criterion = CustomOBBLoss(model)
        return model


def train(model_name=None):

    # 检查数据集配置
    data_config = os.path.join('/root/autodl-tmp', 'dataset', 'data.yaml')
    if not os.path.exists(data_config):
        print(f"错误: 未找到数据集配置文件 {data_config}")
        return
    
    # 加载预训练模型
    model = YOLO('yolo11l-obb.pt')

    project_path = os.path.join(os.path.dirname(__file__), 'result')

    if model_name is None:
        model_name = 'note_unknown'

    # 参数
    workers_num = 24
    batch_num = 29
    
    # 开始训练（使用自定义的 VarifocalLoss 训练器）
    print("开始训练（使用 VarifocalLoss 处理数据集不平衡）...")
    results = model.train(
        trainer=CustomOBBTrainer,  # 使用自定义 OBB 训练器
        data=data_config,
        epochs=100,     
        imgsz=960,        
        batch=batch_num,        
        patience=5,           
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
    results = train('note_obb_v1')
    
    # 打印训练结果
    if results:
        best_model_path = os.path.join(results.save_dir, 'weights', 'best.pt')
        print(f"\n训练完成！最佳模型路径: {best_model_path}")


if __name__ == "__main__":
    main()
