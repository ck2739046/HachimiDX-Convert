import json
import os
import cv2
import numpy as np
import math
import functools
import traceback
from ultralytics import YOLO
import time
from math import dist, gcd

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
        tap_data = {}
        counter = 0

        close_tolerance = circle_radius * 0.05
        start_tolerance = circle_radius * 0.02
        dist_start = circle_radius * 0.25
        dist_end = circle_radius

        # read final_tracks
        for track_id, track_data in final_tracks.items():
            if 'path' not in track_data: continue
            track_path = track_data['path']
            if len(track_path) < 5: continue
            class_id = round(track_data['class_id'])
            if class_id != 2: continue # tap

            predict_track_path = []

            for track_box in track_path:
                track_frame_num = round(track_box['frame'])
                track_conf = float(track_box['conf'])
                track_x1 = round(track_box['x1'])
                track_y1 = round(track_box['y1'])
                track_x2 = round(track_box['x2'])
                track_y2 = round(track_box['y2'])
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
                    predict_class_id = round(predict_result['class'])
                    if predict_class_id != class_id: continue
                    # 判断 中心距离
                    box = predict_result['box']
                    predict_x1 = round(box['x1'])
                    predict_y1 = round(box['y1'])
                    predict_x2 = round(box['x2'])
                    predict_y2 = round(box['y2'])
                    predict_center_x = (predict_x1 + predict_x2) / 2
                    predict_center_y = (predict_y1 + predict_y2) / 2
                    if abs(track_center_x - predict_center_x) > close_tolerance or \
                        abs(track_center_y - predict_center_y) > close_tolerance: continue 
                    # 计算距离圆心的距离
                    dist_to_center = np.sqrt(((predict_center_x - circle_center_x)**2 + (predict_center_y - circle_center_y)**2))                   
                    # 计算方向(1-8)
                    position = self.calculate_oct_position(circle_center_x, circle_center_y, predict_center_x, predict_center_y)
                    # 添加到匹配列表
                    match_found.append((track_frame_num,
                                        predict_x1,
                                        predict_y1,
                                        predict_x2,
                                        predict_y2,
                                        predict_center_x,
                                        predict_center_y,
                                        position,
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
            # 检验方位
            positions = [x[7] for x in predict_track_path]
            if len(set(positions)) != 1:
                print(f"preprocess_tap_data: positions not consistent for track_id {track_id}")
                continue
            # 添加到tap_data
            path = []
            for frame_num, x1, y1, x2, y2, center_x, center_y, position, dist_to_center in predict_track_path:
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
            tap_data[(track_id, positions[0])] = path

            counter += 1
            print(f"preprocessing tap data...{counter}", end='\r')

            #self.draw_path_on_frame(track_id, path[0]['frame']+3, path, circle_info)

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

        for (track_id, position), path in tap_data.items():
            frame_num_start = path[0]['frame']
            frame_num_end = path[-1]['frame']
            dist_start = path[0]['dist']
            dist_end = path[-1]['dist']

            frame_num_diff = frame_num_end - frame_num_start
            total_dist = dist_end - dist_start
            note_speed = total_dist / frame_num_diff # pixel/frame
            note_speeds.append(note_speed)

            #self.draw_path_on_frame(track_id, frame_num_start, path, circle_info)

        length = len(note_speeds)
        mean = np.mean(note_speeds)
        min = np.min(note_speeds)
        max = np.max(note_speeds)
        median = np.median(note_speeds)
        std_dev = np.std(note_speeds)
        std_dev_percent = std_dev / mean * 100
        print(f"note speed {length}: [Mean {mean:.3f}], Min {min:.3f}, Max {max:.3f}, Median {median:.3f}, Std Dev {std_dev_percent:.3f}%")

        note_DefaultMsec, note_OptionNotespeed = self.get_note_DefaultMsec(mean, fps, circle_info[2])
        return note_DefaultMsec, note_OptionNotespeed
    


    @log_error
    def analyze_tap_reach_time(self, tap_data, circle_info, fps):

        tap_info = {}
        for (track_id, direction), path in tap_data.items():
            # 平均所有轨迹的到达时间
            times = []
            for point in path:
                frame_num = point['frame']
                dist = point['dist']
                reach_end_Msec = self.predict_note_reach_end_time(dist, frame_num, circle_info[2], fps)
                times.append(reach_end_Msec)
            mean = np.mean(times)
            tap_info[(track_id, direction)] = mean

        return tap_info


    @log_error
    def predict_note_reach_end_time(self, cur_dist, cur_frame, circle_radius, fps):
        '''
        正向:
        [dist_offset] = -1/120 * 总距离 * (OptionNotespeed/150f -1)
        [time_offset] = (OptionNotespeed/150f -1) * (-0.5 / (OptionNotespeed/150f -1)) * 1.6 * 1000 / 60
        高速的dist和time偏移都是负值 (实测后取消应用 time_offset)

        时间进度 = (current_Msec - leave_start_Msec + time_offset) / [DefaultMsec]
        travelled_dist = 时间进度 * [total_dist]
        current_dist = [startPos] + travelled_dist + [dist_offset]

        逆向:
        已知 current_dist, [dist_offset], [startPos]
        -> travelled_dist = current_dist - startPos - dist_offset
        已知 travelled_dist, [total_dist]
        -> 时间进度 = travelled_dist / total_dist
        已知 时间进度, [DefaultMsec], current_Msec, [time_offset]
        -> leave_start_Msec = current_Msec - 时间进度 * DefaultMsec + time_offset
        -> reach_end_Msec = leave_start_Msec + DefaultMsec
        '''

        cur_time = cur_frame / fps * 1000 # 转换为毫秒
        total_dist = circle_radius * 0.75
        dist_offset = -1/120 * total_dist * (self.note_OptionNotespeed / 150 - 1)
        #time_offset = (self.note_OptionNotespeed / 150 - 1) * (-0.5 / (self.note_OptionNotespeed / 150 - 1)) * 1.6 * 1000 / 60
        start_pos = circle_radius * 0.25

        travelled_dist = cur_dist - start_pos - dist_offset
        time_progress = travelled_dist / total_dist
        leave_start_Msec = cur_time - time_progress * self.note_DefaultMsec # + time_offset
        reached_end_Msec = leave_start_Msec + self.note_DefaultMsec

        return reached_end_Msec



    @log_error
    def get_note_DefaultMsec(self, detected_note_speed, fps, circle_radius):

        def get_standard_note_DefaultMsec(ui_speed):
            # 游戏源码实现
            OptionNotespeed = round(ui_speed * 100 + 100) # 6.25 = 725
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
        cv2.circle(frame, (round(circle_center_x), round(circle_center_y)), round(circle_radius*0.25), (0, 255, 0), 2)

        for point in path:
            frame_num = point['frame']
            center_x = point['center_x']
            center_y = point['center_y']
            cv2.circle(frame, (round(center_x), round(center_y)), 3, (0, 0, 255), -1)

        # Resize and show frame
        resized_frame = cv2.resize(frame, None, fx=0.8, fy=0.8, interpolation=cv2.INTER_AREA)
        window_name = f'Tap ID: {track_id}'
        cv2.namedWindow(window_name)
        cv2.moveWindow(window_name, 500, 80)
        cv2.imshow(window_name, resized_frame)
        cv2.waitKey(0)
        cv2.destroyAllWindows()



    @log_error
    def calculate_oct_position(self, circle_center_x, circle_center_y, note_x, note_y):
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
        counter = 0

        # read final_tracks
        for track_id, track_data in final_tracks.items():
            if 'path' not in track_data: continue
            track_path = track_data['path']
            if len(track_path) < 10: continue
            class_id = round(track_data['class_id'])
            if class_id != 3: continue # touch

            # classify touch type
            temp_x1 = round(track_path[9]['x1'])
            temp_y1 = round(track_path[9]['y1'])
            temp_x2 = round(track_path[9]['x2'])
            temp_y2 = round(track_path[9]['y2'])
            temp_frame_num = round(track_path[9]['frame'])
            type_name, roi_threshold = self.classify_touch_type(temp_x1, temp_y1, temp_x2, temp_y2, temp_frame_num, track_id)

            path = []

            for i in range(len(track_path)):

                track_box = track_path[i]
                track_frame_num = round(track_box['frame'])
                track_x1 = round(track_box['x1'])
                track_y1 = round(track_box['y1'])
                track_x2 = round(track_box['x2'])
                track_y2 = round(track_box['y2'])

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
                x1, y1, x2, y2, cx, cy, dist = self.detect_precise_touch(i, roi, thresh_roi, circle_info, track_frame_num, track_id)
                if x1 is None or y1 is None or x2 is None or y2 is None or cx is None or cy is None or dist is None:
                    print(f"preprocess_touch_data: [track_id {track_id}] fail to detect precise touch at frame {track_frame_num}")
                    continue
                
                # 转换为frame坐标
                x1 = round(x1 + track_x1 - 5)
                y1 = round(y1 + track_y1 - 5)
                x2 = round(x2 + track_x1 - 5)
                y2 = round(y2 + track_y1 - 5)
                cx = round(cx + track_x1 - 5)
                cy = round(cy + track_y1 - 5)

                # 计算方位
                position = self.calculate_all_position(cx, cy)

                # 添加轨迹点
                path.append((track_frame_num, x1, y1, x2, y2, cx, cy, position, dist))


            if not path:
                print(f"preprocess_touch_data: path not found for track_id {track_id}")
                continue
            path.sort(key=lambda x: x[0]) # 按frame排序
            # 检验长度
            if len(path) < 5:
                print(f"preprocess_tap_data: path too short for track_id {track_id}, length: {len(path)}")
                continue
            # 检验方位
            positions = [x[7] for x in path]
            if len(set(positions)) != 1:
                print(f"preprocess_tap_data: positions not consistent for track_id {track_id}")
                continue
            # 添加到touch_data
            final_path = []
            for frame_num, x1, y1, x2, y2, center_x, center_y, position, dist_to_center in path:
                final_path.append({
                    'frame': frame_num,
                    'x1': x1,
                    'y1': y1,
                    'x2': x2,
                    'y2': y2,
                    'center_x': center_x,
                    'center_y': center_y,
                    'dist': dist_to_center
                })
            touch_data[(track_id, positions[0])] = final_path

            counter += 1
            print(f"preprocessing touch data...{counter}", end='\r')

        if not touch_data:
            print("preprocess_touch_data: no touch data")
            return {}
        
        return touch_data



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
        touch_radius_min = circle_radius * 0.035
        touch_radius_max = circle_radius * 0.055
        center_dot_min = circle_radius * 0.02
        center_dot_max = circle_radius * 0.04
        None_result = (None, None, None, None, None, None, None)

        # 寻找中心点
        note_cx = 0
        note_cy = 0
        roi_cx = (roi.shape[1] - 1) / 2
        roi_cy = (roi.shape[0] - 1) / 2
        gray_dot_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        _, thresh_dot_roi = cv2.threshold(gray_dot_roi, 160, 255, cv2.THRESH_BINARY)
        # 轮廓识别
        contours, _ = cv2.findContours(thresh_dot_roi, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        if not contours: return None_result
        for contour in contours:
            (x, y), radius = cv2.minEnclosingCircle(contour)         
            # 尺寸合适 
            if radius < center_dot_min or radius > center_dot_max: continue
            # 验证轮廓圆形度 (0.8)
            area = cv2.contourArea(contour)
            circle_area = 3.14 * radius * radius + 1e-6 # 避免除0错误
            circularity = area / circle_area
            if circularity < 0.8: continue
            # 验证是否在中心附近
            if abs(x - roi_cx) > center_dot_max or abs(y - roi_cy) > center_dot_max: continue
            # 视为合法结果
            note_cx = x
            note_cy = y

        if note_cx == 0 or note_cy == 0:
            print(f"detect_precise_touch: [track_id {track_id}] no valid center point at frame {frame_num}")
            return None_result


        valid_points = {}
        # 轮廓识别
        contours, _ = cv2.findContours(thresh_roi, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        if not contours: return None_result
        for contour in contours:

            # 尺寸合适
            (x, y), radius = cv2.minEnclosingCircle(contour)          
            if radius < touch_radius_min or radius > touch_radius_max:
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
            up = (x, y - radius)
            left = (x - radius, y)
            down = (x, y + radius)
            right = (x + radius, y)
            box_points = [up, left, down, right]
            # 计算轮廓的几何中心（centroid）
            M = cv2.moments(contour)
            cx = M["m10"] / M["m00"]
            cy = M["m01"] / M["m00"]
            # 计算三角形方向 (取离几何中心最近的点)
            distances = [np.linalg.norm(np.array((cx, cy)) - np.array(point)) for point in box_points]
            closest_index = np.argmin(distances)
            orientation = ["up", "left", "down", "right"][closest_index]
            closest_box_point = box_points[closest_index]
            # 排除非法方向
            if orientation == "up":
                if note_cy - cy > 0: continue
            elif orientation == "left":
                if note_cx - cx > 0: continue
            elif orientation == "down":
                if note_cy - cy < 0: continue
            elif orientation == "right":
                if note_cx - cx < 0: continue
            # 计算cloest_box_point到音符中心的距离
            dist = np.sqrt(((closest_box_point[0] - note_cx) ** 2 + (closest_box_point[1] - note_cy) ** 2))
            # 保存结果 
            if orientation not in valid_points.keys():
                valid_points[orientation] = (radius, dist, closest_box_point, contour, round(x), round(y))
            else:
                # 如果同方向已存在，取半径较小的
                existing_radius = valid_points[orientation][0]
                if radius < existing_radius:
                    valid_points[orientation] = (radius, dist)


        # 计算精准的尺寸
        dists = [value[1] for value in valid_points.values()]
        if len(dists) <= 1:
            print(f"detect_precise_touch: [track_id {track_id}] not enough valid points at frame {frame_num}")

            # show frame
            thresh_roi_bgr = cv2.cvtColor(thresh_roi, cv2.COLOR_GRAY2BGR)
            combined_view = np.hstack((roi, thresh_roi_bgr))
            window_name = f'ID{track_id}-{frame_num}-{i}'
            cv2.namedWindow(window_name)
            cv2.moveWindow(window_name, 500, 500)
            time.sleep(0.005)
            cv2.imshow(window_name, combined_view)
            cv2.waitKey(0)
            cv2.destroyAllWindows()

            return None_result
        

        # 转换为外框尺寸 ( offset = 0.08 * radius )
        avg_dist = np.mean(dists)
        touch_outer = circle_radius * 0.08
        precise_x1 = note_cx - avg_dist - touch_outer
        precise_y1 = note_cy - avg_dist - touch_outer
        precise_x2 = note_cx + avg_dist + touch_outer
        precise_y2 = note_cy + avg_dist + touch_outer


        # cv2.rectangle(roi, (round(precise_x1), round(precise_y1)), (round(precise_x2), round(precise_y2)), (0, 255, 0), 2)
        # cv2.circle(roi, (round(note_cx), round(note_cy)), 3, (255, 0, 0), 2)
        # # draw contour
        # for radius, dist, closest_box_point, contour, x, y in valid_points.values():
        #     cv2.drawContours(roi, [contour], 0, (0, 255, 0), 2)
        #     cv2.circle(roi, (round(closest_box_point[0]), round(closest_box_point[1])), 2, (0, 0, 255), 2)
        #     cv2.putText(roi, f'{round(radius)}', (round(x), round(y)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 1)
        # # show window
        # thresh_roi_bgr = cv2.cvtColor(thresh_roi, cv2.COLOR_GRAY2BGR)
        # combined_view = np.hstack((roi, thresh_roi_bgr))
        # window_name = f'ID{track_id}-{frame_num}-{i}'
        # cv2.namedWindow(window_name)
        # cv2.moveWindow(window_name, 500, 500)
        # time.sleep(0.005)
        # cv2.imshow(window_name, combined_view)
        # cv2.waitKey(0)
        # cv2.destroyAllWindows()


        # if roi_threshold == 150:
        #     output_dir = r'C:\Users\ck273\Desktop\touch_scale\天蓋_regular'
        # else:
        #     output_dir = r'C:\Users\ck273\Desktop\touch_scale\天蓋_each'
        # if not os.path.exists(output_dir):
        #     os.makedirs(output_dir)
        # filename = f"天蓋_{track_id}_{frame_num}.jpg"
        # output_path = os.path.join(output_dir, filename)
        # if os.path.exists(output_path):
        #     os.remove(output_path)
        # cv2.imwrite(output_path, thresh_roi)

        return (precise_x1, precise_y1, precise_x2, precise_y2, note_cx, note_cy, avg_dist)
    


    @log_error
    def calculate_all_position(self, note_x, note_y):
        
        closeset_label = None
        closeset_dist = 999

        for label, data in self.touch_areas.items():
            (cx, cy) = data['center']
            dist = np.sqrt(((note_x - cx) ** 2 + (note_y - cy) ** 2))
            if dist < closeset_dist:
                closeset_label = label
                closeset_dist = dist
        
        return closeset_label
    


    @log_error
    def estimate_touch_DefaultMsec(self, touch_data, circle_info, fps):
        '''
        正向：
        根据 time_progress = (current_time - move_start_time) / DefaultMsec 获得 time_progress
        应用缓动函数, location_progress = 缓动函数(time_progress)
        根据 location_progress 决定4个三角距离中心点的距离
        current_Dist = total_Dist * (1 - location_progress) 纯线性的

        逆向：
        反推 location_progress = 1 - current_Dist / total_Dist
        二分法, 通过location_progress反推出time_progress ( y -> x )
        反推 DefaultMsec = (current_time - move_start_time) / time_progress

        方案:
        已知 current_dist, current_time, 求解 DefaultMsec, move_start_time
        通过dump游戏得知total_Dist = 34 (对于标准1920x1080屏幕)
        DispAdjustFlame: 0 (时间微调参数没有影响, 可以忽略)
        DefaultCorlsPos Values: [(0.0, 34.0, -1.0), (0.0, -34.0, -1.0), (34.0, 0.0, 0.0), (-34.0, 0.0, 0.0)]

        首先反推出每个点的time_progress, (只保留location_progress 0.15-0.85)
        选择缓动函数斜率较大的区间，因为这些区间对时间变化更敏感
        选两个点相减消除未知的move_start_time常量
        -> DefaultMsec = (current_time1 - current_time2) / (time_progress1 - time_progress2)

        计算多个数据点对的 DefaultMsec 然后取平均值
        '''

        def reverse_function(y, tolerance=0.000001):
            # 二分查找求解 y = 3.5x⁴ - 3.75x³ + 1.45x² - 0.05x + 0.0005 的反函数
            low, high = 0.0, 1.0
            
            while high - low > tolerance:
                mid = (low + high) / 2
                eased_y = 3.5 * mid**4 - 3.75 * mid**3 + 1.45 * mid**2 - 0.05 * mid + 0.0005
                
                if abs(eased_y - y) < tolerance:
                    return mid
                elif eased_y < y:
                    low = mid  # 二分查找更新
                else:
                    high = mid
            return (low + high) / 2


        DefaultMsecs = []
        dist_min = 17.5
        #dist_max = 51.5
        total_dist = 34
        for (track_id, position), path in touch_data.items():

            # 过滤掉斜率较小的轨迹点
            big_slope_points = []
            for point in path:
                # 反推 location_progress
                dist = point['dist']
                cur_dist = dist - dist_min if dist >= dist_min else 0
                location_progress = 1 - cur_dist / total_dist
                if location_progress < 0.15 or location_progress > 0.85:
                    continue
                # 反推 time_progress
                time_progress = reverse_function(location_progress)
                # 加入列表
                cur_time = point['frame'] / fps * 1000 # 转换为毫秒
                big_slope_points.append((cur_time, time_progress))

            if len(big_slope_points) < 4:
                print(f"estimate_touch_DefaultMsec: [track_id {track_id}] not enough big slope points, length: {len(big_slope_points)}")
                continue

            # 轨迹点配对并计算 DefaultMsec
            big_slope_points.sort(key=lambda x: x[1]) # 按 time_progress 排序
            for i in range(len(big_slope_points)):
                for j in range(i + 1, len(big_slope_points)):
                    time1, progress1 = big_slope_points[i]
                    time2, progress2 = big_slope_points[j]
                    if abs(progress1 - progress2) < 0.2:
                        continue # 忽略相近的 progress 减少误差 (2%) 
                    default_msec_estimate = abs(time1 - time2) / abs(progress1 - progress2)
                    DefaultMsecs.append(default_msec_estimate)


        if not DefaultMsecs:
            print("estimate_touch_DefaultMsec: no valid touch data")
            return 0, 0
        
        length = len(DefaultMsecs)
        mean = np.mean(DefaultMsecs)
        min = np.min(DefaultMsecs)
        max = np.max(DefaultMsecs)
        median = np.median(DefaultMsecs)
        std_dev = np.std(DefaultMsecs)
        std_dev_percent = std_dev / median * 100
        print(f"touch DefaultMsec {length}: [Median {median:.3f}], Min {min:.3f}, Max {max:.3f}, Mean {mean:.3f}, Std Dev {std_dev_percent:.3f}%")

        touch_DefaultMsec, touch_OptionNotespeed = self.get_touch_DefaultMsec(median)
        return touch_DefaultMsec, touch_OptionNotespeed
    


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
            return DefaultMsec, OptionNotespeed
        
        # 查找最接近的 DefaultMsec
        cloest_DefaultMsec = 0
        cloest_i = 0
        cloest_OptionNotespeed = 0
        i = 1
        while i <= 10:

            DefaultMsec, OptionNotespeed = get_standard_touch_DefaultMsec(i)

            if abs(DefaultMsec - detected_touch_DefaultMsec) < abs(cloest_DefaultMsec - detected_touch_DefaultMsec):
                cloest_DefaultMsec = DefaultMsec
                cloest_i = i
                cloest_OptionNotespeed = OptionNotespeed
            i += 0.25

        print(f"estimate touch speed: {cloest_i:.2f} - {cloest_DefaultMsec:.3f}ms (detect {detected_touch_DefaultMsec:.3f}ms)")

        return cloest_DefaultMsec, cloest_OptionNotespeed
    


    @log_error
    def analyze_touch_reach_time(self, touch_data, fps):

        touch_info = {}
        for (track_id, position), path in touch_data.items():
            # 平均所有轨迹的到达时间
            times = []
            for point in path:
                frame_num = point['frame']
                dist = point['dist']
                reach_end_Msec = self.predict_touch_reach_end_time(dist, frame_num, fps)
                if reach_end_Msec != 0:
                    times.append(reach_end_Msec)
                    
            mean = np.mean(times)
            touch_info[(track_id, position)] = mean

        return touch_info
    


    @log_error
    def predict_touch_reach_end_time(self, dist, cur_frame, fps):
        '''
        正向：
        根据 time_progress = (current_time - move_start_time) / DefaultMsec 获得 time_progress
        应用缓动函数, location_progress = 缓动函数(time_progress)
        根据 location_progress 决定4个三角距离中心点的距离
        current_Dist = total_Dist * (1 - location_progress) 纯线性的

        逆向：
        反推 location_progress = 1 - current_Dist / total_Dist
        二分法, 通过location_progress反推出time_progress ( y -> x )
        反推 move_start_time = current_time - time_progress * DefaultMsec
        '''

        def reverse_function(y, tolerance=0.000001):
            # 二分查找求解 y = 3.5x⁴ - 3.75x³ + 1.45x² - 0.05x + 0.0005 的反函数
            low, high = 0.0, 1.0
            
            while high - low > tolerance:
                mid = (low + high) / 2
                eased_y = 3.5 * mid**4 - 3.75 * mid**3 + 1.45 * mid**2 - 0.05 * mid + 0.0005
                
                if abs(eased_y - y) < tolerance:
                    return mid
                elif eased_y < y:
                    low = mid  # 二分查找更新
                else:
                    high = mid
            return (low + high) / 2


        # 反推 location_progress
        cur_dist = dist - 17.5 if dist >= 17.5 else 0
        total_dist = 34
        location_progress = 1 - cur_dist / total_dist
        if location_progress < 0.15 or location_progress > 0.85:
            return 0
        # 反推 time_progress
        time_progress = reverse_function(location_progress)
        # 反推 move_start_time
        cur_time = cur_frame / fps * 1000  # 转换为毫秒
        move_start_time = cur_time - time_progress * self.touch_DefaultMsec
        reach_end_time = move_start_time + self.touch_DefaultMsec

        return reach_end_time
    



    # debug
    @log_error
    def preprocess_hold_data(self, final_tracks, track_results_all, predict_results_all, circle_info):
        '''
        坐标使用predict_results_all的数据
        过滤scale阶段的数据, 只保留move阶段的数据

        返回格式:
        dict{
            key: (track_id, position),
            value: two note path list (前半/后半)
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
            ],
            ...
        }
        '''

        def split_dist(frame_num, x1, y1, x2, y2, tan_22_5, long, short, circle_info, position):

            circle_center_x, circle_center_y, circle_radius = circle_info
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2
            height = abs(y2 - y1)
            width = abs(x2 - x1)

            # 正方形
            if abs(width - height) < circle_radius * 0.02:
                dist_to_center = np.sqrt(((cx - circle_center_x) ** 2 + (cy - circle_center_y) ** 2))
                return dist_to_center, dist_to_center

            if width > height:
                # 横向长方形 (2/3/6/7)
                x_offset = abs(cx - x1) - short
                y_offset = abs(cy - y1) - long
                x_offset_baseY = y_offset / tan_22_5
                y_offset_baseX = x_offset * tan_22_5
                final_x_offset = (x_offset + x_offset_baseY) / 2
                final_y_offset = (y_offset + y_offset_baseX) / 2
            else:
                # 纵向长方形 (1/4/5/8)
                x_offset = abs(cx - x1) - long
                y_offset = abs(cy - y1) - short
                x_offset_baseY = y_offset * tan_22_5
                y_offset_baseX = x_offset / tan_22_5
                final_x_offset = (x_offset + x_offset_baseY) / 2
                final_y_offset = (y_offset + y_offset_baseX) / 2

            if position == 1 or position == 2:
                tail_x = cx - final_x_offset
                tail_y = cy + final_y_offset
                head_x = cx + final_x_offset
                head_y = cy - final_y_offset
            elif position == 3 or position == 4:
                tail_x = cx - final_x_offset
                tail_y = cy - final_y_offset
                head_x = cx + final_x_offset
                head_y = cy + final_y_offset
            elif position == 5 or position == 6:
                tail_x = cx + final_x_offset
                tail_y = cy - final_y_offset
                head_x = cx - final_x_offset
                head_y = cy + final_y_offset
            elif position == 7 or position == 8:
                tail_x = cx + final_x_offset
                tail_y = cy + final_y_offset
                head_x = cx - final_x_offset
                head_y = cy - final_y_offset

            # # 读取帧
            # self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
            # ret, frame = self.cap.read()
            # # 绘制点
            # cv2.circle(frame, (round(cx), round(cy)), 2, (255, 0, 0), 2)
            # cv2.circle(frame, (round(tail_x), round(tail_y)), 2, (0, 255, 0), 2)
            # cv2.circle(frame, (round(head_x), round(head_y)), 2, (0, 0, 255), 2)
            # # 显示窗口
            # window_name = f'ID{track_id}-{frame_num}'
            # cv2.namedWindow(window_name)
            # cv2.moveWindow(window_name, 500, 50)
            # time.sleep(0.005)
            # cv2.imshow(window_name, frame)
            # cv2.waitKey(0)
            # cv2.destroyAllWindows()

            dist_head = np.sqrt(((head_x - circle_center_x) ** 2 + (head_y - circle_center_y) ** 2))
            dist_tail = np.sqrt(((tail_x - circle_center_x) ** 2 + (tail_y - circle_center_y) ** 2))
            return dist_head, dist_tail
        


        circle_center_x, circle_center_y, circle_radius = circle_info
        hold_data = {}
        counter = 0

        close_tolerance = circle_radius * 0.05
        start_tolerance = circle_radius * 0.02
        mid_tolerance = circle_radius * 0.015
        dist_start = circle_radius * 0.25
        dist_end = circle_radius
        dist_mid = circle_radius * (0.25 + 0.75/2)
        radian = math.radians(47.02034)
        base_dist = circle_radius * 0.18
        short = round(math.cos(radian) * base_dist)
        long = round(math.sin(radian) * base_dist)
        radian_22_5 = math.radians(22.5)
        tan_22_5 = math.tan(radian_22_5)

        # read final_tracks
        for track_id, track_data in final_tracks.items():
            if 'path' not in track_data: continue
            track_path = track_data['path']
            if len(track_path) < 5: continue
            class_id = round(track_data['class_id'])
            if class_id != 0: continue # hold

            predict_track_path = []

            for track_box in track_path:
                track_frame_num = round(track_box['frame'])
                track_conf = float(track_box['conf'])
                track_x1 = round(track_box['x1'])
                track_y1 = round(track_box['y1'])
                track_x2 = round(track_box['x2'])
                track_y2 = round(track_box['y2'])
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
                    predict_class_id = round(predict_result['class'])
                    if predict_class_id != class_id: continue
                    # 判断 中心距离
                    box = predict_result['box']
                    predict_x1 = round(box['x1'])
                    predict_y1 = round(box['y1'])
                    predict_x2 = round(box['x2'])
                    predict_y2 = round(box['y2'])
                    predict_center_x = (predict_x1 + predict_x2) / 2
                    predict_center_y = (predict_y1 + predict_y2) / 2
                    if abs(track_center_x - predict_center_x) > close_tolerance or \
                        abs(track_center_y - predict_center_y) > close_tolerance: continue 
                    # 计算距离圆心的距离
                    dist_to_center = np.sqrt(((predict_center_x - circle_center_x)**2 + (predict_center_y - circle_center_y)**2))                   
                    # 计算方向(1-8)
                    position = self.calculate_oct_position(circle_center_x, circle_center_y, predict_center_x, predict_center_y)
                    # 添加到匹配列表
                    match_found.append((track_frame_num,
                                        predict_x1,
                                        predict_y1,
                                        predict_x2,
                                        predict_y2,
                                        predict_center_x,
                                        predict_center_y,
                                        position,
                                        dist_to_center))


                if not match_found:
                    print(f"preprocess_hold_data: no match found for track_id {track_id} at frame {track_frame_num}")
                    continue
                elif len(match_found) > 1:
                    print(f"preprocess_hold_data: multiple matches found for track_id {track_id} at frame {track_frame_num}")
                    match_found.sort(key=lambda x: x[-1]) # 按距离排序

                # 过滤 scale 阶段的数据
                dist_to_center = match_found[0][-1]
                if abs(dist_to_center - dist_start) < start_tolerance:
                    continue # 掐头
                elif dist_to_center > dist_end:
                    continue # 去尾

                # 过滤 mid 阶段的数据
                if abs(dist_to_center - dist_mid) < mid_tolerance:
                    continue

                predict_track_path.append(match_found[0])

            
            if not predict_track_path:
                print(f"preprocess_hold_data: predict_track_path not found for track_id {track_id}")
                continue
            predict_track_path.sort(key=lambda x: x[0]) # 按frame排序
            # 检验长度
            if len(predict_track_path) < 5:
                print(f"preprocess_hold_data: predict_track_path too short for track_id {track_id}, length: {len(predict_track_path)}")
                continue
            # 检验方位
            positions = [x[7] for x in predict_track_path]
            if len(set(positions)) != 1:
                print(f"preprocess_hold_data: positions not consistent for track_id {track_id}")
                continue
            # 添加到hold_data
            path1 = [] # 前半
            path2 = [] # 后半
            for frame_num, x1, y1, x2, y2, center_x, center_y, position, dist_to_center in predict_track_path:

                path = path1 if dist_to_center < dist_mid else path2
                dist_head, dist_tail = split_dist(frame_num, x1, y1, x2, y2, tan_22_5, long, short, circle_info, position)
                dist = dist_head if dist_to_center < dist_mid else dist_tail

                path.append({
                    'frame': frame_num,
                    'x1': x1,
                    'y1': y1,
                    'x2': x2,
                    'y2': y2,
                    'center_x': center_x,
                    'center_y': center_y,
                    'dist': dist
                })
            
            if len(path1) < 5 or len(path2) < 5:
                print(f"preprocess_hold_data: path1 or path2 too short for track_id {track_id}, length: {len(path1)}, {len(path2)}")
                continue

            hold_data[(track_id, f'{positions[0]}h')] = (path1, path2)

            counter += 1
            print(f"preprocessing hold data...{counter}", end='\r')

            #self.draw_path_on_frame(track_id, path[0]['frame']+3, path, circle_info)

        if not hold_data:
            print("preprocess_hold_data: no hold data")
            return {}

        return hold_data
    


    @log_error
    def analyze_hold_reach_time(self, hold_data, circle_info, fps):

        hold_info = {}
        for (track_id, direction), (path1, path2) in hold_data.items():
            # 计算前半段的到达时间
            times = []
            for point in path1:
                frame_num = point['frame']
                dist = point['dist']
                reach_end_Msec = self.predict_note_reach_end_time(dist, frame_num, circle_info[2], fps)
                times.append(reach_end_Msec)
            mean1 = np.mean(times)

            # min1 = np.min(times)
            # max1 = np.max(times)
            # median1 = np.median(times)
            # std_dev1 = np.std(times)
            # std_dev_percent1 = std_dev1 / mean1 * 100
            # print(f"hold track_id {track_id}, direction {direction}\n  Mean {mean1:.3f}, Min {min1:.3f}, Max {max1:.3f}, Median {median1:.3f}, Std Dev {std_dev_percent1:.3f}%")

            # 计算后半段的到达时间
            times = []
            for point in path2:
                frame_num = point['frame']
                dist = point['dist']
                reach_end_Msec = self.predict_note_reach_end_time(dist, frame_num, circle_info[2], fps)
                times.append(reach_end_Msec)
            mean2 = np.mean(times)

            # min2 = np.min(times)
            # max2 = np.max(times)
            # median2 = np.median(times)
            # std_dev2 = np.std(times)
            # std_dev_percent2 = std_dev2 / mean2 * 100
            # print(f"  Mean {mean2:.3f}, Min {min2:.3f}, Max {max2:.3f}, Median {median2:.3f}, Std Dev {std_dev_percent2:.3f}%")

            hold_info[(track_id, direction)] = (mean1, mean2)


        return hold_info



    


    # debug
    @log_error
    def analyze_all_notes_info(self, video_name, bpm, tap_info, touch_info, hold_info):

        def get_fraction(diff_beat, base_denominator):
            #numerator分子, denominator分母
            one = 0
            base_numerator = round(diff_beat * base_denominator)
            if base_numerator == 0:
                return 0, 1, 0
            # 先处理整倍数
            if base_numerator // base_denominator >= 1 and base_numerator % base_denominator == 0:
                return base_numerator // base_denominator, 1, 0
            # 处理分数
            if base_numerator > base_denominator:
                one = base_numerator // base_denominator
                if one > 1:
                    base_numerator = base_numerator % base_denominator
                else:
                    one = 0
            # 约分
            gcd_num = gcd(base_numerator, base_denominator)
            numerator = base_numerator // gcd_num
            denominator = base_denominator // gcd_num
            return numerator, denominator, one


        txt_path = rf"C:\Users\ck273\Desktop\{video_name}.txt"
        if os.path.exists(txt_path):
            os.remove(txt_path)
        f = open(txt_path, 'w', encoding='utf-8')
        f.write(f'&title={video_name}\n')
        f.write('&artist=ck273\n')
        f.write('&first=0\n')
        f.write('&des_4=ck273\n')
        f.write('&lv_4=10\n')
        f.write(f'&inote_4=({bpm})' + '{1},,')


        # 合并所有info
        all_notes_info = {**tap_info, **touch_info, **hold_info}
        # 按时间排序
        sorted_notes = sorted(all_notes_info.items(), key=lambda item: item[1][0] if isinstance(item[1], tuple) else item[1])

        init_time = 0
        last_time = 0
        base_numerator_counter = 0
        last_position = None
        last_denominator = 0
        time_deviations = []

        base_denominator = 16  # 基准分母

        for (track_id, position), time in sorted_notes:

            # 处理 length 信息
            if isinstance(time, tuple):
                length = time[1] - time[0]
                time = time[0]
                
                length_beat = length / (60 / bpm * 1000 * 4)
                numerator, denominator, one = get_fraction(length_beat, base_denominator)
                if numerator != 0:
                    if one == 0:
                        numerator = numerator + one * denominator
                    position = f'{position}[{denominator}:{numerator}]'


            if last_time == 0:
                init_time = time
                last_time = time
                last_position = position
                print(f"[{time:.3f}] ", end='')
                continue
            
            diff_Msec = time - last_time
            diff_beat = diff_Msec / (60 / bpm * 1000 * 4)
            numerator, denominator, one = get_fraction(diff_beat, base_denominator)

            # update last_time
            base_numerator = round(diff_beat * base_denominator)
            base_numerator_counter += base_numerator
            passed_beat = base_numerator_counter / base_denominator
            passed_beat_Msec = passed_beat * (60 / bpm * 1000 * 4)
            last_time = passed_beat_Msec + init_time

            # 统计误差
            real_time_diff = time - init_time
            time_deviation = real_time_diff - passed_beat_Msec
            time_deviations.append(time_deviation)

            if numerator == 0:
                last_position = f'{last_position}/{position}'
                continue

            if one > 0:
                commas = f'{"," * numerator}' + '{1}' + f'{"," * one}'
                print(f"{last_position}-{numerator}/{denominator}+{one}, ", end='')
            else:
                commas = f'{"," * numerator}'
                print(f"{last_position}-{numerator}/{denominator}, ", end='')

            if denominator != last_denominator:
                f.write('\n{' + f'{denominator}' + '}' + f'{last_position}{commas}')
            else:
                f.write(f'{last_position}{commas}')

            if one > 0: denominator = 1
            last_denominator = denominator
            last_position = position
                

        print(f'{last_position}-E')
        f.write(f'{last_position},E\n')
        f.close()

        length = len(time_deviations)
        mean = np.mean(time_deviations)
        min = np.min(time_deviations)
        max = np.max(time_deviations)
        median = np.median(time_deviations)
        std_dev = np.std(time_deviations)
        print(f"Time deviations {length}: Median {median:.3f}, Min {min:.3f}, Max {max:.3f}, Mean {mean:.3f}, Std Dev {std_dev:.3f}")



    # debug
    def process(self, state: dict):
        try:
            video_name = state['video_name']
            print(f"NoteAnalyzer: {video_name}")
            print("NoteAnalyzer Initialize...", end = '\r')

            circle_center_x = 540
            circle_center_y = 540
            circle_radius = 478
            circle_info = (circle_center_x, circle_center_y, circle_radius)
            detect_video_path = state['detect_video_path']
            output_dir = os.path.dirname(detect_video_path)
            debug = state['debug']
            fps = state['video_fps']
            bpm = state['bpm']
            std_video = state['std_video_path']
            self.touch_areas = state['touch_areas']
            self.cap = cv2.VideoCapture(std_video)

            touch_type_classify_model_path = r"D:\git\mai-chart-analyze\yolo-train\runs\classify\touch_type_classify\weights\best.pt"
            if not os.path.exists(touch_type_classify_model_path):
                raise FileNotFoundError(f"Touch type classify model not found: {touch_type_classify_model_path}")
            self.touch_type_classify_model = YOLO(touch_type_classify_model_path)

            touch_scale_classify_regular_model_path = r"D:\git\mai-chart-analyze\yolo-train\runs\classify\touch_scale_classify_regular\weights\best.pt"
            if not os.path.exists(touch_scale_classify_regular_model_path):
                raise FileNotFoundError(f"Touch scale classify regular model not found: {touch_scale_classify_regular_model_path}")
            self.touch_scale_classify_regular_model = YOLO(touch_scale_classify_regular_model_path)

            touch_scale_classify_each_model_path = r"D:\git\mai-chart-analyze\yolo-train\runs\classify\touch_scale_classify_each\weights\best.pt"
            if not os.path.exists(touch_scale_classify_each_model_path):
                raise FileNotFoundError(f"Touch scale classify each model not found: {touch_scale_classify_each_model_path}")
            self.touch_scale_classify_each_model = YOLO(touch_scale_classify_each_model_path)

            
            # Load detection data
            final_tracks, track_results_all, predict_results_all, metadata = self.load_detection_data(output_dir, video_name)

            # tap
            tap_info = {}
            tap_data = self.preprocess_tap_data(final_tracks, track_results_all, predict_results_all, circle_info)
            if tap_data:
                self.note_DefaultMsec, self.note_OptionNotespeed = self.estimate_note_DefaultMsec(tap_data, circle_info, fps)
                tap_info = self.analyze_tap_reach_time(tap_data, circle_info, fps)

            # touch
            touch_info = {}
            touch_data = self.preprocess_touch_data(final_tracks, track_results_all, predict_results_all, circle_info)
            if touch_data:
                self.touch_DefaultMsec, self.touch_OptionNotespeed = self.estimate_touch_DefaultMsec(touch_data, circle_info, fps)
                touch_info = self.analyze_touch_reach_time(touch_data, fps)

            # hold
            hold_data = self.preprocess_hold_data(final_tracks, track_results_all, predict_results_all, circle_info)
            if hold_data:
                hold_info = self.analyze_hold_reach_time(hold_data, circle_info, fps)
            
            # analyze all notes info
            self.analyze_all_notes_info(video_name, bpm, tap_info, touch_info, hold_info)



        except Exception as e:
            raise Exception(f"Error in NoteAnalyzer: {e}")
        finally:
            if self.cap is not None:
                self.cap.release()
        




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

    
    id = '6.25'
    state1 = {
        'video_name': f'test_{id}',
        'detect_video_path': rf"D:\git\mai-chart-analyze\yolo-train\runs\detect\test_{id}\test_{id}_tracked.mp4",
        'std_video_path': rf"D:\git\mai-chart-analyze\yolo-train\runs\detect\test_{id}\test_{id}_standardlized.mp4",
        'debug': True,
        'video_fps': 60,
        'bpm': 170, # test
        'touch_areas': touch_areas,
    }
    

    state2 = {
        'video_name': '踊',
        'detect_video_path': r"D:\git\mai-chart-analyze\yolo-train\runs\detect\踊\踊_tracked.mp4",
        'std_video_path': r"D:\git\mai-chart-analyze\yolo-train\runs\detect\踊\踊_standardlized.mp4",
        'debug': True,
        'video_fps': 60,
        'bpm': 128, # 踊
        'touch_areas': touch_areas,
    }

    state3 = {
        'video_name': '[maimai谱面确认] 天蓋 MASTER-p01-116',
        'detect_video_path': r"D:\git\mai-chart-analyze\yolo-train\runs\detect\[maimai谱面确认] 天蓋 MASTER-p01-116\[maimai谱面确认] 天蓋 MASTER-p01-116_tracked.mp4",
        'std_video_path': r"D:\git\mai-chart-analyze\yolo-train\runs\detect\[maimai谱面确认] 天蓋 MASTER-p01-116\[maimai谱面确认] 天蓋 MASTER-p01-116_standardlized.mp4",
        'debug': True,
        'video_fps': 60,
        'bpm': 178, # 天蓋
        'touch_areas': touch_areas,
    }

    state4 = {
        'video_name': 'Hurtling Boys EXPERT',
        'detect_video_path': r"D:\git\mai-chart-analyze\yolo-train\runs\detect\Hurtling Boys EXPERT\Hurtling Boys EXPERT_tracked.mp4",
        'std_video_path': r"D:\git\mai-chart-analyze\yolo-train\runs\detect\Hurtling Boys EXPERT\Hurtling Boys EXPERT_standardlized.mp4",
        'debug': True,
        'video_fps': 60,
        'bpm': 195,
        'touch_areas': touch_areas,
    }

    analyzer.process(state4)
