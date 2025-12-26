"""
持久化设置模型
使用 Pydantic 进行数据校验和序列化
"""

from pydantic import BaseModel, Field, field_validator
from typing import Literal
import re


class PersistentSettings(BaseModel):
    """应用持久化设置"""
    
    # === 模型推理相关 ===
    model_backend: Literal["tensorrt", "directml"] = Field(
        default="tensorrt",
        description="模型推理后端选择"
    )
    
    tensorrt_batch_size: int = Field(
        default=2,
        ge=1,
        le=8,
        description="TensorRT 批处理大小，范围 1-8，默认 2"
    )
    
    # === FFmpeg 硬件加速相关 ===
    ffmpeg_hw_accel_vp9: Literal["cpu", "nvidia"] = Field(
        default="nvidia",
        description="VP9 解码加速策略"
    )
    
    ffmpeg_hw_accel_h264: Literal["cpu", "nvidia"] = Field(
        default="nvidia",
        description="H.264 编解码加速策略"
    )
    
    # === 应用通用设置 ===
    language: Literal["zh-cn", "en-us"] = Field(
        default="zh-cn",
        description="语言"
    )
    
    main_output_dir_name: str = Field(
        default="aaa-result",
        description="主要输出文件夹名称，默认 aaa-result"
    )
    
    main_app_init_size: tuple[int, int] = Field(
        default=(1300, 900),
        description="应用初始窗口大小 (w, h)"
    )
    
    main_app_min_size: tuple[int, int] = Field(
        default=(800, 600),
        description="应用最小窗口大小 (w, h)"
    )
    

    # === 字段校验器 ===
    @field_validator('main_output_dir_name')
    @classmethod
    def validate_windows_filename(cls, v: str) -> str:
        """校验 Windows 文件/文件夹名称"""
        if not v or not v.strip():
            raise ValueError("输出目录名称不能为空")
        
        # Windows 文件名禁止字符
        invalid_chars = r'[\\/:*?"<>|]'
        if re.search(invalid_chars, v):
            raise ValueError(
                '文件夹名称不能包含以下字符: \\ / : * ? " < > |'
            )
        
        # 禁止保留名称
        reserved_names = {
            'CON', 'PRN', 'AUX', 'NUL',
            'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
            'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
        }
        if v.upper() in reserved_names:
            raise ValueError(f"不能使用 Windows 保留名称: {v}")
        
        return v.strip()
    
    
    class Config:
        extra = "forbid"  # 禁止未定义的字段
        validate_assignment = True  # 赋值时也进行校验
