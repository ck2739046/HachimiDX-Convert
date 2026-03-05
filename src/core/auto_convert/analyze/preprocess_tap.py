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
        if self.noteDetector.get_main_class_id(class_id) != 1:
            continue # 1 = tap，忽视非tap音符


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
        # 检查dist是否递增 (允许微小回退5%总距离)
        dists = [x[6] for x in valid_track_path]
        if not all(later - earlier > - 0.5 * start_tolerance for earlier, later in zip(dists, dists[1:])):
            print(f"preprocess_tap_data: dist not increasing for track_id {track_id}")
            continue
        # 检查dist是否在头尾 (20%-80%)
        if dists[0] > valid_judgeline_start + 2*start_tolerance or dists[-1] < valid_judgeline_end - 2*end_tolerance:
            print(f"preprocess_tap_data: dist out of range for track_id {track_id}, start_dist: {dists[0]}, end_dist: {dists[-1]}")
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
