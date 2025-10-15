import os
import cv2
import numpy as np


class Note:
    def __init__(self, frameTime=None, type=None, index=None, posX=None, posY=None, 
                 local_posX=None, local_posY=None, status=None, 
                 appearMsec=None, isEX=None, touchDecor=None, tapScale=None, holdScale=None, 
                 holdSize=None, starScale=None, userNoteSize=None):
        
        self.frameTime = frameTime
        self.type = type
        self.index = index
        self.posX = posX
        self.posY = posY
        self.local_posX = local_posX
        self.local_posY = local_posY
        self.status = status
        self.appearMsec = appearMsec
        self.isEX = isEX
        self.touchDecor = touchDecor
        self.tapScale = tapScale
        self.holdScale = holdScale
        self.holdSize = holdSize
        self.starScale = starScale
        self.userNoteSize = userNoteSize
    
    





def parse_txt(txt_path):
    """
    解析txt文件，返回一个按时间组织的notes字典
    键为时间戳(毫秒)，值为该时间点的notes列表
    """
    if not os.path.exists(txt_path):
        return {}
    
    time_notes = {}  # 存储按时间组织的notes字典
    
    with open(txt_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    
    current_time = None
    
    for line in lines:
        line = line.strip()
        
        # 跳过空行和头部信息
        if not line or line.startswith('Note Dump') or line.startswith('Music Info') or line.startswith('Format') or line.startswith('='):
            continue
        
        # 检查是否是Time行
        if line.startswith('Time:'):
            # 解析时间信息
            time_parts = line.split('|')
            time_str = time_parts[0].replace('Time:', '')
            current_time = float(time_str)
            
            # 初始化这个时间点的notes列表
            if current_time not in time_notes:
                time_notes[current_time] = []
            continue
        
        # 解析note行
        if current_time is not None:
            note = parse_note_line(line, current_time)
            if note:
                time_notes[current_time].append(note)
    
    return time_notes


def find_closest_notes(time_notes, sorted_times, target_time):
    """
    根据目标时间查找最接近的notes数据
    
    参数:
        time_notes: 按时间组织的notes字典 {时间戳: [notes列表]}
        sorted_times: 已排序的时间戳列表
        target_time: 目标时间(毫秒)
        
    返回:
        最接近目标时间的notes列表
    """
    if not time_notes:
        return []

    # 如果目标时间小于等于第一个时间戳，返回第一个时间戳的notes
    if target_time <= sorted_times[0]:
        return time_notes[sorted_times[0]]
    
    # 如果目标时间大于等于最后一个时间戳，返回最后一个时间戳的notes
    if target_time >= sorted_times[-1]:
        return time_notes[sorted_times[-1]]
    
    # 找到目标时间前后最近的时间戳
    left_time = None
    right_time = None
    
    for i in range(len(sorted_times) - 1):
        if sorted_times[i] <= target_time <= sorted_times[i + 1]:
            left_time = sorted_times[i]
            right_time = sorted_times[i + 1]
            break
    
    if left_time is None or right_time is None:
        return []
    
    # 计算目标时间与左右时间戳的距离
    left_diff = target_time - left_time
    right_diff = right_time - target_time
    
    # 返回距离更近的时间戳的notes
    if left_diff <= right_diff:
        return time_notes[left_time]
    else:
        return time_notes[right_time]


def frame_to_time(frame_number, fps):
    """
    将帧号转换为时间(毫秒)
    
    参数:
        frame_number: 帧号
        fps: 视频帧率
        
    返回:
        对应的时间(毫秒)
    """
    return (frame_number / fps) * 1000


def parse_note_line(line, frame_time):
    """
    解析单个note行，返回Note对象
    """
    try:
        # 分割主要部分
        parts = line.split(' | ')
        if len(parts) < 6:
            return None
        
        # 解析type和index
        type_index = parts[0].strip()
        type_name, index = type_index.split('-')
        index = int(index)
        
        # 解析位置信息
        pos_parts = parts[1].split(', ')
        posX = float(pos_parts[0])
        posY = float(pos_parts[1])
        
        local_pos_parts = parts[2].split(', ')
        local_posX = float(local_pos_parts[0])
        local_posY = float(local_pos_parts[1])
        
        # 解析状态
        status = parts[3].strip()
        
        # 解析出现时间
        appear_msec = float(parts[4].strip())

        # 解析是否为EX
        isEX_str = parts[5].strip().lower()
        isEX = True if isEX_str == 'ex:y' else False
        
        # 创建Note对象
        note = Note(
            frameTime=frame_time,
            type=type_name,
            index=index,
            posX=posX,
            posY=posY,
            local_posX=local_posX,
            local_posY=local_posY,
            status=status,
            appearMsec=appear_msec,
            isEX=isEX
        )
        
        # 处理额外数据
        extra_data = parts[6].strip().lower() if len(parts) >= 7 else ""
        extra_data2 = parts[7].strip().lower() if len(parts) >= 8 else ""

        #print(f"Parsing note: {type_name}-{index} at {frame_time}ms with extra data: '{extra_data}' and '{extra_data2}'")
        
        # 处理Touch/Touch-Hold类型的TouchDecor数据
        if 'touch' in type_name.lower():
            if 'touchdecorposition' in extra_data:
                touch_decor = float(extra_data.split('touchdecorposition:')[1].strip())
                note.touchDecor = touch_decor
        
        # 处理Hold类型的HoldScale和HoldSize数据
        elif 'hold' in type_name.lower():
            if 'holdscale' in extra_data and 'holdbodysize' in extra_data2:
                hold_scale_str = extra_data.split('holdscale:')[1].strip()
                hold_scale1 = float(hold_scale_str.split(',')[0].strip())
                hold_scale2 = float(hold_scale_str.split(',')[1].strip())
                note.holdScale = (hold_scale1, hold_scale2)
                hold_size = float(extra_data2.split('holdbodysize:')[1].strip())
                note.holdSize = hold_size

        # 处理Star类型的StarScale和UserNoteSize数据
        elif 'star' in type_name.lower():
            if 'starcale' in extra_data and 'usernotesize' in extra_data2:
                star_scale_str = extra_data.split('starcale:')[1].strip()
                star_scale1 = float(star_scale_str.split(',')[0].strip())
                star_scale2 = float(star_scale_str.split(',')[1].strip())
                note.starScale = (star_scale1, star_scale2)
                user_note_size = float(extra_data2.split('usernotesize:')[1].strip())
                note.userNoteSize = user_note_size

        # 处理Tap类型的TapScale数据
        elif 'tap' in type_name.lower() or 'break' in type_name.lower():
            if 'tapscale' in extra_data:
                tap_scale_str = extra_data.split('tapscale:')[1].strip()
                tap_scale1 = float(tap_scale_str.split(',')[0].strip())
                tap_scale2 = float(tap_scale_str.split(',')[1].strip())
                note.tapScale = (tap_scale1, tap_scale2)
        
        return note

    except Exception as e:
        print(f"Error in parse_note_line(): {e}")
        return None




def manual_align(video_path, txt_path, time_notes):
    """
    手动对齐视频帧和时间戳音符数据
    
    操作说明：
    - 空格：播放/暂停
    - 模式1（对齐模式）：音符保持不变
    - 按'c'键切换到模式2
    - 模式2（验证模式）：视频和音符同步（时间差固定）
    - 左/右箭头：暂停并前进/后退一帧
    - 按'q'退出
    
    返回：时间偏移量(毫秒)
    """
    
    video_frame_counter = 0  # 视频当前帧计数
    last_video_frame_counter = -1  # 上一次的视频帧计数器
    time_offset = 0.0  # notes与video的时间差(ms)
    mode = 1  # 1=对齐模式, 2=验证模式
    is_playing = False  # 播放状态

    cap = cv2.VideoCapture(video_path)
    total_video_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    if not time_notes:
        print("没有找到音符数据！")
        cap.release()
        return 0

    # 预先读取所有帧的时间戳（支持VFR视频）
    print("正在读取视频帧时间戳...")
    frame_timestamps = []
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    i = 0
    while i < total_video_frames and cap.grab():
        # 获取当前（已抓取）帧的时间戳（毫秒）
        timestamp = cap.get(cv2.CAP_PROP_POS_MSEC)
        frame_timestamps.append(timestamp)
        i += 1
        if (i) % 10 == 0 or i == total_video_frames:
            print(f"\r进度: {i}/{total_video_frames} 帧", end="", flush=True)
    print("\r时间戳读取完成！            ")

    # 重置视频到第一帧
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    # 获取所有时间戳并排序
    sorted_times = sorted(time_notes.keys())    
    window_name = 'Label Notes Alignment Tool'
    cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)

    while True:
        # 设置视频到指定帧
        if video_frame_counter - last_video_frame_counter != 1: # 不是下一帧
            cap.set(cv2.CAP_PROP_POS_FRAMES, video_frame_counter)

        last_video_frame_counter = video_frame_counter
        ret, raw_frame = cap.read()
        
        if not ret:
            video_frame_counter = min(video_frame_counter, total_video_frames - 1)
            is_playing = False
            continue
        
        # 从预先缓存的时间戳列表中获取当前帧的真实时间戳
        current_video_timestamp = frame_timestamps[video_frame_counter]
        
        # 计算notes虚拟时间 = 视频真实时间戳 + 时间差
        notes_virtual_time = current_video_timestamp + time_offset
        
        # 根据notes虚拟时间查找最接近的音符
        current_notes = find_closest_notes(time_notes, sorted_times, notes_virtual_time)
        
        # 绘制音符
        result_frame = draw_all_notes(raw_frame, current_notes, notes_virtual_time)
        
        # 显示信息
        play_status = "[PLAYING]" if is_playing else "[PAUSED]"
        mode_text = f"{play_status} Mode 1: Alignment" if mode == 1 else f"{play_status} Mode 2: Sync"
        mode_color = (0, 255, 255) if mode == 1 else (0, 255, 0)
        
        cv2.putText(result_frame, mode_text,
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, mode_color, 2)
        cv2.putText(result_frame, f"Video: {video_frame_counter}/{total_video_frames} frame ({current_video_timestamp:.2f}ms)",
                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(result_frame, f"Notes: {notes_virtual_time:.2f}ms",
                    (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(result_frame, f"Diff: {time_offset:.2f}ms",
                    (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
        cv2.putText(result_frame, "Q:Quit | C:Mode",
                    (10, result_frame.shape[0] - 80), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        cv2.putText(result_frame, "Space: Play/Pause",
                    (10, result_frame.shape[0] - 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        cv2.putText(result_frame, "Arrow: Last frame",
                    (10, result_frame.shape[0] - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        
        cv2.imshow(window_name, result_frame)

        # 等待按键
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('q') or key == ord('Q'):  # 退出
            print(f"对齐完成！")
            print(f"Time Offset: {time_offset:.2f}ms")
            break
            
        elif key == ord('c') or key == ord('C'):  # 切换模式
            is_playing = False
            mode = 2 if mode == 1 else 1
        
        elif key == 32:  # 空格：播放/暂停
            is_playing = not is_playing
                
        elif key == 0:  # 四个箭头键 (四个键都是0，不知道怎么区分)
            is_playing = False  # 箭头操作时暂停
            if mode == 1:
                # 模式1：视频后退一帧，同时调整时间差以保持notes虚拟时间不变
                new_video_frame_counter = max(video_frame_counter - 1, 0)
                if new_video_frame_counter != video_frame_counter:
                    # 从缓存中获取新帧的时间戳
                    new_video_timestamp = frame_timestamps[new_video_frame_counter]
                    # 调整时间差：让notes虚拟时间保持不变
                    # notes_virtual_time = new_video_timestamp + new_time_offset
                    # 由于notes_virtual_time不变，所以：
                    time_offset += (current_video_timestamp - new_video_timestamp)
                    video_frame_counter = new_video_frame_counter
            else:
                # 模式2：视频后退一帧，时间差不变（notes会同步后退）
                video_frame_counter = max(video_frame_counter - 1, 0)
        
        # 如果正在播放，自动前进
        if is_playing:
            if mode == 1:
                # 模式1：视频前进，同时调整时间差以保持notes虚拟时间不变
                new_video_frame_counter = video_frame_counter + 1
                if new_video_frame_counter >= total_video_frames:
                    video_frame_counter = total_video_frames - 1
                    is_playing = False
                else:
                    # 获取下一帧的时间戳
                    next_video_timestamp = frame_timestamps[new_video_frame_counter]
                    # 调整时间差：让notes虚拟时间保持不变
                    # notes_virtual_time = next_video_timestamp + new_time_offset
                    # 由于notes_virtual_time不变，所以：
                    time_offset += (current_video_timestamp - next_video_timestamp)
                    video_frame_counter = new_video_frame_counter
            else:
                # 模式2：视频前进，时间差不变（notes会同步前进）
                video_frame_counter += 1
                if video_frame_counter >= total_video_frames:
                    video_frame_counter = total_video_frames - 1
                    is_playing = False
    
    cap.release()
    cv2.destroyWindow(window_name)

    return time_offset



def draw_tap_note(note, target_time):
    """
    绘制单个Tap音符
    
    输入：
        note: Note对象
        
    返回：
        list: 4个点的坐标 [(x1,y1), (x2,y2), (x3,y3), (x4,y4)]
              这4个点构成一个可能带旋转角度的矩形
    """

    if note.status.lower() != "move": return None, None

    center_x = 1080 + note.posX
    center_y = 120 - note.posY
    ox = 540
    oy = 540

    if note.isEX:
        size = 1080 * 0.055
    else:
        size = 1080 * 0.049

    # 假设速度 7.50
    # OptionNotespeed = 850
    # DefaultMsec = 1000 / (850 / 60) * 4 = 282.35294
    # 说明音符走完全程要 282ms
    # 在标准 1080p 下，起点 120 终点 480 全程 360 像素
    # 所以此时移动速度为 360 / 282 像素/毫秒
    speed = 360 / (1000 / 850 * 60 * 4)
    time_diff = target_time - note.frameTime
    new_distance_to_o = note.local_posY + speed * time_diff
    # local_posY就是到屏幕中心的距离

    # 以 O (屏幕中心) 为中心，沿直线获得距离为 new_distance_to_o 的两个点
    a = (center_y - oy) / (center_x - ox)
    dx = new_distance_to_o / (np.sqrt(1 + np.power(a, 2)))
    dy = a * dx
    p1x = ox + dx
    p1y = oy + dy
    p2x = ox - dx
    p2y = oy - dy

    # 更接近 center 的点就是新的中心点
    if abs(p1x - center_x) > abs(p2x - center_x):
        new_center_x = p2x
        new_center_y = p2y
    else:
        new_center_x = p1x
        new_center_y = p1y

    # 返回4个角点（左上、右上、右下、左下）和中心点
    points = [
        (new_center_x - size, new_center_y - size),  # 左上
        (new_center_x + size, new_center_y - size),  # 右上
        (new_center_x + size, new_center_y + size),  # 右下
        (new_center_x - size, new_center_y + size),  # 左下
    ]

    return points, (round(new_center_x), round(new_center_y))


def draw_hold_note(note, target_time):
    """
    绘制单个Hold音符
    
    输入：
        note: Note对象，包含holdSize等属性
        
    返回：
        list: 4个点的坐标 [(x1,y1), (x2,y2), (x3,y3), (x4,y4)]
              这4个点构成一个可能带旋转角度的矩形
    """

    if note.status.lower() != "move": return None, None

    box_width = 140 * 0.5 * 0.78
    box_length = box_width + (note.holdSize - 140) * 0.5 * 1.05
    center_x = 1080 + note.posX
    center_y = 120 - note.posY
    ox = 540
    oy = 540

    # y = ax + b
    a = (center_y - oy) / (center_x - ox)
    
    # 以 center xy 为中心，沿直线获得距离为 box_length 的两个点
    # 这两个点是 hold 的头尾两条边的中点
    dx = box_length / ((1 + a**2)**0.5)
    dy = a * dx
    mid1x = center_x - dx
    mid1y = center_y - dy
    mid2x = center_x + dx
    mid2y = center_y + dy

    # 现在根据头尾两条边的中点，计算出四个角点
    a_perpendicular = -1 / a

    dx1 = box_width / ((1 + a_perpendicular**2)**0.5)
    dy1 = a_perpendicular * dx1
    p1 = (mid1x - dx1, mid1y - dy1)
    p2 = (mid1x + dx1, mid1y + dy1)

    dx2 = box_width / ((1 + a_perpendicular**2)**0.5)
    dy2 = a_perpendicular * dx2
    p3 = (mid2x + dx2, mid2y + dy2)
    p4 = (mid2x - dx2, mid2y - dy2)

    return [
        (round(p1[0]), round(p1[1])),
        (round(p2[0]), round(p2[1])),
        (round(p3[0]), round(p3[1])),
        (round(p4[0]), round(p4[1])),
    ], (center_x, center_y)



def draw_slide_note(note, target_time):
    """
    绘制单个Slide音符
    
    输入：
        note: Note对象
        
    返回：
        list: 4个点的坐标 [(x1,y1), (x2,y2), (x3,y3), (x4,y4)]
              这4个点构成一个可能带旋转角度的矩形
    """
    # TODO: 实现具体逻辑
    # Slide音符可能需要考虑滑动方向和角度
    center_x = 1080 + note.posX
    center_y = 120 - note.posY
    size = 47
    
    points = [
        (center_x - size, center_y - size),
        (center_x + size, center_y - size),
        (center_x + size, center_y + size),
        (center_x - size, center_y + size),
    ]

    return points, (center_x, center_y)


def draw_touch_note(note, target_time):
    """
    绘制单个Touch音符
    
    输入：
        note: Note对象，包含touchDecor等属性
        
    返回：
        list: 4个点的坐标 [(x1,y1), (x2,y2), (x3,y3), (x4,y4)]
              这4个点构成一个可能带旋转角度的矩形
    """
    # TODO: 实现具体逻辑
    # Touch音符可能需要考虑touchDecor位置
    center_x = 1080 + note.posX
    center_y = 120 - note.posY
    size = 1080 * 0.042
    
    touch_decor = note.touchDecor if note.touchDecor else 0.0
    
    points = [
        (center_x - size, center_y - size),
        (center_x + size, center_y - size),
        (center_x + size, center_y + size),
        (center_x - size, center_y + size),
    ]

    return points, (center_x, center_y)


def draw_touch_hold_note(note, target_time):
    """
    绘制单个Touch-Hold音符
    
    输入：
        note: Note对象，可能包含touchDecor和holdSize属性
        
    返回：
        list: 4个点的坐标 [(x1,y1), (x2,y2), (x3,y3), (x4,y4)]
              这4个点构成一个可能带旋转角度的矩形
    """
    # TODO: 实现具体逻辑
    # Touch-Hold音符结合了Touch和Hold的特性
    center_x = 1080 + note.posX
    center_y = 120 - note.posY
    size = 1080 * 0.042
    
    points = [
        (center_x - size, center_y - size),
        (center_x + size, center_y - size),
        (center_x + size, center_y + size),
        (center_x - size, center_y + size),
    ]

    return points, (center_x, center_y)


def draw_rotated_rect(frame, points, color, thickness=2):
    """
    在帧上绘制旋转矩形
    
    输入：
        frame: 图像帧
        points: 4个点的坐标列表 [(x1,y1), (x2,y2), (x3,y3), (x4,y4)]
        color: BGR颜色元组
        thickness: 线条粗细
        
    返回：
        frame: 绘制后的图像帧
    """
    
    # 转换为整数坐标
    pts = np.array(points, dtype=np.int32)
    
    # 绘制矩形（连接4个点）
    cv2.polylines(frame, [pts], isClosed=True, color=color, thickness=thickness)
    
    return frame


def draw_all_notes(frame, notes, target_time):
    """
    绘制所有类型的音符
    使用独立的绘制函数为每种音符类型生成矩形框
    """
    for note in notes:
        note_type = note.type.lower()
        
        # 根据音符类型调用对应的绘制函数
        points = None
        center = None
        color = (255, 255, 255)  # 默认白色
        label = ""
        
        # Tap音符：绿色
        if note_type == 'tapnote':
            points, center = draw_tap_note(note, target_time)
            color = (0, 255, 0)
            label = 'TAP'
        elif note_type == 'breaknote':
            points, center = draw_tap_note(note, target_time)
            color = (0, 255, 0)
            label = 'TAP-B'

        # Hold音符：蓝色
        elif note_type == 'holdnote':
            points, center = draw_hold_note(note, target_time)
            color = (255, 0, 0)
            label = 'HOLD'
        elif note_type == 'breakholdnote':
            points, center = draw_hold_note(note, target_time)
            color = (255, 0, 0)
            label = 'HOLD-B'
        
        # Slide音符：黄色
        elif note_type == 'starnote':
            points, center = draw_slide_note(note, target_time)
            color = (0, 255, 255)
            label = 'SLIDE'
        elif note_type == 'breakstarnote':
            points, center = draw_slide_note(note, target_time)
            color = (0, 255, 255)
            label = 'SLIDE-B'
        
        # Touch-Hold音符：青色
        elif 'touchhold' in note_type:
            points, center = draw_touch_hold_note(note, target_time)
            color = (255, 255, 0)
            label = 'TOUCH-HOLD'
        
        # Touch音符：紫色
        elif 'touch' in note_type:
            points, center = draw_touch_note(note, target_time)
            color = (255, 0, 255)
            label = 'TOUCH'

        if note.isEX:
            if label.endswith('-B'):
                label += 'X'
            else:
                label += '-X'

        label += f' {note.index}'
            
        # 绘制矩形框
        if points:
            frame = draw_rotated_rect(frame, points, color, thickness=2)
            
            # 绘制中心点
            center_x, center_y = center
            center_x = int(round(center_x))
            center_y = int(round(center_y))
            cv2.circle(frame, (center_x, center_y), 2, (0, 0, 255), 3)

            # 显示音符类型标签
            cv2.putText(frame, label, (center_x - 40, center_y + 20), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    return frame


def calculate_oct_position(circle_center_x, circle_center_y, note_x, note_y):
    x_diff = note_x - circle_center_x
    y_diff = note_y - circle_center_y
    if x_diff > 0 and y_diff < 0:
        # 1, 2
        if abs(x_diff) < abs(y_diff):
            return 1
        else:
            return 2
    elif x_diff > 0 and y_diff > 0:
        # 3, 4
        if abs(x_diff) > abs(y_diff):
            return 3
        else:
            return 4
    elif x_diff < 0 and y_diff > 0:
        # 5, 6
        if abs(x_diff) < abs(y_diff):
            return 5
        else:
            return 6
    elif x_diff < 0 and y_diff < 0:
        # 7, 8
        if abs(x_diff) > abs(y_diff):
            return 7
        else:
            return 8
    else:
        return 0


def main(video_path, txt_path, output_dir, mode):
    """
    主函数
    """
    # check file exist
    if not os.path.exists(video_path):
        print(f"Video file not found: {video_path}")
        return

    if not os.path.exists(txt_path):
        print(f"Text file not found: {txt_path}")
        return

    # 解析txt文件
    time_notes = parse_txt(txt_path)
    
    if len(time_notes) == 0:
        print("错误：没有找到任何音符数据！")
        return
    
    # 手动对齐
    time_offset = manual_align(video_path, txt_path, time_notes)
    
    # 保存对齐结果
    if output_dir and os.path.exists(output_dir):
        result_file = os.path.join(output_dir, "alignment_result.txt")
        with open(result_file, 'w', encoding='utf-8') as f:
            f.write(f"Video File: {video_path}\n")
            f.write(f"Notes File: {txt_path}\n")
            f.write(f"Time Offset: {time_offset}ms\n")
        print(f"对齐结果已保存到: {result_file}")
    
    return time_offset


def process_video_with_notes(video_path, txt_path, time_offset, output_path=None):
    """
    处理视频，将notes数据叠加到视频帧上
    
    参数:
        video_path: 输入视频路径
        txt_path: notes数据文件路径
        time_offset: 时间偏移量(毫秒)
        output_path: 输出视频路径(可选)
        
    返回:
        无
    """
    # 解析notes数据
    time_notes = parse_txt(txt_path)
    if not time_notes:
        return
    
    # 打开视频
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return
    
    # 获取视频属性
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    # 设置输出视频
    if output_path:
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    else:
        out = None
    
    # 创建窗口
    window_name = 'Video with Notes'
    cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)
    
    # 处理每一帧
    for frame_num in range(total_frames):
        # 读取帧
        ret, frame = cap.read()
        if not ret:
            break
        
        # 计算当前帧的时间
        current_time = frame_to_time(frame_num, fps)
        
        # 查找最接近的notes
        target_time = current_time + time_offset
        current_notes = find_closest_notes(time_notes, target_time)
        
        # 绘制notes
        result_frame = draw_all_notes(frame, current_notes, target_time)
        
        # 显示帧
        cv2.imshow(window_name, result_frame)
        
        # 写入输出视频
        if out:
            out.write(result_frame)
        
        # 检查按键
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == ord('Q'):
            break
    
    # 释放资源
    cap.release()
    if out:
        out.release()
    cv2.destroyWindow(window_name)


if __name__ == "__main__":

    video_path = r"D:\git\mai-chart-analyze\yolo-train\temp\11753_120_standardized.mp4"
    txt_path= r"C:\Users\ck273\Desktop\训练视频\11753_2025-10-15_18-04-41.txt"
    output_dir = r"C:\Users\ck273\Desktop\训练视频\11753"
    mode = 0

    # 执行对齐
    time_offset = main(video_path, txt_path, output_dir, mode)
    
    # 如果需要对齐后的视频处理，可以取消注释下面的代码
    # output_video = os.path.join(output_dir, "output_with_notes.mp4")
    # process_video_with_notes(video_path, txt_path, time_offset, output_video)
