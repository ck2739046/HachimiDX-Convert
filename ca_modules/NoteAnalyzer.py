import json
import os
import cv2
import numpy as np
import functools
import traceback
from ultralytics import YOLO

error_trace = []

def log_error(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:
            error_trace.append(f'{func.__name__}')
            raise
    return wrapper



class NoteAnalyzer:
    def __init__(self):
        self.note_DefaultMsec = 0
        self.note_OptionNotespeed = 0
        self.touch_DefaultMsec = 0
        self.touch_OptionNotespeed = 0
        self.cap = None
        self.touch_type_classify_model = None
        self.touch_scale_classify_regular_model = None
        self.touch_scale_classify_each_model = None
        self.touch_areas = None



    # debug
    @log_error
    def preprocess_tap_data(self, final_tracks, track_results_all, predict_results_all, circle_info):
        '''
        坐标使用predict_results_all的数据
        过滤scale阶段的数据, 只保留move阶段的数据

        返回格式:
        dict{
            key: (track_id, direction),
            value: note path list
            [
                {
                    'frame': frame_num,
                    'x1': x1,
                    'y1': y1,
                    'x2': x2,
                    'y2': y2,
                    'center_x': center_x,
                    'center_y': center_y,
                    'dist': dist_to_center
                },
                ...
            ]
        }
        '''

        circle_center_x, circle_center_y, circle_radius = circle_info
        tap_data = {}

        close_tolerance = circle_radius * 0.05
        start_tolerance = circle_radius * 0.02
        dist_start = circle_radius * 0.25
        dist_end = circle_radius

        # read final_tracks
        for track_id, track_data in final_tracks.items():
            if 'path' not in track_data: continue
            track_path = track_data['path']
            if len(track_path) < 5: continue
            class_id = int(track_data['class_id'])
            if class_id != 2: continue # tap

            predict_track_path = []

            for track_box in track_path:
                track_frame_num = int(track_box['frame'])
                track_conf = float(track_box['conf'])
                track_x1 = int(track_box['x1'])
                track_y1 = int(track_box['y1'])
                track_x2 = int(track_box['x2'])
                track_y2 = int(track_box['y2'])
                track_center_x = (track_x1 + track_x2) / 2
                track_center_y = (track_y1 + track_y2) / 2

                match_found = []

                # 从predict_results_all中获取对应的音符
                predict_results_list = predict_results_all[track_frame_num]
                for predict_result in predict_results_list:

                    # 判断 conf
                    predict_conf = float(predict_result['confidence'])
                    if track_conf != predict_conf: continue
                    # 判断 class_id
                    predict_class_id = int(predict_result['class'])
                    if predict_class_id != class_id: continue
                    # 判断 中心距离
                    box = predict_result['box']
                    predict_x1 = int(box['x1'])
                    predict_y1 = int(box['y1'])
                    predict_x2 = int(box['x2'])
                    predict_y2 = int(box['y2'])
                    predict_center_x = (predict_x1 + predict_x2) / 2
                    predict_center_y = (predict_y1 + predict_y2) / 2
                    if abs(track_center_x - predict_center_x) > close_tolerance or \
                        abs(track_center_y - predict_center_y) > close_tolerance: continue 
                    # 计算距离圆心的距离
                    dist_to_center = np.sqrt(((predict_center_x - circle_center_x)**2 + (predict_center_y - circle_center_y)**2))                   
                    # 计算方向(1-8)
                    direction = self.calculate_oct_direction(circle_center_x, circle_center_y, predict_center_x, predict_center_y)
                    # 添加到匹配列表
                    match_found.append((track_frame_num,
                                        predict_x1,
                                        predict_y1,
                                        predict_x2,
                                        predict_y2,
                                        predict_center_x,
                                        predict_center_y,
                                        direction,
                                        dist_to_center))


                if not match_found:
                    print(f"preprocess_tap_data: no match found for track_id {track_id} at frame {track_frame_num}")
                    continue
                elif len(match_found) > 1:
                    print(f"preprocess_tap_data: multiple matches found for track_id {track_id} at frame {track_frame_num}")
                    match_found.sort(key=lambda x: x[-1]) # 按距离排序

                # 过滤 scale 阶段的数据
                dist_to_center = match_found[0][-1]
                if abs(dist_to_center - dist_start) < start_tolerance:
                    continue # 掐头
                elif dist_to_center > dist_end:
                    continue # 去尾

                predict_track_path.append(match_found[0])

            
            if not predict_track_path:
                print(f"preprocess_tap_data: predict_track_path not found for track_id {track_id}")
                continue
            predict_track_path.sort(key=lambda x: x[0]) # 按frame排序
            # 检验长度
            if len(predict_track_path) < 5:
                print(f"preprocess_tap_data: predict_track_path too short for track_id {track_id}, length: {len(predict_track_path)}")
                continue
            # 检验方向
            directions = [x[7] for x in predict_track_path]
            if len(set(directions)) != 1:
                print(f"preprocess_tap_data: directions not consistent for track_id {track_id}")
                continue
            # 添加到tap_data
            path = []
            for frame_num, x1, y1, x2, y2, center_x, center_y, direction, dist_to_center in predict_track_path:
                path.append({
                    'frame': frame_num,
                    'x1': x1,
                    'y1': y1,
                    'x2': x2,
                    'y2': y2,
                    'center_x': center_x,
                    'center_y': center_y,
                    'dist': dist_to_center
                })
            tap_data[(track_id, directions[0])] = path

        if not tap_data:
            print("preprocess_tap_data: no tap data")
            return {}

        return tap_data
    


    @log_error
    def estimate_note_DefaultMsec(self, tap_data, circle_info, fps):
        """
        音符移动阶段的生命周期是 DefaultMsec (ms)
        从起点移动到判定线需要耗时 DefaultMsec (ms)
        """

        note_speeds = []

        for (track_id, direction), path in tap_data.items():
            frame_num_start = path[0]['frame']
            frame_num_end = path[-1]['frame']
            dist_start = path[0]['dist']
            dist_end = path[-1]['dist']

            frame_num_diff = frame_num_end - frame_num_start
            total_dist = dist_end - dist_start
            note_speed = total_dist / frame_num_diff # pixel/frame
            note_speeds.append(note_speed)

            #self.draw_path_on_frame(track_id, frame_num_start, path, circle_info)

        mean = np.mean(note_speeds)
        min = np.min(note_speeds)
        max = np.max(note_speeds)
        median = np.median(note_speeds)
        std_dev = np.std(note_speeds)
        print(f"Avg note speed: Mean {mean:.3f}, Min: {min:.3f}, Max: {max:.3f}, Median: {median:.3f}, Std Dev: {std_dev:.3f}")

        note_DefaultMsec, note_OptionNotespeed = self.get_note_DefaultMsec(mean, fps, circle_info[2])
        return note_DefaultMsec, note_OptionNotespeed
    


    @log_error
    def analyze_tap_reach_time(self, tap_data, circle_info, fps, bpm):

        tap_info = {}
        for (track_id, direction), path in tap_data.items():
            # 平均所有轨迹的到达时间
            times = []
            for point in path:
                frame_num = point['frame']
                dist = point['dist']
                reach_end_Msec2 = self.predict_note_reach_end_time(dist, frame_num, circle_info[2], fps)
                times.append(reach_end_Msec2)
            mean = np.mean(times)
            tap_info[(track_id, direction)] = mean

        return tap_info

        '''
        last_time = 0
        for (track_id, direction), time in tap_info.items():
            if last_time == 0:
                last_time = time
                print(f"{direction}-{time:.3f}, ", end='')
                continue
            diff_Msec = time - last_time
            diff_beat = diff_Msec / (60 / bpm * 1000 * 4)
            print(f"{direction}-{diff_beat:.3f}, ", end='')

            last_time = time
        '''


    @log_error
    def predict_note_reach_end_time(self, cur_dist, cur_frame, circle_radius, fps):
        '''
        正向:
        [dist_offset] = -1/120 * 总距离 * (OptionNotespeed/150f -1)

        时间进度 = (current_Msec - leave_start_Msec) / [DefaultMsec]
        travelled_dist = 时间进度 * [total_dist]
        current_dist = [startPos] + travelled_dist + [dist_offset]

        逆向:
        已知 current_dist, [dist_offset], [startPos]
        -> travelled_dist = current_dist - startPos - dist_offset
        已知 travelled_dist, [total_dist]
        -> 时间进度 = travelled_dist / total_dist
        已知 时间进度, [DefaultMsec], current_Msec
        -> leave_start_Msec = current_Msec - 时间进度 * DefaultMsec
        -> reach_end_Msec = leave_start_Msec + DefaultMsec
        '''

        cur_time = cur_frame / fps * 1000 # 转换为毫秒
        total_dist = circle_radius * 0.75
        dist_offset = -1/120 * total_dist * (self.note_OptionNotespeed / 150 - 1)
        start_pos = circle_radius * 0.25

        travelled_dist = cur_dist - start_pos - dist_offset
        time_progress = travelled_dist / total_dist
        leave_start_Msec = cur_time - time_progress * self.note_DefaultMsec
        reached_end_Msec = leave_start_Msec + self.note_DefaultMsec

        return reached_end_Msec



    @log_error
    def get_note_DefaultMsec(self, detected_note_speed, fps, circle_radius):

        def get_standard_note_DefaultMsec(ui_speed):
            # 游戏源码实现
            OptionNotespeed = int(ui_speed * 100 + 100) # 6.25 = 725
            NoteSpeedForBeat = 1000 / (OptionNotespeed / 60)
            DefaultMsec = NoteSpeedForBeat * 4
            return DefaultMsec, OptionNotespeed

        offset = 0.985
        total_dist = circle_radius * 0.75
        detected_note_speed = detected_note_speed * fps / 1000 # pixel/frame to pixel/ms
        note_lifetime = total_dist / detected_note_speed * offset

        # 查找最接近的 DefaultMsec
        cloest_DefaultMsec = 0
        cloest_i = 0
        cloest_OptionNotespeed = 0
        i = 1
        while i <= 10:

            DefaultMsec, OptionNotespeed = get_standard_note_DefaultMsec(i)

            if abs(DefaultMsec - note_lifetime) < abs(cloest_DefaultMsec - note_lifetime):
                cloest_DefaultMsec = DefaultMsec
                cloest_i = i
                cloest_OptionNotespeed = OptionNotespeed
            i += 0.25

        print(f"estimate note speed: {cloest_i:.2f} - {cloest_DefaultMsec:.3f}ms (detect {note_lifetime:.3f}ms)")

        return cloest_DefaultMsec, cloest_OptionNotespeed
    


    @log_error
    def draw_path_on_frame(self, track_id, frame_num, path, circle_info):
          
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
        ret, frame = self.cap.read()
        if not ret:
            print(f"draw_path_on_frame: failed to read frame {frame_num}")
            return
        
        circle_center_x, circle_center_y, circle_radius = circle_info
        cv2.putText(frame, f"track_id: {track_id}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.circle(frame, (int(circle_center_x), int(circle_center_y)), int(circle_radius*0.25), (0, 255, 0), 2)

        for point in path:
            frame_num = point['frame']
            center_x = point['center_x']
            center_y = point['center_y']
            cv2.circle(frame, (int(center_x), int(center_y)), 3, (0, 0, 255), -1)

        cv2.imshow('Note Speed', frame)
        cv2.waitKey(0)
        cv2.destroyAllWindows()



    @log_error
    def calculate_oct_direction(self, circle_center_x, circle_center_y, note_x, note_y):
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
                








    # debug
    @log_error
    def preprocess_touch_data(self, final_tracks, track_results_all, predict_results_all, circle_info):
        '''
        使用基于轮廓识别的坐标数据
        过滤scale阶段的数据, 只保留move阶段的数据

        返回格式:
        dict{
            key: (track_id, position),
            value: note path list
            [
                {
                    'frame': frame_num,
                    'x1': x1,
                    'y1': y1,
                    'x2': x2,
                    'y2': y2,
                    'center_x': center_x,
                    'center_y': center_y,
                    'dist': dist_to_center
                },
                ...
            ]
        }
        '''

        circle_center_x, circle_center_y, circle_radius = circle_info
        touch_data = {}

        # read final_tracks
        for track_id, track_data in final_tracks.items():
            if 'path' not in track_data: continue
            track_path = track_data['path']
            if len(track_path) < 10: continue
            class_id = int(track_data['class_id'])
            if class_id != 3: continue # touch

            # classify touch type
            temp_x1 = int(track_path[9]['x1'])
            temp_y1 = int(track_path[9]['y1'])
            temp_x2 = int(track_path[9]['x2'])
            temp_y2 = int(track_path[9]['y2'])
            temp_frame_num = int(track_path[9]['frame'])
            type_name, roi_threshold = self.classify_touch_type(temp_x1, temp_y1, temp_x2, temp_y2, temp_frame_num, track_id)

            for i in range(len(track_path)):

                track_box = track_path[i]
                track_frame_num = int(track_box['frame'])
                track_x1 = int(track_box['x1'])
                track_y1 = int(track_box['y1'])
                track_x2 = int(track_box['x2'])
                track_y2 = int(track_box['y2'])

                # 读取视频帧
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, track_frame_num)
                ret, frame = self.cap.read()
                if not ret:
                    print(f"preprocess_touch_data: [track_id {track_id}] failed to read frame {track_frame_num}")
                    continue
                roi = frame[track_y1-5:track_y2+5, track_x1-5:track_x2+5]
                gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                _, thresh_roi = cv2.threshold(gray_roi, roi_threshold, 255, cv2.THRESH_BINARY)

                # 过滤scale阶段的数据 (仅前6帧)
                if i < 6:
                    is_scale = self.classify_touch_scale(type_name, thresh_roi)
                    if not is_scale: continue
                
                # 计算精确位置
                self.detect_precise_touch(i, roi, thresh_roi, circle_info, track_frame_num, track_id)




    @log_error
    def classify_touch_type(self, x1, y1, x2, y2, frame_num, track_id):

        # 读取视频帧
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
        ret, frame = self.cap.read()
        if not ret:
            print(f"classify_touch_type: [track_id {track_id}] failed to read frame {frame_num}")
            return None, None
        
        roi = frame[y1-5:y2+5, x1-5:x2+5]

        results = self.touch_type_classify_model.predict(source=roi, imgsz=224, conf=0.5, iou=0.5, save=False, verbose=False)
        top1_index = results[0].probs.top1
        result_name = results[0].names[top1_index]
        conf = results[0].probs.top1conf
        if result_name == 'regular':
            threshold = 150
        elif result_name == 'each':
            threshold = 185

        return result_name, threshold
    


    @log_error
    def classify_touch_scale(self, type_name, thresh_roi):

        if type_name == 'regular':
            results = self.touch_scale_classify_regular_model.predict(source=thresh_roi, imgsz=224, conf=0.5, iou=0.5, save=False, verbose=False)
        elif type_name == 'each':
            results = self.touch_scale_classify_each_model.predict(source=thresh_roi, imgsz=224, conf=0.5, iou=0.5, save=False, verbose=False)
        top1_index = results[0].probs.top1
        result_name = results[0].names[top1_index]
        conf = results[0].probs.top1conf

        if result_name == 'false':
            return False
        else:
            return True



    @log_error
    def detect_precise_touch(self, i, roi, thresh_roi, circle_info, frame_num, track_id):

        circle_center_x, circle_center_y, circle_radius = circle_info
        touch_radiu_min = circle_radius * 0.035
        touch_radiu_max = circle_radius * 0.055

        # 轮廓识别
        frame_cx = roi.shape[1] // 2
        frame_cy = roi.shape[0] // 2
        contours, _ = cv2.findContours(thresh_roi, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        if not contours: return None
        for contour in contours:

            # 尺寸合适
            (x, y), radius = cv2.minEnclosingCircle(contour)          
            if radius < touch_radiu_min or radius > touch_radiu_max:
                continue

            # 轮廓是三角形
            epsilon = 0.04 * cv2.arcLength(contour, True) # 逼近精度，值越小，越接近原始轮廓。
            approx = cv2.approxPolyDP(contour, epsilon, True) # 近似多边形
            if len(approx) != 3: continue

            # 轮廓内部是白色
            # 创建掩码
            mask = np.zeros(thresh_roi.shape, dtype=np.uint8)
            cv2.fillPoly(mask, [contour], 255)
            # 轮廓内的像素
            contour_pixels = thresh_roi[mask == 255]
            # 计算白色像素比例
            white_pixels = np.sum(contour_pixels == 255)
            total_pixels = len(contour_pixels)
            white_ratio = white_pixels / total_pixels
            if white_ratio > 0.5: continue
            
            # 方向正确
            # 获取包围圆的上下左右四个点
            up = (int(x), int(y - radius))
            left = (int(x - radius), int(y))
            down = (int(x), int(y + radius))
            right = (int(x + radius), int(y))
            box_points = [up, left, down, right]
            # 计算轮廓的几何中心（centroid）
            M = cv2.moments(contour)
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            # 计算三角形方向 (取离几何中心最近的点)
            distances = [np.linalg.norm(np.array((cx, cy)) - np.array(point)) for point in box_points]
            closest_index = np.argmin(distances)
            orientation = ["up", "left", "down", "right"][closest_index]
            closest_box_point = box_points[closest_index]
            # 排除非法方向
            if orientation == "up":
                if frame_cy - cy > 0: continue
            elif orientation == "left":
                if frame_cx - cx > 0: continue
            elif orientation == "down":
                if frame_cy - cy < 0: continue
            elif orientation == "right":
                if frame_cx - cx < 0: continue

            # Draw contour
            cv2.drawContours(roi, [contour], 0, (0, 255, 0), 2)
            cv2.circle(roi, closest_box_point, 2, (0, 0, 255), 2)
            cv2.circle(roi, (frame_cx, frame_cy), 2, (255, 0, 0), 2)
            cv2.putText(roi, f'{int(radius)}', (int(x), int(y)), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 1)


        # if i < 8:
        #     if roi_threshold == 150:
        #         output_dir = r'C:\Users\ck273\Desktop\touch_scale\天蓋_regular'
        #     else:
        #         output_dir = r'C:\Users\ck273\Desktop\touch_scale\天蓋_each'
        #     if not os.path.exists(output_dir):
        #         os.makedirs(output_dir)
        #     filename = f"天蓋_{track_id}_{frame_num}.jpg"
        #     output_path = os.path.join(output_dir, filename)
        #     if os.path.exists(output_path):
        #         os.remove(output_path)
        #     cv2.imwrite(output_path, thresh_roi)
        
        # return


        # show frame in window
        thresh_roi_bgr = cv2.cvtColor(thresh_roi, cv2.COLOR_GRAY2BGR)
        combined_view = np.hstack((roi, thresh_roi_bgr))
        cv2.imshow(f'ID{track_id}-{frame_num}-{i}', combined_view)
        cv2.waitKey(0)
        cv2.destroyAllWindows()








    @log_error
    def get_touch_DefaultMsec(self, detected_touch_DefaultMsec):

        def get_standard_touch_DefaultMsec(ui_speed):
            # 游戏源码实现
            option_touchspeed_dict = {
                1.00: 175.0, 1.25: 183.0, 1.50: 200.0, 1.75: 212.0,
                2.00: 225.0, 2.25: 237.0, 2.50: 250.0, 2.75: 262.0,
                3.00: 275.0, 3.25: 283.0, 3.50: 300.0, 3.75: 312.0,
                4.00: 325.0, 4.25: 337.0, 4.50: 350.0, 4.75: 375.0,
                5.00: 400.0, 5.25: 425.0, 5.50: 450.0, 5.75: 475.0,
                6.00: 500.0, 6.25: 525.0, 6.50: 550.0, 6.75: 575.0,
                7.00: 600.0, 7.25: 625.0, 7.50: 650.0, 7.75: 675.0,
                8.00: 700.0, 8.25: 725.0, 8.50: 750.0, 8.75: 775.0,
                9.00: 800.0, 9.25: 825.0, 9.50: 850.0, 9.75: 875.0,
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


    





    # debug
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
            self.touch_areas = state['touch_areas']
            self.cap = cv2.VideoCapture(std_video)

            touch_type_classify_model_path = r"D:\git\mai-chart-analyse\yolo-train\runs\classify\touch_type_classify\weights\best.pt"
            if not os.path.exists(touch_type_classify_model_path):
                raise FileNotFoundError(f"Touch type classify model not found: {touch_type_classify_model_path}")
            self.touch_type_classify_model = YOLO(touch_type_classify_model_path)

            touch_scale_classify_regular_model_path = r"D:\git\mai-chart-analyse\yolo-train\runs\classify\touch_scale_classify_regular\weights\best.pt"
            if not os.path.exists(touch_scale_classify_regular_model_path):
                raise FileNotFoundError(f"Touch scale classify regular model not found: {touch_scale_classify_regular_model_path}")
            self.touch_scale_classify_regular_model = YOLO(touch_scale_classify_regular_model_path)

            touch_scale_classify_each_model_path = r"D:\git\mai-chart-analyse\yolo-train\runs\classify\touch_scale_classify_each\weights\best.pt"
            if not os.path.exists(touch_scale_classify_each_model_path):
                raise FileNotFoundError(f"Touch scale classify each model not found: {touch_scale_classify_each_model_path}")
            self.touch_scale_classify_each_model = YOLO(touch_scale_classify_each_model_path)

            
            # Load detection data
            final_tracks, track_results_all, predict_results_all, metadata = self.load_detection_data(output_dir, video_name)

            tap_data = self.preprocess_tap_data(final_tracks, track_results_all, predict_results_all, circle_info)
            self.note_DefaultMsec, self.note_OptionNotespeed = self.estimate_note_DefaultMsec(tap_data, circle_info, fps)
            tap_info = self.analyze_tap_reach_time(tap_data, circle_info, fps, bpm)

            self.preprocess_touch_data(final_tracks, track_results_all, predict_results_all, circle_info)



        except Exception as e:
            raise Exception(f"Error in NoteAnalyzer: {e}")
        finally:
            if self.cap is not None:
                self.cap.release()
        


   
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


    touch_areas = {
        'C1': {'center': ((539, 541))},
        'B1': {'center': ((624, 336))},
        'B2': {'center': ((745, 456))},
        'B3': {'center': ((744, 626))},
        'B4': {'center': ((624, 745))},
        'B5': {'center': ((455, 745))},
        'B6': {'center': ((335, 626))},
        'B7': {'center': ((335, 456))},
        'B8': {'center': ((454, 336))},
        'E1': {'center': ((540, 229))},
        'E2': {'center': ((760, 320))},
        'E3': {'center': ((852, 540))},
        'E4': {'center': ((760, 761))},
        'E5': {'center': ((539, 853))},
        'E6': {'center': ((319, 760))},
        'E7': {'center': ((228, 540))},
        'E8': {'center': ((319, 321))},
        'A1': {'center': ((693, 171))},
        'A2': {'center': ((909, 388))},
        'A3': {'center': ((908, 693))},
        'A4': {'center': ((692, 910))},
        'A5': {'center': ((387, 909))},
        'A6': {'center': ((170, 694))},
        'A7': {'center': ((170, 388))},
        'A8': {'center': ((386, 170))},
        'D1': {'center': ((540, 117))},
        'D2': {'center': ((840, 241))},
        'D3': {'center': ((963, 542))},
        'D4': {'center': ((839, 840))},
        'D5': {'center': ((540, 964))},
        'D6': {'center': ((241, 840))},
        'D7': {'center': ((116, 540))},
        'D8': {'center': ((239, 241))}
    }

    
    id = '6.00'
    state1 = {
        'video_name': f'test_{id}',
        'detect_video_path': rf"D:\git\mai-chart-analyse\yolo-train\runs\detect\test_{id}\test_{id}_tracked.mp4",
        'std_video_path': rf"D:\git\mai-chart-analyse\yolo-train\runs\detect\test_{id}\test_{id}_standardlized.mp4",
        'debug': True,
        'video_fps': 60,
        'bpm': 170, # test
        'touch_areas': touch_areas,
    }
    

    state2 = {
        'video_name': '踊',
        'detect_video_path': r"D:\git\mai-chart-analyse\yolo-train\runs\detect\踊\踊_tracked.mp4",
        'std_video_path': r"D:\git\mai-chart-analyse\yolo-train\runs\detect\踊\踊_standardlized.mp4",
        'debug': True,
        'video_fps': 60,
        'bpm': 128, # 踊
        'touch_areas': touch_areas,
    }

    state3 = {
        'video_name': '[maimai谱面确认] 天蓋 MASTER-p01-116',
        'detect_video_path': r"D:\git\mai-chart-analyse\yolo-train\runs\detect\[maimai谱面确认] 天蓋 MASTER-p01-116\[maimai谱面确认] 天蓋 MASTER-p01-116_tracked.mp4",
        'std_video_path': r"D:\git\mai-chart-analyse\yolo-train\runs\detect\[maimai谱面确认] 天蓋 MASTER-p01-116\[maimai谱面确认] 天蓋 MASTER-p01-116_standardlized.mp4",
        'debug': True,
        'video_fps': 60,
        'bpm': 178, # 天蓋
        'touch_areas': touch_areas,
    }

    analyzer.process(state3)
