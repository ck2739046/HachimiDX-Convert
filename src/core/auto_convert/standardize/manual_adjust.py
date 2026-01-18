import cv2
from typing import Tuple, Optional
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
import time

from ...schemas.op_result import OpResult, ok, err, print_op_result


class ManualAdjust:

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

        self.operation_history = []
        self.operation_history.append((circle_center, circle_radius))

        self.video_width = 0
        self.video_height = 0


    




    def main(self) -> OpResult[Tuple[Tuple[int, int], int]]:
        """
        如果没有跳过 initial detection
        那么需要人工确认是否识别正确
        显示预览窗口，绘制原始图像帧和圆形
        
        Returns:
            OpResult -> (circle_center, circle_radius)
        """

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
            
            start_frame = round(self.start_sec * fps)
            end_frame = round(self.end_sec * fps) if self.end_sec > 0 else total_frames
            
            self.display_preview(cap, start_frame, end_frame, fps)

            return ok(self.operation_history[-1])
            
        except Exception as e:
            return err(f"Error in display_preview", error_raw = e)
        
        finally:
            try:
                cv2.destroyAllWindows()
                cap.release()
            except:
                pass





    def display_preview(self, cap: cv2.VideoCapture, start_frame: int, end_frame: int, fps: float) -> None:
        
        # 设置窗口
        window_name = "Detected Circle Preview"
        cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)

        # 设置进度到开始帧
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        current_frame_idx = start_frame

        is_playing: bool = True
        should_update_paused_frame: bool = True

        raw_frame = None     # opencv 读取的原始帧
        drawed_frame = None  # 绘制后的帧
        
        delay: int = 1
        last_time: float = 0
        target_delay_ms: float = 1000 / fps
        delay_when_paused_ms: int = 30  # 暂停时降低循环速度
        
        while True:

            if is_playing:
                # 读取下一帧
                ret, raw_frame = cap.read()
                if not ret or current_frame_idx > end_frame:
                    # 视频到达结尾或用户指定的结束帧，从头开始播放
                    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
                    current_frame_idx = start_frame
                    continue
                # 绘制帧
                drawed_frame = self.draw_frame(raw_frame, is_playing)
                current_frame_idx += 1
                should_update_paused_frame = True  # reset flag
                # 调整播放速度，匹配原始帧率
                current_time = time.time() * 1000
                elapsed_time = current_time - last_time
                delay = max(1, int(target_delay_ms - elapsed_time))
                last_time = current_time
                print(delay, end="\r")
            
            else:
                # 暂停时不读取新帧，直接使用 raw_frame
                # 由于暂停后需要在画面左上角绘制 "PAUSED"，所以需要重新绘制帧
                # 但只用绘制一次，后续直接使用 drawed_frame
                if should_update_paused_frame and raw_frame is not None:
                    drawed_frame = self.draw_frame(raw_frame, is_playing)
                    should_update_paused_frame = False
                # 暂停时降低循环速度
                delay = delay_when_paused_ms

            # 显示帧
            # 不管是否暂停，cv2 都需要 imshow 来处理窗口事件
            cv2.imshow(window_name, drawed_frame)

            # 处理键盘输入
            key = cv2.waitKey(delay) & 0xFF # 通过 delay 控制循环速度
            
            # esc/enter: 保存并退出
            if key == 27 or key == 13:
                return
            
            # 空格: 播放/暂停
            elif key == ord(' '):
                is_playing = not is_playing

            # r: 回退到上一次修改
            elif key == ord('r'):
                # 确保 list 始终有初始值
                if len(self.operation_history) > 1:
                    self.operation_history.pop()
                # 暂停并更新帧
                is_playing = False
                should_update_paused_frame = True
                
            # 其他: 进入调整界面
            # 用户想要调整圆心和半径
            else:
                # 暂停并更新帧
                is_playing = False
                should_update_paused_frame = True
                # 创建弹窗
                self.create_dialog()







    def draw_frame(self, raw_frame, is_playing: bool):
        """
        在帧上绘制圆形和其他元素
        
        Args:
            raw_frame: 原始视频帧
            is_playing: 当前是否在播放状态
            
        Returns:
            处理后的帧
        """

        (circle_cx, circle_cy), circle_r = self.operation_history[-1]

        font_size = 0.7
        font_thickness = 2
        
        # 裁剪帧坐标
        x1 = circle_cx - circle_r
        x2 = circle_cx + circle_r
        y1 = circle_cy - circle_r
        y2 = circle_cy + circle_r
        # 确保不越界
        if x1 < 0: x1 = 0
        if y1 < 0: y1 = 0
        if x2 > self.video_width: x2 = self.video_width
        if y2 > self.video_height: y2 = self.video_height
        # 检查是否需要裁剪
        if x1 != 0 or y1 != 0 or x2 != self.video_width or y2 != self.video_height:
            raw_frame = raw_frame[y1:y2, x1:x2] # 裁剪

        # 缩放到 800x800
        new_frame_size = 800
        resized_frame = cv2.resize(raw_frame, (new_frame_size, new_frame_size))

        # 绘制圆心
        cv2.circle(img = resized_frame,
                   center = (new_frame_size // 2, new_frame_size // 2),
                   radius = 4,
                   color = (0, 0, 255),
                   thickness = 2)

        # 左上角提示
        instructions = [
            "Press SPACE to pause/play video",
            "Press Esc/Enter to quit",
            "Press R to undo",
            "If circle is incorrect,",
            "press any other key to adjust"
        ]
        
        for i, instruction in enumerate(instructions):
            cv2.putText(
                img = resized_frame,
                text = instruction,
                org = (10, 30 + i * 30),
                fontFace = cv2.FONT_HERSHEY_SIMPLEX,
                fontScale = font_size,
                color = (255, 255, 255),
                thickness = font_thickness
            )
        
        # 左下角提示
        # 第1行：暂停状态
        if not is_playing:
            cv2.putText(
                img = resized_frame,
                text = "PAUSED",
                org = (10, new_frame_size - 60),
                fontFace = cv2.FONT_HERSHEY_SIMPLEX,
                fontScale = font_size,
                color = (0, 255, 255),
                thickness = font_thickness
            )
        
        # 第2行：圆形坐标和半径
        circle_info = f"Center: ({circle_cx}, {circle_cy}), Radius: {circle_r}"
        cv2.putText(
            img = resized_frame,
            text = circle_info,
            org = (10, new_frame_size - 30),
            fontFace = cv2.FONT_HERSHEY_SIMPLEX,
            fontScale = font_size,
            color = (255, 255, 255),
            thickness = font_thickness
        )
        
        return resized_frame






    def on_submit(self, entry_x, entry_y, entry_radius, dialog) -> None:
        """
        gui handler
    
        如果用户确认调整，直接更新 self.operation_history
        其他情况下不做任何修改
        """

        # 从GUI输入框中获取用户输入的数值
        try:
            x_offset = int(entry_x.get())
        except Exception:
            messagebox.showerror("错误", "X offset 输入无效")
            return
        try:
            y_offset = int(entry_y.get())
        except Exception:
            messagebox.showerror("错误", "Y offset 输入无效")
            return
        try:
            radius = float(entry_radius.get())
        except Exception:
            messagebox.showerror("错误", "Radius 输入无效")
            return
        
        (circle_cx, circle_cy), circle_r = self.operation_history[-1]
        
        # 计算新的圆心坐标（当前坐标 + 用户输入的偏移量）
        new_x = circle_cx + x_offset
        new_y = circle_cy + y_offset
        
        # 验证新的圆心坐标是否在视频范围内
        if new_x < 0 or new_x >= self.video_width or new_y < 0 or new_y >= self.video_height:
            messagebox.showerror(
                "错误", 
                f"调整后的圆心 ({new_x}, {new_y}) 超出视频范围\n"
                f"有效范围: X: 0-{self.video_width-1}, Y: 0-{self.video_height-1}"
            )
            return

        # 处理半径参数：支持两种输入方式

        # 方式1：用户直接输入了半径值（≥100）
        if radius >= 100:
            new_radius = round(radius)
        # 方式2：用户输入了缩放系数（0.5-1.5）
        elif 0.5 <= radius <= 1.5:
            # 计算新的半径 = 当前半径 * 缩放系数
            new_radius = round(circle_r * radius)
        # 无效
        else:
            messagebox.showerror("错误", "半径输入无效，请输入 ≥100 的整数或 0.5-1.5 之间的小数")
            return

        # 验证新的半径值
        if new_radius > max(self.video_width, self.video_height):
            messagebox.showerror("错误", f"新半径 {new_radius} 超出视频范围 {max(self.video_width, self.video_height)}")
            return
        if new_radius < 100:
            messagebox.showerror("错误", f"新半径 {new_radius} 太小（最小值为 100）")
            return
        
        # 所有验证通过，保存调整结果并关闭窗口
        self.operation_history.append(((new_x, new_y), new_radius))
        print(f"Adjustment applied: New center ({new_x}, {new_y}), New radius {new_radius}")
        dialog.destroy()
            









    def create_dialog(self) -> None:
        """创建 gui 弹窗，供用户调整圆心和半径"""

        (circle_cx, circle_cy), circle_r = self.operation_history[-1]

        # ========== 创建GUI窗口 ==========
        dialog = tk.Tk()
        dialog.title("Adjust circle")
        dialog.geometry("400x300")
        dialog.resizable(False, False)
        
        # 将窗口显示在屏幕中央
        dialog.update_idletasks()
        screen_width = dialog.winfo_screenwidth()
        screen_height = dialog.winfo_screenheight()
        x = (screen_width - 400) // 2
        y = (screen_height - 300) // 2
        dialog.geometry(f"400x300+{x}+{y}")

        # ========== 上半部分：显示当前圆心和半径信息 ==========
        info_frame = ttk.LabelFrame(dialog, text="Current", padding="10")
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        
        current_info = ttk.Label(
            info_frame,
            text=f"Center: ({circle_cx}, {circle_cy})   Radius: {circle_r}"
        )
        current_info.pack()
        
        # ========== 中间部分：参数调整输入框 ==========
        input_frame = ttk.LabelFrame(dialog, text="Adjustment", padding="10")
        input_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # X轴偏移输入框
        x_frame = ttk.Frame(input_frame)
        x_frame.pack(fill=tk.X, pady=8)
        ttk.Label(x_frame, text="X offset:", width=7).pack(side=tk.LEFT, padx=(0, 10))
        entry_x = ttk.Entry(x_frame, width=6)
        entry_x.pack(side=tk.LEFT)
        entry_x.insert(0, "0")
        ttk.Label(x_frame, text="(unit: pixel) + right, - left").pack(side=tk.LEFT, padx=(10, 0))
        
        # Y轴偏移输入框
        y_frame = ttk.Frame(input_frame)
        y_frame.pack(fill=tk.X, pady=8)
        ttk.Label(y_frame, text="Y offset:", width=7).pack(side=tk.LEFT, padx=(0, 10))
        entry_y = ttk.Entry(y_frame, width=6)
        entry_y.pack(side=tk.LEFT)
        entry_y.insert(0, "0")
        ttk.Label(y_frame, text="(unit: pixel) + down, - up").pack(side=tk.LEFT, padx=(10, 0))
        
        # 半径调整输入框
        radius_frame = ttk.Frame(input_frame)
        radius_frame.pack(fill=tk.X, pady=8)
        ttk.Label(radius_frame, text="Radius:", width=7).pack(side=tk.LEFT, padx=(0, 10))
        entry_radius = ttk.Entry(radius_frame, width=6)
        entry_radius.pack(side=tk.LEFT)
        entry_radius.insert(0, "1.0")
        ttk.Label(radius_frame, text="0.5-1.5: scale, ≥100: set exact value").pack(side=tk.LEFT, padx=(10, 0))
        
        # ========== 下半部分：按钮区域 ==========
        button_frame = ttk.Frame(dialog, padding="10")
        button_frame.pack(fill=tk.X)
        
        ttk.Button(button_frame, text="OK", width=10,
                   command=lambda: self.on_submit(entry_x, entry_y, entry_radius, dialog)
                  ).pack(side=tk.RIGHT, padx=5)
        
        # 焦点设置到第一个输入框
        entry_x.focus()
        
        # 绑定快捷键：回车键=按下 OK 按钮
        dialog.bind('<Return>', lambda e: self.on_submit(entry_x, entry_y, entry_radius, dialog))

        # 显示窗口并等待用户操作
        dialog.mainloop()
