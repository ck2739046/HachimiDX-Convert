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



def main(video_path, bpm, click_times=4):
    """
    在视频中的音频起始时间 (ms)

    参数:
        video_path (str): 视频文件路径（librosa 能读取的路径）
        bpm (float|int): 启动拍的bpm
        click_times (int): 启动拍数量，默认为4

    返回:
        float: 匹配到的时间（秒）

    抛出:
        FileNotFoundError, ValueError: 在模板或音频无法加载时抛出
    """

    try:
        # 1. Load template and audio
        template_path = os.path.normpath(os.path.abspath(tools.path_config.click_template))
        template, template_sr = _load_audio_file(template_path)
        audio_data, audio_sr = _load_audio_file(video_path)

        # 2. Generate multi-beat template
        full_template = generate_template(bpm, click_times, template, template_sr)
        
        # 3. Resample both to 44100 Hz
        target_sr = 44100
        if template_sr != target_sr:
            full_template = librosa.resample(full_template, orig_sr=template_sr, target_sr=target_sr)
        if audio_sr != target_sr:
            audio_data = librosa.resample(audio_data, orig_sr=audio_sr, target_sr=target_sr)
        
        full_template_mono = librosa.to_mono(full_template)
        audio_mono = librosa.to_mono(audio_data)
        
        # 4. Calculate offset
        match_time = template_match(audio_mono, full_template_mono)

        # 虽然不知道为什么，但实测需要 -25ms 才能得到正确结果
        adjusted_match_time = match_time - 25

        if adjusted_match_time < 0:
            print(f"error: adjusted_match_time < 0 ({adjusted_match_time})")
            return None
   
        return adjusted_match_time
    
    except Exception as e:
        print(f"Error in detecting audio start: {e}")
        return None


def _load_audio_file(path):
    try:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Audio file not found: {path}")
        with suppress_audio_warnings():
            data, sr = librosa.load(path, sr=None, mono=True)
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

    # 剔除开头的静音片段
    # 设置阈值：找到第一个振幅超过最大振幅1%的位置
    threshold = np.max(np.abs(full_template)) * 0.01
    non_silent_indices = np.where(np.abs(full_template) > threshold)[0]
    
    if len(non_silent_indices) > 0:
        first_sound_pos = non_silent_indices[0]
        if first_sound_pos > 0:
            full_template = full_template[first_sound_pos:]
            # print(f"Removed {first_sound_pos} samples of silence from template start")

    # Save the generated template to desktop
    # from scipy.io import wavfile
    # desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
    # output_file = os.path.join(desktop_path, "generated_template.wav")
    # normalized_template = full_template / (np.max(np.abs(full_template)) + 1e-8)
    # wavfile.write(output_file, template_sr, normalized_template.astype(np.float32))

    return full_template


def template_match(signal1, signal2):
    """
    在给定的音频中查找启动拍的匹配位置 (ms)
    """
    if len(signal1) < len(signal2):
        raise ValueError("Audio data too short for template matching")

    if signal1.ndim > 1:
        signal1 = signal1.mean(axis=1)
    if signal2.ndim > 1:
        signal2 = signal2.mean(axis=1)

    # Precise mode: RMS归一化 + 能量归一化
    def rms_normalize(sig):
        rms = np.sqrt(np.mean(sig ** 2))
        return sig / (rms + 1e-8)
    
    sig1_norm = rms_normalize(signal1)
    sig2_norm = rms_normalize(signal2)
    
    correlation = signal.correlate(sig1_norm, sig2_norm, mode='full', method='fft')
    
    # 能量归一化
    template_energy = np.sum(sig2_norm ** 2)
    if template_energy > 0:
        correlation = correlation / np.sqrt(template_energy)

    lag_index = np.argmax(correlation)
    offset = lag_index - (len(signal2) - 1)

    # Convert to milliseconds
    offset_ms = (offset / 44100) * 1000

    return offset_ms


if __name__ == '__main__':
    
    args = sys.argv
    if len(args) == 4:
        result = main(args[1], float(args[2]), int(args[3]))
        print(f"Detected start time: {result} ms")
    elif len(args) == 3:
        result = main(args[1], float(args[2]))
        print(f"Detected start time: {result} ms")
    else:
        print('Missing arguments')
