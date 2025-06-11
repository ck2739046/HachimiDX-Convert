# filepath: d:\git\mai-chart-analyse\ca_modules\NoteDetector.py
import cv2
import numpy as np
import os

class NoteDetector:
    def __init__(self):
        self.threshold = 210
        self.tap_notes = {}
        self.slide_notes = {}
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
            slide_radius_min = int(state['circle_radius'] * 0.04)
            slide_radius_max = int(state['circle_radius'] * 0.18)

            # main loop
            while frame_counter < limit_frame:
                ret, raw_frame = cap.read()
                if not ret: break # end of video
                print(f"Note Detector...{frame_counter}/{total_frames}", end="\r")

                # 转换为灰度图，二值化突出屏幕部分 (大于阈值的全白)
                gray_frame = cv2.cvtColor(raw_frame, cv2.COLOR_BGR2GRAY)
                _, frame = cv2.threshold(gray_frame, self.threshold, 255, cv2.THRESH_BINARY)

                # 获取轮廓及其最小包围圆
                contour_circle_list = []
                contours, _ = cv2.findContours(frame, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if not contours:
                    raise Exception(f"No contours detected - frame {frame_counter}")
                for contour in contours:
                    (x, y), radius = cv2.minEnclosingCircle(contour)
                    # 将轮廓和圆心坐标/半径一起存储
                    contour_circle_list.append({
                        'contour': contour,
                        'center': (x, y),
                        'radius': radius
                    })

                # Detect tap notes
                detected_tap_notes = self.detect_tap_notes(contour_circle_list, tap_radius_min, tap_radius_max)
                self.tap_notes[frame_counter] = detected_tap_notes
                # Detect slide notes
                detected_slide_notes = self.detect_slide_notes(contour_circle_list, slide_radius_min, slide_radius_max)
                self.slide_notes[frame_counter] = detected_slide_notes

                frame_counter += 1

            print("Note Detector...Done             ")
            if state['debug']: 
                self.display_preview(cap, state)

        except Exception as e:
            raise Exception(f"Error in NoteDetector: {e}")


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
        

    def detect_slide_notes(self, contour_circle_list, slide_radius_min, slide_radius_max):
        '''Detect slide notes
        arg: contour_circle_list, slide_radius_min, slide_radius_max
        ret: slide_notes_list(bbox, center, radius, confidence)
        '''
        try:
            slides = []

            # 遍历所有轮廓，寻找尺寸合适的轮廓
            for item in contour_circle_list:
                contour = item['contour']
                (x, y) = item['center']
                radius = item['radius']
                # 忽略尺寸不对的轮廓
                if radius < slide_radius_min or radius > slide_radius_max: continue
                # 验证轮廓是否接近星形（圆形度大于0.6）
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

                if significant_defects == 5:
                    slides.append((int(x), int(y), int(radius)))
                
            if slides is None:
                return []
            
            detected_notes = []

            for (x, y, r) in slides:
                note = {
                    'bbox': (x - r, y - r, x + r, y + r),
                    'center': (x, y),
                    'radius': r,
                }
                detected_notes.append(note)

            return detected_notes
        
        except Exception as e:
            raise Exception(f"Error in detect_slide_notes: {e}")
        

    def display_preview(self, cap, state):
        """Display preview"""
                
        try:
            frame_counter = state['chart_start']
            total_frames = state['total_frames']
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_counter) # Set to chart start

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
                result_frame = self.debug_draw_slide_notes(result_frame, frame_counter)

                # Add frame info
                cv2.putText(result_frame, f"Frame: {frame_counter}/{total_frames}", 
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                cv2.putText(result_frame, "Press 'q' to quit, 'arrow key' to go back", 
                            (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)

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


if __name__ == "__main__":
    detector = NoteDetector()
    try:
        # deicide 474 ariake 315
        video_path = r"C:\Users\ck273\Desktop\ウェルテル\[maimai谱面确认] DEICIDE MASTER-p01-116.mp4"
        cap = cv2.VideoCapture(video_path)
        state = {
            'chart_start': 2100,
            'total_frames': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            'circle_radius': 474,
            'debug': True
        }
        detector.process(cap, state, 2600)
        cap.release()
        
    except Exception as e:
        print(f"Error: {e}")
