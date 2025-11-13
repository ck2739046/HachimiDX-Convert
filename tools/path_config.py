import os

# 项目根目录
root_dir = os.path.join(os.path.dirname(__file__), '..')

# 用于临时存放文件
temp_dir = os.path.join(root_dir, 'src', 'temp')
temp_auto_convert_args_json = os.path.join(temp_dir, 'auto_convert_args.json')

# Majdata
majdata_dir = os.path.join(root_dir, 'src', 'Majdata')
majdataEdit_exe = os.path.join(majdata_dir, 'MajdataEdit.exe')
majdataView_exe = os.path.join(majdata_dir, 'MajdataView.exe')
# 控制majdataedit的txt路径
majdata_control_txt = os.path.join(majdata_dir, 'HachimiDX-Convert-Majdata-Control.txt')

# 模型文件
models_dir = os.path.join(root_dir, 'src', 'models')
detect_pt = os.path.join(models_dir, 'detect.pt')
detect_onnx = os.path.join(models_dir, 'detect.onnx')
detect_engine = os.path.join(models_dir, 'detect.engine')
obb_pt = os.path.join(models_dir, 'obb.pt')
obb_onnx = os.path.join(models_dir, 'obb.onnx')
cls_break_pt = os.path.join(models_dir, 'cls-break.pt')
cls_break_onnx = os.path.join(models_dir, 'cls-break.onnx')
cls_ex_pt = os.path.join(models_dir, 'cls-ex.pt')
cls_ex_onnx = os.path.join(models_dir, 'cls-ex.onnx')

# ffmpeg.exe路径
ffmpeg_exe = os.path.join(root_dir, 'src', 'ffmpeg-8.0-essentials_build', 'bin', 'ffmpeg.exe')

# 最终数据输出文件夹 (歌曲)
all_songs_dir = os.path.join(root_dir, 'aaa-result')

# 程序图标路径
app_icon = os.path.join(root_dir, 'src', 'icon.ico')
