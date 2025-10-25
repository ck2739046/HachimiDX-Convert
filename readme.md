
**注意：运行本项目推荐使用独立显卡，核显处理速度会很慢**

# 依赖安装说明

## 环境准备
建议先创建Python虚拟环境：
```bash
python -m venv venv
venv\Scripts\activate  # Windows
```

## 依赖安装

### 1. app 部分
```bash
pip install PyQt6 pywin32 psutil flask flask-cors flask-socketio
```

### 2. convert_core 部分
需要YOLO环境：
1. 查看CUDA版本：`nvidia-smi`
2. 到 [PyTorch官网](https://pytorch.org/get-started/locally/) 获取 PyTorch 的安装命令
3. 安装ultralytics库：`pip install ultralytics`
4. 安装OpenCV：`pip install opencv-python`
