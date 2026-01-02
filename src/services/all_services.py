# 导入实例
from .i18n_manage import I18nManage
from .path_manage import PathManage
from .settings_manager import SettingsManager
# from .validation_manage import ValidationManage
import i18n


class AllServices:

    _is_initialized = False



    @classmethod
    def initialize_all(cls):
        if cls._is_initialized:
            return
        
        print("Initializing all services...") # 此时i18n尚未初始化，只能英语

        I18nManage.init()
        PathManage.init()
        SettingsManager.get_instance()
        # ValidationManage.init()

        print(i18n.t("all_services.notice_all_initialized"))
        cls._is_initialized = True



    @classmethod
    def shutdown_all(cls):
        if not cls._is_initialized:
            return
        
        print(i18n.t("all_services.notice_shutting_down_all"))

        SettingsManager.shutdown_instance()

        print(i18n.t("all_services.notice_all_shutdown"))
        cls._is_initialized = False
