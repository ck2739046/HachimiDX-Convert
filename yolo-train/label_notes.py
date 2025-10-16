import os
import cv2
import numpy as np
import shutil


class Note:
    def __init__(self, frameTime=None, type=None, index=None, posX=None, posY=None, 
                 local_posX=None, local_posY=None, status=None, 
                 appearMsec=None, isEX=None, touchDecor=None, touchAlpha=None,
                 tapScale=None, holdScale=None, holdSize=None, starScale=None, starAlpha=None):
        
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
        self.touchAlpha = touchAlpha
        self.tapScale = tapScale
        self.holdScale = holdScale
        self.holdSize = holdSize
        self.starScale = starScale
        self.starAlpha = starAlpha
    
    

star_skin = 0 # 0 圆头星星，1 尖头星星



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
        if (not line or
            line.startswith('Note Dump') or
            line.startswith('Music Info') or
            line.startswith('Format') or
            line.startswith('=') or
            line.startswith('Touch:') or
            line.startswith('Star(1st):')):
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


def find_closest_notes(time_notes, sorted_times, target_time, max_time_diff):
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

    # 如果时间差距太大也要忽略
    if left_diff > max_time_diff and right_diff > max_time_diff:
        return []
    
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
        if "-Move" in type_index:
            type_name, move, index = type_index.split('-')
            type_name = f"{type_name}-Move"
            index = int(index)
        else:
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
            if 'touchdecorposition' in extra_data and 'alpha' in extra_data2:
                touch_decor = float(extra_data.split('touchdecorposition:')[1].strip())
                note.touchDecor = touch_decor
                touch_alpha = float(extra_data2.split('alpha:')[1].strip())
                note.touchAlpha = touch_alpha

        # 处理Hold类型的HoldScale和HoldSize数据
        elif 'hold' in type_name.lower():
            if 'holdscale' in extra_data and 'holdbodysize' in extra_data2:
                hold_scale_str = extra_data.split('holdscale:')[1].strip()
                hold_scale1 = float(hold_scale_str.split(',')[0].strip())
                hold_scale2 = float(hold_scale_str.split(',')[1].strip())
                note.holdScale = (hold_scale1, hold_scale2)
                hold_size = float(extra_data2.split('holdbodysize:')[1].strip())
                note.holdSize = hold_size

        # 处理Star类型的StarScale数据
        elif 'star' in type_name.lower():
            if 'starscale' in extra_data:
                star_scale_str = extra_data.split('starscale:')[1].strip()
                star_scale1 = float(star_scale_str.split(',')[0].strip())
                star_scale2 = float(star_scale_str.split(',')[1].strip())
                note.starScale = (star_scale1, star_scale2)
            if 'alpha' in extra_data2:
                star_alpha = float(extra_data2.split('alpha:')[1].strip())
                note.starAlpha = star_alpha

        # 处理Tap类型的TapScale数据
        elif 'tap' in type_name.lower() or 'break' in type_name.lower():
            if 'tapscale' in extra_data:
                tap_scale_str = extra_data.split('tapscale:')[1].strip()
                tap_scale1 = float(tap_scale_str.split(',')[0].strip())
                tap_scale2 = float(tap_scale_str.split(',')[1].strip())
                note.tapScale = (tap_scale1, tap_scale2)
        
        return note

    except Exception as e:
        print(f"Error in parse_note_line(): {e}: {line}")
        return None




