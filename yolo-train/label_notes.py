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
    解析txt文件，返回一个list of list of notes
    每一帧创建一个note list，然后创建一个list包含所有帧的list
    """
    if not os.path.exists(txt_path):
        print(f"Text file not found: {txt_path}")
        return []
    
    frames_notes = []  # 存储所有帧的notes列表
    current_frame_notes = []  # 当前帧的notes列表
    current_frame_time = None
    
    with open(txt_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # 跳过空行和头部信息
        if not line or line.startswith('Note Dump') or line.startswith('Music Info') or line.startswith('Format') or line.startswith('='):
            i += 1
            continue
        
        # 检查是否是Frame行
        if line.startswith('Frame:'):
            # 如果已有当前帧数据，先保存
            if current_frame_time is not None and current_frame_notes:
                frames_notes.append(current_frame_notes)
            
            # 解析新帧信息
            frame_parts = line.split('|')
            frame_time_str = frame_parts[0].replace('Frame:', '')
            current_frame_time = float(frame_time_str)
            current_frame_notes = []  # 重置当前帧的notes列表
            
            i += 1
            continue
        
        # 解析note行
        if current_frame_time is not None:
            note = parse_note_line(line, current_frame_time)
            if note:
                current_frame_notes.append(note)
        
        i += 1
    
    # 处理最后一帧
    if current_frame_time is not None and current_frame_notes:
        frames_notes.append(current_frame_notes)
    
    return frames_notes


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
        
    except Exception as e:
        print(f"Error parsing note line: {line}")
        print(f"Error: {e}")
        return None




def manual_align(video_path, txt_path, notes):
    """
    手动对齐视频帧和txt音符帧
    
    操作说明：
    - 空格：播放/暂停
    - 模式1（初始对齐模式）：音符保持不变
    - 按'c'键切换到模式2
    - 模式2（验证模式）：视频和音符同步
    - 左/右箭头：暂停并前进/后退一帧
    - 按'q'退出
    
    返回：视频起始帧号（对应txt第一帧）
    """
    
    video_frame_counter = 0  # 视频当前帧
    notes_frame_counter = 0  # txt当前帧索引
    mode = 1  # 1=初始对齐模式, 2=验证模式
    alignment_offset = 0  # 记录对齐偏移量（视频帧 - txt帧）
    is_playing = False  # 播放状态

    cap = cv2.VideoCapture(video_path)
    total_video_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    total_notes_frames = len(notes)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_delay = int(1000 / fps) if fps > 0 else 33  # 毫秒
    
    if total_notes_frames == 0:
        print("没有找到音符数据！")
        cap.release()
        return 0

    window_name = 'Label Notes Alignment Tool'
    cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)
    
    print("=" * 60)
    print("手动对齐工具")
    print(f"视频帧率: {fps:.2f} FPS")
    print("=" * 60)
    print("基本操作：")
    print("  - 空格：播放/暂停")
    print("  - 左/右箭头：暂停并后退/前进一帧")
    print("  - 按'c'：切换模式")
    print("  - 按'q'：退出并保存")
    print("\n模式1（初始对齐）：音符保持在第一帧")
    print("模式2（验证模式）：视频和音符同步播放")
    print("=" * 60)
    
    while True:
        # 设置视频到指定帧
        cap.set(cv2.CAP_PROP_POS_FRAMES, video_frame_counter)
        ret, raw_frame = cap.read()
        
        if not ret:
            print(f"无法读取视频帧 {video_frame_counter}")
            video_frame_counter = min(video_frame_counter, total_video_frames - 1)
            is_playing = False
            continue
        
        # 获取当前要显示的音符
        current_notes = notes[notes_frame_counter] if notes_frame_counter < total_notes_frames else []
        
        # 绘制音符
        result_frame = raw_frame.copy()
        result_frame = draw_all_notes(result_frame, current_notes)
        
        # 显示信息
        play_status = "[PLAYING]" if is_playing else "[PAUSED]"
        mode_text = f"{play_status} Mode 1: Initial Alignment" if mode == 1 else f"{play_status} Mode 2: Verification"
        mode_color = (0, 255, 255) if mode == 1 else (0, 255, 0)
        
        cv2.putText(result_frame, mode_text, 
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, mode_color, 2)
        cv2.putText(result_frame, f"Video Frame: {video_frame_counter}/{total_video_frames}", 
                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(result_frame, f"Notes Frame: {notes_frame_counter}/{total_notes_frames}", 
                    (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(result_frame, f"Notes Count: {len(current_notes)}", 
                    (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        if mode == 2:
            alignment_offset = video_frame_counter - notes_frame_counter
            cv2.putText(result_frame, f"Offset: Video[{video_frame_counter}] = Notes[{notes_frame_counter}]", 
                        (10, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        cv2.putText(result_frame, "Q:Quit | C:Mode | Space:Play/Pause | Left/Right:Step", 
                    (10, result_frame.shape[0] - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

        # 调整窗口大小
        scale = 1000 / result_frame.shape[0]
        new_width = int(result_frame.shape[1] * scale)
        new_height = 1000
        result_frame = cv2.resize(result_frame, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
        
        cv2.imshow(window_name, result_frame)

        # 等待按键（如果播放中使用帧延迟，否则无限等待）
        wait_time = frame_delay if is_playing else 0
        key = cv2.waitKey(wait_time) & 0xFF
        
        if key == ord('q') or key == ord('Q'):  # 退出
            print("\n" + "=" * 60)
            print(f"对齐完成！")
            print(f"视频第 {alignment_offset} 帧 = txt第 0 帧")
            print(f"(即txt第一帧对应视频的第 {alignment_offset} 帧)")
            print("=" * 60)
            break
            
        elif key == ord('c') or key == ord('C'):  # 切换模式
            is_playing = False  # 切换模式时暂停
            if mode == 1:
                mode = 2
                alignment_offset = video_frame_counter - notes_frame_counter
                print(f"\n切换到验证模式。当前对齐：视频帧{video_frame_counter} = 音符帧{notes_frame_counter}")
            else:
                mode = 1
                print(f"\n切换回初始对齐模式。保持在：视频帧{video_frame_counter}, 音符帧{notes_frame_counter}")
        
        elif key == 32:  # 空格：播放/暂停
            is_playing = not is_playing
            status = "播放" if is_playing else "暂停"
            print(f"{status}中...")
                
        elif key == 83:  # 右箭头
            is_playing = False  # 箭头操作时暂停
            if mode == 1:
                # 模式1：只前进视频帧
                video_frame_counter = min(video_frame_counter + 1, total_video_frames - 1)
            else:
                # 模式2：同时前进视频帧和音符帧
                video_frame_counter = min(video_frame_counter + 1, total_video_frames - 1)
                notes_frame_counter = min(notes_frame_counter + 1, total_notes_frames - 1)
                
        elif key == 81:  # 左箭头
            is_playing = False  # 箭头操作时暂停
            if mode == 1:
                # 模式1：只后退视频帧
                video_frame_counter = max(video_frame_counter - 1, 0)
            else:
                # 模式2：同时后退视频帧和音符帧
                video_frame_counter = max(video_frame_counter - 1, 0)
                notes_frame_counter = max(notes_frame_counter - 1, 0)
        
        # 如果正在播放，自动前进
        if is_playing:
            if mode == 1:
                # 模式1：只前进视频帧
                video_frame_counter += 1
                if video_frame_counter >= total_video_frames:
                    video_frame_counter = total_video_frames - 1
                    is_playing = False
            else:
                # 模式2：同时前进视频帧和音符帧
                video_frame_counter += 1
                notes_frame_counter += 1
                if video_frame_counter >= total_video_frames or notes_frame_counter >= total_notes_frames:
                    video_frame_counter = min(video_frame_counter, total_video_frames - 1)
                    notes_frame_counter = min(notes_frame_counter, total_notes_frames - 1)
                    is_playing = False
    
    cap.release()
    cv2.destroyWindow(window_name)

    return alignment_offset



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
    print(f"正在解析文件: {txt_path}")
    notes = parse_txt(txt_path)
    print(f"解析完成！共找到 {len(notes)} 帧音符数据")
    
    if len(notes) == 0:
        print("错误：没有找到任何音符数据！")
        return
    
    # 统计总音符数
    total_notes = sum(len(frame_notes) for frame_notes in notes)
    print(f"总共 {total_notes} 个音符")
    
    # 手动对齐
    print(f"\n正在打开视频: {video_path}")
    alignment_offset = manual_align(video_path, txt_path, notes)
    
    # 保存对齐结果
    if output_dir and os.path.exists(output_dir):
        result_file = os.path.join(output_dir, "alignment_result.txt")
        with open(result_file, 'w', encoding='utf-8') as f:
            f.write(f"Video File: {video_path}\n")
            f.write(f"Notes File: {txt_path}\n")
            f.write(f"Alignment Offset: {alignment_offset}\n")
            f.write(f"(Video frame {alignment_offset} = Notes frame 0)\n")
        print(f"\n对齐结果已保存到: {result_file}")
    
    return alignment_offset

if __name__ == "__main__":

    video_path = r"C:\Users\ck273\Desktop\训练视频\11753.mp4"
    txt_path= r"C:\Users\ck273\Desktop\训练视频\11753_2025-08-15_21-47-03.txt"
    output_dir = r"C:\Users\ck273\Desktop\训练视频\11753"
    mode = 0

    main(video_path, txt_path, output_dir, mode)
