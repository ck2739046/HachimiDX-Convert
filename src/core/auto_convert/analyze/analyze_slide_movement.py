import numpy as np



def guess_target_a_zone_by_inertia(shared_context, note_path):
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
        P_cx, P_cy = shared_context.a_zone_endpoint[zone_key]
        
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





def analyze_slide_tail_movement_syntax(shared_context, note_path):
    '''
    分析运动模式
    暂时只检测边缘旋转 x>x / x<x
    其他的一律视为直线 x-x

    如果星星全程仅在A区或D区内移动，视为旋转
    '''    

    guessed_zone = None

    
    


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

    # 获得音符经过的所有A区判定点
    A_zones = []
    last_A_zone = ''
    for note in note_path:
        pos = note['position']
        if not pos.startswith('A'): continue
        if pos == last_A_zone: continue
        last_A_zone = pos
        A_zones.append(pos)

    if not A_zones: return None

    # 考虑到有些星星速度太快，来不及进入A区就结束了
    # 需要根据惯性猜测最后可能进入哪个A区
    if not end_position.startswith('A'):
        guessed_zone = guess_target_a_zone_by_inertia(shared_context, note_path)
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
                reverse_turn = False
                while j < len(A_zones):
                    check_id = int(A_zones[j][1])
                    prev_id = int(A_zones[j - 1][1])
                    is_consec_next, dir_next = is_consecutive(prev_id, check_id)
                    # 如果方向一致且连续，继续扩展圆弧
                    if is_consec_next and dir_next == direction:
                        arc_end = check_id
                        j += 1
                    else:
                        # 连续但方向变化，说明遇到折返，下一段应从拐点重新开始
                        if is_consec_next and dir_next != direction:
                            reverse_turn = True
                        break
                # 记录这个圆弧
                arc_segments.append(('arc', (arc_start, arc_next, arc_end)))

                if reverse_turn:
                    i = j - 1 # 折返时保留拐点作为下一段起点；否则正常跳过
                else:
                    i = j # 跳过已处理的圆弧部分
                continue

        # 不是圆弧的一部分，作为单独的点
        arc_segments.append(('single', current_id))
        i += 1


    # 将圆弧和单独的点组合成最终语法
    movement_syntax = ''
    last_end_id = None
    for seg_type, seg_data in arc_segments:

        if seg_type == 'arc':
            start_id, next_id, end_id = seg_data
            arc_syntax = _get_arc_syntax(start_id, next_id, end_id)
            new_syntax = f"{start_id}{arc_syntax}"
        else:  # single
            new_syntax = str(seg_data)
            end_id = seg_data

        # 特例：首个语法直接添加，不需要连接符
        if not movement_syntax:
            movement_syntax = new_syntax
            last_end_id = end_id
            continue

        # 特例：弧形折返，前一段终点与后一段起点相同，直接拼接
        # 例如 6<3 + >6 -> 6<3>6
        if seg_type == 'arc' and last_end_id == start_id:
            movement_syntax += arc_syntax
            last_end_id = end_id
            continue
        
        # 普通场景
        movement_syntax += f"-{new_syntax}"
        last_end_id = end_id

    movement_syntax = movement_syntax[1:] # 去掉最开头的起始位置

    # print(f'{" ".join(azone for azone in A_zones)} -> {movement_syntax}')

    return movement_syntax






def _get_arc_syntax(start_position: int, next_position: int, end_position: int) -> str:
    """
    Args: A zone id (1-8)
    Returns: movement syntax like '>5' or '<3'
    """

    # 判断起始点在顶部还是底部
    if start_position in [1,2,7,8]:
        start_side = 'up'
    else:
        start_side = 'down'

    # 判断旋转方向
    # > 代表从起点开始箭头向右, < 代表从起点开始箭头向左
    if start_side == 'up':
        # 处理1和8的特殊情况
        if start_position == 1:
            if next_position in [6, 7, 8]:
                next_position -= 8
        elif start_position == 8:
            if next_position in [1, 2, 3]:
                next_position += 8
        # 判断方向
        if next_position > start_position:
            movement_type = '>'
        else:
            movement_type = '<'
    else: # start_side == 'down'
        if next_position > start_position:
            movement_type = '<'
        else:
            movement_type = '>'

    # 组合语法
    movement_syntax = f"{movement_type}{end_position}"
    return movement_syntax
