import numpy as np
from collections import defaultdict

from ..detect.note_definition import *
from .shared_context import *
from .analyze_tap import analyze_tap_time

from .analyze_slide_time import analyze_slide_tail_start_end_time
from .analyze_slide_movement import analyze_slide_tail_movement_syntax



def analyze_slide_time(shared_context, slide_head_data, slide_tail_data, bpm):

    # 处理星星头，视为 tap 处理
    slide_head_info = analyze_tap_time(shared_context, slide_head_data)
    
    # 处理星星尾
    slide_tail_info = analyze_slide_tail(shared_context, slide_tail_data)

    # 合并slide信息
    slide_info = merge_slide_info(shared_context, slide_head_info, slide_tail_info, bpm)

    return slide_info





def analyze_slide_tail(shared_context, slide_tail_data):
    '''
    返回格式:
    dict{
        key: 同 preprocess_slide_tail_data,
        value: (movement_syntax, start_time, end_time)
    }
    '''

    # 原点为(0, 0)，半径为480 (标准1080p)，标准xy坐标系
    # 判定线圆圈上的8个点
    std_dict = {
        'A1': (184, 443),
        'A2': (443, 184),
        'A3': (443, -183),
        'A4': (184, -443),
        'A5': (-183, -443),
        'A6': (-443, -183),
        'A7': (-443, 183),
        'A8': (-183, 443),
    }
    # 需要转换为屏幕坐标
    new_dict = {}
    for area_label, (x, y) in std_dict.items():
        # 转换成标准1080p屏幕坐标系
        # 原点是(540, 540)，y轴向下为正
        x_on_screen_cx = x + 540
        y_on_screen_cy = -y + 540
        # 按比例缩放到当前分辨率
        scaled_x = round((x_on_screen_cx - 540) * shared_context.std_video_size / 1080 + shared_context.std_video_cx)
        scaled_y = round((y_on_screen_cy - 540) * shared_context.std_video_size / 1080 + shared_context.std_video_cy)
        new_dict[area_label] = (scaled_x, scaled_y)

    A_zone_endpoint_on_judgeline = new_dict


    # 分析运动模式
    # 暂时只检测边缘旋转 x>x / x<x
    # 其他的一律视为直线 x-x
    slide_tail_info = {}
    for key, note_path in slide_tail_data.items():

        # 计算运动语法
        # 期望的返回: >5 / <3 / -7
        movement_syntax = analyze_slide_tail_movement_syntax(shared_context, note_path, A_zone_endpoint_on_judgeline)
        if not movement_syntax:
            print(f"analyze_slide_tail: failed to analyze movement syntax for track id {key[0]}")
            continue
        end_position = 'A' + movement_syntax[-1]

        # 计算持续时间
        start_time, end_time = analyze_slide_tail_start_end_time(shared_context, note_path, end_position, A_zone_endpoint_on_judgeline)
        if start_time is None or end_time is None:
            print(f"analyze_slide_tail: failed to analyze start/end time for track id {key[0]}")
            continue

        slide_tail_info[key] = (movement_syntax, start_time, end_time)

    return slide_tail_info







