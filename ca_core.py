import cv2
import os
from typing import Dict, List
import ca_config

from ca_modules_pre.JudgeLineDetector import JudgeLineDetector

class ChartAnalyzer:
    def __init__(self):
        # video -------------
        self.frame_count: int = 0 # 帧计数
        self.current_frame = None # 当前帧
        self.cap = None           # cv2.VideoCapture对象
        # state -------------
        self.state = {}     # 运行时的状态

    def update_state(self, key: str, value) -> None:
        """更新状态"""
        self.state[key] = value


    def analyze(self, video_path: str) -> bool:
        """主处理流程"""

        # 加载视频
        self.state["debug"] = False
        if not self.load_video(video_path): return False
        
        # 视频预处理
        if not self.run_preprocess(): return False

        while True:
            ret, self.current_frame = self.cap.read()
            if not ret:
                break

            self.frame_count += 1
            if not self.process_frame():
                return False

        self.cap.release()

        # 后处理
        return self.run_postprocess()
    

    def run_preprocess(self) -> bool:
        """运行预处理"""
        try:
            # call modules
            detector = JudgeLineDetector()
            if not detector.process(self.cap, self.state):
                return False

        except Exception as e:
            print(f"Error in preprocess: {e}")
            return False
        

    def process_frame(self) -> bool:
        """处理单个帧"""
        try:
            # call modules
            return True
        except Exception as e:
            print(f"Error processing frame {self.frame_count}: {e}")
            return False
        
        
    def run_postprocess(self) -> bool:
        """运行后处理"""
        try:
            # call modules
            return True
        except Exception as e:
            print(f"Error in postprocess: {e}")
            return False


    def load_video(self, video_path: str) -> bool:
        """加载视频文件, 获取信息
        arg: video_path
        ret: bool
        设置self.state(video_width, video_height, video_fps, total_frames)
        设置self.cap = cv2.VideoCapture(video_path)                 
        """

        # 加载视频文件
        if not os.path.exists(video_path):
            print(f"Error load_video: video file not found: {video_path}")
            return False
        
        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            print("Error load_video: fail set cv2.VideoCapture()")
            return False
        
        # 获取视频信息
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = int(self.cap.get(cv2.CAP_PROP_FPS))
        total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames < 600: # 10s
            print("Error load_video: video too short")
            return False
        self.update_state("video_width", max(width, height))  # 宽取大值
        self.update_state("video_height", min(width, height)) # 高取小值
        self.update_state("video_fps", fps)
        self.update_state("total_frames", total_frames)

        return True


if __name__ == "__main__":
    video = r"C:\Code\Ariake-720p.mp4"
    ca = ChartAnalyzer()
    ca.analyze(video)