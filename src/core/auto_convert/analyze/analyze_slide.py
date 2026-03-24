import numpy as np
from collections import defaultdict

from ..detect.note_definition import *
from .shared_context import *
from .analyze_tap import analyze_tap_time



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
        if movement_syntax is None:
            continue
        end_position = 'A' + movement_syntax[-1]

        # 计算持续时间
        start_time, end_time = analyze_slide_tail_start_end_time(shared_context, note_path, end_position, A_zone_endpoint_on_judgeline)
        if start_time is None or end_time is None:
            continue

        slide_tail_info[key] = (movement_syntax, start_time, end_time)

    return slide_tail_info







def guess_target_a_zone_by_inertia(shared_context, note_path, A_zone_endpoint_on_judgeline):
    '''
    根据倒数最后一段运动方向的惯性，猜测预测最终可能进入的A区。
    '''
    if len(note_path) < 2:
        return None
    
    # 寻找倒序最后一点 (点A)
    last_note = note_path[-1]
    A_cx = last_note['cx']
    A_cy = last_note['cy']
    
    # 倒序遍历寻找距离大于阈值的点 (点B)
    B_cx, B_cy = None, None
    min_dist = shared_context.std_video_size * 0.02 # 1080p下约为20像素
    
    for note in reversed(note_path[:-1]):
        cx = note['cx']
        cy = note['cy']
        dist = np.sqrt((cx - A_cx)**2 + (cy - A_cy)**2)
        if dist > min_dist:
            B_cx, B_cy = cx, cy
            break
            
    if B_cx is None or B_cy is None:
        return None
        
    # 运动向量 BA (从B指向A)
    BA_x = A_cx - B_cx
    BA_y = A_cy - B_cy
    BA_length = np.sqrt(BA_x**2 + BA_y**2)
    if BA_length == 0: return None # 理论上不会发生AB重合
        
    # 过滤并找出距离射线最近的点
    best_zone = None
    min_distance_to_line = 999999
    
    for zone_id in range(1, 9):
        zone_key = f'A{zone_id}'
        P_cx, P_cy = A_zone_endpoint_on_judgeline[zone_key]
        
        # 目标向量 AP (从A指向P)
        AP_x = P_cx - A_cx
        AP_y = P_cy - A_cy
        
        # 1. 筛选排查：利用点乘 (Dot Product) 判断是否在相反方向
        dot_product = BA_x * AP_x + BA_y * AP_y
        if dot_product < 0:
            continue  # 夹角 > 90度，说明目标点在跑过来的“背后”，排除
            
        # 2. 计算点到射线的距离：利用叉乘的绝对值 (Cross Product Area) / 底边长
        cross_product = abs(BA_x * AP_y - BA_y * AP_x)
        distance_to_line = cross_product / BA_length
        
        if distance_to_line < min_distance_to_line:
            min_distance_to_line = distance_to_line
            best_zone = zone_key
            
    return best_zone





