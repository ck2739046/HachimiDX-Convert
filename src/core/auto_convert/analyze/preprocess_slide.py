def preprocess_slide_head_data(self):
    '''
    收集所有slide音符的数据
    只分离出星星头，视为 tap note 处理, 忽略后续轨迹移动
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

    slide_data = {}

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
        if self.noteDetector.get_main_class_id(class_id) != 2:
            continue # 2 = slide，忽视非slide音符


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
            # print(f"preprocess_slide_head_data: no valid_track_path for track_id {track_id}")
            continue
        valid_track_path.sort(key=lambda x: x[0]) # 按frame排序
        
        # 检验长度
        if len(valid_track_path) < 6:
            # print(f"preprocess_slide_head_data: valid_track_path too short for track_id {track_id}, length: {len(valid_track_path)}")
            continue
        # 检验方位一致
        positions = [x[5] for x in valid_track_path]
        if len(set(positions)) != 1:
            # print(f"preprocess_slide_head_data: positions not consistent for track_id {track_id}")
            continue
        # 检查dist是否递增 (允许微小回退 -0.5* start_tolerance)
        dists = [x[6] for x in valid_track_path]
        if not all(later - earlier > -0.5 * start_tolerance for earlier, later in zip(dists, dists[1:])):
            # print(f"preprocess_slide_head_data: dist not increasing for track_id {track_id}")
            continue
        # 检查dist是否在头尾 (20%-80%)
        if dists[0] > valid_judgeline_start + start_tolerance or dists[-1] < valid_judgeline_end - end_tolerance:
            # print(f"preprocess_slide_head_data: dist out of range for track_id {track_id}, start_dist: {dists[0]}, end_dist: {dists[-1]}")
            continue
        # 添加到slide_data
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
        slide_data[(track_id, class_id, positions[0])] = path
        # self.draw_path_on_frame(track_id, path[0]['frame']+3, path)

    if not slide_data:
        print("preprocess_slide_head_data: no slide head data")
        return {}

    return slide_data



def preprocess_slide_tail_data(self):
    '''
    收集所有slide音符的数据
    过滤轨迹过短的音符
    对所有轨迹点进行方位计算，形成移动路径
    只分离出移动阶段的星星，忽略星星头

    分离方法: 仅接受轨迹开头和结尾都在A区的音符

    返回格式:
    dict{
        key: (track_id, class_id, start_position),
        value: note path list
        [
            {
                'frame': frame_num,
                'x1': x1,
                'y1': y1,
                'x2': x2,
                'y2': y2,
                'dist': dist_to_center,
                'position': position
            },
            ...
        ]
    }
    '''

    slide_data = {}

    # read track data
    for track_id, track_data in self.track_data.items():

        if 'path' not in track_data: continue
        track_path = track_data['path']
        if len(track_path) < 10: continue
        if 'class_id' not in track_data: continue
        class_id = round(track_data['class_id'])
        if self.noteDetector.get_main_class_id(class_id) != 2:
            continue # 2 = slide，忽视非slide音符


        # 先检查开头和结尾
        box = track_path[0]
        cx = (box['x1'] + box['x3']) / 2
        cy = (box['y1'] + box['y3']) / 2
        position = self.calculate_all_position(cx, cy)
        if not position.startswith('A'):
            continue # 忽视非A区开头音符
        box = track_path[-1]
        cx = (box['x1'] + box['x3']) / 2
        cy = (box['y1'] + box['y3']) / 2
        position = self.calculate_all_position(cx, cy)
        if not position.startswith('A') and not position.startswith('D'):
            continue # 忽视非A区或D区结尾音符


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
            # 允许音符略微超出判定线范围(10%)，但更远的就忽略了
            if dist_to_center > self.judgeline_end * 1.1: # 110%
                continue
            # 计算方位
            position = self.calculate_all_position(cx, cy)
            # 添加轨迹点
            valid_track_path.append((frame_num, x1, y1, x2, y2, position, dist_to_center))


        # 检查轨迹存在
        if not valid_track_path:
            # print(f"preprocess_slide_tail_data: no valid_track_path for track_id {track_id}")
            continue
        valid_track_path.sort(key=lambda x: x[0]) # 按frame排序
        
        # 检验长度
        if len(valid_track_path) < 6:
            # print(f"preprocess_slide_tail_data: valid_track_path too short for track_id {track_id}, length: {len(valid_track_path)}")
            continue

        # 添加到slide_data
        path = []
        for frame_num, x1, y1, x2, y2, position, dist_to_center in valid_track_path:
            path.append({
                'frame': frame_num,
                'x1': x1,
                'y1': y1,
                'x2': x2,
                'y2': y2,
                'dist': dist_to_center,
                'position': position
            })
        positions = [x[5] for x in valid_track_path]
        slide_data[(track_id, class_id, positions[0])] = path
        # self.draw_path_on_frame(track_id, path[0]['frame']+3, path)

    if not slide_data:
        print("preprocess_slide_tail_data: no slide tail data")
        return {}

    return slide_data
