from .all_services import AllServices

# from .i18n_manage import I18nManage
from .path_manage import PathManage
from .settings_manage import SettingsManage
from .majdata_session import MajdataSession

from .pipeline import MediaPipeline

# 暴露接口模块作为命名空间，以区分同名函数（如 cancel, get_signals）
from . import process_manager_api
from . import task_scheduler_api

__all__ = [
    "AllServices",
    # "I18nManage",
    "PathManage",
    "SettingsManage",
    "MajdataSession",

    "MediaPipeline",

    "process_manager_api",
    "task_scheduler_api",
]
