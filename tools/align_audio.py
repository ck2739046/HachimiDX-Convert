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
    return offset



def calculate_audio_offset(file1_path, file2_path):
    """
    计算两个音频文件之间的时间偏移
    
    参数:
        file1_path: 基准音频文件路径
        file2_path: 待对齐音频文件路径
            
    返回:
        float: file2 相对于 file1 的偏移（毫秒）
               正值表示 file2 需要向后移动才能与 file1 对齐
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
            y1, sr1 = librosa.load(file1_path, sr=None, mono=False)
    except Exception as e:
        print(f"Error loading audio from file1: {e}")
        return None
    
    try:
        with suppress_audio_warnings():
            y2, sr2 = librosa.load(file2_path, sr=None, mono=False)
    except Exception as e:
        print(f"Error loading audio from file2: {e}")
        return None

    # 2. Resample to 44100 Hz
    target_sr = 44100
    if sr1 != target_sr:
        y1 = librosa.resample(y1, orig_sr=sr1, target_sr=target_sr)
        sr1 = target_sr
    if sr2 != target_sr:
        y2 = librosa.resample(y2, orig_sr=sr2, target_sr=target_sr)
        sr2 = target_sr
    
    y1_mono = librosa.to_mono(y1)
    y2_mono = librosa.to_mono(y2)

    # 3. Calculate offset
    offset_samples = find_best_alignment_offset(y1_mono, y2_mono)
    
    # 4. Convert to milliseconds
    offset_ms = (offset_samples / float(target_sr)) * 1000

    # build output
    if offset_ms == 0:
        final_str = "file1 equals file2"
    elif offset_ms > 0:
        final_str = "file2 is later than file1"
    else:
        final_str = "file2 is earlier than file1"
    
    print(f"Offset: {offset_ms:.2f} ms ({final_str})")
    return offset_ms

    # # 4. Align audio based on offset
    # print("Aligning audio based on offset...")
    # if offset > 0:
    #     y_drums_aligned = y_drums[..., offset:]
    #     y_no_drums_aligned = y_no_drums
    # else:
    #     y_drums_aligned = y_drums
    #     y_no_drums_aligned = y_no_drums[..., abs(offset):]

    # # 5. Crop audio length
    # min_len = min(y_drums_aligned.shape[-1], y_no_drums_aligned.shape[-1])
    # y_drums_aligned = y_drums_aligned[..., :min_len]
    # y_no_drums_aligned = y_no_drums_aligned[..., :min_len]

    # # 6. Subtract
    # drum_track = y_drums_aligned - y_no_drums_aligned

    # # 7. Audio Normalization
    # max_abs_val = np.max(np.abs(drum_track))
    # if max_abs_val > 0:
    #     drum_track /= max_abs_val
    # else:
    #     print("Warning: Subtraction result is silent, normalization skipped.")

    # # 8. Export mp3
    # try:
    #     output_mp3 = output_path + ".mp3"
    #     ffmpeg_path = shutil.which("ffmpeg")
    #     if not ffmpeg_path:
    #         print("ffmpeg not found, save as wav")
    #         output_wav_fallback = output_path + ".wav"
    #         sf.write(output_wav_fallback, drum_track.T, sr_drums, subtype='PCM_16')
    #         print(f"audio save to: {output_wav_fallback}")
    #         return



    #     with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
    #         tmp_wav_path = tmp_wav.name
    #     sf.write(tmp_wav_path, drum_track.T, sr_drums, subtype='PCM_16')

    #     print(f"Use ffmpeg to convert to MP3: {output_mp3}")
    #     cmd = [
    #         ffmpeg_path,
    #         "-y",
    #         "-i", tmp_wav_path,
    #         "-codec:a", "libmp3lame",
    #         "-b:a", "256k",
    #         output_mp3,
    #     ]
    #     result = subprocess.run(cmd, capture_output=True, text=True)
    #     try:
    #         os.remove(tmp_wav_path)
    #     except Exception:
    #         pass

    #     if result.returncode != 0:
    #         print("ffmpeg conversion failed.")
    #         print(result.stderr)
    #         print("Fallback: Saving as WAV...")
    #         output_wav_fallback = output_path + ".wav"
    #         sf.write(output_wav_fallback, drum_track.T, sr_drums, subtype='PCM_16')
    #         print(f"audio save to: {output_wav_fallback}")
    #         return

    #     print(f"success! MP3 save to {output_mp3}")
    # except Exception as e:
    #     print(f"Error saving audio: {e}")



if __name__ == '__main__':
    import sys
    
    if len(sys.argv) >= 3:
        file1 = sys.argv[1]
        file2 = sys.argv[2]
        
        offset = calculate_audio_offset(file1, file2)
        if offset is not None:
            print(f"\nFinal result: {offset:.2f} ms")
        else:
            print("\nFailed to calculate offset")
    else:
        print("Missing arguments.")
