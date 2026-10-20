"""
AI服务配置
支持多种AI提供商：豆包(Doubao)、千问(Qwen)、GPT(OpenAI)等
所有提供商均兼容OpenAI API格式
"""
import os
from typing import Optional


class AIConfig:
    """AI服务配置"""

    # AI提供商选择：doubao / qwen / openai / custom
    PROVIDER = os.getenv("AI_PROVIDER", "doubao")

    # 是否启用AI（关闭时使用规则引擎降级）
    ENABLED = os.getenv("AI_ENABLED", "true").lower() == "true"

    # ========== 各提供商配置 ==========

    # 豆包（字节跳动）- https://www.volcengine.com/product/doubao
    DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY", "")
    DOUBAO_BASE_URL = os.getenv("DOUBAO_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
    DOUBAO_MODEL = os.getenv("DOUBAO_MODEL", "doubao-1-5-pro-32k-250115")

    # 千问（阿里通义千问）- https://dashscope.aliyun.com/
    QWEN_API_KEY = os.getenv("QWEN_API_KEY", "")
    QWEN_BASE_URL = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen-plus")

    # OpenAI / GPT
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # 自定义（兼容OpenAI格式）
    CUSTOM_API_KEY = os.getenv("CUSTOM_API_KEY", "")
    CUSTOM_BASE_URL = os.getenv("CUSTOM_BASE_URL", "")
    CUSTOM_MODEL = os.getenv("CUSTOM_MODEL", "")

    # ========== 通用配置 ==========
    TEMPERATURE = float(os.getenv("AI_TEMPERATURE", "0.1"))  # 解析任务用低温度保证稳定性
    MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "4096"))
    TIMEOUT = int(os.getenv("AI_TIMEOUT", "60"))  # 秒
    MAX_RETRIES = int(os.getenv("AI_MAX_RETRIES", "2"))

    @classmethod
    def get_provider_config(cls) -> dict:
        """获取当前选中的提供商配置"""
        configs = {
            "doubao": {
                "api_key": cls.DOUBAO_API_KEY,
                "base_url": cls.DOUBAO_BASE_URL,
                "model": cls.DOUBAO_MODEL,
                "name": "豆包(Doubao)"
            },
            "qwen": {
                "api_key": cls.QWEN_API_KEY,
                "base_url": cls.QWEN_BASE_URL,
                "model": cls.QWEN_MODEL,
                "name": "千问(Qwen)"
            },
            "openai": {
                "api_key": cls.OPENAI_API_KEY,
                "base_url": cls.OPENAI_BASE_URL,
                "model": cls.OPENAI_MODEL,
                "name": "GPT(OpenAI)"
            },
            "custom": {
                "api_key": cls.CUSTOM_API_KEY,
                "base_url": cls.CUSTOM_BASE_URL,
                "model": cls.CUSTOM_MODEL,
                "name": "自定义"
            }
        }
        return configs.get(cls.PROVIDER, configs["doubao"])

    @classmethod
    def is_configured(cls) -> bool:
        """检查AI是否已配置API Key"""
        if not cls.ENABLED:
            return False
        config = cls.get_provider_config()
        return bool(config["api_key"]) and bool(config["base_url"])

    @classmethod
    def load_from_db(cls, db_session=None):
        """从数据库热加载配置，覆盖环境变量默认值
        每次AI调用前调用此方法即可实现热更新，无需重启服务
        """
        if db_session is None:
            return
        try:
            from models import SystemConfig
            configs = db_session.query(SystemConfig).all()
            config_map = {c.config_key: c.config_value for c in configs}

            # 通用配置
            if "ai_enabled" in config_map:
                cls.ENABLED = str(config_map.get("ai_enabled", "true")).lower() == "true"
            if "ai_provider" in config_map:
                cls.PROVIDER = config_map.get("ai_provider", "doubao")

            # 各提供商配置
            provider_keys = ["doubao", "qwen", "openai", "custom"]
            for provider in provider_keys:
                key_attr = f"{provider.upper()}_API_KEY"
                url_attr = f"{provider.upper()}_BASE_URL"
                model_attr = f"{provider.upper()}_MODEL"
                if f"{provider}_api_key" in config_map:
                    setattr(cls, key_attr, config_map.get(f"{provider}_api_key", ""))
                if f"{provider}_base_url" in config_map:
                    setattr(cls, url_attr, config_map.get(f"{provider}_base_url", ""))
                if f"{provider}_model" in config_map:
                    setattr(cls, model_attr, config_map.get(f"{provider}_model", ""))

            # 通用参数
            if "ai_temperature" in config_map:
                try:
                    cls.TEMPERATURE = float(config_map.get("ai_temperature", "0.1"))
                except (ValueError, TypeError):
                    pass
            if "ai_max_tokens" in config_map:
                try:
                    cls.MAX_TOKENS = int(config_map.get("ai_max_tokens", "4096"))
                except (ValueError, TypeError):
                    pass
            if "ai_timeout" in config_map:
                try:
                    cls.TIMEOUT = int(config_map.get("ai_timeout", "60"))
                except (ValueError, TypeError):
                    pass
            if "ai_max_retries" in config_map:
                try:
                    cls.MAX_RETRIES = int(config_map.get("ai_max_retries", "2"))
                except (ValueError, TypeError):
                    pass
        except Exception as e:
            # 热加载失败不影响服务，继续使用默认配置
            import logging
            logging.getLogger(__name__).warning(f"AI配置热加载失败: {e}")
