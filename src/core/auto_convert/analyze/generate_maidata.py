import numpy as np
import os
import math
from pathlib import Path

from .shared_context import *
from ..detect.note_definition import *


def generate_maidata(shared_context: SharedContext, bpm, chart_lv, base_denominator, duration_denominator, notes_info):


    # 准备输出txt文件
    output_dir = shared_context.std_video_path.parent
    txt_path = output_dir / "maidata.txt"
    if os.path.exists(txt_path):
        os.remove(txt_path)

    # 写入文件头
    video_name = output_dir.name
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(f'&title={video_name}\n')
        f.write('&artist=default\n')
        f.write('&first=0\n')
        f.write(f'&des_{chart_lv}=default\n')
        f.write(f'&lv_{chart_lv}=15\n')
        f.write(f'&inote_{chart_lv}=({bpm})' + '{1},')

    # 打印基础信息
    level_label = ['zero', 'easy', 'basic', 'advanced', 'expert', 'master', 'remaster', 'special']
    print(f"\n{video_name} - {level_label[chart_lv]}")
    one_beat_Msec = 60 / bpm * 1000 * 4
    base_resolution = one_beat_Msec / base_denominator
    print(f"bpm: {bpm}, one beat: {one_beat_Msec:.3f} ms, base resolution: {base_resolution:.3f} ms")






    # 计算最小公倍数分母用于累加 (兼容1/12)
    if base_denominator >= 16:
        lcm_denom = base_denominator * 12 // math.gcd(base_denominator, 12)
    else:
        lcm_denom = base_denominator


    init_time = 0
    last_time = 0
    base_numerator_counter = 0
    last_position = None
    last_denominator = 0
    time_deviations = []






    with open(txt_path, 'a', encoding='utf-8') as f:
        for (track_id, note_type, note_varient, position), time in notes_info.items():

            note_time = check_note_time(time, track_id)
            if note_time is None:
                continue
            
            # 对于 slide, hold, touch_hold 可能存在 duration 信息
            if isinstance(time, tuple) and len(time) >= 2:
                duration_syntax = parse_note_duration(one_beat_Msec, note_type, time, base_denominator, duration_denominator)
                position += duration_syntax

            if last_time == 0:
                # 第一个音符
                init_time = note_time
                last_time = note_time
                last_position = position
                print(f"[{note_time:.3f}] ", end='')
                continue
            
            diff_Msec = note_time - last_time
            diff_beat = diff_Msec / one_beat_Msec
            numerator, denominator, one = get_fraction(diff_beat, base_denominator, enable_12=True)

            # update last_time
            # 使用最小公倍数分母进行累加 (为了兼容1/12)
            # 采用 init_time + 总passed_beat
            # 这是精确的谱面播放到此处的时间点，避免了累加误差
            base_numerator = round(diff_beat * lcm_denom)
            base_numerator_counter += base_numerator
            passed_beat = base_numerator_counter / lcm_denom
            passed_beat_Msec = passed_beat * one_beat_Msec
            last_time = passed_beat_Msec + init_time

            # 统计误差
            real_time_diff = note_time - init_time
            time_deviation = real_time_diff - passed_beat_Msec
            time_deviations.append(time_deviation)

            if numerator == 0 and one == 0:
                # 零间隔，使用 '/' 与上一个音符连接 
                last_position = f'{last_position}/{position}'
                continue
            
            # 打印当前音符信息
            if one > 0:
                print(f"{last_position}-{numerator}/{denominator}+{one}, ", end='')
            else:
                print(f"{last_position}-{numerator}/{denominator}, ", end='')

            # 生成逗号部分
            if numerator == 0 and denominator == 1 and one > 0:
                commas = f'{"," * one}'
            elif one > 0:
                commas = f'{"," * numerator}' + '{1}' + f'{"," * one}'
            else:
                commas = f'{"," * numerator}'

            # 将当前音符写入txt
            if denominator != last_denominator:
                f.write('\n{' + f'{denominator}' + '}' + f'{last_position}{commas}')
            else:
                f.write(f'{last_position}{commas}')

            if one > 0: denominator = 1
            last_denominator = denominator
            last_position = position
            









    # 添加结尾E
    print(f'{last_position}-E')
    with open(txt_path, 'a', encoding='utf-8') as f:
        f.write(f'{last_position},\n' + '{1},E\n')

    # 打印offset统计信息
    length = len(time_deviations)
    mean = np.mean(time_deviations)
    min = np.min(time_deviations)
    max = np.max(time_deviations)
    median = np.median(time_deviations)
    std_dev = np.std(time_deviations)
    print(f"Time deviations of {length} notes: Median {median:.3f}, Min {min:.3f}, Max {max:.3f}, Mean {mean:.3f}, Std Dev {std_dev:.3f}")





