import json
import os
import tempfile
import threading
from typing import Literal, Annotated
from pydantic import BaseModel, Field, field_validator, ValidationError
import i18n
from .path_manage import PathManage
from .validation_manage import ValidationManage

# 创建本地别名，避免每次都写 PathManage.xxx
SETTINGS_PATH = PathManage.SETTINGS_PATH
TEMP_DIR = PathManage.TEMP_DIR
LOCALES_DIR = PathManage.LOCALES_DIR





# 配置模型定义
class SettingsModel(BaseModel):

    # 模型推理相关
    model_backend: Literal["tensorrt", "directml"] = Field(default="tensorrt")
    tensorrt_batch_size: Annotated[int, Field(ge=1, le=8)] = 2
    # FFmpeg 硬件加速相关
    ffmpeg_hw_accel_vp9: Literal["cpu", "nvidia"] = Field(default="cpu")
    ffmpeg_hw_accel_h264: Literal["cpu", "nvidia"] = Field(default="cpu")
    # 应用通用设置
    language: Literal["zh_CN", "en_US"] = Field(default="zh_CN")
    main_output_dir_name: str = Field(default="1-output")
    # 窗口大小
    main_app_init_size: tuple[Annotated[int, Field(ge=500, le=5000)], Annotated[int, Field(ge=500, le=5000)]] = (1300, 900)
    main_app_min_size: tuple[Annotated[int, Field(ge=500, le=5000)], Annotated[int, Field(ge=500, le=5000)]] = (800, 600)

    # 自定义校验逻辑
    @field_validator('main_output_dir_name')
    @classmethod
    def check_filename(cls, v):
        if not PathManage.validate_windows_filename(v):
            raise ValueError(i18n.t('settings_manager.error_invalid_filename', value=v))
        return v






# 管理器实现
class SettingsManager:

    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    

    @classmethod
    def shutdown_instance(cls):
        cls._instance = None


    def __init__(self):
        self._lock = threading.Lock()
        # load_or_create 可能抛出critical error
        # 此处不管，由上游处理
        self._config: SettingsModel = self._load_or_create()
        # 如果运行到这里，说明初始化成功
        print("--" + i18n.t("general.notice_init_complete", name="SettingsManager"))


    def _load_or_create(self) -> SettingsModel:
        """加载配置，如果不存在或损坏则重置"""
        try:
            with self._lock:
                if os.path.isfile(SETTINGS_PATH):
                    # 1. 文件存在：尝试读取并校验
                    try:
                        with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        return SettingsModel(**data)
                    except ValidationError as e:
                        # 提取方便阅读的错误信息
                        formatted_error = ValidationManage.format_validation_error(e)
                        print(i18n.t('settings_manager.warning_load_json_failed', error=formatted_error))
                    except Exception as e:
                        print(i18n.t('settings_manager.warning_load_json_failed', error=str(e)))

                # 2. 文件不存在，或者文件存在但读取或校验失败：创建默认配置
                print(i18n.t('settings_manager.notice_create_new_json', filepath=SETTINGS_PATH))
                if os.path.exists(SETTINGS_PATH):
                    os.remove(SETTINGS_PATH)
                default_model = SettingsModel()
                self._save_to_file(default_model)
                return default_model
        
        except Exception as e:
            # 此处是critical error，直接抛出
            print(i18n.t('settings_manager.critical_error_init_failed'))
            raise
        

    def _save_to_file(self, model: SettingsModel):
        """原子化保存到文件"""
        temp_path = None
        try:
            os.makedirs(TEMP_DIR, exist_ok=True)
            data_json = model.model_dump_json(indent=4)
            
            with tempfile.NamedTemporaryFile(
                mode='w', encoding='utf-8', dir=TEMP_DIR,
                delete=False, suffix='.tmp', prefix='settings_'
            ) as tf:
                tf.write(data_json)
                temp_path = tf.name

            os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
            os.replace(temp_path, SETTINGS_PATH)

        except Exception as e:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
            print(i18n.t('settings_manager.warning_save_json_failed', error=str(e)))
            raise
        

    def reset(self):
        """
        重置配置到默认值：删除配置文件并重新创建
        可能抛出异常，需要上游处理
        """
        with self._lock:
            # 删除现有的配置文件
            if os.path.exists(SETTINGS_PATH):
                os.remove(SETTINGS_PATH)
            # 创建默认配置
            default_model = SettingsModel()
            self._save_to_file(default_model)
            # 更新内存配置
            self._config = default_model


    def get(self, key: str, default=None):
        """获取配置项"""
        with self._lock:
            return getattr(self._config, key, default)


    def set(self, key: str, value):
        """
        设置配置项（带校验和持久化）
        可能抛出异常，需要上游处理
        """
        with self._lock:
            # 获取当前配置的副本
            current_data = self._config.model_dump()
            # 更新副本的值
            current_data[key] = value
            # 尝试创建新模型（触发校验）
            new_config = SettingsModel(**current_data)
            # 校验通过，保存到文件
            self._save_to_file(new_config)
            # 更新内存中的配置
            self._config = new_config
