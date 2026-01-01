# 导入实例
from .i18n_manage import I18nManage
from .path_manage import PathManage
import i18n


class AllServices:

    _is_initialized = False



    @classmethod
    def initialize_all(cls):
        if cls._is_initialized:
            return
        
        print("Initializing all services...")

        I18nManage.init()
        PathManage.init()

        

        print("All services initialized.")
        cls._is_initialized = True



    @classmethod
    def shutdown_all(cls):
        if not cls._is_initialized:
            return
        
        print("Shutting down all services...")

        print("All services shut down.")
        cls._is_initialized = False
