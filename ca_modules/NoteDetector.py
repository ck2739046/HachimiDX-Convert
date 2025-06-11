# filepath: d:\git\mai-chart-analyse\ca_modules\NoteDetector.py
import cv2
import numpy as np
import os

class NoteDetector:
    def __init__(self):
        self.threshold = 200
        self.tap_template_path = "static/template/tap.png"
        self.tap_notes = {}
        # dict{frame_counter: detected_notes}
        #                     notes_list( note_dict{ bbox, center, radius, confidence } )


    def process(self, cap, state, limit_frame: int = 0):
        '''main rpocess'''
        try:
            print('Note Detector', end="\r")
            
            total_frames = state['total_frames']
            limit_frame = limit_frame if limit_frame > 0 else total_frames

            frame_counter = state['chart_start']
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_counter)  # Set to chart start

            tap_radius_min = int(state['circle_radius'] * 0.09)
            tap_radius_max = int(state['circle_radius'] * 0.12)

            # main loop
            while frame_counter < limit_frame:
                ret, frame = cap.read()
                if not ret: break # end of video
                print(f"Note Detector...{frame_counter}/{total_frames}", end="\r")

                # 转换为灰度图，二值化突出屏幕部分 (大于阈值的全白)
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                _, pure_frame = cv2.threshold(gray, self.threshold, 255, cv2.THRESH_BINARY)

                # Detect tap notes
                detected_notes = self.detect_tap_notes(pure_frame, tap_radius_min, tap_radius_max)
                self.tap_notes[frame_counter] = detected_notes

                frame_counter += 1

            print("Note Detector...Done             ")
            if state['debug']: 
                self.display_preview(cap, state)

        except Exception as e:
            raise Exception(f"Error in NoteDetector: {e}")
        
        
    def load_tap_template(self):
        """Load tap template and process it with alpha thresholding and edge detection
        ret: processed template and contours
        """
        try:
            print("Note Detector...Loading tap template...", end="\r")
            
            # Get full path to template
            template_path_full = os.path.join(os.path.dirname(os.path.dirname(__file__)), self.tap_template_path)
            if not os.path.exists(template_path_full):
                raise Exception("load_tap_template: Template tap.png not found")
            
            # Load image with alpha channel
            template_bgra = cv2.imread(template_path_full, cv2.IMREAD_UNCHANGED)
            if template_bgra is None:
                raise Exception("load_tap_template: Cannot load tap.png")
            
            # Check if image has alpha channel
            if template_bgra.shape[2] != 4:
                raise Exception("load_tap_template: tap.png must have alpha channel")
            
            # Extract alpha channel
            alpha_channel = template_bgra[:, :, 3]
            
            # Apply threshold to alpha channel (threshold = 200)
            _, binary_alpha = cv2.threshold(alpha_channel, 200, 255, cv2.THRESH_BINARY)
            
            # Apply edge detection (Canny)
            edges = cv2.Canny(binary_alpha, 50, 150)
            
            # Find contours from edge detection
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if not contours:
                raise Exception("load_tap_template: No contours found in tap template")
            
            # Store the original template (BGR) and contours
            self.tap_template = cv2.cvtColor(template_bgra[:, :, :3], cv2.COLOR_BGR2RGB)  # Convert to RGB for matplotlib
            self.tap_contours = contours
            print("Note Detector...Loading tap template...Done                    ")
            print(f"  Found {len(contours)} contour(s) in tap template")
            
            return self.tap_template, self.tap_contours
            
        except Exception as e:
            raise Exception(f"Error in load_tap_template: {e}")
    

    def visualize_tap_template(self):
        """Visualize the tap template with contours in a new window
        """
        try:
            if self.tap_template is None or self.tap_contours is None:
                print("Note Detector: Loading template first...")
                self.load_tap_template()
            
            print("Note Detector...Visualizing tap template...", end="\r")
            
            # Convert RGB back to BGR for OpenCV display
            template_bgr = cv2.cvtColor(self.tap_template, cv2.COLOR_RGB2BGR)
            
            # Create a copy for drawing contours
            template_with_contours = template_bgr.copy()
            
            # Draw contours on the template
            cv2.drawContours(template_with_contours, self.tap_contours, -1, (0, 0, 255), 2)
            
            # Create side-by-side display
            height = max(template_bgr.shape[0], template_with_contours.shape[0])
            width = template_bgr.shape[1] + template_with_contours.shape[1] + 20  # Add gap
            
            # Create combined image
            combined = np.zeros((height, width, 3), dtype=np.uint8)
            
            # Place original template on the left
            combined[:template_bgr.shape[0], :template_bgr.shape[1]] = template_bgr
            
            # Place template with contours on the right
            start_x = template_bgr.shape[1] + 20
            combined[:template_with_contours.shape[0], start_x:start_x+template_with_contours.shape[1]] = template_with_contours
            
            # Add text labels
            cv2.putText(combined, "Original", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            cv2.putText(combined, f"With Contours ({len(self.tap_contours)} found)", 
                       (start_x + 10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            
            # Display the window
            window_name = "Tap Template Visualization"
            cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)
            cv2.imshow(window_name, combined)
            
            print("Note Detector...Visualizing tap template...Done                    ")
            print("  Press any key to close the visualization window")
            
            # Wait for user input            cv2.waitKey(0)
            cv2.destroyWindow(window_name)
            
        except Exception as e:
            raise Exception(f"Error in visualize_tap_template: {e}")
    

    def detect_tap_notes(self, frame, tap_radius_min, tap_radius_max):
        """使用轮廓检测，识别圆形音符
        arg: pure_frame, tap_radius_min, tap_radius_max
        ret: tap_notes_list(bbox, center, radius, confidence)
        """
        try:
            # 寻找轮廓
            contours, _ = cv2.findContours(frame, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                raise Exception("detect_circle: No contours detected")
            
            # 遍历所有轮廓，寻找尺寸合适的圆
            circles = []
            for contour in contours:
                # 计算最小包围圆
                (x, y), radius = cv2.minEnclosingCircle(contour)
                # 忽略尺寸不对的轮廓
                if radius < tap_radius_min or radius > tap_radius_max: continue
                # 验证轮廓是否接近圆形
                area = cv2.contourArea(contour)
                circle_area = 3.14 * radius * radius
                circularity = area / circle_area
                # 如果轮廓接近圆形（圆形度大于0.9）
                if circularity > 0.9:
                    circles.append((int(x), int(y), int(radius)))

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
        

    def display_preview(self, cap, state):
        """Display preview"""
                
        try:
            frame_counter = state['chart_start']
            total_frames = state['total_frames']
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_counter)  # Set to chart start

            window_name = 'Note Detector Preview'
            cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)
            
            # Display frames
            while True:
                ret, frame = cap.read()
                if not ret: break  # end of video

                # 转换为灰度图，二值化突出屏幕部分 (大于阈值的全白)
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                _, frame1 = cv2.threshold(gray, self.threshold, 255, cv2.THRESH_BINARY)
                # 将单通道黑白图像转换为3通道，以支持彩色绘制
                frame2 = cv2.cvtColor(frame1, cv2.COLOR_GRAY2BGR)

                result_frame = self.debug_draw_tap_notes(frame2, frame_counter)

                # Add frame info
                cv2.putText(result_frame, f"Frame: {frame_counter}/{total_frames}", 
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                cv2.putText(result_frame, "Press 'q' to quit", 
                            (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)

                cv2.imshow(window_name, result_frame)

                key = cv2.waitKey(0) & 0xFF
                if key == ord('q'): # quit
                    break
                frame_counter += 1
            
            cv2.destroyWindow(window_name)

        except Exception as e:
            cv2.destroyAllWindows()
            raise Exception(f"Error in display_preview: {e}")          
            

    def debug_draw_tap_notes(self, frame, frame_counter):
        """Draw tap notes on frame"""

        try:
            detected_notes = self.tap_notes.get(frame_counter, [])
            # Draw notes counter
            cv2.putText(frame, f"Notes: {len(detected_notes)}",
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


if __name__ == "__main__":
    detector = NoteDetector()
    try:
        # Load and visualize the template
        #detector.load_tap_template()
        #detector.visualize_tap_template()

        # deicide 474 ariake 315
        video_path = r"C:\Users\ck273\Desktop\ウェルテル\[maimai谱面确认] DEICIDE MASTER-p01-116.mp4"
        cap = cv2.VideoCapture(video_path)
        state = {
            'chart_start': 2100,
            'total_frames': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            'circle_radius': 474,
            'debug': True
        }
        detector.process(cap, state, 2400)
        cap.release()
        
    except Exception as e:
        print(f"Error: {e}")
