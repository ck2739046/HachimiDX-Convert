"""
多语言管理器（静态类）
提供文本获取和语言切换功能
"""

import json
import os
from pathlib import Path
from threading import Lock
from typing import Any
from ..settings_manage import SettingsManage


def _initialize_locale() -> tuple[dict, str]:
    """
    初始化多语言系统（模块加载时执行）
    
    Returns:
        (texts_dict, language_code)
    """
    # 获取语言设置
    try:
        lang, success, _ = SettingsManage.get_persistent_settings('language')
        if not success:
            lang = 'zh-cn'
    except Exception:
        lang = 'zh-cn'
    
    # 加载对应的 JSON 文件
    locale_dir = Path(__file__).parent
    json_file = locale_dir / f"{lang.replace('-', '_')}.json"
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            texts = json.load(f)
        return texts, lang
    except Exception as e:
        # 文件不存在或损坏
        print(f"错误: 无法加载默认语言文件，错误: {e}")
        return {}, 'zh-cn'


class LocaleManage:
    """
    多语言管理器（静态类）
    负责文本获取和语言切换
    """
    
    # 模块加载时直接初始化
    _texts: dict
    _current_lang: str
    _lock = Lock()  # 线程锁，保护语言切换操作
    
    # 初始化
    _texts, _current_lang = _initialize_locale()
    
    
    @classmethod
    def get(cls, key: str, **kwargs) -> str:
        """
        获取文本（支持参数化模板）
        
        Args:
            key: 文本键，支持点号分隔（如 "messages.task_completed"）
            **kwargs: 模板参数
        
        Returns:
            格式化后的文本字符串
            
        Examples:
            >>> LocaleManage.get("common.confirm")
            "确认"
            
            >>> LocaleManage.get("messages.progress", current=5, total=10, percentage=50)
            "进度：5/10 (50%)"
        """
        # 解析点号分隔的键路径
        keys = key.split('.')
        value = cls._texts
        
        try:
            # 逐级访问嵌套字典
            for k in keys:
                value = value[k]
            
            # 如果值不是字符串，返回键名
            if not isinstance(value, str):
                return f"[!] {key}"
            
            # 如果有参数，进行模板替换
            if kwargs:
                try:
                    return value.format(**kwargs)
                except KeyError:
                    # 参数缺失，返回原始模板
                    return value
            
            return value
            
        except (KeyError, TypeError):
            # 键不存在
            return f"[!] {key}"
