from pathlib import Path
from src.core.schemas.op_result import OpResult, ok, err


class PathManage:
    """
    所有的路径属性都是 pathlib.Path 对象，而不是字符串。
    """

    # 以下是静态路径，因为不会变，所以设置为常量

    # 初始化时必须存在的路径

    ROOT_DIR: Path = Path(__file__).resolve().parents[2] # 往上三级目录
    DATA_DIR: Path = ROOT_DIR / "data" # 如果为空自动创建
    TEMP_DIR: Path = DATA_DIR / "temp" # 如果为空自动创建
    RESOURCES_DIR: Path = ROOT_DIR / "src" / "resources"
    LOCALES_DIR: Path = RESOURCES_DIR / "locales"
    WORKERS_DIR: Path = ROOT_DIR / "src" / "services" / "workers"

    # 资源文件
    
    APP_ICON_PATH: Path = RESOURCES_DIR / "icon.ico"
    CLICK_TEMPLATE_PATH: Path = RESOURCES_DIR / "click_template.aac"
    TEST_H264_PATH: Path = RESOURCES_DIR / "test_h264.mp4"
    TEST_VP9_PATH: Path = RESOURCES_DIR / "test_vp9.webm"

    FFMPEG_EXE_PATH: Path = RESOURCES_DIR / "ffmpeg" / "bin" / "ffmpeg.exe"
    FFPROBE_EXE_PATH: Path = RESOURCES_DIR / "ffmpeg" / "bin" / "ffprobe.exe"

    MajdataView_EXE_PATH: Path = RESOURCES_DIR / "majdata" / "MajdataView.exe"
    MajdataEdit_EXE_PATH: Path = RESOURCES_DIR / "majdata" / "MajdataEdit.exe"

    MODELS_DIR: Path = RESOURCES_DIR / "models"
    DETECT_PT_PATH: Path = MODELS_DIR / "detect.pt"
    OBB_PT_PATH: Path = MODELS_DIR / "obb.pt"
    CLS_BREAK_PT_PATH: Path = MODELS_DIR / "cls-break.pt"
    CLS_EX_PT_PATH: Path = MODELS_DIR / "cls-ex.pt"

    # worker 脚本

    AUTO_CONVERT_WORKER_PATH: Path = WORKERS_DIR / "auto_convert_worker.py"



    # 初始化时可以不存在的路径

    SETTINGS_PATH: Path = DATA_DIR / "settings.json"

    MajdataEdit_CONTROL_TXT_PATH: Path = RESOURCES_DIR / "majdata" / "HachimiDX_MajdataEdit_Control.txt"

    DETECT_ENGINE_PATH: Path = MODELS_DIR / "detect.engine"
    OBB_ENGINE_PATH: Path = MODELS_DIR / "obb.engine"
    CLS_BREAK_ENGINE_PATH: Path = MODELS_DIR / "cls-break.engine"
    CLS_EX_ENGINE_PATH: Path = MODELS_DIR / "cls-ex.engine"

    DETECT_ONNX_PATH: Path = MODELS_DIR / "detect_a.onnx"
    OBB_ONNX_PATH: Path = MODELS_DIR / "obb_a.onnx"
    CLS_BREAK_ONNX_PATH: Path = MODELS_DIR / "cls-break_a.onnx"
    CLS_EX_ONNX_PATH: Path = MODELS_DIR / "cls-ex_a.onnx"

    TEMP_DETECT_ONNX_PATH: Path = MODELS_DIR / "detect.onnx"
    TEMP_OBB_ONNX_PATH: Path = MODELS_DIR / "obb.onnx"
    TEMP_CLS_BREAK_ONNX_PATH: Path = MODELS_DIR / "cls-break.onnx"
    TEMP_CLS_EX_ONNX_PATH: Path = MODELS_DIR / "cls-ex.onnx"



    @classmethod
    def init(cls) -> OpResult[None]:
        """初始化检查一些必须存在的路径"""
        
        # 检查必须存在的目录
        for dir_path in [cls.RESOURCES_DIR, cls.MODELS_DIR, cls.LOCALES_DIR, cls.WORKERS_DIR]:
            if not dir_path.is_dir():
                error_msg = f"Critical Error: Required directory not found: {dir_path}"
                return err(error_msg)
        
        # 创建可自动创建的目录
        for dir_path in [cls.DATA_DIR, cls.TEMP_DIR]:
            if not dir_path.is_dir():
                dir_path.mkdir(parents=True, exist_ok=True)
        
        # 检查资源文件是否存在
        for file_path in [cls.APP_ICON_PATH, cls.CLICK_TEMPLATE_PATH,
                          cls.TEST_H264_PATH, cls.TEST_VP9_PATH,
                          cls.FFMPEG_EXE_PATH, cls.FFPROBE_EXE_PATH,
                          cls.MajdataView_EXE_PATH, cls.MajdataEdit_EXE_PATH,
                          cls.DETECT_PT_PATH, cls.OBB_PT_PATH,
                          cls.CLS_BREAK_PT_PATH, cls.CLS_EX_PT_PATH]:
            if not file_path.is_file():
                error_msg = f"Critical Error: Required file not found: {file_path}"
                return err(error_msg)
            
        # 检查 worker 是否存在
        for file_path in [cls.AUTO_CONVERT_WORKER_PATH]:
            if not file_path.is_file():
                error_msg = f"Critical Error: Required worker script not found: {file_path}"
                return err(error_msg)

        return ok()



    @classmethod
    def get_main_output_dir(cls) -> OpResult[Path]:
        """获取主输出目录路径"""
        
        # 临时导入 SettingsManager 避免循环依赖
        from .settings_manage import SettingsManage

        result = SettingsManage.get("main_output_dir_name")
        if result.is_ok:
            return ok(cls.DATA_DIR / result.value)
        else:
            error_msg = f"Failed to get main output directory name from settings"
            return err(error_msg, inner=result)


    @classmethod
    def _module_to_path(cls, module) -> Path:
        return cls.ROOT_DIR / f"{module.replace('.', '/')}.py"
