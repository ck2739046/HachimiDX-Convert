import os
import random
import shutil
import argparse
from pathlib import Path


# 全局路径
script_dir = os.path.dirname(__file__)
dataset_dir = os.path.join(script_dir, 'datasets')
valid_dir = os.path.join(dataset_dir, 'valid')
train_dir = os.path.join(dataset_dir, 'train')
backup_dir = os.path.join(dataset_dir, 'backup')

valid_images_dir = os.path.join(valid_dir, 'images')
valid_labels_dir = os.path.join(valid_dir, 'labels')
train_images_dir = os.path.join(train_dir, 'images')
train_labels_dir = os.path.join(train_dir, 'labels')
backup_images_dir = os.path.join(backup_dir, 'images')
backup_labels_dir = os.path.join(backup_dir, 'labels')


def move_samples_to_valid(input_num):

    # 检查train目录是否存在
    if not os.path.exists(train_images_dir) or not os.path.exists(train_labels_dir):
        print("错误: train数据集不存在!")
        return False
    
    # 创建valid目录
    os.makedirs(valid_images_dir, exist_ok=True)
    os.makedirs(valid_labels_dir, exist_ok=True)
    
    # 获取train中的所有图片文件
    image_files = []
    for image in os.listdir(train_images_dir):
        if image.lower().endswith(('.jpg', '.jpeg', '.png')):
            # 检查对应的标签文件是否存在
            label_file = os.path.splitext(image)[0] + '.txt'
            if os.path.exists(os.path.join(train_labels_dir, label_file)):
                image_files.append(image)
    
    print(f"train数据集中共有 {len(image_files)} 个配对的样本")
    
    # 检查请求的数量是否合理
    if input_num <= 0 or input_num >= 1:
        print("错误: 样本数量必须在0-1之间!")
        return False

    num_samples = int(input_num * len(image_files))
    
    # 随机选择样本
    selected_files = random.sample(image_files, num_samples)
    
    print(f"正在移动 {num_samples} 个样本到 valid...")
    
    # 移动选中的文件
    moved_count = 0
    for image_file in selected_files:
        try:
            # 构造文件路径
            image_src = os.path.join(train_images_dir, image_file)
            label_file = os.path.splitext(image_file)[0] + '.txt'
            label_src = os.path.join(train_labels_dir, label_file)
            
            image_dst = os.path.join(valid_images_dir, image_file)
            label_dst = os.path.join(valid_labels_dir, label_file)
            
            # 移动图片和标签文件
            shutil.move(image_src, image_dst)
            shutil.move(label_src, label_dst)
            
            moved_count += 1
            
        except Exception as e:
            print(f"移动文件时出错 {image_file}: {e}")
    
    # 显示移动后的统计信息
    valid_total = len(os.listdir(valid_images_dir))
    train_total = len(os.listdir(train_images_dir))
    
    print(f"移动完成:")
    print(f"  - valid数据集: {valid_total} 个样本")
    print(f"  - train数据集: {train_total} 个样本")
    
    return True



