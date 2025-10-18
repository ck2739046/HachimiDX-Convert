import cv2
import numpy as np
import os
import subprocess
from typing import Tuple, Optional

class Standardizer:
    def __init__(self):
        self.circle_center = None  # (x, y)
        self.circle_radius = None
        self.temp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'yolo-train', 'temp')
        
    def standardize_video(self, video_path: str, start_frame: int, end_frame: int, video_mode: str, target_res=1080) -> str:
        """
        标准化视频的主要函数
        
        Args:
            video_path: 视频文件的完整路径
            start_frame: 开始的帧数 (-1表示从头开始)
            end_frame: 结束的帧数 (-1表示到尾结束)
            video_mode: 视频模式(str)
            target_res: 视频分辨率(int)，默认1080

        Returns:
            标准化后的视频的完整路径
        """
        try:
            print("Starting video standardization...")
            
            # 1. 获取视频基本信息
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                raise Exception(f"Cannot open video file: {video_path}")
                
            video_width = round(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            video_height = round(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            total_frames = round(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            cap.release()
            
            # 验证帧数参数
            if start_frame == -1: start_frame = 0
            if end_frame == -1: end_frame = total_frames
            if start_frame < 0 or end_frame > total_frames or start_frame >= end_frame:
                raise Exception(f"Invalid frame range: [{start_frame}, {end_frame}], expect 0~{total_frames}")
            
            # 2. 检测圆心和半径
            cap = cv2.VideoCapture(video_path)
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            self.circle_center, self.circle_radius = self.detect_circle(cap, video_width, video_height, total_frames, video_mode)
            cap.release()
            # print(f"Detected circle - Center: {self.circle_center}, Radius: {self.circle_radius}")
            
            # 3. 显示预览窗口
            self.display_preview(video_path, video_width, video_height, start_frame, end_frame)
            
            # 4. 标准化视频
            standardized_path = self.process_video_standardization(
                video_path, start_frame, end_frame, fps, video_width, video_height, target_res,
                self.circle_center, self.circle_radius
            )
            
            print(f"Video standardization completed. Output: {standardized_path}")
            return standardized_path
            
        except Exception as e:
            raise Exception(f"Error in standardize_video: {e}")

    def detect_circle(self, cap, video_width: int, video_height: int, total_frames: int, mode: str = 'source', target: int = 15) -> Tuple[Tuple[int, int], int]:
        """
        检测视频中的圆形判定线
        
        Args:
            cap: 视频捕获对象
            video_width: 视频宽度
            video_height: 视频高度
            total_frames: 总帧数
            mode: 视频模式（'source'或'camera shot'）
            target: 需要检测的圆形数量
            
        Returns:
            (circle_center, circle_radius, frame_counter)
        """
        try:
            print("Detecting circle in video...", end="\r")
            
            frame_counter = 0
            circles_detected = []
            circles = 0
            video_size = min(video_width, video_height)
            r_small = round(video_size * 0.2)
            r_large = round(video_size * 0.6)

            # 处理帧
            while frame_counter < total_frames:
                ret, frame = cap.read()
                if not ret: break  # 视频结束
                print(f"Detecting circle... {frame_counter}/{total_frames}", end="\r")
                
                # 预处理
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                
                # 如果是录屏，直接固定阈值二值化
                if mode == 'source':
                    _, binary = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
                # 如果是拍摄，使用Canny边缘检测
                elif mode == 'camera shot':
                    # 自适应Canny边缘检测
                    median = np.median(gray)
                    lower = int(max(0, 0.66 * median))
                    upper = int(min(255, 1.33 * median))
                    binary = cv2.Canny(gray, lower, upper)
                    # 形态学闭操作，连接断裂边缘
                    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
                    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
                
                # 寻找轮廓
                contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if not contours:
                    continue
                
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
                        valid_circles.append((x, y, round(radius)))
                
                # 如果找到合适的圆形，选择半径最大的
                if valid_circles:
                    valid_circles.sort(key=lambda x: x[2], reverse=True)
                    x, y, radius = valid_circles[0]
                    circles_detected.append((round(x), round(y), round(radius)))
                    circles += 1
                    if circles == target: break
                    
                frame_counter += 1
            
            if len(circles_detected) < target:
                raise Exception("Not enough circles detected")
            
            # 取出现次数最多的圆
            circles_detected = [(round(x), round(y), round(r)) for x, y, r in circles_detected]
            most_common = max(set(circles_detected), key=circles_detected.count)
            circle_center = (most_common[0], most_common[1])
            circle_radius = most_common[2]

            # 微调
            circle_center = (circle_center[0]+1, circle_center[1]) # x轴左移1像素
            circle_radius -= int(video_size / 800)  # 半径减掉一点以避免边缘误差
            
            return circle_center, circle_radius
            
        except Exception as e:
            raise Exception(f"Error in detect_circle: {e}")
    
    def display_preview(self, video_path: str, video_width: int, video_height: int, start_frame: int, end_frame: int):
        """
        显示预览窗口，绘制原始图像帧和圆形
        
        Args:
            video_path: 视频路径
            video_width: 视频宽度
            video_height: 视频高度
            start_frame: 开始帧数
            end_frame: 结束帧数
        """
        try:
            print("Displaying preview...")
            
            while True:
                # 重置视频到开始帧
                cap = cv2.VideoCapture(video_path)
                cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
                
                # 设置窗口
                window_name = "Video Standardizer Preview"
                cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)
                
                # 播放控制变量
                isPaused = False
                current_frame = None
                need_restart = False
                
                # 显示帧
                while True:
                    if not isPaused:
                        ret, frame = cap.read()
                        if not ret or cap.get(cv2.CAP_PROP_POS_FRAMES) > end_frame:
                            # 视频结束或到达结束帧，从头开始播放
                            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
                            continue
                        new_frame = self.draw_frame(frame, video_width, video_height, isPaused)
                        cv2.imshow(window_name, new_frame)
                        if current_frame is not None:
                            current_frame = None  # 清除当前帧缓存
                    else:
                        # 暂停状态，仅等待用户输入
                        if current_frame is None:
                            # 如果没有当前帧，继续读取
                            ret, frame = cap.read()
                            if not ret or cap.get(cv2.CAP_PROP_POS_FRAMES) > end_frame:
                                cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
                                continue
                            new_frame = self.draw_frame(frame, video_width, video_height, isPaused)
                            current_frame = frame.copy()

                        cv2.imshow(window_name, new_frame)
                    
                    key = cv2.waitKey(10) & 0xFF
                    if key == ord('q') or (key != 255 and key != ord('c') and key != ord(' ')):
                        # 按任意键（除了c和空格）继续
                        need_restart = False
                        break
                    if key == ord(' '):
                        isPaused = not isPaused
                    elif key == ord('c'):
                        # 用户想要调整圆心和半径
                        try:
                            cv2.destroyWindow(window_name)
                        except:
                            pass  # 忽略窗口已销毁的错误
                        cap.release()
                        
                        adjustment_result = self.get_user_adjustment(video_width, video_height)
                        if adjustment_result:
                            self.circle_center, self.circle_radius = adjustment_result
                            need_restart = True
                            break
                        else:
                            # 用户取消调整，重新打开窗口
                            need_restart = True
                            break
                
                try:
                    cv2.destroyWindow(window_name)
                except:
                    pass  # 忽略窗口已销毁的错误
                cap.release()
                
                # 如果不需要重新开始预览，退出循环
                if not need_restart:
                    break
            
        except Exception as e:
            raise Exception(f"Error in display_preview: {e}")
    
    def draw_frame(self, frame, video_width: int, video_height: int, isPaused: bool):
        """
        在帧上绘制圆形和其他元素
        
        Args:
            frame: 视频帧
            video_width: 视频宽度
            video_height: 视频高度
            isPaused: 是否暂停
            
        Returns:
            处理后的帧
        """
        try:
            screen_r = self.circle_radius
            font_size = 0.7
            video_size = min(video_width, video_height)
            
            # 裁剪帧
            x1 = self.circle_center[0] - screen_r
            x2 = self.circle_center[0] + screen_r
            y1 = self.circle_center[1] - screen_r
            y2 = self.circle_center[1] + screen_r
            # 确保不越界
            if x1 < 0: x1 = 0
            if y1 < 0: y1 = 0
            if x2 > video_width: x2 = video_width
            if y2 > video_height: y2 = video_height
            # 定义裁剪区域
            if x1 != 0 or y1 != 0 or x2 != video_width or y2 != video_height:
                frame = frame[y1:y2, x1:x2]

            # 缩放到 900x900
            new_frame_size = 900
            frame = cv2.resize(frame, (new_frame_size, new_frame_size))

            # 绘制圆心
            cv2.circle(frame, (450, 450), 4, (0, 0, 255), 2)

            # 左上角提示 - 3行
            instructions = [
                "Press SPACE to pause/play",
                "Press C if circle is incorrect",
                "Press any other key to continue"
            ]
            
            for i, instruction in enumerate(instructions):
                cv2.putText(
                    frame,
                    instruction,
                    (10, 30 + i * 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    font_size,
                    (255, 255, 255),
                    2
                )
            
            # 左下角提示 - 2行
            # 第1行：暂停状态
            if isPaused:
                cv2.putText(
                    frame,
                    "PAUSED",
                    (10, new_frame_size - 60),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    font_size,
                    (0, 255, 255),
                    2
                )
            
            # 第2行：圆形坐标和半径
            circle_info = f"Center: ({self.circle_center[0]}, {self.circle_center[1]}), Radius: {screen_r}"
            cv2.putText(
                frame,
                circle_info,
                (10, new_frame_size - 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                font_size,
                (255, 255, 255),
                2
            )
            
            return frame
            
        except Exception as e:
            raise Exception(f"Error in draw_frame: {e}")
    
    def get_user_adjustment(self, video_width: int, video_height: int) -> Optional[Tuple[Tuple[int, int], int]]:
        """
        获取用户输入的圆心和半径调整参数
        
        Args:
            video_width: 视频宽度
            video_height: 视频高度
            
        Returns:
            如果参数合法，返回新的(圆心坐标, 半径)，否则返回None
        """
        try:
            print("\nCircle Adjustment")
            print("Enter three numbers separated by commas:")
            print("1. X offset (pixels, can be positive or negative)")
            print("2. Y offset (pixels, can be positive or negative)")
            print("3. Radius scale factor (0.5-1.5, can be positive or negative)")
            print("   Or type radius directly (pixels, must be over 100)")
            print("Example: 10, -5, 1.1")
            
            while True:
                user_input = input("Enter adjustment parameters: ").strip()

                try:
                    # 解析用户输入
                    parts = user_input.replace(' ', '').split(',')
                    if len(parts) != 3:
                        print("Error: Please enter exactly three numbers separated by commas.")
                        continue
                    
                    x_offset = int(parts[0])
                    y_offset = int(parts[1])
                    radius = float(parts[2])
                    
                    # 验证参数
                    new_x = self.circle_center[0] + x_offset
                    new_y = self.circle_center[1] + y_offset
                    
                    # 检查圆心是否在画面内
                    if new_x < 0 or new_x >= video_width or new_y < 0 or new_y >= video_height:
                        print(f"Error: Adjusted center ({new_x}, {new_y}) is outside the video frame.")
                        print(f"Valid range: X: 0-{video_width-1}, Y: 0-{video_height-1}")
                        continue

                    # 检查半径参数
                    if radius >= 100:
                        # 用户直接输入了半径
                        new_radius = round(radius)
                    else:
                        # 检查缩放系数
                        if radius < 0.5 or radius > 1.5:
                            print("Error: Radius scale factor must be between 0.5 and 1.5.")
                            continue
                        new_radius = round(self.circle_radius * radius)

                    # 检查新的半径    
                    if new_radius > max(video_width, video_height):
                        print(f"Error: New radius {new_radius} is too large for the video.")
                        continue
                    if new_radius < 100:
                        print(f"Error: New radius {new_radius} is too small (minimum 100).")
                        continue
                    
                    # 所有检查通过，返回新的圆心和半径
                    print(f"Adjustment applied: New center ({new_x}, {new_y}), New radius {new_radius}")
                    return ((new_x, new_y), new_radius)
                    
                except ValueError:
                    print("Error: Invalid input format. Please enter three numbers separated by commas.")
                    print("Example: 10, -5, 1.1")
                    
        except Exception as e:
            print(f"Error in get_user_adjustment: {e}")
            return None
    
    def process_video_standardization(self, input_video: str, start_frame: int, end_frame: int, fps: float,
                                      video_width: int, video_height: int, target_res: int,
                                      circle_center: Tuple[int, int], circle_radius: int) -> str:
        """
        使用ffmpeg进行视频的crop、trim和resize操作，保留音频
        
        Args:
            input_video: 输入视频路径
            start_frame: 开始帧数
            end_frame: 结束帧数
            fps: 视频帧率
            video_width: 视频宽度
            video_height: 视频高度
            target_res: 目标分辨率
            circle_center: 圆心坐标
            circle_radius: 圆半径
            
        Returns:
            处理后的视频路径
        """
        try:
            total_frames = round(cv2.VideoCapture(input_video).get(cv2.CAP_PROP_FRAME_COUNT))
            video_size = min(video_width, video_height)
            
            need_trim_ss = True
            need_trim_to = True
            need_crop = True
            need_resize = True
            
            # 定义trim参数
            if start_frame == 0: need_trim_ss = False
            if end_frame == total_frames: need_trim_to = False
            
            # 定义crop参数
            tolerance = video_size / 360 # 一半的容差
            # 计算最后裁剪出的视频的尺寸
            crop_size = round(circle_radius * 2)
            if abs(crop_size - target_res) < tolerance*2: crop_size = target_res # 接近目标分辨率则直接设为目标分辨率
            crop_size = min(crop_size, video_size) # 确保不越界
            # 计算裁剪区域左上角坐标
            crop_x = round(circle_center[0] - circle_radius)
            crop_y = round(circle_center[1] - circle_radius)
            # 避免坐标越界
            if crop_x < 0:
                crop_x = 0
            if crop_y < 0:
                crop_y = 0
            if crop_x + crop_size > video_width:
                crop_x = video_width - crop_size
            if crop_y + crop_size > video_height:
                crop_y = video_height - crop_size
            # 如果裁剪画面尺寸≈实际视频尺寸，并且裁剪中心≈实际视频中心，则不裁剪
            if abs(crop_size - video_size) < tolerance*2 and crop_x < tolerance and crop_y < tolerance:
                need_crop = False
            
            # 定义resize参数
            if crop_size == target_res:
                need_resize = False
            
            # 如果不需要任何处理，直接返回原视频路径
            if not need_crop and not need_resize and not need_trim_ss and not need_trim_to:
                print("Video already standardized.")
                return input_video
            
            # 设置视频输出路径
            video_name = os.path.basename(input_video).rsplit('.', 1)[0]
            os.makedirs(self.temp_dir, exist_ok=True)
            output_path = os.path.join(self.temp_dir, f'{video_name}_standardized.mp4')
            
            # 如果标准化视频已存在
            if os.path.exists(output_path):
                try:
                    cap = cv2.VideoCapture(output_path)
                    output_width = round(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    output_height = round(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    output_total_frames = round(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    cap.release()
                    if output_width == target_res and output_height == target_res:
                        if abs(output_total_frames - (end_frame-start_frame)) < 40:
                            print(f"Standardized video already exists")
                            return output_path  # 输出文件已存在，直接返回
                    raise Exception(f'standardized video exists but invalid, will re-generate')
                except Exception as e:
                    print(f"{e}")
                    os.remove(output_path)  # 删除损坏的文件
            
            print(f"Standardizing video...")
            
            # 构建ffmpeg命令
            cmd = ['ffmpeg', '-y', '-hide_banner', '-stats', '-loglevel', 'error']
            # -y: 覆盖文件 -hide_banner: 隐藏FFmpeg的版本信息和配置信息
            # -loglevel error: 只显示错误信息（不显示流信息）
            # -stats: 显示编码统计信息
            
            # 输入文件
            cmd.extend(['-i', input_video])
            
            # Trim参数 (帧数转为时间值)
            if need_trim_ss:
                cmd.extend(['-ss', str(start_frame / fps)])
            if need_trim_to:
                cmd.extend(['-to', str(end_frame / fps)])
            
            # Crop/Resize参数
            if need_crop:
                crop_cmd = f'crop={crop_size}:{crop_size}:{crop_x}:{crop_y}'
            if need_resize:
                resize_cmd = f'scale={target_res}:{target_res}'
            
            if need_crop and need_resize:
                cmd.extend(['-vf', f'{crop_cmd},{resize_cmd}'])
            elif need_crop:
                cmd.extend(['-vf', crop_cmd])
            elif need_resize:
                cmd.extend(['-vf', resize_cmd])

            # 音频编解码器
            cmd.extend(['-c:a', 'aac'])  # 使用AAC重新编码
            cmd.extend(['-b:a', '192k'])  # 统一码率192k
            # 视频编解码器
            cmd.extend(['-c:v', 'libx264'])
            # 确保音视频同步
            cmd.extend(['-async', '1'])
            # 输出文件
            cmd.append(output_path)
            
            # 执行ffmpeg命令
            print(f"trim {start_frame}-{end_frame}")
            if need_crop:
                print(f"crop source video to {crop_size}x{crop_size} from ({crop_x},{crop_y})")
            if need_resize:
                print(f"resize to {target_res}x{target_res}")
            print(f"Using FFmpeg command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=False, text=True, encoding='utf-8')
            
            if result.returncode != 0:
                raise Exception(f"FFmpeg error: {result.stderr}")
            
            return output_path
            
        except Exception as e:
            raise Exception(f"Error in process_video_standardization: {e}")


if __name__ == "__main__":
    # 测试代码
    standardizer = Standardizer()

    # 1590 779 476
    # 3440x1440 1180 1920 1000 -600

    # "source" or "camera shot"
    

    # video_path = r"C:\Users\ck273\Desktop\train\11753_120.mp4"
    # video_mode = "source"
    # start_frame = 490
    # end_frame = 19370

    # video_path = r"C:\Users\ck273\Desktop\train\11394_120.mkv"
    # video_mode = "source"
    # start_frame = 2290
    # end_frame = 19880

    # video_path = r"C:\Users\ck273\Desktop\train\11311_120.mkv"
    # video_mode = "source"
    # start_frame = 910
    # end_frame = 17060

    # video_path = r"C:\Users\ck273\Desktop\train\11814_120.mkv"
    # video_mode = "source"
    # start_frame = 1090
    # end_frame = 17100

    # video_path = r"C:\Users\ck273\Desktop\train\11741_120.mkv"
    # video_mode = "source"
    # start_frame = 930
    # end_frame = 18850

    # video_path = r"C:\Users\ck273\Desktop\train\11818_120.mkv"
    # video_mode = "source"
    # start_frame = 830
    # end_frame = 20050

    # video_path = r"C:\Users\ck273\Desktop\train\11820_120.mkv"
    # video_mode = "source"
    # start_frame = 610
    # end_frame = 31820

    # video_path = r"C:\Users\ck273\Desktop\殿ッ！？ご乱心！？(BASIC_Lv.6).mp4"
    # video_mode = "camera shot"
    # start_frame = 150
    # end_frame = 4100

    video_path = r"C:\Users\ck273\Desktop\風又ねリ\はじまりの未来_MASTER.mp4"
    video_mode = "source"
    start_frame = 740
    end_frame = 16600

    try:
        result_path = standardizer.standardize_video(video_path, start_frame, end_frame, video_mode, target_res=2160)
        print(f"Standardized video saved to: {result_path}")
    except Exception as e:
        print(f"Error: {e}")
