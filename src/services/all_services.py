# 导入实例
from src.core.schemas.op_result import OpResult, ok, err

from .path_manage import PathManage
from .settings_manage import SettingsManage
from .i18n_manage import I18nManage
import i18n


class AllServices:

    _is_initialized = False

    @classmethod
    def initialize_all(cls) -> OpResult[None]:
        if cls._is_initialized:
            return ok()
        
        print("Initializing all services...") # 此时i18n尚未初始化，只能英语


        result = PathManage.init()
        if result.is_ok:
            print("PathManage initialization completed.")
        else:
            return err("Failed to initialize PathManage.", inner=result)

        result = SettingsManage.init()
        if result.is_ok:
            print("SettingsManage initialization completed.")
        else:
            return err("Failed to initialize SettingsManager.", inner=result)
        
        result = I18nManage.init()
        if result.is_ok:
            print("I18nManage initialization completed.")
        else:
            return err("Failed to initialize I18nManage.", inner=result)
        

        print(i18n.t("all_services.notice_all_initialized"))
        cls._is_initialized = True
        return ok()



    @classmethod
    def shutdown_all(cls) -> None:
        if not cls._is_initialized:
            return
        
        print(i18n.t("all_services.notice_shutting_down_all"))

        # 关闭顺序要反着来

        print(i18n.t("all_services.notice_all_shutdown"))
        cls._is_initialized = False
