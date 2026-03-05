def preprocess_touch_hold_data(self):
    '''
    收集所有touch_hold音符的数据
    过滤轨迹过短的音符
    计算音符方位
    计算音符的三角到中心的距离 (精确)
    过滤前后两端的数据 (距离10%-75%, 百分比3%-47%)

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
                'dist': dist_to_center,
                'percent': percent_of_hold
            },
            ...
        ]
    }
    '''

    touch_hold_data = {}

    dist_end_tolerance = self.touch_hold_travel_dist * 0.25
    dist_start_tolerance = self.touch_hold_travel_dist * 0.1
    valid_dist_end = 0 + dist_end_tolerance
    valid_dist_start = self.touch_hold_travel_dist - dist_start_tolerance
    percent_end_tolerance = 0.03
    percent_start_tolerance = 0.03
    valid_percent_end = 0.5 - percent_end_tolerance
    valid_percent_start = 0 + percent_start_tolerance
    cap = cv2.VideoCapture(self.video_path)

    # read track data
    for track_id, track_data in self.track_data.items():

        if 'path' not in track_data: continue
        track_path = track_data['path']
        if len(track_path) < 10: continue
        class_id = round(track_data['class_id'])
        if self.noteDetector.get_main_class_id(class_id) != 5:
            continue # 5 = touch_hold，忽视非touch_hold音符

        counter = 0
        precent_counter = 0

        # read track path
        valid_track_path = []
        for track_box in track_path:

            print(f"preprocess_touch_hold_data: processing track_id {track_id}, frame_{counter}/{len(track_path)}   ", end='\r', flush=True)
            counter += 1

            frame_num = track_box['frame']
            x1 = track_box['x1'] # 左上角
            y1 = track_box['y1'] # 左上角
            x2 = track_box['x3'] # 右下角
            y2 = track_box['y3'] # 右下角
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2

            # 计算三角到中心的距离
            if precent_counter >= 5: break # 节省时间，hold阶段后半都不用计算了
            dist, percent_of_hold = self.get_touch_hold_data(cx, cy, frame_num, cap)
            # 过滤前后两端的数据
            if dist > valid_dist_start:
                dist = -1 # 掐头
            elif dist < valid_dist_end:
                dist = -1 # 去尾
            if percent_of_hold < valid_percent_start:
                percent_of_hold = -1 # 掐头
            elif percent_of_hold > valid_percent_end:
                percent_of_hold = -1 # 去尾
                precent_counter += 1
            #  两个值都无效才跳过
            if dist == -1 and percent_of_hold == -1:
                continue
            # 计算方位
            position = self.calculate_all_position(cx, cy)
            # 添加轨迹点
            valid_track_path.append((frame_num, x1, y1, x2, y2, position, dist, percent_of_hold))


        # 检查轨迹存在
        if not valid_track_path:
            print(f"preprocess_touch_hold_data: no valid_track_path for track_id {track_id}")
            continue
        valid_track_path.sort(key=lambda x: x[0]) # 按frame排序
        # 检验长度
        if len(valid_track_path) < 6:
            print(f"preprocess_touch_hold_data: path too short for track_id {track_id}, length: {len(valid_track_path)}")
            continue
        # 检验方位一致
        positions = [x[5] for x in valid_track_path]
        if len(set(positions)) != 1:
            print(f"preprocess_touch_hold_data: positions not consistent for track_id {track_id}")
            continue
        # 添加到touch_hold_data
        path = []
        for frame_num, x1, y1, x2, y2, position, dist, percent_of_hold in valid_track_path:
            path.append({
                'frame': frame_num,
                'x1': x1,
                'y1': y1,
                'x2': x2,
                'y2': y2,
                'dist': dist,
                'percent': percent_of_hold
            })
        touch_hold_data[(track_id, class_id, positions[0])] = path


    if not touch_hold_data:
        print("preprocess_touch_hold_data: no touch data")
        touch_hold_data = {}
    
    cap.release()
    print(f"{' '*70}", end='\r', flush=True) # 清除行
    return touch_hold_data



