from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from .op_result import OpResult, ok, err
from ..tools import validate_windows_filename




@dataclass(slots=True)
class AutoConvertConfig_Definition:
    """
    Definition for AutoConvertConfig

    Attributes:
        key: str
        type: Literal["int", "float", "path", "str", "bool", "enum(Standardize_VideoMode)"]
        group: Literal["standardize", "detect", "analyze"]
        default: any
        optional: bool
        constraints: dict | None

    Constraints:
        For int/float:
            - "ge": int, minimum value (inclusive)
            - "gt": int, minimum value (exclusive)
            - "le": int, maximum value (inclusive)
            - "lt": int, maximum value (exclusive)
            - "options": list of allowed values
        For str:
            - "options": list of allowed strings
        For path:
            - "must_exist": bool
        For bool:
            - N/A
    """

    key: str
    type: Literal["int", "float", "path", "str", "bool", "enum"]
    group: Literal["standardize", "detect", "analyze"]
    default: any = None
    optional: bool = True
    constraints: dict | None = None




@dataclass(slots=True)
class AutoConvertConfig_Definitions:
      

	# standardize
    
	input_video_path = AutoConvertConfig_Definition(
		key="input_video_path",
		type="path",
		group="standardize",
		optional=False, # 必选没有默认值
		constraints={"must_exist": True} # 输入视频必须存在
	)

	video_name = AutoConvertConfig_Definition(
		key="video_name",
		type="str",
		group="standardize",
		default=None, # 如果没有输入，使用 input_video_path 的文件名（不带扩展名）
	)

	video_mode = AutoConvertConfig_Definition(
		key="video_mode",
		type="str",
		group="standardize",
		default = "source video", # 默认模式
		constraints={"options":["source video", "camera footage"]}
    )

	duration = AutoConvertConfig_Definition(
		key="duration",
		type="float",
		group="standardize",
		optional=False, # 必选没有默认值
	)

	start_sec = AutoConvertConfig_Definition(
		key="start_sec",
		type="float",
		group="standardize",
		default=None,
		constraints={"ge": 0.0}
	)

	end_sec = AutoConvertConfig_Definition(
		key="end_sec",
		type="float",
		group="standardize",
		default=None,
		constraints={"ge": 0.0}
	)

	skip_detect_circle = AutoConvertConfig_Definition(
		key="skip_detect_circle",
		type="bool",
		group="standardize",
		default=False
	)

	target_res = AutoConvertConfig_Definition(
		key="target_res",
		type="int",
		group="standardize",
		default=1080,
		constraints={"gt": 0}
	)



	# detect

	std_video_path_detect = AutoConvertConfig_Definition(
		key="std_video_path_detect",
		type="path",
		group="detect",
		optional=False, # 必选没有默认值
		constraints={"must_exist": True}
	)

	batch_detect = AutoConvertConfig_Definition(
		key="batch_detect",
		type="int",
		group="detect",
		default=2,
		constraints={"options": [1, 2, 3, 4, 5, 6, 7, 8]}
	)

	batch_cls = AutoConvertConfig_Definition(
		key="batch_cls",
		type="int",
		group="detect",
		default=16,
		constraints={"options": [1, 2, 4, 8, 16, 32, 64]}
	)

	inference_device = AutoConvertConfig_Definition(
		key="inference_device",
		type="str",
		group="detect",
		optional=False, # 必选没有默认值
		# tensorRT -> "cuda"
		# direct_ml -> "0"
	)

	detect_model_path = AutoConvertConfig_Definition(
		key="detect_model_path",
		type="path",
		group="detect",
		optional=False, # 必选没有默认值
		constraints={"must_exist": True} # 模型路径必须存在
	)

	obb_model_path = AutoConvertConfig_Definition(
		key="obb_model_path",
		type="path",
		group="detect",
		optional=False, # 必选没有默认值
		constraints={"must_exist": True} # 模型路径必须存在
	)

	cls_ex_model_path = AutoConvertConfig_Definition(
		key="cls_ex_model_path",
		type="path",
		group="detect",
		optional=False, # 必选没有默认值
		constraints={"must_exist": True} # 模型路径必须存在
	)

	cls_break_model_path = AutoConvertConfig_Definition(
		key="cls_break_model_path",
		type="path",
		group="detect",
		optional=False, # 必选没有默认值
		constraints={"must_exist": True} # 模型路径必须存在
	)

	skip_detect = AutoConvertConfig_Definition(
		key="skip_detect",
		type="bool",
		group="detect",
		default=False
	)

	skip_cls = AutoConvertConfig_Definition(
		key="skip_cls",
		type="bool",
		group="detect",
		default=False
	)

	skip_export_tracked_video = AutoConvertConfig_Definition(
		key="skip_export_tracked_video",
		type="bool",
		group="detect",
		default=False
	)




	# analyze

	std_video_path_analyze = AutoConvertConfig_Definition(
		key="std_video_path_analyze",
		type="path",
		group="analyze",
		optional=False,
		constraints={"must_exist": True}
	)

	bpm = AutoConvertConfig_Definition(
		key="bpm",
		type="float",
		group="analyze",
		optional=False, # 必选没有默认值
	)

	chart_lv = AutoConvertConfig_Definition(
		key="chart_lv",
		type="int",
		group="analyze",
		default=5, # master
		constraints={"options": [0, 1, 2, 3, 4, 5, 6, 7]}
	)

	base_denominator = AutoConvertConfig_Definition(
		key="base_denominator",
		type="int",
		group="analyze",
		default=16,
		constraints={"options": [4, 8, 16, 32, 64]}
	)

	duration_denominator = AutoConvertConfig_Definition(
		key="duration_denominator",
		type="int",
		group="analyze",
		default=8,
		constraints={"options": [4, 8, 16, 32, 64]}
	 )


