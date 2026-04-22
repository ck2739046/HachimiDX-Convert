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


    # 分析运动模式
    slide_tail_info = {}
    for key, note_path in slide_tail_data.items():

        # 计算运动语法
        # 期望的返回: >5 / <3 / -7
        result = analyze_slide_tail_movement_syntax(shared_context, note_path, key[3], key[4])
        if result is None:
            print(f"analyze_slide_tail: failed to analyze movement syntax for track id {key[0]}")
            continue
        movement_syntax, start_pos, end_pos = result
        if not movement_syntax:
            print(f"analyze_slide_tail: failed to analyze movement syntax for track id {key[0]}")
            continue
        
        # 计算持续时间
        start_time, end_time = analyze_slide_tail_start_end_time(shared_context, note_path, start_pos, end_pos)
        if start_time is None or end_time is None:
            print(f"analyze_slide_tail: failed to analyze start/end time for track id {key[0]}")
            continue

        slide_tail_info[key] = (movement_syntax, start_time, end_time)

    return slide_tail_info







def merge_slide_info(shared_context, slide_head_info, slide_tail_info, bpm, delay_index=0.25):
    '''
    合并slide头尾信息
    输入: for (head_track_id, note_type, note_variant, head_position), head_end_time in slide_head_info.items():
          for (tail_track_id, note_type, note_variant, tail_start_position, tail_end_position): (tail_movement_syntax, tail_start_time, tail_end_time) in slide_tail_info.items():

    将这两组进行匹配：
    delay = tail_start_time - head_end_time
    规则1：head_position = tail_start_position
    规则2：min_delay < delay < max_delay
    规则3：一个tail最多只能匹配到一个head，但是一个head可以匹配多个tail
    规则4：如果tail与多个head都符合匹配条件，选择delay与std_delay最接近的head

    返回格式:
    dict{
        # 匹配的 head_tail 组合（同 head 多 tail 用 * 聚合）
        key: (head_track_id, note_type, note_variant, merged_movement_syntax),
        value: (time, duration_1, duration_2, ...)

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

    # 收集每个 head 匹配到的 tail 列表，后续方便聚合同头星星
    matched_tails_by_head = defaultdict(list)

    # 遍历所有tail，寻找匹配的head
    processed_tails = 0
    for (tail_track_id, tail_note_type, tail_note_variant, tail_start_position, tail_end_position), (tail_movement_syntax, tail_start_time, tail_end_time) in slide_tail_info.items():
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

        # 找到了匹配的head，暂存匹配结果
        head_track_id, head_note_type, head_note_variant, head_position, head_end_time = best_head
        duration = tail_end_time - tail_start_time
        matched_tails_by_head[head_track_id].append({
            'tail_track_id': tail_track_id,
            'tail_note_variant': tail_note_variant,
            'tail_movement_syntax': tail_movement_syntax,
            'tail_start_time': tail_start_time,
            'duration': duration,
            'head_note_type': head_note_type,
            'head_note_variant': head_note_variant,
            'head_position': str(head_position[0]),
            'head_end_time': head_end_time,
        })


    # 将匹配成功的 head 聚合写入 final_slide_info
    for (head_track_id, head_note_type, head_note_variant, head_position), head_end_time in slide_head_info.items():
        if head_track_id in matched_tails_by_head:
            matched_tails = matched_tails_by_head[head_track_id]

            head_start_pos = str(head_position[0])
            head_prefix = f"{head_start_pos}{get_suffix(head_note_variant)}"

            segment_syntax_list = []
            segment_durations = []
            for item in matched_tails:
                seg_full_syntax = f"{head_start_pos}{get_suffix(head_note_variant)}{item['tail_movement_syntax']}{get_suffix(item['tail_note_variant'])}"
                segment_syntax_list.append(seg_full_syntax)
                segment_durations.append(item['duration'])

            # 组装链式语法（仅语法，不含时值）
            merged_movement_syntax = segment_syntax_list[0] # 第一个segment完整保留
            for seg_full_syntax in segment_syntax_list[1:]:
                # 尝试删除后续的同头星星的的起始头
                seg_tail_syntax = None
                if seg_full_syntax.startswith(head_prefix):
                    seg_tail_syntax = seg_full_syntax[len(head_prefix):]
                if not seg_tail_syntax:
                    # 前缀剥离失败，回退为 '/' 连接整段语法
                    merged_movement_syntax += f"/{seg_full_syntax}"
                    continue
                merged_movement_syntax += f"*{seg_tail_syntax}"

            key = (head_track_id, head_note_type, head_note_variant, merged_movement_syntax)
            value = (head_end_time, *segment_durations)
            final_slide_info[key] = value

        else:
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
