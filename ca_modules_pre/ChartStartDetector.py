import cv2
import numpy as np

class ChartStartDetector:
    def __init__(self):
        pass


    def process(self, cap, state: dict) -> float:
        """Main process
        arg: cap, state(circle_center, circle_radius, total_frames, debug)
        ret: first_offset (in seconds)
        """
        try:
            print("Chart Start Detector...", end="\r")

            # Find first frame when the inner circle is completely black
            first_black_frame = self.find_first_black_frame(cap, state)
            
            # Find first frame when the first note appears
            chart_start = self.find_chart_start_frame(cap, state, first_black_frame)

            print(f"Chart Start Detector...Done                                ")
            if state["debug"]: print(f"  DEBUG: {first_black_frame} - {chart_start}")
            
            # Reset to start of video and return
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            return chart_start

        except Exception as e:
            raise Exception(f"Error in ChartStartDetector: {e}")
        

    def find_first_black_frame(self, cap, state) -> int:
        """Find the first frame where the inner circle is completely black
        arg: cap, state(circle_center, circle_radius, total_frames)
        ret: first_black_frame (frame number)
        """
        try:
            print("Chart Start Detector...Find_first_black_frame...", end="\r")

            circle_center = state["circle_center"]
            inner_radius = int(state["circle_radius"] * 0.8)  # 80% of radius for outer circle
            frame_number = 0
            total_frames = state["total_frames"]

            while frame_number < total_frames:
                ret, frame = cap.read()
                if not ret: break # end of video
                print(f"Chart Start Detector...Find_first_black_frame...{frame_number}/{total_frames}", end="\r")

                # Create a ring-shaped mask for the inner circle area
                mask = np.zeros(frame.shape[:2], dtype=np.uint8)
                cv2.circle(mask, circle_center, inner_radius, 255, -1)
                masked_frame = cv2.bitwise_and(frame, frame, mask=mask)

                gray = cv2.cvtColor(masked_frame, cv2.COLOR_BGR2GRAY)
                # Check if all pixels in masked area are drak (value < 5)
                if np.all(np.where(mask > 0, gray < 5, True)): break

                frame_number += 1
            
            if frame_number == total_frames:
                raise Exception("find first black frame: First black frame not found")
            
            return frame_number
            
        except Exception as e:
            raise Exception(f"Error in find_first_black_frame: {e}")


    def find_chart_start_frame(self, cap, state, first_black_frame) -> int:
        """Find first frame when the first note appears
        arg: cap, state(circle_center, circle_radius, total_frames), first_black_frame
        ret: chart start frame number
        """
        try:
            print("Chart Start Detector...Find_chart_start_frame...", end="\r")

            cap.set(cv2.CAP_PROP_POS_FRAMES, first_black_frame + 60) 
            circle_center = state["circle_center"]
            inner_radius = int(state["circle_radius"] * 0.8)  # 80% of radius for outer circle
            frame_number = first_black_frame + 60
            total_frames = state["total_frames"]

            while frame_number < total_frames:
                ret, frame = cap.read()
                if not ret: break # end of video
                print(f"Chart Start Detector...Find_chart_start_frame...{frame_number}/{total_frames}", end="\r")

                # 创建80%判定区域的遮罩，避免outline的干扰
                mask = np.zeros(frame.shape[:2], dtype=np.uint8)
                cv2.circle(mask, circle_center, inner_radius, 255, -1)
                masked_frame = cv2.bitwise_and(frame, frame, mask=mask)

                # 将帧转换为灰度图
                gray = cv2.cvtColor(masked_frame, cv2.COLOR_BGR2GRAY)
                # 使用二值化，将灰度值<75的变为黑色，避免bga的干扰
                _, binary = cv2.threshold(gray, 75, 255, cv2.THRESH_BINARY)
                # Check if any pixel in masked area is bright
                if np.any(binary > 0): break
                
                frame_number += 1
            
            if frame_number == total_frames or frame_number < 10:
                raise Exception("find chart start frame: Chart start frame not found")
            
            return frame_number-5 # 保险起见，往前推5帧
            
        except Exception as e:
            raise Exception(f"Error in find_chart_start_frame: {e}")
