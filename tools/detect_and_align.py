import sys
import os
import json
import io
from detect_click_start import main as detect_click_start_main
from align_audio import calculate_audio_offset

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
    
    返回:
        dict: detect_click_start, align_audio, final_time
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

    print(f"  reference_file: {reference_file}")
    print(f"  target_file: {target_file}")
    print(f"  beat_count: {beat_count}")
    print(f"  bpm: {bpm}")
    
    results = {}
    

    # 1. 调用 detect_click_start 分析基准文件
    print("\n根据启动拍分析基准文件的音频起始时间...")
    
    detect_result = detect_click_start_main(reference_file, bpm, beat_count)
    if detect_result is not None and detect_result >= 0:
        results['detect_click_start'] = detect_result
        print(f"{detect_result:.2f} ms")
    else:
        results['detect_click_start'] = None
        print("分析失败")
        return results
    

    # 2. 调用 align_audio 分析文件对齐
    print("\n对齐基准文件和目标文件...")
    
    align_result = calculate_audio_offset(reference_file, target_file)
    if align_result is not None:
        results['align_audio'] = align_result
    else:
        results['align_audio'] = None
        print("对齐失败")
        return results
    

    # 3. 计算最终结果
    print("\n计算最终结果...")
    
    # 最终时间 = 基准文件启动拍时间 + 对齐偏移
    final_time = results['detect_click_start'] + results['align_audio']
    results['final_time'] = final_time
    print(f"最终时间: {final_time:.2f} ms")
    
    return results


if __name__ == '__main__':
    main()