def move_samples_to_valid_advanced(input_num):
    '''
    train数据集经过增强, 一个样本变三个
    此方法会将增强的三个样本中的第一个样本移动到valid目录
    并将train中的其它两个样本移动到backup目录
    保证valid中的样本是模型训练时没见过的
    '''

    # 检查train目录是否存在
    if not os.path.exists(train_images_dir) or not os.path.exists(train_labels_dir):
        print("错误: train数据集不存在!")
        return False
    
    # 创建valid目录
    os.makedirs(valid_images_dir, exist_ok=True)
    os.makedirs(valid_labels_dir, exist_ok=True)

    # 创建backup目录
    os.makedirs(backup_images_dir, exist_ok=True)
    os.makedirs(backup_labels_dir, exist_ok=True)
    
    # 获取train中的所有图片文件
    image_files = {}
    for image in os.listdir(train_images_dir):
        if image.lower().endswith(('.jpg', '.jpeg', '.png')):
            # 检查对应的标签文件是否存在
            label_file = os.path.splitext(image)[0] + '.txt'
            if os.path.exists(os.path.join(train_labels_dir, label_file)):
                # 获取图片的文件名前缀
                key = image.split('.rf.')[0]
                if key not in image_files:
                    # 保存图片文件如果key不存在
                    image_list = [image]
                    image_files[key] = image_list
                else:
                    # 如果key已存在，添加当前图片到列表
                    image_list = image_files[key]
                    image_list.append(image)
                    image_files[key] = image_list
    
    print(f"train数据集中共有 {len(image_files)} 个配对的样本")
    
    # 检查请求的数量是否合理
    if input_num <= 0 or input_num >= 1:
        print("错误: 样本数量必须在0-1之间!")
        return False

    num_samples = int(input_num * len(image_files))
    
    # 随机选择样本
    selected_files = random.sample(list(image_files.items()), num_samples)
    
    print(f"正在移动 {num_samples} 个样本到 valid...")
    
    # 移动选中的文件
    moved_count = 0
    for image_key, image_list in selected_files:
        try:
            image_file = image_list[0]  # 只移动第一个图片文件
            # 构造文件路径
            image_src = os.path.join(train_images_dir, image_file)
            label_file = os.path.splitext(image_file)[0] + '.txt'
            label_src = os.path.join(train_labels_dir, label_file)
            
            image_dst = os.path.join(valid_images_dir, image_file)
            label_dst = os.path.join(valid_labels_dir, label_file)
            
            # 移动图片和标签文件
            shutil.move(image_src, image_dst)
            shutil.move(label_src, label_dst)

            # 移动其它两个增强样本到backup目录
            for other_image in image_list[1:]:

                other_image_src = os.path.join(train_images_dir, other_image)
                other_label_file = os.path.splitext(other_image)[0] + '.txt'
                other_label_src = os.path.join(train_labels_dir, other_label_file)
                
                other_image_dst = os.path.join(backup_images_dir, other_image)
                other_label_dst = os.path.join(backup_labels_dir, other_label_file)

                shutil.move(other_image_src, other_image_dst)
                shutil.move(other_label_src, other_label_dst)
            
            moved_count += 1
            
        except Exception as e:
            print(f"移动文件时出错 {image_file}: {e}")
    
    # 显示移动后的统计信息
    valid_total = len(os.listdir(valid_images_dir))
    train_total = len(os.listdir(train_images_dir))
    backup_total = len(os.listdir(backup_images_dir))
    
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
    if not os.path.exists(valid_images_dir) or not os.path.exists(valid_labels_dir):
        print("警告: valid数据集不存在或为空!")
        return True
    
    # 检查backup目录是否存在
    if not os.path.exists(backup_images_dir) or not os.path.exists(backup_labels_dir):
        is_backup = False
    else:
        is_backup = True
    
    # 确保train目录存在
    os.makedirs(train_images_dir, exist_ok=True)
    os.makedirs(train_labels_dir, exist_ok=True)

    image_files = []
    # 获取valid中的所有图片文件
    for image in os.listdir(valid_images_dir):
        if image.lower().endswith(('.jpg', '.jpeg', '.png')):
            # 检查对应的标签文件是否存在
            img_path = os.path.join(valid_images_dir, image)
            label_file = os.path.splitext(image)[0] + '.txt'
            label_path = os.path.join(valid_labels_dir, label_file)
            if os.path.exists(label_path):
                # 保存image文件名，img路径，label路径
                file_tuple = (image, img_path, label_path)
                image_files.append(file_tuple)
    # 如果backup目录存在，获取其中的所有图片文件
    if is_backup:
        for image in os.listdir(backup_images_dir):
            if image.lower().endswith(('.jpg', '.jpeg', '.png')):
                # 检查对应的标签文件是否存在
                img_path = os.path.join(backup_images_dir, image)
                label_file = os.path.splitext(image)[0] + '.txt'
                label_path = os.path.join(backup_labels_dir, label_file)
                if os.path.exists(label_path):
                    # 保存image文件名，img路径，label路径
                    file_tuple = (image, img_path, label_path)
                    image_files.append(file_tuple)
    
    if len(image_files) == 0:
        print("valid/backup数据集中没有找到配对的样本")
        return True
    
    print(f"valid/backup数据集中共有 {len(image_files)} 个配对的样本")
    print(f"正在移动所有样本从到 train...")
    
    # 移动所有文件
    moved_count = 0
    for image_file, image_src, label_src in image_files:
        try:
            # 构造文件路径
            label_file = os.path.splitext(image_file)[0] + '.txt'
            
            image_dst = os.path.join(train_images_dir, image_file)
            label_dst = os.path.join(train_labels_dir, label_file)
            
            # 移动图片和标签文件
            shutil.move(image_src, image_dst)
            shutil.move(label_src, label_dst)
            
            moved_count += 1
            
        except Exception as e:
            print(f"移动文件时出错 {image_file}: {e}")
    
    # 显示移动后的统计信息
    train_total = len(os.listdir(train_images_dir)) if os.path.exists(train_images_dir) else 0
    
    print(f"移动完成:")
    print(f"  - train数据集: {train_total} 个样本")
    
    return True



def main():
    # 设置随机种子以便结果可重现（可选）
    # random.seed(42)
    
    num = 0.2

    #success = move_samples_to_valid(num)
    success = move_samples_to_valid_advanced(num)
    #success = move_back_to_train()
    
    if not success: print("操作失败!")

if __name__ == "__main__":
    main()