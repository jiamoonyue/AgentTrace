"""数据库模型 —— 把 Trace/TraceStep 映射到 SQLite 表。

两张表:
    traces       → 一条 Trace 一行
    trace_steps  → 一个 TraceStep 一行, 外键关联 traces

嵌套数据 (Decision、Action) 用 JSON 列存储, 不拆成更多表。
原因: 这些数据总是和 TraceStep 一起读写, 拆表增加 JOIN 开销, 没有独立查询需求。
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class TraceRecord(Base):
    """traces 表: 一条 Trace 一行。

    字段对应 SDK 里 Trace 类的属性。"""
    __tablename__ = "traces"

    id = Column(String(32), primary_key=True)              # trace_abc123
    task = Column(String(500), nullable=False)             # 用户任务描述
    agent_name = Column(String(100), nullable=False)       # 哪个 Agent
    model = Column(String(100), nullable=False)            # 哪个 LLM
    start_time = Column(DateTime, nullable=False)          # 开始时间
    end_time = Column(DateTime, nullable=True)             # 结束时间
    total_tokens = Column(Integer, default=0)              # 总 Token
    total_cost = Column(Float, default=0.0)                # 总费用
    tools_called = Column(Text, default="")                # 工具列表, 逗号分隔

    # 一对多: 一个 Trace 有多个 TraceStep
    steps = relationship("StepRecord", back_populates="trace",
                         order_by="StepRecord.sequence")

    def __repr__(self):
        return f"<TraceRecord id={self.id} agent={self.agent_name}>"


class StepRecord(Base):
    """trace_steps 表: 一个 ReAct 步骤一行。

    Decision 和 Action 的嵌套数据用 JSON 字符串存储。
    读写时通过 SDK 的 Pydantic 模型做序列化/反序列化。"""
    __tablename__ = "trace_steps"

    id = Column(String(16), primary_key=True)              # step_abc123
    trace_id = Column(String(32), ForeignKey("traces.id"),  # 属于哪条 Trace
                      nullable=False, index=True)
    sequence = Column(Integer, nullable=False)              # 步骤序号 (1-based)
    phase = Column(String(20), nullable=False)              # reasoning/acting/observing/evaluating
    timestamp = Column(DateTime, default=datetime.now)      # 步骤时间

    # 不同阶段的有效字段 (JSON 字符串, 用 Pydantic 序列化)
    decision_json = Column(Text, nullable=True)             # Decision.model_dump_json()
    action_json = Column(Text, nullable=True)               # Action.model_dump_json()
    observation = Column(Text, nullable=True)               # observation 字符串
    confidence = Column(Float, nullable=True)               # confidence 数值
    token_used = Column(Integer, default=0)                 # 这一步的 Token

    # 反向关联
    trace = relationship("TraceRecord", back_populates="steps")

    def __repr__(self):
        return f"<StepRecord id={self.id} seq={self.sequence} phase={self.phase}>"
