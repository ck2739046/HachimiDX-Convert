import sys
from pathlib import Path

if len(sys.argv) <= 1:
    print("No root args provided. Exiting.")
    sys.exit(1)

# 第一个参数是项目根目录
# 确保能正确使用间接导入
root = str(Path(sys.argv[1]).resolve())
if root not in sys.path:
    sys.path.insert(0, root)

# 2026.03.20

# see https://github.com/pytorch/pytorch/issues/166628
# 当前最新版 pytorch + pyqt6 在一起使用时有问题
# 如果 pyqt6 比 torch 先导入，会产生 winerror1114 (dll加载失败)
# 解决方法是先导入 torch 再导入 pyqt6
import torch

# 不能使用 python -m 启动此 worker
# 因为 python -m 启动后，import torch 无法解决上述问题
# 原因不清楚，可能和 python -m 的模块导入机制有关？
# 只能通过传统 python xxx.py 启动
# 不管了，反正现在这样能正常工作了
# 以后哪天此问题修复了再改回 python -m 启动吧


from src.core.auto_convert.standardize.main import main as standardize_main
from src.core.auto_convert.detect.main import main as detect_main
from src.core.auto_convert.analyze.main import main as analyze_main
from src.core.schemas.media_config import MediaType
from src.core.schemas.op_result import print_op_result



def _as_bool(raw: str) -> bool:
    text = str(raw).strip().lower()
    if text == "true":
        return True
    elif text == "false":
        return False
    else:
        raise ValueError(f"Invalid bool value: {raw}")



def _fail(message: str) -> bool:
    print(f"[AUTO_CONVERT_WORKER][ERROR] {message}")
    return False



def main(args: list[str]) -> bool:
    try:
        # --key value 成对输入
        cfg = {args[i][2:]: args[i + 1] for i in range(0, len(args), 2)}

        is_standardize_enabled = _as_bool(cfg["is_standardize_enabled"])
        is_detect_enabled = _as_bool(cfg["is_detect_enabled"])
        is_analyze_enabled = _as_bool(cfg["is_analyze_enabled"])

        std_video_path: Path | None = None

        if is_standardize_enabled:
            result = standardize_main(
                input_video=Path(cfg["standardize_input_video_path"]),
                song_name=cfg["song_name"],
                video_mode=cfg["video_mode"],
                media_type=MediaType(cfg["media_type"]),
                duration=float(cfg["duration"]),
                start_sec=float(cfg["start_sec"]),
                end_sec=float(cfg["end_sec"]),
                skip_detect_circle=_as_bool(cfg["skip_detect_circle"]),
                target_res=int(cfg["target_res"]),
            )
            if not result.is_ok:
                return _fail(print_op_result(result))
            std_video_path = result.value



        if is_detect_enabled:
            std_video_for_detect = std_video_path or Path(cfg["std_video_path_detect"])

            result = detect_main(
                std_video_path=std_video_for_detect,
                batch_detect=int(cfg["predict_batch_size_detect_obb"]),
                batch_cls=int(cfg["predict_batch_size_classify"]),
                inference_device=cfg["inference_device"],
                detect_model_path=Path(cfg["detect_model_path"]),
                obb_model_path=Path(cfg["obb_model_path"]),
                cls_ex_model_path=Path(cfg["cls_ex_model_path"]),
                cls_break_model_path=Path(cfg["cls_break_model_path"]),
                skip_detect=_as_bool(cfg["skip_detect"]),
                skip_cls=_as_bool(cfg["skip_cls"]),
                skip_export_tracked_video=_as_bool(cfg["skip_export_tracked_video"]),
            )
            if not result.is_ok:
                return _fail(print_op_result(result))
            std_video_path = std_video_for_detect



        if is_analyze_enabled:
            std_video_for_analyze = std_video_path or Path(cfg["std_video_path_analyze"])

            result = analyze_main(
                std_video_path=std_video_for_analyze,
                bpm=float(cfg["bpm"]),
                chart_lv=int(cfg["chart_lv"]),
                base_denominator=int(cfg["base_denominator"]),
                duration_denominator=int(cfg["duration_denominator"]),
            )
            if not result.is_ok:
                return _fail(print_op_result(result))

        return True
    
    except Exception as e:
        return _fail(str(e))


if __name__ == "__main__":
    # 跳过第一个参数（脚本路径）和第二个参数（root路径）
    result = main(sys.argv[2:])
    sys.exit(0 if result else 1)
