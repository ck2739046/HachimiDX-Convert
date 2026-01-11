import inspect
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Optional, TypeVar, Generic

T = TypeVar('T') # 带泛型是为了让 data 有类型提示


@dataclass
class OpResult(Generic[T]):
    """
    全局结果对象，类似 rust 的 Result 类型。
    该对象用于表示操作的成功或失败状态，并携带相应的数据或错误信息。

    Attributes:
        is_ok (bool)
        source (str): 来源 "文件名: 函数名"
        data (Optional[T]): 成功时返回的数据（泛型）
        error_msg (str): 错误信息（面向用户/日志）
        error_raw (any): 原始错误信息（存放 Exception, 字符串, 状态码等）
        inner (Optional['OpResult[Any]']): 内部嵌套的 OpResult
    """

    # 通用
    is_ok: bool
    source: str = ""
    # 成功
    data: Optional[T] = None
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
        
        return f"{filename}: {func_name}"
    except Exception:
        return "unknown:unknown"



def ok(data: Optional[T] = None) -> OpResult[T]:
    """
    创建一个表示成功的 Result 对象。

    Args:
        data (Optional[T]): 成功时返回的数据

    Returns:
        OpResult[T]: 表示成功的 Result 对象
    """
    return OpResult(
        is_ok=True, 
        source=_get_caller_context(),
        data=data
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
