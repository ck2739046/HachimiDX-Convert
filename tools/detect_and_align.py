import sys
import os
import json
import io
from detect_click_start import main as detect_click_start_main
from align_audio import calculate_audio_offset
import draw_audio_wave 

# 解决 Windows 控制台 Unicode 编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def main():
    """
    整合 detect_click_start 和 align_audio 功能
    
    参数:
        reference_file (str): 基准文件路径（包含完整启动拍）
        target_file (str): 待对齐文件路径
        beat_count (int): 启动拍数量
        bpm (float): 启动拍的BPM值
        duration (int): 仅加载前多少秒
    
    返回:
        final_time
    """

    if len(sys.argv) <= 1:
        print("Error: no JSON file path provided.")
        sys.exit(1)

    json_path = sys.argv[1]
    if not os.path.exists(json_path):
        print(f"Error: JSON file does not exist: {json_path}")
        sys.exit(1)

    # 读取临时 JSON 文件
    print(f"Loading JSON file: {json_path}")
    with open(json_path, 'r', encoding='utf-8') as f:
        params = json.load(f)
    # 删除临时 JSON 文件
    try:
        os.remove(json_path)
    except:
        pass
    
    # 从参数字典中提取参数
    reference_file = params.get('reference_file')
    target_file = params.get('target_file')
    beat_count = params.get('beat_count')
    bpm = params.get('bpm')
    duration = params.get('duration')

    print(f"  reference_file: {reference_file}")
    print(f"  target_file: {target_file}")
    print(f"  beat_count: {beat_count}")
    print(f"  bpm: {bpm}")
    print(f"  duration: {duration}")
    
    

    # 1. 调用 detect_click_start 分析基准文件
    print("\n根据启动拍分析基准文件的音频起始时间...")
    detect_result_dict = detect_click_start_main(reference_file, bpm, beat_count, duration)
    if detect_result_dict is not None:
        detect_result = detect_result_dict['adjusted_match_time']
        match_time = detect_result_dict['match_time']
        generated_template = detect_result_dict['generated_template']
        print(f"{detect_result:.2f} ms")
    else:
        print("分析失败")
        return None
    

    # 2. 调用 align_audio 分析文件对齐
    print("\n对齐基准文件和目标文件...")
    align_result_dict = calculate_audio_offset(reference_file, target_file)
    if align_result_dict is None:
        print("对齐失败")
        return None
    align_result = align_result_dict['offset_ms']
    reference_audio = align_result_dict['reference_audio']
    target_audio = align_result_dict['target_audio']
    

    # 3. 计算最终结果
    final_time = detect_result - align_result
    print(f"\n在基准文件中，音频从 {detect_result:.2f} ms 开始")
    print(f"在基准文件中，目标文件的音频从 {align_result:.2f} ms 开始")
    if abs(final_time) < 0.01:
        print("已经对齐了，无需调整")
    elif final_time > 0:
        print(f"目标文件需要提前 {final_time:.2f} ms")
    else:
        print(f"目标文件需要延后 {abs(final_time):.2f} ms")
    
    # 4. 生成音频波形图
    print("\n生成音频波形图...")
    try:
        draw_audio_wave.main(
            reference_audio=reference_audio,
            template_audio=generated_template,
            target_audio=target_audio,
            match_time=match_time,
            align_result=align_result,
            adjusted_match_time=detect_result
        )
    except Exception as e:
        print(f"波形图生成失败: {e}")
    
    return final_time



if __name__ == '__main__':
    main()
