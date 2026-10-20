"""
AI客户端 - 统一的大模型调用接口
兼容OpenAI Chat Completions API格式
支持豆包、千问、GPT等多种提供商
"""
import json
import time
import logging
from typing import List, Dict, Optional, Any
import requests

from .config import AIConfig

logger = logging.getLogger(__name__)


class AIClientError(Exception):
    """AI调用异常"""
    pass


class AIClient:
    """
    统一AI客户端
    所有提供商均使用OpenAI兼容的Chat Completions API
    """

    def __init__(self):
        self.config = AIConfig.get_provider_config()
        self.api_key = self.config["api_key"]
        self.base_url = self.config["base_url"].rstrip("/")
        self.model = self.config["model"]
        self.provider_name = self.config["name"]
        self.timeout = AIConfig.TIMEOUT
        self.max_retries = AIConfig.MAX_RETRIES

    def is_available(self) -> bool:
        """检查AI服务是否可用"""
        return AIConfig.is_configured()

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict] = None,
    ) -> str:
        """
        调用AI对话接口
        Args:
            messages: 对话消息列表 [{"role": "system/user/assistant", "content": "..."}]
            temperature: 温度（0-2），越低越稳定
            max_tokens: 最大生成token数
            response_format: 响应格式，如 {"type": "json_object"}
        Returns:
            AI生成的文本内容
        """
        if not self.is_available():
            raise AIClientError(f"AI服务未配置（提供商：{self.provider_name}），请配置API Key")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else AIConfig.TEMPERATURE,
            "max_tokens": max_tokens or AIConfig.MAX_TOKENS,
        }

        # JSON模式（部分提供商支持）
        if response_format:
            payload["response_format"] = response_format

        # 带重试的调用
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout
                )

                if response.status_code == 429:
                    # 限流，退避重试
                    wait_time = 2 ** attempt
                    logger.warning(f"AI限流，等待{wait_time}秒后重试（第{attempt+1}次）")
                    time.sleep(wait_time)
                    continue

                if response.status_code != 200:
                    error_msg = f"AI调用失败 HTTP {response.status_code}: {response.text[:500]}"
                    logger.error(error_msg)
                    if attempt < self.max_retries:
                        time.sleep(1)
                        continue
                    raise AIClientError(error_msg)

                result = response.json()
                content = result["choices"][0]["message"]["content"]
                return content

            except requests.exceptions.Timeout:
                last_error = f"AI调用超时（{self.timeout}秒）"
                logger.warning(f"{last_error}，第{attempt+1}次尝试")
                if attempt < self.max_retries:
                    time.sleep(2)
                    continue
            except requests.exceptions.RequestException as e:
                last_error = f"AI网络请求异常: {str(e)}"
                logger.error(last_error)
                if attempt < self.max_retries:
                    time.sleep(1)
                    continue
            except (KeyError, IndexError, json.JSONDecodeError) as e:
                last_error = f"AI响应解析失败: {str(e)}"
                logger.error(last_error)
                if attempt < self.max_retries:
                    time.sleep(1)
                    continue

        raise AIClientError(last_error or "AI调用失败")

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        调用AI并解析JSON响应
        自动在prompt中要求返回JSON，并做容错解析
        """
        # 在最后一条用户消息后追加JSON格式要求
        if messages and messages[-1]["role"] == "user":
            messages[-1]["content"] += "\n\n请严格以JSON格式返回结果，不要包含任何解释性文字。"

        content = self.chat(messages, temperature, max_tokens)

        # 容错解析JSON
        try:
            # 直接解析
            return json.loads(content)
        except json.JSONDecodeError:
            # 尝试提取```json ... ```包裹的内容
            json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', content, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass
            # 尝试提取第一个{到最后一个}
            brace_start = content.find('{')
            brace_end = content.rfind('}')
            if brace_start >= 0 and brace_end > brace_start:
                try:
                    return json.loads(content[brace_start:brace_end + 1])
                except json.JSONDecodeError:
                    pass

            logger.error(f"AI返回的JSON解析失败，原始内容: {content[:500]}")
            raise AIClientError(f"AI返回的JSON格式解析失败: {content[:200]}")


import re  # 放在文件末尾避免影响

# 全局单例
ai_client = AIClient()