def manual_align(video_path, txt_path, time_notes, align_diff=0):
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
    is_playing = False  # 播放状态

    if align_diff == 0:
        time_offset = 0.0  # notes与video的时间差(ms)
        mode = 1  # 1=对齐模式, 2=验证模式
    else:
        time_offset = align_diff
        mode = 2

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

    max_time_diff = (1000 / (cap.get(cv2.CAP_PROP_FPS))) - 0.1 # 最大时间差，1帧时间

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
        current_notes = find_closest_notes(time_notes, sorted_times, notes_virtual_time, max_time_diff)
        
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
    """

    if note.status.lower() == "init": return None, None

    center_x = 1080 + note.posX
    center_y = 120 - note.posY
    ox = 540
    oy = 540

    if note.status.lower() == "scale":
        index = note.tapScale[0]
        if index < 0.5: return None, None # 忽略过小的音符
        if note.isEX:
            size = 1080 * 0.055 * index
        else:
            size = 1080 * 0.049 * index
        # 不需要位置补偿，直接使用center计角点
        return [
            (center_x - size, center_y - size),  # 左上
            (center_x + size, center_y - size),  # 右上
            (center_x + size, center_y + size),  # 右下
            (center_x - size, center_y + size),  # 左下
        ], (center_x, center_y)


    # 对于 move 状态的音符，需要根据时间差进行位置补偿
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
    dx = new_distance_to_o / np.sqrt(1 + np.power(a, 2))
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
    """

    if note.status.lower() == "init": return None, None, None

    if note.status.lower() == "scale":
        index = note.holdScale[0]
        if index < 0.5: return None, None, None # 忽略过小的音符
    else:
        index = 1

    ex_extend = 5 # 如果是 ex 音符，外扩 5 像素来包住保护套光晕
    if not note.isEX:
        box_width = 140 * 0.5 * 0.77 * index
        box_length = (note.holdSize-20) * 0.5 * index
    else:
        box_width = (ex_extend + 140 * 0.5 * 0.77) * index
        box_length = (ex_extend + (note.holdSize-20) * 0.5) * index

    center_x = 1080 + note.posX
    center_y = 120 - note.posY
    ox = 540
    oy = 540
    head_x, head_y = None, None


    # 对于 move 状态的音符，需要根据时间差进行位置补偿
    # 但是排除中点位于中间的情况，这时候头尾都占满轨道了不需要移动
    if note.status.lower() == "move" and note.local_posY != 300:
        # 假设速度 7.50
        # 由于是中点，移动速度减半
        speed = 360 / (1000 / 850 * 60 * 4) * 0.5
        time_diff = target_time - note.frameTime
        new_distance_to_o = note.local_posY + speed * time_diff
        # 以 O (屏幕中心) 为中心，沿直线获得距离为 new_distance_to_o 的两个点
        a = (center_y - oy) / (center_x - ox)
        dx = new_distance_to_o / np.sqrt(1 + np.power(a, 2))
        dy = a * dx
        p1x = ox + dx
        p1y = oy + dy
        p2x = ox - dx
        p2y = oy - dy
        # 更接近 center 的点就是新的中心点
        if abs(p1x - center_x) > abs(p2x - center_x):
            center_x = p2x
            center_y = p2y
        else:
            center_x = p1x
            center_y = p1y


    # y = ax + b
    a = (center_y - oy) / (center_x - ox)
    
    # 对于 move 阶段，根据中心点计算出头部追踪点
    # 140 的时候 head 与中点重合了，所以要等 160 以后才显示
    if note.status.lower() == "move" and note.holdSize > 160:
        # 以 center xy 为中心，沿直线获得距离为 box_length - c 的两个点
        c = 60 + ex_extend if note.isEX else 60
        dx = (box_length - c) / np.sqrt(1 + np.power(a, 2))
        dy = a * dx
        p1x = center_x + dx
        p1y = center_y + dy
        p2x = center_x - dx
        p2y = center_y - dy
        # 更远离屏幕中心的点就是头部追踪点
        if abs(p1x - ox) < abs(p2x - ox):
            head_x = p2x
            head_y = p2y
        else:
            head_x = p1x
            head_y = p1y


    # 根据中心点和边长计算出四个角点（带角度的）
    # 以 center xy 为中心，沿直线获得距离为 box_length 的两个点
    # 这两个点是 hold 的头尾两条边的中点
    dx = box_length / np.sqrt(1 + np.power(a, 2))
    dy = a * dx
    mid1x = center_x - dx
    mid1y = center_y - dy
    mid2x = center_x + dx
    mid2y = center_y + dy

    # 现在根据头尾两条边的中点，计算出四个角点
    a_perpendicular = -1 / a

    dx1 = box_width / np.sqrt(1 + np.power(a_perpendicular, 2))
    dy1 = a_perpendicular * dx1
    p1 = (mid1x - dx1, mid1y - dy1)
    p2 = (mid1x + dx1, mid1y + dy1)

    dx2 = box_width / np.sqrt(1 + np.power(a_perpendicular, 2))
    dy2 = a_perpendicular * dx2
    p3 = (mid2x + dx2, mid2y + dy2)
    p4 = (mid2x - dx2, mid2y - dy2)

    return [
        (round(p1[0]), round(p1[1])),
        (round(p2[0]), round(p2[1])),
        (round(p3[0]), round(p3[1])),
        (round(p4[0]), round(p4[1])),
    ], (center_x, center_y), (head_x, head_y)



