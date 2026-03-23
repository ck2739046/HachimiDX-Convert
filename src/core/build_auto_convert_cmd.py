import sys

from src.services.path_manage import PathManage
from .schemas.auto_convert_model import AutoConvertModel
from .schemas.auto_convert_config import AutoConvertConfig_Definitions as AC_Defs
from .schemas.auto_convert_config import AutoConvertConfig_Definition

from .schemas.op_result import OpResult, ok, err


def build_auto_convert_cmd(data: AutoConvertModel) -> OpResult[list[str]]:
    """
    主入口: 构建 AutoConvert 命令行参数列表

    输入:
        data (AutoConvertModel)

    输出:
        OpResult[list[str]]: AutoConvert 命令行参数列表
    """

    try:
        # call worker without buffer
        cmd = [sys.executable, "-u", str(PathManage.AUTO_CONVERT_WORKER_PATH)]

        # add common args
        cmd.append(f"--{AC_Defs.is_standardize_enabled.key}")
        cmd.append("true" if data.is_standardize_enabled else "false")
        cmd.append(f"--{AC_Defs.is_detect_enabled.key}")
        cmd.append("true" if data.is_detect_enabled else "false")
        cmd.append(f"--{AC_Defs.is_analyze_enabled.key}")
        cmd.append("true" if data.is_analyze_enabled else "false")

        # add standardize args
        if data.is_standardize_enabled:
            cmd.extend(_parse_fields(data, "standardize"))

        # add detect args
        if data.is_detect_enabled:
            cmd.extend(_parse_fields(data, "detect"))

        # add analyze args
        if data.is_analyze_enabled:
            cmd.extend(_parse_fields(data, "analyze"))

        return ok(cmd)
    
    except Exception as e:
        return err("Unexpected error in build_auto_convert_cmd", e)





def _parse_fields(data: AutoConvertModel, group: str) -> list[str]:
    """
    通用字段解析函数，根据字段定义自动构建命令行参数列表
    """
    args = []

    for definition in vars(AC_Defs).values():
        if not isinstance(definition, AutoConvertConfig_Definition):
            continue

        if definition.group != group:
            continue

        value = getattr(data, definition.key)
        if value is None:
            continue
        
        arg_key = f"--{definition.key}"
        if definition.type == "bool":
            arg_value = "true" if value else "false"
        elif definition.type == "enum":
            arg_value = value.value
        else:
            arg_value = str(value)
        
        args.append(arg_key)
        args.append(arg_value)

    return args
