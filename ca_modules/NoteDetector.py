# filepath: d:\git\mai-chart-analyse\ca_modules\NoteDetector.py
import cv2
import numpy as np
import os

class NoteDetector:
    def __init__(self):
        self.track_mask_path = 'static/template/track_mask.png'
        self.track_mask = None
        self.threshold = 160
        self.tap_notes = {}
        self.slide_notes = {}
        self.hold_notes = {}
        # dict{frame_counter: detected_notes}
        #                     notes_list( note_dict{ bbox, center, radius, confidence } )


    def process(self, cap, state, limit_frame: int = 0):
        '''main rpocess'''
        try:
            print('Note Detector', end="\r")
            
            self.load_track_mask(state)
            total_frames = state['total_frames']
            limit_frame = limit_frame if limit_frame > 0 else total_frames

            closing_regions, closing_kernel = self.define_closing_region(state)

            frame_counter = state['chart_start']
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_counter)  # Set to chart start

            tap_radius_min = int(state['circle_radius'] * 0.09)
            tap_radius_max = int(state['circle_radius'] * 0.12)

            slide_radius_min = int(state['circle_radius'] * 0.04)
            slide_radius_max = int(state['circle_radius'] * 0.18)

            hold_radius_min = int(state['circle_radius'] * 0.08)
            hold_radius_max = int(state['circle_radius'] * 0.6)
            hold_width = int(state['circle_radius'] * 0.18)
            hold_size = (hold_radius_min, hold_radius_max, hold_width)

            # main loop
            while frame_counter < limit_frame:
                ret, raw_frame = cap.read()
                if not ret: break # end of video
                print(f"Note Detector...{frame_counter}/{total_frames}", end="\r")
                
                # 转换为灰度图，二值化突出屏幕部分 (大于阈值的全白)
                gray_frame = cv2.cvtColor(raw_frame, cv2.COLOR_BGR2GRAY)
                _, frame = cv2.threshold(gray_frame, self.threshold, 255, cv2.THRESH_BINARY)
                # 将掩码应用到二值化图像上
                frame = cv2.bitwise_and(frame, self.track_mask)
                # 形态学闭运算
                for x1, y1, x2, y2 in closing_regions:
                    frame[y1:y2, x1:x2] = cv2.morphologyEx(frame[y1:y2, x1:x2], cv2.MORPH_CLOSE, closing_kernel, iterations=1)

                # 获取轮廓及其最小包围圆
                contour_circle_list = []
                contours, _ = cv2.findContours(frame, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
                if not contours:
                    continue
                for contour in contours:
                    (x, y), radius = cv2.minEnclosingCircle(contour)
                    # 将轮廓和圆心坐标/半径一起存储
                    contour_circle_list.append({
                        'contour': contour,
                        'center': (int(x), int(y)),
                        'radius': int(radius)
                    })

                # Detect tap notes
                self.tap_notes[frame_counter] = self.detect_tap_notes(contour_circle_list, tap_radius_min, tap_radius_max)
                # Detect slide notes
                self.slide_notes[frame_counter] = self.detect_slide_notes(contour_circle_list, slide_radius_min, slide_radius_max)
                # Detect hold notes
                self.hold_notes[frame_counter] = self.detect_hold_notes(contour_circle_list, hold_size, state)

                frame_counter += 1

            print("Note Detector...Done             ")
            if state['debug']: 
                self.display_preview(cap, state)

        except Exception as e:
            raise Exception(f"Error in NoteDetector: {e}")
        

    def define_closing_region(self, state):

        closing_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (10, 10))
        cx, cy = state['circle_center']
        r = state['circle_radius']
        
        a = int(r * 0.22)
        b = int(r * 0.17)
        c = int(r * 0.12)

        # x1, y1, x2, y2
        closing_regions = [(cx+c, cy-a, cx+b, cy-b), # 1
                           (cx+b, cy-b, cx+a, cy-c), # 2
                           (cx+b, cy+c, cx+a, cy+b), # 3
                           (cx+c, cy+b, cx+b, cy+a), # 4
                           (cx-b, cy+b, cx-c, cy+a), # 5
                           (cx-a, cy+c, cx-b, cy+b), # 6
                           (cx-a, cy-b, cx-b, cy-c), # 7
                           (cx-b, cy-a, cx-c, cy-b)] # 8
        
        return closing_regions, closing_kernel
    

    def load_track_mask(self, state):
        try:
            size = int(state['circle_radius'] * 1.14 * 2)
            track_mask_pic = cv2.imread(self.track_mask_path, cv2.IMREAD_GRAYSCALE)
            track_mask_pic = cv2.resize(track_mask_pic, (size, size))
            # white areas become 255, gray areas become 0
            _, track_mask = cv2.threshold(track_mask_pic, 254, 255, cv2.THRESH_BINARY)
            # 创建一个与视频帧大小相同的完整掩码
            frame_height = int(state['video_height'])
            frame_width = int(state['video_width'])
            mask_h, mask_w = track_mask.shape
            # 创建一个纯白的背景
            full_mask = np.ones((frame_height, frame_width), dtype=np.uint8) * 255
            # 计算偏移量以将track_mask居中
            x_offset = (frame_width - mask_w) // 2
            y_offset = (frame_height - mask_h) // 2
            # 计算目标区域（在 full_mask 上），处理 mask 比 frame 大的情况
            dest_x_start = max(0, x_offset)
            dest_y_start = max(0, y_offset)
            dest_x_end = min(frame_width, x_offset + mask_w)
            dest_y_end = min(frame_height, y_offset + mask_h)
            # 计算源区域（从 track_mask 上裁剪）
            src_x_start = max(0, -x_offset)
            src_y_start = max(0, -y_offset)
            src_x_end = src_x_start + (dest_x_end - dest_x_start)
            src_y_end = src_y_start + (dest_y_end - dest_y_start)
            # 如果有重叠区域，则将裁剪后的 mask 复制到 full_mask 的中心
            if dest_x_end > dest_x_start and dest_y_end > dest_y_start:
                full_mask[dest_y_start:dest_y_end, dest_x_start:dest_x_end] = \
                    track_mask[src_y_start:src_y_end, src_x_start:src_x_end]
            # 使用新的完整掩码
            self.track_mask = full_mask
        except Exception as e:
            raise Exception(f"Error in load_track_mask: {e}")


    def detect_tap_notes(self, contour_circle_list, tap_radius_min, tap_radius_max):
        """识别圆形音符
        arg: contour_circle_list, tap_radius_min, tap_radius_max
        ret: tap_notes_list(bbox, center, radius, confidence)
        """
        try:
            circles = []
            # 遍历所有轮廓，寻找尺寸合适的圆
            for item in contour_circle_list:
                contour = item['contour']
                (x, y) = item['center']
                radius = item['radius']
                # 忽略尺寸不对的轮廓
                if radius < tap_radius_min or radius > tap_radius_max: continue
                # 验证轮廓是否接近圆形
                area = cv2.contourArea(contour)
                circle_area = 3.14 * radius * radius
                circularity = area / circle_area
                # 如果轮廓接近圆形（圆形度大于0.9）
                if circularity > 0.9:
                    circles.append((x, y, radius))

            if circles is None:
                return []
            
            detected_notes = []
            
            for (x, y, r) in circles:
                note = {
                    'bbox': (x - r, y - r, x + r, y + r),
                    'center': (x, y),
                    'radius': r,
                }
                detected_notes.append(note)
            
            return detected_notes
            
        except Exception as e:
            raise Exception(f"Error in detect_tap_notes: {e}")
        

    def detect_slide_notes(self, contour_circle_list, slide_radius_min, slide_radius_max):
        '''Detect slide notes
        arg: contour_circle_list, slide_radius_min, slide_radius_max
        ret: slide_notes_list(bbox, center, radius, confidence)
        '''
        try:
            slides = {}

            # 遍历所有轮廓，寻找尺寸合适的轮廓
            for item in contour_circle_list:
                contour = item['contour']
                (x, y) = item['center']
                radius = item['radius']
                # 忽略尺寸不对的轮廓
                if radius < slide_radius_min or radius > slide_radius_max: continue
                # 验证轮廓是否接近星形（圆形度0.4-0.5）
                area = cv2.contourArea(contour)
                circle_area = 3.14 * radius * radius
                circularity = area / circle_area
                if not 0.41 <= circularity <= 0.5: continue
                # 使用凸包缺陷检测
                try:
                    hull = cv2.convexHull(contour, returnPoints=False)
                    defects = cv2.convexityDefects(contour, hull)
                    if defects is None: continue
                except cv2.error as e:
                    continue
                # 五角星应该有5个明显的凹陷点
                significant_defects = 0
                for i in range(defects.shape[0]):
                    s, e, f, d = defects[i, 0]
                    # d是缺陷深度，除以256得到实际像素距离
                    depth = d / 256.0
                    # 如果缺陷深度足够大，认为是一个有效的凹陷
                    if depth > radius * 0.2:
                        significant_defects += 1
                    else:
                        significant_defects -= 1
                if significant_defects != 5: continue
                # 如果中心相近（允许x,y各有±2的误差），保留最大半径的音符
                found_similar = False
                similar_key = None
                for existing_key in slides.keys():
                    if abs(existing_key[0] - x) <= 2 and abs(existing_key[1] - y) <= 2:
                        found_similar = True
                        similar_key = existing_key
                        break
                if found_similar:
                    if slides[similar_key][2] < radius:
                        del slides[similar_key]
                        slides[(x, y)] = (x, y, radius)
                else:
                    slides[(x, y)] = (x, y, radius)
                
            if slides is None:
                return []
            
            detected_notes = []

            for (key, (x, y, r)) in slides.items():
                note = {
                    'bbox': (x - r, y - r, x + r, y + r),
                    'center': (x, y),
                    'radius': r,
                }
                detected_notes.append(note)

            return detected_notes
        
        except Exception as e:
            raise Exception(f"Error in detect_slide_notes: {e}")
        

    def detect_hold_notes(self, contour_circle_list, hold_size, state):
        '''Detect hold notes
        arg: contour_circle_list, hold_size, state
        ret: hold_notes_list(box_points, center, radius, confidence)
        '''
        try:
            hold_radius_min, hold_radius_max, _ = hold_size
            holds = {}

            # 遍历所有轮廓，寻找尺寸合适的轮廓
            for item in contour_circle_list:
                contour = item['contour']
                (x, y) = item['center']
                radius = item['radius']
                # 忽略尺寸不对的轮廓
                if radius < hold_radius_min or radius > hold_radius_max: continue
                # 获取最小包围矩形
                rect = cv2.minAreaRect(contour)
                width, height = rect[1]
                # 检查长宽比 (>1.2)
                aspect_ratio = max(width, height) / min(width, height)
                if aspect_ratio < 1.2: continue
                # 检查填充度 (>0.7)
                area = cv2.contourArea(contour)
                rect_area = width * height
                fill_ratio = area / rect_area
                if fill_ratio < 0.7: continue
                # 检查轮廓是否有连续三个120度的角
                if self.has_three_consecutive_120_angles(contour):
                    box_points = np.intp(cv2.boxPoints(rect))
                    head, tail = self.calculate_head_and_tail(box_points, state, hold_size)
                    holds[tail] = (tail[0], tail[1], head[0], head[1], box_points)
                    continue

            if holds is None:
                return []
            
            detected_notes = []

            for (key, (x1, y1, x2, y2, box_points)) in holds.items():
                note = {
                    'box_points': box_points,
                    'tail': (x1, y1),
                    'head': (x2, y2)
                }
                detected_notes.append(note)

            return detected_notes
        
        except Exception as e:
            raise Exception(f"Error in detect_hold_notes: {e}")
        

    def calculate_head_and_tail(self, box_points, state, hold_size):

        def move_point(x, y, offset, circle_center, circle_radius):
            # calculate direction vector from circle center to point
            point = np.array([x, y])
            center = np.array(circle_center)
            direction_vector = point - center
            # Get distance + offset
            distance_to_center = np.linalg.norm(direction_vector)
            new_distance_to_center = distance_to_center + offset * circle_radius
            # Calculate angle of the point relative to circle center
            point_angle = np.arctan2(direction_vector[1], direction_vector[0])
            if point_angle < 0:
                point_angle += 2 * np.pi  # Convert to [0, 2π] range
            # Find the closest line angle
            line_angles = np.array([22.5, 67.5, 112.5, 157.5, 202.5, 247.5, 292.5, 337.5]) * np.pi / 180
            angle_differences = np.abs(line_angles - point_angle)
            # Handle wraparound (e.g., 157.5° vs 22.5°)
            angle_differences = np.minimum(angle_differences, 2*np.pi - angle_differences)
            closest_line_index = np.argmin(angle_differences)
            closest_angle = line_angles[closest_line_index]
            # Calculate new point position on the closest line
            new_x = center[0] + new_distance_to_center * np.cos(closest_angle)
            new_y = center[1] + new_distance_to_center * np.sin(closest_angle)
            
            return (int(new_x), int(new_y))

        circle_center = state['circle_center']
        circle_radius = state['circle_radius']
        # 按点到圆心的距离排序
        distances = [np.linalg.norm(np.array(p) - np.array(circle_center)) for p in box_points]
        sorted_indices = np.argsort(distances)
        # 近的两点是尾
        tail_1 = box_points[sorted_indices[0]]
        tail_2 = box_points[sorted_indices[1]]
        # 远的两点是头
        head_1 = box_points[sorted_indices[2]]
        head_2 = box_points[sorted_indices[3]]
        # 计算两边的中点
        tail_midpoint_x = (tail_1[0] + tail_2[0]) // 2
        tail_midpoint_y = (tail_1[1] + tail_2[1]) // 2
        head_midpoint_x = (head_1[0] + head_2[0]) // 2
        head_midpoint_y = (head_1[1] + head_2[1]) // 2
        # 判断当前轮廓内外
        width = np.linalg.norm(np.array(tail_1) - np.array(tail_2))
        _, _, hold_width = hold_size
        offset = 0.08 if width < hold_width else 0.12
        # 移动头尾
        final_head = move_point(head_midpoint_x, head_midpoint_y, (-1*offset), circle_center, circle_radius)
        final_tail = move_point(tail_midpoint_x, tail_midpoint_y, offset, circle_center, circle_radius)
            
        return final_head, final_tail


    def has_three_consecutive_120_angles(self, contour):
        '''检查轮廓是否有连续三个角都接近120度'''
        try:
            # 获得多边形近似
            epsilon = 0.01 * cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, epsilon, True)
            
            # 至少需要5个点
            if len(approx) < 5:
                return False
                
            # 计算所有角度
            angles = []
            n = len(approx)
            for i in range(n):
                p1 = approx[i-1][0]
                p2 = approx[i][0]
                p3 = approx[(i+1) % n][0]
                
                # 计算向量
                v1 = p1 - p2
                v2 = p3 - p2
                
                # 计算角度
                cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
                cos_angle = np.clip(cos_angle, -1, 1)  # 防止数值误差
                angle = np.arccos(cos_angle) * 180 / np.pi
                angles.append(angle)
            
            # 检查是否有连续三个角都接近120度（允许±15度的误差）
            target_angle = 120
            tolerance = 15
            
            consecutive_count = 0
            max_consecutive = 0
            
            for angle in angles:
                if abs(angle - target_angle) <= tolerance:
                    consecutive_count += 1
                    max_consecutive = max(max_consecutive, consecutive_count)
                else:
                    consecutive_count = 0
            
            # 检查环形连续性（最后几个和开头几个角度）
            if consecutive_count > 0:
                for angle in angles:
                    if abs(angle - target_angle) <= tolerance:
                        consecutive_count += 1
                        max_consecutive = max(max_consecutive, consecutive_count)
                    else:
                        break
            
            return max_consecutive >= 3
            
        except Exception as e:
            return False
        

    def display_preview(self, cap, state):
        """Display preview"""
                
        try:
            frame_counter = state['chart_start']
            total_frames = state['total_frames']
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_counter) # Set to chart start

            closing_regions, closing_kernel = self.define_closing_region(state)

            window_name = 'Note Detector Preview'
            cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)
            
            # Display frames
            while True:
                ret, raw_frame = cap.read()
                if not ret: break  # end of video
                
                # 转换为灰度图，二值化突出屏幕部分 (大于阈值的全白)
                gray = cv2.cvtColor(raw_frame, cv2.COLOR_BGR2GRAY)
                _, frame = cv2.threshold(gray, self.threshold, 255, cv2.THRESH_BINARY)
                # 将掩码应用到二值化图像上
                frame = cv2.bitwise_and(frame, self.track_mask)
                # 形态学闭运算
                for x1, y1, x2, y2 in closing_regions:
                    frame[y1:y2, x1:x2] = cv2.morphologyEx(frame[y1:y2, x1:x2], cv2.MORPH_CLOSE, closing_kernel, iterations=1)
                # 将单通道黑白图像转换为3通道，以支持彩色绘制
                frame_final = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)

                # 绘制闭运算区域
                for x1, y1, x2, y2 in closing_regions:
                    cv2.rectangle(frame_final, (x1, y1), (x2, y2), (255, 0, 255), 2)

                # 绘制识别音符
                result_frame = self.debug_draw_tap_notes(frame_final, frame_counter)
                result_frame = self.debug_draw_slide_notes(result_frame, frame_counter)
                result_frame = self.debug_draw_hold_notes(result_frame, frame_counter)

                # 添加文字
                cv2.putText(result_frame, f"Frame: {frame_counter}/{total_frames}", 
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                cv2.putText(result_frame, "Press 'q' to quit, 'arrow key' to go back", 
                            (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)

                # resize
                scale = 1000 / state['video_height']
                new_size = (int(state['video_width']*scale), 1000)
                result_frame = cv2.resize(result_frame, new_size, interpolation=cv2.INTER_LINEAR)
                cv2.imshow(window_name, result_frame)

                key = cv2.waitKey(0) & 0xFF
                if key == ord('q'): # quit
                    break
                elif key == 0: # '方向键'
                    frame_counter = max(0, frame_counter - 1) # Last frame
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_counter)
                else:
                    frame_counter += 1 # Next frame
            
            cv2.destroyWindow(window_name)

        except Exception as e:
            cv2.destroyAllWindows()
            raise Exception(f"Error in display_preview: {e}")          
            

    def debug_draw_tap_notes(self, frame, frame_counter):
        """Draw tap notes on frame"""

        try:
            detected_notes = self.tap_notes.get(frame_counter, [])
            # Draw notes counter
            cv2.putText(frame, f"Tap: {len(detected_notes)}",
                        (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            
            if not detected_notes: return frame

            for i, note in enumerate(detected_notes):
                bbox = note['bbox']
                center = note['center']
                radius = note.get('radius')
                
                # Draw bounding box (rectangle)
                cv2.rectangle(frame, (bbox[0], bbox[1]), (bbox[2], bbox[3]), (0, 255, 0), 2)
                
                # Draw circular outline if radius is available
                if radius is not None:
                    cv2.circle(frame, center, radius, (255, 0, 0), 2)
                
                # Draw center point
                cv2.circle(frame, center, 5, (0, 0, 255), -1)
                
                # Draw note index and radius info
                cv2.putText(frame, f"{radius}", 
                            (center[0] + 10, center[1] + 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
                
            return frame
            
        except Exception as e:
            raise Exception(f"Error in debug_draw_preview_frame: {e}")
        

    def debug_draw_slide_notes(self, frame, frame_counter):
        try:
            detected_notes = self.slide_notes.get(frame_counter, [])
            # Draw notes counter
            cv2.putText(frame, f"Slide: {len(detected_notes)}",
                        (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            
            if not detected_notes: return frame

            for i, note in enumerate(detected_notes):
                bbox = note['bbox']
                center = note['center']
                radius = note.get('radius')
                
                # Draw bounding box (rectangle)
                cv2.rectangle(frame, (bbox[0], bbox[1]), (bbox[2], bbox[3]), (0, 255, 0), 2)
                
                # Draw center point
                cv2.circle(frame, center, 5, (0, 0, 255), -1)
                
                # Draw note index and radius info
                cv2.putText(frame, f"{radius}", 
                            (center[0] + 10, center[1] + 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
                
            return frame
        
        except Exception as e:
            raise Exception(f"Error in debug_draw_slide_notes: {e}")
        

    def debug_draw_hold_notes(self, frame, frame_counter):
        try:
            detected_notes = self.hold_notes.get(frame_counter, [])
            # Draw notes counter
            cv2.putText(frame, f"Hold: {len(detected_notes)}",
                        (10, 150), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            
            if not detected_notes: return frame

            for i, note in enumerate(detected_notes):
                bbox = note['box_points']
                tail = note['tail']
                head = note['head']
                
                # Draw bounding box (rotated rectangle)
                cv2.polylines(frame, [bbox], isClosed=True, color=(0, 255, 0), thickness=2)
                
                # Draw head and tail points
                cv2.circle(frame, tail, 5, (0, 0, 255), -1)
                cv2.circle(frame, head, 5, (0, 0, 255), -1)
                
                # Draw line segment between head and tail
                cv2.line(frame, tail, head, (255, 0, 255), 1)
                
            return frame
        
        except Exception as e:
            raise Exception(f"Error in debug_draw_hold_notes: {e}")


if __name__ == "__main__":
    detector = NoteDetector()
    try:
        # deicide 474 ariake 315
        video_path = r"C:\Users\ck273\Desktop\ウェルテル\[maimai谱面确认] DEICIDE MASTER-p01-116.mp4"
        cap = cv2.VideoCapture(video_path)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        state = {
            'chart_start': 500,
            'total_frames': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            'circle_center': (959, 539),
            'circle_radius': 474,
            'video_height': min(width, height),
            'video_width': max(width, height),
            'debug': True
        }
        detector.process(cap, state, 1000)
        cap.release()
        
    except Exception as e:
        print(f"Error: {e}")