def draw_slide_note(note, target_time):
    """
    绘制单个Slide音符（星星头）
    """

    # 直接复制 tap 的代码
    if note.status.lower() == "init": return None, None

    center_x = 1080 + note.posX
    center_y = 120 - note.posY
    ox = 540
    oy = 540


    if "move" in note.type.lower():
        if note.starAlpha < 0.75: return None, None # 忽略过于透明的音符

        index = 0.88 if star_skin == 0 else 1   # 0 圆头星星，1 尖头星星
        size = 1080 * 0.055 * note.starScale[0] * index

        # 不需要位置补偿，直接使用center计角点
        return [
            (center_x - size, center_y - size),  # 左上
            (center_x + size, center_y - size),  # 右上
            (center_x + size, center_y + size),  # 右下
            (center_x - size, center_y + size),  # 左下
        ], (center_x, center_y)


    if note.status.lower() == "scale":
        index = note.starScale[0]
        if index < 0.5: return None, None # 忽略过小的音符
        
        if note.isEX:
            size = 1080 * 0.055 * index
        else:
            size = 1080 * 0.05 * index

        # 不需要位置补偿，直接使用center计角点
        return [
            (center_x - size, center_y - size),  # 左上
            (center_x + size, center_y - size),  # 右上
            (center_x + size, center_y + size),  # 右下
            (center_x - size, center_y + size),  # 左下
        ], (center_x, center_y)


    # 对于 move 状态的音符，需要根据时间差进行位置补偿
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
    dx = new_distance_to_o / np.sqrt(1 + np.power(a, 2))
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


def draw_touch_note(note, target_time):
    """
    绘制单个Touch音符
    """

    center_x = 1080 + note.posX
    center_y = 120 - note.posY
    size = note.touchDecor + 54

    if note.touchAlpha < 0.4: return None, None # 忽略过于透明的音符

    # touch 音符的公式有点复杂，就不补偿了
    # 反正最后识别尺寸也是靠查找轮廓，不需要画框很精准
    return [
        (center_x - size, center_y - size),  # 左上
        (center_x + size, center_y - size),  # 右上
        (center_x + size, center_y + size),  # 右下
        (center_x - size, center_y + size),  # 左下
    ], (center_x, center_y)


