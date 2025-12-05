import librosa
import numpy as np
from scipy import signal
import os
import warnings
import sys
from contextlib import contextmanager


@contextmanager
def suppress_audio_warnings():
    """抑制音频加载时的警告和错误信息"""
    # 抑制 librosa FutureWarning
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=FutureWarning, module="librosa")
        warnings.filterwarnings("ignore", message='PySoundFile failed. Trying audioread instead.')
        yield


def find_best_alignment_offset(signal1, signal2):
    """
    计算两个音频信号之间的时间偏移
    
    参数:
        signal1: 基准音频信号
        signal2: 待对齐音频信号
            
    返回:
        int: 样本偏移量（正值表示signal2需要向后移动）
    """

    # --- 零均值标准化 (Zero-Mean / Z-Score) ---
    # 1. 减去均值：消除直流偏移（DC Offset）和低频背景噪音的影响
    # 2. 除以标准差：消除音量大小差异（游戏音效大或者音乐声音小都不受影响）
    
    def standardize(sig):
        # 减去均值 (Center)
        sig = sig - np.mean(sig)
        # 除以标准差 (Scale)，加 eps 防止除以零
        std = np.std(sig)
        return sig / (std + 1e-8)
    
    sig1_norm = standardize(signal1)
    sig2_norm = standardize(signal2)
    
    # 执行互相关 (FFT加速)
    correlation = signal.correlate(sig1_norm, sig2_norm, mode='full', method='fft')

    lag_index = np.argmax(correlation)
    offset = lag_index - (len(signal2) - 1)
    
    return offset


def calculate_audio_offset(file1_path, file2_path):
    """
    计算两个音频文件之间的时间偏移
        
    参数:
        file1_path: 基准音频文件路径
        file2_path: 待对齐音频文件路径
            
    返回:
        dict: 包含对齐结果和音频数据的字典
            - offset_ms: file2 相对于 file1 的偏移（毫秒）
                       正值表示 file2 需要向后移动才能与 file1 对齐
            - reference_audio: 基准音频数据 (44100Hz)
            - target_audio: 目标音频数据 (44100Hz)
            
        None: 如果发生错误
    """
    if not os.path.exists(file1_path):
        print(f"file not found -> {file1_path}")
        return None
    if not os.path.exists(file2_path):
        print(f"file not found -> {file2_path}")
        return None

    # 1. Load audio files
    try:
        with suppress_audio_warnings():
            y1, sr1 = librosa.load(file1_path, sr=None, mono=True) # 直接加载为 Mono
    except Exception as e:
        print(f"Error loading audio from file1: {e}")
        return None
    
    try:
        with suppress_audio_warnings():
            y2, sr2 = librosa.load(file2_path, sr=None, mono=True)
    except Exception as e:
        print(f"Error loading audio from file2: {e}")
        return None

    # 2. Resample to 44100 Hz
    target_sr = 44100
    if sr1 != target_sr:
        y1 = librosa.resample(y1, orig_sr=sr1, target_sr=target_sr)
    if sr2 != target_sr:
        y2 = librosa.resample(y2, orig_sr=sr2, target_sr=target_sr)
    
    # 3. Calculate offset
    offset_samples = find_best_alignment_offset(y1, y2)
    
    # 4. Convert to milliseconds
    offset_ms = (offset_samples / float(target_sr)) * 1000

    # build output
    if offset_ms == 0:
        final_str = "file1 equals file2"
    elif offset_ms > 0:
        final_str = "file2 is earlier than file1"
    else:
        final_str = "file2 is later than file1"
    
    print(f"{offset_ms:.2f} ms ({final_str})")
    
    # 返回对齐结果和音频数据用于可视化
    return {
        'offset_ms': offset_ms,
        'reference_audio': y1,
        'target_audio': y2
    }



if __name__ == '__main__':
    
    if len(sys.argv) >= 3:
        file1 = sys.argv[1]
        file2 = sys.argv[2]
        
        offset = calculate_audio_offset(file1, file2)
        if offset is not None:
            print(f"\nFinal result: {offset['offset_ms']:.2f} ms")
        else:
            print("\nFailed to calculate offset")
    else:
        print("Missing arguments.")
