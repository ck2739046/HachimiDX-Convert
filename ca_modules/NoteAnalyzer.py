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
        self.note_DefaultMsec = -1
        self.touch_DefaultMsec = -1

    
    
    def get_DefaultMsec(self, detected_note_speed, fps, circle_radius):

        def get_standard_DefaultMsec(ui_speed):
            # 游戏源码实现
            OptionNotespeed = int(ui_speed * 100 + 100) # 6.25 = 725
            NoteSpeedForBeat = 1000 / (OptionNotespeed / 60)
            DefaultMsec = NoteSpeedForBeat * 4
            return DefaultMsec

        offset = 5
        # detected_note_speed 单位是 像素/帧
        Msec_per_frame = 1000 / fps
        detected_note_speed_per_Msec = detected_note_speed / Msec_per_frame

        total_dist = circle_radius * 0.75
        note_lifetime = total_dist / detected_note_speed_per_Msec + offset

        # 查找最接近的 DefaultMsec
        cloest_DefaultMsec = 0
        cloest_i = 0
        i = 1
        while i <= 10:
            DefaultMsec = get_standard_DefaultMsec(i)
            if abs(DefaultMsec - note_lifetime) < abs(cloest_DefaultMsec - note_lifetime):
                cloest_DefaultMsec = DefaultMsec
                cloest_i = i
            i += 0.25

        print(f"estimate speed: {cloest_i:.2f} - {cloest_DefaultMsec:.3f}ms (detect {note_lifetime:.3f}ms)")

        return cloest_DefaultMsec
    


    def predict_note_remaining_time(self, dist, circle_info):

        circle_center_x, circle_center_y, circle_radius = circle_info
        start = circle_radius * 0.25
        end = circle_radius
        total_dist = end - start

        travelled_dist = (dist - start) / total_dist
        travelled_Msec = travelled_dist * self.note_DefaultMsec
        remaining_Msec = self.note_DefaultMsec - travelled_Msec

        return remaining_Msec



    def draw_circle(self, video_path):
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                raise Exception(f"Cannot open video file: {video_path}")
            circle_center_x = 540
            circle_center_y = 540
            circle_radius = int(478 * 0.9)
            while True:
                ret, frame = cap.read()
                if not ret: break
                # 绘制圆
                cv2.circle(frame, (circle_center_x, circle_center_y), circle_radius, (0, 255, 0), 2)
                # 显示当前帧
                cv2.imshow('Circle', frame)
                # 按 'q' 键退出
                key = cv2.waitKey(0)
                if key & 0xFF == ord('q'):
                    break
        except Exception as e:
            raise Exception(f"Error in draw_circle: {e}")



    def process(self, state: dict):
        try:
            circle_center_x = 540
            circle_center_y = 540
            circle_radius = 478
            circle_info = (circle_center_x, circle_center_y, circle_radius)
            video_name = state['video_name']
            detect_video_path = state['detect_video_path']
            output_dir = os.path.dirname(detect_video_path)
            debug = state['debug']
            fps = state['video_fps']
            bpm = state['bpm']
            
            # Load detection data
            self.final_tracks, self.track_results_all, self.predict_results_all, self.metadata = self.load_detection_data(output_dir, video_name)

            # Calculate speed
            self.note_speed = self.calculate_note_speed(circle_info, fps, debug)
            #self.touch_speed = self.calculate_touch_speed(circle_info, debug)

            # Calculate note time
            self.calculate_tap_arrival_time(circle_info, fps, bpm, debug)


        except Exception as e:
            raise Exception(f"Error in NoteAnalyzer: {e}")
        


    def calculate_tap_arrival_time(self, circle_info, fps, bpm, debug):
        try:
            circle_center_x, circle_center_y, circle_radius = circle_info

            dist_to_center_dict = {}

            # read final_tracks
            for track_id, track_data in self.final_tracks.items():
                if 'path' not in track_data: continue
                track_path = track_data['path']
                if len(track_path) < 5: continue
                class_id = int(track_data['class_id'])

                if class_id != 2: continue # tap
                dist_to_center_dict[track_id] = []

                for track_box in track_path:
                    track_frame_num = int(track_box['frame'])
                    track_center_x = int(track_box['center_x'])
                    track_center_y = int(track_box['center_y'])

                    dist_to_center = np.sqrt(((track_center_x - circle_center_x)**2 + (track_center_y - circle_center_y)**2))
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
                            dist_to_center = np.sqrt(((predict_center_x - circle_center_x)**2 + (predict_center_y - circle_center_y)**2))
                            dist_to_center_dict[track_id].append((dist_to_center, track_frame_num))
                            break
                    '''

            # 计算tap到达时间
            start_tolerance = circle_radius * 0.05
            end_tolerance = circle_radius * 0.15
            dist_start = circle_radius * 0.25
            dist_end = circle_radius
            tap_arrival_time = {}
            for track_id, distances in dist_to_center_dict.items():
                distances.sort(key=lambda x: x[1]) # 按frame排序
                tap_arrival_time[track_id] = []

                for dist, frame_num in distances:

                    # 排除scale阶段的数据
                    if abs(dist - dist_start) <= start_tolerance:
                        continue
                    elif abs(dist - dist_end) <= end_tolerance:
                        continue

                    current_time = frame_num / fps * 1000  # 转换为毫秒
                    remaining_time = self.predict_note_remaining_time(dist, circle_info)
                    arrival_time = current_time + remaining_time
                    tap_arrival_time[track_id].append(arrival_time)

            # 计算平均tap到达时间
            if not tap_arrival_time:
                print('No tap notes found')
                return 0
            
            final_arrival_times = []
            for track_id, arrival_times in tap_arrival_time.items():
                
                data = np.array(arrival_times)
                mean = np.mean(data)
                final_arrival_times.append((track_id, mean))

                #if debug:
                    #min = np.min(data)
                    #max = np.max(data)
                    #median = np.median(data)
                    #std_dev = np.std(data)
                    #print(f"Tap arrival time for track {track_id}: Mean: {mean:.3f}, Min: {min:.3f}, Max: {max:.3f}, Median: {median:.3f}, Std Dev: {std_dev:.3f}")
            
            beat_Msec = 60 / bpm * 1000 * 4
            first = 0
            last_note_arrival_time = 0
            final_arrival_times.sort(key=lambda x: x[1]) # sort by arrival time
            for track_id, arrival_time in final_arrival_times:
                if first == 0:
                    first = arrival_time
                    last_note_arrival_time = arrival_time
                    print(f'{track_id}-{arrival_time:.3f}, ', end='')
                    continue
                diff = arrival_time - last_note_arrival_time
                diff_beat = diff / beat_Msec
                print(f'{track_id}-{diff_beat:.3f}, ', end='')
                last_note_arrival_time = arrival_time


        except Exception as e:
            raise Exception(f"Error in calculate_tap_arrival_time: {e}")



    def calculate_note_speed(self, circle_info, fps, debug):
        try:
            circle_center_x, circle_center_y, circle_radius = circle_info

            dist_to_center_dict = {}

            # read final_tracks
            for track_id, track_data in self.final_tracks.items():
                if 'path' not in track_data: continue
                track_path = track_data['path']
                if len(track_path) < 5: continue
                class_id = int(track_data['class_id'])

                if class_id != 2: continue # tap
                dist_to_center_dict[track_id] = []

                for track_box in track_path:
                    track_frame_num = int(track_box['frame'])
                    track_center_x = int(track_box['center_x'])
                    track_center_y = int(track_box['center_y'])

                    dist_to_center = np.sqrt(((track_center_x - circle_center_x)**2 + (track_center_y - circle_center_y)**2))
                    dist_to_center_dict[track_id].append((dist_to_center, track_frame_num))


            start_tolerance = circle_radius * 0.05
            end_tolerance = circle_radius * 0.15
            dist_start = circle_radius * 0.25
            dist_end = circle_radius
            final_tap_speed = {}
            for track_id, distances in dist_to_center_dict.items():
                
                distances.sort(key=lambda x: x[1]) # 按frame排序
                leave_start = (0, 0)
                reach_end = (0, 0)
                for dist, frame_num in distances:
                    # 只取中间段的数据
                    if abs(dist - dist_start) < start_tolerance:
                        continue
                    elif abs(dist - dist_end) < end_tolerance:
                        continue
                    
                    if leave_start[1] == 0: leave_start = (dist, frame_num)
                    reach_end = (dist, frame_num)
                
                #print(f"track_id: {track_id}, leave_start: {leave_start}, reach_end: {reach_end}")
                if leave_start[1] > 0 and reach_end[1] > 0 and reach_end[1] > leave_start[1]:
                    total_dist = reach_end[0] - leave_start[0]
                    total_frame = reach_end[1] - leave_start[1]
                    note_speed = total_dist / total_frame
                    final_tap_speed[track_id] = note_speed


            # calcualte average speed
            if not final_tap_speed:
                print('2')
                return 0
            
            if debug:
                data = list(final_tap_speed.values())
                mean = np.mean(data)
                #min = np.min(data)
                #max = np.max(data)
                #median = np.median(data)
                #std_dev = np.std(data)
                #print(f"note speed: Mean: {mean:.3f}, Min: {min:.3f}, Max: {max:.3f}, Median: {median:.3f}, Std Dev: {std_dev:.3f}")

            DefaultMsec = self.get_DefaultMsec(mean, fps, circle_radius)

            return round(DefaultMsec, 3)

        except Exception as e:
            raise Exception(f"Error in calculate_note_speed: {e}")
        
    #touch_size_min = circle_radius * 0.245
    #touch_size_max = circle_radius * 0.386
        


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
    id = '7.50'
    state = {
        'video_name': '踊',
        #'video_name': f'test_{id}',
        'detect_video_path': r"D:\git\mai-chart-analyse\yolo-train\runs\detect\踊\踊_tracked.mp4",
        #'detect_video_path': rf"D:\git\mai-chart-analyse\yolo-train\runs\detect\test_{id}\test_{id}_tracked.mp4",
        'debug': True,
        'video_fps': 60,
        'bpm': 120,
        #'bpm': 170, # test
    }
    analyzer.process(state)
    #analyzer.draw_circle(state['detect_video_path'])
