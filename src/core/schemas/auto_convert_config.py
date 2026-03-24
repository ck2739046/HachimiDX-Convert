from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .op_result import OpResult, ok, err
from ..tools.validate_windows_filename import validate_windows_filename
from .media_config import MediaType




@dataclass(slots=True)
class AutoConvertConfig_Definition:
    """
    Definition for AutoConvertConfig

    Attributes:
        key: str
        type: Literal["int", "float", "path", "str", "bool", "enum"]
        group: Literal["common", "standardize", "detect", "analyze"]
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
    group: Literal["common", "standardize", "detect", "analyze"]
    default: any = None
    optional: bool = True
    constraints: dict | None = None




@dataclass(slots=True)
class AutoConvertConfig_Definitions:
      


	# common
    
	is_standardize_enabled = AutoConvertConfig_Definition(
		key="is_standardize_enabled",
		type="bool",
		group="common",
		default=True
	)
      
	is_detect_enabled = AutoConvertConfig_Definition(
		key="is_detect_enabled",
		type="bool",
		group="common",
		default=True
	)
      
	is_analyze_enabled = AutoConvertConfig_Definition(
		key="is_analyze_enabled",
		type="bool",
		group="common",
		default=True
	)
      



	# standardize
    
	standardize_input_video_path = AutoConvertConfig_Definition(
		key="standardize_input_video_path",
		type="path",
		group="standardize",
		optional=False, # 必选没有默认值
		constraints={"must_exist": True} # 输入视频必须存在
	)
      
	song_name = AutoConvertConfig_Definition(
		key="song_name",
		type="str",
		group="standardize",
		optional=False, # 必选没有默认值
	)

	video_mode = AutoConvertConfig_Definition(
		key="video_mode",
		type="str",
		group="standardize",
		default = "source video", # 默认模式
		constraints={"options":["source video", "camera footage"]}
    )
      
	media_type = AutoConvertConfig_Definition(
        key="media_type",
        type="enum",
        group="standardize",
        optional=False, # 必选没有默认值
        constraints={"options": [MediaType.VIDEO_WITH_AUDIO, MediaType.VIDEO_WITHOUT_AUDIO]}
    )

	duration = AutoConvertConfig_Definition(
		key="duration",
		type="float",
		group="standardize",
		optional=False, # 必选没有默认值
        constraints={"gt": 0}
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
		default=None
	)

	skip_detect_circle = AutoConvertConfig_Definition(
		key="skip_detect_circle",
		type="bool",
		group="standardize",
		default=True
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
		constraints={"gt": 0}
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


