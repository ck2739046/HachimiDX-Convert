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
import shutil
import traceback

original_level = LOGGER.level
LOGGER.setLevel(logging.ERROR) # 只显示错误信息，忽略 Warning


class NoteDetector:
    def __init__(self):
        pass

    def obb_to_rect(self, obb_points):
        # obb_points: [x1, y1, x2, y2, x3, y3, x4, y4]
        x_coords = obb_points[0::2]  # 所有x坐标
        y_coords = obb_points[1::2]  # 所有y坐标
        # 计算最小外接矩形
        x1 = min(x_coords)
        y1 = min(y_coords)
        x2 = max(x_coords)
        y2 = max(y_coords)
        return x1, y1, x2, y2


    def predict(self, input_path, detect_model_path, obb_model_path, output_dir):

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
            video_name = os.path.basename(input_path).rsplit('.', 1)[0]
            print(f"Predict: {video_name}")
            print(f'Predict initialize...', end='\r', flush=True)
            # 获取视频信息
            cap = cv2.VideoCapture(input_path)
            video_width = round(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            video_height = round(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = round(cap.get(cv2.CAP_PROP_FPS))
            total_frames = round(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            # 输出视频设置：在 output_dir 下创建以 video_name 命名的子文件夹，作为新的 output_dir
            os.makedirs(output_dir, exist_ok=True)
            output_dir = os.path.join(output_dir, video_name)
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, f'{video_name}_tracked.mp4')
            if os.path.exists(output_path):
                os.remove(output_path)  # 如果输出文件已存在，删除它
            # 设置视频编码器
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, (video_width, video_height))


            # 初始化跟踪器
            trackers = []
            # trackers: tap, slide, touch, hold, touch_hold
            thresholds = [0.8, 0.95, 0.8, 0.8, 0.8]
            for thresh in thresholds:
                tracker_args = SimpleNamespace(
                    # 没有注释的全是默认参数
                    tracker_type='botsort',
                    track_high_thresh=0.25,
                    track_low_thresh=0.1,
                    new_track_thresh=0.25,
                    track_buffer=10,
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
            detect_model = YOLO(detect_model_path)
            obb_model = YOLO(obb_model_path)
            if torch.cuda.is_available():
                detect_model.to('cuda')
                obb_model.to('cuda')
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

            # 主循环
            while True:
                ret, frame = cap.read()
                if not ret: break # end of video

                # 使用两个模型预测当前帧
                detect_results = detect_model.predict(
                    source=frame,
                    conf=0.6,
                    iou=0.7,
                    verbose=False, # 关闭详细输出
                    device='cuda' if torch.cuda.is_available() else 'cpu',
                    max_det=50
                )
                
                obb_results = obb_model.predict(
                    source=frame,
                    conf=0.6,
                    iou=0.7,
                    verbose=False, # 关闭详细输出
                    device='cuda' if torch.cuda.is_available() else 'cpu',
                    max_det=50
                )

                # 直接使用原始检测结果
                track_results = []
                orig_shape = frame.shape[:2]
                
                # 初始化候选框字典
                candidates = {0: np.empty((0, 6)), 1: np.empty((0, 6)), 2: np.empty((0, 6)), 3: np.empty((0, 6)), 4: np.empty((0, 6))}
                
                # 处理detect模型结果
                if len(detect_results) > 0 and detect_results[0].boxes is not None:
                    all_boxes = detect_results[0].boxes.data.cpu().numpy()
                    
                    # 分离出各个class_id的检测框
                    tap_mask = all_boxes[:, 5] == 0
                    candidates[0] = (all_boxes[tap_mask])
                    slide_mask = all_boxes[:, 5] == 1
                    candidates[1] = (all_boxes[slide_mask])
                    touch_mask = all_boxes[:, 5] == 2
                    candidates[2] = (all_boxes[touch_mask])
                
                # 处理obb模型结果
                if len(obb_results) > 0 and obb_results[0].obb is not None:
                    # 获取OBB结果
                    obb_data = obb_results[0].obb
                    
                    # 获取多边形格式的OBB (xyxyxyxy)
                    xyxyxyxy = obb_data.xyxyxyxy.cpu().numpy()
                    # 获取类别
                    cls = obb_data.cls.cpu().numpy()
                    # 获取置信度
                    conf = obb_data.conf.cpu().numpy()
                    
                    # 分离出各个class_id的检测框并转换为矩形
                    touch_obb_mask = cls == 0
                    touch_hold_obb_mask = cls == 1
                    
                    # 转换touch OBB为矩形
                    if np.any(touch_obb_mask):
                        touch_obb_boxes = []
                        for i in range(len(xyxyxyxy)):
                            if touch_obb_mask[i]:
                                obb_points = xyxyxyxy[i].flatten()  # 展平为8个点
                                x1, y1, x2, y2 = self.obb_to_rect(obb_points)
                                touch_obb_boxes.append([x1, y1, x2, y2, conf[i], 2])  # class_id 2 = touch
                        candidates[2] = np.vstack([candidates[2], np.array(touch_obb_boxes)]) if len(touch_obb_boxes) > 0 else candidates[2]
                    
                    # 转换touch-hold OBB为矩形
                    if np.any(touch_hold_obb_mask):
                        touch_hold_obb_boxes = []
                        for i in range(len(xyxyxyxy)):
                            if touch_hold_obb_mask[i]:
                                obb_points = xyxyxyxy[i].flatten()  # 展平为8个点
                                x1, y1, x2, y2 = self.obb_to_rect(obb_points)
                                touch_hold_obb_boxes.append([x1, y1, x2, y2, conf[i], 4])  # class_id 4 = touch_hold
                        candidates[4] = np.array(touch_hold_obb_boxes) if len(touch_hold_obb_boxes) > 0 else candidates[4]
                
                # 将过滤后的结果重新封装为Boxes对象，再交给对应的追踪器处理
                for i in range(len(trackers)):
                    boxes = Boxes(candidates[i], orig_shape)
                    track_result = trackers[i].update(boxes, frame)
                    track_results.append(track_result)
                    

                    # 不再保存跟踪结果

                
                # 处理跟踪结果
                current_track_ids = set()  # 当前帧中存在的轨迹ID
                
                # 首先绘制原始检测结果
                # 绘制detect模型结果
                if len(detect_results) > 0 and detect_results[0].boxes is not None:
                    all_boxes = detect_results[0].boxes.data.cpu().numpy()
                    for box in all_boxes:
                        x1, y1, x2, y2, conf, class_id = box[:6]
                        x1, y1, x2, y2, class_id = round(x1), round(y1), round(x2), round(y2), round(class_id)
                        
                        # 获取颜色（使用class_id作为临时ID）
                        color = get_color_for_id(class_id)
                        # 绘制边界框
                        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                        # 绘制标签
                        class_name = ['tap', 'slide', 'touch', 'hold', 'touch_hold'][class_id]
                        label = f'{class_name} {conf:.2f}'
                        label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
                        cv2.rectangle(frame, (x1, y1 - label_size[1] - 10), 
                                    (x1 + label_size[0], y1), color, -1)
                        cv2.putText(frame, label, (x1, y1 - 5), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                
                # 绘制obb模型结果
                if len(obb_results) > 0 and obb_results[0].obb is not None:
                    # 获取OBB结果
                    obb_data = obb_results[0].obb
                    
                    # 获取多边形格式的OBB (xyxyxyxy)
                    xyxyxyxy = obb_data.xyxyxyxy.cpu().numpy()
                    # 获取类别
                    cls = obb_data.cls.cpu().numpy()
                    # 获取置信度
                    conf = obb_data.conf.cpu().numpy()
                    
                    for i in range(len(xyxyxyxy)):
                        # OBB格式: [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
                        points = xyxyxyxy[i]
                        class_id = int(cls[i])
                        confidence = conf[i]
                        
                        # 获取颜色（使用class_id + 3作为临时ID，避免与detect模型冲突）
                        color = get_color_for_id(class_id + 3)
                        # 绘制OBB边界框
                        cv2.polylines(frame, [points.astype(np.int32)], True, color, 2)
                        # 绘制标签
                        class_name = ['touch', 'touch_hold'][class_id]
                        label = f'{class_name} {confidence:.2f}'
                        label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
                        # 计算标签位置（使用第一个点）
                        label_x = int(points[0][0])
                        label_y = int(points[0][1])
                        cv2.rectangle(frame, (label_x, label_y - label_size[1] - 10), 
                                    (label_x + label_size[0], label_y), color, -1)
                        cv2.putText(frame, label, (label_x, label_y - 5), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                
                # 然后处理跟踪结果（仅用于轨迹线）
                for track_result in track_results:
                    if track_result is not None and len(track_result) > 0:
                        for track in track_result:
                            # 获取轨迹信息
                            if len(track) < 7: continue
                            x1, y1, x2, y2, track_id, conf, class_id = track[:7]
                            x1, y1, x2, y2, track_id, class_id = round(x1), round(y1), round(x2), round(y2), round(track_id), round(class_id)
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

                frame_count += 1
                fps_counter += 1

            end_time = time.time()
            average_fps_rate = frame_count / (end_time - start_time_fixed)
            print(f"predict done, average FPS: {average_fps_rate:.2f}            ")
            cap.release()
            out.release() 
            

            # 使用ffmpeg添加音频到跟踪视频
            final_output_path = output_path.replace('.mp4', '_with_audio.mp4')
            if os.path.exists(final_output_path):
                os.remove(final_output_path)
            # 构建ffmpeg命令来合并视频和音频
            audio_cmd = [
                'ffmpeg', '-y',
                '-i', output_path,  # 无声的跟踪视频
                '-i', input_path,  # 原始视频（有音频）
                '-c:v', 'copy',  # 复制视频流
                '-c:a', 'copy',  # 复制音频流
                '-map', '0:v:0',  # 使用第一个输入的视频流
                '-map', '1:a:0',  # 使用第二个输入的音频流
                '-shortest',  # 以最短的流为准
                final_output_path
            ]
            
            try:
                result = subprocess.run(audio_cmd, capture_output=True, text=True, encoding='utf-8')
                if result.returncode == 0:
                    # 成功添加音频，删除无声视频
                    os.remove(output_path)
                else:
                    raise Exception(result.stderr)
            except Exception as e:
                print(f"Warning: Error adding audio - {e}")
                # 发生错误时，重命名无声视频为最终输出
                os.rename(output_path, final_output_path)

            # 复制原始视频到输出目录
            original_video_path = os.path.join(output_dir, f'{video_name}.mp4')
            if os.path.exists(original_video_path):
                os.remove(original_video_path)
            shutil.copy(input_path, original_video_path)

            # 返回最终视频路径
            return final_output_path

        except Exception as e:
            raise Exception(f"Error in predict: {e}")
        






    def main(self, video_path, detect_model_path, obb_model_path, output_dir):
        try:
            final_output_path = self.predict(video_path, detect_model_path, obb_model_path, output_dir)
            return final_output_path
        except KeyboardInterrupt:
            print("\n中断")
        except Exception as e:
            print(f"Error in main: {e}")
            print(traceback.format_exc())



if __name__ == "__main__":

    video_path = r"D:\git\mai-chart-analyze\yolo-train\temp\DEICIDE_standardized.mp4"
    detect_model_path = r"C:\Users\ck273\Desktop\detect_varifocalloss.pt"
    obb_model_path = r"C:\Users\ck273\Desktop\obb.pt"
    output_dir = r"D:\git\mai-chart-analyze\yolo-train\runs\detect"
    
    detector = NoteDetector()
    final_output_path = detector.main(video_path, detect_model_path, obb_model_path, output_dir)
    print(f"处理完成，输出文件：{final_output_path}")
