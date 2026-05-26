"""AgentTrace SDK 装饰器 —— 一行代码接入轨迹采集。

核心设计:
    @trace_agent 创建 Trace, 用 contextvars 隐式传递给 reason()/act()/observe()。
    函数执行完毕自动 finalize, 返回 Trace 对象。

技术选型: contextvars 而非 threading.local
    - contextvars 是 Python 3.7+ 标准库, 协程安全
    - threading.local 在多协程场景下会串数据
    - 这个项目后续肯定要支持 async, 所以直接用 contextvars
"""

import functools
import time
from contextvars import ContextVar
from typing import Callable, Optional, ParamSpec, TypeVar

from agenttrace_sdk.models import (
    Action,
    Decision,
    StepPhase,
    ToolCandidate,
    Trace,
    TraceStep,
)

# ── 全局 ContextVar: 存当前线程/协程的"活跃 Trace" ──
# 为什么用 ContextVar 而不是全局变量？
#   全局变量: 两个请求同时进来, 会互相覆盖 Trace
#   ContextVar: 每个协程/线程各有一份独立的 Trace, 天然隔离
_current_trace: ContextVar[Optional[Trace]] = ContextVar(
    "current_trace", default=None
)

P = ParamSpec("P")
R = TypeVar("R")


# ── 装饰器 ───────────────────────────────────────────────────

def trace_agent(
    agent_name: str,
    model: str,
):
    """装饰器: 将被装饰函数的一次执行, 包装为一条 Trace。

    Args:
        agent_name: Agent 名称 (如 "research_bot")
        model: 使用的 LLM (如 "deepseek-chat")

    Returns:
        装饰后的函数, 其返回值从原函数的 return 变为 Trace 对象
    """
    def decorator(func: Callable[P, R]) -> Callable[P, Trace]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> Trace:
            # ── 1. 从函数参数中提取任务描述 ──
            task = _extract_task(args, kwargs)

            # ── 2. 创建 Trace ──
            trace = Trace(
                task=task,
                agent_name=agent_name,
                model=model,
            )

            # ── 3. 设置到 ContextVar, 让 reason()/act()/observe() 能找到 ──
            token = _current_trace.set(trace)
            try:
                # ── 4. 执行原函数 ──
                # 原函数的返回值我们保留但不使用, 因为返回的是 Trace
                func(*args, **kwargs)

                # ── 5. 结束 Trace ──
                trace.finalize()
            finally:
                # ── 6. 恢复 ContextVar (防止泄漏到其他协程) ──
                _current_trace.reset(token)

            return trace

        return wrapper
    return decorator


# ── 辅助函数: 推理 / 行动 / 观察 ──────────────────────────────

def reason(
    thought: str,
    tool_candidates: Optional[list[ToolCandidate]] = None,
    rejected_alternatives: Optional[list[str]] = None,
    chosen_tool: Optional[str] = None,
    decision_rationale: str = "",
    prompt_snapshot: Optional[str] = None,
    context_window_usage_pct: Optional[float] = None,
    token_used: int = 0,
) -> None:
    """记录一步 Reasoning (对应 ReAct 的 Thought 阶段)。

    在 Agent 函数中, 每次"思考下一步做什么"后调用此函数。

    Args:
        thought: Agent 的思考过程
        tool_candidates: Agent 考虑过的候选工具列表
        rejected_alternatives: 被否决的方案 (自由文本)
        chosen_tool: 最终选择的工具名
        decision_rationale: 为什么这么选择
        prompt_snapshot: 此时的完整 Prompt (可用来诊断上下文窗口问题)
        context_window_usage_pct: 上下文窗口占用率
        token_used: 这次 LLM 调用消耗的 Token 数
    """
    trace = _current_trace.get()
    if trace is None:
        raise RuntimeError(
            "reason() 必须在 @trace_agent 装饰的函数内调用"
        )

    step = TraceStep(
        phase=StepPhase.REASONING,
        token_used=token_used,
        decision=Decision(
            thought=thought,
            tool_candidates=tool_candidates or [],
            rejected_alternatives=rejected_alternatives or [],
            chosen_tool=chosen_tool,
            decision_rationale=decision_rationale,
            prompt_snapshot=prompt_snapshot,
            context_window_usage_pct=context_window_usage_pct,
        ),
    )
    trace.add_step(step)


def act(
    tool_name: str,
    params: Optional[dict] = None,
    result: Optional[str] = None,
    latency_ms: Optional[int] = None,
    tool_type: str = "function",
    error: Optional[str] = None,
) -> None:
    """记录一步 Acting (对应 ReAct 的 Action 阶段)。

    在调用完工具后立即调用此函数, 这样能记录到准确耗时。

    Args:
        tool_name: 工具名称
        params: 传给工具的参数
        result: 工具返回值 (摘要即可, 不存全量)
        latency_ms: 工具调用耗时 (毫秒)
        tool_type: 工具类型 ("function", "mcp", "rest_api")
        error: 如果调用失败, 记录错误信息
    """
    trace = _current_trace.get()
    if trace is None:
        raise RuntimeError(
            "act() 必须在 @trace_agent 装饰的函数内调用"
        )

    step = TraceStep(
        phase=StepPhase.ACTING,
        action=Action(
            tool_name=tool_name,
            tool_type=tool_type,
            params=params or {},
            result_snippet=result,
            latency_ms=latency_ms,
            error=error,
        ),
    )
    trace.add_step(step)


