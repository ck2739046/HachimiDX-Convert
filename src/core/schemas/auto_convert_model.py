from typing import Optional, Literal, Any
from pathlib import Path
from pydantic import BaseModel, Field, FilePath, field_validator, model_validator

from .auto_convert_config import AutoConvertConfig_Definitions as AC_Defs
from src.core.tools import validate_windows_filename
from src.services.settings_manage import SettingsManage



class AutoConvertModel(BaseModel):
	"""
	AutoConvert configuration model for validation and processing.
	All fields have defaults as defined in auto_convert_config.py.
	"""

	# Standardize group

	input_video_path: FilePath # 必需参数 没有默认值
	
	video_name: Optional[str] = Field(default=AC_Defs.video_name.default)
	
	video_mode: Optional[str] = Field(default=AC_Defs.video_mode.default)

	duration: float # 必需参数 没有默认值

	start_sec: Optional[float] = Field(default=AC_Defs.start_sec.default, ge=AC_Defs.start_sec.constraints["ge"])

	end_sec: Optional[float] = Field(default=AC_Defs.end_sec.default, ge=AC_Defs.end_sec.constraints["ge"])

	skip_detect_circle: Optional[bool] = Field(default=AC_Defs.skip_detect_circle.default)

	target_res: Optional[int] = Field(default=AC_Defs.target_res.default, gt=AC_Defs.target_res.constraints["gt"])




	# detect group

	std_video_path_detect: FilePath # 必需参数 没有默认值

	batch_detect: Optional[int] = Field(default=AC_Defs.batch_detect.default)

	batch_cls: Optional[int] = Field(default=AC_Defs.batch_cls.default)

	inference_device: str # 必需参数 没有默认值

	detect_model_path: FilePath # 必需参数 没有默认值

	obb_model_path: FilePath # 必需参数 没有默认值

	cls_ex_model_path: FilePath # 必需参数 没有默认值

	cls_break_model_path: FilePath # 必需参数 没有默认值

	skip_detect: Optional[bool] = Field(default=AC_Defs.skip_detect.default)

	skip_cls: Optional[bool] = Field(default=AC_Defs.skip_cls.default)

	skip_export_tracked_video: Optional[bool] = Field(default=AC_Defs.skip_export_tracked_video.default)




	# analyze group

	std_video_path_analyze: FilePath # 必需参数 没有默认值

	bpm: float # 必需参数 没有默认值

	chart_lv: Optional[int] = Field(default=AC_Defs.chart_lv.default)

	base_denominator: Optional[int] = Field(default=AC_Defs.base_denominator.default)

	duration_denominator: Optional[int] = Field(default=AC_Defs.duration_denominator.default)





	# field validators
	
	@field_validator('video_mode')
	@classmethod
	def validate_video_mode_options(cls, v):
		if v is None:
			return v
		allowed = AC_Defs.video_mode.constraints["options"]
		if v not in allowed:
			raise ValueError(f"video_mode must be one of {allowed}, got {v}")
		return v
	
	@field_validator('batch_detect')
	@classmethod
	def validate_batch_detect_options(cls, v):
		if v is None:
			return v
		allowed = AC_Defs.batch_detect.constraints["options"]
		if v not in allowed:
			raise ValueError(f"batch_detect must be one of {allowed}, got {v}")
		return v
	
	@field_validator('batch_cls')
	@classmethod
	def validate_batch_cls_options(cls, v):
		if v is None:
			return v
		allowed = AC_Defs.batch_cls.constraints["options"]
		if v not in allowed:
			raise ValueError(f"batch_cls must be one of {allowed}, got {v}")
		return v
	
	@field_validator('chart_lv')
	@classmethod
	def validate_chart_lv_options(cls, v):
		if v is None:
			return v
		allowed = AC_Defs.chart_lv.constraints["options"]
		if v not in allowed:
			raise ValueError(f"chart_lv must be one of {allowed}, got {v}")
		return v
	
	@field_validator('base_denominator')
	@classmethod
	def validate_base_denominator_options(cls, v):
		if v is None:
			return v
		allowed = AC_Defs.base_denominator.constraints["options"]
		if v not in allowed:
			raise ValueError(f"base_denominator must be one of {allowed}, got {v}")
		return v
	
	@field_validator('duration_denominator')
	@classmethod
	def validate_duration_denominator_options(cls, v):
		if v is None:
			return v
		allowed = AC_Defs.duration_denominator.constraints["options"]
		if v not in allowed:
			raise ValueError(f"duration_denominator must be one of {allowed}, got {v}")
		return v
	
	

	




	# model validators

	# 检查 video_name
	@model_validator(mode='after')
	def validate_video_name(self):
		# 验证合法性
		if self.video_name is not None:
			res = validate_windows_filename(self.video_name)
			if res.is_ok:
				return self
			else:
				raise ValueError(f"video_name '{self.video_name}' contains invalid characters for Windows filenames.")
		# 如果没有输入，使用输入文件名作为默认视频名称
		default_name = self.input_video_path.stem
		res = validate_windows_filename(default_name)
		if res.is_ok:
			self.video_name = default_name # update
			return self
		else:
			raise ValueError(f"Derived default video_name '{default_name}' from input_video_path is not a valid Windows filename.")
		
	


	# 检查 start_sec / end_sec
	@model_validator(mode='after')
	def validate_start_end_sec(self):

		def resolve_end(self):
			return self.duration + self.end_sec if self.end_sec < 0 else self.end_sec
		
		set_start = self.start_sec is not None and self.start_sec !=  0
		set_end = self.end_sec is not None and self.end_sec != 0

		if self.duration <= 0:
			raise ValueError(f"duration must be greater than 0, got {self.duration}")
		
		# 确保 start < end < duration
		if set_start and self.start_sec >= self.duration:
			raise ValueError("'start' must be less than 'duration'.")
		if set_end and resolve_end(self) >= self.duration:
			raise ValueError("'end' must be less than 'duration'.")
		if set_start and set_end and self.start_sec >= resolve_end(self):
			raise ValueError("'start' must be less than 'end'.")

        # 最后更新 end 值 (如果设置了)
		if set_end:
			self.end_sec = resolve_end(self)
        # 统一设置为三位小数/None
		self.start_sec = round(self.start_sec, 3) if set_start else None
		self.end_sec   = round(self.end_sec, 3)   if set_end else None
		self.duration  = round(self.duration, 3)
		
		return self
		



