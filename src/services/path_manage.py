import os
from pathlib import Path
import i18n


def concat_path(*args: str) -> str:
    return str(os.path.normpath(os.path.abspath(os.path.join(*args))))


# 以下是静态路径，因为不会变，所以设置为常量

# 这三个是在 path manager 初始化之前给 i18n 使用的
ROOT = str(Path(__file__).resolve().parents[2])
SETTINGS_PATH = concat_path(ROOT, "data", "settings.json")
LOCALES_DIR = concat_path(ROOT, "src", "resources", "locales")

# 初始化时，这些路径必须存在
RESOURCES_DIR = concat_path(ROOT, "src", "resources")
TEMP_DIR = concat_path(ROOT, "data", "temp")
MODELS_DIR = concat_path(RESOURCES_DIR, "models")

APP_ICON_PATH = concat_path(RESOURCES_DIR, "icon.ico")
CLICK_TEMPLATE_PATH = concat_path(RESOURCES_DIR, "click_template.aac")
TEST_H264_PATH = concat_path(RESOURCES_DIR, "test_h264.mp4")
TEST_VP9_PATH = concat_path(RESOURCES_DIR, "test_vp9.webm")

FFMPEG_EXE_PATH = concat_path(RESOURCES_DIR, "ffmpeg-8.0-essentials_build", "bin", "ffmpeg.exe")
FFPROBE_EXE_PATH = concat_path(RESOURCES_DIR, "ffmpeg-8.0-essentials_build", "bin", "ffprobe.exe")

MajdataView_EXE_PATH = concat_path(RESOURCES_DIR, "Majdata", "MajdataView.exe")
MajdataEdit_EXE_PATH = concat_path(RESOURCES_DIR, "Majdata", "MajdataEdit.exe")

# 初始化时，这些路径可以不存在
MajdataEdit_CONTROL_TXT_PATH = concat_path(RESOURCES_DIR, "Majdata", "HachimiDX_MajdataEdit_Control.txt")

DETECT_PT_PATH = concat_path(MODELS_DIR, "detect.pt")
DETECT_ONNX_PATH = concat_path(MODELS_DIR, "detect.onnx")
DETECT_ENGINE_PATH = concat_path(MODELS_DIR, "detect.engine")
OBB_PT_PATH = concat_path(MODELS_DIR, "obb.pt")
OBB_ONNX_PATH = concat_path(MODELS_DIR, "obb.onnx")
CLS_BREAK_PT_PATH = concat_path(MODELS_DIR, "cls-break.pt")
CLS_BREAK_ONNX_PATH = concat_path(MODELS_DIR, "cls-break.onnx")
CLS_EX_PT_PATH = concat_path(MODELS_DIR, "cls-ex.pt")
CLS_EX_ONNX_PATH = concat_path(MODELS_DIR, "cls-ex.onnx")




class PathManage:

    @staticmethod
    def init() -> None:

        # 检查静态路径是否存在
        for dir in [RESOURCES_DIR, TEMP_DIR, MODELS_DIR]:
            if not os.path.isdir(dir):
                raise FileNotFoundError(i18n.t("path_manage.error_missing_directory", dir=dir))
        
        for file in [APP_ICON_PATH, CLICK_TEMPLATE_PATH, TEST_H264_PATH, TEST_VP9_PATH,
                     FFMPEG_EXE_PATH, FFPROBE_EXE_PATH,
                     MajdataView_EXE_PATH, MajdataEdit_EXE_PATH]:
            if not os.path.isfile(file):
                raise FileNotFoundError(i18n.t("path_manage.error_missing_file", file=file))

        print("--" + i18n.t("general.init_complete", name="PathManage"))
