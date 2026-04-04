import numpy as np

shared_context = None


def analyze_slide_tail_movement_syntax(input_shared_context, note_path):
    '''
    分析运动模式
    暂时只检测边缘旋转 x>x / x<x
    其他的一律视为直线 x-x

    如果星星全程仅在A区或D区内移动，视为旋转
    '''

    global shared_context
    shared_context = input_shared_context


    if len(note_path) < 6:
        return None
    positions = [x['position'] for x in note_path]
    if not positions or len(positions) < 6:
        return None
    
    note_path_segments = _divide_path_by_A_zone(note_path)
    classified_segments = []
    for note_path_segment, start_A_zone, end_A_zone in note_path_segments:

        start_A_zone_id = int(start_A_zone[1])
        end_A_zone_id = int(end_A_zone[1])

        # 对一个 segemnt, 只有几种情况:

        #   -  : straight
        #  > < : arc
        #   v  : center_reflection
        #  p q : inner loop
        #  z s : zigzag
        # pp qq: outer loop

        #   V  : a-zone-reflection 经过多个A区，会被拆分，忽略

        is_straight, syntax = is_straight(note_path_segment, start_A_zone_id, end_A_zone_id)
        if is_straight:
            classified_segments.append(('straight', syntax))
            continue

        is_arc, syntax = is_arc(note_path_segment, start_A_zone_id, end_A_zone_id)
        if is_arc:
            classified_segments.append(('arc', syntax))
            continue

        is_center_reflection, syntax = is_center_reflection(note_path_segment, start_A_zone_id, end_A_zone_id)
        if is_center_reflection:
            classified_segments.append(('center_reflection', syntax))
            continue

        is_inner_loop, syntax = is_inner_loop(note_path_segment, start_A_zone_id, end_A_zone_id)
        if is_inner_loop:
            classified_segments.append(('inner_loop', syntax))
            continue

        is_zigzag, syntax = is_zigzag(note_path_segment, start_A_zone_id, end_A_zone_id)
        if is_zigzag:
            classified_segments.append(('zigzag', syntax))
            continue

        is_outer_loop, syntax = is_outer_loop(note_path_segment, start_A_zone_id, end_A_zone_id)
        if is_outer_loop:
            classified_segments.append(('outer_loop', syntax))
            continue

        # 无法识别, syntax fallback to straight
        classified_segments.append(('unknown', f'{start_A_zone_id}-{end_A_zone_id}'))










def is_straight(note_path: list, start_A_zone_id: int, end_A_zone_id: int) -> tuple[bool, str]:

    pos_diff = _get_pos_diff(start_A_zone_id, end_A_zone_id)
    
    if pos_diff == 0:
        # 直线不可能起点和终点相同
        return False, None
    if pos_diff == 1:
        # 直线不可能是相邻的A区
        return False, None
    
    positions = [x['position'] for x in note_path]
    required = []
    optional = []
    banned = []

    # 必须激活起点/终点
    required.append(f'A{start_A_zone_id}')
    required.append(f'A{end_A_zone_id}')
    
    if pos_diff == 2:
        # 可选激活之间的 AB 区
        between_AB_zones_id = _get_between_AB_zones(start_A_zone_id, end_A_zone_id)
        for id in between_AB_zones_id:
            optional.append(f'A{id}')
            optional.append(f'B{id}')
        # 可选激活之间的 DE 区
        between_DE_zones_id = _get_between_DE_zones(start_A_zone_id, end_A_zone_id)
        for id in between_DE_zones_id:
            optional.append(f'D{id}')
            optional.append(f'E{id}')
        
    if pos_diff == 3:
        # 必须激活之间的 B 区
        between_AB_zones_id = _get_between_AB_zones(start_A_zone_id, end_A_zone_id)
        for id in between_AB_zones_id:
            required.append(f'B{id}')
        # 可选激活之间的 E 区 (排除中间)
        between_DE_zones_id = _get_between_DE_zones(start_A_zone_id, end_A_zone_id)
        optional.append(f'E{between_DE_zones_id[0]}')
        optional.append(f'E{between_DE_zones_id[-1]}')
        
    if pos_diff == 4:
        # 必须激活 C 区
        required.append(f'C1')
        # 必须激活 B 区
        required.append(f'B{start_A_zone_id}')
        required.append(f'B{end_A_zone_id}')

    # 检查
    if _ckeck_zones(positions, required, optional, banned):
        return True, f'{start_A_zone_id}-{end_A_zone_id}'
    
    return False, None



        


