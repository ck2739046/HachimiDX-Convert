import cv2
import numpy as np

class JudgeLineDetector:
    def __init__(self):
        self.circle_center = None  # (x, y)
        self.circle_radius = None
        self.template_path = "static/judge_area.png"
        self.touch_areas = None


    def process(self, cap, state: dict) -> bool:
        """main process"""
        try:
            print("Judge Line Detector...", end="\r")
            # detect circle
            black_frames = self.collect_frames(cap, state)
            self.circle_center, self.circle_radius = self.detect_circle(state, black_frames)

            # detect touch areas
            template = self.load_template()
            regions = self.detect_regions(template)
            self.touch_areas = self.organize_regions(regions)

            # display preview
            if state['debug']: self.display_preview(cap, state)

            print("Judge Line Detector... Done")
            return True

        except Exception as e:
            print(f"Error in process: {e}")
            return False


    def collect_frames(self, cap, state, traget=30) -> list:
        """采样30个黑帧
        arg: cap, state(video_width, video_height), target(可选采样数量 默认20)
        ret: balck_frames[]
        """
        try:
            black_frames = []
            black_frames_processed = 0
            total_pixels = state["video_width"] * state["video_height"]

            # Collect target black frames
            while black_frames_processed < traget:
                ret, frame = cap.read()
                if not ret: break # end of video
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
                raise Exception("collect_frames: No frames detected")

            return black_frames

        except Exception as e:
            raise Exception(f"Error in collect_frames: {e}")


    def detect_circle(self, state, black_frames) -> tuple:
        """对采集的帧进行圆形检测，取出现次数最多的圆
        arg: cap, state(video_height), black_frames[]
        ret: circle_center(x, y), circle_radius
        """
        try:
            height = state["video_height"]
            x_offset = int(-0.003*height) # 补偿-0.3%
            y_offset = 0
            r_offset = 0
            circles_detected = []

            # Process the collected black frames
            for frame in black_frames:
                # 转换为灰度图，二值化突出白色部分
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                _, binary = cv2.threshold(gray, 220, 255, cv2.THRESH_BINARY)
                # detect circle
                circles = cv2.HoughCircles(
                    binary,
                    cv2.HOUGH_GRADIENT,
                    dp=1,                         # 保持原分辨率
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
                raise Exception("detect circle: No circle detected")
            
            # 取出现次数最多的圆
            circles_detected = [(int(x), int(y), int(r)) for x, y, r in circles_detected]
            most_common = max(set(circles_detected), key=circles_detected.count)
            circle_center = (most_common[0]+x_offset, most_common[1]+y_offset)
            circle_radius = most_common[2]+r_offset

            return circle_center, circle_radius

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
            # Convert template to grayscale
            gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
            # Simple threshold to find gray regions
            # background: 0, regions: 255
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
            if len(regions) != 34:
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
            # Sort by distance from center and group
            regions.sort(key=lambda x: x["dist_from_center"])
            groups = {
                'C': regions[:2],
                'B': regions[2:10],
                'E': regions[10:18],
                'A': regions[18:26],
                'D': regions[26:]
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
            # Show frames
            while True:
                ret, frame = cap.read()
                if not ret: break # end of video
                frame = self.draw_frames(frame, state)
                cv2.imshow(window_name, frame)
                if cv2.waitKey(12) & 0xFF == ord('q'):
                    break
            cv2.destroyWindow(window_name)
            
        except Exception as e:
            raise Exception(f"Error in display_preview: {e}")


    def draw_frames(self, frame, state):
        """Draw cirle and touch areas with labels"""
        try:
            font_size = max(0.5, round(state["video_height"]/1000, 1))
            thickness = max(1, round(state["video_height"]/360))

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

            # Resize frame
            return frame
    
        except Exception as e:
            raise Exception(f"Error in draw_frames: {e}")


if __name__ == "__main__":
    # prepare parameters from ca_core.py
    # cap
    video_path = r"C:\Code\Ariake-720p.mp4"
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