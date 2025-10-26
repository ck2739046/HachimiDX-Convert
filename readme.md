# HachimiDX-Convert 🐱

**小团体不拉我，拿不到最新最热，所以自己抄谱😡😭😭😭🤔😋**

本项目使用 YOLO11+OpenCV 识别和处理音乐游戏 maimai 的谱面确认视频，反向推理出谱面信息，最后导出为 maidata.txt。

## 当前局限
- 无法识别烟花特效
- 不支持超大尺寸的touch和touch-hold音符 (常见于basic难度)
- 不支持变化的BPM（一首歌的BPM必须全程不变）
- 只能识别星星头，无法识别星星轨迹
- 只支持游戏录屏，不支持相机拍屏幕（会有色偏）



## 依赖安装
**注意：运行本项目推荐使用独立显卡，核显处理速度会很慢**

### 0. 创建Python虚拟环境（建议）
```bash
python -m venv venv
venv\Scripts\activate  # Windows
```

### 1. app 部分
```bash
pip install PyQt6 pywin32 psutil flask flask-cors flask-socketio opencv-python
```

### 2. convert_core 部分
需要YOLO环境：
1. 运行cmd命令查看CUDA版本：`nvidia-smi` (如果是N卡)
2. 到 [PyTorch官网](https://pytorch.org/get-started/locally/) 获取安装命令，然后安装PyTorch
3. 安装ultralytics库：`pip install ultralytics`
4. 需要安装ffmpeg，确保在cmd中输入 `ffmpeg` 可以看到版本信息
