from ultralytics import YOLO
import os



def train(model_name=None):

    # 检查数据集配置
    data_config = os.path.join('/root/autodl-tmp', 'dataset_touch_hold', 'data_touch_hold.yaml')
    if not os.path.exists(data_config):
        print(f"错误: 未找到数据集配置文件 {data_config}")
        return
    
    # 加载预训练模型
    model = YOLO('yolo26s.pt')

    project_path = os.path.join(os.path.dirname(__file__), 'result')

    if model_name is None:
        model_name = 'note_unknown'

    # 参数
    workers_num = 10
    batch_num = 100
    
    # 开始训练
    print("开始训练...")
    results = model.train(
        data=data_config,
        epochs=100,     
        imgsz=224,        
        batch=batch_num,
        patience=10, 
        save_period=1,
        workers=workers_num,    
        device=0,        
        project=project_path,
        name=model_name,    # 使用指定的模型名称
        amp=True,      
        cache=False,        
        verbose=True,
        plots=False,
        
        compile=True,

        optimizer="auto",

        hsv_h=0.03,         # HSV色调增强，适应不同光照
        hsv_s=0.2,          # HSV饱和度增强
        hsv_v=0.3           # HSV亮度增强
    )
    
    print("训练完成！")
    print(f"最佳模型保存在: {results.save_dir}")

    return results


def main():
    # 开始训练
    results = train('touch_hold')
    
    # 打印训练结果
    if results:
        best_model_path = os.path.join(results.save_dir, 'weights', 'best.pt')
        print(f"\n训练完成！最佳模型路径: {best_model_path}")


if __name__ == "__main__":
    main()
