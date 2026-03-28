"""
路径设置模型
所有路径都必须存在，否则抛出异常
"""

import os
from pydantic import BaseModel, FilePath, DirectoryPath, field_validator
from pathlib import Path
from typing import Any


class PathSettings(BaseModel):
    """应用路径配置（只读）"""
    
    # === 项目根目录 ===
    root_dir: DirectoryPath
    
    # === 临时文件目录 ===
    temp_dir: DirectoryPath
    
    # === Majdata 工具 ===
    majdata_dir: DirectoryPath
    majdata_edit_exe: FilePath
    majdata_view_exe: FilePath
    majdata_control_txt: Path  # 控制文件可以不存在，运行时创建
    
    # === 模型文件 ===
    models_dir: DirectoryPath

    detect_pt: FilePath
    obb_pt: FilePath
    cls_break_pt: FilePath
    cls_ex_pt: FilePath

    detect_onnx: Path     # 可以不存在
    obb_onnx: Path        # 可以不存在
    cls_break_onnx: Path  # 可以不存在
    cls_ex_onnx: Path     # 可以不存在

    detect_engine: Path   # 可以不存在
    
    # === FFmpeg 工具 ===
    ffmpeg_exe: FilePath
    ffprobe_exe: FilePath
    
    # === 编解码测试视频 ===
    # https://test-videos.co.uk/vids/bigbuckbunny/webm/vp9/1080/Big_Buck_Bunny_1080_10s_1MB.webm
    vp9_test_video: FilePath
    # https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/1080/Big_Buck_Bunny_1080_10s_1MB.mp4
    h264_test_video: FilePath
    
    # === 输出目录 ===
    main_output_dir: Path  # 初始可能不存在
    
    # === app src ===
    app_icon: FilePath
    click_template: FilePath
    
    # === 配置文件 ===
    settings_json: Path  # 配置文件路径，初始可能不存在
    

    @classmethod
    def from_root(cls, root: Path, output_dir_name) -> "PathSettings":
        """
        从项目根目录构建路径配置
        
        Args:
            root: 项目根目录
            output_dir_name: 输出目录名称（从 PersistentSettings 获取）
        
        Returns:
            PathSettings 实例
        
        Raises:
            FileNotFoundError: 如果必需的文件或目录不存在
        """
        # 标准化根目录路径
        root_normalized = os.path.normpath(os.path.abspath(str(root)))
        root = Path(root_normalized)
        
        # 构建所有路径
        paths = {
            'root_dir': root,
            'temp_dir': root / 'src' / 'temp',
            
            # Majdata
            'majdata_dir': root / 'src' / 'Majdata',
            'majdata_edit_exe': root / 'src' / 'Majdata' / 'MajdataEdit.exe',
            'majdata_view_exe': root / 'src' / 'Majdata' / 'MajdataView.exe',
            'majdata_control_txt': root / 'src' / 'Majdata' / 'HachimiDX-Convert-Majdata-Control.txt',
            
            # 模型
            'models_dir': root / 'src' / 'models',
            'detect_pt': root / 'src' / 'models' / 'detect.pt',
            'detect_onnx': root / 'src' / 'models' / 'detect.onnx',
            'detect_engine': root / 'src' / 'models' / 'detect.engine',
            'obb_pt': root / 'src' / 'models' / 'obb.pt',
            'obb_onnx': root / 'src' / 'models' / 'obb.onnx',
            'cls_break_pt': root / 'src' / 'models' / 'cls-break.pt',
            'cls_break_onnx': root / 'src' / 'models' / 'cls-break.onnx',
            'cls_ex_pt': root / 'src' / 'models' / 'cls-ex.pt',
            'cls_ex_onnx': root / 'src' / 'models' / 'cls-ex.onnx',
            
            # FFmpeg
            'ffmpeg_exe': root / 'src' / 'ffmpeg-8.0-essentials_build' / 'bin' / 'ffmpeg.exe',
            'ffprobe_exe': root / 'src' / 'ffmpeg-8.0-essentials_build' / 'bin' / 'ffprobe.exe',
            
            # 测试视频
            'vp9_test_video': root / 'src' / 'vp9_test.webm',
            'h264_test_video': root / 'src' / 'h264_test.mp4',
            
            # 输出目录（动态）
            'main_output_dir': root / output_dir_name,
            
            # 应用资源
            'app_icon': root / 'src' / 'icon.ico',
            'click_template': root / 'src' / 'click_template.aac',
            
            # 配置文件
            'settings_json': root / 'src' / 'settings.json',
        }
        
        return cls(**paths)
    

    def ensure_dirs_exist(self) -> None:
        """确保目录存在，如果不存在则创建"""
        writable_dirs = [
            self.temp_dir,
            self.main_output_dir,
        ]
        
        for dir_path in writable_dirs:
            dir_path.mkdir(parents=True, exist_ok=True)
    

    class Config:
        # 禁止额外字段
        extra = "forbid"
        # 允许 Path 对象
        arbitrary_types_allowed = True
