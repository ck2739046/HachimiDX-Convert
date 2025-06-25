# YOLO音符检测项目

这是一个基于YOLOv11的音乐游戏音符检测项目。

## 项目结构

```
yolo-train/
├── datasets/                # 数据集目录
│   ├── images/
│   │   ├── train/          # 训练图片
│   │   ├── val/            # 验证图片
│   │   └── test/           # 测试图片
│   ├── labels/
│   │   ├── train/          # 训练标注
│   │   ├── val/            # 验证标注
│   │   └── test/           # 测试标注
│   └── data.yaml           # 数据集配置
├── input/                  # 输入文件目录
├── models/                 # 模型保存目录
├── runs/                   # 训练和推理结果
├── generate_dataset.py     # 数据集生成工具
├── train.py               # 训练脚本
├── validate.py            # 验证脚本
├── predict.py             # 推理脚本
├── requirements.txt       # 依赖包
└── README.md             # 说明文档
```

## 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 生成数据集
```bash
# 将测试视频放入合适位置，然后运行
python generate_dataset.py
```

### 3. 训练模型
```bash
python train.py
```

### 4. 验证模型
```bash
python validate.py
```

### 5. 使用模型推理
```bash
# 将测试视频放入 input/ 目录，然后运行
python predict.py
```

## 音符类别

- 0: tap_note (圆形音符)
- 1: slide_note (星形音符)  
- 2: hold_note (长条音符)
- 3: touch_note (三角形音符)

## 注意事项

1. 首次运行train.py时会自动下载YOLOv11s预训练模型
2. 请根据您的GPU内存调整batch size
3. 建议准备至少500-1000张标注图片用于训练
4. 训练完成后，最佳模型会保存在 `runs/train/note_detection/weights/best.pt`
