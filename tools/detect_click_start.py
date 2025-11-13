import sys
import os
import librosa
import numpy as np
from scipy.signal import correlate

root = os.path.normpath(os.path.abspath(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root not in sys.path:
    sys.path.insert(0, root)

import tools.path_config


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
        # template path
        template_path = os.path.normpath(os.path.abspath(tools.path_config.click_template))
        # Load template and audio
        template, template_sr = _load_audio_file(template_path)
        audio_data, audio_sr = _load_audio_file(video_path)
        # Generate multi-beat template
        full_template = generate_template(bpm, click_times, template, template_sr, audio_sr)
        # Perform template matching and return match time in seconds
        match_time = template_match(audio_data, audio_sr, full_template)
        
        # 不知道为什么，match_time是第三声click响起的时刻
        # 模板click开头有10ms空白，要减去
        # 1个click是1/4小节，(60/bpm*1000*4)/4
        # 由于是第三声响起，要减去前2个click的时间
        # 最后加上91ms的游戏固定音频延迟
        # 这才是真正的音频起始时间
        adjusted_match_time = match_time - 10 - 2 * (60 / bpm * 1000 * 4) / 4 + 91
        return adjusted_match_time
    
    except Exception as e:
        print(f"Error in detecting audio start: {e}")
        return None


def _load_audio_file(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Audio file not found: {path}")
    data, sr = librosa.load(path, sr=None, mono=True)
    if data is None or len(data) == 0:
        raise ValueError(f"Cannot load audio data from: {path}")
    return data, sr


def generate_template(bpm, click_times, template, template_sr, audio_sr):
    """
    基于 BPM 生成多个启动拍的完整模板
    """
    beat_interval = 60.0 / float(bpm)

    # Resample template to audio sample rate if needed
    if template_sr != audio_sr:
        template_resampled = librosa.resample(template, orig_sr=template_sr, target_sr=audio_sr)
    else:
        template_resampled = template.copy()

    # Calculate sample interval between beats
    sample_interval = round(beat_interval * audio_sr)
    template_length = len(template_resampled)

    # Create multi-beat template with proper intervals
    total_length = template_length + (click_times - 1) * sample_interval
    full_template = np.zeros(total_length, dtype=template_resampled.dtype)
    for i in range(click_times):
        start_pos = i * sample_interval
        end_pos = start_pos + template_length
        if end_pos <= total_length:
            full_template[start_pos:end_pos] = template_resampled

    # Save the generated template to desktop
    # from scipy.io import wavfile
    # desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
    # output_file = os.path.join(desktop_path, "generated_template.wav")
    # normalized_template = full_template / (np.max(np.abs(full_template)) + 1e-8)
    # wavfile.write(output_file, int(audio_sr), normalized_template.astype(np.float32))

    return full_template


def template_match(audio_data, audio_sr, full_template):
    """
    在给定的音频中查找启动拍的最佳匹配位置 (ms)
    """
    if len(audio_data) < len(full_template):
        raise ValueError("Audio data too short for template matching")

    def rms_normalize(signal):
        rms = np.sqrt(np.mean(signal ** 2))
        return signal / (rms + 1e-8)

    audio_norm = rms_normalize(audio_data)
    template_norm = rms_normalize(full_template)

    # Perform normalized cross-correlation
    correlation = correlate(audio_norm, template_norm, mode='valid')

    # Normalize by template energy
    template_energy = np.sum(template_norm ** 2)
    if template_energy <= 0:
        raise ValueError("Template energy is zero")
    correlation = correlation / np.sqrt(template_energy)

    # Find the position of maximum correlation
    max_pos = int(np.argmax(correlation))

    # Compute match time in ms
    match_time = max_pos / float(audio_sr) * 1000

    return match_time


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
