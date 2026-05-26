"""DeepSeek LLM 客户端 (兼容 OpenAI API 格式)。

DeepSeek 的 API 和 OpenAI 完全兼容, 所以这个客户端也能用于:
    - 任何 OpenAI 兼容的 API (vLLM、LocalAI、Ollama 等)
    - 只需改 base_url 和 api_key 即可
"""

import httpx

from agenttrace_engine.llm.config import get_deepseek_config


class LLMClient:
    """通用 LLM 客户端, 支持 OpenAI 兼容 API。

    用法:
        client = LLMClient()
        response = client.chat([
            {"role": "system", "content": "你是一个助手"},
            {"role": "user", "content": "你好"}
        ])
        print(response["content"])   # 助手的回复
        print(response["tokens"])    # Token 用量
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ):
        config = get_deepseek_config()
        self.api_key = api_key or config["api_key"]
        self.base_url = (base_url or config["base_url"]).rstrip("/")
        self.model = model or config["model"]

        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY 未设置, 请检查 .env 文件")

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> dict:
        """发送对话请求, 返回 {content, tokens, raw}。

        Args:
            messages: OpenAI 格式的消息列表
            temperature: 随机性 (0=确定, 1=创意)
            max_tokens: 最大输出 Token 数

        Returns:
            {"content": "助手的回复文本",
             "tokens": {"prompt": 50, "completion": 30, "total": 80},
             "raw": {...原始响应...}}
        """
        url = f"{self.base_url}/v1/chat/completions"

        body = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        response = httpx.post(url, json=body, headers=headers, timeout=60)
        response.raise_for_status()
        data = response.json()

        choice = data["choices"][0]
        usage = data.get("usage", {})

        return {
            "content": choice["message"]["content"],
            "tokens": {
                "prompt": usage.get("prompt_tokens", 0),
                "completion": usage.get("completion_tokens", 0),
                "total": usage.get("total_tokens", 0),
            },
            "raw": data,
        }

    def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        temperature: float = 0.7,
    ) -> dict:
        """发送带工具定义的对话请求, 返回可能包含 tool_calls。

        Args:
            messages: 消息列表
            tools: OpenAI 格式的工具定义列表

        Returns:
            {"content": "文本回复"|None,
             "tool_calls": [{"name": "xxx", "arguments": {...}}]|None,
             "tokens": {...}}
        """
        url = f"{self.base_url}/v1/chat/completions"

        body = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "temperature": temperature,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        response = httpx.post(url, json=body, headers=headers, timeout=60)
        response.raise_for_status()
        data = response.json()

        choice = data["choices"][0]
        msg = choice["message"]
        usage = data.get("usage", {})

        # 解析 tool_calls
        tool_calls = None
        if msg.get("tool_calls"):
            tool_calls = []
            for tc in msg["tool_calls"]:
                import json
                tool_calls.append({
                    "id": tc["id"],
                    "name": tc["function"]["name"],
                    "arguments": json.loads(tc["function"]["arguments"]),
                })

        return {
            "content": msg.get("content"),
            "tool_calls": tool_calls,
            "tokens": {
                "prompt": usage.get("prompt_tokens", 0),
                "completion": usage.get("completion_tokens", 0),
                "total": usage.get("total_tokens", 0),
            },
            "raw": data,
        }
