"""
任务配置基类
所有任务配置都应继承此类
"""

from pydantic import BaseModel, Field
from datetime import datetime
import uuid


class BaseTaskConfig(BaseModel):
    """
    任务配置基类
    提供所有任务通用的字段
    """
    
    task_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="任务唯一标识符"
    )
    
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="任务创建时间"
    )
    
    class Config:
        # 禁止未定义的字段
        extra = "forbid"
        # 赋值时也进行校验
        validate_assignment = True
        # 允许任意类型（如 datetime）
        arbitrary_types_allowed = True
