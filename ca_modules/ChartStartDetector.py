import cv2
import numpy as np
import librosa
import os
from scipy.signal import correlate
from scipy.io import wavfile
import warnings

# Suppress deprecation warnings
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

class ChartStartDetector:
    def __init__(self):
        self.template_path = "static/template/start_sound.aac"


    def process(self, cap, state: dict) -> float:
        """Main process
        arg: cap, state(circle_center, circle_radius, total_frames, debug, bpm, video_fps, video_path, chart_start)
        ret: chart_start_frame, audio_start_frame, outline_mask
        """
        try:
            print("Chart Start Detector...", end="\r")

            # Find first frame when the inner circle is completely black
            first_black_frame = self.find_first_black_frame(cap, state)

            # Find outline mask
            outline_mask = self.find_outline_mask(cap, state)
            
            # Find first frame when the first note appears
            chart_start = self.find_chart_start_frame(cap, state, first_black_frame)

            # Try audio start detection
            is_audio_success = False
            try:
                # Load template and audio data
                template, template_sr, audio_data, audio_sr = self.load_template_and_audio(state)
                # Generate the full 4-beat template based on BPM
                full_template = self.generate_template(state, template, template_sr, audio_sr)
                # Perform template matching to find the match frame
                match_frame = self.template_match(state, audio_data, audio_sr, full_template, chart_start)
                # End
                is_audio_success = True
            except Exception as e:
                print(f"ChartStartDetector: Audio start detection error: {e}")

            if is_audio_success:
                audio_start = match_frame
            else:
                audio_start = -666

            print(f"Chart Start Detector...Done                              ")
            if not is_audio_success:
                print("  Warning: Fail to get audio start due to audio detection error")

            if state["debug"]:
                if is_audio_success:
                    print(f"  DEBUG (audio): first_black_frame {first_black_frame} - chart_start {chart_start} - audio_start {audio_start}")
                else:
                    print(f"  DEBUG (visual): first_black_frame {first_black_frame} - chart_start {chart_start}")
            
            # Reset to start of video and return
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            return chart_start-5, audio_start, outline_mask
                   # 保险起见，提前5帧

        except Exception as e:
            raise Exception(f"Error in ChartStartDetector: {e}")


    def find_first_black_frame(self, cap, state) -> int:
        """Find the first frame where the inner circle is completely black
        arg: cap, state(circle_center, circle_radius, total_frames)
        ret: first_black_frame (frame number)
        """
        try:
            print("Chart Start Detector...Find_first_black_frame...", end="\r")

            cap.set(cv2.CAP_PROP_POS_FRAMES, state['chart_start']) 
            circle_center = state["circle_center"]
            outer_radius = round(state["circle_radius"] * 0.8)
            inner_radius = round(state["circle_radius"] * 0.4)
            frame_number = state['chart_start']
            total_frames = state["total_frames"]

            while frame_number < total_frames:
                ret, frame = cap.read()
                if not ret: break # end of video
                print(f"Chart Start Detector...Find_first_black_frame...{frame_number}/{total_frames}", end="\r")

                # 创建外部遮罩（80%半径）
                outer_mask = np.zeros(frame.shape[:2], dtype=np.uint8)
                cv2.circle(outer_mask, circle_center, outer_radius, 255, -1)
                # 创建内部遮罩（40%半径）
                inner_mask = np.zeros(frame.shape[:2], dtype=np.uint8)
                cv2.circle(inner_mask, circle_center, inner_radius, 255, -1)
                # 创建环形区域遮罩（外部遮罩 - 内部遮罩）
                ring_mask = cv2.bitwise_and(outer_mask, cv2.bitwise_not(inner_mask))
                # 应用外部遮罩获取整体区域
                masked_frame = cv2.bitwise_and(frame, frame, mask=outer_mask)
                gray = cv2.cvtColor(masked_frame, cv2.COLOR_BGR2GRAY)

                # 对内部区域进行二值化处理（宽容<200变为黑色）
                inner_gray = cv2.bitwise_and(gray, gray, mask=inner_mask)
                _, inner_binary = cv2.threshold(inner_gray, 200, 255, cv2.THRESH_BINARY)
                # 对环形区域进行二值化处理（严格<10变为黑色）
                ring_gray = cv2.bitwise_and(gray, gray, mask=ring_mask)
                _, ring_binary = cv2.threshold(ring_gray, 10, 255, cv2.THRESH_BINARY)

                # 检查两个区域是否全黑（值 < 5）
                inner_all_black = np.all(np.where(inner_mask > 0, inner_binary < 5, True))
                ring_all_black = np.all(np.where(ring_mask > 0, ring_binary < 5, True))
                if inner_all_black and ring_all_black:
                    break

                frame_number += 1
            
            if frame_number == total_frames:
                raise Exception("find first black frame: First black frame not found")
            
            return frame_number
            
        except Exception as e:
            raise Exception(f"Error in find_first_black_frame: {e}")
        

    def find_outline_mask(self, cap, state) -> np.ndarray:
        """Find outline mask by detecting non-black pixels in the ring area
        arg: cap, state(circle_center, circle_radius, debug)
        ret: outline_mask
        """
        try:            
            ret, frame = cap.read()
            if not ret:
                raise Exception("find_outline_mask: Cannot read frame")
            
            circle_center = state["circle_center"]
            outer_radius = round(state["circle_radius"] * 1.2)  # 120% radius
            inner_radius = round(state["circle_radius"] * 0.8)  # 80% radius
            
            # Create outer mask (120% radius)
            outer_mask = np.zeros(frame.shape[:2], dtype=np.uint8)
            cv2.circle(outer_mask, circle_center, outer_radius, 255, -1)
            # Create inner mask (80% radius)
            inner_mask = np.zeros(frame.shape[:2], dtype=np.uint8)
            cv2.circle(inner_mask, circle_center, inner_radius, 255, -1)
            # Create ring area mask (outer - inner)
            ring_mask = cv2.bitwise_and(outer_mask, cv2.bitwise_not(inner_mask))
            # Apply ring mask to frame
            masked_frame = cv2.bitwise_and(frame, frame, mask=ring_mask)
            
            # Convert to grayscale
            gray = cv2.cvtColor(masked_frame, cv2.COLOR_BGR2GRAY)
            # Create mask for all non-black pixels
            outline_mask = np.zeros(frame.shape[:2], dtype=np.uint8)
            outline_mask[gray > 160] = 255
            # Only keep pixels that are also in the ring area
            outline_mask = cv2.bitwise_and(outline_mask, ring_mask)

            # 在新窗口中显示轮廓遮罩
            if state.get("debug", True):
                # crop and resize
                screen_r = round(state["circle_radius"] / 0.88)
                x1 = circle_center[0] - screen_r
                x2 = circle_center[0] + screen_r
                y1 = circle_center[1] - screen_r
                y2 = circle_center[1] + screen_r
                outline_mask_crop = outline_mask[y1:y2, x1:x2]
                outline_mask_crop = cv2.resize(outline_mask_crop, (1000, 1000))
                # show
                cv2.imshow("Outline Mask Preview", outline_mask_crop)
                cv2.waitKey(0)
                cv2.destroyAllWindows()
            
            return outline_mask
            
        except Exception as e:
            raise Exception(f"Error in find_outline_mask: {e}")


    def find_chart_start_frame(self, cap, state, first_black_frame) -> int:
        """Find first frame when the first note appears
        arg: cap, state(circle_center, circle_radius, total_frames), first_black_frame
        ret: chart start frame number
        """
        try:
            print("Chart Start Detector...Find_chart_start_frame...", end="\r")

            cap.set(cv2.CAP_PROP_POS_FRAMES, first_black_frame + 60) 
            circle_center = state["circle_center"]
            inner_radius = round(state["circle_radius"] * 0.8)
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
                # 使用二值化，将<180的变为黑色，避免其他元素的干扰
                _, binary = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)
                # Check if any pixel in masked area is bright
                if np.any(binary > 0): break
                
                frame_number += 1
            
            if frame_number == total_frames or frame_number < 10:
                raise Exception("find chart start frame: Chart start frame not found")
            
            return frame_number
            
        except Exception as e:
            raise Exception(f"Error in find_chart_start_frame: {e}")
        

    def load_template_and_audio(self, state):
        """Load the start sound template adn video audio
        arg: self.template_path, state(video_path)
        ret: template, template_sr, audio_data, audio_sr
        """
        try:
            print("Chart Start Detector...audio_match...                        ", end="\r")
            
            template_path_full = os.path.join(os.path.dirname(os.path.dirname(__file__)), self.template_path)
            if not os.path.exists(template_path_full):
                raise Exception("load_template_and_video: Template start_sound not found")
            
            template, template_sr = librosa.load(template_path_full, sr=None)
            if template is None or len(template) == 0:
                raise Exception("load_template_and_video: Cannot load template start_sound")
            
            audio_data, audio_sr = librosa.load(state['video_path'], sr=None)
            if audio_data is None or len(audio_data) == 0:
                raise Exception("load_template_and_video: No audio track found in video")
            
            return template, template_sr, audio_data, audio_sr
        
        except Exception as e:
            raise Exception(f"Error in load_template_and_audio: {e}")


    def generate_template(self, state, template, template_sr, audio_sr) -> np.ndarray:
        """Generate the 4-beat full template based on BPM
        arg: state(bpm, debug), template, template_sr, audio_sr
        ret: full_template
        """
        try:
            beat_interval = 60.0 / state.get("bpm")
            
            # Resample template to audio sample rate if needed
            if template_sr != audio_sr:
                template_resampled = librosa.resample(
                    template, 
                    orig_sr=template_sr, 
                    target_sr=audio_sr
                )
            else:
                template_resampled = template.copy()
            
            # Calculate sample interval between beats
            sample_interval = round(beat_interval * audio_sr)
            template_length = len(template_resampled)
            
            # Create 4-beat template with proper intervals
            total_length = template_length + 3 * sample_interval
            full_template = np.zeros(total_length)
            for i in range(4):
                start_pos = i * sample_interval
                end_pos = start_pos + template_length
                if end_pos <= total_length:
                    full_template[start_pos:end_pos] = template_resampled

            #if state['debug']:
                # Save the generated template to desktop
                #desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
                #output_file = os.path.join(desktop_path, "generated_template.wav")
                #normalized_template = full_template / (np.max(np.abs(full_template)) + 1e-8)
                #wavfile.write(output_file, int(audio_sr), normalized_template.astype(np.float32))
                    
            return full_template
            
        except Exception as e:
            raise Exception(f"Error in generate_template: {e}")
        

    def template_match(self, state, audio_data, audio_sr, full_template, chart_start, threshold: float = 10) -> float:
        """Find the best match position for the template in audio data
        arg: state(video_fps, total_frames), audio_data, audio_sr, full_template, chart_start, threshold
        ret: audio_start
        """
        try:
            # Convert chart_start frame to audio sample position
            offset = 5 * state["video_fps"]
            chart_start_time = (chart_start+offset) / state["video_fps"]
            chart_start_sample = round(chart_start_time * audio_sr)
            if chart_start_sample >= len(audio_data):
                raise Exception(f"template_match: chart_start exceeds audio length")
            
            # Truncate audio data to only include samples before chart_start
            audio_data_truncated = audio_data[:chart_start_sample]
            if len(audio_data_truncated) < len(full_template):
                raise Exception(f"template_match: not enough audio data before chart_start for template matching")

            # Normalize both audio and template
            def rms_normalize(signal):
                rms = np.sqrt(np.mean(signal**2))
                return signal / (rms + 1e-8)
            
            audio_norm = rms_normalize(audio_data_truncated)
            template_norm = rms_normalize(full_template)
            
            # Perform normalized cross-correlation
            correlation = correlate(audio_norm, template_norm, mode='valid')
            
            # Normalize correlation by template energy for proper scaling
            template_energy = np.sum(template_norm**2)
            correlation = correlation / np.sqrt(template_energy)

            max_correlation = np.max(correlation)

            if max_correlation < threshold:
                raise Exception(f"template_match: Correlation too low: {max_correlation:.3f} < {threshold}")
                
            # Find the position of maximum correlation
            max_pos = np.argmax(correlation)
            
            # Convert sample position to match frame
            match_time = max_pos / audio_sr
            audio_start = round(match_time * state["video_fps"])
            if not 0 <= audio_start <= state["total_frames"]:
                raise Exception(f"audio start {audio_start} out of bounds (0, {state['total_frames']})")

            return audio_start
            
        except Exception as e:
            raise Exception(f"Error in template_match: {e}")
