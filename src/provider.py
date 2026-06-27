"""Provider Interface - LLM 调用抽象层

Relationship Engine 不绑定任何具体 LLM。
通过 Provider Interface 调用，支持流式输出。
任何 LLM（DeepSeek、Claude、GPT、Qwen）都可以通过此接口统一调用。
"""

import os
import json
import urllib.request
import urllib.error
from abc import ABC, abstractmethod
from typing import Optional, AsyncGenerator
import asyncio


class LLMProvider(ABC):
    """LLM 提供者抽象接口"""

    @abstractmethod
    def name(self) -> str:
        """提供者名称"""
        ...

    @abstractmethod
    def chat(self, system_prompt: str, messages: list[dict],
             temperature: float = 0.7, max_tokens: int = 2000) -> str:
        """非流式对话"""
        ...

    @abstractmethod
    def stream_chat(self, system_prompt: str, messages: list[dict],
                    temperature: float = 0.7, max_tokens: int = 2000) -> AsyncGenerator[str, None]:
        """流式对话，逐字返回"""
        ...


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
             temperature: float = 0.7, max_tokens: int = 2000) -> str:
        url = f"{self._base_url}/chat/completions"
        payload = {
            "model": self._model,
            "messages": [{"role": "system", "content": system_prompt}] + messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode())
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            return f"[LLM 调用失败: {e}]"

    async def stream_chat(self, system_prompt: str, messages: list[dict],
                          temperature: float = 0.7, max_tokens: int = 2000) -> AsyncGenerator[str, None]:
        """流式调用 OpenAI 兼容 API"""
        url = f"{self._base_url}/chat/completions"
        payload = {
            "model": self._model,
            "messages": [{"role": "system", "content": system_prompt}] + messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers)

        try:
            resp = urllib.request.urlopen(req, timeout=120)
            buffer = ""
            while True:
                chunk = resp.read(1024)
                if not chunk:
                    break
                buffer += chunk.decode("utf-8")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line or line == "data: [DONE]":
                        continue
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            delta = data.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            yield f"\n[LLM 调用失败: {e}]"


def create_provider() -> Optional[LLMProvider]:
    """根据环境变量自动创建 Provider

    优先级：
    1. CC_SWITCH_* 环境变量 → CC Switch（OpenAI 兼容）
    2. LLM_BASE_URL + LLM_API_KEY → OpenAI 兼容
    3. 都没有 → None（离线模式）
    """
    # CC Switch
    cc_url = os.getenv("CC_SWITCH_BASE_URL")
    cc_key = os.getenv("CC_SWITCH_API_KEY")
    if cc_url and cc_key:
        model = os.getenv("CC_SWITCH_MODEL", "deepseek-chat")
        return OpenAICompatibleProvider(cc_url, cc_key, model, f"CCSwitch({model})")

    # 通用 OpenAI 兼容
    llm_url = os.getenv("LLM_BASE_URL")
    llm_key = os.getenv("LLM_API_KEY")
    if llm_url and llm_key:
        model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        name = os.getenv("LLM_PROVIDER_NAME", model)
        return OpenAICompatibleProvider(llm_url, llm_key, model, name)

    return None
