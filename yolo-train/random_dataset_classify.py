import os
import random
import shutil


# 全局路径
script_dir = os.path.dirname(__file__)
dataset_dir = os.path.join(script_dir, 'dataset-classify-touch-each')

valid_dir = os.path.join(dataset_dir, 'val')
train_dir = os.path.join(dataset_dir, 'train')
backup_dir = os.path.join(dataset_dir, 'backup')

valid_true_dir = os.path.join(valid_dir, 'true')
valid_false_dir = os.path.join(valid_dir, 'false')
train_true_dir = os.path.join(train_dir, 'true')
train_false_dir = os.path.join(train_dir, 'false')
backup_true_dir = os.path.join(backup_dir, 'true')
backup_false_dir = os.path.join(backup_dir, 'false')


def move_samples_to_valid_advanced(input_num, round=None):
    '''
    train数据集经过增强, 一个样本变三个
    此方法会将增强的三个样本中的第一个样本移动到valid目录
    并将train中的其它两个样本移动到backup目录
    保证valid中的样本是模型训练时没见过的
    '''

    # 检查train目录是否存在
    if not os.path.exists(train_true_dir) or not os.path.exists(train_false_dir):
        print("错误: train数据集不存在!")
        return False
    
    # 创建valid目录
    os.makedirs(valid_true_dir, exist_ok=True)
    os.makedirs(valid_false_dir, exist_ok=True)

    # 创建backup目录
    os.makedirs(backup_true_dir, exist_ok=True)
    os.makedirs(backup_false_dir, exist_ok=True)
    
    # 获取train中的所有图片文件
    image_files = {}
    for dir, dir_bool in [(train_true_dir, True), (train_false_dir, False)]:
        for image in os.listdir(dir):
            if image.lower().endswith(('.jpg', '.jpeg', '.png')):
                # 获取图片的文件名前缀
                key = (image.split('.rf.')[0], dir_bool)
                if key not in image_files:
                    # 保存图片文件如果key不存在
                    image_list = []
                    image_list.append(image)
                    image_files[key] = image_list
                else:
                    # 如果key已存在，添加当前图片到列表
                    image_list = image_files[key]
                    image_list.append(image)
                    image_files[key] = image_list

    print(f"train数据集中共有 {len(image_files)} 对样本")
    
    # 检查请求的数量是否合理
    if input_num <= 0 or input_num >= 1:
        print("错误: 样本数量必须在0-1之间!")
        return False

    num_samples = int(input_num * len(image_files))
    
    # 随机选择样本
    selected_files = random.sample(list(image_files.items()), num_samples)
    
    print(f"正在移动 {num_samples} 个样本到 valid...")
    
    # 保存选中的文件key到txt文件
    if round is not None:
        selected_keys_file = os.path.join(script_dir, f'selected_keys_round{round}.txt')
        if os.path.exists(selected_keys_file):
            os.remove(selected_keys_file)
        with open(selected_keys_file, 'w', encoding='utf-8') as f:
            for (image_key, dir_bool), image_list in selected_files:
                f.write(f'"{image_key}"-{dir_bool}\n')
        print(f"已保存选中的样本key到: {selected_keys_file}")
    
    # 移动选中的文件
    moved_count = 0
    for (image_key, dir_bool), image_list in selected_files:
        try:
            filename = image_list[0]  # 只移动第一个图片文件

            # 移动图片和标签文件
            image_src = os.path.join(train_true_dir if dir_bool else train_false_dir, filename)
            image_dst = os.path.join(valid_true_dir if dir_bool else valid_false_dir, filename)
            shutil.move(image_src, image_dst)

            # 移动其它两个样本到backup目录
            for other_image in image_list[1:]:
                other_src = os.path.join(train_true_dir if dir_bool else train_false_dir, other_image)
                other_dst = os.path.join(backup_true_dir if dir_bool else backup_false_dir, other_image)
                shutil.move(other_src, other_dst)
            
            moved_count += 1
            
        except Exception as e:
            print(f'移动文件时出错 "{image_key}"-{dir_bool}: {e}')
    
    # 显示移动后的统计信息
    valid_total = len(os.listdir(valid_true_dir)) + len(os.listdir(valid_false_dir))
    train_total = len(os.listdir(train_true_dir)) + len(os.listdir(train_false_dir))
    backup_total = len(os.listdir(backup_true_dir)) + len(os.listdir(backup_false_dir))
    
    print(f"移动完成:")
    print(f"  - valid数据集: {valid_total} 个样本")
    print(f"  - train数据集: {train_total} 个样本")
    print(f"  - backup数据集: {backup_total} 个样本")
    
    return True



def move_back_to_train():
    '''
    将valid和backup目录中的样本移动回train目录
    '''

    # 检查valid目录是否存在
    if not os.path.exists(valid_true_dir) or not os.path.exists(valid_false_dir):
        print("警告: valid数据集不存在或为空!")
        return True
    
    # 检查backup目录是否存在
    if not os.path.exists(backup_true_dir) or not os.path.exists(backup_false_dir):
        is_backup = False
    else:
        is_backup = True
    
    # 确保train目录存在
    os.makedirs(train_true_dir, exist_ok=True)
    os.makedirs(train_false_dir, exist_ok=True)

    # 移动valid中的样本到train
    for image in os.listdir(valid_true_dir):
        if image.lower().endswith(('.jpg', '.jpeg', '.png')):
            src = os.path.join(valid_true_dir, image)
            dst = os.path.join(train_true_dir, image)
            shutil.move(src, dst)
    for image in os.listdir(valid_false_dir):
        if image.lower().endswith(('.jpg', '.jpeg', '.png')):
            src = os.path.join(valid_false_dir, image)
            dst = os.path.join(train_false_dir, image)
            shutil.move(src, dst)

    # 移动backup中的样本到train
    if is_backup:
        for image in os.listdir(backup_true_dir):
            if image.lower().endswith(('.jpg', '.jpeg', '.png')):
                src = os.path.join(backup_true_dir, image)
                dst = os.path.join(train_true_dir, image)
                shutil.move(src, dst)
        for image in os.listdir(backup_false_dir):
            if image.lower().endswith(('.jpg', '.jpeg', '.png')):
                src = os.path.join(backup_false_dir, image)
                dst = os.path.join(train_false_dir, image)
                shutil.move(src, dst)
    

    train_total = len(os.listdir(train_true_dir)) + len(os.listdir(train_false_dir))
    print(f"移动完成:")
    print(f"  - train数据集: {train_total} 个样本")
    
    return True



def main():
    # 设置随机种子以便结果可重现（可选）
    # random.seed(42)
    
    num = 0.2

    success = move_samples_to_valid_advanced(num)
    #success = move_back_to_train()
    
    if not success: print("操作失败!")

if __name__ == "__main__":
    main()