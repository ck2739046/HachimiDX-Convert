from dataclasses import dataclass
from ultralytics import YOLO
from ultralytics.trackers import BOTSORT
import os
import cv2
import time
import numpy as np
from collections import defaultdict
from types import SimpleNamespace
from ultralytics.engine.results import OBB
from ultralytics.utils import LOGGER
import logging
import shutil
import traceback
import math


def export_video_module(self, track_results, std_video_path, output_dir, video_name):

    print("开始导出视频模块...")
    
    try:
        # 获取视频信息
        cap = cv2.VideoCapture(std_video_path)
        video_width = round(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        video_height = round(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = round(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # 输出视频设置
        temp_track_video_path = os.path.join(output_dir, f'{video_name}_tracked_temp.mp4')
        if os.path.exists(temp_track_video_path):
            os.remove(temp_track_video_path)

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(temp_track_video_path, fourcc, fps, (video_width, video_height))

        # 为不同ID生成不同颜色
        def get_color_for_id(track_id):
            color_palette = [
                (0, 0, 190),   # RED
                (190, 0, 0),   # BLUE
                (0, 170, 0),   # GREEN
                (0, 100, 200), # ORANGE
                (200, 0, 150), # PURPLE
                (180, 130, 0), # TEAL
                (160, 0, 210), # MAGENTA
                (0, 150, 160), # OLIVE
                (40, 80, 160)  # SIENNA
            ]
            # 使用track_id对颜色池长度取模来选择颜色
            color_index = track_id % len(color_palette)
            return color_palette[color_index]
        
        # 按帧号组织轨迹点
        frame_tracks = defaultdict(list)
        for track_id, track_data in track_results.items():
            if track_data['class_id'] is not None:
                for point in track_data['path']:
                    frame_tracks[point['frame']].append({
                        'track_id': track_id,
                        'class_id': track_data['class_id'],
                        'x1': point['x1'],
                        'y1': point['y1'],
                        'x2': point['x2'],
                        'y2': point['y2'],
                        'x3': point['x3'],
                        'y3': point['y3'],
                        'x4': point['x4'],
                        'y4': point['y4']
                    })
        
        # 存储轨迹历史用于绘制轨迹线
        track_history = defaultdict(list)
        track_last_seen = defaultdict(int)  # 记录轨迹最后出现的帧号
        
        # 逐帧处理
        start_time = time.time()
        last_start_time = start_time
        last_frame_number = 0
        
        for frame_number in range(total_frames):
            ret, frame = cap.read()
            if not ret:
                break
            
            # 获取当前帧的轨迹点
            current_tracks = frame_tracks.get(frame_number, [])
            
            # 更新当前帧中存在的轨迹
            current_track_ids = set()
            
            # 绘制当前帧的音符
            for track in current_tracks:
                track_id = track['track_id']
                class_id = track['class_id']
                color = get_color_for_id(track_id)
                
                # 记录当前帧中存在的轨迹
                current_track_ids.add(track_id)
                
                # 根据class_id绘制不同类型的音符
                if self.is_obb(class_id):
                    points = np.array([
                        [track['x1'], track['y1']],
                        [track['x2'], track['y2']],
                        [track['x3'], track['y3']],
                        [track['x4'], track['y4']]
                    ], dtype=np.int32)
                    cv2.polylines(frame, [points], True, color, 2)
                else:
                    x1, y1, x2, y2 = int(track['x1']), int(track['y1']), int(track['x3']), int(track['y3'])
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                
                # 绘制标签
                class_name = self.class_id_map.get(class_id, f'unknown')
                label = f'{class_name} ID:{track_id}'
                label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
                
                if self.is_obb(class_id):
                    # 找到OBB四个点中最上方的点作为标签位置；若y相同则选择x最小
                    points = [
                        (int(track['x1']), int(track['y1'])),
                        (int(track['x2']), int(track['y2'])),
                        (int(track['x3']), int(track['y3'])),
                        (int(track['x4']), int(track['y4']))
                    ]
                    label_x, label_y = min(points, key=lambda p: (p[1], p[0])) # 先选y最小，再选x最小
                else:
                    label_x = x1
                    label_y = y1
                
                cv2.rectangle(frame, (label_x, label_y - label_size[1] - 10), 
                            (label_x + label_size[0], label_y), color, -1)
                
                cv2.putText(frame, label, (label_x, label_y - 5), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                
                # 更新轨迹历史
                # 计算中心点：OBB 使用四点平均，其他类型使用矩形中心
                if self.is_obb(class_id):
                    center_x = int(round((track['x1'] + track['x2'] + track['x3'] + track['x4']) / 4.0))
                    center_y = int(round((track['y1'] + track['y2'] + track['y3'] + track['y4']) / 4.0))
                else:
                    center_x = int(round((track['x1'] + track['x3']) / 2.0))
                    center_y = int(round((track['y1'] + track['y3']) / 2.0))

                track_history[track_id].append((center_x, center_y))
                track_last_seen[track_id] = frame_number
                
                if len(track_history[track_id]) > 512:
                    track_history[track_id].pop(0)
            
            # 清理过期的轨迹（超过0.5秒未出现）
            tracks_to_remove = []
            timeout = fps // 2
            for track_id in list(track_history.keys()):
                if track_id not in current_track_ids:
                    frames_since_last_seen = frame_number - track_last_seen.get(track_id, frame_number)
                    if frames_since_last_seen > timeout:  # 超过0.5秒未出现，清理轨迹
                        tracks_to_remove.append(track_id)
            
            for track_id in tracks_to_remove:
                if track_id in track_history:
                    del track_history[track_id]
                if track_id in track_last_seen:
                    del track_last_seen[track_id]
            
            # 绘制轨迹线
            for track_id, points in track_history.items():
                if len(points) > 1:
                    color = get_color_for_id(track_id)
                    for i in range(1, len(points)):
                        cv2.line(frame, points[i-1], points[i], color, 3)
                    
                    # 在轨迹起点绘制小圆点
                    if points:
                        cv2.circle(frame, points[0], 3, color, -1)
            
            # 写入输出视频
            out.write(frame)
            
            # 显示进度
            if frame_number % 30 == 0:
                progress = (frame_number / total_frames) * 100
                end_time = time.time()
                elapsed_time = end_time - last_start_time
                elapsed_frame = frame_number - last_frame_number
                last_start_time = end_time # 重置时间给下一轮
                last_frame_number = frame_number # 重置帧数给下一轮
                fps_rate = elapsed_frame / elapsed_time if elapsed_time > 0 else 0
                print(f"导出进度: {frame_number}/{total_frames} ({progress:.1f}%) {fps_rate:.1f}fps", end="\r", flush=True)
        
        cap.release()
        out.release()

        elapsed_time = time.time() - start_time
        average_fps = total_frames / elapsed_time if elapsed_time > 0 else 0
        print(f"临时视频导出完成，耗时{elapsed_time:.1f}s, 平均{average_fps:.2f}fps               ")

        # 使用ffmpeg添加音频并且crf压缩
        final_track_video_path = temp_track_video_path.replace('_temp.mp4', '.mp4')
        if os.path.exists(final_track_video_path):
            os.remove(final_track_video_path)
        # 构建ffmpeg命令来合并视频和音频
        ffmpeg_args = [
            '-y', '-hide_banner', '-stats', '-loglevel', 'error',
            '-i', temp_track_video_path, # 无声的跟踪视频
            '-i', std_video_path,  # 原始视频（有音频）
            '-c:v', 'libx264',  '-preset', 'veryfast', '-crf', '23', '-pix_fmt', 'yuv420p',
            '-c:a', 'copy',    # 复制音频流
            '-map', '0:v:0',   # 使用第一个输入的视频流
            '-map', '1:a:0',   # 使用第二个输入的音频流
            '-shortest',       # 以最短的流为准
            final_track_video_path
        ]
        
        try:
            result = ffmpeg_utils.run_ffmpeg(ffmpeg_args)
            if result.returncode == 0:
                os.remove(temp_track_video_path)
            else:
                raise Exception("FFmpeg processing failed")
        except Exception as e:
            print(f"Warning: Error adding audio to temp_track_video - {e}")
            os.rename(temp_track_video_path, final_track_video_path)
        
        # 复制原始视频到输出目录
        new_std_video_path = os.path.join(output_dir, f'{video_name}_standardized.mp4')
        if os.path.exists(new_std_video_path):
            os.remove(new_std_video_path)
        shutil.copy(std_video_path, new_std_video_path)

        elapsed_time = time.time() - start_time
        print(f"追踪视频导出完成，总耗时{elapsed_time:.1f}s")
        print(f"追踪视频已保存到：{final_track_video_path}")

        return final_track_video_path

    except Exception as e:
        raise Exception(f"视频导出模块错误: {e}") 
