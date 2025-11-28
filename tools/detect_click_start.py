import sys
import os
import librosa
import numpy as np
from scipy import signal
import warnings
import sys
from contextlib import contextmanager

root = os.path.normpath(os.path.abspath(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root not in sys.path:
    sys.path.insert(0, root)

import tools.path_config


@contextmanager
def suppress_audio_warnings():
    """抑制音频加载时的警告和错误信息"""
    # 抑制 librosa FutureWarning
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=FutureWarning, module="librosa")
        warnings.filterwarnings("ignore", message='PySoundFile failed. Trying audioread instead.')
        yield



def main(video_path, bpm, click_times, duration):
    """
    在视频中的音频起始时间 (ms)

    参数:
        video_path (str): 视频文件路径（librosa 能读取的路径）
        bpm (float|int): 启动拍的bpm
        click_times (int): 启动拍数量
        duration (int): 仅加载前多少秒

    返回:
        float: 匹配到的时间（秒）
    """

    try:
        # 1. Load template and audio
        template_path = os.path.normpath(os.path.abspath(tools.path_config.click_template))
        template, template_sr = _load_audio_file(template_path)
        audio_data, audio_sr = _load_audio_file(video_path, duration=duration) # 仅加载前duration秒

        # 2. Generate multi-beat template
        full_template = generate_template(bpm, click_times, template, template_sr)
        
        # 3. Resample both to 44100 Hz
        target_sr = 44100
        if template_sr != target_sr:
            full_template = librosa.resample(full_template, orig_sr=template_sr, target_sr=target_sr)
        if audio_sr != target_sr:
            audio_data = librosa.resample(audio_data, orig_sr=audio_sr, target_sr=target_sr)
        
        # 4. Calculate offset using Normalized Cross-Correlation
        match_time = template_match(audio_data, full_template)

        # 模板音频开头有0.5秒静音，匹配结果需要加上0.5秒
        # 虽然不知道为什么，但实测还需要 +40ms 才能得到正确结果
        adjusted_match_time = match_time + 500 + 40

        if adjusted_match_time < 0:
            print(f"error: adjusted_match_time < 0 ({adjusted_match_time})")
            return None
   
        return adjusted_match_time
    
    except Exception as e:
        print(f"Error in detecting audio start: {e}")
        return None


def _load_audio_file(path, duration=None):
    """
    加载音频文件
    :param duration: 仅加载前多少秒，None为加载全部
    """
    try:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Audio file not found: {path}")
        with suppress_audio_warnings():
            # duration
            data, sr = librosa.load(path, sr=None, mono=True, duration=duration)
            if data is None or len(data) == 0:
                raise ValueError(f"Cannot load audio data from: {path}")
            return data, sr
    except Exception as e:
        raise Exception(f"Error loading audio file '{path}': {e}")


def generate_template(bpm, click_times, template, template_sr):
    """
    基于 BPM 生成多个启动拍的完整模板
    """
    beat_interval = 60.0 / float(bpm)
    sample_interval = round(beat_interval * template_sr)
    template_length = len(template)

    # Create multi-beat template with proper intervals
    total_length = template_length + (click_times - 1) * sample_interval
    full_template = np.zeros(total_length, dtype=template.dtype)
    for i in range(click_times):
        start_pos = i * sample_interval
        end_pos = start_pos + template_length
        if end_pos <= total_length:
            full_template[start_pos:end_pos] = template

    # 剔除结尾的10ms静音，避免影响匹配
    end_silence_samples = int(0.010 * template_sr)
    full_template = full_template[:-end_silence_samples]

    # 在开头增加0.5秒的静音
    start_silence_samples = int(0.5 * template_sr)
    full_template = np.concatenate((np.zeros(start_silence_samples, dtype=template.dtype), full_template))

    # 剔除开头的静音片段
    # 设置阈值：找到第一个振幅超过最大振幅1%的位置
    # threshold = np.max(np.abs(full_template)) * 0.01
    # non_silent_indices = np.where(np.abs(full_template) > threshold)[0]
    
    # if len(non_silent_indices) > 0:
    #     first_sound_pos = non_silent_indices[0]
    #     if first_sound_pos > 0:
    #         full_template = full_template[first_sound_pos:]
    #         # print(f"Removed {first_sound_pos} samples of silence from template start")

    # Save the generated template to desktop
    # from scipy.io import wavfile
    # desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
    # output_file = os.path.join(desktop_path, "generated_template.wav")
    # normalized_template = full_template / (np.max(np.abs(full_template)) + 1e-8)
    # wavfile.write(output_file, template_sr, normalized_template.astype(np.float32))

    return full_template


def template_match(signal1, signal2):
    """
    双阶段音频对齐流程
    阶段一：基于 Onset 包络的粗匹配
    阶段二：基于波形的精细匹配 (ZNCC)
    计算模板在目标信号中的位置
    """
    if len(signal1) < len(signal2):
        raise ValueError("Audio data too short for template matching")
    
    # 设置采样率
    target_sr = 44100
    
    # ==========================================
    # 阶段一：基于 Onset 包络的粗匹配 (Coarse Match)
    # ==========================================
    coarse_offset_sec = coarse_match_onset(signal1, signal2, target_sr)
    print(f"  -> Coarse offset: {coarse_offset_sec * 1000:.2f} ms")
    
    # ==========================================
    # 阶段二：基于波形的精细匹配 (Fine Match)
    # ==========================================
    # 设定搜索窗口：在粗匹配结果的基础上，前后各搜 80ms
    search_radius_sec = 0.08
    final_offset_ms = fine_match_zncc(
        signal1, 
        signal2, 
        coarse_offset_sec, 
        search_radius_sec, 
        target_sr
    )
    
    return final_offset_ms


def coarse_match_onset(y_target, y_template, sr):
    """
    阶段一算法：使用 Onset Strength (瞬态强度) 进行匹配
    优势：忽略背景噪音和持续音，只关注"打击感"的变化率
    """
    # 1. 高通滤波：去掉 200Hz 以下低频，防止鼓点干扰点击音
    sos = signal.butter(4, 200, 'hp', fs=sr, output='sos')
    y_target_filt = signal.sosfilt(sos, y_target)
    y_template_filt = signal.sosfilt(sos, y_template)

    # 2. 提取 Onset 包络
    # hop_length=882 在 44.1k 下约为 20ms 的分辨率
    hop_length = 882
    onset_target = librosa.onset.onset_strength(y=y_target_filt, sr=sr, hop_length=hop_length)
    onset_template = librosa.onset.onset_strength(y=y_template_filt, sr=sr, hop_length=hop_length)

    # 3. 归一化包络 (Min-Max)
    onset_target = librosa.util.normalize(onset_target)
    onset_template = librosa.util.normalize(onset_template)

    # 4. 互相关
    correlation = signal.correlate(onset_target, onset_template, mode='full')
    lag = np.argmax(correlation)
    
    # 5. 换算回时间 (秒)
    # 这里的 lag 是特征帧的偏移，需要转换回采样点时间
    frame_offset = lag - (len(onset_template) - 1)
    time_offset = librosa.frames_to_time(frame_offset, sr=sr, hop_length=hop_length)
    
    return time_offset


def fine_match_zncc(y_target, y_template, coarse_center_sec, radius_sec, sr):
    """
    阶段二算法：局部零均值归一化互相关 (Local ZNCC)
    优势：在已知小范围内，进行采样点级别的波形对齐，抗音量差异
    """
    # 1. 确定截取范围 (在长音频上截取一段窗口)
    center_sample = int(coarse_center_sec * sr)
    radius_sample = int(radius_sec * sr)
    
    start_idx = center_sample - radius_sample
    end_idx = center_sample + radius_sample + len(y_template) # 窗口长度需要包含模板长度

    # 边界保护
    pad_left = 0
    if start_idx < 0:
        pad_left = -start_idx
        start_idx = 0
    
    if end_idx > len(y_target):
        end_idx = len(y_target)

    # 截取目标片段 (Windowed Target)
    y_window = y_target[start_idx:end_idx]

    # 如果因为边界导致窗口太小，直接返回粗匹配结果
    if len(y_window) < len(y_template):
        print("Warning: Window too small near edges, returning coarse result.")
        return coarse_center_sec * 1000

    # 2. 标准化 (Z-Score Standardization) - 这一步是 ZNCC 的核心
    # 减去均值，除以标准差。这能消除局部窗口内的 DC 偏移和音量差异
    def standardize(y):
        return (y - np.mean(y)) / (np.std(y) + 1e-9)

    y_window_norm = standardize(y_window)
    y_template_norm = standardize(y_template)

    # 3. 互相关计算 (此时数据量很小，直接计算即可)
    correlation = signal.correlate(y_window_norm, y_template_norm, mode='valid')
    
    # 4. 找到局部峰值
    local_lag = np.argmax(correlation)

    # 5. 计算绝对时间偏移
    # 这里的 local_lag 是相对于 y_window 起始点的偏移
    # 由于 mode='valid'，结果索引 0 对应完全重叠的起始位置
    
    # 绝对采样点位置 = 窗口起始点 + 局部偏移 - 左侧填充修正
    absolute_sample_offset = start_idx + local_lag - pad_left
    
    offset_ms = (absolute_sample_offset / sr) * 1000.0
    
    print(f"  -> Adjustment: {(offset_ms - coarse_center_sec*1000):.2f} ms from coarse")
    
    return offset_ms


if __name__ == '__main__':

    args = sys.argv
    if len(args) == 5:
        result = main(args[1], float(args[2]), int(args[3]), float(args[4]))
        print(f"Detected start time: {result} ms")
    else:
        print('Missing arguments')
