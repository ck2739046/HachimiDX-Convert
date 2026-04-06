import cv2
import numpy as np
from pathlib import Path
from typing import Tuple

from ...schemas.op_result import OpResult, ok, err


class PerspectiveCorrection:
    PREVIEW_SIZE = 800
    TRACKBAR_NAME = "Scale %"
    TRACKBAR_MIN = 10
    TRACKBAR_MAX = 300
    TRACKBAR_DEFAULT = 100

    def __init__(self,
                 input_video: Path,
                 circle_center: Tuple[int, int],
                 circle_radius: int,
                 start_sec: float,
                 end_sec: float):
        self.input_video = input_video
        self.circle_cx = int(circle_center[0])
        self.circle_cy = int(circle_center[1])
        self.circle_r = int(circle_radius)
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.x_rot_deg = 0.0
        self.y_rot_deg = 0.0
        self.z_rot_deg = 0.0
        self.start_sec = 0.0 if start_sec is None else float(start_sec)
        self.end_sec = 0.0 if end_sec is None else float(end_sec)

    def main(self) -> OpResult[Tuple[Tuple[int, int], int, float, float, float, float, float]]:
        cap = None
        window_name = "Perspective Correction"

        try:
            cap = cv2.VideoCapture(str(self.input_video))
            if not cap.isOpened():
                return err(f"Cannot open video file: {self.input_video}")

            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0:
                fps = 30.0
            total_frames = max(1, round(cap.get(cv2.CAP_PROP_FRAME_COUNT)))

            start_frame = max(0, round(self.start_sec * fps))
            end_frame = round(self.end_sec * fps) if self.end_sec > 0 else total_frames - 1
            end_frame = min(max(start_frame, end_frame), total_frames - 1)

            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(window_name, self.PREVIEW_SIZE, self.PREVIEW_SIZE)
            cv2.createTrackbar(
                self.TRACKBAR_NAME,
                window_name,
                self.TRACKBAR_DEFAULT - self.TRACKBAR_MIN,
                self.TRACKBAR_MAX - self.TRACKBAR_MIN,
                lambda _v: None,
            )

            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
            current_frame_idx = start_frame

            is_playing = True
            raw_frame = None
            target_delay_ms = max(1, int(1000 / fps))

            while True:
                if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                    break

                if is_playing or raw_frame is None:
                    ret, raw_frame = cap.read()
                    if not ret or current_frame_idx > end_frame:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
                        current_frame_idx = start_frame
                        continue
                    current_frame_idx += 1

                zoom_percent = cv2.getTrackbarPos(self.TRACKBAR_NAME, window_name)
                zoom = (zoom_percent + self.TRACKBAR_MIN) / 100.0

                preview = self._compose_preview(raw_frame, zoom, is_playing)
                cv2.imshow(window_name, preview)

                delay = target_delay_ms if is_playing else 30
                key = cv2.waitKey(delay) & 0xFF
                if key == ord(" "):
                    is_playing = not is_playing
                elif key == 27:  # ESC
                    break

            last_op = (
                (self.circle_cx, self.circle_cy),
                self.circle_r,
                self.scale_x,
                self.scale_y,
                self.x_rot_deg,
                self.y_rot_deg,
                self.z_rot_deg,
            )
            return ok(last_op)

        except Exception as e:
            return err("Error in perspective correction preview", error_raw=e)

        finally:
            try:
                cv2.destroyWindow(window_name)
            except Exception:
                pass
            try:
                cv2.destroyAllWindows()
            except Exception:
                pass
            if cap is not None:
                cap.release()

    def _compose_preview(self, frame, zoom: float, is_playing: bool):
        canvas = np.zeros((self.PREVIEW_SIZE, self.PREVIEW_SIZE, 3), dtype=np.uint8)

        frame_h, frame_w = frame.shape[:2]
        scaled_w = max(1, int(round(frame_w * zoom)))
        scaled_h = max(1, int(round(frame_h * zoom)))
        scaled = cv2.resize(frame, (scaled_w, scaled_h), interpolation=cv2.INTER_LINEAR)

        src_x1 = max(0, (scaled_w - self.PREVIEW_SIZE) // 2)
        src_y1 = max(0, (scaled_h - self.PREVIEW_SIZE) // 2)
        src_x2 = min(scaled_w, src_x1 + self.PREVIEW_SIZE)
        src_y2 = min(scaled_h, src_y1 + self.PREVIEW_SIZE)

        crop = scaled[src_y1:src_y2, src_x1:src_x2]
        crop_h, crop_w = crop.shape[:2]

        dst_x1 = (self.PREVIEW_SIZE - crop_w) // 2
        dst_y1 = (self.PREVIEW_SIZE - crop_h) // 2
        dst_x2 = dst_x1 + crop_w
        dst_y2 = dst_y1 + crop_h
        canvas[dst_y1:dst_y2, dst_x1:dst_x2] = crop

        cv2.putText(
            canvas,
            "SPACE: pause/play  ESC: exit",
            (10, self.PREVIEW_SIZE - 14),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        if not is_playing:
            cv2.putText(
                canvas,
                "PAUSED",
                (10, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 255),
                2,
                cv2.LINE_AA,
            )

        return canvas
