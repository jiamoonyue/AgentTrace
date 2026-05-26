"""AgentTrace 核心数据模型 —— 把 ReAct 变成精确的 Python 类。

设计原则:
    - 一个 Trace = 一串 TraceStep
    - 每个 TraceStep 属于 ReAct 的四个阶段之一
    - 所有字段都有明确含义,不做"万能字典"
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── ReAct 四阶段 ──────────────────────────────────────────────

class StepPhase(str, Enum):
    """ReAct 循环的四个阶段。

    REASONING  → 对应 ReAct 的 Thought（思考下一步做什么）
    ACTING     → 对应 ReAct 的 Action（调用工具/执行操作）
    OBSERVING  → 对应 ReAct 的 Observation（观察工具返回结果）
    EVALUATING → 额外加的：每轮结束后的自我评估
    """
    REASONING = "reasoning"
    ACTING = "acting"
    OBSERVING = "observing"
    EVALUATING = "evaluating"


# ── Reasoning 阶段的数据 ──────────────────────────────────────

class ToolCandidate(BaseModel):
    """Agent 在思考阶段考虑过的一个候选工具。

    不是每个被考虑的工具都会被选中——记录"想过但没选"的方案,
    是 AgentTrace 区别于普通日志的关键设计。
    """
    name: str
    score: float = 1.0          # 0~1, Agent 认为该工具的匹配度
    reason: str = ""            # Agent 为什么考虑这个工具


class Decision(BaseModel):
    """Reasoning 阶段的完整快照——Agent 的"内心戏"。

    包含:
        - 当时的 Prompt（因为上下文窗口可能已被裁剪）
        - 思考内容
        - 候选工具及其评分
        - 被否决的方案（这对调试极有价值）
    """
    thought: str                                        # Agent 的思考过程
    prompt_snapshot: Optional[str] = None                # 那一刻的完整 Prompt
    context_window_usage_pct: Optional[float] = None     # 上下文窗口占用率
    tool_candidates: list[ToolCandidate] = Field(default_factory=list)
    rejected_alternatives: list[str] = Field(default_factory=list)
    chosen_tool: Optional[str] = None
    decision_rationale: str = ""                         # 为什么这么选


# ── Acting 阶段的数据 ────────────────────────────────────────

class Action(BaseModel):
    """Agent 执行的具体操作。

    tool_type 区分调用来源:
        - "function": 普通 Python 函数
        - "mcp": MCP 协议工具
        - "rest_api": HTTP API 调用
    这个区分对后续按协议类型做分析很有用。
    """
    tool_name: str
    tool_type: str = "function"
    params: dict = Field(default_factory=dict)
    result_snippet: Optional[str] = None    # 返回值摘要（不存全量,太大了）
    latency_ms: Optional[int] = None        # 工具调用耗时
    error: Optional[str] = None             # 如果调用失败,错误信息


# ── TraceStep: ReAct 的一个回合 ───────────────────────────────

class TraceStep(BaseModel):
    """一条轨迹中的一个步骤——对应 ReAct 的一个阶段。

    一个完整的 ReAct 周期是:
        REASONING → ACTING → OBSERVING → (EVALUATING)

    每个阶段是一个独立的 TraceStep。通过 sequence 字段保证顺序。
    不同 phase 有不同的有效字段:
        - REASONING: decision 字段有值
        - ACTING:    action 字段有值
        - OBSERVING: observation 字段有值
        - EVALUATING: confidence 字段有值
    """
    id: str = Field(default_factory=lambda: f"step_{uuid.uuid4().hex[:8]}")
    sequence: int = 0                   # 在 Trace 中的序号（1-based）
    phase: StepPhase                    # 当前是 ReAct 的哪个阶段
    timestamp: datetime = Field(default_factory=datetime.now)

    # 不同阶段的有效字段
    decision: Optional[Decision] = None     # REASONING 时填充
    action: Optional[Action] = None         # ACTING 时填充
    observation: Optional[str] = None       # OBSERVING 时填充
    confidence: Optional[float] = None      # EVALUATING 时填充（0~1）

    # 通用指标
    token_used: int = 0                  # 这一步消耗的 Token 数


# ── Trace: 一条完整的 Agent 执行轨迹 ──────────────────────────

class Trace(BaseModel):
    """一次 Agent 任务执行的完整记录。

    一条 Trace 包含:
        - 任务描述 + 执行 Agent + 使用模型
        - 一串按时间排列的 TraceStep
        - 汇总统计（Token / 耗时 / 工具调用列表）

    用法:
        trace = Trace(task="查天气", agent_name="weather_bot", model="claude-sonnet-4-6")

        # Reasoning
        trace.add_step(TraceStep(phase=StepPhase.REASONING, decision=Decision(
            thought="需要查天气API",
            tool_candidates=[ToolCandidate(name="weather_api", score=0.9)],
            chosen_tool="weather_api"
        )))

        # Acting
        trace.add_step(TraceStep(phase=StepPhase.ACTING, action=Action(
            tool_name="weather_api", params={"city": "北京"}
        )))

        # Observing
        trace.add_step(TraceStep(phase=StepPhase.OBSERVING, observation="晴,25°C"))
    """
    id: str = Field(default_factory=lambda: f"trace_{uuid.uuid4().hex[:12]}")
    task: str                                   # 用户任务
    agent_name: str                             # 哪个 Agent 执行的
    model: str                                  # 使用哪个 LLM
    steps: list[TraceStep] = Field(default_factory=list)
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: Optional[datetime] = None

    # 汇总（Trace 完成后自动计算）
    total_tokens: int = 0
    total_cost: float = 0.0
    tools_called: list[str] = Field(default_factory=list)

    # ── 方法 ──

    def add_step(self, step: TraceStep) -> None:
        """添加一个步骤,自动分配序号。"""
        step.sequence = len(self.steps) + 1
        self.steps.append(step)

    def finalize(self) -> None:
        """标记 Trace 完成,计算汇总指标。"""
        self.end_time = datetime.now()
        self.total_tokens = sum(s.token_used for s in self.steps)
        self.tools_called = list(set(
            s.action.tool_name
            for s in self.steps
            if s.action is not None
        ))

    # ── 计算属性 ──

    @property
    def react_cycles(self) -> int:
        """完成了几轮完整的 Thought→Action→Observe 循环。

        用 OBSERVING 阶段的数量来衡量,因为每轮循环以 Observation 结束。
        """
        return len([s for s in self.steps if s.phase == StepPhase.OBSERVING])

    @property
    def decision_path(self) -> str:
        """返回决策路径的缩写,如 'R→A→O→R→A→O→R→A'。

        R = Reasoning, A = Acting, O = Observing, E = Evaluating
        """
        abbreviations = {
            StepPhase.REASONING: "R",
            StepPhase.ACTING: "A",
            StepPhase.OBSERVING: "O",
            StepPhase.EVALUATING: "E",
        }
        return "→".join(abbreviations[s.phase] for s in self.steps)

    @property
    def total_time_ms(self) -> float:
        """总耗时（毫秒）。"""
        if self.end_time is None:
            return 0
        return (self.end_time - self.start_time).total_seconds() * 1000
