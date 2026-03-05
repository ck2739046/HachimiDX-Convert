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
        if self.noteDetector.get_main_class_id(class_id) != 3:
            continue # 3 = touch，忽视非touch音符

        # read track path
        valid_track_path = []
        for track_box in track_path:

            frame_num = track_box['frame']
            x1 = track_box['x1'] # 左上角
            y1 = track_box['y1'] # 左上角
            x2 = track_box['x3'] # 右下角
            y2 = track_box['y3'] # 右下角
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
