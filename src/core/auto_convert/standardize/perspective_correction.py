import cv2
import numpy as np
from pathlib import Path
from typing import Dict, Optional, Tuple

from ...schemas.op_result import OpResult, ok, err


class PerspectiveCorrection:
    PANEL_SIZE = 800
    WINDOW_WIDTH = PANEL_SIZE * 2
    WINDOW_HEIGHT = PANEL_SIZE

    CONTROL_HEIGHT = 136
    SLIDER_TOP_Y_OFFSET = 34
    SLIDER_MID_Y_OFFSET = 66
    SLIDER_BOTTOM_Y_OFFSET = 98
    SLIDER_TRACK_PADDING = 72
    SLIDER_KNOB_RADIUS = 8

    SCALE_MIN_PERCENT = 10
    SCALE_MAX_PERCENT = 300
    SCALE_DEFAULT_PERCENT = 100

    STRETCH_MIN_PERCENT = 30
    STRETCH_MAX_PERCENT = 300
    STRETCH_DEFAULT_PERCENT = 100

    OFFSET_MIN_PX = -5000
    OFFSET_MAX_PX = 5000
    OFFSET_DEFAULT_PX = 0

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
        self.dragging_slider_name: Optional[str] = None
        self.input_zoom_percent = self.SCALE_DEFAULT_PERCENT
        self.output_zoom_percent = self.SCALE_DEFAULT_PERCENT
        self.output_stretch_x_percent = self.STRETCH_DEFAULT_PERCENT
        self.output_stretch_y_percent = self.STRETCH_DEFAULT_PERCENT
        self.output_offset_x_px = self.OFFSET_DEFAULT_PX
        self.output_offset_y_px = self.OFFSET_DEFAULT_PX

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

                input_zoom = self.input_zoom_percent / 100.0
                output_zoom = self.output_zoom_percent / 100.0

                left_panel, left_meta = self._compose_panel(raw_frame, input_zoom)
                self.left_panel_meta = left_meta
                self._draw_quad_overlay(left_panel, left_meta)

                corrected_frame = self._warp_full_frame(raw_frame)
                corrected_frame = self._apply_output_stretch(corrected_frame)
                right_panel, _ = self._compose_panel(
                    corrected_frame,
                    output_zoom,
                    offset_x=self.output_offset_x_px,
                    offset_y=self.output_offset_y_px,
                )

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

    def _compose_panel(self, frame, zoom: float, offset_x: int = 0, offset_y: int = 0):
        canvas = np.zeros((self.PANEL_SIZE, self.PANEL_SIZE, 3), dtype=np.uint8)

        frame_h, frame_w = frame.shape[:2]
        scaled_w = max(1, int(round(frame_w * zoom)))
        scaled_h = max(1, int(round(frame_h * zoom)))
        scaled = cv2.resize(frame, (scaled_w, scaled_h), interpolation=cv2.INTER_LINEAR)

        top_left_x = int(round((self.PANEL_SIZE - scaled_w) * 0.5 + offset_x))
        top_left_y = int(round((self.PANEL_SIZE - scaled_h) * 0.5 + offset_y))

        dst_x1 = max(0, top_left_x)
        dst_y1 = max(0, top_left_y)
        dst_x2 = min(self.PANEL_SIZE, top_left_x + scaled_w)
        dst_y2 = min(self.PANEL_SIZE, top_left_y + scaled_h)

        src_x1 = max(0, -top_left_x)
        src_y1 = max(0, -top_left_y)
        src_x2 = src_x1 + max(0, dst_x2 - dst_x1)
        src_y2 = src_y1 + max(0, dst_y2 - dst_y1)

        if src_x1 < src_x2 and src_y1 < src_y2 and dst_x1 < dst_x2 and dst_y1 < dst_y2:
            canvas[dst_y1:dst_y2, dst_x1:dst_x2] = scaled[src_y1:src_y2, src_x1:src_x2]

        meta = {
            "zoom": float(zoom),
            "top_left_x": float(top_left_x),
            "top_left_y": float(top_left_y),
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

        self._draw_slider_panel(preview, 0, "Input scale", self.input_zoom_percent, input_zoom, "input")
        self._draw_slider_panel(preview, self.PANEL_SIZE, "Corrected scale", self.output_zoom_percent, output_zoom, "output")
        self._draw_right_stretch_sliders(preview)
        self._draw_right_offset_sliders(preview)

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
            (12, self.PANEL_SIZE - self.CONTROL_HEIGHT - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        cv2.putText(
            preview,
            f"Output zoom: {output_zoom:.2f}x",
            (self.PANEL_SIZE + 12, self.PANEL_SIZE - self.CONTROL_HEIGHT - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

        cv2.putText(
            preview,
            "SPACE: pause/play  ESC: exit",
            (12, self.PANEL_SIZE - self.CONTROL_HEIGHT - 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.58,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

        cv2.putText(
            preview,
            "Reference quad can be inside target; transform applies to whole frame",
            (self.PANEL_SIZE + 12, self.PANEL_SIZE - self.CONTROL_HEIGHT - 30),
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

    def _draw_slider_panel(self,
                             preview: np.ndarray,
                             panel_offset_x: int,
                             label: str,
                             percent_value: int,
                             zoom_value: float,
                             slider_name: str) -> None:
        panel_bottom = self.PANEL_SIZE
        control_top = panel_bottom - self.CONTROL_HEIGHT
        control_bottom = panel_bottom

        cv2.rectangle(
            preview,
            (panel_offset_x, control_top),
            (panel_offset_x + self.PANEL_SIZE, control_bottom),
            (0, 0, 0),
            -1,
        )
        cv2.rectangle(
            preview,
            (panel_offset_x, control_top),
            (panel_offset_x + self.PANEL_SIZE - 1, control_bottom - 1),
            (70, 70, 70),
            1,
        )

        slider_geo = self._get_slider_geometries()[slider_name]
        self._draw_slider(
            preview=preview,
            label=f"{label}: {percent_value}%",
            value_text=f"{zoom_value:.2f}x",
            slider_name=slider_name,
            track_x1=slider_geo["x1"],
            track_x2=slider_geo["x2"],
            track_y=slider_geo["y"],
            percent_value=percent_value,
            min_percent=slider_geo["min"],
            max_percent=slider_geo["max"],
        )

    def _draw_right_stretch_sliders(self, preview: np.ndarray) -> None:
        geo = self._get_slider_geometries()
        x_geo = geo["stretch_x"]
        y_geo = geo["stretch_y"]

        self._draw_slider(
            preview=preview,
            label=f"H stretch: {self.output_stretch_x_percent}%",
            value_text=f"{self.output_stretch_x_percent}%",
            slider_name="stretch_x",
            track_x1=x_geo["x1"],
            track_x2=x_geo["x2"],
            track_y=x_geo["y"],
            percent_value=self.output_stretch_x_percent,
            min_percent=x_geo["min"],
            max_percent=x_geo["max"],
        )
        self._draw_slider(
            preview=preview,
            label=f"V stretch: {self.output_stretch_y_percent}%",
            value_text=f"{self.output_stretch_y_percent}%",
            slider_name="stretch_y",
            track_x1=y_geo["x1"],
            track_x2=y_geo["x2"],
            track_y=y_geo["y"],
            percent_value=self.output_stretch_y_percent,
            min_percent=y_geo["min"],
            max_percent=y_geo["max"],
        )

    def _draw_right_offset_sliders(self, preview: np.ndarray) -> None:
        geo = self._get_slider_geometries()
        x_geo = geo["offset_x"]
        y_geo = geo["offset_y"]

        self._draw_slider(
            preview=preview,
            label=f"H offset: {self.output_offset_x_px}px",
            value_text=f"{self.output_offset_x_px}px",
            slider_name="offset_x",
            track_x1=x_geo["x1"],
            track_x2=x_geo["x2"],
            track_y=x_geo["y"],
            percent_value=self.output_offset_x_px,
            min_percent=x_geo["min"],
            max_percent=x_geo["max"],
        )
        self._draw_slider(
            preview=preview,
            label=f"V offset: {self.output_offset_y_px}px",
            value_text=f"{self.output_offset_y_px}px",
            slider_name="offset_y",
            track_x1=y_geo["x1"],
            track_x2=y_geo["x2"],
            track_y=y_geo["y"],
            percent_value=self.output_offset_y_px,
            min_percent=y_geo["min"],
            max_percent=y_geo["max"],
        )

    def _draw_slider(self,
                     preview: np.ndarray,
                     label: str,
                     value_text: str,
                     slider_name: str,
                     track_x1: int,
                     track_x2: int,
                     track_y: int,
                     percent_value: int,
                     min_percent: int,
                     max_percent: int) -> None:
        label_y = track_y - 14
        cv2.putText(
            preview,
            label,
            (track_x1, label_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

        cv2.line(preview, (track_x1, track_y), (track_x2, track_y), (170, 170, 170), 2)

        knob_x = int(round(self._slider_percent_to_x(percent_value, track_x1, track_x2, min_percent, max_percent)))
        knob_color = (0, 200, 255) if self.dragging_slider_name == slider_name else (0, 140, 255)
        cv2.circle(preview, (knob_x, track_y), self.SLIDER_KNOB_RADIUS + 2, (255, 255, 255), 1)
        cv2.circle(preview, (knob_x, track_y), self.SLIDER_KNOB_RADIUS, knob_color, -1)

        cv2.putText(
            preview,
            value_text,
            (track_x2 - 94, label_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.46,
            (200, 200, 200),
            1,
            cv2.LINE_AA,
        )

    def _slider_percent_to_x(self,
                             percent_value: int,
                             track_x1: int,
                             track_x2: int,
                             min_percent: int,
                             max_percent: int) -> float:
        clamped = self._clamp_value(percent_value, min_percent, max_percent)
        ratio = (clamped - min_percent) / float(max(1, max_percent - min_percent))
        return track_x1 + ratio * (track_x2 - track_x1)

    def _slider_x_to_percent(self,
                             x: float,
                             track_x1: int,
                             track_x2: int,
                             min_percent: int,
                             max_percent: int) -> int:
        ratio = (x - track_x1) / float(max(1, track_x2 - track_x1))
        percent = min_percent + ratio * (max_percent - min_percent)
        return self._clamp_value(int(round(percent)), min_percent, max_percent)

    def _clamp_value(self, value: int, min_value: int, max_value: int) -> int:
        return max(min_value, min(max_value, int(value)))

    def _get_slider_geometries(self) -> Dict[str, Dict[str, int]]:
        control_top = self.PANEL_SIZE - self.CONTROL_HEIGHT

        left_panel_offset = 0
        right_panel_offset = self.PANEL_SIZE

        left_full_x1 = left_panel_offset + self.SLIDER_TRACK_PADDING
        left_full_x2 = left_panel_offset + self.PANEL_SIZE - self.SLIDER_TRACK_PADDING
        right_full_x1 = right_panel_offset + self.SLIDER_TRACK_PADDING
        right_full_x2 = right_panel_offset + self.PANEL_SIZE - self.SLIDER_TRACK_PADDING

        half_len = (right_full_x2 - right_full_x1) // 2
        right_half_left_x1 = right_full_x1
        right_half_left_x2 = right_half_left_x1 + half_len
        right_half_right_x2 = right_full_x2
        right_half_right_x1 = right_half_right_x2 - half_len

        return {
            "input": {
                "x1": left_full_x1,
                "x2": left_full_x2,
                "y": control_top + self.SLIDER_TOP_Y_OFFSET,
                "min": self.SCALE_MIN_PERCENT,
                "max": self.SCALE_MAX_PERCENT,
            },
            "output": {
                "x1": right_full_x1,
                "x2": right_full_x2,
                "y": control_top + self.SLIDER_TOP_Y_OFFSET,
                "min": self.SCALE_MIN_PERCENT,
                "max": self.SCALE_MAX_PERCENT,
            },
            "stretch_x": {
                "x1": right_half_left_x1,
                "x2": right_half_left_x2,
                "y": control_top + self.SLIDER_MID_Y_OFFSET,
                "min": self.STRETCH_MIN_PERCENT,
                "max": self.STRETCH_MAX_PERCENT,
            },
            "stretch_y": {
                "x1": right_half_right_x1,
                "x2": right_half_right_x2,
                "y": control_top + self.SLIDER_MID_Y_OFFSET,
                "min": self.STRETCH_MIN_PERCENT,
                "max": self.STRETCH_MAX_PERCENT,
            },
            "offset_x": {
                "x1": right_half_left_x1,
                "x2": right_half_left_x2,
                "y": control_top + self.SLIDER_BOTTOM_Y_OFFSET,
                "min": self.OFFSET_MIN_PX,
                "max": self.OFFSET_MAX_PX,
            },
            "offset_y": {
                "x1": right_half_right_x1,
                "x2": right_half_right_x2,
                "y": control_top + self.SLIDER_BOTTOM_Y_OFFSET,
                "min": self.OFFSET_MIN_PX,
                "max": self.OFFSET_MAX_PX,
            },
        }

    def _frame_to_panel(self, frame_point: np.ndarray, meta: Dict[str, float]) -> np.ndarray:
        zoom = meta["zoom"]
        panel_x = frame_point[0] * zoom + meta["top_left_x"]
        panel_y = frame_point[1] * zoom + meta["top_left_y"]
        return np.array([panel_x, panel_y], dtype=np.float32)

    def _panel_to_frame(self, panel_x: float, panel_y: float, meta: Dict[str, float]) -> np.ndarray:
        zoom = max(1e-6, meta["zoom"])
        frame_x = (panel_x - meta["top_left_x"]) / zoom
        frame_y = (panel_y - meta["top_left_y"]) / zoom

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

    def _apply_output_stretch(self, frame: np.ndarray) -> np.ndarray:
        stretch_x = self.output_stretch_x_percent / 100.0
        stretch_y = self.output_stretch_y_percent / 100.0

        if abs(stretch_x - 1.0) < 1e-6 and abs(stretch_y - 1.0) < 1e-6:
            return frame

        frame_h, frame_w = frame.shape[:2]
        stretched_w = max(1, int(round(frame_w * stretch_x)))
        stretched_h = max(1, int(round(frame_h * stretch_y)))
        return cv2.resize(frame, (stretched_w, stretched_h), interpolation=cv2.INTER_LINEAR)

    def _on_mouse_event(self, event, x, y, flags, param) -> None:
        _ = flags
        _ = param
        if self.quad_points is None or self.left_panel_meta is None:
            return

        if self._handle_slider_event(event, x, y):
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

    def _handle_slider_event(self, event: int, x: int, y: int) -> bool:
        control_top = self.PANEL_SIZE - self.CONTROL_HEIGHT
        slider_geo = self._get_slider_geometries()

        if self.dragging_slider_name is not None:
            slider_name = self.dragging_slider_name
            geo = slider_geo.get(slider_name)
            if geo is None:
                self.dragging_slider_name = None
                return False

            if event == cv2.EVENT_MOUSEMOVE:
                self._update_slider_from_mouse(slider_name, x, geo)
                return True

            if event == cv2.EVENT_LBUTTONUP:
                self._update_slider_from_mouse(slider_name, x, geo)
                self.dragging_slider_name = None
                return True

            return True

        if y < control_top:
            if event == cv2.EVENT_LBUTTONUP:
                self.dragging_slider_name = None
            return False

        if x < 0 or x >= self.WINDOW_WIDTH:
            return False

        if event == cv2.EVENT_LBUTTONDOWN:
            for slider_name, geo in slider_geo.items():
                hit_x_min = geo["x1"] - 14
                hit_x_max = geo["x2"] + 14
                hit_y_min = geo["y"] - 18
                hit_y_max = geo["y"] + 18
                if hit_x_min <= x <= hit_x_max and hit_y_min <= y <= hit_y_max:
                    self.dragging_slider_name = slider_name
                    self._update_slider_from_mouse(slider_name, x, geo)
                    return True

        return True

    def _update_slider_from_mouse(self, slider_name: str, x: int, geo: Dict[str, int]) -> None:
        percent = self._slider_x_to_percent(
            float(x),
            geo["x1"],
            geo["x2"],
            geo["min"],
            geo["max"],
        )
        if slider_name == "input":
            self.input_zoom_percent = percent
        elif slider_name == "output":
            self.output_zoom_percent = percent
        elif slider_name == "stretch_x":
            self.output_stretch_x_percent = percent
        elif slider_name == "stretch_y":
            self.output_stretch_y_percent = percent
        elif slider_name == "offset_x":
            self.output_offset_x_px = percent
        elif slider_name == "offset_y":
            self.output_offset_y_px = percent
