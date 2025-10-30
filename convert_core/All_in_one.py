import Standardizer
import NoteDetector
import NoteAnalyzer
import os


def main():

    standardizer = Standardizer.Standardizer()
    note_detector = NoteDetector.NoteDetector()
    note_analyzer = NoteAnalyzer.NoteAnalyzer()

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
            "video_path": r"C:\Users\ck273\Desktop\風又ねリ\ニルヴの心臓 MASTER 14.3.mp4",
            "video_mode": "source",
            "start_frame": 670,
            "end_frame": 18500,
            "target_res": 1080,
            "skip_detect_circle": True,
            # note_analyzer 参数
            "bpm": 256,
            "chart_lv": 4,
            "base_denominator": 32
        }
    ]

    for i, params in enumerate(parameter_sets):
        try:
            print(f"\n------------------------------")
            print(f"正在处理第 {i+1} 组参数...\n")
            
            # standardizer 参数
            video_path = params["video_path"]
            video_mode = params["video_mode"]
            start_frame = params["start_frame"]
            end_frame = params["end_frame"]
            target_res = params["target_res"]
            skip_detect_circle = params["skip_detect_circle"]

            # note_analyzer 参数
            bpm = params["bpm"]
            chart_lv = params["chart_lv"]
            base_denominator = params["base_denominator"]
            # one_beat_Msec = 60 / bpm * 1000 * 4
            # base_resolution = one_beat_Msec / base_denominator

            std_video_path = standardizer.standardize_video(video_path, start_frame, end_frame, video_mode, target_res, skip_detect_circle)

            tracked_dir_path = note_detector.main(
                std_video_path, 
                os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'aaa-result'),
                os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'yolo-train/pt/detect.pt'),
                os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'yolo-train/pt/obb.pt'),
                os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'yolo-train/pt/cls-ex.pt'),
                os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'yolo-train/pt/cls-break.pt'),
                detect=True
            )

            note_analyzer.main(tracked_dir_path, bpm, chart_lv, base_denominator)

        except Exception as e:
            print(f"处理第 {i+1} 组参数时出错: {e}")


if __name__ == "__main__":
    main()
