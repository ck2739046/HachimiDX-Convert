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
import subprocess
import json
import shutil

original_level = LOGGER.level
LOGGER.setLevel(logging.ERROR) # 只显示错误信息，忽略 Warning


class NoteDetector:
    def __init__(self):
        self.output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'yolo-train', 'runs', 'detect')
        self.temp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'yolo-train', 'temp')
        self.model_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'yolo-train', 'runs', 'train', 'note_detection1080_v4', 'weights', 'best.pt')



    def standardlize_video(self, state, input_video, start=None, end=None):
        """
        使用ffmpeg进行视频的crop、trim和resize操作, 保留音频
        
        Args:
            start: 开始帧数
            end: 结束帧数
            state: 包含circle_center/circle_radius/debug的状态字典
            input_video: 输入视频路径
        
        Returns:
            处理后的视频路径
        """
        try:
            # 获取基础参数
            cap = cv2.VideoCapture(input_video)
            video_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            video_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            cap.release()
            circle_radius = state['circle_radius']
            circle_center = state['circle_center']

            need_trim_ss = True
            need_trim_to = True
            need_crop = True
            need_resize = True

            # 检查start和end参数
            if start is not None and end is not None:
                if start < 0 or end > total_frames or start >= end:
                    raise Exception(f"Invalid start/end: [{start}, {end}], expect 0~{total_frames}")
                
            # 定义trim参数
            if start is None:
                start = 0
                need_trim_ss = False
            if end is None:
                end = total_frames
                need_trim_to = False

            # 定义crop参数
            if video_height < circle_radius * 2.3:
                # 检查画面是否已经正常
                if video_width == video_height:
                    frame_center = (video_width // 2, video_height // 2)
                    diff_x = abs(frame_center[0] - circle_center[0])
                    diff_y = abs(frame_center[1] - circle_center[1])
                    if diff_x < 5 and diff_y < 5:
                        need_crop = False # 不需要裁剪

                # 说明圆圈已经铺满整个画面，直接裁两边即可
                crop_size = min(video_width, video_height)
                # 画面中心
                crop_x = (video_width - crop_size) // 2
                crop_y = (video_height - crop_size) // 2
            else:
                # 裁出圆形区域
                crop_size = int(circle_radius * 2.28)
                # 圆形区域左上角
                crop_x = circle_center[0] - int(circle_radius * 1.14)
                crop_y = circle_center[1] - int(circle_radius * 1.14)

            # 定义resize参数
            if crop_size == 1080:
                need_resize = False


            # 如果不需要任何处理，直接返回原视频路径
            if not need_crop and not need_resize and not need_trim_ss and not need_trim_to:
                print("Standardlize video: Video already standardlized.")
                return input_video
            
            # 设置视频输出路径
            video_name = os.path.basename(input_video).rsplit('.', 1)[0]
            os.makedirs(self.temp_dir, exist_ok=True)
            output_path = os.path.join(self.temp_dir, f'{video_name}_standardlized.mp4')
            # 如果标准化视频已存在
            if os.path.exists(output_path):
                try:
                    cap = cv2.VideoCapture(output_path)
                    output_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    output_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    output_total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    cap.release()
                    if output_width == 1080 and output_height == 1080:
                        if output_total_frames == (end-start):
                            print(f"Standardlize video: Output file already exists")
                            return output_path # 输出文件已存在，直接返回
                    raise Exception('standardlized video exists but invalid')
                except Exception as e:
                    os.remove(output_path)  # 删除损坏的文件
            print(f"Standardlize video...")
            
            
            # 构建ffmpeg命令
            cmd = ['ffmpeg', '-y', '-hide_banner', '-stats', '-loglevel', 'error']
            # -y: 覆盖文件 -hide_banner: 隐藏FFmpeg的版本信息和配置信息
            # -loglevel error: 只显示错误信息（不显示流信息）
            # -stats: 显示编码统计信息
            
            # 输入文件
            cmd.extend(['-i', input_video])
            
            # Trim参数 (帧数转为时间值)
            if need_trim_ss:
                cmd.extend(['-ss', str(start / fps)]) 
            if need_trim_to:
                cmd.extend(['-to', str(end / fps)])
            
            # Crop/Resize参数
            if need_crop:
                crop_cmd = f'crop={crop_size}:{crop_size}:{crop_x}:{crop_y}'
            if need_resize:
                resize_cmd = f'scale=1080:1080'

            if need_crop and need_resize:
                cmd.extend(['-vf', f'{crop_cmd},{resize_cmd}'])
            elif need_crop:
                cmd.extend(['-vf', crop_cmd])
            elif need_resize:
                cmd.extend(['-vf', resize_cmd])
            
            # 音频编解码器
            cmd.extend(['-c:a', 'aac'])  # 使用AAC重新编码
            cmd.extend(['-b:a', '192k']) # 统一码率192k
            # 视频编解码器
            cmd.extend(['-c:v', 'libx264'])
            # 确保音视频同步
            cmd.extend(['-async', '1'])
            # 输出文件
            cmd.append(output_path)

            # 执行ffmpeg命令
            result = subprocess.run(cmd, capture_output=False, text=True, encoding='utf-8')
            
            if result.returncode != 0:
                raise Exception(f"FFmpeg error: {result.stderr}")
            
            if state['debug']:
                print(f"  Debug: Use FFmpeg command: {' '.join(cmd)}")
            
            print("Standardlize video: completed")
            return output_path
            
        except Exception as e:
            raise Exception(f"Error in standardlize_video: {e}")



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
                    width = x2 - x1
                    height = y2 - y1
                    # 检查宽高比 (1.25)
                    #if height == 0: continue # 避免除以零
                    #aspect_ratio = width / height
                    #if aspect_ratio > 1.25: continue
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
                #(128, 0, 0), (0, 128, 0), (0, 0, 128),
                (128, 255, 255), (255, 128, 255), (255, 255, 128),
                #(0, 128, 128), (128, 0, 128), (128, 128, 0),
                (255, 0, 0), (0, 255, 0), (0, 0, 255),
                (255, 128, 128), (128, 255, 128), (128, 128, 255),
                (128, 128, 128)
            ]
            # 使用track_id对颜色池长度取模来选择颜色
            color_index = track_id % len(color_pool)
            return color_pool[color_index]


        try:
            # 处理视频
            input_path = os.path.abspath(input_path)
            input_path = os.path.normpath(input_path)
            video_name_og = os.path.basename(input_path).rsplit('.', 1)[0]
            print(f"Predict: {video_name_og}")
            
            # 输入视频标准化
            input_path_final = self.standardlize_video(state, input_path, start, end)
            video_name_final = os.path.basename(input_path_final).rsplit('.', 1)[0]
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
            # 存储最终返回的轨迹数据
            final_tracks = defaultdict(lambda: {'class_id': None, 'path': []})

            # 创建JSONL文件用于流式写入
            predict_results_file_path = os.path.join(self.temp_dir, f'{video_name_final}_predict_results.jsonl')
            if os.path.exists(predict_results_file_path):
                os.remove(predict_results_file_path)
            predict_results_file = open(predict_results_file_path, 'w', encoding='utf-8')

            track_results_file_path = os.path.join(self.temp_dir, f'{video_name_final}_track_results.jsonl')    
            if os.path.exists(track_results_file_path):
                os.remove(track_results_file_path)
            track_results_file = open(track_results_file_path, 'w', encoding='utf-8')


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

                # 流式写入预测结果
                predict_frame_data = {
                    'frame': frame_count,
                    'results': json.loads(results[0].tojson())
                }
                predict_results_file.write(json.dumps(predict_frame_data, ensure_ascii=False) + '\n')
                predict_results_file.flush()  # 确保数据写入


                # 过滤检测结果
                track_results = []
                if len(results) > 0 and results[0].boxes is not None:
                    track_results = self.filter_track(frame_count, results, trackers, frame)
                    

                    # 转换track_results为可序列化格式
                    track_results_serializable = []
                    for result in track_results:
                        if result is not None and len(result) > 0:
                            for track in result:
                                if len(track) >= 7:
                                    track_values = []
                                    for i, val in enumerate(track[:7]):
                                        if i == 4:  # track_id
                                            track_values.append(int(val))
                                        elif i == 5:  # confidence
                                            track_values.append(round(float(val), 2))
                                        elif i == 6:  # class_id
                                            track_values.append(int(val))
                                        else:  # x1, y1, x2, y2
                                            track_values.append(int(val))
                                    track_results_serializable.append(track_values)
                    # 写入文件
                    track_frame_data = {
                        'frame': frame_count,
                        'results': track_results_serializable
                    }
                    track_results_file.write(json.dumps(track_frame_data, ensure_ascii=False) + '\n')
                    track_results_file.flush()  # 确保数据写入

                
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
                            
                            # 记录当前帧中存在的轨迹ID
                            current_track_ids.add(track_id)
  
                            # 添加到最终轨迹数据
                            final_tracks[track_id]['class_id'] = class_id
                            final_tracks[track_id]['path'].append({
                                'frame': frame_count,
                                'x1': x1,
                                'y1': y1,
                                'x2': x2,
                                'y2': y2,
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
            predict_results_file.close()
            track_results_file.close() 
            

            # 移动tracked_video到最终输出目录
            final_output_dir = os.path.join(self.output_dir, video_name_og)
            os.makedirs(final_output_dir, exist_ok=True)
            final_output_path = os.path.join(final_output_dir, f'{video_name_og}_tracked.mp4')
            # 处理文件名冲突，自动生成 _1, _2, _3 等后缀
            counter = 1
            while os.path.exists(final_output_path):
                final_output_path = os.path.join(final_output_dir, f'{video_name_og}_tracked_{counter}.mp4')
                counter += 1


            # 使用ffmpeg添加音频到跟踪视频
            temp_final_path = final_output_path.replace('.mp4', '_temp.mp4')
            if os.path.exists(temp_final_path):
                os.remove(temp_final_path)
            # 构建ffmpeg命令来合并视频和音频
            audio_cmd = [
                'ffmpeg', '-y',
                '-i', output_path,  # 无声的跟踪视频
                '-i', input_path_final,  # 有声的标准化视频
                '-c:v', 'copy',  # 复制视频流
                '-c:a', 'copy',  # 复制音频流
                '-map', '0:v:0',  # 使用第一个输入的视频流
                '-map', '1:a:0',  # 使用第二个输入的音频流
                '-shortest',  # 以最短的流为准
                temp_final_path
            ]
            
            try:
                result = subprocess.run(audio_cmd, capture_output=True, text=True, encoding='utf-8')
                if result.returncode == 0:
                    # 成功添加音频，替换原文件
                    os.rename(temp_final_path, final_output_path)
                    os.remove(output_path)  # 删除临时的无声视频
                else:
                    raise Exception(result.stderr)
            except Exception as e:
                print(f"Warning: Error adding audio - {e}")
                # 发生错误时，使用无声视频
                os.rename(output_path, final_output_path)
                if os.path.exists(temp_final_path):
                    os.remove(temp_final_path)

            # 复制 standardlized 视频到输出目录
            final_standardlized_path = os.path.join(final_output_dir, f'{video_name_og}_standardlized.mp4')
            if os.path.exists(final_standardlized_path):
                os.remove(final_standardlized_path)
            shutil.copy(input_path_final, final_standardlized_path)

            # 清理临时目录
            if not os.listdir(self.temp_dir):
                os.rmdir(self.temp_dir)

            # 保存数据为JSON文件
            self.save_detection_data(final_tracks, final_output_dir, track_results_file_path, predict_results_file_path, video_name_og)

            # 返回轨迹数据
            return final_output_path

        except Exception as e:
            raise Exception(f"Error in predict: {e}")
        finally:
           # 确保文件被关闭
            if 'predict_results_file' in locals():
                if not predict_results_file.closed:
                    predict_results_file.close()
            if 'track_results_file' in locals():
                if not track_results_file.closed:
                    track_results_file.close()
        


    def save_detection_data(self, final_tracks, output_dir, track_results_path, predict_results_path, video_name):
        """
        保存轨迹数据到文件
        
        Args:
            final_tracks: 最终轨迹数据
            output_dir: 输出目录
            track_results_file_path: track results JSONL文件路径
            predict_results_file_path: predict results JSONL文件路径
            video_name: 原始视频名称
        """
        try:
            # 转换 final_tracks 为JSON可序列化格式
            final_tracks_serializable = {}
            for track_id, track_data in dict(final_tracks).items():
                final_tracks_serializable[str(track_id)] = {
                    'class_id': int(track_data['class_id']) if track_data['class_id'] is not None else None,
                    'path': []
                }
                for point in track_data['path']:
                    serializable_point = {
                        'frame': int(point['frame']),
                        'x1': int(point['x1']),
                        'y1': int(point['y1']),
                        'x2': int(point['x2']),
                        'y2': int(point['y2']),
                        'conf': round(float(point['confidence']), 2)
                    }
                    final_tracks_serializable[str(track_id)]['path'].append(serializable_point)
            
            # 保存 final_tracks
            final_tracks_path = os.path.join(output_dir, f'{video_name}_final_tracks.json')
            if os.path.exists(final_tracks_path):
                os.remove(final_tracks_path)
            with open(final_tracks_path, 'w', encoding='utf-8') as f:
                json.dump(final_tracks_serializable, f, ensure_ascii=False, indent=2)


            # 移动JSONL文件到最终输出目录
            final_track_results_path = os.path.join(output_dir, f'{video_name}_track_results.jsonl')
            final_predict_results_path = os.path.join(output_dir, f'{video_name}_predict_results.jsonl')
            # 删除已存在的文件
            if os.path.exists(final_track_results_path):
                os.remove(final_track_results_path)
            if os.path.exists(final_predict_results_path):
                os.remove(final_predict_results_path)
            # 移动文件
            os.rename(track_results_path, final_track_results_path)
            os.rename(predict_results_path, final_predict_results_path)
            
            

            # 保存元数据信息
            metadata = {
                'video_name': video_name,
                'class_mapping': {
                    0: 'hold',
                    1: 'slide', 
                    2: 'tap',
                    3: 'touch',
                    4: 'touch_hold'
                },
                'final_tracks_format': {
                    'description': 'Dictionary with track_id as key',
                    'structure': {
                        'class_id': 'int - object class (0=hold, 1=slide, 2=tap, 3=touch, 4=touch_hold)',
                        'path': 'list of notes with format dict{frame, x1, y1, x2, y2, conf}'
                    }
                },
                'track_results_format': {
                    'description': 'JSONL file with one line per frame',
                    'structure': {
                        'each_line': {
                            'frame': 'int - frame number',
                            'results': 'List of notes with format [x1, y1, x2, y2, track_id, confidence, class_id]'
                        }
                    }
                },
                'predict_results_format': {
                    'description': 'JSONL file with one line per frame', 
                    'structure': {
                        'each_line': {
                            'frame': 'int - frame number',
                            'results': 'List of notes with yolo format [name, class, confidence, box{x1, y1, x2, y2}]'
                        }
                    }
                }
            }
            
            metadata_path = os.path.join(output_dir, f'{video_name}_metadata.json')
            if os.path.exists(metadata_path):
                os.remove(metadata_path)
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            
            print(f"Note detection data saved to:")
            print(f"  - {final_tracks_path}")
            print(f"  - {final_track_results_path}") 
            print(f"  - {final_predict_results_path}")
            print(f"  - {metadata_path}")
            
        except Exception as e:
            raise Exception(f"Error in save_detection_data: {e}")



    def main(self, state, single_video=None, start=None, end=None):
        try:
            if single_video:
                final_output_path = self.predict(single_video, state, start=start, end=end)
                return
            path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'yolo-train/input')
            for file in os.listdir(path):
                if file.endswith('.mp4'):
                    final_output_path = self.predict(os.path.join(path, file), state, start=start, end=end)
                    print()
        except KeyboardInterrupt:
            print("\n中断")
        except Exception as e:
            print(f"Error in main: {e}")
            print(e.stacktrace())



    def process(self, state):
        try:
            video_path = state['video_path']
            start = state['chart_start']
            final_output_path = self.predict(video_path, state, start=start, end=None)
            return final_output_path

        except Exception as e:
            raise Exception(f"Error in NoteDetector: {e}")



if __name__ == "__main__":

    # raw 踊
    # 380, 9670, (1702, 702), r 568

    #video_path = r"C:\Users\ck273\Desktop\踊.mp4"
    #start=380
    #end=9670
    video_path = r"D:\git\mai-chart-analyse\yolo-train\input\test_6.00.mp4"
    start = 520
    end = 2910

    # O (1702, 702), R 568, start=400, end=9670
    cap = cv2.VideoCapture(video_path)
    state = {
        'total_frames': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        'circle_center': (1702, 703),
        # 1920x1080: 959, 539
        # 1080x1080: 539, 539
        'circle_radius': 568,
        'debug': True
    }
    cap.release()

    detector = NoteDetector()
    detector.main(state, video_path, start, end)
    #detector.main(state, start=400)
