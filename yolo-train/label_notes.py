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
    with open(txt_path, "r") as f:
        lines = f.readlines()



def manual_align(video_path, txt_path):

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

    video_start = manual_align(video_path, txt_path)

if __name__ == "__main__":

    video_path = r"C:\Users\ck273\Desktop\训练视频\11537_standardlized.mp4"
    txt_path= r"C:\Users\ck273\Desktop\训练视频\11537_2025-08-15_21-50-32.txt"
    output_dir = r"C:\Users\ck273\Desktop\训练视频\11537"
    mode = 0

    main(video_path, txt_path, output_dir, mode)
