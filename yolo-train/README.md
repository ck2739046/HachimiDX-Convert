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

#### 2.1 准备视频文件
```bash
# 将maimai游戏视频放入 input/ 目录
# 支持常见视频格式: .mp4, .avi, .mov 等
```

#### 2.2 配置参数
编辑 `generate_dataset.py` 或使用 `example_usage.py` 中的示例配置：

```python
# 关键参数需要根据您的视频调整:
state_config = {
    'chart_start': 500,           # 谱面开始的帧数
    'circle_center': (960, 540),  # 游戏圆圈中心坐标 (x, y)
    'circle_radius': 400,         # 游戏圆圈半径 (像素)
    'debug': False               # 调试模式
}
```

**参数调整方法:**
1. **chart_start**: 观看视频，记录谱面开始播放的大概时间，转换为帧数
2. **circle_center**: 暂停视频，测量maimai游戏圆圈的中心像素坐标
3. **circle_radius**: 测量游戏圆圈的半径像素大小

#### 2.3 运行数据集生成
```bash
# 方法1: 直接运行
python generate_dataset.py

# 方法2: 使用示例配置 (推荐)
python example_usage.py
```

#### 2.4 调试模式
如果不确定参数是否正确，可以先运行调试模式：
```bash
# 在 example_usage.py 中选择调试模式
# 这会显示检测结果的可视化界面，帮助调整参数
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

项目检测4种maimai音符类型:

- **0: tap_note** (圆形音符) - 普通的圆形点击音符
- **1: slide_note** (星形音符) - 星形滑动音符，包括单星和双星
- **2: hold_note** (长条音符) - 需要按住的长条音符
- **3: touch_note** (三角形音符) - 触摸感应区域的三角形音符

## 数据集格式

生成的数据集采用YOLO标准格式:

```
datasets/
├── images/
│   ├── train/     # 训练图片 (.jpg)
│   ├── val/       # 验证图片
│   └── test/      # 测试图片
├── labels/
│   ├── train/     # 训练标注 (.txt)
│   ├── val/       # 验证标注
│   └── test/      # 测试标注
└── data.yaml     # 数据集配置
```

每个标注文件(.txt)格式:
```
class_id center_x center_y width height
# 例如: 0 0.5 0.3 0.1 0.1
# 坐标为相对坐标 (0-1 范围)
```

## 注意事项

1. **首次运行**: train.py会自动下载YOLOv11s预训练模型 (~20MB)
2. **GPU内存**: 根据您的GPU内存调整batch size (在train.py中修改)
3. **数据集大小**: 建议准备至少500-1000张标注图片用于训练
4. **模型保存**: 训练完成后，最佳模型保存在 `runs/train/note_detection/weights/best.pt`

## 故障排除

### 常见问题

**Q1: 导入NoteDetector失败**
```bash
# 确保目录结构正确:
yolo-train/
├── generate_dataset.py
└── ../ca_modules/NoteDetector.py
```

**Q2: 生成的数据集为空**
- 检查 `chart_start` 参数是否正确设置到谱面开始位置
- 检查 `circle_center` 和 `circle_radius` 是否匹配视频中的游戏圆圈
- 使用调试模式查看检测效果

**Q3: 训练效果不好**
- 增加数据集大小 (更多视频或更长的视频片段)
- 调整数据采样间隔 (在generate_dataset.py中修改frame_interval)
- 确保数据集包含各种难度的谱面

**Q4: 内存不足**
- 减少batch_size (在train.py中)
- 减少图像尺寸 (在train.py中修改imgsz)
- 减少workers数量

### 参数调优建议

1. **数据生成阶段**:
   - 使用多个不同难度的视频
   - 调整frame_interval平衡数据量和多样性
   - 确保包含各种音符类型的充分样本

2. **训练阶段**:
   - 从较小的epochs开始 (如50)
   - 监控验证损失，避免过拟合
   - 根据mAP指标调整学习率和其他超参数
