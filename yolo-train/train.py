from ultralytics import YOLO
import os

def main():

    # 检查数据集配置
    data_config = os.path.join(os.path.dirname(__file__), 'datasets', 'data.yaml')
    if not os.path.exists(data_config):
        print(f"错误: 未找到数据集配置文件 {data_config}")
        return
    
    # 加载预训练模型
    yolo_path = os.path.join(os.path.dirname(__file__), 'yolo11n.pt')
    model = YOLO(yolo_path)

    project_path = os.path.join(os.path.dirname(__file__), 'runs', 'train')

    # 参数
    workers_num = 16
    batch_num = 16
    
    # 开始训练
    print("开始训练...")
    results = model.train(
        data=data_config,
        epochs=100,     
        imgsz=640,        
        batch=batch_num,
        lr0=0.01,         
        patience=20,       
        save_period=10,      
        workers=workers_num,    
        device=0,        
        project=project_path,
        name="note_detection1080_v4", 
        amp=True,      
        cache=True,        
        verbose=True,
        plots=False,

        rect=True,          # 启用矩形训练以提高效率
        mosaic=1.0,         # 启用马赛克增强
        copy_paste=0.2,     # 启用copy-paste增强

        hsv_h=0.02,         # HSV色调增强，适应不同光照
        hsv_s=0.2,          # HSV饱和度增强
        hsv_v=0.2           # HSV亮度增强
    )
    
    print("训练完成！")
    print(f"最佳模型保存在: {results.save_dir}")

if __name__ == "__main__":
    main()
