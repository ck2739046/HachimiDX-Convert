import os
import cv2


class Note:
    def __init__(self, frameTime=None, type=None, index=None, posX=None, posY=None, 
                 local_posX=None, local_posY=None, status=None, 
                 appearMsec=None, touchDecor=None, holdSize=None, 
                 starScale=None, userNoteSize=None):
        self.frameTime = frameTime
        self.type = type
        self.index = index
        self.posX = posX
        self.posY = posY
        self.local_posX = local_posX
        self.local_posY = local_posY
        self.status = status
        self.appearMsec = appearMsec
        self.touchDecor = touchDecor
        self.holdSize = holdSize
        self.starScale = starScale
        self.userNoteSize = userNoteSize
    
    # 赋值方法
    def set_frameTime(self, frameTime):
        self.frameTime = frameTime

    def set_type(self, type):
        self.type = type
    
    def set_index(self, index):
        self.index = index
    
    def set_position(self, posX, posY):
        self.posX = posX
        self.posY = posY
    
    def set_local_position(self, local_posX, local_posY):
        self.local_posX = local_posX
        self.local_posY = local_posY
    
    def set_status(self, status):
        self.status = status
    
    def set_appearMsec(self, appearMsec):
        self.appearMsec = appearMsec
    
    def set_touchDecor(self, touchDecor):
        self.touchDecor = touchDecor
    
    def set_holdSize(self, holdSize):
        self.holdSize = holdSize
    
    def set_starScale(self, starScale):
        self.starScale = starScale
    
    def set_userNoteSize(self, userNoteSize):
        self.userNoteSize = userNoteSize
    
    # 查询方法
    def get_frameTime(self):
        return self.frameTime

    def get_type(self):
        return self.type
    
    def get_index(self):
        return self.index
    
    def get_position(self):
        return (self.posX, self.posY)
    
    def get_local_position(self):
        return (self.local_posX, self.local_posY)
    
    def get_status(self):
        return self.status
    
    def get_appearMsec(self):
        return self.appearMsec
    
    def get_touchDecor(self):
        return self.touchDecor
    
    def get_holdSize(self):
        return self.holdSize
    
    def get_starScale(self):
        return self.starScale
    
    def get_userNoteSize(self):
        return self.userNoteSize
    





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


def find_closest_notes(time_notes, target_time):
    """
    根据目标时间查找最接近的notes数据
    
    参数:
        time_notes: 按时间组织的notes字典 {时间戳: [notes列表]}
        target_time: 目标时间(毫秒)
        
    返回:
        最接近目标时间的notes列表
    """
    if not time_notes:
        return []
    
    # 获取所有时间戳并排序
    sorted_times = sorted(time_notes.keys())
    
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
        if len(parts) < 5:
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
            appearMsec=appear_msec
        )
        
        # 处理额外数据（如果存在第6部分）
        if len(parts) >= 6:
            extra_data = parts[5].strip()
            
            # 处理Touch类型的touchDecor数据
            if 'touch' in type_name.lower():
                if 'TouchDecorPosition:' in extra_data:
                    touch_decor = float(extra_data.split('TouchDecorPosition:')[1].strip())
                    note.set_touchDecor(touch_decor)
            
            # 处理Hold类型的holdSize数据
            elif 'hold' in type_name.lower():
                if 'HoldSize:' in extra_data:
                    hold_size = float(extra_data.split('HoldSize:')[1].strip())
                    note.set_holdSize(hold_size)
            
            # 处理Star类型的StarScale和UserNoteSize数据
            elif 'star' in type_name.lower():
                if 'StarScale:' in extra_data and 'UserNoteSize:' in extra_data:
                    # 解析StarScale
                    star_scale_part = extra_data.split('StarScale:')[1].split('|')[0].strip()
                    star_scale_values = star_scale_part.split(',')
                    star_scale = (float(star_scale_values[0]), float(star_scale_values[1]))
                    note.set_starScale(star_scale)
                    
                    # 解析UserNoteSize
                    user_note_size = float(extra_data.split('UserNoteSize:')[1].strip())
                    note.set_userNoteSize(user_note_size)
        
        return note
        
    except Exception:
        return None




