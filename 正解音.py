import librosa
import numpy as np
import soundfile as sf
from scipy import signal
import os
import subprocess
import shutil
import tempfile

def find_best_alignment_offset(signal1, signal2):

    print("calculate audio offset...")

    if signal1.ndim > 1:
        signal1 = signal1.mean(axis=1)
    if signal2.ndim > 1:
        signal2 = signal2.mean(axis=1)

    correlation = signal.correlate(signal1, signal2, mode='full', method='fft')

    lag_index = np.argmax(correlation)
    
    offset = lag_index - (len(signal2) - 1)

    print(f"calculate completed. Detected sample offset is: {offset}")
    return offset



def align_and_subtract(with_drums_path, no_drums_path, output_path):

    if not os.path.exists(with_drums_path):
        print(f"file not found -> {with_drums_path}")
        return
    if not os.path.exists(no_drums_path):
        print(f"file not found -> {no_drums_path}")
        return

    # 1. Load audio files
    try:
        y_drums, sr_drums = librosa.load(with_drums_path, sr=None, mono=False)
        y_no_drums, sr_no_drums = librosa.load(no_drums_path, sr=None, mono=False)
    except Exception as e:
        print(f"Error loading audio: {e}")
        return

    # 2. Resample to 44100 Hz
    target_sr = 44100
    if sr_drums != target_sr:
        print(f"Warning: Drums audio sample rate is {sr_drums} Hz, resampling to {target_sr} Hz...")
        y_drums = librosa.resample(y_drums, orig_sr=sr_drums, target_sr=target_sr)
        sr_drums = target_sr
    if sr_no_drums != target_sr:
        print(f"Warning: No-drums audio sample rate is {sr_no_drums} Hz, resampling to {target_sr} Hz...")
        y_no_drums = librosa.resample(y_no_drums, orig_sr=sr_no_drums, target_sr=target_sr)
        sr_no_drums = target_sr
    
    y_drums_mono = librosa.to_mono(y_drums)
    y_no_drums_mono = librosa.to_mono(y_no_drums)

    # 3. Calculate offset
    offset = find_best_alignment_offset(y_drums_mono, y_no_drums_mono)

    # 4. Align audio based on offset
    print("Aligning audio based on offset...")
    if offset > 0:
        y_drums_aligned = y_drums[..., offset:]
        y_no_drums_aligned = y_no_drums
    else:
        y_drums_aligned = y_drums
        y_no_drums_aligned = y_no_drums[..., abs(offset):]

    # 5. Crop audio length
    min_len = min(y_drums_aligned.shape[-1], y_no_drums_aligned.shape[-1])
    y_drums_aligned = y_drums_aligned[..., :min_len]
    y_no_drums_aligned = y_no_drums_aligned[..., :min_len]

    # 6. Subtract
    drum_track = y_drums_aligned - y_no_drums_aligned

    # 7. Audio Normalization
    max_abs_val = np.max(np.abs(drum_track))
    if max_abs_val > 0:
        drum_track /= max_abs_val
    else:
        print("Warning: Subtraction result is silent, normalization skipped.")

    # 8. Export mp3
    try:
        output_mp3 = output_path + ".mp3"
        ffmpeg_path = shutil.which("ffmpeg")
        if not ffmpeg_path:
            print("ffmpeg not found, save as wav")
            output_wav_fallback = output_path + ".wav"
            sf.write(output_wav_fallback, drum_track.T, sr_drums, subtype='PCM_16')
            print(f"audio save to: {output_wav_fallback}")
            return



        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
            tmp_wav_path = tmp_wav.name
        sf.write(tmp_wav_path, drum_track.T, sr_drums, subtype='PCM_16')

        print(f"Use ffmpeg to convert to MP3: {output_mp3}")
        cmd = [
            ffmpeg_path,
            "-y",
            "-i", tmp_wav_path,
            "-codec:a", "libmp3lame",
            "-b:a", "256k",
            output_mp3,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        try:
            os.remove(tmp_wav_path)
        except Exception:
            pass

        if result.returncode != 0:
            print("ffmpeg conversion failed.")
            print(result.stderr)
            print("Fallback: Saving as WAV...")
            output_wav_fallback = output_path + ".wav"
            sf.write(output_wav_fallback, drum_track.T, sr_drums, subtype='PCM_16')
            print(f"audio save to: {output_wav_fallback}")
            return

        print(f"success! MP3 save to {output_mp3}")
    except Exception as e:
        print(f"Error saving audio: {e}")



if __name__ == '__main__':

    # 带有鼓点的音频文件
    audio_with_drums = r"C:\Users\ck273\Desktop\[maimai谱面确认] Amereistr MASTER-p01-116_audio_index0.aac"
    
    # 没有鼓点的音频文件
    audio_without_drums = r"C:\Users\ck273\Desktop\Amereistr\track.mp3"
    
    # 输出的纯鼓点文件
    output_drum_track = r"C:\Users\ck273\Desktop\drum_track"
    
    # --- 文件路径修改结束 ---

    align_and_subtract(audio_with_drums, audio_without_drums, output_drum_track)

    # 原始音频需要走一遍mcm压缩再导出 (待实现)
