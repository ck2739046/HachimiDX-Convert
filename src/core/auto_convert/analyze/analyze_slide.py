def analyze_slide_tail(self, slide_tail_data):
    '''
    return {(track_id, class_id, start_position): (movement_syntax, start_time, end_time)}
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
        scaled_x = round((x_on_screen_cx - 540) * self.video_size / 1080 + self.screen_cx)
        scaled_y = round((y_on_screen_cy - 540) * self.video_size / 1080 + self.screen_cy)
        new_dict[area_label] = (scaled_x, scaled_y)

    A_zone_endpoint_on_judgeline = new_dict


    # 分析运动模式
    # 暂时只检测边缘旋转 x>x / x<x
    # 其他的一律视为直线 x-x
    slide_tail_info = {}
    for (track_id, class_id, start_position), note_path in slide_tail_data.items():

        # 计算运动语法
        # 期望的返回: >5 / <3 / -7
        movement_syntax = self.analyze_slide_tail_movement_syntax(note_path, A_zone_endpoint_on_judgeline)
        if movement_syntax is None:
            continue
        
        # 计算持续时间
        start_time, end_time = self.analyze_slide_tail_start_end_time(note_path, A_zone_endpoint_on_judgeline)
        if start_time is None or end_time is None:
            continue

        slide_tail_info[(track_id, class_id, start_position[1])] = (movement_syntax, start_time, end_time)

    return slide_tail_info



def analyze_slide_tail_movement_syntax(self, note_path, A_zone_endpoint_on_judgeline):
    '''
    分析运动模式
    暂时只检测边缘旋转 x>x / x<x
    其他的一律视为直线 x-x

    如果星星全程仅在A区或D区内移动，视为旋转
    '''

    def get_A_zone_endpoint_on_judgeline(x, y, A_zone_endpoint_on_judgeline):
        tolerance = self.video_size * 0.02
        for label, (px, py) in A_zone_endpoint_on_judgeline.items():
            dist = np.sqrt((x - px)**2 + (y - py)**2)
            if dist < tolerance:
                return label
        return None
    

    def get_outer_rotation_syntax(start_position_id, next_position_id, end_position_id):
        # 判断起始点在左侧还是右侧
        if start_position_id in [1,2,7,8]:
            start_side = 'up'
        else:
            start_side = 'down'
        # 判断旋转方向
        # > 代表从起点开始箭头向右, < 代表从起点开始箭头向左
        if start_side == 'up':
            # 处理1和8的特殊情况
            if start_position_id == 1:
                if next_position_id in [7, 8]:
                    next_position_id -= 8
            elif start_position_id == 8:
                if next_position_id in [1, 2]:
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

    start_position_id = int(positions[0][1]) # A1 -> 1
    end_position_id = int(positions[-1][1])

    # 如果只在A区或D区移动，视为旋转
    if all(pos.startswith('A') or pos.startswith('D') for pos in positions):

        # 找到第一个与起始点不同的位置
        next_position_id = None
        for pos in positions[1:]:
            if pos[1] != str(start_position_id):
                next_position_id = int(pos[1])
                break
        if next_position_id is None:
            return None

        movement_syntax = get_outer_rotation_syntax(start_position_id, next_position_id, end_position_id)

    else:
        # 获得音符经过的所有A区判定点
        A_zones = []
        last_A_zone = ''
        for note in note_path:
            x1 = note['x1']
            y1 = note['y1']
            x2 = note['x2']
            y2 = note['y2']
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2
            pos = get_A_zone_endpoint_on_judgeline(cx, cy, A_zone_endpoint_on_judgeline)
            if pos is None: continue
            if not pos.startswith('A'): continue
            if pos == last_A_zone: continue
            last_A_zone = pos
            A_zones.append(pos)
        # 考虑到有些星星最后可能提前结束，没有进入A区
        # 使用最后一个位置作为保底结尾
        end_position = f'A{end_position_id}'
        if end_position != last_A_zone:
            A_zones.append(end_position)
        if len(A_zones) < 2:
            return None



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
                arc_syntax = get_outer_rotation_syntax(start_id, next_id, end_id)
                syntax_parts.append(f"{start_id}{arc_syntax}")
            else:  # single
                syntax_parts.append(str(seg_data))
        
        movement_syntax = '-'.join(syntax_parts)
        movement_syntax = movement_syntax[1:] # 去掉最开头的起始位置

        # print(f'{" ".join(azone for azone in A_zones)} -> {movement_syntax}')

    return movement_syntax



def analyze_slide_tail_start_end_time(self, note_path, A_zone_endpoint_on_judgeline):
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
    frame_speeds = []
    for i in range(len(note_path)):
        point = note_path[i]
        frame_num = point['frame']
        x1 = point['x1']
        y1 = point['y1']
        x2 = point['x2']
        y2 = point['y2']
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2

        if last_cx is not None and last_cy is not None and last_frame is not None:
            dist = np.sqrt((cx - last_cx)**2 + (cy - last_cy)**2)
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

    # 定义起点和终点位置
    point = A_zone_endpoint_on_judgeline.get(positions[0], None)
    if point is None:
        return None, None
    start_cx, start_cy = point
    # 允许终点在A区或D区
    temp_position_str = f'A{positions[-1][1]}'
    point = A_zone_endpoint_on_judgeline.get(temp_position_str, None)
    if point is None:
        return None, None
    end_cx, end_cy = point

    # 定义A区中心半径
    self.note_travel_dist = 0
    a_zone_radius = (self.note_travel_dist) / 7

    # 找到第一个离开起始A区的点
    start_move_frame = None
    dist_to_start = 0
    for i in range(round(len(note_path)*0.5)): # 只搜索前半，从前往后
        point = note_path[i]
        frame_num = point['frame']
        x1 = point['x1']
        y1 = point['y1']
        x2 = point['x2']
        y2 = point['y2']
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        dist_to_start = np.sqrt((cx - start_cx)**2 + (cy - start_cy)**2)
        if dist_to_start > a_zone_radius:
            start_move_frame = frame_num
            break
    
    # 计算开始时间
    if start_move_frame is None:
        return None, None
    time_to_start_Msec = (dist_to_start / note_speed) * (1000 / self.fps)
    note_start_time_Msec = start_move_frame / self.fps * 1000 - time_to_start_Msec

    # 找到最后一个进入终点A区的点
    end_move_frame = None
    dist_to_end = 0
    for i in range(len(note_path)-1, round(len(note_path)*0.5), -1): # 只搜索后半，从后往前
        point = note_path[i]
        frame_num = point['frame']
        x1 = point['x1']
        y1 = point['y1']
        x2 = point['x2']
        y2 = point['y2']
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        dist_to_end = np.sqrt((cx - end_cx)**2 + (cy - end_cy)**2)
        if dist_to_end > a_zone_radius:
            end_move_frame = frame_num
            break

    # 计算结束时间
    if end_move_frame is None:
        return None, None
    time_to_end_Msec = (dist_to_end / note_speed) * (1000 / self.fps)
    note_end_time_Msec = end_move_frame / self.fps * 1000 + time_to_end_Msec

    return note_start_time_Msec, note_end_time_Msec



def merge_slide_info(self, slide_head_info, slide_tail_info, bpm, delay_index=0.25):
    '''
    合并slide头尾信息
    输入: for (head_track_id, head_class_id, head_position), head_end_time in slide_head_info.items():
            for (tail_track_id, tail_class_id, tail_start_position): (tail_movement_syntax, tail_start_time, tail_end_time) in slide_tail_info.items():

    将这两组进行匹配：
    delay = tail_start_time - head_end_time
    规则1：head_position = tail_start_position (str)
    规则2：min_delay < delay < max_delay
    规则3：一个tail最多只能匹配到一个head，但是一个head可以匹配多个tail
    规则4：如果tail与多个head都符合匹配条件，选择delay与std_delay最接近的head

    返回格式:
    dict{
        # 匹配的head_tail组合
        key: (head_track_id, head_class_id, full_movement_syntax),
        value: (head_end_time, tail_start_time, tail_end_time)
        # 未匹配的head
        key: (head_track_id, head_class_id, head_position),
        value: head_end_time
    }
    '''

    def get_suffix(class_id, isSingleHead=False):
        dict = {
            20: '',    # slide
            21: 'b',   # break-slide
            22: 'x',   # ex-slide
            23: 'bx',  # break-ex-slide
        }
        dict_single = {
            20: '$',    # single-slide
            21: 'b$',   # break-single-slide
            22: 'x$',   # ex-single-slide
            23: 'bx$',  # break-ex-single-slide
        }
        if isSingleHead:
            return dict_single.get(class_id, '')
        else:
            return dict.get(class_id, '')


    final_slide_info = {}

    # 标准延迟是0.25拍
    one_beat_Msec = 60 / bpm * 1000 * 4
    std_delay = one_beat_Msec * delay_index
    max_delay = one_beat_Msec * delay_index * 1.2
    min_delay = one_beat_Msec * delay_index * 0.6

    # print(f"\n=== Matching Parameters ===")
    # print(f"BPM: {bpm}, One Beat: {one_beat_Msec:.2f} ms")
    # print(f"Std Delay: {std_delay:.2f} ms")
    # print(f"Min Delay: {min_delay:.2f} ms")
    # print(f"Max Delay: {max_delaye:.2f} ms")
    # print(f"===========================\n")

    # 先按位置分组head数据
    # 这样后续tail查找head时，只会在对应位置的head中查找，减少计算量
    head_by_position = defaultdict(list)
    for (track_id, head_class_id, head_position), head_end_time in slide_head_info.items():
        head_by_position[str(head_position)].append((track_id, head_class_id, head_position, head_end_time))

    # 记录哪些head_track_id被匹配了，使用set避免重复
    matched_head_track_ids = set()

    # 遍历所有tail，寻找匹配的head
    processed_tails = 0
    for (tail_track_id, tail_class_id, tail_start_position), (tail_movement_syntax, tail_start_time, tail_end_time) in slide_tail_info.items():
        processed_tails += 1

        # 先看看有没有任何与tail位置相同的head
        tail_start_position = str(tail_start_position)
        if tail_start_position not in head_by_position:
            print(f"{tail_track_id} Tail not match: No heads at position {tail_start_position}")
            continue
        # 如果有，遍历这些head，寻找符合delay条件的head
        # 条件1：min_delay < delay < max_delay
        # 条件2：与std_delay最接近
        best_head = None
        best_delay_diff = float('inf')
        for head_track_id, head_class_id, head_position, head_end_time in head_by_position[tail_start_position]:
            # 条件1
            delay = tail_start_time - head_end_time
            if not (min_delay < delay < max_delay):
                continue
            # 条件2
            delay_diff = abs(delay - std_delay)
            if delay_diff < best_delay_diff:
                best_delay_diff = delay_diff
                best_head = (head_track_id, head_class_id, head_position, head_end_time)

        if best_head is None:
            print(f"{tail_track_id} Tail not match: No heads match delay at position {tail_start_position}")
            continue

        # 找到了匹配的head，进行记录
        head_track_id, head_class_id, head_position, head_end_time = best_head
        matched_head_track_ids.add(head_track_id)
        # 由于未知原因，星星时长总是长了1/16拍，进行修正
        tail_end_time -= one_beat_Msec / 16
        # 写入final_slide_info
        full_movement_syntax = f"{tail_start_position}{get_suffix(head_class_id)}{tail_movement_syntax}{get_suffix(tail_class_id)}"
        key = (head_track_id, head_class_id, full_movement_syntax)
        value = (head_end_time, tail_start_time, tail_end_time)
        final_slide_info[key] = value


    # 将未匹配的head也写入final_slide_info
    for (head_track_id, head_class_id, head_position), head_end_time in slide_head_info.items():
        if head_track_id not in matched_head_track_ids:
            full_movement_syntax = f"{head_position}{get_suffix(head_class_id, isSingleHead=True)}"
            key = (head_track_id, head_class_id, full_movement_syntax)
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
