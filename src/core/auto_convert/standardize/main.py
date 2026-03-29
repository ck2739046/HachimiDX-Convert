from pathlib import Path

from ...schemas.op_result import OpResult, ok, err, print_op_result
from ...schemas.media_model import MediaType
from src.services import PathManage

from . import detect_circle
from .manual_adjust import ManualAdjust
from . import process_video




def main(input_video: Path,
         song_name: str,
         video_mode: str,
         media_type: MediaType,
         duration: float,
         start_sec: float = 0.0,
         end_sec: float = 0.0,
         skip_detect_circle: bool = False,
         target_res: int = 1080
        ) -> OpResult[Path]:
    
    """
    规范化视频 主入口

    Args:
        input_video(Path): 输入视频路径
        song_name(str): 歌曲名称（不带扩展名）
        video_mode(str): 视频模式 source video / camera footage
        media_type(MediaType): 媒体类型 video_with_audio / video_without_audio
        duration(float): 视频总时长(秒)
        start_sec(float): 开始时间(秒)
        end_sec(float): 结束时间(秒)
        skip_detect_circle(bool): 是否跳过圆心检测，默认 False
        target_res(int): 目标分辨率(边长)，默认 1080

    Returns:
        OpResult[Path]: 标准化后的视频的完整路径
    """
    
    try:
        print("Standardize...")

        # 第一步：检测圆形判定线
        result = detect_circle.main(
            input_video=input_video,
            mode=video_mode,
            skip_detect_circle=skip_detect_circle
        )
        if not result.is_ok:
            return err("Failed to detect circle.", inner=result)
        circle_center, circle_radius = result.value
        scale_x, scale_y = 1.0, 1.0

        # 第二步：手动微调圆心和半径
        if not skip_detect_circle:
            result = ManualAdjust(
                input_video=input_video,
                circle_center=circle_center,
                circle_radius=circle_radius,
                start_sec=start_sec,
                end_sec=end_sec
            ).main()
            if not result.is_ok:
                return err("Failed to manual adjust circle.", inner=result)
            circle_center, circle_radius, scale_x, scale_y = result.value
        # 第三步：构建输出路径
        output_filename = f"{song_name}_std.mp4"
        temp_output_path = PathManage.TEMP_DIR / output_filename

        result = PathManage.get_main_output_dir()
        if not result.is_ok:
            return err(f"Failed to get main output dir", inner = result)
        main_output_dir = result.value
        
        final_output_dir = main_output_dir / song_name
        final_output_path = final_output_dir / output_filename

        # 第四步：处理视频
        result = process_video.main(
            input_video=input_video,
            temp_output_path=temp_output_path,
            final_output_path=final_output_path,
            circle_center=circle_center,
            circle_radius=circle_radius,
            scale_x=scale_x,
            scale_y=scale_y,
            media_type=media_type,
            duration=duration,
            start_sec=start_sec,
            end_sec=end_sec,
            target_res=target_res
        )
        if not result.is_ok:
            return err("Failed to process video.", inner=result)
        std_output_path = result.value

        # 第五步：移动到正式输出目录
        if std_output_path != final_output_path:
            try:
                final_output_dir.mkdir(parents=True, exist_ok=True)
                std_output_path.replace(final_output_path)
            except Exception as e:
                return err(f"Failed to move output video to main output dir.", error_raw=e)

        return ok(final_output_path)
        
    except Exception as e:
        return err(f"Unexcepted error in Standardize.main().", error_raw = e)
