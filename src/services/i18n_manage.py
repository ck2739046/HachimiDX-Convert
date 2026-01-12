import json
import os

from src.core.schemas.op_result import OpResult, ok, err
from .path_manage import PathManage
from .settings_manage import SettingsManage
import i18n

SETTINGS_PATH = PathManage.SETTINGS_PATH
LOCALES_DIR = PathManage.LOCALES_DIR


class I18nManage:

    @staticmethod
    def init() -> OpResult[None]:

        fallback_language = 'en_US'
        
        # 从 settings 获取语言设置
        result = SettingsManage.get("language")
        if result.is_ok:
            language = result.value
        else:
            print(f"--Warning: I18nInit: Failed to get language setting from configuration, using fallback '{fallback_language}'.")
            language = fallback_language

        # 检查语言文件是否存在
        fallback_file = os.path.join(LOCALES_DIR, f'{fallback_language}.yaml')
        selected_file = os.path.join(LOCALES_DIR, f'{language}.yaml')

        if language != fallback_language:
            if not os.path.isfile(selected_file):
                print(f"--Warning: I18nInit: Language file for '{language}' not found, falling back to '{fallback_language}'.")
        
        if not os.path.isfile(fallback_file):
            return err(f"Critical Error: I18nInit: Fallback language file not found: '{fallback_file}'.")

        # 初始化 i18n 模块
        i18n.load_path.append(LOCALES_DIR)
        i18n.set('filename_format', '{locale}.yaml')
        i18n.set('locale', language)
        i18n.set('fallback', 'en_US') # fallback

        return ok()