def is_arc(note_path: list, start_A_zone_id: int, end_A_zone_id: int) -> tuple[bool, str]:

    pos_diff = _get_pos_diff(start_A_zone_id, end_A_zone_id)

    if pos_diff != 1:
        # 圆弧必须是相邻的A区
        return False, None
    
    positions = [x['position'] for x in note_path]
    required = []
    optional = []
    banned = []

    # 必须激活起点/终点
    required.append(f'A{start_A_zone_id}')
    required.append(f'A{end_A_zone_id}')

    # 必须激活之间的 D 区
    between_DE_zones_id = _get_between_DE_zones(start_A_zone_id, end_A_zone_id)
    for id in between_DE_zones_id:
        required.append(f'D{id}')

    # 检查
    if _ckeck_zones(positions, required, optional, banned):
        syntax = _get_arc_syntax(start_A_zone_id, end_A_zone_id, end_A_zone_id)
        return True, syntax
    
    return False, None







def is_center_reflection(note_path: list, start_A_zone_id: int, end_A_zone_id: int) -> tuple[bool, str]:

    pos_diff = _get_pos_diff(start_A_zone_id, end_A_zone_id)

    if pos_diff == 0:
        # 不可能起点和终点相同
        return False, None
    if pos_diff == 4:
        # 不可能是相对的A区
        return False, None
    
    positions = [x['position'] for x in note_path]
    required = []
    optional = []
    banned = []

    # 必须激活起点/终点
    required.append(f'A{start_A_zone_id}')
    required.append(f'A{end_A_zone_id}')

    # 必须激活 C 区
    required.append(f'C1')
    
    # 必须激活 B 区
    required.append(f'B{start_A_zone_id}')
    required.append(f'B{end_A_zone_id}')

    # 检查
    if _ckeck_zones(positions, required, optional, banned):
        syntax = _get_arc_syntax(start_A_zone_id, end_A_zone_id, end_A_zone_id)
        return True, syntax
    
    return False, None
    






def _ckeck_zones(note_positions: list[str],
                 reqiured: list[str] = [],
                 optional: list[str] = [],
                 banned: list[str] = []) -> bool:
    # banned
    for pos in note_positions:
        if pos in banned or (pos not in reqiured and pos not in optional):
            return False
    # required
    for pos in reqiured:
        if pos not in note_positions:
            return False
    return True



def _get_pos_diff(start_A_zone_id: int, end_A_zone_id: int) -> int:
    
    if start_A_zone_id == 1 and end_A_zone_id == 8:
        return 1
    if start_A_zone_id == 8 and end_A_zone_id == 1:
        return 1
    
    diff1 = abs(end_A_zone_id - start_A_zone_id)
    diff2 = 8 - diff1
    return min(diff1, diff2)



def _is_clockwise(start_A_zone_id: int, end_A_zone_id: int) -> bool:
    # 计算顺时针距离
    if start_A_zone_id < end_A_zone_id:
        clockwise_distance = end_A_zone_id - start_A_zone_id
    else:
        clockwise_distance = (8 - start_A_zone_id) + end_A_zone_id
    # 计算逆时针距离
    if start_A_zone_id > end_A_zone_id:
        counterclockwise_distance = start_A_zone_id - end_A_zone_id
    else:
        counterclockwise_distance = start_A_zone_id + (8 - end_A_zone_id)
    # 如果顺时针距离更短，返回True
    # 特例, 如果两个A区相对 (差4), 无法判断, 默认逆时针
    return clockwise_distance < counterclockwise_distance



def _get_between_AB_zones(start_A_zone_id: int, end_A_zone_id: int) -> list[int]:

    # 如果两个A区相同/相邻/相对，无法判断
    pos_diff = _get_pos_diff(start_A_zone_id, end_A_zone_id)
    if pos_diff in [0, 1, 4]:
        return []

    between_zones = []
    if _is_clockwise(start_A_zone_id, end_A_zone_id):
        # 顺时针方向
        current = start_A_zone_id
        while True:
            current = current + 1 if current < 8 else 1
            if current == end_A_zone_id:
                break
            between_zones.append(current)
    else:
        # 逆时针方向
        current = start_A_zone_id
        while True:
            current = current - 1 if current > 1 else 8
            if current == end_A_zone_id:
                break
            between_zones.append(current)
    
    return between_zones



def _get_between_DE_zones(start_A_zone_id: int, end_A_zone_id: int) -> list[int]:

    # 如果两个A区相同/相对，无法判断
    pos_diff = _get_pos_diff(start_A_zone_id, end_A_zone_id)
    if pos_diff in [0, 4]:
        return []
    
    between_zones = []
    if _is_clockwise(start_A_zone_id, end_A_zone_id):
        # 顺时针方向
        current = start_A_zone_id
        while True:
            # 移动到下一个A区
            next_a = current + 1 if current < 8 else 1
            # 顺时针方向时，D区编号等于next_a（因为next_a是较大的编号）
            d_zone = next_a
            between_zones.append(d_zone)
            
            if next_a == end_A_zone_id:
                break
            current = next_a
    else:
        # 逆时针方向
        current = start_A_zone_id
        while True:
            # 移动到下一个A区
            next_a = current - 1 if current > 1 else 8
            # 逆时针方向时，D区编号等于current（因为current是较大的编号）
            d_zone = current
            between_zones.append(d_zone)
            
            if next_a == end_A_zone_id:
                break
            current = next_a
    
    return between_zones







    


