import numpy as np

from ..detect.note_definition import *
from .tool import *
from .shared_context import *


DEBUG_TOUCH_HOLD_PREPROCESS = True


def debug_touch_hold(message):
    if DEBUG_TOUCH_HOLD_PREPROCESS:
        print(message)



def preprocess_touch_hold_data(shared_context: SharedContext):
    '''
    返回格式:
    dict{
        key: (track_id, note_type, note_variant, note_position),
        value: note path
        [
            {
                'frame': frame_num,
                'dist': dist_to_center,
                'percent': percent_of_hold
            },
            ...
        ]
    }
    '''

    touch_hold_data = {}

    dist_end_tolerance = shared_context.touch_hold_travel_dist * 0.25
    dist_start_tolerance = shared_context.touch_hold_travel_dist * 0.1
    valid_dist_end = 0 + dist_end_tolerance
    valid_dist_start = shared_context.touch_hold_travel_dist - dist_start_tolerance
    touch_hold_max_size = shared_context.touch_hold_max_size
    percent_end_tolerance = 0.03
    percent_start_tolerance = 0.03
    valid_percent_end = 0.5 - percent_end_tolerance
    valid_percent_start = 0 + percent_start_tolerance
    cap = cv2.VideoCapture(shared_context.std_video_path)

    # read track data
    for key, value in shared_context.track_data.items():

        track_id, note_type = key
        note_geometry_list = value

        if note_type != NoteType.TOUCH_HOLD: continue
        if len(note_geometry_list) < 10: continue

        counter = 0
        precent_counter = 0

        # read track path
        valid_track_path = []
        for note in note_geometry_list:

            print(f"preprocess_touch_hold_data: processing track_id {track_id}, frame_{counter}/{len(note_geometry_list)}   ", end='\r', flush=True)
            counter += 1

            # 计算三角到中心的距离
            if precent_counter >= 5: break # 节省时间，hold阶段后半都不用计算了
            dist, percent_of_hold = get_touch_hold_data(shared_context.std_video_size, note.cx, note.cy, note.frame, cap, touch_hold_max_size)
            debug_touch_hold(
                f"preprocess_touch_hold_data: track_id={track_id}, frame={note.frame}, note_type={note_type.name}, "
                f"note_variant={note.note_variant.name}, raw_dist={dist}, raw_percent={percent_of_hold}"
            )
            # 过滤前后两端的数据
            if dist > valid_dist_start:
                debug_touch_hold(
                    f"preprocess_touch_hold_data: track_id={track_id}, frame={note.frame} dist filtered as head, "
                    f"dist={dist:.3f}, valid_dist_start={valid_dist_start:.3f}"
                )
                dist = -1 # 掐头
            elif dist < valid_dist_end:
                debug_touch_hold(
                    f"preprocess_touch_hold_data: track_id={track_id}, frame={note.frame} dist filtered as tail, "
                    f"dist={dist:.3f}, valid_dist_end={valid_dist_end:.3f}"
                )
                dist = -1 # 去尾
            if percent_of_hold < valid_percent_start:
                debug_touch_hold(
                    f"preprocess_touch_hold_data: track_id={track_id}, frame={note.frame} percent filtered as head, "
                    f"percent={percent_of_hold:.3f}, valid_percent_start={valid_percent_start:.3f}"
                )
                percent_of_hold = -1 # 掐头
            elif percent_of_hold > valid_percent_end:
                debug_touch_hold(
                    f"preprocess_touch_hold_data: track_id={track_id}, frame={note.frame} percent filtered as tail, "
                    f"percent={percent_of_hold:.3f}, valid_percent_end={valid_percent_end:.3f}"
                )
                percent_of_hold = -1 # 去尾
                precent_counter += 1
            #  两个值都无效才跳过
            if dist == -1 and percent_of_hold == -1:
                debug_touch_hold(
                    f"preprocess_touch_hold_data: track_id={track_id}, frame={note.frame} skipped because both dist and percent are invalid"
                )
                continue
            # 计算方位
            position = calculate_all_position(shared_context.touch_areas, note.cx, note.cy)
            debug_touch_hold(
                f"preprocess_touch_hold_data: track_id={track_id}, frame={note.frame} accepted position={position}, "
                f"dist={dist}, percent={percent_of_hold}"
            )
            # 添加轨迹点
            valid_track_path.append((note.frame, position, dist, percent_of_hold))



        # 检查轨迹存在
        if not valid_track_path:
            print(f"preprocess_touch_hold_data: no valid_track_path for track_id {track_id}")
            continue
        
        # 检验长度
        if len(valid_track_path) < 6:
            print(f"preprocess_touch_hold_data: path too short for track_id {track_id}, length: {len(valid_track_path)}")
            continue

        # 检验方位一致
        positions = [x[1] for x in valid_track_path]
        if len(set(positions)) != 1:
            print(f"preprocess_touch_hold_data: positions not consistent for track_id {track_id}")
            continue
        
        # 按frame排序
        valid_track_path.sort(key=lambda x: x[0])

        # 检查通过，添加到touch_hold_data
        note_variant = note_geometry_list[0].note_variant
        position = positions[0]
        key = (track_id, note_type, note_variant, position)
        debug_touch_hold(
            f"preprocess_touch_hold_data: track_id={track_id} finalized with {len(valid_track_path)} points, "
            f"position={position}, note_variant={note_variant.name}"
        )

        path = []
        for frame_num, position, dist, percent_of_hold in valid_track_path:
            path.append({
                'frame': frame_num,
                'dist': dist,
                'percent': percent_of_hold
            })
        touch_hold_data[key] = path

    if not touch_hold_data:
        print("preprocess_touch_hold_data: no touch hold data")
        touch_hold_data = {}
    
    cap.release()
    print(f"{' '*70}", end='\r', flush=True) # 清除行
    return touch_hold_data




