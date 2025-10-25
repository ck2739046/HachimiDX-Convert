import Standardizer
import NoteDetector
import NoteAnalyzer
import os


def main():

    standardizer = Standardizer.Standardizer()
    note_detector = NoteDetector.NoteDetector()
    note_analyzer = NoteAnalyzer.NoteAnalyzer()

    try:

        # standardizer 参数
        video_path = r"C:\Users\ck273\Desktop\風又ねリ\廃墟にいますキャンペーン.mp4"
        video_mode = "source"
        start_frame = 670
        end_frame = 17000
        target_res = 2160

        # note_analyzer 参数
        bpm = 215
        chart_lv = 4
        base_denominator = 32
        # one_beat_Msec = 60 / bpm * 1000 * 4
        # base_resolution = one_beat_Msec / base_denominator

        std_video_path = standardizer.standardize_video(video_path, start_frame, end_frame, video_mode, target_res)

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
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