# def aaa():
    # # 检测这个A区路径里边是否包含一些圆弧，要单独拆分出来
    # arc_segments = []
    # i = 0
    # while i < len(A_zones):
    #     current_id = int(A_zones[i][1])  # 'A7' -> 7
    #     # 尝试检测从当前位置开始的圆弧
    #     if i + 1 < len(A_zones):
    #         next_id = int(A_zones[i + 1][1])
    #         is_consec, direction = is_consecutive(current_id, next_id)

    #         if is_consec:
    #             # 找到圆弧的起点，继续向后查找相同方向的连续点
    #             arc_start = current_id
    #             arc_next = next_id
    #             arc_end = next_id
    #             j = i + 2
    #             reverse_turn = False
    #             while j < len(A_zones):
    #                 check_id = int(A_zones[j][1])
    #                 prev_id = int(A_zones[j - 1][1])
    #                 is_consec_next, dir_next = is_consecutive(prev_id, check_id)
    #                 # 如果方向一致且连续，继续扩展圆弧
    #                 if is_consec_next and dir_next == direction:
    #                     arc_end = check_id
    #                     j += 1
    #                 else:
    #                     # 连续但方向变化，说明遇到折返，下一段应从拐点重新开始
    #                     if is_consec_next and dir_next != direction:
    #                         reverse_turn = True
    #                     break
    #             # 记录这个圆弧
    #             arc_segments.append(('arc', (arc_start, arc_next, arc_end)))

    #             if reverse_turn:
    #                 i = j - 1 # 折返时保留拐点作为下一段起点；否则正常跳过
    #             else:
    #                 i = j # 跳过已处理的圆弧部分
    #             continue

    #     # 不是圆弧的一部分，作为单独的点
    #     arc_segments.append(('single', current_id))
    #     i += 1


    # # 将圆弧和单独的点组合成最终语法
    # movement_syntax = ''
    # last_end_id = None
    # for seg_type, seg_data in arc_segments:

    #     if seg_type == 'arc':
    #         start_id, next_id, end_id = seg_data
    #         arc_syntax = _get_arc_syntax(start_id, next_id, end_id)
    #         new_syntax = f"{start_id}{arc_syntax}"
    #     else:  # single
    #         new_syntax = str(seg_data)
    #         end_id = seg_data

    #     # 特例：首个语法直接添加，不需要连接符
    #     if not movement_syntax:
    #         movement_syntax = new_syntax
    #         last_end_id = end_id
    #         continue

    #     # 特例：弧形折返，前一段终点与后一段起点相同，直接拼接
    #     # 例如 6<3 + >6 -> 6<3>6
    #     if seg_type == 'arc' and last_end_id == start_id:
    #         movement_syntax += arc_syntax
    #         last_end_id = end_id
    #         continue
        
    #     # 普通场景
    #     movement_syntax += f"-{new_syntax}"
    #     last_end_id = end_id

    # movement_syntax = movement_syntax[1:] # 去掉最开头的起始位置

    # # print(f'{" ".join(azone for azone in A_zones)} -> {movement_syntax}')

    # return movement_syntax






