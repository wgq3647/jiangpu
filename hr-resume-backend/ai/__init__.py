"""
AI服务模块
提供AI驱动的简历解析和智能匹配能力，支持多提供商
当AI不可用时自动降级到规则引擎
"""
from .config import AIConfig
from .client import ai_client, AIClientError
from .parser import ai_resume_parser
from .matcher import ai_match_engine

__all__ = [
    'AIConfig',
    'ai_client',
    'AIClientError',
    'ai_resume_parser',
    'ai_match_engine',
]
