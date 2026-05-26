"""AgentTrace SDK — Agent 决策轨迹采集库。

两种用法:
    1. 手动模式（完全控制）:
       from agenttrace_sdk import Trace, TraceStep, StepPhase, Decision, Action
       trace = Trace(task="...", agent_name="...", model="...")
       trace.add_step(TraceStep(phase=StepPhase.REASONING, decision=Decision(...)))
       trace.finalize()

    2. 装饰器模式（推荐, 一行接入）:
       from agenttrace_sdk import trace_agent, reason, act, observe

       @trace_agent(agent_name="weather_bot", model="deepseek-chat")
       def my_agent(query: str):
           reason(thought="需要查天气", ...)
           act(tool_name="weather_api", ...)
           observe("晴, 25°C")

       trace = my_agent("北京天气?")  # 返回 Trace 对象
"""

from agenttrace_sdk.decorators import (
    TimedAction,
    act,
    evaluate,
    observe,
    reason,
    timed_act,
    trace_agent,
)
from agenttrace_sdk.models import (
    Action,
    Decision,
    StepPhase,
    ToolCandidate,
    Trace,
    TraceStep,
)
from agenttrace_sdk.tracer import LLMTracer

__all__ = [
    # 数据模型
    "Trace",
    "TraceStep",
    "StepPhase",
    "Decision",
    "Action",
    "ToolCandidate",
    # 装饰器 + 辅助函数
    "trace_agent",
    "reason",
    "act",
    "observe",
    "evaluate",
    # 上下文管理器
    "timed_act",
    "TimedAction",
    # LLM 追踪器
    "LLMTracer",
]
