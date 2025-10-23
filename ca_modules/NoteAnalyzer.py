from collections import defaultdict
import os
import cv2
import numpy as np
import math
import functools
import traceback
import time
from math import dist, gcd
import NoteDetector

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

        # 速度常数
        self.note_DefaultMsec = 0
        self.note_OptionNotespeed = 0
        self.touch_DefaultMsec = 0
        self.touch_OptionNotespeed = 0

        # 常用变量
        self.video_size = 0
        self.fps = 0
        self.screen_cx = 0
        self.screen_cy = 0
        self.judgeline_start = 0
        self.judgeline_end = 0
        self.note_travel_dist = 0
        self.touch_travel_dist = 0
        self.bpm = 0
        self.touch_areas = {}
        self.track_data = ()
        self.noteDetector = None
        self.video_path = ""



    # debug
    @log_error
    def preprocess_tap_data(self):
        '''
        收集所有tap音符的数据
        过滤轨迹过短的音符
        计算音符方向
        计算音符到圆心的距离
        过滤刚离开起点的和马上要到终点的音符数据 (10%-90%距离)

        返回格式:
        dict{
            key: (track_id, class_id, position),
            value: note path list
            [
                {
                    'frame': frame_num,
                    'x1': x1,
                    'y1': y1,
                    'x2': x2,
                    'y2': y2,
                    'dist': dist_to_center
                },
                ...
            ]
        }
        '''

        tap_data = {}

        end_tolerance = self.note_travel_dist * 0.1
        start_tolerance = self.note_travel_dist * 0.1
        valid_judgeline_start = self.judgeline_start + start_tolerance
        valid_judgeline_end = self.judgeline_end - end_tolerance

        # read track data
        for track_id, track_data in self.track_data.items():

            if 'path' not in track_data: continue
            track_path = track_data['path']
            if len(track_path) < 10: continue
            if 'class_id' not in track_data: continue
            class_id = round(track_data['class_id'])
            if self.noteDetector.get_main_class_id(class_id) != 0:
                continue # 0 = tap，忽视非tap音符


            # read track path
            valid_track_path = []
            for track_box in track_path:

                frame_num = track_box['frame']
                x1 = track_box['x1']
                y1 = track_box['y1']
                x2 = track_box['x2']
                y2 = track_box['y2']
                cx = (x1 + x2) / 2
                cy = (y1 + y2) / 2

                # 计算距离圆心的距离
                dist_to_center = np.sqrt(((cx - self.screen_cx)**2 + (cy - self.screen_cy)**2))
                # 计算方向(1-8)
                position = self.calculate_oct_position(self.screen_cx, self.screen_cy, cx, cy)
                # 过滤10%-90%距离的数据
                if dist_to_center < valid_judgeline_start:
                    continue # 掐头
                elif dist_to_center > valid_judgeline_end:
                    continue # 去尾
                # 添加轨迹点
                valid_track_path.append((frame_num, x1, y1, x2, y2, position, dist_to_center))


            # 检查轨迹存在
            if not valid_track_path:
                print(f"preprocess_tap_data: no valid_track_path for track_id {track_id}")
                continue
            valid_track_path.sort(key=lambda x: x[0]) # 按frame排序
            # 检验长度
            if len(valid_track_path) < 6:
                print(f"preprocess_tap_data: valid_track_path too short for track_id {track_id}, length: {len(valid_track_path)}")
                continue
            # 检验方位一致
            positions = [x[5] for x in valid_track_path]
            if len(set(positions)) != 1:
                print(f"preprocess_tap_data: positions not consistent for track_id {track_id}")
                continue
            # 添加到tap_data
            path = []
            for frame_num, x1, y1, x2, y2, position, dist_to_center in valid_track_path:
                path.append({
                    'frame': frame_num,
                    'x1': x1,
                    'y1': y1,
                    'x2': x2,
                    'y2': y2,
                    'dist': dist_to_center
                })
            tap_data[(track_id, class_id, positions[0])] = path
            # self.draw_path_on_frame(track_id, path[0]['frame']+3, path)

        if not tap_data:
            print("preprocess_tap_data: no tap data")
            return {}

        return tap_data
    


    @log_error
    def estimate_note_DefaultMsec(self, tap_data):
        """
        音符从起点移动到判定线需要耗时 DefaultMsec (ms)
        采样4个点（0%、25%、50%、100%）计算三个阶段性速度
        """

        note_speeds = []

        for path in tap_data.values():

            # 获取4个采样点的索引
            path_length = len(path)
            indices = [
                0,  # 0%
                path_length // 4,  # 25%
                path_length // 2,  # 50%
                path_length - 1  # 100%
            ]
            
            # 计算三个阶段性速度
            for i in range(3):
                start_idx = indices[i]
                end_idx = indices[i + 1]
                
                frame_num_start = path[start_idx]['frame']
                frame_num_end = path[end_idx]['frame']
                dist_start = path[start_idx]['dist']
                dist_end = path[end_idx]['dist']

                frame_num_diff = frame_num_end - frame_num_start
                total_dist = dist_end - dist_start
                
                if frame_num_diff > 0: # 避免除零错误
                    note_speed = total_dist / frame_num_diff  # pixel/frame
                    note_speeds.append(note_speed)

        length = len(note_speeds)
        mean = np.mean(note_speeds)
        min = np.min(note_speeds)
        max = np.max(note_speeds)
        median = np.median(note_speeds)
        std_dev = np.std(note_speeds)
        std_dev_percent = std_dev / mean * 100
        print(f"speed of {length} tap notes: [Median {median:.3f}], Min {min:.3f}, Max {max:.3f}, Mean {mean:.3f}, Std Dev {std_dev_percent:.3f}%")

        note_DefaultMsec, note_OptionNotespeed = self.get_note_DefaultMsec(median)
        return note_DefaultMsec, note_OptionNotespeed
    


    @log_error
    def analyze_tap_reach_time(self, tap_data):

        tap_info = {}
        for (track_id, class_id, direction), path in tap_data.items():
            # 平均所有轨迹的到达时间
            times = []
            for point in path:
                frame_num = point['frame']
                dist = point['dist']
                reach_end_Msec = self.predict_note_reach_end_time(dist, frame_num)
                times.append(reach_end_Msec)
            mean = np.mean(times)
            tap_info[(track_id, class_id, direction)] = mean

        return tap_info



    @log_error
    def predict_note_reach_end_time(self, cur_dist, cur_frame):
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

        cur_time = cur_frame / self.fps * 1000 # 转换为毫秒
        total_dist = self.note_travel_dist
        dist_offset = -1/120 * total_dist * (self.note_OptionNotespeed / 150 - 1)
        #time_offset = (self.note_OptionNotespeed / 150 - 1) * (-0.5 / (self.note_OptionNotespeed / 150 - 1)) * 1.6 * 1000 / 60
        start_pos = self.judgeline_start

        travelled_dist = cur_dist - start_pos - dist_offset
        time_progress = travelled_dist / total_dist
        leave_start_Msec = cur_time - time_progress * self.note_DefaultMsec # + time_offset
        reach_end_Msec = leave_start_Msec + self.note_DefaultMsec

        return reach_end_Msec



    @log_error
    def get_note_DefaultMsec(self, detected_note_speed):

        def get_standard_note_DefaultMsec(ui_speed):
            # 游戏源码实现
            OptionNotespeed = round(ui_speed * 100 + 100) # 6.25 = 725
            NoteSpeedForBeat = 1000 / (OptionNotespeed / 60)
            DefaultMsec = NoteSpeedForBeat * 4
            return DefaultMsec, OptionNotespeed

        total_dist = self.note_travel_dist
        detected_note_speed = detected_note_speed * self.fps / 1000 # pixel/frame to pixel/ms
        note_lifetime = total_dist / detected_note_speed # 走完全程需要多少时间

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
    def draw_path_on_frame(self, track_id, frame_num, path):

        cap = cv2.VideoCapture(self.video_path)  
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
        ret, frame = cap.read()
        if not ret:
            print(f"draw_path_on_frame: failed to read frame {frame_num}")
            cap.release()
            return
        
        cv2.putText(frame, f"track_id: {track_id}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        # 绘制两个圈
        cv2.circle(frame, (round(self.screen_cx), round(self.screen_cy)), round(self.judgeline_end), (0, 255, 0), 2)
        cv2.circle(frame, (round(self.screen_cx), round(self.screen_cy)), round(self.judgeline_start), (255, 0, 0), 2)

        for point in path:
            frame_num = point['frame']
            cx = (point['x1'] + point['x2']) // 2
            cy = (point['y1'] + point['y2']) // 2
            cv2.circle(frame, (round(cx), round(cy)), 3, (0, 0, 255), -1)

        # Resize and show frame
        resized_frame = cv2.resize(frame, (900, 900), interpolation=cv2.INTER_AREA)
        window_name = f'Tap ID: {track_id}'
        cv2.namedWindow(window_name)
        cv2.moveWindow(window_name, 500, 80)
        cv2.imshow(window_name, resized_frame)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        cap.release()



    @log_error
    def calculate_oct_position(self, circle_center_x, circle_center_y, note_x, note_y):
        x_diff = note_x - circle_center_x
        y_diff = note_y - circle_center_y
        if x_diff >= 0 and y_diff <= 0:
            # 1, 2
            if abs(x_diff) < abs(y_diff):
                return 1
            else:
                return 2
        elif x_diff >= 0 and y_diff >= 0:
            # 3, 4
            if abs(x_diff) > abs(y_diff):
                return 3
            else:
                return 4
        elif x_diff <= 0 and y_diff >= 0:
            # 5, 6
            if abs(x_diff) < abs(y_diff):
                return 5
            else:
                return 6
        elif x_diff <= 0 and y_diff <= 0:
            # 7, 8
            if abs(x_diff) > abs(y_diff):
                return 7
            else:
                return 8
                








    # debug
    @log_error
    def preprocess_touch_data(self):
        '''
        收集所有touch音符的数据
        过滤轨迹过短的音符
        计算音符方位
        计算音符的三角到中心的距离
        过滤刚离开起点的和马上要到终点的音符数据 (10%-90%距离)

        返回格式:
        dict{
            key: (track_id, class_id, position),
            value: note path list
            [
                {
                    'frame': frame_num,
                    'x1': x1,
                    'y1': y1,
                    'x2': x2,
                    'y2': y2,
                    'dist': dist_to_center
                },
                ...
            ]
        }
        '''

        touch_data = {}

        end_tolerance = self.touch_travel_dist * 0.1
        start_tolerance = self.touch_travel_dist * 0.1
        valid_dist_end = 0 + end_tolerance
        valid_dist_start = self.touch_travel_dist - start_tolerance
        outer_size = 54 * self.video_size / 1080 # 1080p下，外部尺寸为54

        # read track data
        for track_id, track_data in self.track_data.items():

            if 'path' not in track_data: continue
            track_path = track_data['path']
            if len(track_path) < 10: continue
            class_id = round(track_data['class_id'])
            if self.noteDetector.get_main_class_id(class_id) != 2:
                continue # 2 = touch，忽视非touch音符

            # read track path
            valid_track_path = []
            for track_box in track_path:

                frame_num = track_box['frame']
                x1 = track_box['x1']
                y1 = track_box['y1']
                x2 = track_box['x2']
                y2 = track_box['y2']
                cx = (x1 + x2) / 2
                cy = (y1 + y2) / 2

                # 计算三角到中心的距离
                # 根据label_notes可知，touch音符的整体尺寸=(dist+54)x2，1080p下
                avg_touch_size = ((x2 - x1) + (y2 - y1)) / 2
                dist = avg_touch_size / 2 - outer_size
                # 计算方位
                position = self.calculate_all_position(cx, cy)
                # 过滤前后两端的数据
                if dist > valid_dist_start:
                    continue # 掐头
                elif dist < valid_dist_end:
                    continue # 去尾
                # 添加轨迹点
                valid_track_path.append((frame_num, x1, y1, x2, y2, position, dist))


            # 检查轨迹存在
            if not valid_track_path:
                print(f"preprocess_touch_data: no valid_track_path for track_id {track_id}")
                continue
            valid_track_path.sort(key=lambda x: x[0]) # 按frame排序
            # 检验长度
            if len(valid_track_path) < 6:
                print(f"preprocess_touch_data: path too short for track_id {track_id}, length: {len(valid_track_path)}")
                continue
            # 检验方位一致
            positions = [x[5] for x in valid_track_path]
            if len(set(positions)) != 1:
                print(f"preprocess_touch_data: positions not consistent for track_id {track_id}")
                continue
            # 添加到touch_data
            path = []
            for frame_num, x1, y1, x2, y2, position, dist in valid_track_path:
                path.append({
                    'frame': frame_num,
                    'x1': x1,
                    'y1': y1,
                    'x2': x2,
                    'y2': y2,
                    'dist': dist
                })
            touch_data[(track_id, class_id, positions[0])] = path


        if not touch_data:
            print("preprocess_touch_data: no touch data")
            return {}
        
        return touch_data



    # @log_error
    # def detect_precise_touch(self, i, roi, thresh_roi, circle_info, frame_num, track_id):

    #     # 使用基于轮廓识别的坐标和dist精确数据
    #     # threshhold: regular 150, each 185

    #     circle_center_x, circle_center_y, circle_radius = circle_info
    #     touch_radius_min = circle_radius * 0.035
    #     touch_radius_max = circle_radius * 0.055
    #     center_dot_min = circle_radius * 0.02
    #     center_dot_max = circle_radius * 0.04
    #     None_result = (None, None, None, None, None, None, None)

    #     # 寻找中心点
    #     note_cx = 0
    #     note_cy = 0
    #     roi_cx = (roi.shape[1] - 1) / 2
    #     roi_cy = (roi.shape[0] - 1) / 2
    #     gray_dot_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    #     _, thresh_dot_roi = cv2.threshold(gray_dot_roi, 160, 255, cv2.THRESH_BINARY)
    #     # 轮廓识别
    #     contours, _ = cv2.findContours(thresh_dot_roi, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    #     if not contours: return None_result
    #     for contour in contours:
    #         (x, y), radius = cv2.minEnclosingCircle(contour)         
    #         # 尺寸合适 
    #         if radius < center_dot_min or radius > center_dot_max: continue
    #         # 验证轮廓圆形度 (0.8)
    #         area = cv2.contourArea(contour)
    #         circle_area = 3.14 * radius * radius + 1e-6 # 避免除0错误
    #         circularity = area / circle_area
    #         if circularity < 0.8: continue
    #         # 验证是否在中心附近
    #         if abs(x - roi_cx) > center_dot_max or abs(y - roi_cy) > center_dot_max: continue
    #         # 视为合法结果
    #         note_cx = x
    #         note_cy = y

    #     if note_cx == 0 or note_cy == 0:
    #         print(f"detect_precise_touch: [track_id {track_id}] no valid center point at frame {frame_num}")
    #         return None_result


    #     valid_points = {}
    #     # 轮廓识别
    #     contours, _ = cv2.findContours(thresh_roi, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    #     if not contours: return None_result
    #     for contour in contours:

    #         # 尺寸合适
    #         (x, y), radius = cv2.minEnclosingCircle(contour)          
    #         if radius < touch_radius_min or radius > touch_radius_max:
    #             continue

    #         # 轮廓是三角形
    #         epsilon = 0.04 * cv2.arcLength(contour, True) # 逼近精度，值越小，越接近原始轮廓。
    #         approx = cv2.approxPolyDP(contour, epsilon, True) # 近似多边形
    #         if len(approx) != 3: continue

    #         # 轮廓内部是白色
    #         # 创建掩码
    #         mask = np.zeros(thresh_roi.shape, dtype=np.uint8)
    #         cv2.fillPoly(mask, [contour], 255)
    #         # 轮廓内的像素
    #         contour_pixels = thresh_roi[mask == 255]
    #         # 计算白色像素比例
    #         white_pixels = np.sum(contour_pixels == 255)
    #         total_pixels = len(contour_pixels)
    #         white_ratio = white_pixels / total_pixels
    #         if white_ratio > 0.5: continue
            
    #         # 方向正确
    #         # 获取包围圆的上下左右四个点
    #         up = (x, y - radius)
    #         left = (x - radius, y)
    #         down = (x, y + radius)
    #         right = (x + radius, y)
    #         box_points = [up, left, down, right]
    #         # 计算轮廓的几何中心（centroid）
    #         M = cv2.moments(contour)
    #         cx = M["m10"] / M["m00"]
    #         cy = M["m01"] / M["m00"]
    #         # 计算三角形方向 (取离几何中心最近的点)
    #         distances = [np.linalg.norm(np.array((cx, cy)) - np.array(point)) for point in box_points]
    #         closest_index = np.argmin(distances)
    #         orientation = ["up", "left", "down", "right"][closest_index]
    #         closest_box_point = box_points[closest_index]
    #         # 排除非法方向
    #         if orientation == "up":
    #             if note_cy - cy > 0: continue
    #         elif orientation == "left":
    #             if note_cx - cx > 0: continue
    #         elif orientation == "down":
    #             if note_cy - cy < 0: continue
    #         elif orientation == "right":
    #             if note_cx - cx < 0: continue
    #         # 计算cloest_box_point到音符中心的距离
    #         dist = np.sqrt(((closest_box_point[0] - note_cx) ** 2 + (closest_box_point[1] - note_cy) ** 2))
    #         # 保存结果 
    #         if orientation not in valid_points.keys():
    #             valid_points[orientation] = (radius, dist, closest_box_point, contour, round(x), round(y))
    #         else:
    #             # 如果同方向已存在，取半径较小的
    #             existing_radius = valid_points[orientation][0]
    #             if radius < existing_radius:
    #                 valid_points[orientation] = (radius, dist)


    #     # 计算精准的尺寸
    #     dists = [value[1] for value in valid_points.values()]
    #     if len(dists) <= 1:
    #         print(f"detect_precise_touch: [track_id {track_id}] not enough valid points at frame {frame_num}")

    #         # show frame
    #         thresh_roi_bgr = cv2.cvtColor(thresh_roi, cv2.COLOR_GRAY2BGR)
    #         combined_view = np.hstack((roi, thresh_roi_bgr))
    #         window_name = f'ID{track_id}-{frame_num}-{i}'
    #         cv2.namedWindow(window_name)
    #         cv2.moveWindow(window_name, 500, 500)
    #         time.sleep(0.005)
    #         cv2.imshow(window_name, combined_view)
    #         cv2.waitKey(0)
    #         cv2.destroyAllWindows()

    #         return None_result
        

    #     # 转换为外框尺寸 ( offset = 0.08 * radius )
    #     avg_dist = np.mean(dists)
    #     touch_outer = circle_radius * 0.08
    #     precise_x1 = note_cx - avg_dist - touch_outer
    #     precise_y1 = note_cy - avg_dist - touch_outer
    #     precise_x2 = note_cx + avg_dist + touch_outer
    #     precise_y2 = note_cy + avg_dist + touch_outer


    #     # cv2.rectangle(roi, (round(precise_x1), round(precise_y1)), (round(precise_x2), round(precise_y2)), (0, 255, 0), 2)
    #     # cv2.circle(roi, (round(note_cx), round(note_cy)), 3, (255, 0, 0), 2)
    #     # # draw contour
    #     # for radius, dist, closest_box_point, contour, x, y in valid_points.values():
    #     #     cv2.drawContours(roi, [contour], 0, (0, 255, 0), 2)
    #     #     cv2.circle(roi, (round(closest_box_point[0]), round(closest_box_point[1])), 2, (0, 0, 255), 2)
    #     #     cv2.putText(roi, f'{round(radius)}', (round(x), round(y)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 1)
    #     # # show window
    #     # thresh_roi_bgr = cv2.cvtColor(thresh_roi, cv2.COLOR_GRAY2BGR)
    #     # combined_view = np.hstack((roi, thresh_roi_bgr))
    #     # window_name = f'ID{track_id}-{frame_num}-{i}'
    #     # cv2.namedWindow(window_name)
    #     # cv2.moveWindow(window_name, 500, 500)
    #     # time.sleep(0.005)
    #     # cv2.imshow(window_name, combined_view)
    #     # cv2.waitKey(0)
    #     # cv2.destroyAllWindows()

    #     return (precise_x1, precise_y1, precise_x2, precise_y2, note_cx, note_cy, avg_dist)
    


    @log_error
    def calculate_all_position(self, note_x, note_y):
        
        closeset_label = None
        closeset_dist = 9999

        for label, (cx, cy) in self.touch_areas.items():
            dist = np.sqrt(((note_x - cx) ** 2 + (note_y - cy) ** 2))
            if dist < closeset_dist:
                closeset_label = label
                closeset_dist = dist
        
        return closeset_label
    


    @log_error
    def estimate_touch_DefaultMsec(self, touch_data):
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
        通过dump游戏得知total_Dist = 34 (对于标准1080p)
        DispAdjustFlame: 0 (时间微调参数没有影响, 可以忽略)
        DefaultCorlsPos Values: [(0.0, 34.0, -1.0), (0.0, -34.0, -1.0), (34.0, 0.0, 0.0), (-34.0, 0.0, 0.0)]

        首先反推出每个点的time_progress, (只保留location_progress 0.15-0.85)
        选择缓动函数斜率较大的区间，因为这些区间对时间变化更敏感
        选两个点相减消除未知的move_start_time常量
        -> DefaultMsec = (current_time1 - current_time2) / (time_progress1 - time_progress2)

        计算多个数据点对的 DefaultMsec 然后取平均值
        '''

        def reverse_function(y, tolerance=0.001):
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

        for (track_id, class_id, position), path in touch_data.items():

            # 过滤掉斜率较小的轨迹点
            big_slope_points = []
            for point in path:
                # 反推 location_progress (保留15%-85%的点)
                cur_dist = point['dist']
                location_progress = 1 - cur_dist / self.touch_travel_dist
                if location_progress < 0.15 or location_progress > 0.85:
                    continue
                # 反推 time_progress
                time_progress = reverse_function(location_progress)
                # 加入列表
                cur_time = point['frame'] / self.fps * 1000 # 帧数转换为毫秒
                big_slope_points.append((cur_time, time_progress))

            if len(big_slope_points) < 6:
                print(f"estimate_touch_DefaultMsec: [track_id {track_id}] not enough big slope points, length: {len(big_slope_points)}")
                continue

            # 轨迹点配对并计算 DefaultMsec
            big_slope_points.sort(key=lambda x: x[1]) # 按 time_progress 排序
            for i in range(len(big_slope_points)):
                for j in range(i + 1, len(big_slope_points)):
                    time1, progress1 = big_slope_points[i]
                    time2, progress2 = big_slope_points[j]
                    if abs(progress1 - progress2) < 0.15:
                        continue # 忽略相近的 progress 减少误差 (15%) 
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
    def analyze_touch_reach_time(self, touch_data):

        touch_info = {}
        for (track_id, class_id, position), path in touch_data.items():
            # 平均所有轨迹的到达时间
            times = []
            for point in path:
                frame_num = point['frame']
                dist = point['dist']
                reach_end_Msec = self.predict_touch_reach_end_time(dist, frame_num)
                if reach_end_Msec != 0:
                    times.append(reach_end_Msec)
                    
            mean = np.mean(times)
            touch_info[(track_id, position)] = mean

        return touch_info
    


    @log_error
    def predict_touch_reach_end_time(self, dist, cur_frame):
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

        def reverse_function(y, tolerance=0.001):
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
        total_dist = self.touch_travel_dist
        location_progress = 1 - dist / total_dist
        if location_progress < 0.15 or location_progress > 0.85:
            return 0
        # 反推 time_progress
        time_progress = reverse_function(location_progress)
        # 反推 move_start_time
        cur_time = cur_frame / self.fps * 1000  # 转换为毫秒
        move_start_time = cur_time - time_progress * self.touch_DefaultMsec
        reach_end_time = move_start_time + self.touch_DefaultMsec

        return reach_end_time
    









    # debug
    @log_error
    def preprocess_hold_data(self):
        '''
        收集所有hold音符的数据
        过滤轨迹过短的音符
        计算音符方向
        分离头尾
        分别计算头尾到圆心的距离
        过滤刚离开起点的和马上要到终点的音符数据 (5%-95%距离)

        返回格式:
        dict{
            key: (track_id, class_id, position),
            value: note path list
            [
                {
                    'frame': frame_num,
                    'x-head': x1,
                    'y-head': y1,
                    'x-tail': x2,
                    'y-tail': y2,
                    'dist-head': dist_head,
                    'dist-tail': dist_tail
                },
                ...
            ]
        }
        '''

        hold_data = {}

        end_tolerance = self.note_travel_dist * 0.05
        start_tolerance = self.note_travel_dist * 0.05
        valid_judgeline_start = self.judgeline_start + start_tolerance
        valid_judgeline_end = self.judgeline_end - end_tolerance

        # read track data
        for track_id, track_data in self.track_data.items():

            if 'path' not in track_data: continue
            track_path = track_data['path']
            if len(track_path) < 10: continue
            if 'class_id' not in track_data: continue
            class_id = round(track_data['class_id'])
            if self.noteDetector.get_main_class_id(class_id) != 3:
                continue # 3 = hold，忽视非hold音符


            # read track path
            valid_track_path = []
            for track_box in track_path:

                frame_num = track_box['frame']
                x1 = track_box['x1']
                y1 = track_box['y1']
                x2 = track_box['x2']
                y2 = track_box['y2']
                x3 = track_box['x3']
                y3 = track_box['y3']
                x4 = track_box['x4']
                y4 = track_box['y4']
                cx = (x1 + x2 + x3 + x4) / 4
                cy = (y1 + y2 + y3 + y4) / 4

                # 计算距离圆心的距离
                dist_to_center = np.sqrt(((cx - self.screen_cx)**2 + (cy - self.screen_cy)**2))
                # 计算方向(1-8)
                position = self.calculate_oct_position(self.screen_cx, self.screen_cy, cx, cy)
                # 过滤10%-90%距离的数据
                if dist_to_center < valid_judgeline_start:
                    continue # 掐头
                elif dist_to_center > valid_judgeline_end:
                    continue # 去尾
                # 计算头和尾的坐标
                x_head, y_head, x_tail, y_tail, dist_head, dist_tail = self.calculate_hold_head_tail(x1, y1, x2, y2, x3, y3, x4, y4, position, class_id)
                # 添加轨迹点
                valid_track_path.append((frame_num, x_head, y_head, x_tail, y_tail, position, dist_head, dist_tail))


            # 检查轨迹存在
            if not valid_track_path:
                print(f"preprocess_hold_data: no valid_track_path for track_id {track_id}")
                continue
            valid_track_path.sort(key=lambda x: x[0]) # 按frame排序
            # 检验长度
            if len(valid_track_path) < 6:
                print(f"preprocess_hold_data: valid_track_path too short for track_id {track_id}, length: {len(valid_track_path)}")
                continue
            # 检验方位一致
            positions = [x[5] for x in valid_track_path]
            if len(set(positions)) != 1:
                print(f"preprocess_hold_data: positions not consistent for track_id {track_id}")
                continue
            # 添加到hold_data
            path = []
            for frame_num, x_head, y_head, x_tail, y_tail, position, dist_head, dist_tail in valid_track_path:
                path.append({
                    'frame': frame_num,
                    'x-head': x_head,
                    'y-head': y_head,
                    'x-tail': x_tail,
                    'y-tail': y_tail,
                    'dist-head': dist_head,
                    'dist-tail': dist_tail
                })
            hold_data[(track_id, class_id, positions[0])] = path

        if not hold_data:
            print("preprocess_hold_data: no hold data")
            return {}

        return hold_data
    


    @log_error
    def calculate_hold_head_tail(self, x1, y1, x2, y2, x3, y3, x4, y4, position, class_id):
        '''
        获取hold框与轨道线的两个交点，视为hold的两个端点
        然后两个端点往回缩一点就是head和tail的位置
        '''

        # 直线经过中心点 (screen_cx, screen_cy)
        # 输入直线的y轴下方与x轴正半轴的夹角 (0°-180°)
        def get_line(angle):
            # 计算斜率 a = tan(angle)
            a = math.tan(math.radians(angle)) # 角度转换为弧度
            # 将屏幕中心点代入 y=ax+b 求解 b
            b = self.screen_cy - a * self.screen_cx
            return (a, b)


        # 计算矩形与直线的交点，应该是会有两个
        def calculate_line_rectangle_intersections(a, b, x1, y1, x2, y2, x3, y3, x4, y4):        
            # 四条边
            edges = [(x1, y1, x2, y2), (x2, y2, x3, y3), (x3, y3, x4, y4), (x4, y4, x1, y1)]
            intersections = []
            for x_start, y_start, x_end, y_end in edges:
                # 特殊处理竖直边，防止除零错误
                if abs(x_end - x_start) < 1e-1:
                    x_intersect = x_start
                    y_intersect = a * x_intersect + b   
                # 普通情况
                else:
                    # 计算边的斜率和截距
                    edge_a = (y_end - y_start) / (x_end - x_start)
                    edge_b = y_start - edge_a * x_start
                    # 计算交点
                    if abs(a - edge_a) < 1e-1: continue # 跳过平行边，防止除零错误
                    x_intersect = (edge_b - b) / (a - edge_a)
                    y_intersect = a * x_intersect + b
                # 检查交点是否在边的x范围内
                if ((min(x_start, x_end) <= x_intersect <= max(x_start, x_end)) and
                    (min(y_start, y_end) <= y_intersect <= max(y_start, y_end))):
                    intersections.append((x_intersect, y_intersect))
            return intersections
        

        # 根据到中心点的距离，在轨迹线上计算新的点
        def get_point_by_dist_to_center(a, b, x, y, dist):
            # 沿轨迹线获得距离为 dist 的两个点
            dx = dist / np.sqrt(1 + np.power(a, 2))
            dy = a * dx
            p1x = self.screen_cx + dx
            p1y = self.screen_cy + dy
            p2x = self.screen_cx - dx
            p2y = self.screen_cy - dy
            # 更接近原始点的就是新的点
            if abs(p1x - x) > abs(p2x - x):
                return p2x, p2y
            else:
                return p1x, p1y


        # 根据方向确定轨道直线
        if position == 1 or position == 5:
            a, b = get_line(112.5)
        elif position == 2 or position == 6:
            a, b = get_line(157.5)
        elif position == 3 or position == 7:
            a, b = get_line(22.5)
        elif position == 4 or position == 8:
            a, b = get_line(67.5)

        # 计算hold框的四条边与轨道直线的交点
        intersections = calculate_line_rectangle_intersections(a, b, x1, y1, x2, y2, x3, y3, x4, y4)
        
        if len(intersections) != 2:
            print(f"expect 2 intersections, but got {len(intersections)}, skip")
            return None, None, None, None, None, None
            
        # 根据距离圆心的远近区分head和tail
        dist1 = math.sqrt((intersections[0][0] - self.screen_cx)**2 + (intersections[0][1] - self.screen_cy)**2)
        dist2 = math.sqrt((intersections[1][0] - self.screen_cx)**2 + (intersections[1][1] - self.screen_cy)**2)
        # 更远的是 head, 更近的是 tail
        head_x, head_y = intersections[0] if dist1 > dist2 else intersections[1]
        tail_x, tail_y = intersections[1] if dist1 > dist2 else intersections[0]
        dist_head = dist1 if dist1 > dist2 else dist2
        dist_tail = dist2 if dist1 > dist2 else dist1

        # 根据 label_notes 定义，整个hold的一半宽度为 70x0.77 (ex再+5)
        # 那么正六边形的端点到中心的距离约为 70x0.77 x 2/√3
        width = 70 * 0.77 if class_id not in [17,18] else 75 * 0.77 + 5
        offset = width * 2 / math.sqrt(3)
        # 往回缩一点
        new_dist_head = dist_head - offset
        new_dist_tail = dist_tail + offset
        # 防止越过起点和终点
        if new_dist_head > self.judgeline_end:
            new_dist_head = self.judgeline_end
        if new_dist_head < self.judgeline_start:
            new_dist_head = self.judgeline_start
        if new_dist_tail > self.judgeline_end:
            new_dist_tail = self.judgeline_end
        if new_dist_tail < self.judgeline_start:
            new_dist_tail = self.judgeline_start
        # 计算新的head和tail坐标
        new_head_x, new_head_y = get_point_by_dist_to_center(a, b, head_x, head_y, new_dist_head)
        new_tail_x, new_tail_y = get_point_by_dist_to_center(a, b, tail_x, tail_y, new_dist_tail)

        return new_head_x, new_head_y, new_tail_x, new_tail_y, new_dist_head, new_dist_tail


  
    @log_error
    def analyze_hold_reach_time(self, hold_data):

        hold_info = {}

        end_tolerance = self.note_travel_dist * 0.1
        start_tolerance = self.note_travel_dist * 0.1
        valid_judgeline_start = self.judgeline_start + start_tolerance
        valid_judgeline_end = self.judgeline_end - end_tolerance

        for (track_id, class_id, direction), path in hold_data.items():

            head_times = []
            tail_times = []
            # 平均所有轨迹的到达时间
            for point in path:
                frame_num = point['frame']
                dist_head = point['dist-head']
                dist_tail = point['dist-tail']
                # 过滤 head 和 tail (10%-90%)
                if valid_judgeline_start <= dist_head <= valid_judgeline_end:
                    reach_end_Msec_head = self.predict_note_reach_end_time(dist_head, frame_num)
                    head_times.append(reach_end_Msec_head)
                if valid_judgeline_start <= dist_tail <= valid_judgeline_end:
                    reach_end_Msec_tail = self.predict_note_reach_end_time(dist_tail, frame_num)
                    tail_times.append(reach_end_Msec_tail)
            # 计算平均时间
            mean_head = np.mean(head_times)
            mean_tail = np.mean(tail_times)
            hold_info[(track_id, class_id, direction)] = (mean_head, mean_tail)

            # print(f"Hold ID {track_id} Direction {direction}:")
            # min1 = np.min(head_times)
            # max1 = np.max(head_times)
            # median1 = np.median(head_times)
            # std_dev1 = np.std(head_times)
            # std_dev_percent1 = std_dev1 / mean_head * 100
            # print(f"  head - Mean {mean_head:.3f}, Min {min1:.3f}, Max {max1:.3f}, Median {median1:.3f}, Std Dev {std_dev_percent1:.3f}%")

            # min2 = np.min(tail_times)
            # max2 = np.max(tail_times)
            # median2 = np.median(tail_times)
            # std_dev2 = np.std(tail_times)
            # std_dev_percent2 = std_dev2 / mean_tail * 100
            # print(f"  tail - Mean {mean_tail:.3f}, Min {min2:.3f}, Max {max2:.3f}, Median {median2:.3f}, Std Dev {std_dev_percent2:.3f}%")

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
    @log_error
    def main(self, main_folder: str, bpm: float):
        try:
            # 在文件夹查找视频文件
            for root, _, files in os.walk(main_folder):
                for fn in files:
                    if fn.lower().endswith('standardized.mp4'):
                        self.video_path = os.path.join(root, fn)
                        break
            if not self.video_path:
                raise Exception(f"No standardized.mp4 file found under {main_folder}")
            
            # 获取视频信息
            cap = cv2.VideoCapture(self.video_path)
            self.video_size = round(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.fps = round(cap.get(cv2.CAP_PROP_FPS))
            #total_frames = round(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.release()

            # 定义一些常数
            self.screen_cx = self.video_size // 2
            self.screen_cy = self.screen_cx
            # 1080p下，音符从120出现480结束
            self.judgeline_start = self.video_size * 120 / 1080
            self.judgeline_end = self.video_size * 480 / 1080
            self.note_travel_dist = self.judgeline_end - self.judgeline_start
            self.touch_travel_dist = 34 * self.video_size / 1080 # 1080p下，touch移动距离为34像素
            self.bpm = bpm
            self.touch_areas = self.get_touch_areas()
            self.noteDetector = NoteDetector.NoteDetector()
            self.track_data = self.noteDetector._load_track_results(main_folder)


            # tap
            tap_info = {}
            tap_data = self.preprocess_tap_data()
            if tap_data:
                self.note_DefaultMsec, self.note_OptionNotespeed = self.estimate_note_DefaultMsec(tap_data)
                tap_info = self.analyze_tap_reach_time(tap_data)

            # touch
            touch_info = {}
            touch_data = self.preprocess_touch_data()
            if touch_data:
                self.touch_DefaultMsec, self.touch_OptionNotespeed = self.estimate_touch_DefaultMsec(touch_data)
                touch_info = self.analyze_touch_reach_time(touch_data)

            # hold
            hold_info = {}
            hold_data = self.preprocess_hold_data()
            if hold_data:
                hold_info = self.analyze_hold_reach_time(hold_data)
            
            # # analyze all notes info
            # self.analyze_all_notes_info(video_name, bpm, tap_info, touch_info, hold_info)



        except Exception as e:
            raise Exception(f"Error in NoteAnalyzer: {e}")
        


    @log_error
    def get_touch_areas(self) -> dict:
        # 1080p的触摸区域中心坐标
        std_touch_areas = {
            # A
            'A1': (693, 171), 'A2': (909, 388), 'A3': (908, 693), 'A4': (692, 910),
            'A5': (387, 909), 'A6': (170, 694), 'A7': (170, 388), 'A8': (386, 170),
            # B
            'B1': (624, 336), 'B2': (745, 456), 'B3': (744, 626), 'B4': (624, 745),
            'B5': (455, 745), 'B6': (335, 626), 'B7': (335, 456), 'B8': (454, 336),
            # C
            'C1': (540, 540),
            # D
            'D1': (540, 117), 'D2': (840, 241), 'D3': (963, 542), 'D4': (839, 840),
            'D5': (540, 964), 'D6': (241, 840), 'D7': (116, 540), 'D8': (239, 241),
            # E
            'E1': (540, 229), 'E2': (760, 320), 'E3': (852, 540), 'E4': (760, 761),
            'E5': (539, 853), 'E6': (319, 760), 'E7': (228, 540), 'E8': (319, 321),
        }
        new_touch_areas = {}
        for area_label, (x, y) in std_touch_areas.items():
            scaled_x = round((x - 540) * self.video_size / 1080 + self.screen_cx)
            scaled_y = round((y - 540) * self.video_size / 1080 + self.screen_cy)
            new_touch_areas[area_label] = (scaled_x, scaled_y)
        return new_touch_areas




if __name__ == "__main__":

    folder_name = "Customized Justice EXPERT_standardized"
    folder_path = rf"D:\git\mai-chart-analyze\yolo-train\runs\detect\{folder_name}"

    bpm = 0

    try:
        analyzer = NoteAnalyzer()
        analyzer.main(folder_path, bpm)
    except Exception as e:
        print(f"Error: {e}")
        print(f"Error trace: {error_trace}")
        traceback.print_exc()
