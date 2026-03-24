import sys

from src.services.path_manage import PathManage
from src.services.settings_manage import SettingsManage

from .schemas.auto_convert_model import AutoConvertModel
from .schemas.auto_convert_config import AutoConvertConfig_Definitions as AC_Defs
from .schemas.auto_convert_config import AutoConvertConfig_Definition
from .schemas.op_result import OpResult, ok, err
from .schemas.settings_config import SettingsConfig_Definitions as SC_Defs
from .tools.run_worker import build_cmd_head_python_exe


def build_auto_convert_cmd(data: AutoConvertModel) -> OpResult[list[str]]:
    """
    主入口: 构建 AutoConvert 命令行参数列表

    输入:
        data (AutoConvertModel)

    输出:
        OpResult[list[str]]: AutoConvert 命令行参数列表
    """

    try:
        cmd = build_cmd_head_python_exe(PathManage.AUTO_CONVERT_WORKER_PATH)

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

            # 增加一些额外的参数
            res = _get_detect_args_from_settings()
            if not res.is_ok:
                return err("Failed to get detect args from settings", inner=res)
            cmd.extend(res.value)
            # 增加模型路径
            res = _get_detect_model_paths()
            if not res.is_ok:
                return err("Failed to get model paths", inner=res)
            cmd.extend(res.value)



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






def _get_detect_args_from_settings() -> OpResult[list]:
                
    cmd = []

    res = SettingsManage.get(SC_Defs.inference_device.key)
    if not res.is_ok:
        return err(f"Failed to get {SC_Defs.inference_device.key} from settings", inner=res)
    cmd.append(f"--{SC_Defs.inference_device.key}")
    cmd.append(str(res.value))

    res = SettingsManage.get(SC_Defs.predict_batch_size_detect_obb.key)
    if not res.is_ok:
        return err(f"Failed to get {SC_Defs.predict_batch_size_detect_obb.key} from settings", inner=res)
    cmd.append(f"--{SC_Defs.predict_batch_size_detect_obb.key}")
    cmd.append(str(res.value))

    res = SettingsManage.get(SC_Defs.predict_batch_size_classify.key)
    if not res.is_ok:
        return err(f"Failed to get {SC_Defs.predict_batch_size_classify.key} from settings", inner=res)
    cmd.append(f"--{SC_Defs.predict_batch_size_classify.key}")
    cmd.append(str(res.value))

    return ok(cmd)





def _get_detect_model_paths() -> OpResult[list]:

    cmd = []

    res = SettingsManage.get(SC_Defs.model_backend.key)
    if not res.is_ok:
        return err(f"Failed to get {SC_Defs.model_backend.key} from settings", inner=res)
    model_backend = res.value

    res = SC_Defs.get_path_by_backend(model_backend)
    if not res.is_ok:
        return err(f"Failed to get model paths for backend: {model_backend}", inner=res)
    paths = res.value

    cmd.append(f"--detect_model_path")
    cmd.append(str(paths[0]))
    cmd.append(f"--obb_model_path")
    cmd.append(str(paths[1]))
    cmd.append(f"--cls_break_model_path")
    cmd.append(str(paths[2]))
    cmd.append(f"--cls_ex_model_path")
    cmd.append(str(paths[3]))

    return ok(cmd)
