import json
import os
import cv2
import numpy as np

class NoteAnalyzer:
    def __init__(self):
        self.final_tracks = {}
        self.track_results_all = {}
        self.predict_results_all = {}
        self.metadata = {}
        self.avg_speed = -1



    def process(self, state: dict):
        try:
            circle_center_x = 540
            circle_center_y = 540
            circle_radius = 474
            circle_info = (circle_center_x, circle_center_y, circle_radius)
            video_name = state['video_name']
            detect_video_path = state['detect_video_path']
            output_dir = os.path.dirname(detect_video_path)
            debug = state['debug']
            
            # Load detection data
            self.final_tracks, self.track_results_all, self.predict_results_all, self.metadata = self.load_detection_data(output_dir, video_name)

            # Calculate average speed
            self.avg_speed = self.calculate_avg_speed(circle_info, debug)


        except Exception as e:
            raise Exception(f"Error in NoteAnalyzer: {e}")



    def calculate_avg_speed(self, circle_info, debug):
        try:
            circle_center_x, circle_center_y, circle_radius = circle_info
            dist_to_center_dict = {}
            # read final_tracks
            for track_id, track_data in self.final_tracks.items():
                if 'path' not in track_data: continue
                track_path = track_data['path']
                if len(track_path) < 5: continue
                class_id = int(track_data['class_id'])

                if class_id != 2: continue
                dist_to_center_dict[track_id] = []

                for track_box in track_path:
                    track_frame_num = int(track_box['frame'])
                    track_center_x = int(track_box['center_x'])
                    track_center_y = int(track_box['center_y'])
                    track_width = int(track_box['width'])
                    track_height = int(track_box['height'])
                    track_conf = float(track_box['conf'])

                    dist_to_center = circle_radius - np.sqrt(((track_center_x - circle_center_x)**2 + (track_center_y - circle_center_y)**2))
                    dist_to_center_dict[track_id].append((dist_to_center, track_frame_num))

                    '''
                    predict_results_list = self.predict_results_all[track_frame_num]
                    for predict_result in predict_results_list:
                        predict_class_id = int(predict_result['class'])
                        if predict_class_id != class_id: continue
                        predict_box = predict_result['box']
                        predict_x1 = int(predict_box['x1'])
                        predict_y1 = int(predict_box['y1'])
                        predict_x2 = int(predict_box['x2'])
                        predict_y2 = int(predict_box['y2'])
                        predict_center_x = int((predict_x1 + predict_x2) / 2)
                        predict_center_y = int((predict_y1 + predict_y2) / 2)

                        tolerance = circle_radius * 0.05
                        if abs(track_center_x - predict_center_x) < tolerance and abs(track_center_y - predict_center_y) < tolerance:
                            pass
                    '''

            speed_tolerance = circle_radius * 0.03
            final_tap_speed = {}
            for track_id, distances in dist_to_center_dict.items():
                
                distances.sort(key=lambda x: x[1]) # 按frame排序
                last_distance = -1
                last_frame = -1
                speed_list = []
                for i in range(len(distances)-1): # skip last frame
                    dist, frame = distances[i]
                    dist_diff = last_distance - dist
                    frame_diff = frame-last_frame
                    last_distance = dist
                    last_frame = frame
                    if dist_diff > speed_tolerance and frame_diff > 0:
                        speed = dist_diff / frame_diff
                        speed_list.append(speed)
                    
                if len(speed_list) > 5:
                    average_speed = sum(speed_list) / len(speed_list)
                    final_tap_speed[track_id] = average_speed

            # calcualte average speed
            if not final_tap_speed:
                return 0

            if debug:
                data = list(final_tap_speed.values())
                min = np.min(data)
                max = np.max(data)
                mean = sum(data) / len(data)
                median = np.median(data)
                std_dev = np.std(data)
                print(f"  Mean: {mean:.3f}, Min: {min:.3f}, Max: {max:.3f}, Median: {median:.3f}, Std Dev: {std_dev:.3f}")

            return round(mean, 3)

        except Exception as e:
            raise Exception(f"Error in calculate_avg_speed: {e}")
        


    def load_detection_data(self, output_dir, video_name):
        try:
            # 加载final_tracks
            final_tracks_path = os.path.join(output_dir, f'{video_name}_final_tracks.json')
            with open(final_tracks_path, 'r', encoding='utf-8') as f:
                final_tracks = json.load(f)

            # 加载track_results_all from JSONL
            track_results_path = os.path.join(output_dir, f'{video_name}_track_results.jsonl')
            track_results_all = {}
            
            if os.path.exists(track_results_path):
                with open(track_results_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            frame_data = json.loads(line)
                            frame_num = frame_data['frame']
                            track_results_all[frame_num] = frame_data['results']
            
            # 加载predict_results_all from JSONL
            predict_results_path = os.path.join(output_dir, f'{video_name}_predict_results.jsonl')
            predict_results_all = {}
            
            if os.path.exists(predict_results_path):
                with open(predict_results_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            frame_data = json.loads(line)
                            frame_num = frame_data['frame']
                            predict_results_all[frame_num] = frame_data['results']

            # 加载元数据
            metadata_path = os.path.join(output_dir, f'{video_name}_metadata.json')
            metadata = None
            if os.path.exists(metadata_path):
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
            
            return final_tracks, track_results_all, predict_results_all, metadata
            
        except Exception as e:
            raise Exception(f"Error in load_detection_data: {e}")


if __name__ == "__main__":
    analyzer = NoteAnalyzer()
    state = {
        'video_name': 'test_6.0',
        #'detect_video_path': r"D:\git\mai-chart-analyse\yolo-train\runs\detect\踊\踊_tracked.mp4",
        'detect_video_path': r"D:\git\mai-chart-analyse\yolo-train\runs\detect\test\test_6.0_tracked.mp4",
        'debug': True
    }
    analyzer.process(state)
