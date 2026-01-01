# 导入实例
from .i18n_init import I18nInit


class AllServices:

    _is_initialized = False



    @classmethod
    def initialize_all(cls):
        if cls._is_initialized:
            return
        
        print("Initializing all services...")

        # xxx.get_instance()
        I18nInit.init()

        print("All services initialized.")
        cls._is_initialized = True



    @classmethod
    def shutdown_all(cls):
        if not cls._is_initialized:
            return
        
        print("Shutting down all services...")

        # xxx.shutdown_instance()

        print("All services shut down.")
        cls._is_initialized = False
