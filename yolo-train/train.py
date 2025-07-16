from ultralytics import YOLO
import os
import random_dataset
import yaml

def train(model_name=None):

    # 检查数据集配置
    data_config = os.path.join(os.path.dirname(__file__), 'datasets', 'data.yaml')
    if not os.path.exists(data_config):
        print(f"错误: 未找到数据集配置文件 {data_config}")
        return
    
    # 加载预训练模型
    yolo_path = os.path.join(os.path.dirname(__file__), 'yolo11n.pt')
    model = YOLO(yolo_path)

    project_path = os.path.join(os.path.dirname(__file__), 'runs', 'train')

    if model_name is None:
        model_name = 'note_detection1080_v4'

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
        name=model_name,    # 使用指定的模型名称
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

    return results


def analyze_training_results(results_list):
    """
    分析5轮训练的结果，打印每一轮的best.pt性能
    """
    print("\n" + "="*80)
    print("五轮训练结果分析")
    print("="*80)
    
    best_round = None
    best_map50 = 0
    
    for i, results in enumerate(results_list):
        round_num = i + 1
        print(f"\n第 {round_num} 轮训练结果:")
        print("-" * 40)
        
        # 获取最佳模型路径
        best_model_path = os.path.join(results.save_dir, 'weights', 'best.pt')
        
        if os.path.exists(best_model_path):
            print(f"最佳模型路径: {best_model_path}")
            
            # 读取训练结果文件
            results_csv = os.path.join(results.save_dir, 'results.csv')
            if os.path.exists(results_csv):
                # 读取最后一行的结果
                with open(results_csv, 'r') as f:
                    lines = f.readlines()
                    if len(lines) > 1:  # 跳过标题行
                        last_line = lines[-1].strip().split(',')
                        try:
                            # CSV文件格式: epoch, train/box_loss, train/cls_loss, train/dfl_loss, metrics/precision(B), metrics/recall(B), metrics/mAP50(B), metrics/mAP50-95(B), val/box_loss, val/cls_loss, val/dfl_loss, lr/pg0, lr/pg1, lr/pg2
                            epoch = int(float(last_line[0]))
                            precision = float(last_line[4])
                            recall = float(last_line[5])
                            map50 = float(last_line[6])
                            map50_95 = float(last_line[7])
                            
                            print(f"训练轮次: {epoch}")
                            print(f"精确度 (Precision): {precision:.4f}")
                            print(f"召回率 (Recall): {recall:.4f}")
                            print(f"mAP@0.5: {map50:.4f}")
                            print(f"mAP@0.5:0.95: {map50_95:.4f}")
                            
                            # 记录最佳轮次
                            if map50 > best_map50:
                                best_map50 = map50
                                best_round = round_num
                                
                        except (ValueError, IndexError) as e:
                            print(f"解析结果文件时出错: {e}")
                            print("使用训练对象的属性...")
                            print(f"保存目录: {results.save_dir}")
            else:
                print("未找到详细结果文件，显示基本信息...")
                print(f"保存目录: {results.save_dir}")
        else:
            print(f"警告: 未找到最佳模型文件 {best_model_path}")
    
    print("\n" + "="*80)
    print("总结")
    print("="*80)
    if best_round:
        print(f"最佳轮次: 第 {best_round} 轮 (mAP@0.5: {best_map50:.4f})")
        best_results = results_list[best_round - 1]
        best_model_path = os.path.join(best_results.save_dir, 'weights', 'best.pt')
        print(f"最佳模型路径: {best_model_path}")
    else:
        print("无法确定最佳轮次")
    print("="*80)


def main():
    results_list = []
    
    for i in range(5):
        print(f"\n开始第 {i+1} 轮训练...")
        random_dataset.move_back_to_train()
        random_dataset.move_samples_to_valid_advanced(0.2, round=i+1)
        results = train(f'note_detection1080_v4_round{i+1}')
        results_list.append(results)
    
    # 分析所有训练结果
    analyze_training_results(results_list)


if __name__ == "__main__":
    main()
