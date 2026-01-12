import inspect
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Optional, TypeVar, Generic

T = TypeVar('T') # 带泛型是为了让 data 有类型提示


@dataclass(slots=True)
class OpResult(Generic[T]):
    """
    全局结果对象，类似 rust 的 Result 类型。
    该对象用于表示操作的成功或失败状态，并携带相应的数据或错误信息。

    Attributes:
        is_ok (bool)
        source (str): 来源 "文件名: 函数名"
        value (Optional[T]): 成功时返回的数据（泛型）
        error_msg (str): 错误信息（面向用户/日志）
        error_raw (any): 原始错误信息（存放 Exception, 字符串, 状态码等）
        inner (Optional['OpResult[Any]']): 内部嵌套的 OpResult
    """

    # 通用
    is_ok: bool
    source: str = ""
    # 成功
    value: Optional[T] = None
    # 错误
    error_msg: str = ""
    error_raw: Any = None
    inner: Optional['OpResult[Any]'] = None


    
def _get_caller_context() -> str:
    """
    返回str 文件名: 函数名
    """
    try:
        # stack[0] 是 _get_caller_context
        # stack[1] 是 ok() 或 err()
        # stack[2] 是业务函数
        frame = inspect.stack()[2]
        
        # frame.filename 是全路径，只取文件名，比如 'logic.py'
        filename = Path(frame.filename).name
        func_name = frame.function
        
        return f"{filename}: {func_name}()"
    except Exception:
        return "unknown:unknown"



def ok(value: Optional[T] = None) -> OpResult[T]:
    """
    创建一个表示成功的 Result 对象。

    Args:
        value (Optional[T]): 成功时返回的数据

    Returns:
        OpResult[T]: 表示成功的 Result 对象
    """
    return OpResult(
        is_ok=True, 
        source=_get_caller_context(),
        value=value
    )



def err(error_msg: str = "", 
        error_raw: Any = None, 
        inner: Optional[OpResult[Any]] = None) -> OpResult[Any]:
    """
    创建一个表示失败的 Result 对象。

    Args:
        error_msg (str): 错误信息（面向用户/日志）
        error_raw (any): 原始错误信息（存放 Exception, 字符串, 状态码等）
        inner (Optional[OpResult[Any]]): 内部嵌套的 OpResult

    Returns:
        OpResult[Any]: 表示失败的 Result 对象
    """
    return OpResult(
        is_ok=False,
        source=_get_caller_context(),
        error_msg=error_msg,
        error_raw=error_raw,
        inner=inner
    )



def print_op_result(result: OpResult[Any]) -> None:
    """
    打印 OpResult 对象的详细信息。
    如果有嵌套的 inner result，会递归打印。

    Args:
        result (OpResult[Any]): 要打印的 OpResult 对象
    """
    
    def _print_recursive(res: OpResult[Any], level: int):
        # 定义缩进，每一层增加 2 个空格
        indent = " " * 2 * level
        
        # 视觉分割线，显示层级和简要状态
        status_icon = "✓" if res.is_ok else "✗"
        print(f"{indent}{status_icon} [OpResult Level {level}]")
        
        # 打印基础属性
        print(f"{indent}    - source   : {res.source}")
        print(f"{indent}    - is_ok    : {res.is_ok}")
        
        # 根据状态打印更有意义的数据，但为了满足“打印每一个参数”，这里全部打印
        print(f"{indent}    - value    : {res.value}")
        print(f"{indent}    - error_msg: {res.error_msg}")
        print(f"{indent}    - error_raw: {res.error_raw}")
        
        # 处理嵌套逻辑
        if res.inner:
            print(f"{indent}    - inner    : (Nested below)\n")
            _print_recursive(res.inner, level + 1)
        else:
            print(f"{indent}    - inner    : None")
            
    # 开始打印，初始层级为 0
    _print_recursive(result, 0)