def analyze_slide_tail_movement_syntax(shared_context, note_path, A_zone_endpoint_on_judgeline):
    '''
    分析运动模式
    暂时只检测边缘旋转 x>x / x<x
    其他的一律视为直线 x-x

    如果星星全程仅在A区或D区内移动，视为旋转
    '''    

    def get_outer_rotation_syntax(start_position, next_position, end_position):

        start_position_id = int(start_position[1]) # 'A1' -> 1
        next_position_id = int(next_position[1])   # 'A1' -> 1

        # 判断起始点在顶部还是底部
        if start_position_id in [1,2,7,8]:
            start_side = 'up'
        else:
            start_side = 'down'

        # 判断旋转方向
        # > 代表从起点开始箭头向右, < 代表从起点开始箭头向左
        if start_side == 'up':
            # 处理1和8的特殊情况
            if start_position_id == 1:
                if next_position_id in [6, 7, 8]:
                    next_position_id -= 8
            elif start_position_id == 8:
                if next_position_id in [1, 2, 3]:
                    next_position_id += 8
            # 判断方向
            if next_position_id > start_position_id:
                movement_type = '>'
            else:
                movement_type = '<'
        else: # start_side == 'down'
            if next_position_id > start_position_id:
                movement_type = '<'
            else:
                movement_type = '>'

        # 处理终点位置
        if end_position.startswith('A'):
            # 分支1：终点在A区
            # 直接作为终点位置
            end_position_id = int(end_position[1])
        else:
            # 分支2：终点在D区
            # 这种情况大概是因为星星提太快了，来不及进入A区就结束了
            # 终点位置应该是D区后面的那个A区
            
            # 判断旋转方向(顺时针/逆时针)
            if start_position_id == 1:
                if next_position_id in [6, 7, 8]:
                    next_position_id -= 8
            elif start_position_id == 8:
                if next_position_id in [1, 2, 3]:
                    next_position_id += 8
            
            if next_position_id > start_position_id:
                # 顺时针, D3 -> A3，序号不变
                end_position_id = int(end_position[1])
            else:
                # 逆时针, D3 -> A2，序号减一
                end_position_id = int(end_position[1]) - 1
                if end_position_id == 0:
                    end_position_id = 8 # D1 -> A8

        # 组合语法
        movement_syntax = f"{movement_type}{end_position_id}"
        return movement_syntax
    

    def is_consecutive(id1, id2):
            # 检查两个A区ID是否连续（考虑环形结构）
            # 顺时针：1->2, 2->3, ..., 7->8, 8->1
            if (id2 - id1) == 1 or (id1 == 8 and id2 == 1):
                return True, 'clockwise'
            # 逆时针：1->8, 8->7, ..., 2->1
            if (id1 - id2) == 1 or (id1 == 1 and id2 == 8):
                return True, 'counterclockwise'
            return False, None





    if len(note_path) < 6:
        return None
    positions = [x['position'] for x in note_path]
    if not positions or len(positions) < 6:
        return None

    start_position = positions[0]
    end_position = positions[-1]

    # 如果只在A区或D区移动，视为旋转
    if all(pos.startswith('A') or pos.startswith('D') for pos in positions):

        # 找到第一个与起始点不同的位置
        next_position = None
        for pos in positions[1:]:
            if pos != start_position:
                next_position = pos
                break
        if next_position is None:
            return None

        movement_syntax = get_outer_rotation_syntax(start_position, next_position, end_position)





    else:
        # 获得音符经过的所有A区判定点
        A_zones = []
        last_A_zone = ''
        for note in note_path:
            cx = note['cx']
            cy = note['cy']
            pos = note['position']
            if not pos.startswith('A'): continue
            if pos == last_A_zone: continue
            last_A_zone = pos
            A_zones.append(pos)
        
        # 考虑到有些星星速度太快，来不及进入A区就结束了
        # 需要根据惯性猜测最后可能进入哪个A区
        if not end_position.startswith('A'):
            guessed_zone = guess_target_a_zone_by_inertia(shared_context, note_path, A_zone_endpoint_on_judgeline)
            if guessed_zone and last_A_zone != guessed_zone:
                A_zones.append(guessed_zone)

        # 检测这个A区路径里边是否包含一些圆弧，要单独拆分出来
        arc_segments = []
        i = 0
        while i < len(A_zones):
            current_id = int(A_zones[i][1])  # 'A7' -> 7
            # 尝试检测从当前位置开始的圆弧
            if i + 1 < len(A_zones):
                next_id = int(A_zones[i + 1][1])
                is_consec, direction = is_consecutive(current_id, next_id)

                if is_consec:
                    # 找到圆弧的起点，继续向后查找相同方向的连续点
                    arc_start = current_id
                    arc_next = next_id
                    arc_end = next_id
                    j = i + 2
                    while j < len(A_zones):
                        check_id = int(A_zones[j][1])
                        prev_id = int(A_zones[j - 1][1])
                        is_consec_next, dir_next = is_consecutive(prev_id, check_id)
                        # 如果方向一致且连续，继续扩展圆弧
                        if is_consec_next and dir_next == direction:
                            arc_end = check_id
                            j += 1
                        else:
                            break
                    # 记录这个圆弧
                    arc_segments.append(('arc', (arc_start, arc_next, arc_end)))
                    i = j  # 跳过已处理的圆弧部分
                    continue
            
            # 不是圆弧的一部分，作为单独的点
            arc_segments.append(('single', current_id))
            i += 1
        
        
        # 将圆弧和单独的点组合成最终语法
        syntax_parts = []
        for seg_type, seg_data in arc_segments:
            if seg_type == 'arc':
                start_id, next_id, end_id = seg_data
                start_position, next_position, end_position = f"A{start_id}", f"A{next_id}", f"A{end_id}"
                arc_syntax = get_outer_rotation_syntax(start_position, next_position, end_position)
                syntax_parts.append(f"{start_id}{arc_syntax}")
            else:  # single
                syntax_parts.append(str(seg_data))
        
        movement_syntax = '-'.join(syntax_parts)
        movement_syntax = movement_syntax[1:] # 去掉最开头的起始位置

        # print(f'{" ".join(azone for azone in A_zones)} -> {movement_syntax}')

    return movement_syntax





