"""
FFmpeg 硬件加速支持检测工具
检测 VP9 解码和 H.264 编码的硬件加速支持情况
"""
import os
import sys
import subprocess
import datetime

root = os.path.normpath(os.path.abspath(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root not in sys.path:
    sys.path.insert(0, root)
import tools.path_config


# 配置列表
TEST_CASES = {
    "vp9_decode_nvidia": {
        "args_template": [
            '-hwaccel', 'cuda', 
            '-hwaccel_output_format', 'cuda',
            '-i', '{input}', 
            '-f', 'null', '-'
        ],
        "input_key": "vp9_test_video",
        "desc": "Nvidia VP9 Decode (NVDEC via CUDA)"
    },
    
    "h264_nvidia": {
        "args_template": [
            '-hwaccel', 'cuda', 
            '-hwaccel_output_format', 'cuda', 
            '-i', '{input}', 
            '-t', '1', 
            '-c:v', 'h264_nvenc', 
            '-f', 'null', '-'
        ],
        "input_key": "h264_test_video",
        "desc": "Nvidia H.264 Transcode (NVDEC + NVENC)"
    },

    "vp9_decode_intel": {
        "args_template": [
            '-init_hw_device', 'qsv=qsv:hw_any',
            '-hwaccel', 'qsv', 
            '-hwaccel_output_format', 'qsv',
            '-i', '{input}', 
            '-f', 'null', '-'
        ],
        "input_key": "vp9_test_video",
        "desc": "Intel VP9 Decode (QSV)"
    },

    "h264_intel": {
        "args_template": [
            # 原理同上
            '-init_hw_device', 'qsv=qsv:hw_any',
            '-hwaccel', 'qsv', 
            '-hwaccel_output_format', 'qsv',
            '-i', '{input}', 
            '-t', '1', 
            '-c:v', 'h264_qsv', 
            '-f', 'null', '-'
        ],
        "input_key": "h264_test_video",
        "desc": "Intel H.264 Transcode (QSV Decode + QSV Encode)"
    },

    "vp9_decode_universal": {
        "args_template": [
            '-hwaccel', 'd3d11va', 
            '-hwaccel_output_format', 'd3d11', 
            '-i', '{input}', 
            '-f', 'null', '-'
        ],
        "input_key": "vp9_test_video",
        "desc": "Windows Universal VP9 Decode (D3D11VA)"
    },
    
    "h264_universal": {
        "args_template": [
            '-hwaccel', 'd3d11va', 
            '-i', '{input}', 
            '-t', '1', 
            '-c:v', 'h264_mf', 
            '-f', 'null', '-'
        ],
        "input_key": "h264_test_video",
        "desc": "Windows Universal H.264 Transcode (D3D11VA Decode + MediaFoundation Encode)"
    }
}



def _probe_ffmpeg(args):
    """
    执行单次 FFmpeg 命令
    Returns: (is_success: bool, error_log: str)
    """
    try:
        ffmpeg_path = os.path.normpath(os.path.abspath(tools.path_config.ffmpeg_exe))
        full_args = ['-hide_banner', '-loglevel', 'error'] + args
        cmd = [ffmpeg_path] + full_args
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8'
        )
        
        if result.returncode == 0:
            return True, ""
        else:
            return False, result.stderr if result.stderr else "Unknown error (no stderr)"
            
    except Exception as e:
        return False, f"Exception: {str(e)}"



def run_single_testcase(case_id):
    """
    运行单个测试用例，只返回成功/失败
    """
    if case_id not in TEST_CASES:
        return False
        
    config = TEST_CASES[case_id]
    input_path = getattr(tools.path_config, config["input_key"])
    
    # 检查文件是否存在
    if not os.path.exists(input_path):
        return False
        
    args = [arg.format(input=input_path) for arg in config["args_template"]]
    success, _ = _probe_ffmpeg(args)
    return success



def check_all_hardware_acceleration():
    """
    运行所有硬件加速检测
    Returns: list[str] 支持的测试ID列表
    """
    supported_ids = []
    error_logs = []
    
    print("FFmpeg 硬件加速支持检测:")
    
    for case_id, config in TEST_CASES.items():
        input_path = getattr(tools.path_config, config["input_key"])
        
        # 检查文件是否存在
        if not os.path.exists(input_path):
            msg = f"Missing test file: {input_path}"
            print(f"  - {config['desc']}: ✗ ({msg})")
            error_logs.append(f"[{datetime.datetime.now()}] [{case_id}] {msg}")
            continue
            
        args = [arg.format(input=input_path) for arg in config["args_template"]]
        success, error_msg = _probe_ffmpeg(args)
        
        status = "✓" if success else "✗"
        print(f"  - {config['desc']}: {status}")
        
        if success:
            supported_ids.append(case_id)
        else:
            error_logs.append(f"[{datetime.datetime.now()}] [{case_id}] Failed.\nError Output:\n{error_msg}\n{'-'*50}")

    # 保存错误日志
    if error_logs:
        timestamp = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        log_filename = f"check_ffmpeg_hw_accleration_errors_{timestamp}.txt"
        log_path = os.path.join(tools.path_config.temp_dir, log_filename)
        
        try:
            os.makedirs(tools.path_config.temp_dir, exist_ok=True)
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(error_logs))
            print(f"\n检测过程中发现错误，详细日志已保存至:\n{log_path}")
        except Exception as e:
            print(f"\n保存错误日志失败: {e}")

    return supported_ids



if __name__ == "__main__":
    supported = check_all_hardware_acceleration()
    print(f"\n支持的硬件加速方案ID: {supported}")