def manual_align(video_path, txt_path, time_notes):
    """
    手动对齐视频帧和时间戳音符数据
    
    操作说明：
    - 空格：播放/暂停
    - 模式1（初始对齐模式）：音符保持不变
    - 按'c'键切换到模式2
    - 模式2（验证模式）：视频和音符同步
    - 左/右箭头：暂停并前进/后退一帧
    - 按'q'退出
    
    返回：时间偏移量(毫秒)
    """
    
    video_frame_counter = 0  # 视频当前帧
    notes_frame_counter = 0  # notes的虚拟帧计数器（独立于视频）
    mode = 1  # 1=初始对齐模式, 2=验证模式
    is_playing = False  # 播放状态

    cap = cv2.VideoCapture(video_path)
    total_video_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    #frame_delay = int(1000 / fps) if fps > 0 else 33  # 毫秒
    frame_delay = 1
    
    if not time_notes:
        print("没有找到音符数据！")
        cap.release()
        return 0

    # 获取所有时间戳并排序
    sorted_times = sorted(time_notes.keys())
    min_time = sorted_times[0]
    max_time = sorted_times[-1]
    
    window_name = 'Label Notes Alignment Tool'
    cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)
    

    
    while True:
        # 设置视频到指定帧
        cap.set(cv2.CAP_PROP_POS_FRAMES, video_frame_counter)
        ret, raw_frame = cap.read()
        
        if not ret:
            video_frame_counter = min(video_frame_counter, total_video_frames - 1)
            is_playing = False
            continue
        
        # 计算当前视频帧对应的时间(毫秒)
        current_video_time = frame_to_time(video_frame_counter, fps)
        
        # 计算notes虚拟帧对应的时间(毫秒)
        current_notes_time_from_frame = frame_to_time(notes_frame_counter, fps)
        
        # 根据notes虚拟帧时间查找最接近的音符
        current_notes = find_closest_notes(time_notes, current_notes_time_from_frame)
        
        # 绘制音符
        result_frame = raw_frame.copy()
        result_frame = draw_all_notes(result_frame, current_notes)
        
        # 显示信息
        play_status = "[PLAYING]" if is_playing else "[PAUSED]"
        mode_text = f"{play_status} Mode 1: Alignment" if mode == 1 else f"{play_status} Mode 2: Sync"
        mode_color = (0, 255, 255) if mode == 1 else (0, 255, 0)
        frame_diff = notes_frame_counter - video_frame_counter
        
        cv2.putText(result_frame, mode_text,
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, mode_color, 2)
        cv2.putText(result_frame, f"Video: {video_frame_counter}/{total_video_frames} frame ({current_video_time:.2f}ms)",
                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(result_frame, f"Notes: {notes_frame_counter} frame ({current_notes_time_from_frame:.2f}ms)",
                    (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(result_frame, f"Diff: {frame_diff} frames",
                    (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
        cv2.putText(result_frame, "Q:Quit | C:Mode",
                    (10, result_frame.shape[0] - 80), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        cv2.putText(result_frame, "Space: Play/Pause",
                    (10, result_frame.shape[0] - 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        cv2.putText(result_frame, "Arrow: Last frame",
                    (10, result_frame.shape[0] - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

        # 调整窗口大小
        if result_frame.shape[0] > result_frame.shape[1]:
            scale = 1000 / result_frame.shape[0]
            new_width = int(result_frame.shape[1] * scale)
            new_height = 1000
        else:
            scale = 1000 / result_frame.shape[1]
            new_width = 1000
            new_height = int(result_frame.shape[0] * scale)
        result_frame = cv2.resize(result_frame, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
        
        cv2.imshow(window_name, result_frame)

        # 等待按键（如果播放中使用帧延迟，否则无限等待）
        wait_time = frame_delay if is_playing else 0
        key = cv2.waitKey(wait_time) & 0xFF
        
        if key == ord('q') or key == ord('Q'):  # 退出
            # 计算帧数差
            frame_diff = notes_frame_counter - video_frame_counter
            time_diff_ms = frame_to_time(abs(frame_diff), fps)
            
            print(f"对齐完成！")
            print(f"Diff: {frame_diff} frames ({time_diff_ms:.2f} ms)")
            time_offset = time_diff_ms if frame_diff >= 0 else -time_diff_ms
            break
            
        elif key == ord('c') or key == ord('C'):  # 切换模式
            is_playing = False
            mode = 2 if mode == 1 else 1
        
        elif key == 32:  # 空格：播放/暂停
            is_playing = not is_playing
                
        elif key == 0:  # 四个箭头键 (四个键都是0，不知道怎么区分)
            is_playing = False  # 箭头操作时暂停
            if mode == 1:
                # 模式1：只后退视频帧，notes进度不变
                video_frame_counter = max(video_frame_counter - 1, 0)
            else:
                # 模式2：视频和notes同时后退
                video_frame_counter = max(video_frame_counter - 1, 0)
                notes_frame_counter = max(notes_frame_counter - 1, 0)
        
        # 如果正在播放，自动前进
        if is_playing:
            if mode == 1:
                # 模式1：只前进视频帧，notes进度不变
                video_frame_counter += 1
                if video_frame_counter >= total_video_frames:
                    video_frame_counter = total_video_frames - 1
                    is_playing = False
            else:
                # 模式2：视频和notes同时前进
                video_frame_counter += 1
                notes_frame_counter += 1
                if video_frame_counter >= total_video_frames:
                    video_frame_counter = total_video_frames - 1
                    is_playing = False
    
    cap.release()
    cv2.destroyWindow(window_name)

    return time_offset



def draw_tap_note(note):
    """
    绘制单个Tap音符
    
    输入：
        note: Note对象
        
    返回：
        list: 4个点的坐标 [(x1,y1), (x2,y2), (x3,y3), (x4,y4)]
              这4个点构成一个可能带旋转角度的矩形
    """
    # TODO: 实现具体逻辑
    # 目前返回一个基于音符位置的简单矩形
    center_x = 1080 + note.posX
    center_y = 120 - note.posY
    size = 1080 * 0.042  # 基础大小
    
    # 返回4个角点（左上、右上、右下、左下）
    points = [
        (center_x - size, center_y - size),  # 左上
        (center_x + size, center_y - size),  # 右上
        (center_x + size, center_y + size),  # 右下
        (center_x - size, center_y + size),  # 左下
    ]
    
    return points


def draw_hold_note(note):
    """
    绘制单个Hold音符
    
    输入：
        note: Note对象，包含holdSize等属性
        
    返回：
        list: 4个点的坐标 [(x1,y1), (x2,y2), (x3,y3), (x4,y4)]
              这4个点构成一个可能带旋转角度的矩形
    """
    # TODO: 实现具体逻辑
    # Hold音符可能需要考虑holdSize来确定矩形大小
    center_x = 1080 + note.posX
    center_y = 120 - note.posY
    size = 1080 * 0.042
    
    # 如果有holdSize，可以用来调整矩形大小
    hold_size = note.get_holdSize() if note.get_holdSize() else 1.0
    
    points = [
        (center_x - size, center_y - size),
        (center_x + size, center_y - size),
        (center_x + size, center_y + size),
        (center_x - size, center_y + size),
    ]
    
    return points


def draw_slide_note(note):
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
    size = 1080 * 0.042
    
    points = [
        (center_x - size, center_y - size),
        (center_x + size, center_y - size),
        (center_x + size, center_y + size),
        (center_x - size, center_y + size),
    ]
    
    return points


def draw_touch_note(note):
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
    
    touch_decor = note.get_touchDecor() if note.get_touchDecor() else 0.0
    
    points = [
        (center_x - size, center_y - size),
        (center_x + size, center_y - size),
        (center_x + size, center_y + size),
        (center_x - size, center_y + size),
    ]
    
    return points


def draw_touch_hold_note(note):
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
    
    return points


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
    import numpy as np
    
    # 转换为整数坐标
    pts = np.array(points, dtype=np.int32)
    
    # 绘制矩形（连接4个点）
    cv2.polylines(frame, [pts], isClosed=True, color=color, thickness=thickness)
    
    return frame


def draw_all_notes(frame, notes):
    """
    绘制所有类型的音符
    使用独立的绘制函数为每种音符类型生成矩形框
    """
    for note in notes:
        note_type = note.get_type().lower()
        
        # 根据音符类型调用对应的绘制函数
        points = None
        color = (255, 255, 255)  # 默认白色
        label = ""
        
        if 'tap' in note_type and 'hold' not in note_type:
            # Tap音符：绿色
            points = draw_tap_note(note)
            color = (0, 255, 0)
            label = 'TAP'
            
        elif 'hold' in note_type and 'touch' not in note_type:
            # Hold音符：蓝色
            points = draw_hold_note(note)
            color = (255, 0, 0)
            label = 'HOLD'
            
        elif 'slide' in note_type:
            # Slide音符：黄色
            points = draw_slide_note(note)
            color = (0, 255, 255)
            label = 'SLIDE'
            
        elif 'touch' in note_type and 'hold' in note_type:
            # Touch-Hold音符：青色
            points = draw_touch_hold_note(note)
            color = (255, 255, 0)
            label = 'T-HOLD'
            
        elif 'touch' in note_type:
            # Touch音符：紫色
            points = draw_touch_note(note)
            color = (255, 0, 255)
            label = 'TOUCH'
        
        # 绘制矩形框
        if points:
            frame = draw_rotated_rect(frame, points, color, thickness=2)
            
            # 计算中心点用于显示标签
            center_x = int(sum(p[0] for p in points) / 4)
            center_y = int(sum(p[1] for p in points) / 4)
            
            # 显示音符类型标签
            cv2.putText(frame, label, (center_x - 25, center_y + 5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
            
            # 显示索引号
            cv2.putText(frame, str(note.get_index()), 
                       (center_x - 8, center_y - 20), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    return frame


def draw_tap_notes(frame, notes):
    """保留原函数以兼容"""
    for note in notes:
        # draw circle
        center = (round(1080+note.posX)+1, round(120-note.posY))
        radius = round(1080 * 0.042)
        cv2.circle(frame, center, radius, (0, 255, 0), 2)

    return frame


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
        result_frame = draw_all_notes(frame, current_notes)
        
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

    video_path = r"D:\git\mai-chart-analyze\yolo-train\temp\11753_standardized.mp4"
    txt_path= r"C:\Users\ck273\Desktop\训练视频\11753_2025-08-15_21-47-03.txt"
    output_dir = r"C:\Users\ck273\Desktop\训练视频\11753"
    mode = 0

    # 执行对齐
    time_offset = main(video_path, txt_path, output_dir, mode)
    
    # 如果需要对齐后的视频处理，可以取消注释下面的代码
    # output_video = os.path.join(output_dir, "output_with_notes.mp4")
    # process_video_with_notes(video_path, txt_path, time_offset, output_video)
