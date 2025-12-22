import os
import json
import sys
root = os.path.normpath(os.path.abspath(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root not in sys.path: sys.path.insert(0, root)
import tools.path_config

# 配置文件路径


def get_config(key, valid_values=None):
    """
    从配置文件读取指定键的值
    
    Args:
        key: 配置项的键名
        valid_values: 可选的有效值列表，如果提供，会验证读取的值是否在列表中
    
    Returns:
        (value, error_msg, success_msg): 
            - value: 配置项的值，如果出错则为 None
            - error_msg: 错误信息，如果成功则为 None
            - success_msg: 成功信息，如果失败则为 None
    """
    config_file_path = os.path.normpath(os.path.abspath(tools.path_config._config_file))
    
    # 检查配置文件是否存在
    if not os.path.exists(config_file_path):
        return None, "配置文件不存在", None
    
    # 读取配置文件
    try:
        with open(config_file_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
    except json.JSONDecodeError:
        return None, "配置文件格式错误", None
    except Exception as e:
        return None, f"读取配置文件失败: {str(e)}", None
    
    # 检查键是否存在
    if key not in config_data:
        return None, f"配置项 [{key}] 未设置", None
    
    value = config_data[key]
    
    # 如果提供了有效值列表，验证值是否有效
    if valid_values is not None and value not in valid_values:
        return None, f"配置项 [{key}] 的值无效", None
    
    return value, None, f"成功读取配置项 {key} = {value}"


def set_config(key, value):
    """
    将指定键值对写入配置文件
    
    Args:
        key: 配置项的键名
        value: 配置项的值
    
    Returns:
        (error_msg, success_msg): 
            - error_msg: 错误信息，如果成功则为 None
            - success_msg: 成功信息，如果失败则为 None
    """
    config_file_path = os.path.normpath(os.path.abspath(tools.path_config._config_file))
    
    # 如果配置文件不存在，创建空字典
    if os.path.exists(config_file_path):
        try:
            with open(config_file_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
        except json.JSONDecodeError:
            config_data = {}
        except Exception as e:
            return f"读取配置文件失败: {str(e)}", None
    else:
        config_data = {}
        # 确保目录存在
        config_dir = os.path.dirname(config_file_path)
        if not os.path.exists(config_dir):
            try:
                os.makedirs(config_dir)
            except Exception as e:
                return f"创建配置目录失败: {str(e)}", None
    
    # 更新配置
    config_data[key] = value
    
    # 写入配置文件
    try:
        with open(config_file_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"写入配置文件失败: {str(e)}", None
    
    return None, f"成功保存配置项 {key} = {value}"
