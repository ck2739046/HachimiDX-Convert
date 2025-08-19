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

    video_start = 0

    return video_start




def main(video_path, txt_path, output_dir, mode):

    # check file exist
    if not os.path.exists(video_path):
        print(f"Video file not found: {video_path}")
        return

    if not os.path.exists(txt_path):
        print(f"Text file not found: {txt_path}")
        return

    notes = parse_txt(txt_path)
    video_start = manual_align(video_path, txt_path, notes)

if __name__ == "__main__":

    video_path = r"C:\Users\ck273\Desktop\训练视频\11537_standardlized.mp4"
    txt_path= r"C:\Users\ck273\Desktop\训练视频\11537_2025-08-15_21-50-32.txt"
    output_dir = r"C:\Users\ck273\Desktop\训练视频\11537"
    mode = 0

    main(video_path, txt_path, output_dir, mode)