def merge_slide_info(shared_context, slide_head_info, slide_tail_info, bpm, delay_index=0.25):
    '''
    合并slide头尾信息
    输入: for (head_track_id, note_type, note_variant, head_position), head_end_time in slide_head_info.items():
          for (tail_track_id, note_type, note_variant, tail_start_position): (tail_movement_syntax, tail_start_time, tail_end_time) in slide_tail_info.items():

    将这两组进行匹配：
    delay = tail_start_time - head_end_time
    规则1：head_position = tail_start_position
    规则2：min_delay < delay < max_delay
    规则3：一个tail最多只能匹配到一个head，但是一个head可以匹配多个tail
    规则4：如果tail与多个head都符合匹配条件，选择delay与std_delay最接近的head

    返回格式:
    dict{
        # 匹配的head_tail组合
        key: (head_track_id, note_type, note_variant, full_movement_syntax),
        value: (time, duration)

        # 未匹配的head
        key: (head_track_id, note_type, note_variant, head_position),
        value: time
    }
    '''

    def get_suffix(note_variant: NoteVariant):

        if note_variant == NoteVariant.NORMAL:
            suffix = ''
        elif note_variant == NoteVariant.BREAK:
            suffix = 'b'
        elif note_variant == NoteVariant.EX:
            suffix = 'x'
        elif note_variant == NoteVariant.BREAK_EX:
            suffix = 'bx'
        else:
            suffix = '?'
        
        return suffix




    final_slide_info = {}

    # 标准延迟是0.25拍
    one_beat_Msec = 60 / bpm * 1000 * 4
    std_delay = one_beat_Msec * delay_index
    max_delay = std_delay * 1.2
    min_delay = std_delay * 0.8

    # print(f"\n=== Matching Parameters ===")
    # print(f"BPM: {bpm}, One Beat: {one_beat_Msec:.2f} ms")
    # print(f"Std Delay: {std_delay:.2f} ms")
    # print(f"Min Delay: {min_delay:.2f} ms")
    # print(f"Max Delay: {max_delaye:.2f} ms")
    # print(f"===========================\n")

    # 先按位置分组head数据
    # 这样后续tail查找head时，只会在对应位置的head中查找，减少计算量
    head_by_position = defaultdict(list)
    for (track_id, note_type, note_variant, head_position), head_end_time in slide_head_info.items():
        # 此处的head_position是带有variant后缀的，如 1bx，需要去除
        new_position = str(head_position[0])
        head_by_position[new_position].append((track_id, note_type, note_variant, head_position, head_end_time))

    # 记录哪些head_track_id被匹配了，使用set避免重复
    matched_head_track_ids = set()

    # 遍历所有tail，寻找匹配的head
    processed_tails = 0
    for (tail_track_id, tail_note_type, tail_note_variant, tail_start_position), (tail_movement_syntax, tail_start_time, tail_end_time) in slide_tail_info.items():
        processed_tails += 1

        # 先看看有没有任何与tail位置相同的head
        tail_start_position = str(tail_start_position)
        if tail_start_position not in head_by_position.keys():
            print(f"[{tail_track_id}] Tail not match: No heads at position {tail_start_position}")
            continue
        # 如果有，遍历这些head，寻找符合delay条件的head
        # 条件1：min_delay < delay < max_delay
        # 条件2：与std_delay最接近
        best_head = None
        best_delay_diff = float('inf')
        for head_track_id, head_note_type, head_note_variant, head_position, head_end_time in head_by_position[tail_start_position]:
            # 条件1
            delay = tail_start_time - head_end_time
            if not (min_delay < delay < max_delay):
                continue
            # 条件2
            delay_diff = abs(delay - std_delay)
            if delay_diff < best_delay_diff:
                best_delay_diff = delay_diff
                best_head = (head_track_id, head_note_type, head_note_variant, head_position, head_end_time)

        if best_head is None:
            print(f"[{tail_track_id}] Tail not match: No heads match delay at position {tail_start_position}")
            continue

        # 找到了匹配的head，进行记录
        head_track_id, head_note_type, head_note_variant, head_position, head_end_time = best_head
        matched_head_track_ids.add(head_track_id)

        # # 由于未知原因，星星时长总是长了1/16拍，进行修正
        # tail_end_time -= one_beat_Msec / 16

        # 写入final_slide_info
        full_movement_syntax = f"{tail_start_position}{get_suffix(head_note_variant)}{tail_movement_syntax}{get_suffix(tail_note_variant)}"
        key = (head_track_id, head_note_type, head_note_variant, full_movement_syntax)
        duration = tail_end_time - tail_start_time
        value = (head_end_time, duration)
        final_slide_info[key] = value



    # 将未匹配的head也写入final_slide_info
    for (head_track_id, head_note_type, head_note_variant, head_position), head_end_time in slide_head_info.items():
        if head_track_id not in matched_head_track_ids:
            full_movement_syntax = f"{head_position}$"
            key = (head_track_id, head_note_type, head_note_variant, full_movement_syntax)
            value = head_end_time
            final_slide_info[key] = value

    # # 打印final_slide_info
    # print("\n=== Final Slide Info ===")
    # for (track_id, class_id, movement_syntax), time_info in final_slide_info.items():
    #     if isinstance(time_info, tuple):
    #         head_end_time, tail_start_time, tail_end_time = time_info
    #         print(f"Slide Note: Track ID {track_id}, Class ID {class_id}, Movement {movement_syntax}, Head End Time {head_end_time:.2f} ms, Tail Start Time {tail_start_time:.2f} ms, Tail End Time {tail_end_time:.2f} ms")
    #     else:
    #         head_end_time = time_info
    #         print(f"Single Slide Note: Track ID {track_id}, Class ID {class_id}, Movement {movement_syntax}, Head End Time {head_end_time:.2f} ms")

    return final_slide_info
