import os
import cv2

class NoteAnalyzer:

    def __init__(self):
        self.output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "yolo-train", "runs", "detect")

    def read_labels(self, state):
        
        try:
            name = "Deicide"
            total_frames = state['total_frames']
            labels = {}
            label_dir = os.path.join(self.output_dir, name, "labels")
            label_list_temp = []

            for label in os.listdir(label_dir):
                if not label.endswith(".txt"):
                    continue
                label_path = os.path.join(label_dir, label)
                # 分离出frame_counter
                frame_counter = label.split('_')[-1].split('.')[0]
                if not 0 < int(frame_counter) <= total_frames:
                    continue
                # 读取标签文件
                with open(label_path, 'r') as f:
                    lines = f.readlines()
                    for line in lines:
                        parts = line.strip().split()
                        if len(parts) != 6:
                            continue
                        # class id: 0 hold, 1 slide, 2 tap, 3 touch, 4 touch_hold
                        label_data = {
                            'class_id': int(parts[0]),
                            'x_norm': float(parts[1]),
                            'y_norm': float(parts[2]),
                            'w_norm': float(parts[3]),
                            'h_norm': float(parts[4]),
                            'confidence': float(parts[5])
                        }
                        label_list_temp.append(label_data)
                # 保存标签
                labels[int(frame_counter)] = label_list_temp
                label_list_temp = []

            return labels
        
        except Exception as e:
            raise Exception(f"Error in read_labels: {e}")
        

    def analyze(self, state, labels):

        try:
            video_path = state['video_path']
            video_fps = state['video_fps']
            video_width = state['video_width']
            video_height = state['video_height']
            total_frames = state['total_frames']
            bpm = state['bpm']
            chart_start = state['chart_start']

            cap = cv2.VideoCapture(video_path)
            frame_counter = 0

            for frame_num, label_list in labels:

                # 首先通过cap获取视频原始帧
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
                ret, frame = cap.read()
                if not ret:
                    raise Exception(f"Error reading frame {frame_num} from video {video_path}") 


        except Exception as e:
            raise Exception(f"Error in analyze: {e}")