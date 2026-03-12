from pathlib import Path
from typing import Tuple
import cv2
import shutil
import subprocess

from ...schemas.op_result import OpResult, ok, err, print_op_result
from src.core.schemas.media_config import MediaType, MediaConfig_Definition
from src.core.schemas.media_config import MediaConfig_Definitions as M_Defs
from src.services import PathManage
from src.services.pipeline import MediaPipeline




def main(input_video: Path,
         video_name: str,
         circle_center: Tuple[int, int],
         circle_radius: int,
         media_type: MediaType,
         duration: float,
         start_sec: float = 0.0,
         end_sec: float = 0.0,
         target_res: int = 1080
        ) -> OpResult[Path]:
    
    """
    生成标准化视频 主入口

    Args:
        input_video(Path): 输入视频路径
        video_name(str): 视频名称（不带扩展名）
        circle_center(Tuple[int, int]): 圆心坐标
        circle_radius(int): 圆半径
        media_type(MediaType): 媒体类型 video_with_audio / video_without_audio
        duration(float): 视频总时长(秒)
        start_sec(float): 开始时间(秒)
        end_sec(float): 结束时间(秒)
        target_res(int): 目标分辨率(边长)，默认 1080

    Returns:
        OpResult[Path]: 标准化后的视频的完整路径
    """

    try:

        print("Process video...")

        # 获取视频基本信息
        cap = cv2.VideoCapture(input_video)
        if not cap.isOpened():
            return err(f"Cannot open video file: {input_video}")
        video_width = round(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        video_height = round(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()




        crop_size, crop_x, crop_y = calculate_crop_params(video_width, video_height, circle_center, circle_radius, target_res)
        
        result = build_output_path(video_name)
        if not result.is_ok:
            return result
        output_path = result.value

        is_output_std = is_output_already_standardized(output_path, target_res, duration, start_sec, end_sec)
        if is_output_std:
            return ok(output_path) # 如果输出已经标准了，直接返回
        
        is_input_std, need_crop, need_resize, need_trim_start, need_trim_end = is_input_already_standardized(crop_size, crop_x, crop_y, video_width, video_height, target_res, start_sec, end_sec)
        if is_input_std:
            # 如果输入已经标准了，直接复制到输出路径
            print("Input video already standardized, copy to output path.")
            try:
                # 如果输出文件已存在，先删除
                if output_path.exists():
                    output_path.unlink()
                # 复制输入文件到输出路径
                shutil.copy2(input_video, output_path)
                return ok(output_path)
            except Exception as e:
                return err(f"Failed to copy video file: {e}")
        




        # 构建参数
        params = {
            M_Defs.media_type.key: media_type,
            M_Defs.input_path.key: str(input_video.resolve()),
            M_Defs.output_path.key: str(output_path.resolve()),
            M_Defs.duration.key: duration,
        }

        if need_crop:
            params.update({
                M_Defs.video_crop_w.key: crop_size,
                M_Defs.video_crop_h.key: crop_size,
                M_Defs.video_crop_x.key: crop_x,
                M_Defs.video_crop_y.key: crop_y,
            })

        if need_resize:
            params.update({
                M_Defs.video_side_resolution.key: target_res,
            })
        
        if need_trim_start:
            params.update({
                M_Defs.start.key: start_sec,
            })

        if need_trim_end:
            params.update({
                M_Defs.end.key: end_sec,
            })

        change_hint = ''

        if need_crop:
            change_hint += f'  crop to {crop_size}:{crop_size}:{crop_x}:{crop_y} (w:h:x:y)\n'
        if need_resize:
            change_hint += f'  resize to {target_res}x{target_res}\n'
        if need_trim_start:
            change_hint += f'  trim start to {start_sec}s\n'
        if need_trim_end:
            change_hint += f'  trim end to {end_sec}s\n'

        if change_hint:
            print(f"Process video with changes:\n{change_hint}")




        # 实际运行 ffmpeg
        v_res = MediaPipeline.validate(params)
        if not v_res.is_ok:
            return err(f"Failed to validate process video parameters.", inner = v_res)
        
        cmd_res = MediaPipeline.build_cmd(v_res.value)
        if not cmd_res.is_ok:
            return err(f"Failed to build ffmpeg command.", inner = cmd_res)
            
        cmd = cmd_res.value
        
        print("Running FFmpeg command:", " ".join(cmd))
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=False,
                text=True,
                encoding='utf-8'
            )
            if result.returncode != 0:
                error_msg = f'Standardize video process: ffmpeg failed with exit code: {result.returncode}'
                return err(error_msg)
            
        except Exception as e:
            raise Exception("FFmpeg processing failed", e)
        
        # 二次验证：确保输出文件存在且参数符合预期
        if not is_output_already_standardized(output_path, target_res, duration, start_sec, end_sec):
            return err("Output video is invalid after processing.")
        
        print("Process video...Ok")

        return ok(output_path)

    except Exception as e:
        return err(f"Unexcepted error in process_video", error_raw = e)
    



def calculate_crop_params(video_width: int,
                          video_height: int,
                          circle_center: Tuple[int, int],
                          circle_radius: int,
                          target_res: int
                        ) -> Tuple[int, int, int]:
    
    video_size = min(video_width, video_height)
    tolerance = video_size / 360

    # 计算最后裁剪出的视频的尺寸
    crop_size = circle_radius * 2
    if abs(crop_size - target_res) < tolerance*2:
        # 如果接近目标分辨率，则直接设为目标分辨率
        crop_size = target_res
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

    return crop_size, crop_x, crop_y






def is_input_already_standardized(crop_size: int,
                                  crop_x: int,
                                  crop_y: int,
                                  video_width: int,
                                  video_height: int,
                                  target_res: int,
                                  start_sec: float,
                                  end_sec: float
                                 ) -> tuple[bool, bool, bool, bool, bool]:

    video_size = min(video_width, video_height)
    tolerance = video_size / 360

    need_crop = True
    need_resize = True
    need_trim_start = True
    need_trim_end = True

    # 如果裁剪画面尺寸≈实际视频尺寸，并且裁剪中心≈实际视频中心，则不裁剪
    if abs(crop_size - video_size) < tolerance*2 and crop_x < tolerance and crop_y < tolerance:
        need_crop = False

    # resize
    if crop_size == target_res:
        need_resize = False

    # trim
    if start_sec <= 0:
        need_trim_start = False
    if end_sec <= 0:
        need_trim_end = False
    
    if not need_crop and not need_resize and not need_trim_start and not need_trim_end:
        print("Video already standardized.")
        return True, False, False, False, False
    
    return False, need_crop, need_resize, need_trim_start, need_trim_end







def build_output_path(video_name: str) -> OpResult[Path]:
    
    output_dir = PathManage.TEMP_DIR
    output_filename = f"{video_name}_std.mp4"
    output_path = output_dir / output_filename

    return ok(output_path.resolve())







def is_output_already_standardized(output_path: Path,
                                   target_res: int,
                                   duration: float,
                                   start_sec: float,
                                   end_sec: float
                                  ) -> bool:
    
    """如果视频已存在，检查分辨率+时长是否符合要求，如果符合则视为已标准化"""
    
    if not output_path.exists():
        return False
    
    try:
        cap = cv2.VideoCapture(output_path)
        output_width = round(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        output_height = round(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        output_total_frames = round(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        output_fps = cap.get(cv2.CAP_PROP_FPS)
        cap.release()
        
        if output_width != target_res or output_height != target_res:
            raise(f'output resolution mismatch, expect {target_res}x{target_res}, got {output_width}x{output_height}.')
        
        output_duration = output_total_frames / output_fps
        expect_duration = duration - start_sec if end_sec <=0 else end_sec - start_sec
        # 允许 0.5 秒误差
        if abs(output_duration - expect_duration) > 0.5:
            raise(f'output duration mismatch, expect {expect_duration}s, got {output_duration}s.')

        print(f"Standardized video already exists")
        return True  
        
    except Exception as e:
        print(f"Warning: {e}")
        print('standardized video exists but invalid, will re-generate.')
        return False
