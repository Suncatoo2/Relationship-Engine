"""Provider Interface - LLM 调用抽象层

Relationship Engine 不绑定任何具体 LLM。
通过 Provider Interface 调用，默认接入 CC Switch。
任何 LLM（DeepSeek、Claude、GPT、Qwen）都可以通过 CC Switch 统一调用。
"""

import os
import json
from abc import ABC, abstractmethod
from typing import Optional


class LLMProvider(ABC):
    """LLM 提供者抽象接口"""

    @abstractmethod
    def chat(self, system_prompt: str, messages: list[dict],
             temperature: float = 0.7, max_tokens: int = 1000) -> str:
        """发送对话请求，返回回复文本"""
        ...

    @abstractmethod
    def name(self) -> str:
        """提供者名称"""
        ...


class CCSwitchProvider(LLMProvider):
    """CC Switch 默认提供者

    CC Switch 是一个 LLM 网关/代理，统一接入多家模型。
    只需配置 CC_SWITCH_BASE_URL 和 CC_SWITCH_API_KEY，
    就可以通过它调用 DeepSeek、Claude、GPT、Qwen 等任何模型。
    """

    def __init__(self, base_url: str, api_key: str, model: str = "deepseek-chat"):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model

    def name(self) -> str:
        return f"CCSwitch({self._model})"

    def chat(self, system_prompt: str, messages: list[dict],
             temperature: float = 0.7, max_tokens: int = 1000) -> str:
        import urllib.request
        import urllib.error

        url = f"{self._base_url}/chat/completions"
        payload = {
            "model": self._model,
            "messages": [{"role": "system", "content": system_prompt}] + messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }

        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(), headers=headers
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            return f"[CC Switch 调用失败: {e}]"


class OpenAICompatibleProvider(LLMProvider):
    """通用 OpenAI 兼容提供者（DeepSeek、Qwen、GPT 等）"""

    def __init__(self, base_url: str, api_key: str, model: str, name: str = ""):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._name = name or model

    def name(self) -> str:
        return self._name

    def chat(self, system_prompt: str, messages: list[dict],
             temperature: float = 0.7, max_tokens: int = 1000) -> str:
        import urllib.request
        import json as _json

        url = f"{self._base_url}/chat/completions"
        payload = {
            "model": self._model,
            "messages": [{"role": "system", "content": system_prompt}] + messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        req = urllib.request.Request(
            url, data=_json.dumps(payload).encode(), headers=headers
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = _json.loads(resp.read().decode())
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            return f"[LLM 调用失败: {e}]"


def create_provider() -> Optional[LLMProvider]:
    """根据环境变量自动创建 Provider

    优先级：
    1. CC_SWITCH_* 环境变量 → CCSwitchProvider
    2. LLM_BASE_URL + LLM_API_KEY → OpenAICompatibleProvider
    3. 都没有 → None（离线模式，只提供 Tools，不调用 LLM）
    """
    # 优先 CC Switch
    cc_url = os.getenv("CC_SWITCH_BASE_URL")
    cc_key = os.getenv("CC_SWITCH_API_KEY")
    if cc_url and cc_key:
        model = os.getenv("CC_SWITCH_MODEL", "deepseek-chat")
        return CCSwitchProvider(cc_url, cc_key, model)

    # 通用 OpenAI 兼容
    llm_url = os.getenv("LLM_BASE_URL")
    llm_key = os.getenv("LLM_API_KEY")
    if llm_url and llm_key:
        model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        name = os.getenv("LLM_PROVIDER_NAME", model)
        return OpenAICompatibleProvider(llm_url, llm_key, model, name)

    # 离线模式
    return None
