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


original_level = LOGGER.level
LOGGER.setLevel(logging.ERROR) # 只显示错误信息，忽略 Warning

class NoteDetector:
    def __init__(self):
        












    # debug
    def classification_module(self, track_results, std_video_path,
                              batch_cls, inference_device,
                              cls_ex_model_path, cls_break_model_path):
        try:
            print("开始分类模块...")
            start_time = time.time()

            cap = cv2.VideoCapture(std_video_path)

            # 构建采样计划，这样后续读取视频时，就知道当前帧要裁剪哪些图像
            sampling_plan, total_cls_quantity = self._build_sampling_plan(track_results)
            if not sampling_plan:
                print("没有需要分类的轨迹")
                return None
            
            # 准备变量
            counter = 0
            last_counter = 0
            last_time = start_time

            cls_results_all = []
            images_batch_buffer = []

            cls_ex_model = YOLO(cls_ex_model_path)
            cls_break_model = YOLO(cls_break_model_path)
            imgsz = self.get_imgsz('cls')

            total_frames = round(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            crop_border = round(cap.get(cv2.CAP_PROP_FRAME_WIDTH) * 0.003)

            # 按帧读取视频，提取图像并分类
            for frame_number in range(total_frames):
                # 读取当前帧
                ret, frame = cap.read()
                if not ret: break
                # 获取当前帧的采样计划
                if frame_number not in sampling_plan.keys():
                    continue # skip
                this_frame_sample_plan = sampling_plan[frame_number]
                # 提取当前帧的所有采样图像
                cropped_images = self._extract_note_images_in_frame(frame, this_frame_sample_plan, frame_number, crop_border)
                if cropped_images is None:
                    continue
                # 写入batch
                images_batch_buffer.extend(cropped_images)

                # 如果凑满一个batch，就进行分类
                while len(images_batch_buffer) >= batch_cls:
                    # 从buffer中取出一个batch
                    consumed_batch = images_batch_buffer[:batch_cls]
                    images_batch_buffer = images_batch_buffer[batch_cls:]
                    # 分类
                    cls_results = self._classify_image_batch(consumed_batch,
                                                             cls_ex_model, cls_break_model,
                                                             inference_device, imgsz)
                    cls_results_all.extend(cls_results)
                    # 打印进度
                    counter += len(cls_results)
                    last_time, last_counter = self.print_progress('分类', ' images/s', counter, total_cls_quantity, last_time, last_counter)

                # end of frame loop


            # 视频读取完毕后，batch buffer可能有剩余的未分类图像
            if images_batch_buffer:
                cls_results = self._classify_image_batch(images_batch_buffer,
                                                         cls_ex_model, cls_break_model,
                                                         inference_device, imgsz)
                cls_results_all.extend(cls_results)

            # 根据分类结果，更新track_results
            track_results = self._merge_cls_into_track_results(track_results, cls_results_all)

            # 结束
            finish_time = time.time()
            print(f"分类模块完成, 耗时{finish_time - start_time:.1f}s                       ")
            return track_results
            
        except Exception as e:
            print(f"Error in classification_module: {e}")
            print(traceback.format_exc())
            return None
        finally:
            cap.release()



    def _build_sampling_plan(self, track_results):

        sampling_plan = defaultdict(list)
        counter = 0
        
        for track_id, track_data in track_results.items():
            # 获取class_id
            class_id = track_data.get('class_id', None)
            if class_id is None or len(track_data['path']) == 0: continue
            # 确保是main_class_id
            class_id = self.get_main_class_id(class_id)
            # 跳过不需要分类的音符
            if not self.need_cls(class_id): continue

            # 从一个音符的轨迹中选取采样点
            path_length = len(track_data['path'])
            if self.is_obb(class_id):
                # 尽量选择早期的点，避免在后续长条hold时被闪烁特效干扰
                # 间距不同(2-7)，防止周期性闪烁全部采样到同一位置
                sample_positions = [10, 12, 15, 19, 24, 30, 37]
            else:
                # detect 模型，间距(7-12)
                sample_positions = [20, 27, 35, 44, 54, 65, 77]

            for sample_position in sample_positions:
                sample_idx = int(path_length * sample_position / 100.0)
                if sample_idx >= path_length:
                    continue
                # 获取采样点信息
                box = track_data['path'][sample_idx]
                frame_number = box['frame']
                # 写入采样计划
                sampling_plan[frame_number].append({
                    'track_id': track_id,
                    'sample_position': sample_position,
                    'box': box,
                    'class_id': class_id
                })
                counter += 1
        
        return sampling_plan, counter
    


    def _extract_note_images_in_frame(self, frame, this_frame_sample_plan, frame_number, crop_border):
        try:
            cropped_images = []

            for sample_data in this_frame_sample_plan:

                track_id = sample_data['track_id']
                sample_position = sample_data['sample_position']
                box = sample_data['box']
                class_id = sample_data['class_id']

                # 对于普通矩形框，裁剪范围就是(x1, y1, x3, y3)
                if not self.is_obb(class_id):
                    x1, y1, x2, y2 = int(box['x1']), int(box['y1']), int(box['x3']), int(box['y3'])
                    target_frame = frame

                # obb需要先将检测框和图像旋转为水平
                else:
                    # 获取检测框四个点坐标
                    points = np.array([
                        [box['x1'], box['y1']],
                        [box['x2'], box['y2']],
                        [box['x3'], box['y3']],
                        [box['x4'], box['y4']]
                    ], dtype=np.float32)
                    # 计算旋转角度
                    angle = (box['r'] * 180 / np.pi) - 90
                    # dx = box['x2'] - box['x1']
                    # dy = box['y2'] - box['y1']
                    # angle = np.arctan2(dy, dx) * 180 / np.pi
                    # 计算旋转中心
                    cx = np.mean(points[:, 0])
                    cy = np.mean(points[:, 1])
                    # 获取旋转矩阵
                    rotation_matrix = cv2.getRotationMatrix2D((cx, cy), angle, 1.0)
                    # 旋转整个图像为水平
                    target_frame = cv2.warpAffine(frame, rotation_matrix, (frame.shape[1], frame.shape[0]))
                    # 旋转四个点为水平
                    rotated_points = cv2.transform(points.reshape(1, -1, 2), rotation_matrix).reshape(-1, 2)
                    # 计算旋转后的边界框
                    x_coords = rotated_points[:, 0]
                    y_coords = rotated_points[:, 1]
                    x1, y1 = int(np.min(x_coords)), int(np.min(y_coords))
                    x2, y2 = int(np.max(x_coords)), int(np.max(y_coords))

                # 稍微扩展一圈
                x1 -= crop_border
                y1 -= crop_border
                x2 += crop_border
                y2 += crop_border
                # 裁剪范围边界检查
                x1 = max(0, x1)
                y1 = max(0, y1)
                x2 = min(target_frame.shape[1], x2)
                y2 = min(target_frame.shape[0], y2)
                if x1 >= x2 or y1 >= y2:
                    print(f"无效的裁剪区域: {frame_number}: ({x1}, {y1}), ({x2}, {y2}), is_obb={self.is_obb(class_id)}")
                    return None
                # 裁剪图像
                cropped_image = target_frame[y1:y2, x1:x2]
                # 保存信息
                cropped_data = {
                    'frame': frame_number,
                    'track_id': track_id,
                    'sample_position': sample_position,
                    'class_id': class_id,
                    'cropped_image': cropped_image
                }
                cropped_images.append(cropped_data)

            return cropped_images

        except Exception as e:
            print(f"提取第{frame_number}帧的图像时出错: {e}")
            return None
        


    def _classify_image_batch(self, consumed_batch, cls_ex_model, cls_break_model, inference_device, imgsz):

        try:
            # extract images and info
            images = [item['cropped_image'] for item in consumed_batch]
            images_info = [(item['frame'], item['track_id'], item['sample_position'], item['class_id']) for item in consumed_batch]

            # 模型推理
            ex_results = cls_ex_model.predict(
                task='classify',
                source=images,
                conf=0.5,
                verbose=False,
                device=inference_device,
                imgsz=imgsz,
                half=True
            )
            break_results = cls_break_model.predict(
                task='classify',
                source=images,
                conf=0.5,
                verbose=False,
                device=inference_device,
                imgsz=imgsz,
                half=True
            )

            # 解析yolo结果
            ex_flags = []
            for res in ex_results:
                is_ex = False
                if hasattr(res, 'probs') and res.probs is not None:
                    ex_probs = res.probs.data.cpu().numpy()
                    if len(ex_probs) >= 2: # 第一个是"no"，第二个是"yes"
                        is_ex = ex_probs[1] > ex_probs[0]
                ex_flags.append(bool(is_ex))

            break_flags = []
            for res in break_results:
                is_break = False
                if hasattr(res, 'probs') and res.probs is not None:
                    break_probs = res.probs.data.cpu().numpy()
                    if len(break_probs) >= 2: # 第一个是"no"，第二个是"yes"
                        is_break = break_probs[1] > break_probs[0]
                break_flags.append(bool(is_break))

            # reformat results
            final_cls_results = []
            for i, (frame_number, track_id, sample_position, class_id) in enumerate(images_info):
                data = {
                    'track_id': track_id,
                    'is_ex': ex_flags[i],
                    'is_break': break_flags[i],
                    'frame': frame_number,
                    'sample_position': sample_position,
                    'class_id': class_id
                }
                final_cls_results.append(data)

            return final_cls_results

        except Exception as e:
            print(f"批量分类错误: {e}")
            return None



    def _merge_cls_into_track_results(self, track_results, cls_results_all):

        # 根据分类结果is_ex, is_break计算specific_id，按track_id分组
        class_ids_by_track = defaultdict(list)
        for cls_result in cls_results_all:
            track_id = cls_result['track_id']
            is_ex = cls_result['is_ex']
            is_break = cls_result['is_break']
            class_id = cls_result['class_id']
            specific_class_id = self.get_specific_class_id(class_id, is_ex, is_break)
            class_ids_by_track[track_id].append(specific_class_id)
        
        # 每个音符有多个候选点和分类结果，采用最多的类别作为最终结果
        for track_id, class_ids in class_ids_by_track.items():
            if track_id not in track_results:
                continue
            if len(class_ids) == 0:
                continue
            
            # 统计每个class_id的出现次数
            counts = {}
            for class_id in class_ids:
                counts[class_id] = counts.get(class_id, 0) + 1
            
            max_count = max(counts.values())
            most_common = [k for k, v in counts.items() if v == max_count]
            
            if len(most_common) == 1:
                # 有明确的一个最多数
                final_class_id = most_common[0]
            else:
                # 没有明确的多数，默认is_break=False, is_ex=False
                final_class_id = self.get_specific_class_id(most_common[0], False, False)
                print(f"警告: 轨迹 {track_id} 的采样点分类结果不一致，采用默认分类 {final_class_id}")

            # 更新track_results的class_id
            track_results[track_id]['class_id'] = final_class_id

        return track_results
    











    # debug
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
 









    # debug
    def main(self, std_video_path, output_dir,
             batch_detect, batch_cls, inference_device,
             detect_model_path, obb_model_path, cls_ex_model_path, cls_break_model_path,
             skip_detect=False, skip_cls=False, skip_export_tracked_video=False):
        try:
            # 检查输入文件
            paths = []
            for path in [std_video_path, detect_model_path, obb_model_path, cls_ex_model_path, cls_break_model_path]:
                path = os.path.abspath(path)
                path = os.path.normpath(path)
                if not os.path.exists(path):
                    raise FileNotFoundError(f"模型不存在: {path}")
                paths.append(path)
            std_video_path, detect_model_path, obb_model_path, cls_ex_model_path, cls_break_model_path = paths 
            # 检查输出目录
            output_dir = os.path.abspath(output_dir)
            output_dir = os.path.normpath(output_dir)
            os.makedirs(output_dir, exist_ok=True)
            video_name = os.path.basename(output_dir) # 使用输出目录名作为视频名称
            # 检查模型配置
            if batch_detect <= 0 or batch_cls <= 0:
                raise ValueError(f"batch_detect 或 batch_cls 参数无效, 必须大于0: batch_detect={batch_detect}, batch_cls={batch_cls}")
            inference_device = str(inference_device)
            if inference_device.lower() == 'none':
                inference_device = None

            # 检测模块
            if not skip_detect:
                detect_results = self.detect_module(std_video_path, output_dir,
                                                    batch_detect, inference_device,
                                                    detect_model_path, obb_model_path)
            else:
                # 如果跳过检测，使用已有的检测结果
                detect_result_path = os.path.join(output_dir, "detect_result.txt")
                if not os.path.exists(detect_result_path):
                    raise FileNotFoundError(f"检测结果文件不存在: {detect_result_path}")
                print("跳过检测模块，使用已有检测结果...")
                detect_results = self._load_detect_results(detect_result_path)


            # 追踪模块
            track_results = self.track_module(detect_results, std_video_path)
            cls_track_results = track_results.copy()

            # 分类模块
            if not skip_cls:
                cls_track_results = self.classification_module(cls_track_results, std_video_path,
                                                               batch_cls, inference_device,
                                                               cls_ex_model_path, cls_break_model_path)
            else:
                print("跳过分类模块")


            # 保存最终追踪结果
            if not skip_cls and cls_track_results is not None:
                final_track_results = cls_track_results
                self._save_track_results(final_track_results, output_dir, True)
            else:
                final_track_results = track_results
                self._save_track_results(final_track_results, output_dir, False)
            

            # 导出追踪视频模块
            if not skip_export_tracked_video:
                self.export_video_module(final_track_results, std_video_path, output_dir, video_name)
            else:
                print("跳过导出视频模块")


            return output_dir
            
        except KeyboardInterrupt:
            print("\n中断")
        except Exception as e:
            print(f"Error in NoteDetector.main: {e}")
            print(traceback.format_exc())




if __name__ == "__main__":

    detector = NoteDetector()
    detector.main(
        r'd:\git\aaa-HachimiDX-Convert\src\temp\ニルヴの心臓 MASTER 14.3_standardized.mp4',
        r"D:\git\aaa-HachimiDX-Convert\aaa-result\ニルヴの心臓 MASTER 14.3",
        2,    # batch_detect
        16,   # batch_cls
        '0',  # inference_device
        r"D:\git\aaa-HachimiDX-Convert\src\models\detect.engine",
        r"D:\git\aaa-HachimiDX-Convert\src\models\obb.pt",
        r"D:\git\aaa-HachimiDX-Convert\src\models\cls-ex.pt",
        r"D:\git\aaa-HachimiDX-Convert\src\models\cls-break.pt",
        skip_detect=False,               # 是否跳过检测
        skip_cls=False,                  # 是否跳过分类
        skip_export_tracked_video=False  # 是否跳过导出视频
    )
