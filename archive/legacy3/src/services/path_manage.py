import os
from pathlib import Path
import i18n


def concat_path(*args: str) -> str:
    return str(os.path.normpath(os.path.abspath(os.path.join(*args))))


class PathManage:

    # 以下是静态路径，因为不会变，所以设置为常量

    # 这三个是在 path manager 初始化之前给 i18n 使用的
    ROOT = str(Path(__file__).resolve().parents[2])
    SETTINGS_PATH = concat_path(ROOT, "data", "settings.json")
    LOCALES_DIR = concat_path(ROOT, "src", "resources", "locales")

    # 初始化时，这些路径必须存在
    RESOURCES_DIR = concat_path(ROOT, "src", "resources")
    DATA_DIR = concat_path(ROOT, "data")
    TEMP_DIR = concat_path(DATA_DIR, "temp")
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


    @staticmethod
    def concat(*args: str) -> str:
        """拼接路径并规范化"""
        return concat_path(*args)
    

    @staticmethod
    def validate_windows_filename(v):
        """
        校验合法的 Windows 文件名
        不能包含这些字符 \\ \\/ : * ? " < > |
        """
        if not v or not isinstance(v, str) or not v.strip():
            return False
        # Windows 文件名禁止字符
        invalid_chars = {'\\', '/', ':', '*', '?', '"', '<', '>', '|'}
        if any(c in invalid_chars for c in v):
            return False
        # 禁止保留名称
        reserved_names = {
            'CON', 'PRN', 'AUX', 'NUL',
            'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
            'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
        }
        if v.upper() in reserved_names:
            return False
        return True


    @classmethod
    def init(cls) -> None:

        # 检查静态路径是否存在
        for dir in [cls.RESOURCES_DIR, cls.TEMP_DIR, cls.MODELS_DIR]:
            if not os.path.isdir(dir):
                raise FileNotFoundError(i18n.t("path_manage.critical_error_missing_directory", dir=dir))
        
        for file in [cls.APP_ICON_PATH, cls.CLICK_TEMPLATE_PATH, cls.TEST_H264_PATH, cls.TEST_VP9_PATH,
                     cls.FFMPEG_EXE_PATH, cls.FFPROBE_EXE_PATH,
                     cls.MajdataView_EXE_PATH, cls.MajdataEdit_EXE_PATH]:
            if not os.path.isfile(file):
                raise FileNotFoundError(i18n.t("path_manage.critical_error_missing_file", file=file))

        print("--" + i18n.t("general.notice_init_complete", name="PathManage"))


    @classmethod
    def get_main_output_dir(cls) -> str:
        """获取主输出目录路径"""
        
        # 临时导入 SettingsManager 避免循环依赖
        from .settings_manager import SettingsManager

        main_output_dir_name = SettingsManager.get("main_output_dir_name")
        return concat_path(cls.DATA_DIR, main_output_dir_name)
