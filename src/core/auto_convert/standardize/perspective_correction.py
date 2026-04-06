import cv2
import numpy as np
from pathlib import Path
from typing import Dict, Optional, Tuple

from ...schemas.op_result import OpResult, ok, err


class PerspectiveCorrection:
    PANEL_SIZE = 800
    WINDOW_WIDTH = PANEL_SIZE * 2
    WINDOW_HEIGHT = PANEL_SIZE

    TRACKBAR_INPUT_NAME = "Input Scale %"
    TRACKBAR_OUTPUT_NAME = "Corrected Scale %"
    TRACKBAR_MIN = 10
    TRACKBAR_MAX = 300
    TRACKBAR_DEFAULT = 100

    DRAG_RADIUS_PX = 18

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

        self.frame_width = 0
        self.frame_height = 0
        self.quad_points: Optional[np.ndarray] = None
        self.left_panel_meta: Optional[Dict[str, float]] = None
        self.dragging_point_index = -1

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

            self.frame_width = max(1, round(cap.get(cv2.CAP_PROP_FRAME_WIDTH)))
            self.frame_height = max(1, round(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
            if self.quad_points is None:
                self.quad_points = self._build_default_quad(self.frame_width, self.frame_height)

            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(window_name, self.WINDOW_WIDTH, self.WINDOW_HEIGHT)
            cv2.createTrackbar(
                self.TRACKBAR_INPUT_NAME,
                window_name,
                self.TRACKBAR_DEFAULT - self.TRACKBAR_MIN,
                self.TRACKBAR_MAX - self.TRACKBAR_MIN,
                lambda _v: None,
            )
            cv2.createTrackbar(
                self.TRACKBAR_OUTPUT_NAME,
                window_name,
                self.TRACKBAR_DEFAULT - self.TRACKBAR_MIN,
                self.TRACKBAR_MAX - self.TRACKBAR_MIN,
                lambda _v: None,
            )
            cv2.setMouseCallback(window_name, self._on_mouse_event)

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

                    self.frame_height, self.frame_width = raw_frame.shape[:2]
                    if self.quad_points is None:
                        self.quad_points = self._build_default_quad(self.frame_width, self.frame_height)

                input_zoom_percent = cv2.getTrackbarPos(self.TRACKBAR_INPUT_NAME, window_name)
                output_zoom_percent = cv2.getTrackbarPos(self.TRACKBAR_OUTPUT_NAME, window_name)
                input_zoom = (input_zoom_percent + self.TRACKBAR_MIN) / 100.0
                output_zoom = (output_zoom_percent + self.TRACKBAR_MIN) / 100.0

                left_panel, left_meta = self._compose_panel(raw_frame, input_zoom)
                self.left_panel_meta = left_meta
                self._draw_quad_overlay(left_panel, left_meta)

                corrected_frame = self._warp_full_frame(raw_frame)
                right_panel, _ = self._compose_panel(corrected_frame, output_zoom)

                preview = np.zeros((self.WINDOW_HEIGHT, self.WINDOW_WIDTH, 3), dtype=np.uint8)
                preview[:, :self.PANEL_SIZE] = left_panel
                preview[:, self.PANEL_SIZE:] = right_panel
                self._draw_combined_overlay(preview, is_playing, input_zoom, output_zoom)

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

    def _compose_panel(self, frame, zoom: float):
        canvas = np.zeros((self.PANEL_SIZE, self.PANEL_SIZE, 3), dtype=np.uint8)

        frame_h, frame_w = frame.shape[:2]
        scaled_w = max(1, int(round(frame_w * zoom)))
        scaled_h = max(1, int(round(frame_h * zoom)))
        scaled = cv2.resize(frame, (scaled_w, scaled_h), interpolation=cv2.INTER_LINEAR)

        src_x1 = max(0, (scaled_w - self.PANEL_SIZE) // 2)
        src_y1 = max(0, (scaled_h - self.PANEL_SIZE) // 2)
        src_x2 = min(scaled_w, src_x1 + self.PANEL_SIZE)
        src_y2 = min(scaled_h, src_y1 + self.PANEL_SIZE)

        crop = scaled[src_y1:src_y2, src_x1:src_x2]
        crop_h, crop_w = crop.shape[:2]

        dst_x1 = (self.PANEL_SIZE - crop_w) // 2
        dst_y1 = (self.PANEL_SIZE - crop_h) // 2
        dst_x2 = dst_x1 + crop_w
        dst_y2 = dst_y1 + crop_h
        canvas[dst_y1:dst_y2, dst_x1:dst_x2] = crop

        meta = {
            "zoom": float(zoom),
            "src_x": float(src_x1),
            "src_y": float(src_y1),
            "dst_x": float(dst_x1),
            "dst_y": float(dst_y1),
            "crop_w": float(crop_w),
            "crop_h": float(crop_h),
        }
        return canvas, meta

    def _build_default_quad(self, frame_w: int, frame_h: int) -> np.ndarray:
        cx = frame_w / 2.0
        cy = frame_h / 2.0
        half_w = frame_w * 0.18
        half_h = frame_h * 0.18
        return np.array(
            [
                [cx - half_w, cy - half_h],
                [cx + half_w, cy - half_h],
                [cx + half_w, cy + half_h],
                [cx - half_w, cy + half_h],
            ],
            dtype=np.float32,
        )

    def _draw_quad_overlay(self, panel: np.ndarray, meta: Dict[str, float]) -> None:
        if self.quad_points is None:
            return

        canvas_points = []
        for pt in self.quad_points:
            canvas_points.append(self._frame_to_panel(pt, meta))
        canvas_points = np.array(canvas_points, dtype=np.int32)

        cv2.polylines(panel, [canvas_points], isClosed=True, color=(0, 255, 0), thickness=2)

        for i, pt in enumerate(canvas_points):
            cv2.circle(panel, (int(pt[0]), int(pt[1])), 8, (0, 128, 255), -1)
            cv2.circle(panel, (int(pt[0]), int(pt[1])), 12, (255, 255, 255), 1)
            cv2.putText(
                panel,
                str(i + 1),
                (int(pt[0]) + 10, int(pt[1]) - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )

    def _draw_combined_overlay(self,
                               preview: np.ndarray,
                               is_playing: bool,
                               input_zoom: float,
                               output_zoom: float) -> None:
        cv2.line(preview, (self.PANEL_SIZE, 0), (self.PANEL_SIZE, self.PANEL_SIZE), (255, 255, 255), 1)

        cv2.putText(
            preview,
            "Input (drag 4 points)",
            (12, 26),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        cv2.putText(
            preview,
            "Perspective corrected (full frame)",
            (self.PANEL_SIZE + 12, 26),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

        cv2.putText(
            preview,
            f"Input zoom: {input_zoom:.2f}x",
            (12, self.PANEL_SIZE - 44),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        cv2.putText(
            preview,
            f"Output zoom: {output_zoom:.2f}x",
            (self.PANEL_SIZE + 12, self.PANEL_SIZE - 44),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

        cv2.putText(
            preview,
            "SPACE: pause/play  ESC: exit",
            (12, self.PANEL_SIZE - 16),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.58,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

        cv2.putText(
            preview,
            "Reference quad can be inside target; transform applies to whole frame",
            (self.PANEL_SIZE + 12, self.PANEL_SIZE - 16),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.50,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

        if not is_playing:
            cv2.putText(
                preview,
                "PAUSED",
                (12, 56),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (0, 255, 255),
                2,
                cv2.LINE_AA,
            )

    def _frame_to_panel(self, frame_point: np.ndarray, meta: Dict[str, float]) -> np.ndarray:
        zoom = meta["zoom"]
        panel_x = frame_point[0] * zoom - meta["src_x"] + meta["dst_x"]
        panel_y = frame_point[1] * zoom - meta["src_y"] + meta["dst_y"]
        return np.array([panel_x, panel_y], dtype=np.float32)

    def _panel_to_frame(self, panel_x: float, panel_y: float, meta: Dict[str, float]) -> np.ndarray:
        zoom = max(1e-6, meta["zoom"])
        frame_x = (panel_x - meta["dst_x"] + meta["src_x"]) / zoom
        frame_y = (panel_y - meta["dst_y"] + meta["src_y"]) / zoom

        frame_x = float(np.clip(frame_x, 0.0, max(0.0, self.frame_width - 1.0)))
        frame_y = float(np.clip(frame_y, 0.0, max(0.0, self.frame_height - 1.0)))
        return np.array([frame_x, frame_y], dtype=np.float32)

    def _build_target_quad(self, src_quad: np.ndarray) -> np.ndarray:
        top = np.linalg.norm(src_quad[1] - src_quad[0])
        bottom = np.linalg.norm(src_quad[2] - src_quad[3])
        left = np.linalg.norm(src_quad[3] - src_quad[0])
        right = np.linalg.norm(src_quad[2] - src_quad[1])

        rect_w = max(40.0, (top + bottom) * 0.5)
        rect_h = max(40.0, (left + right) * 0.5)

        center = src_quad.mean(axis=0)
        half_w = rect_w * 0.5
        half_h = rect_h * 0.5

        return np.array(
            [
                [center[0] - half_w, center[1] - half_h],
                [center[0] + half_w, center[1] - half_h],
                [center[0] + half_w, center[1] + half_h],
                [center[0] - half_w, center[1] + half_h],
            ],
            dtype=np.float32,
        )

    def _warp_full_frame(self, frame: np.ndarray) -> np.ndarray:
        if self.quad_points is None:
            return frame

        src_quad = self.quad_points.astype(np.float32)
        dst_quad = self._build_target_quad(src_quad)
        matrix = cv2.getPerspectiveTransform(src_quad, dst_quad)
        return cv2.warpPerspective(
            frame,
            matrix,
            (self.frame_width, self.frame_height),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0),
        )

    def _on_mouse_event(self, event, x, y, flags, param) -> None:
        _ = flags
        _ = param
        if self.quad_points is None or self.left_panel_meta is None:
            return

        if x >= self.PANEL_SIZE:
            if event == cv2.EVENT_LBUTTONUP:
                self.dragging_point_index = -1
            return

        if event == cv2.EVENT_LBUTTONDOWN:
            min_dist = float("inf")
            min_idx = -1
            for idx, frame_pt in enumerate(self.quad_points):
                panel_pt = self._frame_to_panel(frame_pt, self.left_panel_meta)
                dist = float(np.hypot(panel_pt[0] - x, panel_pt[1] - y))
                if dist < min_dist:
                    min_dist = dist
                    min_idx = idx

            if min_dist <= self.DRAG_RADIUS_PX:
                self.dragging_point_index = min_idx

        elif event == cv2.EVENT_MOUSEMOVE:
            if self.dragging_point_index >= 0:
                new_point = self._panel_to_frame(float(x), float(y), self.left_panel_meta)
                self.quad_points[self.dragging_point_index] = new_point

        elif event == cv2.EVENT_LBUTTONUP:
            self.dragging_point_index = -1
