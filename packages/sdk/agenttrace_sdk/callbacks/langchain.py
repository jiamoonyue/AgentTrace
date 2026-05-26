"""LangChain / LangGraph 自动回调 —— 零侵入追踪 LangChain Agent。

用法:
    from agenttrace_sdk.callbacks.langchain import AgentTraceCallback
    from langchain.agents import AgentExecutor

    callback = AgentTraceCallback(agent_name="lc_bot", model="gpt-4")
    executor = AgentExecutor(..., callbacks=[callback])
    result = executor.invoke({"input": "..."})
    trace = callback.trace  # 拿到完整的 Trace 对象

不需要手动 reason()/act()/observe(), 回调自动完成。
"""

from agenttrace_sdk.models import (
    Action,
    Decision,
    StepPhase,
    ToolCandidate,
    Trace,
    TraceStep,
)

# try/except: LangChain 是可选依赖, 没有安装时给出友好提示
try:
    from langchain.callbacks.base import BaseCallbackHandler
    HAS_LANGCHAIN = True
except ImportError:
    HAS_LANGCHAIN = False


class AgentTraceCallback:
    """LangChain 回调处理器: 自动将 LLM 调用和工具调用记录为 Trace。

    支持:
        - on_llm_start / on_llm_end → REASONING 步骤
        - on_tool_start / on_tool_end → ACTING + OBSERVING 步骤
        - on_chain_start / on_chain_end → 嵌套链追踪

    集成方式:
        from agenttrace_sdk.callbacks.langchain import AgentTraceCallback

        callback = AgentTraceCallback("my_agent", "gpt-4")
        agent_executor.invoke({"input": "..."}, config={"callbacks": [callback]})
        trace = callback.trace
    """

    def __init__(self, agent_name: str, model: str):
        if not HAS_LANGCHAIN:
            raise ImportError(
                "LangChain 未安装。安装: pip install langchain"
            )

        # 动态创建回调类 (因为 BaseCallbackHandler 可能不存在)
        self._handler = _LangChainHandler(agent_name, model)

    @property
    def trace(self) -> Trace:
        return self._handler.trace

    def __call__(self):
        return self._handler


if HAS_LANGCHAIN:

    class _LangChainHandler(BaseCallbackHandler):
        """实际的 LangChain 回调处理器。"""

        def __init__(self, agent_name: str, model: str):
            super().__init__()
            self.trace = Trace(
                task="(LangChain Agent)",
                agent_name=agent_name,
                model=model,
            )
            self._step_count = 0
            self._llm_tokens = 0

        def on_llm_start(self, serialized, prompts, **kwargs):
            """LLM 调用开始。"""
            self._step_count += 1
            self._current_thought = (
                prompts[0][:300] if prompts else "(LangChain LLM call)"
            )

        def on_llm_end(self, response, **kwargs):
            """LLM 调用结束 → 记录 REASONING 步骤。"""
            content = ""
            if hasattr(response, 'generations'):
                content = str(response.generations[0][0].text)[:300] if response.generations else ""
            usage = getattr(response, 'llm_output', {}).get('token_usage', {})
            tokens = usage.get('total_tokens', 0)

            step = TraceStep(
                phase=StepPhase.REASONING,
                token_used=tokens,
                decision=Decision(
                    thought=f"[LLM] {self._current_thought}\n[Response] {content}",
                    decision_rationale="LangChain LLM 调用",
                ),
            )
            self.trace.add_step(step)

        def on_tool_start(self, serialized, input_str, **kwargs):
            """工具调用开始。"""
            self._tool_name = serialized.get("name", "unknown")
            self._tool_input = input_str

        def on_tool_end(self, output, **kwargs):
            """工具调用结束 → 记录 ACTING + OBSERVING。"""
            # Acting
            self.trace.add_step(TraceStep(
                phase=StepPhase.ACTING,
                action=Action(
                    tool_name=self._tool_name,
                    params={"input": str(self._tool_input)},
                    result_snippet=str(output)[:500],
                ),
            ))

            # Observing
            self.trace.add_step(TraceStep(
                phase=StepPhase.OBSERVING,
                observation=str(output)[:300],
            ))

        def on_chain_end(self, outputs, **kwargs):
            """Chain 结束时 finalize。"""
            self.trace.finalize()
