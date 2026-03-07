from pathlib import Path

from ..detect.note_definition import *
from ...schemas.op_result import OpResult, ok, err
from .tool import *
from .shared_context import *

from .preprocess_tap import preprocess_tap_data
from .preprocess_touch import preprocess_touch_data
from .preprocess_hold import preprocess_hold_data
from .preprocess_touch_hold import preprocess_touch_hold_data
from .preprocess_slide import preprocess_slide_head_data, preprocess_slide_tail_data

from .estimate_tap_speed import estimate_tap_DefaultMsec
from .estimate_touch_speed import estimate_touch_DefaultMsec

from .analyze_tap import analyze_tap_time
from .analyze_touch import analyze_touch_time
from .analyze_hold import analyze_hold_time
from .analyze_touch_hold import analyze_touch_hold_time
from .analyze_slide import analyze_slide_time

from .generate_maidata import generate_maidata




def main(std_video_path: Path,
         bpm: float,
         chart_lv: int,
         base_denominator: int,
         duration_denominator: int
        ) -> OpResult[None]:
    
    try:
        shared_context = create_shared_context(std_video_path)

        tap_info = {}
        touch_info = {}
        hold_info = {}
        touch_hold_info = {}
        slide_info = {}

        # preprocess data
        tap_data = preprocess_tap_data(shared_context)
        touch_data = preprocess_touch_data(shared_context)
        hold_data = preprocess_hold_data(shared_context)
        touch_hold_data = preprocess_touch_hold_data(shared_context)
        slide_head_data = preprocess_slide_head_data(shared_context)
        slide_tail_data = preprocess_slide_tail_data(shared_context)

        # 分析音符流速
        if tap_data:
            shared_context.tap_DefaultMsec, shared_context.tap_OptionNotespeed = estimate_tap_DefaultMsec(shared_context, tap_data)
        if touch_data:
            shared_context.touch_DefaultMsec, shared_context.touch_OptionNotespeed = estimate_touch_DefaultMsec(shared_context, touch_data)
            
        # 分析音符时间
        tap_info = analyze_tap_time(shared_context, tap_data)    
        touch_info = analyze_touch_time(shared_context, touch_data)
        hold_info = analyze_hold_time(shared_context, hold_data)
        touch_hold_info = analyze_touch_hold_time(shared_context, touch_hold_data)
        slide_info = analyze_slide_time(shared_context, slide_head_data, slide_tail_data, bpm)

        # generate maidata
        generate_maidata(shared_context, bpm, chart_lv, base_denominator, duration_denominator, tap_info, slide_info, touch_info, hold_info, touch_hold_info)

        return ok()
    
    except Exception as e:
        return err(f"Unexpected error in auto_convert > analyze > main", e)

