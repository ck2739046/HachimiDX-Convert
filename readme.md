# HachimiDX-Convert 🐱

**小团体不拉我，拿不到最新最热，所以自己抄谱😡😡😡😭😭😭🤔🤔🤔😋😋😋**

本项目使用 YOLO11+OpenCV 识别音乐游戏 maimai 的谱面确认视频，反向推理出谱面信息，最后导出为 simai 语法的 maidata.txt。

## 已实现的功能
- 支持 tap, slide, touch, hold, touch-hold 全种类音符识别
- 支持 slide, hold, touch-hold 时值的识别
- 支持 ex-note, break-note, ex-break-note 识别
- 支持超大尺寸的 touch, touch-hold 音符识别 (常见于 basic 难度)
- 支持基础的星星轨迹 (< > -)

## 当前的局限
- 无法识别 touch, touch-hold 的烟花特效
- 不支持变化的 BPM（一首歌的 BPM 必须全程不变）
- 不支持复杂的 slide 轨迹
- 仅支持 2^n 的时间分辨率，不支持6分或12分音符
- slide, touch-hold 的时值可能不够精准
- 如果谱面确认视频是用相机拍屏幕，受到色偏影响，此时 ex-note, break-note, ex-break-note 的识别准确率可能会降低



## 依赖安装 (必须严格按照顺序安装)
**注意：运行本项目推荐使用独立显卡，纯 cpu 或核显处理速度会很慢**

### 0. 安装 Python 本体

如果还没有安装过 Python 本体，推荐去微软商店搜索 `Python 3.12` 下载

![python312](src/doc/images/python312.png)

在 cmd 输入 `python --version`，如果有输出 `Python 3.xx`，代表 Python 已经成功安装了

### 1. 创建 Python 虚拟环境（必需）

- 创建环境 - `python -m venv .venv`
- 激活环境 - `.venv\Scripts\activate`
- 更新依赖 - `python3 -m pip install --upgrade pip`
- 更新依赖 - `python3 -m pip install wheel`

### 2. 安装 PyTorch

根据硬件选择对应的安装指令：

1. 如果使用 `Nvidia` 显卡 (≥ GTX 900)：
    - 在 cmd 输入 `nvidia-smi` 查看 cuda 版本
    - 到 [PyTorch官网](https://pytorch.org/get-started/locally/) 选择对应 cuda 版本的安装命令

2. 如果使用 `Intel` 显卡，或者 `AMD/Intel` 核显：
    - 到 [PyTorch官网](https://pytorch.org/get-started/locally/) 选择 cpu 版本的安装命令

3. 如果使用 `AMD` 显卡，或者其他硬件：
    - 安装命令 - `pip install torch-directml` 

选择对应的安装命令后，在 Python 虚拟环境中输入以安装 PyTorch

### 3. 安装 Ultralytics

`pip install ultralytics`

### 4. 安装额外的模型推理 runtime

根据硬件不同选择对应的 runtime:

1. 如果使用 `Nvidia` 显卡 (≥ GTX 900)：
    - 安装 tensorRT - `pip install --no-cache-dir tensorrt==10.13.2.6`
    - 2025.11.05 [issue](https://github.com/NVIDIA/tensorrt/issues/4614)：当前新版 10.13.3.9 无法安装，回退到上一版

2. 如果使用 `Intel` 显卡，或者 `AMD/Intel` 核显：
    - 安装 openvino - `pip install openvino`

3. 如果使用 `AMD` 显卡，或者其他硬件：
    - 无需安装额外文件

### 4. 安装其他的库

`pip install PyQt6 pywin32`
