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
            






def calculate_all_position(self, note_x, note_y):
    
    closeset_label = None
    closeset_dist = 9999

    for label, (cx, cy) in self.touch_areas.items():
        dist = np.sqrt(((note_x - cx) ** 2 + (note_y - cy) ** 2))
        if dist < closeset_dist:
            closeset_label = label
            closeset_dist = dist
    
    return closeset_label




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
