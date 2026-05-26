"""LLMTracer — 自动追踪 LLM 调用的每一步。

解决的问题:
    之前: 手动调 LLM → 手动 reason() → 手动 act() → 手动 observe()
          Token 不记录, reason 内容是废话, 代码冗长

    之后: tracer.step(messages, tools) 一行搞定
          Token 自动记录, reason 用 LLM 真正的输出, 代码精简

设计原则:
    LLMTracer 不负责调 LLM — 它只负责"记录 Trace"。
    LLM 调用通过构造函数注入 (依赖反转)。
    这样 LLMTracer 不依赖任何具体的 LLM 客户端。
"""

from typing import Callable, Optional

from agenttrace_sdk.decorators import observe, reason, timed_act
from agenttrace_sdk.models import ToolCandidate


# chat_fn 的类型: (messages, tools) → LLMResponse
# 任何符合这个签名的函数都可以注入
LLMResponse = dict  # {"content": ..., "tool_calls": ..., "tokens": {...}}


class LLMTracer:
    """ReAct 循环追踪器: 自动记录每次 LLM 调用的 Reasoning。

    用法:
        from agenttrace_engine.llm.client import LLMClient
        from agenttrace_sdk.tracer import LLMTracer

        client = LLMClient()
        tracer = LLMTracer(chat_fn=client.chat_with_tools)

        # 在 ReAct 循环中, 一行搞定:
        response = tracer.step(messages, TOOLS)
        # → 自动调了 LLM
        # → 自动调了 reason() (含真实 Token 数)
        # → 自动记录了 LLM 的真实思考内容
    """

    def __init__(self, chat_fn: Callable[[list[dict], list[dict]], LLMResponse]):
        """
        Args:
            chat_fn: LLM 调用函数, 签名为 (messages, tools) → response
                     任何符合此签名的函数都可以, 不绑定具体客户端
        """
        self._chat = chat_fn
        self._call_count = 0  # 本 Trace 中第几次调 LLM

    def step(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        """执行一次 LLM 推理, 自动记录 Reasoning TraceStep。

        Args:
            messages: 当前消息历史
            tools: 可用工具列表 (None 表示纯对话, 不需要工具)

        Returns:
            LLM 的响应, 格式为 {"content": ..., "tool_calls": ..., "tokens": {...}}
        """
        self._call_count += 1
        response = self._chat(messages, tools or [])

        # ── 从 LLM 响应中提取信息, 自动记录 reason() ──

        tool_calls = response.get("tool_calls") or []
        tokens = response.get("tokens", {})
        content = response.get("content") or ""

        if tool_calls:
            # 情况 1: LLM 决定调工具
            tool_names = [tc["name"] for tc in tool_calls]
            tool_args = [tc["arguments"] for tc in tool_calls]

            reason(
                thought=f"[LLM 第{self._call_count}次推理] "
                        f"决定调用工具: {', '.join(tool_names)}\n"
                        f"参数: {tool_args}\n"
                        f"LLM 原始输出: {content[:200] if content else '(无文本)'}",
                tool_candidates=[
                    ToolCandidate(name=n, score=1.0, reason="LLM 自主选择")
                    for n in tool_names
                ],
                chosen_tool=tool_names[0] if len(tool_names) == 1 else None,
                decision_rationale=f"DeepSeek 判断需调用 {', '.join(tool_names)}",
                token_used=tokens.get("total", 0),
            )
        else:
            # 情况 2: LLM 直接回答
            reason(
                thought=f"[LLM 第{self._call_count}次推理] "
                        f"判断信息充足, 直接回答用户\n"
                        f"回答内容: {content[:300]}",
                token_used=tokens.get("total", 0),
                decision_rationale="信息充足, 无需调用工具",
            )

        return response

    def execute(
        self,
        tool_name: str,
        tool_args: dict,
        tool_map: dict[str, Callable],
    ) -> str:
        """执行工具 + 自动记录 Acting 和 Observing TraceStep。

        Args:
            tool_name: 工具名
            tool_args: 工具参数
            tool_map: {工具名: 实现函数} 的字典

        Returns:
            工具的执行结果字符串
        """
        tool_func = tool_map.get(tool_name)

        if tool_func is None:
            result = f"错误: 工具 '{tool_name}' 不存在"
            with timed_act(tool_name, params=tool_args,
                           error=f"工具 {tool_name} 未注册") as ta:
                ta.result = result
        else:
            try:
                with timed_act(tool_name, params=tool_args) as ta:
                    # 自动适配: 单参数传值, 多参数传 **kwargs
                    if len(tool_args) == 1:
                        val = list(tool_args.values())[0]
                        result = str(tool_func(val))
                    else:
                        result = str(tool_func(**tool_args))
                    ta.result = result
            except Exception as e:
                result = f"工具执行失败: {e}"

        observe(f"{tool_name} 返回: {result[:300]}")
        return result
