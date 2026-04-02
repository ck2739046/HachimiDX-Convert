import cv2
from typing import Tuple, Optional
import os
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
import time
import re
import numpy as np

from src.services.path_manage import PathManage
from ...schemas.op_result import OpResult, ok, err

# 设置 Tcl 库路径（便携版 Python 需要）
_tcl_path = PathManage.ROOT_DIR / "python" / "Lib" / "site-packages" / "tcl" / "tcl8.6"
if _tcl_path.exists():
    os.environ["TCL_LIBRARY"] = str(_tcl_path)




class ManualAdjust:

    RADIUS_MIN = 20
    RADIUS_MAX = 9999
    CENTER_MIN = -9999
    CENTER_MAX = 9999

    SCALE_MIN = 0.25
    SCALE_MAX = 4.0
    SCALE_STEP = 0.05

    ROT_MIN = -85.0
    ROT_MAX = 85.0
    ROT_STEP = 0.5

    PREVIEW_SIZE = 800

    def __init__(self,
                 input_video: Path,
                 circle_center: Tuple[int, int],
                 circle_radius: int,
                 start_sec: float,
                 end_sec: float):
        """
        Args:
            input_video(Path): 输入视频路径
            circle_center(Tuple[int, int]): 圆心坐标 (x, y)
            circle_radius(int): 圆半径
            start_sec(float): 开始时间(秒)
            end_sec(float): 结束时间(秒)
        """

        self.input_video = input_video
        self.circle_center_init = circle_center  # 初始传入值的备份，不应该被修改
        self.circle_radius_init = circle_radius  # 初始传入值的备份，不应该被修改
        self.start_sec = start_sec
        self.end_sec = end_sec

        self.circle_cx = int(circle_center[0])
        self.circle_cy = int(circle_center[1])
        self.circle_r = int(circle_radius)
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.x_rot_deg = 0.0
        self.y_rot_deg = 0.0

        self.video_width = 0
        self.video_height = 0

        self.dialog: Optional[tk.Tk] = None
        self.is_confirmed = False

        self.var_radius: Optional[tk.StringVar] = None
        self.var_center_x: Optional[tk.StringVar] = None
        self.var_center_y: Optional[tk.StringVar] = None
        self.var_scale_x: Optional[tk.StringVar] = None
        self.var_scale_y: Optional[tk.StringVar] = None
        self.var_x_rot: Optional[tk.StringVar] = None
        self.var_y_rot: Optional[tk.StringVar] = None



    def main(self) -> OpResult[Tuple[Tuple[int, int], int, float, float, float, float]]:
        """
        如果没有跳过 initial detection
        那么需要人工确认是否识别正确
        显示预览窗口，绘制原始图像帧和圆形

        Returns:
            OpResult -> (circle_center, circle_radius, scale_x, scale_y, x_rot_deg, y_rot_deg)
        """

        cap = None
        try:
            print("Manual check circle...", end="\r")

            # 获取视频基本信息
            cap = cv2.VideoCapture(self.input_video)
            if not cap.isOpened():
                return err(f"Cannot open video file: {self.input_video}")
            self.video_width = round(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.video_height = round(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            total_frames = round(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)

            start_sec = self.start_sec if self.start_sec is not None else 0.0
            end_sec = self.end_sec if self.end_sec is not None else 0.0

            start_frame = round(start_sec * fps)
            end_frame = round(end_sec * fps) if end_sec > 0 else total_frames

            self.create_dialog()
            self.display_preview(cap, start_frame, end_frame, fps)

            print("Manual check circle...ok")
            last_op = (
                (self.circle_cx, self.circle_cy),
                self.circle_r,
                self.scale_x,
                self.scale_y,
                self.x_rot_deg,
                self.y_rot_deg,
            )
            circle_center, circle_radius, scale_x, scale_y, x_rot_deg, y_rot_deg = last_op
            print(
                f"  Circle center: {circle_center}, radius: {circle_radius}, "
                f"scale: ({scale_x}, {scale_y}), rot: ({x_rot_deg}, {y_rot_deg})"
            )

            return ok(last_op)

        except Exception as e:
            return err("Error in display_preview", error_raw=e)

        finally:
            try:
                if self.dialog is not None:
                    self.dialog.destroy()
                cv2.destroyAllWindows()
                if cap is not None:
                    cap.release()
            except Exception:
                pass




    def display_preview(self, cap: cv2.VideoCapture, start_frame: int, end_frame: int, fps: float) -> None:

        # 设置窗口
        window_name = "Detected Circle Preview"
        cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)
        
        # 使用 Tkinter 获取屏幕尺寸
        temp_root = tk.Tk()
        screen_width = temp_root.winfo_screenwidth()
        screen_height = temp_root.winfo_screenheight()
        temp_root.destroy()
        
        # 窗口尺寸（预览画面大小）
        window_width = self.PREVIEW_SIZE
        window_height = self.PREVIEW_SIZE
        
        # 计算居中位置 靠右30%
        pos_x = int((screen_width - window_width) * 0.7)
        pos_y = (screen_height - window_height) // 2
        
        # 移动窗口到屏幕中央
        cv2.moveWindow(window_name, pos_x, pos_y)

        # 设置进度到开始帧
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        current_frame_idx = start_frame

        is_playing = True
        raw_frame = None

        delay = 1
        last_time = time.time() * 1000
        target_delay_ms = 1000 / fps
        delay_when_paused_ms = 30

        while True:
            self.pump_dialog_events()
            if self.is_confirmed:
                return

            if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                self.is_confirmed = True
                return

            if is_playing:
                ret, raw_frame = cap.read()
                if not ret or current_frame_idx > end_frame:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
                    current_frame_idx = start_frame
                    continue
                current_frame_idx += 1

                current_time = time.time() * 1000
                elapsed_time = current_time - last_time
                delay = max(1, int(target_delay_ms - elapsed_time))
                last_time = current_time
            else:
                delay = delay_when_paused_ms

            if raw_frame is None:
                continue

            drawed_frame = self.draw_frame(raw_frame, is_playing)
            cv2.imshow(window_name, drawed_frame)

            key = cv2.waitKey(delay) & 0xFF
            if key == ord(' '):
                is_playing = not is_playing
                last_time = time.time() * 1000




    def draw_frame(self, raw_frame, is_playing: bool):
        """
        在帧上绘制圆形和其他元素

        Args:
            raw_frame: 原始视频帧
            is_playing: 当前是否在播放状态

        Returns:
            处理后的帧
        """

        # 按要求先对整帧做透视旋转，再执行已有的裁剪/缩放流程
        rotated_frame = self.apply_axis_rotation_preview(raw_frame, self.x_rot_deg, self.y_rot_deg)

        font_size = 0.7
        font_thickness = 2

        half_w = max(1, round(self.circle_r * self.scale_x))
        half_h = max(1, round(self.circle_r * self.scale_y))

        x1 = self.circle_cx - half_w
        x2 = self.circle_cx + half_w
        y1 = self.circle_cy - half_h
        y2 = self.circle_cy + half_h

        target_width = max(1, x2 - x1)
        target_height = max(1, y2 - y1)

        frame_h, frame_w = rotated_frame.shape[:2]
        src_x1 = max(0, x1)
        src_y1 = max(0, y1)
        src_x2 = min(frame_w, x2)
        src_y2 = min(frame_h, y2)

        dst_x1 = max(0, -x1)
        dst_y1 = max(0, -y1)

        cropped_frame = np.zeros((target_height, target_width, 3), dtype=np.uint8)

        if src_x1 < src_x2 and src_y1 < src_y2:
            video_slice = rotated_frame[src_y1:src_y2, src_x1:src_x2]
            slice_height, slice_width = video_slice.shape[:2]
            cropped_frame[dst_y1:dst_y1+slice_height, dst_x1:dst_x1+slice_width] = video_slice

        new_frame_size = self.PREVIEW_SIZE
        resized_frame = cv2.resize(cropped_frame, (new_frame_size, new_frame_size))

        cv2.circle(
            img=resized_frame,
            center=(new_frame_size // 2, new_frame_size // 2),
            radius=4,
            color=(0, 0, 255),
            thickness=2,
        )

        cv2.circle(
            img=resized_frame,
            center=(new_frame_size // 2, new_frame_size // 2),
            radius=356,
            color=(0, 255, 0),
            thickness=2,
        )

        instructions = [
            "SPACE -> pause/play",
            "Adjust values in window",
        ]

        for i, instruction in enumerate(instructions):
            cv2.putText(
                img=resized_frame,
                text=instruction,
                org=(10, 30 + i * 30),
                fontFace=cv2.FONT_HERSHEY_SIMPLEX,
                fontScale=font_size,
                color=(255, 255, 255),
                thickness=font_thickness,
            )

        if not is_playing:
            cv2.putText(
                img=resized_frame,
                text="PAUSED",
                org=(10, new_frame_size - 40),
                fontFace=cv2.FONT_HERSHEY_SIMPLEX,
                fontScale=font_size,
                color=(0, 255, 255),
                thickness=font_thickness,
            )

        circle_info = (
            f"Center: ({self.circle_cx}, {self.circle_cy}), R: {self.circle_r}, "
            f"Scale: ({self.scale_x:.2f}, {self.scale_y:.2f}), "
            f"Rot: ({self.x_rot_deg:.1f}, {self.y_rot_deg:.1f})"
        )
        cv2.putText(
            img=resized_frame,
            text=circle_info,
            org=(10, new_frame_size - 10),
            fontFace=cv2.FONT_HERSHEY_SIMPLEX,
            fontScale=font_size,
            color=(255, 255, 255),
            thickness=font_thickness,
        )

        # 绘制9宫格直线
        # 在x轴和y轴的1/3和2/3位置绘制直线
        grid_color = (0, 255, 0)  # 绿色
        grid_thickness = 1
        
        # 计算1/3和2/3位置
        third_x = new_frame_size // 3
        two_thirds_x = 2 * new_frame_size // 3
        third_y = new_frame_size // 3
        two_thirds_y = 2 * new_frame_size // 3
        
        # 绘制垂直线 (x轴固定，y轴变化)
        cv2.line(
            img=resized_frame,
            pt1=(third_x, 0),
            pt2=(third_x, new_frame_size),
            color=grid_color,
            thickness=grid_thickness,
        )
        cv2.line(
            img=resized_frame,
            pt1=(two_thirds_x, 0),
            pt2=(two_thirds_x, new_frame_size),
            color=grid_color,
            thickness=grid_thickness,
        )
        
        # 绘制水平线 (y轴固定，x轴变化)
        cv2.line(
            img=resized_frame,
            pt1=(0, third_y),
            pt2=(new_frame_size, third_y),
            color=grid_color,
            thickness=grid_thickness,
        )
        cv2.line(
            img=resized_frame,
            pt1=(0, two_thirds_y),
            pt2=(new_frame_size, two_thirds_y),
            color=grid_color,
            thickness=grid_thickness,
        )

        return resized_frame




    def apply_axis_rotation_preview(self, frame, x_rot_deg: float, y_rot_deg: float):
        """将沿 x/y 轴旋转角转换成透视预览效果。"""
        if abs(x_rot_deg) < 1e-6 and abs(y_rot_deg) < 1e-6:
            return frame

        height, width = frame.shape[:2]
        cx = (width - 1) / 2.0
        cy = (height - 1) / 2.0

        corners = np.array(
            [
                [-cx, -cy, 0.0],
                [cx, -cy, 0.0],
                [cx, cy, 0.0],
                [-cx, cy, 0.0],
            ],
            dtype=np.float32,
        )

        x_rad = np.deg2rad(x_rot_deg)
        y_rad = np.deg2rad(y_rot_deg)

        rot_x = np.array(
            [
                [1.0, 0.0, 0.0],
                [0.0, np.cos(x_rad), -np.sin(x_rad)],
                [0.0, np.sin(x_rad), np.cos(x_rad)],
            ],
            dtype=np.float32,
        )
        rot_y = np.array(
            [
                [np.cos(y_rad), 0.0, np.sin(y_rad)],
                [0.0, 1.0, 0.0],
                [-np.sin(y_rad), 0.0, np.cos(y_rad)],
            ],
            dtype=np.float32,
        )

        rotation = rot_y @ rot_x
        rotated = corners @ rotation.T

        focal = max(width, height) * 1.2
        distance = max(width, height) * 1.5
        z = rotated[:, 2] + distance
        z = np.where(np.abs(z) < 1e-6, 1e-6, z)

        projected = np.zeros((4, 2), dtype=np.float32)
        projected[:, 0] = focal * rotated[:, 0] / z + cx
        projected[:, 1] = focal * rotated[:, 1] / z + cy

        min_xy = projected.min(axis=0)
        max_xy = projected.max(axis=0)
        span = np.maximum(max_xy - min_xy, 1e-6)

        dst = np.zeros((4, 2), dtype=np.float32)
        dst[:, 0] = (projected[:, 0] - min_xy[0]) * (width - 1) / span[0]
        dst[:, 1] = (projected[:, 1] - min_xy[1]) * (height - 1) / span[1]

        src = np.array(
            [[0.0, 0.0], [width - 1.0, 0.0], [width - 1.0, height - 1.0], [0.0, height - 1.0]],
            dtype=np.float32,
        )
        matrix = cv2.getPerspectiveTransform(src, dst)
        return cv2.warpPerspective(
            frame,
            matrix,
            (width, height),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0),
        )




    def pump_dialog_events(self) -> None:
        if self.dialog is None:
            return
        try:
            self.dialog.update_idletasks()
            self.dialog.update()
        except tk.TclError:
            self.is_confirmed = True




    def create_dialog(self) -> None:
        """创建常驻控制窗口，负责参数编辑与确认退出。"""
        if self.dialog is not None:
            return
        
        window_w = 300
        window_h = 550

        dialog = tk.Tk()
        dialog.title("Adjust circle")
        dialog.geometry(f"{window_w}x{window_h}")
        dialog.resizable(False, False)

        # 初始位置：屏幕居中靠左
        dialog.update_idletasks()
        screen_width = dialog.winfo_screenwidth()
        screen_height = dialog.winfo_screenheight()
        pos_x = int((screen_width - window_w) * 0.3) # 30%
        pos_y = (screen_height - window_h) // 2  # 居中
        dialog.geometry(f"{window_w}x{window_h}+{pos_x}+{pos_y}")

        self.dialog = dialog
        self.var_radius = tk.StringVar(value=str(self.circle_r))
        self.var_center_x = tk.StringVar(value=str(self.circle_cx))
        self.var_center_y = tk.StringVar(value=str(self.circle_cy))
        self.var_scale_x = tk.StringVar(value=f"{self.scale_x:.2f}")
        self.var_scale_y = tk.StringVar(value=f"{self.scale_y:.2f}")
        self.var_x_rot = tk.StringVar(value=f"{self.x_rot_deg:.1f}")
        self.var_y_rot = tk.StringVar(value=f"{self.y_rot_deg:.1f}")

        top_label = ttk.Label(dialog, text="请按 ok 键退出", padding=(10, 10, 10, 2))
        top_label.pack(anchor=tk.CENTER)

        input_frame = ttk.LabelFrame(dialog, text="Parameters", padding="10")
        input_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(2, 5))

        int_signed_validator = dialog.register(self.validate_signed_int_input)
        radius_validator = dialog.register(self.validate_radius_input)
        scale_validator = dialog.register(self.validate_scale_input)
        rot_validator = dialog.register(self.validate_rot_input)

        self.build_param_row(
            parent=input_frame,
            title="radius r",
            variable=self.var_radius,
            validator=radius_validator,
            minus_command=lambda: self.adjust_radius(-1),
            plus_command=lambda: self.adjust_radius(1),
            submit_command=lambda _event=None: self.submit_radius(),
            note=f"整数，范围 {self.RADIUS_MIN}-{self.RADIUS_MAX}，步进 1",
        )

        self.build_param_row(
            parent=input_frame,
            title="center x",
            variable=self.var_center_x,
            validator=int_signed_validator,
            minus_command=lambda: self.adjust_center("x", -1),
            plus_command=lambda: self.adjust_center("x", 1),
            submit_command=lambda _event=None: self.submit_center("x"),
            note=f"整数，范围 {-self.CENTER_MAX} 到 {self.CENTER_MAX}，步进 1",
        )

        self.build_param_row(
            parent=input_frame,
            title="center y",
            variable=self.var_center_y,
            validator=int_signed_validator,
            minus_command=lambda: self.adjust_center("y", -1),
            plus_command=lambda: self.adjust_center("y", 1),
            submit_command=lambda _event=None: self.submit_center("y"),
            note=f"整数，范围 {-self.CENTER_MAX} 到 {self.CENTER_MAX}，步进 1",
        )

        self.build_param_row(
            parent=input_frame,
            title="x scale",
            variable=self.var_scale_x,
            validator=scale_validator,
            minus_command=lambda: self.adjust_scale("x", -self.SCALE_STEP),
            plus_command=lambda: self.adjust_scale("x", self.SCALE_STEP),
            submit_command=lambda _event=None: self.submit_scale("x"),
            note=f"最多 2 位小数，范围 {self.SCALE_MIN}-{self.SCALE_MAX}，步进 {self.SCALE_STEP}",
        )

        self.build_param_row(
            parent=input_frame,
            title="y scale",
            variable=self.var_scale_y,
            validator=scale_validator,
            minus_command=lambda: self.adjust_scale("y", -self.SCALE_STEP),
            plus_command=lambda: self.adjust_scale("y", self.SCALE_STEP),
            submit_command=lambda _event=None: self.submit_scale("y"),
            note=f"最多 2 位小数，范围 {self.SCALE_MIN}-{self.SCALE_MAX}，步进 {self.SCALE_STEP}",
        )

        self.build_param_row(
            parent=input_frame,
            title="x rot",
            variable=self.var_x_rot,
            validator=rot_validator,
            minus_command=lambda: self.adjust_rotation("x", -self.ROT_STEP),
            plus_command=lambda: self.adjust_rotation("x", self.ROT_STEP),
            submit_command=lambda _event=None: self.submit_rotation("x"),
            note=f"最多 1 位小数，范围 {self.ROT_MIN} 到 {self.ROT_MAX}，步进 {self.ROT_STEP}",
        )

        self.build_param_row(
            parent=input_frame,
            title="y rot",
            variable=self.var_y_rot,
            validator=rot_validator,
            minus_command=lambda: self.adjust_rotation("y", -self.ROT_STEP),
            plus_command=lambda: self.adjust_rotation("y", self.ROT_STEP),
            submit_command=lambda _event=None: self.submit_rotation("y"),
            note=f"最多 1 位小数，范围 {self.ROT_MIN} 到 {self.ROT_MAX}，步进 {self.ROT_STEP}",
        )

        button_frame = ttk.Frame(dialog, padding="10")
        button_frame.pack(fill=tk.X)
        ttk.Button(button_frame, text="OK", width=12, command=self.on_dialog_ok).pack(side=tk.RIGHT)

        dialog.protocol("WM_DELETE_WINDOW", self.on_dialog_close)
        self.sync_dialog_values()




    def build_param_row(self,
                        parent,
                        title: str,
                        variable: tk.StringVar,
                        validator,
                        minus_command,
                        plus_command,
                        submit_command,
                        note: str) -> None:
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=(4, 0))

        ttk.Label(row, text=f"{title}:", width=10).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(row, text="-", width=3, command=minus_command).pack(side=tk.LEFT)
        entry = ttk.Entry(
            row,
            width=10,
            textvariable=variable,
            validate="key",
            validatecommand=(validator, "%P"),
        )
        entry.pack(side=tk.LEFT, padx=6)
        entry.bind("<Return>", submit_command)
        entry.bind("<FocusOut>", submit_command)
        ttk.Button(row, text="+", width=3, command=plus_command).pack(side=tk.LEFT)

        note_label = ttk.Label(parent, text=note)
        note_label.pack(anchor=tk.W, padx=(12, 0), pady=(2, 5))




    def validate_signed_int_input(self, proposed: str) -> bool:
        if proposed in ("", "-"):
            return True
        return bool(re.fullmatch(r"-?\d+", proposed))

    def validate_radius_input(self, proposed: str) -> bool:
        if proposed == "":
            return True
        return proposed.isdigit()

    def validate_scale_input(self, proposed: str) -> bool:
        if proposed in ("", "."):
            return True
        return bool(re.fullmatch(r"\d(\.\d{0,2})?", proposed))

    def validate_rot_input(self, proposed: str) -> bool:
        if proposed in ("", "-", "-.", "."):
            return True
        return bool(re.fullmatch(r"-?\d{1,2}(\.\d{0,1})?", proposed))




    def adjust_radius(self, delta: int) -> None:
        self.circle_r = self.clamp_int(self.circle_r + delta, self.RADIUS_MIN, self.RADIUS_MAX)
        self.sync_dialog_values()

    def adjust_center(self, axis: str, delta: int) -> None:
        if axis == "x":
            self.circle_cx = self.clamp_int(self.circle_cx + delta, self.CENTER_MIN, self.CENTER_MAX)
        else:
            self.circle_cy = self.clamp_int(self.circle_cy + delta, self.CENTER_MIN, self.CENTER_MAX)
        self.sync_dialog_values()

    def adjust_scale(self, axis: str, delta: float) -> None:
        if axis == "x":
            self.scale_x = self.clamp_float(self.scale_x + delta, self.SCALE_MIN, self.SCALE_MAX, 2)
        else:
            self.scale_y = self.clamp_float(self.scale_y + delta, self.SCALE_MIN, self.SCALE_MAX, 2)
        self.sync_dialog_values()

    def adjust_rotation(self, axis: str, delta: float) -> None:
        if axis == "x":
            self.x_rot_deg = self.clamp_float(self.x_rot_deg + delta, self.ROT_MIN, self.ROT_MAX, 1)
        else:
            self.y_rot_deg = self.clamp_float(self.y_rot_deg + delta, self.ROT_MIN, self.ROT_MAX, 1)
        self.sync_dialog_values()




    def submit_radius(self) -> None:
        if self.var_radius is None:
            return

        text = self.var_radius.get().strip()
        if text == "":
            self.sync_dialog_values()
            return

        try:
            value = int(text)
        except ValueError:
            self.show_input_error("radius r 输入无效")
            self.sync_dialog_values()
            return

        if value < self.RADIUS_MIN or value > self.RADIUS_MAX:
            self.show_input_error(f"radius r 范围必须是 {self.RADIUS_MIN}-{self.RADIUS_MAX}")
            self.sync_dialog_values()
            return

        self.circle_r = value
        self.sync_dialog_values()




    def submit_center(self, axis: str) -> None:
        if self.var_center_x is None or self.var_center_y is None:
            return

        var = self.var_center_x if axis == "x" else self.var_center_y
        text = var.get().strip()
        if text in ("", "-"):
            self.sync_dialog_values()
            return

        try:
            value = int(text)
        except ValueError:
            self.show_input_error(f"center {axis} 输入无效")
            self.sync_dialog_values()
            return

        if value < self.CENTER_MIN or value > self.CENTER_MAX:
            self.show_input_error(f"center {axis} 范围必须是 {self.CENTER_MIN} 到 {self.CENTER_MAX}")
            self.sync_dialog_values()
            return

        if axis == "x":
            self.circle_cx = value
        else:
            self.circle_cy = value
        self.sync_dialog_values()




    def submit_scale(self, axis: str) -> None:
        if self.var_scale_x is None or self.var_scale_y is None:
            return

        var = self.var_scale_x if axis == "x" else self.var_scale_y
        text = var.get().strip()
        if text in ("", "."):
            self.sync_dialog_values()
            return

        try:
            value = float(text)
        except ValueError:
            self.show_input_error(f"{axis} scale 输入无效")
            self.sync_dialog_values()
            return

        if value < self.SCALE_MIN or value > self.SCALE_MAX:
            self.show_input_error(f"{axis} scale 范围必须是 {self.SCALE_MIN}-{self.SCALE_MAX}")
            self.sync_dialog_values()
            return

        value = round(value, 2)
        if axis == "x":
            self.scale_x = value
        else:
            self.scale_y = value
        self.sync_dialog_values()




    def submit_rotation(self, axis: str) -> None:
        if self.var_x_rot is None or self.var_y_rot is None:
            return

        var = self.var_x_rot if axis == "x" else self.var_y_rot
        text = var.get().strip()
        if text in ("", "-", "-.", "."):
            self.sync_dialog_values()
            return

        try:
            value = float(text)
        except ValueError:
            self.show_input_error(f"{axis} rot 输入无效")
            self.sync_dialog_values()
            return

        if value < self.ROT_MIN or value > self.ROT_MAX:
            self.show_input_error(f"{axis} rot 范围必须是 {self.ROT_MIN} 到 {self.ROT_MAX}")
            self.sync_dialog_values()
            return

        value = round(value, 1)
        if axis == "x":
            self.x_rot_deg = value
        else:
            self.y_rot_deg = value
        self.sync_dialog_values()




    def show_input_error(self, message: str) -> None:
        if self.dialog is not None:
            messagebox.showerror("错误", message, parent=self.dialog)
        else:
            messagebox.showerror("错误", message)

    def clamp_int(self, value: int, min_value: int, max_value: int) -> int:
        return max(min_value, min(max_value, value))

    def clamp_float(self, value: float, min_value: float, max_value: float, precision: int) -> float:
        return round(max(min_value, min(max_value, value)), precision)




    def sync_dialog_values(self) -> None:
        if self.dialog is None:
            return

        if self.var_radius is not None:
            self.var_radius.set(str(self.circle_r))
        if self.var_center_x is not None:
            self.var_center_x.set(str(self.circle_cx))
        if self.var_center_y is not None:
            self.var_center_y.set(str(self.circle_cy))
        if self.var_scale_x is not None:
            self.var_scale_x.set(f"{self.scale_x:.2f}")
        if self.var_scale_y is not None:
            self.var_scale_y.set(f"{self.scale_y:.2f}")
        if self.var_x_rot is not None:
            self.var_x_rot.set(f"{self.x_rot_deg:.1f}")
        if self.var_y_rot is not None:
            self.var_y_rot.set(f"{self.y_rot_deg:.1f}")

    def on_dialog_ok(self) -> None:
        self.is_confirmed = True

    def on_dialog_close(self) -> None:
        if self.dialog is not None:
            messagebox.showinfo("提示", "请点击 OK 完成并退出。", parent=self.dialog)
        else:
            messagebox.showinfo("提示", "请点击 OK 完成并退出。")