def _divide_path_by_A_zone(note_path) -> list:
    """
    将一整条分割成多个小段，分割点是经过了A区 (判定点)
    返回：list[tuple[note_path, start_A_zone_label, end_A_zone_label]]
    """

    def _get_nearest_a_zone_endpoint(cx, cy) -> str:
        # 获取给定位置最近的A区判定点
        min_dist = float('inf')
        nearest_endpoint = None
        for label, (ex, ey) in shared_context.a_zone_endpoint.items():
            dist = np.sqrt((cx - ex)**2 + (cy - ey)**2)
            if dist < min_dist:
                min_dist = dist
                nearest_endpoint = label
        return nearest_endpoint
    

    def _is_pass_a_zone_endpoint(cx, cy) -> tuple[bool, str]:
        # 严格判断是否经过了A区判定点
        max_dist = shared_context.note_travel_dist * 0.15
        for label, (ex, ey) in shared_context.a_zone_endpoint.items():
            dist = np.sqrt((cx - ex)**2 + (cy - ey)**2)
            if dist < max_dist:
                return True, label
        return False, ""
   

    positions = [x['position'] for x in note_path]
    # 在预处理时，不保证起点就在A区
    # 所以要找到离起点最近的A区判定点
    start_pos = positions[0]
    if not start_pos.startswith('A'):
        start_pos = (_get_nearest_a_zone_endpoint(note_path[0]['cx'],
                                                  note_path[0]['cy']))
    # 在预处理中，不保证终点也在A区
    # 所以要找到离终点最近的A区判定点
    end_pos = positions[-1]
    if not end_pos.startswith('A'):
        end_pos = (_get_nearest_a_zone_endpoint(note_path[-1]['cx'],
                                                note_path[-1]['cy']))
        
    note_path_segments = []
    current_segment = []
    current_segment_start_A_zone = None
    current_segment_end_A_zone = None
    for i, point in enumerate(note_path):

        # 特例：第一个点
        if i == 0:
            current_segment.append(point)
            current_segment_start_A_zone = start_pos
            continue

        # 特例：最后一个点
        if i == len(note_path) - 1:
            current_segment.append(point)
            current_segment_end_A_zone = end_pos
            if current_segment_start_A_zone != current_segment_end_A_zone:
                note_path_segments.append((current_segment,
                                           current_segment_start_A_zone,
                                           current_segment_end_A_zone))
            break

        # 普通：其他的轨迹点
        cx, cy = point['cx'], point['cy']
        is_pass, a_zone = _is_pass_a_zone_endpoint(cx, cy)
        # 没经过A区，添加点到当前段
        if not is_pass:
            current_segment.append(point)
            continue
        # 经过A区，但是还在当前段的起点，添加到当前段
        if current_segment_start_A_zone == a_zone:
            current_segment.append(point)
            continue
        # 经过A区，且不是当前段的起点，说明进入了下一个A区
        
        # 保存当前段
        current_segment_end_A_zone = a_zone
        note_path_segments.append((current_segment,
                                   current_segment_start_A_zone,
                                   current_segment_end_A_zone))
        # 开启新段
        current_segment = [point]
        current_segment_start_A_zone = a_zone
        current_segment_end_A_zone = None


    return note_path_segments






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







def _is_consecutive(id1, id2):
    # 检查两个A区ID是否连续（考虑环形结构）
    # 顺时针：1->2, 2->3, ..., 7->8, 8->1
    if (id2 - id1) == 1 or (id1 == 8 and id2 == 1):
        return True, 'clockwise'
    # 逆时针：1->8, 8->7, ..., 2->1
    if (id1 - id2) == 1 or (id1 == 1 and id2 == 8):
        return True, 'counterclockwise'
    return False, None






# def guess_target_a_zone_by_inertia(note_path):
#     '''
#     根据运动惯性，预测最终可能进入的A区。
#     '''
#     if len(note_path) < 2:
#         return None
    
#     # 寻找倒序最后一点 (点A)
#     last_note = note_path[-1]
#     A_cx = last_note['cx']
#     A_cy = last_note['cy']
    
#     # 倒序遍历寻找距离大于阈值的点 (点B)
#     B_cx, B_cy = None, None
#     min_dist = shared_context.std_video_size * 0.02 # 1080p下约为20像素
    
#     for note in reversed(note_path[:-1]):
#         cx = note['cx']
#         cy = note['cy']
#         dist = np.sqrt((cx - A_cx)**2 + (cy - A_cy)**2)
#         if dist > min_dist:
#             B_cx, B_cy = cx, cy
#             break
            
#     if B_cx is None or B_cy is None:
#         return None
        
#     # 运动向量 BA (从B指向A)
#     BA_x = A_cx - B_cx
#     BA_y = A_cy - B_cy
#     BA_length = np.sqrt(BA_x**2 + BA_y**2)
#     if BA_length == 0: return None # 理论上不会发生AB重合
        
#     # 过滤并找出距离射线最近的点
#     best_zone = None
#     min_distance_to_line = 999999
    
#     for zone_id in range(1, 9):
#         zone_key = f'A{zone_id}'
#         P_cx, P_cy = shared_context.a_zone_endpoint[zone_key]
        
#         # 目标向量 AP (从A指向P)
#         AP_x = P_cx - A_cx
#         AP_y = P_cy - A_cy
        
#         # 1. 筛选排查：利用点乘 (Dot Product) 判断是否在相反方向
#         dot_product = BA_x * AP_x + BA_y * AP_y
#         if dot_product < 0:
#             continue  # 夹角 > 90度，说明目标点在跑过来的“背后”，排除
            
#         # 2. 计算点到射线的距离：利用叉乘的绝对值 (Cross Product Area) / 底边长
#         cross_product = abs(BA_x * AP_y - BA_y * AP_x)
#         distance_to_line = cross_product / BA_length
        
#         if distance_to_line < min_distance_to_line:
#             min_distance_to_line = distance_to_line
#             best_zone = zone_key
            
#     return best_zone
