"""
任务配置基类
所有任务配置都应继承此类
"""

import uuid

from pydantic import BaseModel, Field


class BaseTaskConfig(BaseModel):
    """
    任务配置基类
    提供所有任务通用的字段
    """

    task_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="任务唯一标识符"
    )

    class Config:
        # 禁止未定义的字段
        extra = "forbid"
        # 赋值时也进行校验
        validate_assignment = True
        # 允许任意类型（如 datetime）
        arbitrary_types_allowed = True