def get_best_numerator_denominator(diff_beat, input_denominator, enable_12):
    """在12和输入分母中选择误差最小的分母"""

    # 如果输入的分母 >=16，启用12作为备选分母
    candidates = [input_denominator]
    if input_denominator >= 16 and enable_12:
        candidates.append(12)
    
    # 选择误差最小的分母
    best_error = float('inf')
    best_total_numerator = 0
    best_denominator = input_denominator

    for denom in candidates:
        total_numerator = round(diff_beat * denom)
        # 零间隔
        if total_numerator == 0:
            error = abs(diff_beat)
            if error < best_error:
                best_error = error
                best_total_numerator = 0
                best_denominator = 1
            continue
        # 计算误差
        fraction_value = total_numerator / denom
        error = abs(diff_beat - fraction_value)
        if error < best_error:
            best_error = error
            best_total_numerator = total_numerator
            best_denominator = denom

    return best_total_numerator, best_denominator




def get_fraction(diff_beat, input_denominator, enable_12=True):
        # 返回格式：分子，分母，整数
        # 0.5  -> 1/2 + 0 -> 1, 2, 0
        # 1.0  -> 0/1 + 1 -> 0, 1, 1
        # 2.25 -> 1/4 + 2 -> 1, 4, 2
        
        raw_numerator, raw_denominator = get_best_numerator_denominator(diff_beat, input_denominator, enable_12)
        if raw_numerator == 0: return 0, 1, 0 # 零间隔直接返回
        # 获取整数和余数部分
        one = raw_numerator // raw_denominator
        remainder = raw_numerator % raw_denominator
        # 是整数，直接返回，不需要约分余数
        if remainder == 0: return 0, 1, one
        # 是小数，约分余数部分
        gcd_num = math.gcd(remainder, raw_denominator)
        numerator = remainder // gcd_num
        denominator = raw_denominator // gcd_num

        return numerator, denominator, one




def check_note_time(time, track_id):

    if isinstance(time, (float, int)):
        # check time
        if math.isnan(time) or time < 0:
            print(f"analyze_all_notes_info: invalid time value for track_id {track_id}, time: {time}")
            return None
        # 赋值
        return time

    elif isinstance(time, tuple):
        # check time tuple
        if len(time) == 0:
            print(f"analyze_all_notes_info: empty time tuple for track_id {track_id}")
            return None
        valid = True
        for i, t in enumerate(time):
            if not (isinstance(t, (float, int)) and not math.isnan(t) and t >= 0):
                print(f"analyze_all_notes_info: invalid time tuple element at index {i} for track_id {track_id}, value: {t}")
                valid = False
                break
        if not valid:
            return None
        # 赋值
        return time[0]

    else:
        print(f"analyze_all_notes_info: invalid time format for track_id {track_id}, time: {time}")
        return None




def parse_note_duration(one_beat_Msec, note_type, time, base_denominator, duration_denominator) -> str:

    # 提取 length 信息
    note_length = time[-1] - time[-2]
    length_beat = note_length / one_beat_Msec

    # 分类处理
    if note_type == NoteType.TOUCH_HOLD or note_type == NoteType.SLIDE:
        # touch_hold / slide -> duration_denominator
        denominator_to_use = duration_denominator
    else:
        # hold -> base_denominator
        # 因为 hold 头尾视为两个 tap，所以时值按照 base_denominator 处理
        denominator_to_use = base_denominator
    
    # 将 duration 变为分数形式
    numerator, denominator, one = get_fraction(length_beat, denominator_to_use, enable_12=False)
    # 将整数部分加入分子
    if one > 0:
        numerator = numerator + one * denominator
    # 异常情况默认变为10/1 (时值不能为0)
    if numerator == 0 and denominator == 1 and one == 0:
        numerator = 10
        denominator = 1

    duration_syntax = f'[{denominator}:{numerator}]'

    return duration_syntax
