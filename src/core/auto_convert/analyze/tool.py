def calculate_oct_position(circle_center_x, circle_center_y, note_x, note_y):
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




# def draw_path_on_frame(self, track_id, frame_num, path):

#     cap = cv2.VideoCapture(self.video_path)  
#     cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
#     ret, frame = cap.read()
#     if not ret:
#         print(f"draw_path_on_frame: failed to read frame {frame_num}")
#         cap.release()
#         return
    
#     cv2.putText(frame, f"track_id: {track_id}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
#     # 绘制两个圈
#     cv2.circle(frame, (round(self.screen_cx), round(self.screen_cy)), round(self.judgeline_end), (0, 255, 0), 2)
#     cv2.circle(frame, (round(self.screen_cx), round(self.screen_cy)), round(self.judgeline_start), (255, 0, 0), 2)

#     for point in path:
#         frame_num = point['frame']
#         cx = (point['x1'] + point['x2']) // 2
#         cy = (point['y1'] + point['y2']) // 2
#         cv2.circle(frame, (round(cx), round(cy)), 3, (0, 0, 255), -1)

#     # Resize and show frame
#     resized_frame = cv2.resize(frame, (900, 900), interpolation=cv2.INTER_AREA)
#     window_name = f'Tap ID: {track_id}'
#     cv2.namedWindow(window_name)
#     cv2.moveWindow(window_name, 500, 80)
#     cv2.imshow(window_name, resized_frame)
#     cv2.waitKey(0)
#     cv2.destroyAllWindows()
#     cap.release()
