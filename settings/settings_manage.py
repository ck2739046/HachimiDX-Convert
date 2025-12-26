"""
设置管理器（静态类）
提供统一的设置访问接口
"""

import json
import os
from pathlib import Path
from typing import Any
from pydantic import ValidationError
from threading import Lock

from .persistent_settings import PersistentSettings
from .path_settings import PathSettings


def _initialize_settings() -> tuple[PersistentSettings, PathSettings]:
    """初始化配置（模块加载时执行）"""
    # 获取项目根目录
    root_path = os.path.normpath(os.path.abspath(Path(__file__).parent.parent))
    root = Path(root_path)
    
    # 手动构建 settings.json 路径，避免 PathSettings 的二次初始化
    # settings.json 位于 src/settings.json
    settings_file = root / 'src' / 'settings.json'
    
    # 加载持久化配置
    if settings_file.exists():
        try:
            with open(settings_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            persistent_settings = PersistentSettings(**data)
        except (json.JSONDecodeError, ValidationError) as e:
            # 配置文件损坏，使用默认配置
            print(f"警告: 配置文件损坏，使用默认配置。错误: {e}")
            persistent_settings = PersistentSettings()
    else:
        # 配置文件不存在，使用默认配置并保存
        persistent_settings = PersistentSettings()
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        with open(settings_file, 'w', encoding='utf-8') as f:
            json.dump(
                persistent_settings.model_dump(),
                f,
                ensure_ascii=False,
                indent=2
            )
    
    # 构建路径配置
    path_settings = PathSettings.from_root(root, persistent_settings.main_output_dir_name)
    path_settings.ensure_dirs_exist()
    
    return persistent_settings, path_settings


class SettingsManage:
    """
    设置管理器（静态类）
    负责持久化设置的读写和路径配置的获取
    """
    
    # 模块加载时直接初始化
    _persistent: PersistentSettings
    _path: PathSettings
    _lock = Lock()  # 线程锁，保护写操作
    
    # 初始化配置
    _persistent, _path = _initialize_settings()
    
    @classmethod
    def _save_persistent(cls) -> None:
        """保存持久化设置到文件"""
        settings_file = cls._path.settings_json
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(settings_file, 'w', encoding='utf-8') as f:
            json.dump(
                cls._persistent.model_dump(),
                f,
                ensure_ascii=False,
                indent=2
            )
    
    # ===== Persistent Settings 接口 =====
    
    @classmethod
    def get_persistent_settings(cls, key: str) -> tuple[Any, bool, str, Any]:
        """
        获取持久化配置项
        
        Args:
            key: 配置项名称
        
        Returns:
            (value, success, message, default_value)
            - value: 配置值，失败时为 None
            - success: 是否成功
            - message: 错误信息，成功时为空字符串
            - default_value: 默认值
        """
        default_value = None
        try:
            # 校验 key 是否为有效配置项 (必须在 model_fields 中定义)
            if key not in PersistentSettings.model_fields:
                return None, False, f"配置项 '{key}' 不存在", None

            # 获取默认值
            default_value = PersistentSettings.model_fields[key].default

            value = getattr(cls._persistent, key)
            
            return value, True, "", default_value
            
        except Exception as e:
            return None, False, f"获取配置失败: {str(e)}", default_value
    

    @classmethod
    def set_persistent_settings(cls, key: str, value: Any) -> tuple[bool, str]:
        """
        设置持久化配置项
        
        Args:
            key: 配置项名称
            value: 配置值
        
        Returns:
            (success, message)
            - success: 是否成功
            - message: 成功提示或错误信息
        """
        with cls._lock:  # 加锁保护写操作
            try:
                # 校验 key 是否为有效配置项
                if key not in PersistentSettings.model_fields:
                    return False, f"配置项 '{key}' 不存在"
                
                # 构造新的配置字典
                new_data = cls._persistent.model_dump()
                new_data[key] = value
                
                # 使用 Pydantic 校验
                new_settings = PersistentSettings(**new_data)
                
                # 校验通过，更新缓存并保存
                cls._persistent = new_settings
                cls._save_persistent()
                
                return True, f"配置项 '{key}' 已保存"
                
            except ValidationError as e:
                # 提取第一个错误信息
                error_msg = e.errors()[0]['msg']
                return False, f"参数校验失败: {error_msg}"
                
            except Exception as e:
                return False, f"保存配置失败: {str(e)}"
    

    @classmethod
    def get_all_persistent_setttings(cls) -> dict:
        """获取所有持久化配置"""
        return cls._persistent.model_dump()
    

    # ===== Path Settings 接口 =====
    
    @classmethod
    def get_path(cls, key: str) -> tuple[str | None, bool, str]:
        """
        获取路径配置
        
        Args:
            key: 路径配置项名称
        
        Returns:
            (path_string, success, message)
            - path_string: 路径字符串，失败时为 None
            - success: 是否成功
            - message: 错误信息，成功时为空字符串
        """
        try:
            if not hasattr(cls._path, key):
                return None, False, f"路径配置项 '{key}' 不存在"
            
            path_obj = getattr(cls._path, key)
            # 标准化路径
            path_str = os.path.normpath(os.path.abspath(str(path_obj)))
            
            return path_str, True, ""
            
        except Exception as e:
            return None, False, f"获取路径失败: {str(e)}"
    

    @classmethod
    def get_all_paths(cls) -> dict[str, str]:
        """获取所有路径配置（转换为字符串并标准化）"""
        return {k: os.path.normpath(os.path.abspath(str(v))) for k, v in cls._path.model_dump().items()}
