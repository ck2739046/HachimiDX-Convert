import cv2
import numpy as np

class JudgeLineDetector:
    def __init__(self):
        self.circle_center = None  # (x, y)
        self.circle_radius = None
        self.template_path = "static/template/judge_area.png"
        self.touch_areas = None


    def process(self, cap, state: dict) -> tuple:
        """main process
        arg: cap, state(video_width, video_height, debug)
        ret: circle_center, circle_radius,
             touch_areas{label: {center, polygon, original_pos}},
             chart_start
        """
        try:
            print("Judge Line Detector...", end="\r")

            # detect circle
            self.circle_center, self.circle_radius, chart_start = self.detect_circle(cap, state)

            # detect touch areas
            template = self.load_template()
            regions = self.detect_regions(template)
            self.touch_areas = self.organize_regions(regions)

            # display preview
            print("Judge Line Detector...Done                       ")
            if state['debug']:
                print(f"  DEBUG: O {self.circle_center}, R {self.circle_radius}")
                self.display_preview(cap, state)

            # Reset to start of video and return
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            return (self.circle_center, self.circle_radius, self.touch_areas, chart_start)

        except Exception as e:
            raise Exception(f"Error in JudgeLineDetector: {e}")


    def detect_circle(self, cap, state, target=15) -> list:
        """采样15个帧, 检测判定线圆形，返回圆心和半径
        arg: cap, state(video_height, total_frames), target(可选,默认15)
        ret: circle_center(x, y), circle_radius, chart_start
        """
        try:
            print(f"Judge Line Detector...Detect_circle...", end="\r")

            frame_counter = 0
            total_frames = state["total_frames"]
            circles_detected = []
            circles = 0
            r_small = int(state["video_height"] * 0.3)
            r_large = int(state["video_height"] * 0.6)

            # Process frames
            while frame_counter < total_frames:
                ret, frame = cap.read()
                if not ret: break # end of video
                print(f"Judge Line Detector...Detect_circle...{frame_counter}/{total_frames}", end="\r")

                # 转换为灰度图，二值化突出屏幕部分 (大于180的全白)
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                _, binary = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)

                # 寻找轮廓
                contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if not contours:
                    raise Exception("detect_circle: No contours detected")
                
                # 遍历所有轮廓，寻找最圆的轮廓
                valid_circles = []
                for contour in contours:
                    # 计算最小包围圆
                    (x, y), radius = cv2.minEnclosingCircle(contour)
                    # 忽略尺寸不对的轮廓
                    if radius < r_small or radius > r_large: continue
                    # 验证轮廓是否接近圆形
                    area = cv2.contourArea(contour)
                    circle_area = 3.14 * radius * radius
                    circularity = area / circle_area
                    # 如果轮廓接近圆形（圆形度大于0.9）
                    if circularity > 0.9:
                        valid_circles.append((x, y, int(radius)))
                
                # 如果找到合适的圆形，选择半径最大的
                if valid_circles:
                    valid_circles.sort(key=lambda x: x[2], reverse=True)
                    x, y, radius = valid_circles[0]
                    judge_line_r = int(radius * 0.88)
                    circles_detected.append((int(x), int(y), judge_line_r))
                    circles += 1
                    if circles == target: break
                    
                frame_counter += 1

            if len(circles_detected) < target:
                raise Exception("detect circle: Not enough circles detected")
            
            # 取出现次数最多的圆
            circles_detected = [(int(x), int(y), int(r)) for x, y, r in circles_detected]
            most_common = max(set(circles_detected), key=circles_detected.count)
            circle_center = (most_common[0], most_common[1])
            circle_radius = most_common[2]

            return circle_center, circle_radius, frame_counter

        except Exception as e:
            raise Exception(f"Error in detect_circle: {e}")


    def load_template(self):
        """Load and resize template image
        arg: self.template_path
        ret: template
        """
        # Load template image
        template = cv2.imread(self.template_path)
        if template is None:
            raise Exception("load_template: Cannot load template image")
        # Resize template to match circle
        size = self.circle_radius * 2
        template = cv2.resize(template, (size, size))
        return template
    

    def detect_regions(self, template) -> list:
        """Process template and detect individual regions
        arg: template, self.circle_radius
        ret: regions[]
        """
        try:
            print(f"Judge Line Detector...Detect_regions...", end="\r")

            # 转换为灰度图并二值化
            gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
            _, binary = cv2.threshold(
                gray, 
                230, # above 230 -> 0 (black)
                255, # below 230 -> 255 (white)
                cv2.THRESH_BINARY_INV # inverse
            )
            # Find contours
            contours, _ = cv2.findContours(
                binary,
                cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE
            )

            if not contours:
                raise Exception("detect_regions: No contours detected")

            regions = []
            # Process each contour
            for contour in contours:
                # Approximate polygon
                epsilon = 0.01 * cv2.arcLength(contour, True) # smaller epsilon -> more points
                approx = cv2.approxPolyDP(contour, epsilon, True)
                # Calculate center
                M = cv2.moments(approx)
                if M["m00"] == 0: continue
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                # Append to regions
                regions.append({
                    "center": (cx, cy),
                    "polygon": approx,
                    "dist_from_center": np.sqrt((cx - self.circle_radius)**2 + 
                                            (cy - self.circle_radius)**2)
                })

            if not regions:
                raise Exception("detect_regions: No regions detected")
            if len(regions) != 33:
                raise Exception(f"detect_regions: Not enough regions detected {len(regions)}")

            return regions
        
        except Exception as e:
            raise Exception(f"Error in detect_regions: {e}")


    def organize_regions(self, regions) -> dict:
        """label regions
        arg: regions[]
        ret: touch_areas{label: {center, polygon, original_pos}}
        """
        try:
            print(f"Judge Line Detector...Organize_regions...", end="\r")

            # Sort by distance from center and group
            regions.sort(key=lambda x: x["dist_from_center"])
            groups = {
                'C': regions[0:1],
                'B': regions[1:9],
                'E': regions[9:17],
                'A': regions[17:25],
                'D': regions[25:]
            }
            
            touch_areas = {}
            # Label regions
            for group_name, group_regions in groups.items():
                # Sort clockwise from 12 o'clock
                group_regions.sort(key=lambda x: (
                    (-np.arctan2(
                        x["center"][0] - self.circle_radius,
                        x["center"][1] - self.circle_radius
                    ) + 3.15) % (2*3.14)
                ))
                
                # Label regions
                for i, region in enumerate(group_regions, 1):
                    label = f"{group_name}{i}"
                    adjusted_center = (
                        region["center"][0] + self.circle_center[0] - self.circle_radius,
                        region["center"][1] + self.circle_center[1] - self.circle_radius
                    )
                    touch_areas[label] = {
                        "center": adjusted_center,
                        "polygon": region["polygon"],
                        "original_pos": region["center"]
                    }
                    
            return touch_areas

        except Exception as e:
            raise Exception(f"Error in organize_regions: {e}")
        

    def display_preview(self, cap, state):
        """Display preview"""
        try:
            # Reset to start of video
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            # Set window
            window_name = "Judge Line Detector Preview"
            cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)
            # Playback control variables
            isPaused = False
            # Show frames
            while True:
                if not isPaused:
                    ret, frame = cap.read()
                    if not ret: break  # end of video
                    new_frame = self.draw_frames(frame, state, isPaused)

                cv2.imshow(window_name, new_frame)

                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break # quit
                if key == ord(' '):
                    isPaused = not isPaused
                    new_frame = self.draw_frames(frame, state, isPaused) # draw paused text

            cv2.destroyWindow(window_name)
            
        except Exception as e:
            raise Exception(f"Error in display_preview: {e}")


    def draw_frames(self, frame, state, isPaused):
        """Draw cirle and touch areas with labels"""
        try:
            screen_r = int(self.circle_radius / 0.88)
            font_size = 1
            thickness = 3

            # Draw circle
            cv2.circle(frame, self.circle_center, self.circle_radius, (0, 255, 0), thickness)
            # Draw circle center
            cv2.circle(frame, self.circle_center, 2, (0, 0, 255), thickness)
            
            # Draw touch areas
            for label, area in self.touch_areas.items():
                # Draw polygon
                points = area["polygon"]
                points = np.array([[p[0][0] + self.circle_center[0] - self.circle_radius,
                                p[0][1] + self.circle_center[1] - self.circle_radius] 
                                for p in points])
                points = points.reshape((-1, 1, 2))
                cv2.polylines(frame, [points], True, (0, 255, 255), thickness)

                center = area["center"]
                # Draw polygon center
                cv2.circle(frame, center, 2, (0, 0, 255), thickness)
                # Draw label
                cv2.putText(
                    frame,
                    label,
                    center,
                    cv2.FONT_HERSHEY_SIMPLEX,
                    font_size,
                    (255, 255, 255),
                    thickness
                )

            # crop and resize frame
            x1 = self.circle_center[0] - screen_r
            x2 = self.circle_center[0] + screen_r
            y1 = self.circle_center[1] - screen_r
            y2 = self.circle_center[1] + screen_r
            frame = frame[y1:y2, x1:x2]
            frame = cv2.resize(frame, (1000, 1000))

            # Draw instruction text
            cv2.putText(
                frame,
                "Press Q to quit",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                font_size,
                (255, 255, 255),
                thickness
            )

            # Draw paused text if paused
            if isPaused:
                cv2.putText(
                    frame,
                    "Paused",
                    (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    font_size,
                    (0, 255, 255),
                    thickness
                )

            return frame
    
        except Exception as e:
            raise Exception(f"Error in draw_frames: {e}")
