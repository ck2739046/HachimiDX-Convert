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
        self.cap = None



    def calculate_tap_direction(self, circle_center_x, circle_center_y, note_x, note_y):
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
                


    def get_touch_DefaultMsec(self, detected_touch_DefaultMsec):

        def get_standard_touch_DefaultMsec(ui_speed):
            # 游戏源码实现
            option_touchspeed_dict = {
                1.00: 175.0,
                1.25: 183.0,
                1.50: 200.0,
                1.75: 212.0,
                2.00: 225.0,
                2.25: 237.0,
                2.50: 250.0,
                2.75: 262.0,
                3.00: 275.0,
                3.25: 283.0,
                3.50: 300.0,
                3.75: 312.0,
                4.00: 325.0,
                4.25: 337.0,
                4.50: 350.0,
                4.75: 375.0,
                5.00: 400.0,
                5.25: 425.0,
                5.50: 450.0,
                5.75: 475.0,
                6.00: 500.0,
                6.25: 525.0,
                6.50: 550.0,
                6.75: 575.0,
                7.00: 600.0,
                7.25: 625.0,
                7.50: 650.0,
                7.75: 675.0,
                8.00: 700.0,
                8.25: 725.0,
                8.50: 750.0,
                8.75: 775.0,
                9.00: 800.0,
                9.25: 825.0,
                9.50: 850.0,
                9.75: 875.0,
                10.00: 900.0
            }
            ui_speed = f'{ui_speed:.2f}'
            OptionNotespeed = option_touchspeed_dict[float(ui_speed)]
            NoteSpeedForBeat = 1000 / (OptionNotespeed / 60)
            DefaultMsec = NoteSpeedForBeat * 4
            return DefaultMsec
        
        offset = 5
        detected_touch_DefaultMsec += offset
        # 检查 detected_touch_DefaultMsec 距离哪个标准值最近
        closest_DefaultMsec = 0
        closest_i = 0
        i = 1
        while i <= 10:
            DefaultMsec = get_standard_touch_DefaultMsec(i)

            if abs(DefaultMsec - detected_touch_DefaultMsec) < abs(closest_DefaultMsec - detected_touch_DefaultMsec):
                closest_DefaultMsec = DefaultMsec
                closest_i = i
            i += 0.25

        print(f"estimate touch speed: {closest_i:.2f} - {closest_DefaultMsec:.3f}ms (detect {detected_touch_DefaultMsec:.3f}ms)")

        return closest_DefaultMsec


    
    
    def get_note_DefaultMsec(self, detected_note_speed, fps, circle_radius):

        def get_standard_note_DefaultMsec(ui_speed):
            # 游戏源码实现
            OptionNotespeed = int(ui_speed * 100 + 100) # 6.25 = 725
            NoteSpeedForBeat = 1000 / (OptionNotespeed / 60)
            DefaultMsec = NoteSpeedForBeat * 4
            return DefaultMsec

        offset = 5
        total_dist = circle_radius * 0.75

        # detected_note_speed 单位是 像素/帧
        Msec_per_frame = 1000 / fps
        detected_note_speed_per_Msec = detected_note_speed / Msec_per_frame
        note_lifetime = total_dist / detected_note_speed_per_Msec + offset

        # 查找最接近的 DefaultMsec
        cloest_DefaultMsec = 0
        cloest_i = 0
        i = 1
        while i <= 10:

            DefaultMsec = get_standard_note_DefaultMsec(i)

            if abs(DefaultMsec - note_lifetime) < abs(cloest_DefaultMsec - note_lifetime):
                cloest_DefaultMsec = DefaultMsec
                cloest_i = i
            i += 0.25

        print(f"estimate note speed: {cloest_i:.2f} - {cloest_DefaultMsec:.3f}ms (detect {note_lifetime:.3f}ms)")

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
            std_video = state['std_video_path']

            self.cap = cv2.VideoCapture(std_video)
            
            # Load detection data
            self.final_tracks, self.track_results_all, self.predict_results_all, self.metadata = self.load_detection_data(output_dir, video_name)

            # Calculate speed
            self.note_speed = self.calculate_note_speed(circle_info, fps, debug)
            self.touch_speed = self.calculate_touch_speed(circle_info, fps, debug)

            # Calculate note time
            self.calculate_tap_info(circle_info, fps, bpm, debug)


        except Exception as e:
            raise Exception(f"Error in NoteAnalyzer: {e}")
        


    def calculate_tap_info(self, circle_info, fps, bpm, debug):

        try:
            circle_center_x, circle_center_y, circle_radius = circle_info

            dist_to_center_dict = {}
            direction_dict = {}

            # read final_tracks
            for track_id, track_data in self.final_tracks.items():
                if 'path' not in track_data: continue
                track_path = track_data['path']
                if len(track_path) < 5: continue
                class_id = int(track_data['class_id'])

                if class_id != 2: continue # tap
                dist_to_center_dict[track_id] = []
                is_direction_calculated = False

                for track_box in track_path:
                    track_frame_num = int(track_box['frame'])
                    track_center_x = int(track_box['center_x'])
                    track_center_y = int(track_box['center_y'])

                    if not is_direction_calculated:
                        direction = self.calculate_tap_direction(circle_center_x, circle_center_y, track_center_x, track_center_y)
                        direction_dict[track_id] = direction
                        is_direction_calculated = True

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
                direction = direction_dict[track_id]
                final_arrival_times.append((track_id, mean, direction))

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
            for track_id, arrival_time, direction in final_arrival_times:
                if first == 0:
                    first = arrival_time
                    last_note_arrival_time = arrival_time
                    print(f'{direction}-{arrival_time:.3f}, ', end='')
                    continue
                diff = arrival_time - last_note_arrival_time
                diff_beat = diff / beat_Msec
                print(f'{direction}-{diff_beat:.3f}, ', end='')
                last_note_arrival_time = arrival_time


        except Exception as e:
            raise Exception(f"Error in calculate_tap_info: {e}")



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
                min = np.min(data)
                max = np.max(data)
                median = np.median(data)
                std_dev = np.std(data)
                print(f"note speed: Mean: {mean:.3f}, Min: {min:.3f}, Max: {max:.3f}, Median: {median:.3f}, Std Dev: {std_dev:.3f}")

            DefaultMsec = self.get_note_DefaultMsec(mean, fps, circle_radius)

            return round(DefaultMsec, 3)

        except Exception as e:
            raise Exception(f"Error in calculate_note_speed: {e}")
        


    def calculate_touch_speed(self, circle_info, fps, debug):

        #正向：
        #根据 time_progress = (current_time - (move_start_time - 0.25*DefaultMsec)) / DefaultMsec 获得 time_progress
        #应用缓动函数，location_progress = 缓动函数(time_progress)
        #假设touch note在刚开始move时的尺寸边长是start_size，完全闭合的尺寸变成是end_size，则根据location_progress决定新的size.
        #例如如果location_progress=0.5，则此时size=start_size + (end_size - start_size) * location_progress

        #逆向：
        #根据touch note的size，计算location_progress = (touch_size_max - size) / (touch_size_max - touch_size_min)
        #二分法，通过location_progress反推出time_progress ( y -> x )
        #根据 DefaultMsec = (current_time - move_start_time) / (time_progress - 0.25) 反推出 DefaultMsec

        def find_x_for_y(y, tolerance=0.000001):
            # 二分查找求解 y = 3.5x⁴ - 3.75x³ + 1.45x² - 0.05x + 0.0005 的反函数
            low, high = 0.0, 1.0
            
            while high - low > tolerance:
                mid = (low + high) / 2
                eased_y = 3.5 * mid**4 - 3.75 * mid**3 + 1.45 * mid**2 - 0.05 * mid + 0.0005
                
                if abs(eased_y - y) < tolerance:
                    return mid
                elif eased_y < y:
                    low = mid  # 标准的二分查找更新
                else:
                    high = mid
            return (low + high) / 2

        try:
            circle_center_x, circle_center_y, circle_radius = circle_info

            size_dict = {}

            # read final_tracks
            for track_id, track_data in self.final_tracks.items():
                if 'path' not in track_data: continue
                track_path = track_data['path']
                if len(track_path) < 5: continue
                class_id = int(track_data['class_id'])

                if class_id != 3: continue # touch
                size_dict[track_id] = []

                for track_box in track_path:
                    track_frame_num = int(track_box['frame'])
                    #track_center_x = int(track_box['center_x'])
                    #track_center_y = int(track_box['center_y'])
                    track_width = int(track_box['width'])
                    track_height = int(track_box['height'])

                    size = (track_height + track_width) / 2
                    size_dict[track_id].append((size, track_frame_num))


            touch_size_min = circle_radius * 0.245
            touch_size_max = circle_radius * 0.385
            tolerance = circle_radius * 0.03
            note_lifetimes = []
            for track_id, sizes in size_dict.items():
                
                sizes.sort(key=lambda x: x[1]) # 按frame排序;

                # simple note_lifetime
                size_init, frame_num_init = sizes[0]
                if abs(size_init - touch_size_max) > tolerance:
                    print(f"track_id: {track_id} has invalid size_init: {size_init:.2f} ({touch_size_max:.2f})")
                    continue
                size_last, frame_num_last = sizes[-1]
                if abs(size_last - touch_size_min) > tolerance:
                    print(f"track_id: {track_id} has invalid size_last: {size_last:.2f} ({touch_size_max:.2f})")
                    continue

                note_lifetime = (frame_num_last - frame_num_init) / fps * 1000  # 转换为毫秒
                note_lifetimes.append(note_lifetime)


                '''
                for size, frame_num in sizes:

                    if abs(size - touch_size_max) < tolerance or abs(size - touch_size_min) < tolerance:
                        continue

                    # 计算location_progress
                    location_progress = (touch_size_max - size) / (touch_size_max - touch_size_min)
                    if location_progress < 0.15 or location_progress > 0.97: continue
                    # 反推出time_progress
                    time_progress = find_x_for_y(location_progress)
                    # 反推出 DefaultMsec
                    current_time = frame_num / fps * 1000  # 转换为毫秒
                    DefaultMsec = (current_time - leave_start_time) / (time_progress - 0.25)
                    DefaultMsecs.append(DefaultMsec)
                    print(f"track_id: {track_id}, size: {size:.2f}, frame_num: {frame_num}, leave_start: {leave_start_time:.4f}, location_progress: {location_progress:.5f}, time_progress: {time_progress:.6f}, DefaultMsec: {DefaultMsec:.3f}")

                print()
                '''

            # calcualte average speed
            if not note_lifetimes:
                print('3')
                return 0
            
            if debug:
                data = np.array(note_lifetimes)
                mean = np.mean(data)
                min = np.min(data)
                max = np.max(data)
                median = np.median(data)
                std_dev = np.std(data)
                print(f"touch speed: Mean: {mean:.3f}, Min: {min:.3f}, Max: {max:.3f}, Median: {median:.3f}, Std Dev: {std_dev:.3f}")

            DefaultMsec = self.get_touch_DefaultMsec(mean*0.86)

            return round(DefaultMsec, 3)

        except Exception as e:
            raise Exception(f"Error in calculate_touch_speed: {e}")
        


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
    id = '6.75'
    state = {
        #'video_name': '踊',
        'video_name': f'test_{id}',
        #'detect_video_path': r"D:\git\mai-chart-analyse\yolo-train\runs\detect\踊\踊_tracked.mp4",
        'detect_video_path': rf"D:\git\mai-chart-analyse\yolo-train\runs\detect\test_{id}\test_{id}_tracked.mp4",
        'std_video_path': rf"D:\git\mai-chart-analyse\yolo-train\runs\detect\test_{id}\test_{id}_standardlized.mp4",
        'debug': True,
        'video_fps': 60,
        #'bpm': 120,
        'bpm': 170, # test
    }
    analyzer.process(state)
    #analyzer.draw_circle(state['detect_video_path'])
