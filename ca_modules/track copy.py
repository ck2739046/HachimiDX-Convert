from ultralytics import YOLO
from ultralytics.trackers import BOTSORT
import os
import cv2
import time
import torch
import numpy as np
from collections import defaultdict
from types import SimpleNamespace
from ultralytics.engine.results import Boxes
from ultralytics.utils import LOGGER
import logging

original_level = LOGGER.level
LOGGER.setLevel(logging.ERROR) # 只显示错误信息，忽略 Warning


class NoteDetector:
    def __init__(self):
        self.output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "yolo-train/runs/detect")
        self.temp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'yolo-train/temp')
        self.model_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "yolo-train/runs/train/note_detection1080_v3/weights/best.pt")



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
            if start is None: start = 0
            if end is None: end = total_frames
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
                if not ret: break
                    #raise Exception(f'Fail to read frame {current_frame}')
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



    def filter_track(self, frame_counter, results, trackers, orig_img):
        # class id: 0 hold, 1 slide, 2 tap, 3 touch, 4 touch_hold
        # trackers: 0 hold, 1 slide, 2 tap, 3 touch/touch_hold
        try:
            track_results = []
            orig_shape = orig_img.shape[:2]

            # 检查是否有检测结果
            if results[0].boxes is None or len(results[0].boxes) == 0:
                # 即使没有检测，也要调用update，让跟踪器知道时间在流逝，以便管理旧的轨迹
                # 传递一个空的Boxes对象
                empty_boxes = Boxes(np.empty((0, 6)), orig_shape)
                for tracker in trackers:
                    track_result = tracker.update(empty_boxes, orig_img)
                    track_results.append(track_result)
                return track_results

            # 从Results对象中获取所有检测框数据 (xyxy, conf, cls)
            all_boxes = results[0].boxes.data.cpu().numpy()

            # 1. 分离出各个class_id的检测框
            candidates = {}
            hold_mask = all_boxes[:, 5] == 0
            candidates[0] = (all_boxes[hold_mask])
            slide_mask = all_boxes[:, 5] == 1
            candidates[1] = (all_boxes[slide_mask])
            tap_mask = all_boxes[:, 5] == 2
            candidates[2] = (all_boxes[tap_mask])
            touch_mask = all_boxes[:, 5] >= 3
            candidates[3] = (all_boxes[touch_mask])
            
            # 2. 过滤slide音符
            final_slide_detections = []
            if len(candidates[1]) > 0:
                for box in candidates[1]:
                    x1, y1, x2, y2 = box[:4]
                    # 检查宽高比 (1.25)
                    width = x2 - x1
                    height = y2 - y1
                    if height == 0: continue # 避免除以零
                    aspect_ratio = width / height
                    if aspect_ratio > 1.25: continue
                    # 增大slide检测框尺寸1.4x, 改善追踪效果
                    new_width = int(width * 1.4)
                    new_height = int(height * 1.4)
                    center_x = (x1 + x2) / 2
                    center_y = (y1 + y2) / 2
                    new_x1 = max(0, int(center_x - new_width // 2))
                    new_y1 = max(0, int(center_y - new_height // 2))
                    new_x2 = min(orig_shape[1], new_x1 + new_width)
                    new_y2 = min(orig_shape[0], new_y1 + new_height)
                    # 创建新box然后保存
                    final_slide_detections.append([new_x1, new_y1, new_x2, new_y2] + box[4:].tolist())
            
            candidates[1] = np.array(final_slide_detections) if len(final_slide_detections) > 0 else np.empty((0, 6))

            # 3. 将过滤后的结果重新封装为Boxes对象，再交给对应的追踪器处理
            for i in range(len(trackers)):
                boxes = Boxes(candidates[i], orig_shape)
                track_result = trackers[i].update(boxes, orig_img)
                track_results.append(track_result)

            return track_results
        
        except Exception as e:
            raise Exception(f"Error in filter_detections {frame_counter}: {e}")
        


    def predict(self, input_path, state, start=None, end=None):

        # 为不同ID生成不同颜色
        def get_color_for_id(track_id):
            color_pool = [
                (0, 255, 255), (255, 0, 255), (255, 255, 0),
                (128, 0, 0), (0, 128, 0), (0, 0, 128),
                (128, 255, 255), (255, 128, 255), (255, 255, 128),
                (0, 128, 128), (128, 0, 128), (128, 128, 0),
                (255, 0, 0), (0, 255, 0), (0, 0, 255),
                (255, 128, 128), (128, 255, 128), (128, 128, 255),
                (128, 128, 128)
            ]
            # 使用track_id对颜色池长度取模来选择颜色
            color_index = track_id % len(color_pool)
            return color_pool[color_index]


        try:
            # 处理视频
            video_name_og = os.path.basename(input_path).split('.')[0]
            print(f"Predict: {video_name_og}")
            # trim then crop
            input_path_trim = self.trim_video(input_path, start, end)
            input_path_crop = self.crop_video_to_square(state, input_path_trim)
            input_path_final = input_path_crop
            video_name_final = os.path.basename(input_path_final).split('.')[0]
            print(f'Predict initialize...', end='\r', flush=True)
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
            trackers = []
            # trackers: hold, slide, tap, touch/touch_hold
            thresholds = [0.99, 0.99, 0.99, 0.8]
            for thresh in thresholds:
                tracker_args = SimpleNamespace(
                    # 没有注释的全是默认参数
                    tracker_type='botsort',
                    track_high_thresh=0.25,
                    track_low_thresh=0.1,
                    new_track_thresh=0.25,
                    track_buffer=30,
                    match_thresh=thresh,   # 自定义阈值
                    fuse_score=True,
                    # min_box_area=10,
                    gmc_method='none',     # 无需全局运动补偿
                    proximity_thresh=0.5,
                    appearance_thresh=0.8,
                    with_reid=False,
                    model="auto"
                )
                trackers.append(BOTSORT(args=tracker_args, frame_rate=fps))

            
            # 加载模型
            model = YOLO(self.model_path)
            if torch.cuda.is_available():
                model.to('cuda')
                #print(f"使用GPU: {torch.cuda.get_device_name(0)}")

            
            # 设置必要变量
            fps_counter = 0
            start_time = time.time()
            start_time_fixed = start_time
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
            # 存储所有帧的跟踪结果
            track_results_all = {}
            # 存储最终返回的轨迹数据
            final_tracks = defaultdict(lambda: {'class_id': None, 'path': []})


            # 主循环
            while True:
                ret, frame = cap.read()
                if not ret: break # end of video

                frame_count += 1
                fps_counter += 1

                # 使用模型预测当前帧
                results = model.predict(
                    source=frame,
                    conf=0.6,
                    iou=0.7,
                    verbose=False, # 关闭详细输出
                    device='cuda' if torch.cuda.is_available() else 'cpu',
                    max_det=50
                )


                # 过滤检测结果
                track_results = []
                if len(results) > 0 and results[0].boxes is not None:
                    track_results = self.filter_track(frame_count, results, trackers, frame)
                    track_results_all[frame_count] = track_results

                
                # 处理跟踪结果
                current_track_ids = set()  # 当前帧中存在的轨迹ID
                for track_result in track_results:
                    if track_result is not None and len(track_result) > 0:
                        # 绘制检测框和轨迹
                        for track in track_result:
                            # 获取轨迹信息
                            if len(track) < 7: continue
                            x1, y1, x2, y2, track_id, conf, class_id = track[:7]
                            x1, y1, x2, y2, track_id, class_id = int(x1), int(y1), int(x2), int(y2), int(track_id), int(class_id)
                            # 计算中心点
                            center_x = (x1 + x2) // 2
                            center_y = (y1 + y2) // 2
                            # 计算检测框尺寸
                            width = x2 - x1
                            height = y2 - y1
                            
                            # 记录当前帧中存在的轨迹ID
                            current_track_ids.add(track_id)
  
                            # 添加到最终轨迹数据
                            final_tracks[track_id]['class_id'] = class_id
                            final_tracks[track_id]['path'].append({
                                'frame': frame_count,
                                'center_x': center_x,
                                'center_y': center_y,
                                'width': width,
                                'height': height,
                                'confidence': conf
                            })

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
                            if len(track_history[track_id]) > 512:
                                track_history[track_id].pop(0)
                            # 获取颜色
                            color = get_color_for_id(track_id)
                            # 绘制边界框
                            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                            # 绘制标签
                            class_name = ['hold', 'slide', 'tap', 'touch', 'touch_hold'][class_id]
                            label = f'{class_name} ID:{track_id} {conf:.2f}'
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

            end_time = time.time()
            average_fps_rate = frame_count / (end_time - start_time_fixed)
            print(f"predict done, average FPS: {average_fps_rate:.2f}            ")
            cap.release()
            out.release()
            

            # 移动tracked_video到最终输出目录
            final_output_dir = os.path.join(self.output_dir, video_name_og)
            os.makedirs(final_output_dir, exist_ok=True)
            final_output_path = os.path.join(final_output_dir, f'{video_name_og}_tracked.mp4')
            # 处理文件名冲突，自动生成 _1, _2, _3 等后缀
            counter = 1
            while os.path.exists(final_output_path):
                final_output_path = os.path.join(final_output_dir, f'{video_name_og}_tracked_{counter}.mp4')
                counter += 1
            os.rename(output_path, final_output_path)
            # 清理临时目录
            if not os.listdir(self.temp_dir):
                os.rmdir(self.temp_dir)
            
            # 返回轨迹数据
            return dict(final_tracks), track_results_all, final_output_path


        except Exception as e:
            raise Exception(f"Error in predict: {e}")
        

    def main(self, state, single_video=None, start=None, end=None):
        try:
            if single_video:
                final_tracks, track_results_all, final_output_path = self.predict(single_video, state, start=start, end=end)
                return
            path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'yolo-train/input')
            for file in os.listdir(path):
                if file.endswith('.mp4'):
                    final_tracks, track_results_all, final_output_path = self.predict(os.path.join(path, file), state, start=start, end=end)
                    print()
        except Exception as e:
            print(f"Error in main: {e}")
            print(e.stacktrace())



    def process(self, state):
        try:
            video_path = state['video_path']
            start = state['chart_start']
            final_tracks, track_results_all, final_output_path = self.predict(video_path, state, start=start, end=None)
            return final_tracks, track_results_all, final_output_path

        except Exception as e:
            raise Exception(f"Error in process: {e}")



if __name__ == "__main__":
    video_path = r"D:\git\mai-chart-analyse\yolo-train\input\天蓋_cropped.mp4"
    cap = cv2.VideoCapture(video_path)
    state = {
        'total_frames': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        'circle_center': (539, 539), # 1920x1080: 959, 539
        'circle_radius': 474,
    }
    cap.release()

    detector = NoteDetector()
    #detector.main(state, video_path, start=400, end=None)
    detector.main(state, start=400)
