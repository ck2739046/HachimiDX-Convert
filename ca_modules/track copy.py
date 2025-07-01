from ultralytics import YOLO
from ultralytics.trackers import BOTSORT
import os
import cv2
import time
import torch
import numpy as np
from collections import defaultdict
import random
from types import SimpleNamespace
from ultralytics.engine.results import Boxes
from ultralytics.utils import LOGGER
import logging

original_level = LOGGER.level
LOGGER.setLevel(logging.ERROR) # 只显示错误信息，忽略 Warning


class NoteAnalyzer:
    def __init__(self):
        self.output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "yolo-train/runs/detect")
        self.temp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'yolo-train/temp')
        self.model_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "yolo-train/runs/train/note_detection1080/weights/best.pt")



    def crop_video_to_square(self, state, input_video):
        try:
            # 获取基础参数
            circle_radius = state['circle_radius']
            circle_center = state['circle_center']
            cap = cv2.VideoCapture(input_video)
            video_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            video_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = int(cap.get(cv2.CAP_PROP_FPS))
            cap.release()


            # 如果已经是正方形，直接返回原视频路径
            if video_width == video_height:
                return input_video
            

            # 设置视频输出路径
            video_name = os.path.basename(input_video).split('.')[0]
            os.makedirs(self.temp_dir, exist_ok=True)
            output_path = os.path.join(self.temp_dir, f'{video_name}_cropped.mp4')
            if os.path.exists(output_path):
                return output_path  # 如果输出文件已存在，直接返回
            

            # 计算裁剪尺寸和位置
            if video_height < circle_radius * 2.3:
                # 2.3x 半径 = 整个圆
                # 说明圆圈已经铺满整个画面，直接裁两边即可
                crop_size = min(video_width, video_height)
                # 画面中心左上角
                x = (video_width - crop_size) // 2
                y = (video_height - crop_size) // 2
            else:
                # 裁出圆形区域
                crop_size = int(circle_radius * 2.3)
                # 圆形区域左上角
                x = circle_center[0] - circle_radius
                y = circle_center[1] - circle_radius

            print(f"video crop: {video_width}x{video_height} -> {crop_size}x{crop_size}")
            

            # 设置视频编码器
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, (crop_size, crop_size))
            

            # 开始裁剪
            cap = cv2.VideoCapture(input_video)
            frame_count = 0
            while True:
                # 读取帧
                ret, frame = cap.read()
                if not ret: break # end of video
                # 裁剪帧
                cropped_frame = frame[y:y+crop_size, x:x+crop_size]
                out.write(cropped_frame)
                # 更新进度
                frame_count += 1
                if frame_count % 50 == 0: # 每50帧计算一次进度
                    progress = (frame_count / total_frames) * 100
                    print(f"progress: {frame_count}/{total_frames} ({progress:.1f}%)", end="\r", flush=True)

            #print(f"\r裁剪: {frame_count}/{total_frames} (100.0%) 完成", flush=True)
            print(f"  crop done                        ")
            cap.release()
            out.release()
            return output_path
        
        except Exception as e:
            raise Exception(f"Error in crop_video_to_square: {e}")
        


    def trim_video(self, input_video, start, end):
        try:
            # 获取基础参数
            cap = cv2.VideoCapture(input_video)
            video_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            video_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = int(cap.get(cv2.CAP_PROP_FPS))
            cap.release()
            

            # 验证start/end
            if start == 0 and end == total_frames:
                return input_video  # 不需要裁剪，直接返回
            if start < 0 or end > total_frames or start >= end:
                raise Exception(f"Invalid start/end: [{start}, {end}]")
            

            # 设置视频输出路径
            video_name = os.path.basename(input_video).split('.')[0]
            os.makedirs(self.temp_dir, exist_ok=True)
            output_path = os.path.join(self.temp_dir, f'{video_name}_trimmed[{start}_{end}].mp4')
            if os.path.exists(output_path):
                return output_path  # 如果输出文件已存在，直接返回


            # 设置视频编码器
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, (video_width, video_height))
            

            # 跳转到开始帧
            cap = cv2.VideoCapture(input_video)
            cap.set(cv2.CAP_PROP_POS_FRAMES, start)
            current_frame = start
            frames_written = 0
            print(f"video trim: {total_frames} -> {end-start+1} ({start}:{end})")
            
            while current_frame <= end:
                # 读取帧
                ret, frame = cap.read()
                if not ret:
                    raise Exception(f'Fail to read frame {current_frame}')
                # 写入帧
                out.write(frame)
                # 更新进度
                frames_written += 1
                current_frame += 1
                if frames_written % 50 == 0:
                    current = current_frame - start
                    total = end - start + 1
                    progress = current / total * 100
                    print(f"progess: {current}/{total} {progress:.1f}%", end='\r')
            
            print('  trim done                        ')
            cap.release()
            out.release()
            return output_path

        except Exception as e:
            raise Exception(f"Error in trim_video: {e}")



    def filter_track(self, frame_counter, results, tracker_other, tracker_slide, orig_img):
        # class id: 0 hold, 1 slide, 2 tap, 3 touch, 4 touch_hold
        try:
            # 默认返回空列表
            tracked_objects_other = []
            tracked_objects_slide = []
            orig_shape = orig_img.shape[:2]

            # 检查是否有检测结果
            if results[0].boxes is None or len(results[0].boxes) == 0:
                # 即使没有检测，也要调用update，让跟踪器知道时间在流逝，以便管理旧的轨迹
                # 传递一个空的Boxes对象
                empty_boxes = Boxes(np.empty((0, 6)), orig_shape)
                tracked_objects_other = tracker_other.update(empty_boxes, orig_img)
                tracked_objects_slide = tracker_slide.update(empty_boxes, orig_img)
                return tracked_objects_other, tracked_objects_slide

            # 从Results对象中获取所有检测框数据 (xyxy, conf, cls)
            all_boxes = results[0].boxes.data.cpu().numpy()

            # 1. 分离出 class_id != 1 的检测框
            other_mask = all_boxes[:, 5] != 1
            other_detections = all_boxes[other_mask]

            # 2. 分离出 class_id == 1 的检测框
            slide_mask = all_boxes[:, 5] == 1
            slide_candidates = all_boxes[slide_mask]
            
            # 3. 对 slide 检测框应用宽高比过滤
            final_slide_detections = []
            if len(slide_candidates) > 0:
                for box in slide_candidates:
                    x1, y1, x2, y2 = box[:4]
                    width = x2 - x1
                    height = y2 - y1
                    # 避免除以零
                    if height == 0: continue
                    aspect_ratio = width / height
                    if aspect_ratio < 1.2:
                        final_slide_detections.append(box)
            
            final_slide_detections = np.array(final_slide_detections) if len(final_slide_detections) > 0 else np.empty((0, 6))

            # 4. 将过滤后的结果重新包装成Boxes对象，再交给对应的追踪器处理
            other_boxes = Boxes(other_detections, orig_shape)
            slide_boxes = Boxes(final_slide_detections, orig_shape)

            tracked_objects_other = tracker_other.update(other_boxes, orig_img)
            tracked_objects_slide = tracker_slide.update(slide_boxes, orig_img)

            return tracked_objects_other, tracked_objects_slide
        
        except Exception as e:
            raise Exception(f"Error in filter_detections {frame_counter}: {e}")
        


    def predict(self, input_path, state, start=None, end=None):

        # 为不同ID生成不同颜色
        def get_color_for_id(track_id):
            # 使用track_id作为种子生成固定的颜色
            random.seed(track_id)
            return (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))

        try:
            print(f'Predict initialize...', end='\r', flush=True)
            # 处理视频
            if start is None: start = 0
            if end is None: end = int(state['total_frames'])
            video_name_og = os.path.basename(input_path).split('.')[0]
            # trim then crop
            input_path_trim = self.trim_video(input_path, start, end)
            input_path_crop = self.crop_video_to_square(state, input_path_trim)
            input_path_final = input_path_crop
            video_name_final = os.path.basename(input_path_final).split('.')[0]
            # 重新获取处理后的视频信息
            cap = cv2.VideoCapture(input_path_final)
            video_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            video_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = int(cap.get(cv2.CAP_PROP_FPS))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            # 输出视频设置
            output_path = os.path.join(self.temp_dir, f'{video_name_final}_tracked.mp4')
            if os.path.exists(output_path):
                os.remove(output_path)  # 如果输出文件已存在，删除它
            # 设置视频编码器
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, (video_width, video_height))


            # 初始化跟踪器
            tracker_args = SimpleNamespace(
                # 没有注释的全是默认参数
                tracker_type='botsort',
                track_high_thresh=0.25,
                track_low_thresh=0.1,
                new_track_thresh=0.25,
                track_buffer=30,
                match_thresh=0.99,     # 保证不会变为新编号
                fuse_score=True,
                # min_box_area=10,
                gmc_method='sparseOptFlow',
                proximity_thresh=0.5,
                appearance_thresh=0.8,
                with_reid=False,
                model="yolo11n-cls.pt" # ReID 模型
            )
            tracker_other = BOTSORT(args=tracker_args, frame_rate=fps)
            tracker_slide = BOTSORT(args=tracker_args, frame_rate=fps)

            
            # 加载模型
            model = YOLO(self.model_path)
            if torch.cuda.is_available():
                model.to('cuda')
                #print(f"使用GPU: {torch.cuda.get_device_name(0)}")

            
            # 设置必要变量
            fps_counter = 0
            start_time = time.time()
            frame_count = 0
            fps_rate = 0
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0) # 重置到开始
            # 存储轨迹信息
            track_history = defaultdict(list)
            # 存储每个轨迹最后出现的帧数
            track_last_seen = defaultdict(int)
            # 存储隐藏的轨迹（超过5帧未出现但还在30帧恢复期内）
            hidden_tracks = defaultdict(lambda: {'history': [], 'last_seen': 0})
            # 存储轨迹状态：'active', 'hidden', 'expired'
            track_status = defaultdict(lambda: 'active')


            # 主循环
            while True:
                ret, frame = cap.read()
                if not ret: break # end of video

                frame_count += 1
                fps_counter += 1

                # 使用模型预测当前帧
                results = model.predict(
                    source=frame,
                    conf=0.5,
                    iou=0.7,
                    verbose=False, # 关闭详细输出
                    device='cuda' if torch.cuda.is_available() else 'cpu',
                    max_det=50
                )

                tracked_objects_slide = []
                tracked_objects_other = []
                # 过滤检测结果
                if len(results) > 0 and results[0].boxes is not None:
                    tracked_objects_other, tracked_objects_slide = self.filter_track(frame_count, results, tracker_other, tracker_slide, frame)
 

                
                # 处理跟踪结果
                current_track_ids = set()  # 当前帧中存在的轨迹ID
                for tracked_objects, track_type in [(tracked_objects_slide, 'slide'),
                                                    (tracked_objects_other, 'other')]:
                    if len(tracked_objects) > 0:
                        # 绘制检测框和轨迹
                        for track in tracked_objects:
                            # 获取轨迹信息
                            if len(track) < 5: continue
                            x1, y1, x2, y2, track_id = track[:5]
                            x1, y1, x2, y2, track_id = int(x1), int(y1), int(x2), int(y2), int(track_id)
                            if track_type == 'slide':
                                track_id = track_id + 1000 # 偏移ID，避免与其他检测冲突
                            # 计算中心点
                            center_x = (x1 + x2) // 2
                            center_y = (y1 + y2) // 2
                            # 记录当前帧中存在的轨迹ID
                            current_track_ids.add(track_id)
                            # 检查是否是从隐藏状态恢复的轨迹
                            if track_status[track_id] == 'hidden':
                                # 恢复轨迹：将隐藏的历史记录恢复到活跃轨迹
                                track_history[track_id] = hidden_tracks[track_id]['history'].copy()
                                track_status[track_id] = 'active'
                                del hidden_tracks[track_id]
                            # 更新轨迹最后出现的帧数
                            track_last_seen[track_id] = frame_count
                            track_status[track_id] = 'active'
                            # 存储轨迹点
                            track_history[track_id].append((center_x, center_y))
                            # 限制轨迹长度，避免内存过多
                            if len(track_history[track_id]) > 192:
                                track_history[track_id].pop(0)
                            # 获取颜色
                            color = get_color_for_id(track_id)
                            # 绘制边界框
                            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                            # 绘制ID和置信度
                            conf = track[5] if len(track) > 5 else 0.0  # 获取置信度
                            label = f'ID:{track_id} {conf:.2f}'
                            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
                            cv2.rectangle(frame, (x1, y1 - label_size[1] - 10), 
                                        (x1 + label_size[0], y1), color, -1)
                            cv2.putText(frame, label, (x1, y1 - 5), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                

                # 处理轨迹状态管理
                tracks_to_hide = []
                tracks_to_expire = []
                
                # 检查活跃轨迹
                for track_id in list(track_history.keys()):
                    if track_id not in current_track_ids:
                        frames_since_last_seen = frame_count - track_last_seen.get(track_id, frame_count)
                        
                        # 超过5帧未出现，隐藏轨迹
                        if frames_since_last_seen > 5 and track_status[track_id] == 'active':
                            tracks_to_hide.append(track_id)
                
                # 检查隐藏轨迹
                for track_id in list(hidden_tracks.keys()):
                    if track_id not in current_track_ids:
                        frames_since_last_seen = frame_count - hidden_tracks[track_id]['last_seen']
                        
                        # 超过30帧未出现，永久删除
                        if frames_since_last_seen > 30:
                            tracks_to_expire.append(track_id)
                
                # 隐藏轨迹
                for track_id in tracks_to_hide:
                    if track_id in track_history:
                        # 将轨迹移动到隐藏状态
                        hidden_tracks[track_id]['history'] = track_history[track_id].copy()
                        hidden_tracks[track_id]['last_seen'] = track_last_seen[track_id]
                        track_status[track_id] = 'hidden'
    
                        # 从活跃轨迹中删除
                        del track_history[track_id]

                # 永久删除过期轨迹
                for track_id in tracks_to_expire:
                    if track_id in hidden_tracks:
                        del hidden_tracks[track_id]
                    if track_id in track_last_seen:
                        del track_last_seen[track_id]
                    if track_id in track_status:
                        del track_status[track_id]
                
                # 绘制所有活跃轨迹的轨迹线
                for track_id, points in track_history.items():
                    if len(points) > 1 and track_status[track_id] == 'active':
                        color = get_color_for_id(track_id)
                        # 绘制轨迹线
                        for i in range(1, len(points)):
                            cv2.line(frame, points[i-1], points[i], color, 3)
                        
                        # 在轨迹起点绘制小圆点
                        if points:
                            cv2.circle(frame, points[0], 3, color, -1)
                
                # 写入输出视频
                out.write(frame)

                # 显示进度
                if fps_counter >= 30:  # 每30帧更新一次fps
                    # 计算fps
                    current_time = time.time()
                    fps_rate = fps_counter / (current_time - start_time)
                    start_time = current_time
                    fps_counter = 0

                progress = (frame_count / total_frames) * 100 
                print(f"progress: {frame_count}/{total_frames} ({progress:.1f}%) {fps_rate:.1f}fps", end="\r", flush=True)

            print(f"predict done                                  ")
            cap.release()
            out.release()
            
            # 如果使用了裁剪的临时文件，删除它
            #if input_path != input_path_trim:
                #os.remove(input_path_trim)
            #if input_path != input_path_crop:
                #os.remove(input_path_crop)
            # 移动tracked_video到最终输出目录
            final_output_dir = os.path.join(self.output_dir, video_name_og)
            os.makedirs(final_output_dir, exist_ok=True)
            final_output_path = os.path.join(final_output_dir, f'{video_name_og}_tracked.mp4')
            os.rename(output_path, final_output_path)
            # 清理临时目录
            if not os.listdir(self.temp_dir):
                os.rmdir(self.temp_dir)

        except Exception as e:
            raise Exception(f"Error in predict: {e}")
        

    def main(self, state, single_video=None, start=None, end=None):
        try:
            if single_video:
                self.predict(single_video, state, start=start, end=end)
                return
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'yolo-train/input')
            for file in os.listdir(path):
                if file.endswith('.mp4'):
                    self.predict(os.path.join(path, file), state)
                    print()
        except Exception as e:
            print(f"Error in main: {e}")
            print(e.stacktrace())




if __name__ == "__main__":
    video_path = r"D:\git\mai-chart-analyse\yolo-train\input\DEICIDE.mp4"
    cap = cv2.VideoCapture(video_path)
    state = {
        'total_frames': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        'circle_center': (959, 539),
        'circle_radius': 474,
    }
    cap.release()

    analyzer = NoteAnalyzer()
    analyzer.main(state, video_path, start=400, end=4000)