def observe(observation: str) -> None:
    """记录一步 Observing (对应 ReAct 的 Observation 阶段)。

    在理解工具返回结果后调用此函数。

    Args:
        observation: 对工具返回结果的解读
    """
    trace = _current_trace.get()
    if trace is None:
        raise RuntimeError(
            "observe() 必须在 @trace_agent 装饰的函数内调用"
        )

    step = TraceStep(
        phase=StepPhase.OBSERVING,
        observation=observation,
    )
    trace.add_step(step)


def evaluate(confidence: float) -> None:
    """记录一步 Evaluating (每轮 ReAct 循环末尾的自我评估)。

    Args:
        confidence: 对本轮决策的置信度 (0.0~1.0)
    """
    trace = _current_trace.get()
    if trace is None:
        raise RuntimeError(
            "evaluate() 必须在 @trace_agent 装饰的函数内调用"
        )

    step = TraceStep(
        phase=StepPhase.EVALUATING,
        confidence=confidence,
    )
    trace.add_step(step)


# ── 内部工具 ──────────────────────────────────────────────────

def _extract_task(args: tuple, kwargs: dict) -> str:
    """从函数参数中提取任务描述。

    优先取第一个字符串参数, 否则取 kwargs 中的 'task'/'query'/'question'。
    都找不到就用 repr。
    """
    # 策略 1: 第一个位置参数是字符串
    if args and isinstance(args[0], str):
        return args[0]

    # 策略 2: 常见的命名参数
    for key in ("task", "query", "question", "prompt"):
        val = kwargs.get(key)
        if isinstance(val, str):
            return val

    # 策略 3: 兜底
    return str(args[0]) if args else "unknown task"


# ── 上下文管理器: 自动计时的 act ─────────────────────────────

class TimedAction:
    """上下文管理器: 进入时记开始时间, 退出时自动算耗时并调 act()。

    用法:
        with TimedAction(tool_name="stock_api", params={"symbol": "TSLA"}) as ta:
            result = stock_api("TSLA")
            ta.result = str(result)   # 在 with 块内设置返回值
        # 退出时自动调用 act(), latency_ms 自动填充

    技术原理:
        Python 的 with 语句触发两个方法:
            __enter__() → 进入 with 块时调用 (我们在这里记开始时间)
            __exit__()  → 退出 with 块时调用 (我们在这里算耗时 + 调 act())
    """

    def __init__(
        self,
        tool_name: str,
        params: Optional[dict] = None,
        tool_type: str = "function",
    ):
        self.tool_name = tool_name
        self.params = params or {}
        self.tool_type = tool_type
        self.result: Optional[str] = None
        self._start_ns: int = 0

    def __enter__(self) -> "TimedAction":
        """进入 with 块: 记录开始时间。

        用 time.perf_counter_ns() 而非 time.time() 的原因:
            - perf_counter_ns 是纳秒级, time.time 是秒级
            - perf_counter_ns 不受系统时间调整影响 (闰秒、NTP 同步)
            - 计算耗时应该用单调时钟, 而不是墙上时钟
        """
        self._start_ns = time.perf_counter_ns()
        return self  # 返回自己, 方便用户在 with 块内设置 result

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """退出 with 块: 算耗时, 调 act()。

        参数说明 (Python 自动传入):
            exc_type:  异常类型, 没有异常时为 None
            exc_val:   异常值
            exc_tb:    异常堆栈

        返回值:
            True  → 吞掉异常 (不推荐)
            False → 异常继续向上抛出 (我们用这个, 保持一致)
        """
        # 算耗时: 纳秒 → 毫秒
        latency_ms = (time.perf_counter_ns() - self._start_ns) // 1_000_000

        # 提取错误信息
        error_msg: Optional[str] = None
        if exc_type is not None:
            error_msg = f"{exc_type.__name__}: {exc_val}"

        act(
            tool_name=self.tool_name,
            params=self.params,
            result=self.result,
            latency_ms=latency_ms,
            tool_type=self.tool_type,
            error=error_msg,
        )

        return False  # 不吞异常, 让它继续传播


def timed_act(
    tool_name: str,
    params: Optional[dict] = None,
    tool_type: str = "function",
) -> TimedAction:
    """自动计时的工具调用记录器。相当于"带计时器的 act()"。

    推荐用法 (每次工具调用只需 3 行):
        with timed_act("stock_api", params={"symbol": "TSLA"}) as ta:
            result = stock_api("TSLA")
            ta.result = str(result)

    等价于手动写法 (5 行 + 手动计时):
        start = time.perf_counter_ns()
        result = stock_api("TSLA")
        latency = (time.perf_counter_ns() - start) // 1_000_000
        act("stock_api", params={...}, result=str(result), latency_ms=latency)

    省掉了:
        - 手动 time.perf_counter_ns() 开始计时
        - 手动 time.perf_counter_ns() 结束计时
        - 手动算毫秒
        - 手动调用 act() 并传 latency_ms
    """
    return TimedAction(
        tool_name=tool_name,
        params=params,
        tool_type=tool_type,
    )