def analyze_slide_tail_start_end_time(shared_context, note_path, end_position, A_zone_endpoint_on_judgeline):
    '''
    粗略计算持续时间

    根据每一帧之间的位移，计算音符的帧间移动速度，取中位数作为最终速度
    找到第一个离开起始A区的点，计算此时到A区中心的距离，配合速度计算时间
    这个时间就是音符从A区中心移动到此处所消耗的时间
    音符此时的帧时间 - 这个时间 = 反推出音符开始移动的时间
    同理，找到最后一个进入终点A区的点，计算得到音符停止移动的时间
    持续时间 = 停止时间 - 开始时间
    '''

    if len(note_path) < 6:
        return None, None
    positions = [x['position'] for x in note_path]
    if not positions or len(positions) < 6:
        return None, None

    # 计算帧间速度
    last_cx = None
    last_cy = None
    last_frame = None
    min_dist = shared_context.std_video_size * 0.04 # 1080p下约为40像素
    frame_speeds = []

    for point in note_path:
        frame_num = point['frame']
        cx = point['cx']
        cy = point['cy']

        if last_cx is not None and last_cy is not None and last_frame is not None:
            dist = np.sqrt((cx - last_cx)**2 + (cy - last_cy)**2)
            if dist < min_dist:
                continue # 两点间距过短，不能可靠计算速度，跳过
            frame_diff = frame_num - last_frame
            if frame_diff > 0:
                speed = dist / frame_diff
                frame_speeds.append(speed)

        last_cx = cx
        last_cy = cy
        last_frame = frame_num

    # 获取第60%的速度 (比中位数偏右一点)
    if not frame_speeds:
        return None, None
    index = round(len(frame_speeds) * 0.6)
    sorted_speeds = sorted(frame_speeds)
    note_speed = sorted_speeds[index]





    # 起点
    point = A_zone_endpoint_on_judgeline.get(positions[0], None)
    if point is None:
        return None, None
    start_cx, start_cy = point
    # 终点
    point = A_zone_endpoint_on_judgeline.get(end_position, None)
    if point is None:
        return None, None
    end_cx, end_cy = point

    # 定义A区中心半径
    a_zone_radius = (shared_context.note_travel_dist) / 7

    # 找到第一个离开起始A区的点
    start_move_frame = None
    dist_to_start = 0
    for point in note_path:
        frame_num = point['frame']
        cx = point['cx']
        cy = point['cy']
        dist_to_start = np.sqrt((cx - start_cx)**2 + (cy - start_cy)**2)
        if dist_to_start > a_zone_radius:
            start_move_frame = frame_num
            break
    
    # 计算开始时间
    if start_move_frame is None:
        return None, None
    time_to_start_Msec = (dist_to_start / note_speed) * (1000 / shared_context.fps)
    note_start_time_Msec = start_move_frame / shared_context.fps * 1000 - time_to_start_Msec

    # 找到最后一个进入终点A区的点
    end_move_frame = None
    dist_to_end = 0
    for i in range(len(note_path)-1, -1, -1): # 从后往前
        point = note_path[i]
        frame_num = point['frame']
        cx = point['cx']
        cy = point['cy']
        dist_to_end = np.sqrt((cx - end_cx)**2 + (cy - end_cy)**2)
        if dist_to_end > a_zone_radius:
            end_move_frame = frame_num
            break

    # 计算结束时间
    if end_move_frame is None:
        return None, None
    time_to_end_Msec = (dist_to_end / note_speed) * (1000 / shared_context.fps)
    note_end_time_Msec = end_move_frame / shared_context.fps * 1000 + time_to_end_Msec

    return note_start_time_Msec, note_end_time_Msec





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
