from dataclasses import dataclass, field
from typing import Any, Optional, List, Dict, Type
from pydantic import BaseModel, ValidationError
import i18n



@dataclass(slots=True)
class ValidationResult:
    """封装 Pydantic 验证结果的统一结构"""
    success: bool
    data: Optional[BaseModel] = None
    error_msg: str = None

    @property
    def is_valid(self) -> bool:
        return self.success




class ValidationManage:
    """
    统一验证管理服务
    职责：将原始数据转换为合法的 Pydantic 对象，并提供统一的错误反馈结构。
    """

    @staticmethod
    def init():
        print("--" + i18n.t("general.notice_init_complete", name="ValidationManage"))


    @staticmethod
    def format_validation_error(error_input: ValidationError) -> str:
        """
        格式化 Pydantic 验证错误为易读的字符串
        
        Args:
            error_input: Pydantic 验证错误对象（ValidationError）
            
        Returns:
            方便阅读的错误字符串，以 \\n 分隔每条错误
        """
        return '\n'.join(
            f"[{'.'.join(str(loc) for loc in error['loc'])}] {error['msg']}"
            for error in error_input.errors()
        )


    @staticmethod
    def validate(model_class: Type[BaseModel],
                 raw_data: Dict[str, Any],
                 context: Optional[Dict[str, Any]] = None
                ) -> ValidationResult:
        """
        执行验证逻辑
        
        Args:
            model_class: Pydantic 模型类
            raw_data: 待验证的原始字典数据
            context: (可选) 传递给 Pydantic validator 的上下文信息: ValidationInfo.context
        """
        try:
            # 如果 context 为 None，Pydantic 内部会按无上下文处理
            instance = model_class.model_validate(raw_data, context=context)
            return ValidationResult(success=True, data=instance)
        except ValidationError as e:
            # Pydantic 验证错误
            return ValidationResult(success=False, error_msg=ValidationManage.format_validation_error(e))
        except Exception as e:
            # 其他异常
            return ValidationResult(success=False, error_msg=str(e))