@log_error
def get_touch_hold_data(self, cx, cy, frame_num, cap):

    try:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
        ret, frame = cap.read()
        if not ret:
            print(f"get_touch_hold_data: failed to read frame {frame_num}")
            return -1, -1

        # 根据label-notes定义，touch_hold的整体尺寸是 (30+100) x 2/√3 (1080p下)
        # 保险起见变成 200x200
        roi_radius = 100 * self.video_size / 1080

        # 提取ROI区域
        x_start = round(max(cx - roi_radius, 0))
        y_start = round(max(cy - roi_radius, 0))
        x_end = round(min(cx + roi_radius, self.video_size - 1))
        y_end = round(min(cy + roi_radius, self.video_size - 1))
        roi = frame[y_start:y_end, x_start:x_end]
        # 处理roi
        transformed_roi = self.diamond_polar_transform(roi)
        stretched_roi = self.stretch_transformed_image(transformed_roi)
        final_roi = self.apply_hsv_threshold(stretched_roi)
        h, w = final_roi.shape[:2]
        # 计算 final_roi 上方 15% - 50% 区域中黑色像素的比例
        roi_top = final_roi[int(h * 0.15):int(h * 0.5), :, :]
        black_mask = cv2.inRange(roi_top, (0, 0, 0), (10, 10, 10))
        black_pixel_count = cv2.countNonZero(black_mask)
        total_pixel_count = roi_top.shape[0] * roi_top.shape[1]
        black_pixel_ratio = black_pixel_count / total_pixel_count if total_pixel_count > 0 else 0
        # 计算dist和percent
        dist = -1
        percent_of_hold = -1

        # 视为scale阶段,计算dist
        if black_pixel_ratio > 0.25:
            # 动态阈值
            grey_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            _, binary_roi = cv2.threshold(grey_roi, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            # 轮廓识别
            distances = []
            contours, _ = cv2.findContours(binary_roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours: return -1, -1
            for contour in contours:
                # 尺寸合适
                _, radius = cv2.minEnclosingCircle(contour)          
                if radius < roi_radius * 0.4 or radius > roi_radius * 0.5:
                    continue
                # 轮廓是三角形
                epsilon = 0.04 * cv2.arcLength(contour, True)     # 逼近精度，值越小，越接近原始轮廓。
                approx = cv2.approxPolyDP(contour, epsilon, True) # 近似多边形
                if len(approx) != 3: continue
                #cv2.drawContours(roi, [approx], -1, (0, 255, 0), 2)
                # 计算三角形每个顶点到中心的距离
                roi_center = np.array([roi_radius, roi_radius])
                tri_distances = []
                for point in approx:
                    point_coords = point[0] # 获取点的坐标
                    tri_distance = np.linalg.norm(point_coords - roi_center)
                    tri_distances.append(tri_distance)
                # 校验三点距离关系
                tri_distances.sort()
                if ((tri_distances[2] - tri_distances[1]) < roi_radius * 0.05 and # 等边三角形
                    (tri_distances[1] - tri_distances[0]) > roi_radius * 0.4):    # 朝向中心
                    distances.append(tri_distances[0]) # 取最短距离
            # 平均距离
            if distances:
                dist = np.mean(distances)
                dist -= roi_radius * 0.1 # 微调

            # # 显示窗口
            # print(f"frame {frame_num}: dist {dist:.2f}")
            # cv2.imshow(f'frame {frame_num}', roi)
            # cv2.waitKey(0)
            # cv2.destroyAllWindows()

        # 视为hold阶段,计算percent_of_hold
        else:
            # 逐列扫描final_roi的左边一半，关注每一列最下面的30%像素
            # 如果这一列最下面的30%像素中，黑色像素占比小于70%，计数器+1
            counter = 0
            for col in range(w // 2):
                # 获取当前列最下面30%的像素
                bottom_pixels = final_roi[int(h * 0.7):, col]
                # 计算黑色像素的数量
                black_pixels = 0
                for pixel in bottom_pixels:
                    if (pixel[0] < 10 and pixel[1] < 10 and pixel[2] < 10):
                        black_pixels += 1
                # 如果黑色像素占比小于70%，计数器+1
                if black_pixels < h * 0.3 * 0.7:
                    counter += 1
            # 计算百分比
            percent_of_hold = counter / (w // 2 - 1) / 2 # 除以2是因为只扫描了一半宽度

        return dist, percent_of_hold

    except Exception as e:
        print(f"get_touch_hold_data - frame {frame_num}: exception {e}")
        return -1, -1



@log_error
def diamond_polar_transform(self, roi):
    """
    菱形极坐标变换
    """
    
    # 获取ROI尺寸
    h, w = roi.shape[:2]
    cx, cy = w // 2, h // 2
    # 输出的矩形的尺寸
    height = min(cx, cy) - 1 # 防止越界
    width = height * 4
    transformed_image = np.zeros((height, width, 3), dtype=np.uint8)
    # 菱形极坐标变换
    for y_out in range(height):
        for x_out in range(width):
            # 计算菱形极坐标
            # 径向坐标：从中心到外径
            r = y_out
            # 角坐标：沿菱形边界的归一化位置 (0-1)
            # 左移1/8个圆（45度），让起点从菱形正上方开始
            angle_frac = (x_out / width + 0.125) % 1.0
            # 将角坐标转换为菱形边界上的位置
            # 菱形有4个边，每个边对应90度
            side_index = int(angle_frac * 4) % 4
            side_pos = (angle_frac * 4) % 1.0
            # 根据所在边计算笛卡尔坐标
            if side_index == 0:  # 上
                x_diamond = r * (2 * side_pos - 1)
                y_diamond = -r
            elif side_index == 1:  # 右
                x_diamond = r
                y_diamond = r * (2 * side_pos - 1)
            elif side_index == 2:  # 下
                x_diamond = r * (1 - 2 * side_pos)
                y_diamond = r
            else:  # 左
                x_diamond = -r
                y_diamond = r * (1 - 2 * side_pos)
            # 转换为ROI中的像素坐标
            x_roi = int(cx + x_diamond)
            y_roi = int(cy + y_diamond)
            # 检查边界并采样
            if 0 <= x_roi < w and 0 <= y_roi < h:
                transformed_image[y_out, x_out] = roi[y_roi, x_roi]

    return transformed_image



@log_error
def stretch_transformed_image(self, roi):
    """
    对菱形极坐标变换后的矩形进行后处理
    从左到右对每一列进行向下拉伸，消除底部的三角形背景区域
    三角形的底长为矩形宽度的1/4，高度为矩形高度的1/2.4
    """
    h, w = roi.shape[:2]
    # 创建拉伸后的图像（尺寸保持不变）
    stretched_image = np.zeros_like(roi)
    # 计算每个列的拉伸参数
    for x in range(w):
        # 计算当前列在矩形中的位置
        pos_frac = x / w
        # 转换为在一个三角形内的位置 (1/4)
        while pos_frac > 0.25:
            pos_frac -= 0.25
        # 计算此时的三角形的高度
        # 相似三角形：底:底=高:高
        if pos_frac < 0.125: # 左边
            tri_h = (pos_frac / 0.125) * (h / 2.4)
        else: # 右边
            tri_h = ((0.25 - pos_frac) / 0.125) * (h / 2.4)
        # 计算拉伸因子
        stretch_factor = h / (h - tri_h)
        stretch_factor = max(stretch_factor, 1) # 防止小于1

        # 对当前列进行拉伸
        # 使用反向映射避免黑色像素(计算目标像素对应的原始像素)
        for y_stretched in range(h):
            # 计算对应的原始y坐标
            y_orig = y_stretched / stretch_factor
            # 如果y_orig不是整数，使用上下两个像素进行插值（双线性插值）
            y0 = int(y_orig)        # 下界
            y1 = min(y0 + 1, h - 1) # 上界
            if y0 < h:
                # 计算插值权重
                weight = y_orig - y0
                # 双线性插值
                if y0 < h - 1:
                    pixel_value = (1 - weight) * roi[y0, x] + weight * roi[y1, x]
                    stretched_image[y_stretched, x] = pixel_value.astype(np.uint8)
                else:
                    stretched_image[y_stretched, x] = roi[y0, x]

    return stretched_image



@log_error
def apply_hsv_threshold(self, roi):
    """
    采样展开后的矩形最上面一行的所有像素的平均饱和度和亮度
    设置饱和度和亮度阈值，过滤背景和黄色光晕特效
    """
    h, w = roi.shape[:2]

    # 转换到HSV颜色空间
    hsv_image = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    # 采样最上面一行的所有像素
    top_row_hsv = hsv_image[0, :, :]
    # 计算平均饱和度和亮度
    avg_saturation = np.mean(top_row_hsv[:, 1])   # 饱和度通道
    avg_value = np.mean(top_row_hsv[:, 2])        # 亮度通道
    saturation_threshold = avg_saturation * 0.7   # 使用平均饱和度的70%作为阈值
    value_threshold = avg_value * 0.75            # 使用平均亮度的75%作为阈值
    # 对整个图像应用饱和度阈值
    for y in range(h):
        for x in range(w):
            h_val, s_val, v_val = hsv_image[y, x] # 获取当前像素的HSV值
            if s_val < saturation_threshold:      # 如果饱和度低于阈值，将像素变为黑色
                roi[y, x] = [0, 0, 0]
    # 对新的图像的下半30%应用亮度阈值
    hsv_image = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    for y in range(int(h*0.7), h):
        for x in range(w):
            h_val, s_val, v_val = hsv_image[y, x]
            if v_val < value_threshold:
                roi[y, x] = [0, 0, 0]

    return roi