def get_touch_hold_data(std_video_size, cx, cy, frame_num, cap, touch_hold_max_size):

    try:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
        ret, frame = cap.read()
        if not ret:
            print(f"get_touch_hold_data: failed to read frame {frame_num}")
            return -1, -1

        roi_radius = touch_hold_max_size / 2

        # 提取ROI区域
        x_start = round(max(cx - roi_radius, 0))
        y_start = round(max(cy - roi_radius, 0))
        x_end = round(min(cx + roi_radius, std_video_size - 1))
        y_end = round(min(cy + roi_radius, std_video_size - 1))
        roi = frame[y_start:y_end, x_start:x_end]
        if roi.size == 0:
            print(
                f"get_touch_hold_data: empty roi for frame {frame_num}, cx={cx:.3f}, cy={cy:.3f}, "
                f"x=[{x_start},{x_end}), y=[{y_start},{y_end})"
            )
            return -1, -1
        # 处理roi
        transformed_roi = diamond_polar_transform(roi)
        stretched_roi = stretch_transformed_image(transformed_roi)
        final_roi = apply_hsv_threshold(stretched_roi)
        h, w = final_roi.shape[:2]
        debug_touch_hold(
            f"get_touch_hold_data: frame={frame_num}, roi_shape={roi.shape[:2]}, final_roi_shape={final_roi.shape[:2]}, "
            f"cx={cx:.3f}, cy={cy:.3f}"
        )
        # 计算 final_roi 上方 15% - 50% 区域中黑色像素的比例
        roi_top = final_roi[int(h * 0.15):int(h * 0.5), :, :]
        black_mask = cv2.inRange(roi_top, (0, 0, 0), (10, 10, 10))
        black_pixel_count = cv2.countNonZero(black_mask)
        total_pixel_count = roi_top.shape[0] * roi_top.shape[1]
        black_pixel_ratio = black_pixel_count / total_pixel_count if total_pixel_count > 0 else 0
        debug_touch_hold(
            f"get_touch_hold_data: frame={frame_num}, black_pixel_count={black_pixel_count}, "
            f"total_pixel_count={total_pixel_count}, black_pixel_ratio={black_pixel_ratio:.3f}"
        )
        # 计算dist和percent
        dist = -1
        percent_of_hold = -1

        # 视为scale阶段,计算dist
        if black_pixel_ratio > 0.25:
            debug_touch_hold(f"get_touch_hold_data: frame={frame_num} enter dist branch")
            # 动态阈值
            grey_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            _, binary_roi = cv2.threshold(grey_roi, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            # 轮廓识别
            distances = []
            contours, _ = cv2.findContours(binary_roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                print(f"get_touch_hold_data: frame {frame_num} dist branch has no contours")
                return -1, -1
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
                debug_touch_hold(
                    f"get_touch_hold_data: frame={frame_num} dist candidates={len(distances)}, dist={dist:.3f}"
                )
            else:
                print(f"get_touch_hold_data: frame {frame_num} dist branch found no valid triangle candidates")
                # dist -= roi_radius * 0.08 # 减去尖头的圆球的尺寸

            # # 显示窗口
            # print(f"frame {frame_num}: dist {dist:.2f}")
            # cv2.imshow(f'frame {frame_num}', roi)
            # cv2.waitKey(0)
            # cv2.destroyAllWindows()

        # 视为hold阶段,计算percent_of_hold
        else:
            debug_touch_hold(f"get_touch_hold_data: frame={frame_num} enter percent branch")
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
            denom = w // 2 - 1
            if denom <= 0:
                print(f"get_touch_hold_data: frame {frame_num} invalid percent denominator, w={w}")
                return -1, -1
            percent_of_hold = counter / denom / 2 # 除以2是因为只扫描了一半宽度
            debug_touch_hold(
                f"get_touch_hold_data: frame={frame_num} percent counter={counter}, percent={percent_of_hold:.3f}"
            )

        return dist, percent_of_hold

    except Exception as e:
        print(f"get_touch_hold_data - frame {frame_num}: exception {e}")
        return -1, -1




def diamond_polar_transform(roi):
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




def stretch_transformed_image(roi):
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




def apply_hsv_threshold(roi):
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

