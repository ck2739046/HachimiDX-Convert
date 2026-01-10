import json
import os
from .path_manage import PathManage
import i18n

SETTINGS_PATH = PathManage.SETTINGS_PATH
LOCALES_DIR = PathManage.LOCALES_DIR

class I18nManage:

    @staticmethod
    def init() -> None:

        fallback_language = 'en_US'
        
        # 从 settings 获取语言设置
        # 此时 SettingsManager 尚未初始化，直接读取 settings.json 文件
        settings_path = SETTINGS_PATH
        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                settings_data = json.load(f)
                language = settings_data.get("language", fallback_language)
        except Exception as e:
            print(f"--Warning: I18nInit: Failed to get language setting from settings.json, defaulting to '{fallback_language}'. Error: {e}")
            language = fallback_language

        # 检查语言文件是否存在
        fallback_file = os.path.join(LOCALES_DIR, f'{fallback_language}.yaml')
        selected_file = os.path.join(LOCALES_DIR, f'{language}.yaml')

        if language != fallback_language:
            if not os.path.isfile(selected_file):
                print(f"--Warning: I18nInit: Language file for '{language}' not found, falling back to '{fallback_language}'.")
        
        if not os.path.isfile(fallback_file):
            raise Exception(f"Critical Error: I18nInit: Fallback language file not found: '{fallback_file}'.")

        # 初始化 i18n 模块
        i18n.load_path.append(LOCALES_DIR)
        i18n.set('filename_format', '{locale}.yaml')
        i18n.set('locale', language)
        i18n.set('fallback', 'en_US') # fallback

        print("--" + i18n.t("general.notice_init_complete", name="I18nManage"))