def draw_touch_hold_note(note, target_time):
    """
    绘制单个Touch-Hold音符
    """

    center_x = 1080 + note.posX
    center_y = 120 - note.posY

    if note.touchAlpha < 0.4: return None, None # 忽略过于透明的音符

    if note.touchDecor > 0.01:
        size = note.touchDecor + 100 # 缩放阶段
    else:
        size = note.touchDecor + 120 # 转圈阶段

    # 反正最后识别尺寸也是靠识别彩虹框，不需要画框很精准
    # 返回菱形四个点
    return [
        (center_x, center_y - size),  # 上
        (center_x - size, center_y),  # 左
        (center_x, center_y + size),  # 下
        (center_x + size, center_y),  # 右
    ], (center_x, center_y)


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

    if not notes: return frame

    for note in notes:
        note_type = note.type.lower()
        
        # 根据音符类型调用对应的绘制函数
        points = None
        center = None
        head = None
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
            points, center, head = draw_hold_note(note, target_time)
            color = (255, 0, 0)
            label = 'HOLD'
        elif note_type == 'breakholdnote':
            points, center, head = draw_hold_note(note, target_time)
            color = (255, 0, 0)
            label = 'HOLD-B'
        
        # Slide音符：黄色
        elif note_type == 'starnote' or note_type == 'starnote-move':
            points, center = draw_slide_note(note, target_time)
            color = (0, 255, 255)
            label = 'SLIDE'
        elif note_type == 'breakstarnote' or note_type == 'breakstarnote-move':
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
            org_x = int(round(points[0][0]))
            org_y = int(round(points[0][1])) - 5
            cv2.putText(frame, label, (org_x, org_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            
            # 如果是Hold音符，绘制头部追踪点
            if head:
                head_x, head_y = head
                if head_x and head_y:
                    head_x = int(round(head_x))
                    head_y = int(round(head_y))
                    cv2.circle(frame, (head_x, head_y), 2, (255, 0, 0), 3)
            
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


def export_dataset(video_path, txt_path, output_dir, time_offset, video_name=None):
    """
    导出YOLO训练数据集
    
    输出文件结构:
        output_dir/
        ├── images/          # 所有图像文件 (detect和obb共用)
        ├── labels_detect/   # detect格式标签 (bbox: class_id x_center y_center width height)
        └── labels_obb/      # obb格式标签 (oriented bbox: class_id x1 y1 x2 y2 x3 y3 x4 y4)
    
    参数:
        video_path: 视频路径
        txt_path: 音符数据txt路径
        output_dir: 输出目录
        time_offset: 时间偏移量(毫秒)
        video_name: 视频名称（用于文件命名），如果为None则从video_path提取
    """
    
    # 解析txt文件
    time_notes = parse_txt(txt_path)
    
    if not time_notes:
        print("错误：没有找到任何音符数据！")
        return
    
    # 获取视频名称
    if video_name is None:
        video_name = os.path.splitext(os.path.basename(video_path))[0]
    
    # 创建输出目录结构：三个并列文件夹
    images_dir = os.path.join(output_dir, 'images')
    detect_labels_dir = os.path.join(output_dir, 'labels_detect')
    obb_labels_dir = os.path.join(output_dir, 'labels_obb')
    
    # 如果已存在则删除再创建
    for d in (images_dir, detect_labels_dir, obb_labels_dir):
        if os.path.exists(d):
            try:
                if os.path.isfile(d):
                    os.remove(d)
                else:
                    shutil.rmtree(d)
            except Exception as e:
                print(f"Warning: failed to remove {d}: {e}")
        os.makedirs(d, exist_ok=True)
    
    # 打开视频
    cap = cv2.VideoCapture(video_path)
    total_video_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # 预先读取所有帧的时间戳（支持VFR视频）
    print("正在读取视频帧时间戳...")
    frame_timestamps = []
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    i = 0
    while i < total_video_frames and cap.grab():
        timestamp = cap.get(cv2.CAP_PROP_POS_MSEC)
        frame_timestamps.append(timestamp)
        i += 1
        if i % 100 == 0 or i == total_video_frames:
            print(f"\r进度: {i}/{total_video_frames} 帧", end="", flush=True)
    print("\r时间戳读取完成！            ")
    
    max_time_diff = (1000 / cap.get(cv2.CAP_PROP_FPS)) - 0.1
    
    # 重置视频到第一帧
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    
    # 获取所有时间戳并排序
    sorted_times = sorted(time_notes.keys())
    
    # 获取帧尺寸
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    detect_count = 0
    obb_count = 0
    
    print(f"\n开始导出数据集...")
    print(f"视频尺寸: {frame_width}x{frame_height}")
    print(f"输出目录:")
    print(f"  Images: {images_dir}")
    print(f"  Detect labels: {detect_labels_dir}")
    print(f"  OBB labels: {obb_labels_dir}")
    
    # 测试写入权限
    test_file = os.path.join(images_dir, "test.txt")
    try:
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
    except Exception as e:
        print(f"错误: 目录写入测试失败: {e}")
        return
    
    # 遍历所有帧
    for frame_number in range(total_video_frames):
        # 读取帧
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = cap.read()
        
        if not ret:
            continue
        
        # 获取当前帧的时间戳
        current_video_timestamp = frame_timestamps[frame_number]
        
        # 计算notes虚拟时间
        notes_virtual_time = current_video_timestamp + time_offset
        
        # 查找最接近的音符
        current_notes = find_closest_notes(time_notes, sorted_times, notes_virtual_time, max_time_diff)
        
        # 处理detect格式的音符
        detect_labels = []
        if current_notes:
            for note in current_notes:
                note_type = note.type.lower()
                class_id = -1
                points = None
                center = None
                
                # Tap音符 (class_id = 0)
                if note_type in ['tapnote', 'breaknote']:
                    points, center = draw_tap_note(note, notes_virtual_time)
                    class_id = 0
                
                # Slide音符 (class_id = 1)
                elif note_type in ['starnote', 'starnote-move', 'breakstarnote', 'breakstarnote-move']:
                    points, center = draw_slide_note(note, notes_virtual_time)
                    class_id = 1
                
                # Touch音符 (class_id = 2，不包括TouchHold)
                elif 'touch' in note_type and 'touchhold' not in note_type:
                    points, center = draw_touch_note(note, notes_virtual_time)
                    class_id = 2
                
                # 如果成功获取了角点数据
                if points is not None and center is not None and class_id >= 0:
                    # 从4个角点计算宽度和高度
                    x_coords = [p[0] for p in points]
                    y_coords = [p[1] for p in points]
                    
                    min_x = min(x_coords)
                    max_x = max(x_coords)
                    min_y = min(y_coords)
                    max_y = max(y_coords)
                    
                    width = max_x - min_x
                    height = max_y - min_y
                    
                    # 归一化
                    x_center_norm = center[0] / frame_width
                    y_center_norm = center[1] / frame_height
                    width_norm = width / frame_width
                    height_norm = height / frame_height
                    
                    # 添加到标签列表
                    detect_labels.append(f"{class_id} {x_center_norm} {y_center_norm} {width_norm} {height_norm}")
        
        # 保存图像和标签（即使标签为空也保存）
        image_filename = f"{video_name}_{frame_number}.jpg"
        label_filename = f"{video_name}_{frame_number}.txt"
        
        # 保存图像（只保存一次，detect和obb共用）
        image_path = os.path.join(images_dir, image_filename)
        success = cv2.imwrite(image_path, frame)
        
        if not success:
            print(f"\n警告: 无法保存图像 {image_path}")
            print(f"帧信息: shape={frame.shape if frame is not None else 'None'}")
        
        # 保存detect标签文件（空标签也保存）
        with open(os.path.join(detect_labels_dir, label_filename), 'w') as f:
            if detect_labels:
                f.write('\n'.join(detect_labels))
                detect_count += 1
        
        # 处理obb格式的音符
        obb_labels = []
        if current_notes:
            for note in current_notes:
                note_type = note.type.lower()
                class_id = -1
                points = None
                
                # Hold音符 (class_id = 0)
                if note_type in ['holdnote', 'breakholdnote']:
                    points, _, _ = draw_hold_note(note, notes_virtual_time)
                    class_id = 0
                
                # TouchHold音符 (class_id = 1)
                elif 'touchhold' in note_type:
                    points, _ = draw_touch_hold_note(note, notes_virtual_time)
                    class_id = 1
                
                # 如果成功获取了角点数据
                if points is not None and class_id >= 0:
                    # 归一化4个角点
                    normalized_points = []
                    for p in points:
                        x_norm = p[0] / frame_width
                        y_norm = p[1] / frame_height
                        normalized_points.extend([x_norm, y_norm])
                    
                    # 添加到标签列表
                    label_str = f"{class_id}"
                    for coord in normalized_points:
                        label_str += f" {coord}"
                    obb_labels.append(label_str)
        
        # 保存obb标签文件（即使标签为空也保存，图像已在上面保存过了）
        label_filename = f"{video_name}_{frame_number}.txt"
        
        # 保存obb标签文件（空标签也保存）
        with open(os.path.join(obb_labels_dir, label_filename), 'w') as f:
            if obb_labels:
                f.write('\n'.join(obb_labels))
                obb_count += 1
        
        # 显示进度
        if (frame_number + 1) % 10 == 0 or frame_number == total_video_frames - 1:
            print(f"\r处理进度: {frame_number + 1}/{total_video_frames} 帧 | Detect: {detect_count} 帧 | OBB: {obb_count} 帧", end="", flush=True)
    
    print(f"\n\n导出完成！")
    print(f"Detect数据集: {detect_count} 帧")
    print(f"OBB数据集: {obb_count} 帧")
    print(f"输出目录: {output_dir}")
    
    cap.release()


def verify_dataset(output_dir):
    """
    验证并可视化导出的数据集
    
    文件结构要求:
        output_dir/
        ├── images/          # 所有图像文件
        ├── labels_detect/   # detect格式标签
        └── labels_obb/      # obb格式标签
    
    参数:
        output_dir: 数据集根目录
    """
    
    # 定义新文件结构的路径
    images_dir = os.path.join(output_dir, 'images')
    detect_labels_dir = os.path.join(output_dir, 'labels_detect')
    obb_labels_dir = os.path.join(output_dir, 'labels_obb')
    
    # 严格检查新文件结构
    if not os.path.exists(images_dir):
        print(f"错误：未找到 images 目录！")
        print(f"期望路径: {images_dir}")
        print("请确保使用新的数据集文件结构。")
        return
    
    if not os.path.exists(detect_labels_dir):
        print(f"警告：未找到 labels_detect 目录！")
        print(f"期望路径: {detect_labels_dir}")
    
    if not os.path.exists(obb_labels_dir):
        print(f"警告：未找到 labels_obb 目录！")
        print(f"期望路径: {obb_labels_dir}")
    
    # 收集所有帧的信息
    all_frames = {}  # {frame_key: {'img': path, 'detect_label': path, 'obb_label': path}}
    
    # 从images文件夹收集所有图像
    for img_file in os.listdir(images_dir):
        if img_file.endswith(('.jpg', '.png', '.jpeg')):
            frame_key = os.path.splitext(img_file)[0]
            label_file = frame_key + '.txt'
            
            all_frames[frame_key] = {
                'img': os.path.join(images_dir, img_file)
            }
            
            # 查找对应的detect标签文件
            detect_label_path = os.path.join(detect_labels_dir, label_file)
            if os.path.exists(detect_label_path):
                all_frames[frame_key]['detect_label'] = detect_label_path
            
            # 查找对应的obb标签文件
            obb_label_path = os.path.join(obb_labels_dir, label_file)
            if os.path.exists(obb_label_path):
                all_frames[frame_key]['obb_label'] = obb_label_path
    
    if not all_frames:
        print("错误：未找到任何图像文件！")
        return
    
    # 按帧号排序
    sorted_frame_keys = sorted(all_frames.keys(), key=lambda x: int(x.split('_')[-1]))
    
    print(f"\n找到 {len(sorted_frame_keys)} 帧数据")
    print(f"按空格键播放/暂停，左右箭头键切换帧，Q键退出\n")
    
    current_frame_idx = 0
    is_playing = False
    window_name = 'Dataset Verification'
    cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)
    
    while True:
        frame_key = sorted_frame_keys[current_frame_idx]
        frame_info = all_frames[frame_key]
        
        # 获取图像路径
        img_path = frame_info.get('img')
        
        if not img_path or not os.path.exists(img_path):
            print(f"警告：无法找到帧 {frame_key} 的图像")
            current_frame_idx = (current_frame_idx + 1) % len(sorted_frame_keys)
            continue
        
        # 读取图像
        frame = cv2.imread(img_path)
        if frame is None:
            print(f"警告：无法读取图像 {img_path}")
            current_frame_idx = (current_frame_idx + 1) % len(sorted_frame_keys)
            continue
        
        frame_height, frame_width = frame.shape[:2]
        
        # 绘制detect标签（绿色框）
        detect_count = 0
        if 'detect_label' in frame_info and os.path.exists(frame_info['detect_label']):
            with open(frame_info['detect_label'], 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        class_id = int(parts[0])
                        x_center_norm = float(parts[1])
                        y_center_norm = float(parts[2])
                        width_norm = float(parts[3])
                        height_norm = float(parts[4])
                        
                        # 反归一化
                        x_center = int(x_center_norm * frame_width)
                        y_center = int(y_center_norm * frame_height)
                        width = int(width_norm * frame_width)
                        height = int(height_norm * frame_height)
                        
                        # 计算左上角和右下角
                        x1 = int(x_center - width / 2)
                        y1 = int(y_center - height / 2)
                        x2 = int(x_center + width / 2)
                        y2 = int(y_center + height / 2)
                        
                        # 绘制绿色矩形框
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        
                        # 标注类别
                        class_names = ['TAP', 'SLIDE', 'TOUCH']
                        label = class_names[class_id] if class_id < len(class_names) else str(class_id)
                        cv2.putText(frame, label, (x1, y1 - 5), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                        detect_count += 1
        
        # 绘制obb标签（红色框）
        obb_count = 0
        if 'obb_label' in frame_info and os.path.exists(frame_info['obb_label']):
            with open(frame_info['obb_label'], 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 9:
                        class_id = int(parts[0])
                        
                        # 读取4个角点并反归一化
                        points = []
                        for i in range(4):
                            x_norm = float(parts[1 + i*2])
                            y_norm = float(parts[2 + i*2])
                            x = int(x_norm * frame_width)
                            y = int(y_norm * frame_height)
                            points.append((x, y))
                        
                        # 绘制红色多边形
                        pts = np.array(points, dtype=np.int32)
                        cv2.polylines(frame, [pts], isClosed=True, color=(0, 0, 255), thickness=2)
                        
                        # 标注类别
                        class_names = ['HOLD', 'TOUCH-HOLD']
                        label = class_names[class_id] if class_id < len(class_names) else str(class_id)
                        cv2.putText(frame, label, (points[0][0], points[0][1] - 5), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                        obb_count += 1
        
        # 显示信息
        play_status = "[PLAYING]" if is_playing else "[PAUSED]"
        cv2.putText(frame, f"{play_status} Frame: {current_frame_idx + 1}/{len(sorted_frame_keys)} ({frame_key})",
                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        cv2.putText(frame, f"Detect: {detect_count} notes | OBB: {obb_count} notes",
                   (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(frame, "Space: Play/Pause | Left/Right: Previous/Next | Q: Quit",
                   (10, frame_height - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        
        cv2.imshow(window_name, frame)
        
        # 等待按键
        key = cv2.waitKey(30 if is_playing else 1) & 0xFF
        
        if key == ord('q') or key == ord('Q'):  # 退出
            break
        elif key == 32:  # 空格：播放/暂停
            is_playing = not is_playing
        elif key == 0:  # 箭头: 上一帧
            is_playing = False
            current_frame_idx = (current_frame_idx - 1) % len(sorted_frame_keys)
        
        # 如果正在播放，自动前进
        if is_playing:
            current_frame_idx = (current_frame_idx + 1) % len(sorted_frame_keys)
    
    cv2.destroyWindow(window_name)
    print("\n验证完成！")


def main(video_path, txt_path, output_dir, align_diff=0, star_skinn=0):
    """
    主函数
    """

    global star_skin
    star_skin = star_skinn

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
    
    # 询问用户选择操作模式
    print("\n请选择操作模式:")
    print("1. 手动对齐")
    print("2. 导出数据集")
    print("3. 验证数据集")
    choice = input("请输入选择 (1, 2 或 3): ").strip()
    
    if choice == '1':
        # 手动对齐模式
        time_offset = manual_align(video_path, txt_path, time_notes, align_diff)
        return time_offset
    
    elif choice == '2':
        # 导出数据集模式
        if align_diff == 0:
            print("\n警告: 当前 align_diff = 0，可能未对齐！")
            confirm = input("是否继续导出? (y/n): ").strip().lower()
            if confirm != 'y':
                print("已取消导出")
                return
        
        print(f"\n使用时间偏移: {align_diff}ms")
        print(f"输出目录: {output_dir}")
        
        # 从视频路径提取视频名称
        video_name = os.path.splitext(os.path.basename(video_path))[0]
        
        # 导出数据集
        export_dataset(video_path, txt_path, output_dir, align_diff, video_name)
    
    elif choice == '3':
        # 验证数据集模式
        print(f"\n验证数据集: {output_dir}")
        verify_dataset(output_dir)
    
    else:
        print("无效的选择！")
        return None



if __name__ == "__main__":

    align_diff = 0
    # star_skin 0 圆头星星，1 尖头星星
    # detect: 0 Tap, 1 Slide, 2 Touch
    # obb: 0 Hold, 1 TouchHold

    # video_path = r"D:\git\mai-chart-analyze\yolo-train\temp\11753_120_standardized.mp4"
    # txt_path= r"C:\Users\ck273\Desktop\train\11753_2025-10-16_14-59-08.txt"
    # output_dir = r"C:\Users\ck273\Desktop\train\11753"
    # align_diff = -291.666667
    # star_skin = 0

    # video_path = r"D:\git\mai-chart-analyze\yolo-train\temp\11394_120_standardized.mp4"
    # txt_path= r"C:\Users\ck273\Desktop\train\11394_2025-10-16_14-03-19.txt"
    # output_dir = r"C:\Users\ck273\Desktop\train\11394"
    # align_diff = -175.0
    # star_skin = 1

    # video_path = r"D:\git\mai-chart-analyze\yolo-train\temp\11311_120_standardized.mp4"
    # txt_path= r"C:\Users\ck273\Desktop\train\11311_2025-10-16_19-00-53.txt"
    # output_dir = r"C:\Users\ck273\Desktop\train\11311"
    # align_diff = -141.666667
    # star_skin = 0

    # video_path = r"D:\git\mai-chart-analyze\yolo-train\temp\11741_120_standardized.mp4"
    # txt_path= r"C:\Users\ck273\Desktop\train\11741_2025-10-16_18-56-29.txt"
    # output_dir = r"C:\Users\ck273\Desktop\train\11741"
    # align_diff = -133.333333
    # star_skin = 1

    # video_path = r"D:\git\mai-chart-analyze\yolo-train\temp\11814_120_standardized.mp4"
    # txt_path= r"C:\Users\ck273\Desktop\train\11814_2025-10-16_19-17-01.txt"
    # output_dir = r"C:\Users\ck273\Desktop\train\11814"
    # align_diff = -216.666667
    # star_skin = 0

    # video_path = r"D:\git\mai-chart-analyze\yolo-train\temp\11818_120_standardized.mp4"
    # txt_path= r"C:\Users\ck273\Desktop\train\11818_2025-10-16_19-08-17.txt"
    # output_dir = r"C:\Users\ck273\Desktop\train\11818"
    # align_diff = 66.666667
    # star_skin = 1

    video_path = r"D:\git\mai-chart-analyze\yolo-train\temp\11820_120_standardized.mp4"
    txt_path= r"C:\Users\ck273\Desktop\train\11820_2025-10-16_19-03-33.txt"
    output_dir = r"C:\Users\ck273\Desktop\train\11820"
    align_diff = -100.0
    star_skin = 1
   

    # 执行对齐
    time_offset = main(video_path, txt_path, output_dir, align_diff, star_skin)
