import Standardizer
import NoteDetector
import NoteAnalyzer
import os
import sys
import json
import time

root = os.path.normpath(os.path.abspath(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root not in sys.path: sys.path.insert(0, root)
import tools.path_config



def main():

    if len(sys.argv) <= 1:
        print("Error: no JSON file path provided.")
        sys.exit(1)

    json_path = sys.argv[1]
    if not os.path.exists(json_path):
        print(f"Error: JSON file does not exist: {json_path}")
        sys.exit(1)

    # 读取临时 JSON 文件
    print(f"Loading JSON file: {json_path}")
    with open(json_path, 'r', encoding='utf-8') as f:
        params = json.load(f)
    # 删除临时 JSON 文件
    try:
        os.remove(json_path)
    except:
        pass



    try:
        time.sleep(0.5) # 确保能写上日志
        print("\n" + "=" * 40)
        
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
        inference_device = params["inference_device"]
        detect_model = params["detect_model"]
        obb_model = params["obb_model"]
        cls_ex_model = params["cls_ex_model"]
        cls_break_model = params["cls_break_model"]
        skip_detect = params.get("skip_detect", False)
        skip_classify = params.get("skip_classify", False)

        # note_analyzer 参数
        bpm = params["bpm"]
        chart_lv = params["chart_lv"]
        base_denominator = params["base_denominator"]
        # one_beat_Msec = 60 / bpm * 1000 * 4
        # base_resolution = one_beat_Msec / base_denominator

        # 打印所有参数
        print("Standardizer")
        print(f"  video_path: {video_path}")
        print(f"  video_mode: {video_mode}")
        print(f"  start_frame: {start_frame}")
        print(f"  end_frame: {end_frame}")
        print(f"  target_res: {target_res}")
        print(f"  skip_detect_circle: {skip_detect_circle}")
        
        print("\nNoteDetector")
        print(f"  video_name: {video_name}")
        print(f"  batch_detect_obb: {batch_detect}")
        print(f"  batch_classify: {batch_cls}")
        print(f"  inference_device: {inference_device}")
        print(f"  model detect: {detect_model}")
        print(f"  model obb: {obb_model}")
        print(f"  model cls_ex: {cls_ex_model}")
        print(f"  model cls_break: {cls_break_model}")
        print(f"  skip_detect: {skip_detect}")
        print(f"  skip_classify: {skip_classify}")
        
        print("\nNoteAnalyzer")
        print(f"  BPM: {bpm}")
        print(f"  chart_lv: {chart_lv}")
        print(f"  base_denominator: {base_denominator}")
        print("=" * 40 + "\n")



        standardizer = Standardizer.Standardizer()
        note_detector = NoteDetector.NoteDetector()
        note_analyzer = NoteAnalyzer.NoteAnalyzer()

        std_video_path = standardizer.standardize_video(
            video_path,
            start_frame,
            end_frame,
            video_mode,
            target_res,
            skip_detect_circle
        )

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

        note_analyzer.main(
            tracked_output_dir,
            bpm,
            chart_lv,
            base_denominator
        )

    except Exception as e:
        print(f"Error in auto convert: {e}")



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
        # },

        # {
        #     # standardizer 参数
        #     "video_path": r"C:\Users\ck273\Desktop\風又ねリ\[maimai谱面确认] Get U ♭ack EXPERT-p01-120.mp4",
        #     "video_mode": "source",
        #     "start_frame": 670,
        #     "end_frame": 16390,
        #     "target_res": 1080,
        #     "skip_detect_circle": True,
        #     # note-detector 参数
        #     "video_name": "Get U ♭ack EXPERT",
        #     # note_analyzer 参数
        #     "bpm": 205,
        #     "chart_lv": 4,
        #     "base_denominator": 32
        # }


if __name__ == "__main__":
    main()
