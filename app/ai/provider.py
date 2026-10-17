"""大模型适配层（TRD 第九章：AI 只辅助，不决策）。

- AIProvider 协议 + DeepSeekProvider（OpenAI 兼容 /chat/completions）+ MockProvider（测试用）。
- 模型输出必须过 JSON Schema 校验；解析不了的值一律 None，进人工复核。
"""

import json
from typing import Protocol

import httpx

from tradepilot.app.core.config import settings


class AIProvider(Protocol):
    def extract_json(self, system_prompt: str, user_text: str) -> dict:
        """返回模型输出的 JSON dict；失败抛异常，由上层决定降级策略。"""
        ...


class DeepSeekProvider:
    """OpenAI 兼容接口（DeepSeek / 通义 / GLM 等均可通过 base_url 切换）。"""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
    ):
        self.base_url = (base_url or settings.ai_base_url).rstrip("/")
        self.api_key = api_key or settings.ai_api_key
        self.model = model or settings.ai_model
        self.timeout = timeout or settings.ai_timeout_seconds

    def extract_json(self, system_prompt: str, user_text: str) -> dict:
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0,  # 提取任务要确定性输出
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return _loads_json(content)


class MockProvider:
    """测试用：按注入的规则从文本里"提取"，不访问网络。"""

    def __init__(self, handler=None):
        self.handler = handler or (lambda text: {"items": [], "notes": "mock"})

    def extract_json(self, system_prompt: str, user_text: str) -> dict:
        return self.handler(user_text)


def _loads_json(content: str) -> dict:
    """容忍模型输出 ```json 围栏。"""
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def get_provider() -> AIProvider:
    return DeepSeekProvider()
