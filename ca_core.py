import cv2
import os
import ca_config

from ca_modules_pre.JudgeLineDetector import JudgeLineDetector
from ca_modules_pre.ChartStartDetector import ChartStartDetector
from ca_modules_pre.NoteSpeedDetector import NoteSpeedDetector

class ChartAnalyzer:
    def __init__(self):
        # video -------------
        self.frame_count: int = 0 # 帧计数
        self.current_frame = None # 当前帧
        self.cap = None           # cv2.VideoCapture对象
        # state -------------
        self.state = {}
        # video_width, video_height, video_fps, total_frames
        # circle_center, circle_radius, touch_areas, chart_start, note_speed
        # debug

    def update_state(self, key: str, value) -> None:
        """更新状态"""
        self.state[key] = value


    def analyze(self, video_path: str, debug : bool) -> bool:
        """主处理流程"""
        try:
            self.state["debug"] = debug
            # Load video
            self.load_video(video_path)
            
            # Preprocess
            self.run_preprocess()
            return True

            # Process video
            while True:
                ret, self.current_frame = self.cap.read()
                if not ret: break
                self.frame_count += 1
                self.process_frame()
            self.cap.release()

            # Postprocess
            self.run_postprocess()

            return True
        
        except Exception as e:
            print(f"Error in analyze: {e}")
            return False
    

    def run_preprocess(self):
        """运行预处理"""
        try:
            # get judge line
            detector = JudgeLineDetector()
            self.state['circle_center'], \
            self.state['circle_radius'], \
            self.state['touch_areas'] = detector.process(self.cap, self.state)

            # get chart start
            detector = ChartStartDetector()
            self.state['chart_start'] = detector.process(self.cap, self.state)

            # get note speed
            detector = NoteSpeedDetector()
            self.state['note_speed'] = detector.process(self.cap, self.state)
            return

        except Exception as e:
            raise Exception(f"Error in preprocess: {e}")
        

    def process_frame(self):
        """处理单个帧"""
        try:
            # call modules
            return
        except Exception as e:
            raise Exception(f"Error processing frame {self.frame_count}: {e}")
        
        
    def run_postprocess(self):
        """运行后处理"""
        try:
            # call modules
            return
        except Exception as e:
            raise Exception(f"Error in postprocess: {e}")


    def load_video(self, video_path: str):
        """加载视频文件, 获取信息
        arg: video_path
        ret: N/A
        设置self.state(video_width, video_height, video_fps, total_frames)
        设置self.cap = cv2.VideoCapture(video_path)                 
        """

        try:
            # load video
            if not os.path.exists(video_path):
                raise Exception(f"load_video: video file not found: {video_path}")
            
            self.cap = cv2.VideoCapture(video_path)
            if not self.cap.isOpened():
                raise Exception("load_video: fail set cv2.VideoCapture()")
            
            # get video info
            width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = int(self.cap.get(cv2.CAP_PROP_FPS))
            total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if total_frames < 600: # 10s
                raise Exception("load_video: video too short")
            
            # update state 
            self.update_state("video_width", max(width, height))  # 宽取大值
            self.update_state("video_height", min(width, height)) # 高取小值
            self.update_state("video_fps", fps)
            self.update_state("total_frames", total_frames)
            return
        
        except Exception as e:
            raise Exception(f"Error in load_video: {e}")


if __name__ == "__main__":
    video = r"C:\OBS\6_6_touch_178.mp4"
    ca = ChartAnalyzer()
    ca.analyze(video, True)
