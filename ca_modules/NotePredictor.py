from ultralytics import YOLO
import os
import cv2
import time
import torch

class NotePredictor:

    def __init__(self):
        self.model_path = 'runs/train/note_detection1080/weights/best.pt'
    

    def process(self, state):
        try:
            label_path, predict_avi_path = self.predict(state['video_path'], state)
            predict_labels = self.read_labels(label_path, state)
            return predict_labels, predict_avi_path
        except Exception as e:
            raise Exception(f"Error in NotePredictor: {e}")
        

    def read_labels(self, label_path, state):
        """
        读取YOLO标签文件夹中的txt文件，返回字典格式的预测结果
        
        Args:
            label_path: 标签文件夹路径
            state: 状态字典，包含视频信息
            
        Returns:
            dict: {frame_number: [label_data, ...]}
            每个label_data包含: {class_id, x_center, y_center, width, height, confidence}
        """
        try:
            predict_labels = {}
            
            # 检查标签文件夹是否存在
            if not os.path.exists(label_path):
                print(f"NotePredictor: 标签文件夹不存在: {label_path}")
                return predict_labels
            
            # 获取所有txt文件并按帧数排序
            txt_files = [f for f in os.listdir(label_path) if f.endswith('.txt')]
            
            if not txt_files:
                print(f"NotePredictor: 标签文件夹中没有找到txt文件: {label_path}")
                return predict_labels
            
            # 按文件名中的帧数排序（YOLO输出格式通常是 frame_000001.txt）
            txt_files.sort(key=lambda x: int(x.split('_')[-1].split('.')[0]) if '_' in x else int(x.split('.')[0]))
            
            print(f"NotePredictor: 正在读取 {len(txt_files)} 个标签文件...")
            
            for i, txt_file in enumerate(txt_files):
                txt_path = os.path.join(label_path, txt_file)
                
                # 从文件名提取帧数
                if '_' in txt_file:
                    # 格式: frame_000001.txt
                    frame_number = int(txt_file.split('_')[-1].split('.')[0])
                else:
                    # 格式: 000001.txt 或直接使用索引
                    try:
                        frame_number = int(txt_file.split('.')[0])
                    except:
                        frame_number = i + 1  # 如果解析失败，使用索引
                
                # 读取该帧的标签数据
                frame_labels = []
                
                try:
                    with open(txt_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                            
                        # 解析YOLO格式: class_id x_center y_center width height confidence
                        parts = line.split()
                        if len(parts) >= 6:  # 确保有置信度
                            label_data = {
                                'class_id': int(parts[0]),
                                'x_center': float(parts[1]),
                                'y_center': float(parts[2]),
                                'width': float(parts[3]),
                                'height': float(parts[4]),
                                'confidence': float(parts[5])
                            }
                            frame_labels.append(label_data)
                        elif len(parts) >= 5:  # 没有置信度的情况
                            label_data = {
                                'class_id': int(parts[0]),
                                'x_center': float(parts[1]),
                                'y_center': float(parts[2]),
                                'width': float(parts[3]),
                                'height': float(parts[4]),
                                'confidence': 1.0  # 默认置信度
                            }
                            frame_labels.append(label_data)
                            
                except Exception as e:
                    print(f"NotePredictor: 读取标签文件出错 {txt_file}: {e}")
                    continue
                
                # 将该帧的标签数据添加到结果字典
                predict_labels[frame_number] = frame_labels
                
                # 显示进度
                if (i + 1) % 100 == 0 or i == len(txt_files) - 1:
                    progress = ((i + 1) / len(txt_files)) * 100
                    print(f"NotePredictor: 读取标签文件...{i + 1}/{len(txt_files)} ({progress:.1f}%)", end="\r")
            
            print(f"NotePredictor: 读取标签文件完成，共处理 {len(predict_labels)} 帧")
            return predict_labels
            
        except Exception as e:
            raise Exception(f"Error in read_labels: {e}")


    def crop_video_to_square(self, input_path, state):

        try:
            width = state['video_width']
            height = state['video_height']
            fps = state['video_fps']
            total_frames = state['total_frames']

            # 设置临时输出路径
            temp_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "temp")
            os.makedirs(temp_dir, exist_ok=True)
            output_path = os.path.join(temp_dir, f'{os.path.basename(input_path)}_cropped.mp4')
            if os.path.exists(output_path):
                print(f"NotePredictor: 找到了裁剪后的视频, 将跳过裁剪并使用这个文件: {output_path}")
                return output_path

            # 计算裁剪尺寸和位置
            crop_size = min(width, height)
            x_offset = (width - crop_size) // 2
            y_offset = (height - crop_size) // 2
            print(f"crop: {width}x{height} -> {crop_size}x{crop_size}")

            # 设置视频编码器
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, (crop_size, crop_size))
            
            frame_count = 0
            cap = cv2.VideoCapture(input_path)
            while True:
                ret, frame = cap.read()
                if not ret: break
                
                # 裁剪帧
                cropped_frame = frame[y_offset:y_offset + crop_size, x_offset:x_offset + crop_size]
                out.write(cropped_frame)
                
                frame_count += 1
                if frame_count % 50 == 0:
                    progress = (frame_count / total_frames) * 100
                    print(f"NotePredictor: crop_video_to_square...{frame_count}/{total_frames} ({progress:.1f}%)", end="\r")

            print(f"NotePredictor: crop_video_to_square...done                                   ")
                
            cap.release()
            out.release()
            return output_path
        
        except Exception as e:
            raise Exception(f"Error in crop_video_to_square: {e}")


    def predict(self, input_path, state):

        try:
            # 检查视频尺寸，如果不是正方形则进行裁剪
            og_input_path = input_path
            width = state['video_width']
            height = state['video_height']
            if width != height:
                print(f"NotePredictor: 检测到非正方形视频，正在裁剪...")
                input_path = self.crop_video_to_square(input_path, state)

            # 加载模型
            model_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), self.model_path)
            model = YOLO(model_path)
            if torch.cuda.is_available():
                model.to('cuda')
                print(f"NotePredictor: 使用GPU: {torch.cuda.get_device_name(0)}")
            
            fps_counter = 0
            start_time = time.time()
            fps = 0
            frame_count = 0
            batch_num = 40
            total_frames = state['total_frames']
            output_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "runs/detect")
            video_name = os.path.basename(input_path)

            results = model.predict(
                source=input_path,
                conf=0.5,           # 置信度阈值
                iou=0.7,            # NMS IoU阈值
                save=True,          # 保存结果
                save_txt=True,      # 保存检测坐标
                save_conf=True,     # 保存置信度
                project=output_path,  # 输出目录
                name=video_name,    # 实验名称
                verbose=False,      # 关闭详细输出
                stream=True,        # 启用流式处理，可以逐帧处理
                device='cuda' if torch.cuda.is_available() else 'cpu',  # 使用GPU或CPU
                batch=batch_num,
                max_det=50,
                rect=True          # 启用矩形推理
            )

            for result in results:

                frame_count += 1
                fps_counter += 1

                if fps_counter < batch_num:
                    continue

                progress = (frame_count / total_frames) * 100

                # 计算fps
                current_time = time.time()
                fps = fps_counter / (current_time - start_time)
                start_time = current_time
                fps_counter = 0

                if total_frames - frame_count < batch_num:
                    print(f"NotePredictor: predict...{total_frames}/{total_frames} (100.0%) {fps:.1f}fps", flush=True)
                else:
                    print(f"NotePredictor: predict...{frame_count}/{total_frames} ({progress:.1f}%) {fps:.1f}fps", end="\r", flush=True)

            print("NotePredictor: predict...done")
            
            # 如果使用了裁剪的临时文件，删除它以节省空间
            if input_path != og_input_path:
                if os.path.exists(input_path):
                    os.remove(input_path)
                # 清理空文件夹
                temp_dir = os.path.dirname(input_path)
                if not os.listdir(temp_dir):
                    os.rmdir(temp_dir)

            label_path = os.path.join(output_path, video_name, "labels")
            predict_avi_path = os.path.join(output_path, video_name, f"{video_name}.avi")

            if not os.path.exists(label_path):
                raise FileNotFoundError(f"NotePredictor: 预测标签不存在: {label_path}")
            if not os.path.exists(predict_avi_path):
                raise FileNotFoundError(f"NotePredictor: 预测结果不存在: {predict_avi_path}")
            
            return label_path, predict_avi_path

        except Exception as e:
            raise Exception(f"Error in predict: {e}")
        