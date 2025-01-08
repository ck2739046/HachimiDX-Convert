import cv2
import numpy as np

class JudgeLineDetector:
    def __init__(self):
        self.circle_center = None  # (x, y)
        self.circle_radius = None


    def detect_circle(self, cap, state) -> bool:
        """检测判定线圆圈
        arg: cap, state(video_width, video_height)
        ret: bool
        设置circle_center, circle_radius
        采样20个黑帧进行圆形检测, 采用最常见的圆形作为判定线
        """

        try:
            height = state["video_height"]
            x_offset = int(-0.003*height) # 补偿-0.3%
            y_offset = 0
            r_offset = 0
            black_traget = 20

            # Reset to start of video
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

            # Collect target black frames
            black_frames = []
            black_frames_processed = 0
            total_pixels = state["video_width"] * state["video_height"]
            while True:
                ret, frame = cap.read()
                if not ret: break # end of video
                if black_frames_processed >= black_traget: break
                # count black pixels
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                black_pixels = np.sum(gray < 20)
                # check if frame is mostly black (90%)
                is_frame_black = black_pixels / total_pixels > 0.9
                if not is_frame_black: continue
                # add frame
                black_frames.append(frame)
                black_frames_processed += 1

            if not black_frames:
                print("detect circle: No black frames detected")
                return False

            # Process the collected black frames
            circles_detected = []
            for frame in black_frames:
                # 转换为灰度图，二值化突出白色部分
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                _, binary = cv2.threshold(gray, 220, 255, cv2.THRESH_BINARY)
                # detect circle
                circles = cv2.HoughCircles(
                    binary,
                    cv2.HOUGH_GRADIENT,
                    dp=1,                         # 保存原分辨率
                    minDist=height,               # 只检测一个圆
                    param1=50,                    
                    param2=30,
                    minRadius=int(height * 0.2),  # 最小半径为30%
                    maxRadius=int(height * 0.5)   # 最大半径为50%
                )
                if circles is not None:
                    circles = np.uint16(np.around(circles))
                    for circle in circles[0, :]:
                        circles_detected.append((circle[0], circle[1], circle[2]))

            if not circles_detected:
                print("detect circle: No circle detected")
                return False
            
            # 取出现次数最多的圆
            circles_detected = [(int(x), int(y), int(r)) for x, y, r in circles_detected]
            most_common = max(set(circles_detected), key=circles_detected.count)
            self.circle_center = (most_common[0]+x_offset, most_common[1]+y_offset)
            self.circle_radius = most_common[2]+r_offset

            print(f"detect circle: {self.circle_center}, {self.circle_radius} of {len(circles_detected)}")
            return True

        except Exception as e:
            print(f"Error in detect_circle: {e}")
            return False

    def draw_circle(self, frame):
        """在帧上绘制检测到的圆"""
        if self.circle_center and self.circle_radius:
            cv2.circle(frame, self.circle_center, self.circle_radius, (0, 255, 0), 2)
            cv2.circle(frame, self.circle_center, 2, (0, 0, 255), 3)
        return frame

    def process(self, cap, state) -> bool:
        """主处理函数"""
        try:
            # detect circle
            if not self.detect_circle(cap, state):
                print("judge_line_detector: Fail detecte circle")
                return False

            # detect touch areas
            template = self.load_template()
            regions = self.detect_regions(template)
            self.touch_areas = self.group_regions(regions)

            # Reset video position
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

            # Display preview
            if state['debug']:
                window_name = "Judge Line Preview"
                cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
                while True:
                    ret, frame = cap.read()
                    if not ret:break
                    frame = self.draw_circle(frame)
                    frame = self.draw_touch_areas(frame)
                    cv2.imshow(window_name, frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                cv2.destroyWindow(window_name)

            return True

        except Exception as e:
            print(f"Error in process: {e}")
            return False


    def load_template(self):
        """Load and process template image"""
        template = cv2.imread("static/judge_area.png")
        if template is None:
            raise Exception("Cannot load template image")
            
        # Resize template to match circle
        if self.circle_radius:
            size = self.circle_radius * 2
            template = cv2.resize(template, (size, size))
        return template
    

    def detect_regions(self, template):
        """Process template and detect individual regions"""
        # Convert template to grayscale
        gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        
        # Adaptive threshold to find gray regions
        binary = cv2.adaptiveThreshold(
            gray, 
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            11,
            2
        )

        # Find contours
        contours, _ = cv2.findContours(
            binary,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        regions = []
        # Process each contour
        for contour in contours:
            # Approximate polygon
            epsilon = 0.01 * cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, epsilon, True)

            # Calculate center
            M = cv2.moments(approx)
            if M["m00"] == 0:
                continue
            
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])

            regions.append({
                "center": (cx, cy),
                "polygon": approx,
                "dist_from_center": np.sqrt((cx - self.circle_radius)**2 + 
                                        (cy - self.circle_radius)**2)
            })
        
        return regions


    def group_regions(self, regions):
        """Group regions into ABCDE and sort clockwise"""
        # Sort by distance from center
        regions.sort(key=lambda x: x["dist_from_center"])
        
        # Group into ABCDE
        group_size = len(regions) // 5
        groups = {
            'C': regions[:2],
            'B': regions[2:10],
            'E': regions[10:18],
            'A': regions[18:26],
            'D': regions[26:]
        }
        
        touch_areas = {}
        
        # For each group, sort clockwise from 12 o'clock and label
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


    def draw_touch_areas(self, frame):
        """Draw detected touch areas with labels"""
        if hasattr(self, 'touch_areas'):
            # Draw instruction text
            cv2.putText(
                frame,
                "Press Q to quit",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2
            )

            for label, area in self.touch_areas.items():
                # Draw polygon
                points = area["polygon"]
                points = np.array([[p[0][0] + self.circle_center[0] - self.circle_radius,
                                  p[0][1] + self.circle_center[1] - self.circle_radius] 
                                  for p in points])
                points = points.reshape((-1, 1, 2))
                cv2.polylines(frame, [points], True, (0, 255, 255), 2)
                
                # Draw center and label
                center = area["center"]
                cv2.circle(frame, center, 3, (0, 0, 255), -1)
                cv2.putText(
                    frame,
                    label,
                    center,
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, # font size
                    (255, 255, 255),
                    2    # font thickness
                )
        return frame


if __name__ == "__main__":
    # prepare parameters from ca_core.py
    # cap
    video_path = r"C:\Code\Ariake.mp4"
    cap = cv2.VideoCapture(video_path)
    # state
    state = {}
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    state["video_width"] = max(width, height)
    state["video_height"] = min(width, height)
    state["debug"] = True
    # call process()
    detector = JudgeLineDetector()
    detector.process(cap, state)
    cap.release()