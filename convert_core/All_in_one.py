import Standardizer
import NoteDetector
import NoteAnalyzer
import os
import sys
import json

root = os.path.abspath(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if root not in sys.path: sys.path.insert(0, root)
import tools.path_config
import time


def main():

    standardizer = Standardizer.Standardizer()
    note_detector = NoteDetector.NoteDetector()
    note_analyzer = NoteAnalyzer.NoteAnalyzer()
    
    # 检查是否从命令行接收 JSON 参数
    if len(sys.argv) > 1:
        json_path = sys.argv[1]
        if os.path.exists(json_path):
            print(f"从 JSON 文件加载参数: {json_path}")
            with open(json_path, 'r', encoding='utf-8') as f:
                params = json.load(f)
            parameter_sets = [params]
            # 删除临时 JSON 文件
            try:
                os.remove(json_path)
            except:
                pass
        else:
            print(f"错误: JSON 文件不存在: {json_path}")
            return
    else:
        # 硬编码多组参数
        parameter_sets = [
        # {
        #     # standardizer 参数
        #     "video_path": r"C:\Users\ck273\Desktop\風又ねリ\廃墟にいますキャンペーン.mp4",
        #     "video_mode": "source",
        #     "start_frame": 670,
        #     "end_frame": 17000,
        #     "target_res": 1080,
        #     "skip_detect_circle": True,
        #     # note_analyzer 参数
        #     "bpm": 215,
        #     "chart_lv": 4,
        #     "base_denominator": 32
        # },
        # {
        #     # standardizer 参数
        #     "video_path": r"C:\Users\ck273\Desktop\風又ねリ\Hurtling Boys.mp4",
        #     "video_mode": "source",
        #     "start_frame": 670,
        #     "end_frame": 14440,
        #     "target_res": 1080,
        #     "skip_detect_circle": True,
        #     # note_analyzer 参数
        #     "bpm": 195,
        #     "chart_lv": 4,
        #     "base_denominator": 32
        # },
        # {
        #     # standardizer 参数
        #     "video_path": r"C:\Users\ck273\Desktop\風又ねリ\Magical Flavor[DX].mp4",
        #     "video_mode": "source",
        #     "start_frame": 670,
        #     "end_frame": 15810,
        #     "target_res": 1080,
        #     "skip_detect_circle": True,
        #     # note_analyzer 参数
        #     "bpm": 98,
        #     "chart_lv": 4,
        #     "base_denominator": 32
        # },
        # {
        #     # standardizer 参数
        #     "video_path": r"C:\Users\ck273\Desktop\風又ねリ\エンジェル ドリーム.mp4",
        #     "video_mode": "source",
        #     "start_frame": 670,
        #     "end_frame": 17940,
        #     "target_res": 1080,
        #     "skip_detect_circle": True,
        #     # note_analyzer 参数
        #     "bpm": 180,
        #     "chart_lv": 4,
        #     "base_denominator": 32
        # },
        # {
        #     # standardizer 参数
        #     "video_path": r"C:\Users\ck273\Desktop\風又ねリ\おべんきょうたいむ.mp4",
        #     "video_mode": "source",
        #     "start_frame": 670,
        #     "end_frame": 18730,
        #     "target_res": 1080,
        #     "skip_detect_circle": True,
        #     # note_analyzer 参数
        #     "bpm": 165,
        #     "chart_lv": 4,
        #     "base_denominator": 32
        # },
        # {
        #     # standardizer 参数
        #     "video_path": r"C:\Users\ck273\Desktop\風又ねリ\しゅ～しん？変身☆ハカイシンzzZ.mp4",
        #     "video_mode": "source",
        #     "start_frame": 670,
        #     "end_frame": 19030,
        #     "target_res": 1080,
        #     "skip_detect_circle": True,
        #     # note_analyzer 参数
        #     "bpm": 180,
        #     "chart_lv": 4,
        #     "base_denominator": 32
        # },
        # {
        #     # standardizer 参数
        #     "video_path": r"C:\Users\ck273\Desktop\風又ねリ\るろうらんる.mp4",
        #     "video_mode": "source",
        #     "start_frame": 670,
        #     "end_frame": 15510,
        #     "target_res": 1080,
        #     "skip_detect_circle": True,
        #     # note_analyzer 参数
        #     "bpm": 156,
        #     "chart_lv": 4,
        #     "base_denominator": 32
        # },
        # {
        #     # standardizer 参数
        #     "video_path": r"C:\Users\ck273\Desktop\風又ねリ\拝啓、最高の思い出たち.mp4",
        #     "video_mode": "source",
        #     "start_frame": 670,
        #     "end_frame": 17480,
        #     "target_res": 1080,
        #     "skip_detect_circle": True,
        #     # note_analyzer 参数
        #     "bpm": 124,
        #     "chart_lv": 4,
        #     "base_denominator": 32
        # },
        # {
        #     # standardizer 参数
        #     "video_path": r"C:\Users\ck273\Desktop\風又ねリ\怪盗Rのテーマ.mp4",
        #     "video_mode": "source",
        #     "start_frame": 670,
        #     "end_frame": 15610,
        #     "target_res": 1080,
        #     "skip_detect_circle": True,
        #     # note_analyzer 参数
        #     "bpm": 147,
        #     "chart_lv": 4,
        #     "base_denominator": 32
        # },
        # {
        #     # standardizer 参数
        #     "video_path": r"C:\Users\ck273\Desktop\風又ねリ\命テステス.mp4",
        #     "video_mode": "source",
        #     "start_frame": 670,
        #     "end_frame": 13930,
        #     "target_res": 1080,
        #     "skip_detect_circle": True,
        #     # note_analyzer 参数
        #     "bpm": 240,
        #     "chart_lv": 4,
        #     "base_denominator": 32
        # }

        {
            # standardizer 参数
            "video_path": r"C:\Users\ck273\Desktop\風又ねリ\[maimai谱面确认] Get U ♭ack EXPERT-p01-120.mp4",
            "video_mode": "source",
            "start_frame": 670,
            "end_frame": 16390,
            "target_res": 1080,
            "skip_detect_circle": True,
            # note-detector 参数
            "video_name": "Get U ♭ack EXPERT",
            # note_analyzer 参数
            "bpm": 205,
            "chart_lv": 4,
            "base_denominator": 32
        }
        ]

    for i, params in enumerate(parameter_sets):
        try:
            time.sleep(1) # 确保能写上日志
            print(f"\n------------------------------")
            print(f"正在处理第 {i+1} 组参数...\n")
            
            # standardizer 参数
            video_path = params["video_path"]
            video_mode = params["video_mode"]
            start_frame = params["start_frame"]
            end_frame = params["end_frame"]
            target_res = params["target_res"]
            skip_detect_circle = params["skip_detect_circle"]

            # note-detector 参数
            video_name = params["video_name"]
            batch_detect = params.get("batch_detect", 2)
            batch_cls = params.get("batch_cls", 16)
            inference_device = params.get("inference_device", "0")
            detect_model = params.get("detect_model", os.path.join(tools.path_config.models_dir, 'detect.engine'))
            obb_model = params.get("obb_model", os.path.join(tools.path_config.models_dir, 'obb.pt'))
            cls_ex_model = params.get("cls_ex_model", os.path.join(tools.path_config.models_dir, 'cls-ex.pt'))
            cls_break_model = params.get("cls_break_model", os.path.join(tools.path_config.models_dir, 'cls-break.pt'))
            skip_detect = params.get("skip_detect", False)
            skip_classify = params.get("skip_classify", False)

            # note_analyzer 参数
            bpm = params["bpm"]
            chart_lv = params["chart_lv"]
            base_denominator = params["base_denominator"]
            # one_beat_Msec = 60 / bpm * 1000 * 4
            # base_resolution = one_beat_Msec / base_denominator

            # 打印所有参数
            print("=" * 60)
            print("【Standardizer 参数】")
            print(f"  视频路径: {video_path}")
            print(f"  视频模式: {video_mode}")
            print(f"  起始帧: {start_frame}")
            print(f"  结束帧: {end_frame}")
            print(f"  目标分辨率: {target_res}")
            print(f"  跳过圆形检测: {skip_detect_circle}")
            
            print("\n【NoteDetector 参数】")
            print(f"  视频名称: {video_name}")
            print(f"  batch_detect_obb: {batch_detect}")
            print(f"  batch_classify: {batch_cls}")
            print(f"  推理设备: {inference_device}")
            print(f"  detect 模型: {detect_model}")
            print(f"  obb 模型: {obb_model}")
            print(f"  cls_ex 模型: {cls_ex_model}")
            print(f"  cls_break 模型: {cls_break_model}")
            print(f"  跳过检测: {skip_detect}")
            print(f"  跳过分类: {skip_classify}")
            
            print("\n【NoteAnalyzer 参数】")
            print(f"  BPM: {bpm}")
            print(f"  谱面难度: {chart_lv}")
            print(f"  基础分辨率: {base_denominator}")
            print("=" * 60 + "\n")

            std_video_path = standardizer.standardize_video(video_path, start_frame, end_frame, video_mode, target_res, skip_detect_circle)

            tracked_output_dir = note_detector.main(
                std_video_path, 
                os.path.join(tools.path_config.final_data_output_dir, video_name),
                batch_detect,
                batch_cls,
                inference_device,
                detect_model,
                obb_model,
                cls_ex_model,
                cls_break_model,
                skip_detect=skip_detect,
                skip_cls=skip_classify,
                skip_export_tracked_video=False
            )

            note_analyzer.main(tracked_output_dir, bpm, chart_lv, base_denominator)

        except Exception as e:
            print(f"处理第 {i+1} 组参数时出错: {e}")


if __name__ == "__main__":
    main()
