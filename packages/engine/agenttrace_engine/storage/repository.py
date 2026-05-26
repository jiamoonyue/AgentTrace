"""数据仓库层: SDK Pydantic 模型 ↔ 数据库记录 的互相转换。

为什么需要这一层？
    直接让 FastAPI 路由操作数据库会很乱 (SQL 混在路由里)。
    这一层封装了所有的数据库操作, 路由层只调 repository 的方法。
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from agenttrace_engine.storage.models import Base, StepRecord, TraceRecord
from agenttrace_sdk.models import Action, Decision, Trace, TraceStep, StepPhase


class TraceRepository:
    """Trace 的增删查操作。

    用法:
        repo = TraceRepository("sqlite:///traces.db")
        repo.save_trace(trace)           # 存
        traces = repo.list_traces()      # 查所有
        trace = repo.get_trace("xxx")    # 查单个
    """

    def __init__(self, database_url: str = "sqlite:///agenttrace.db"):
        # SQLite 引擎, echo=False 表示不打印 SQL 日志
        self.engine = create_engine(database_url, echo=False)
        # 自动建表 (如果表不存在)
        Base.metadata.create_all(self.engine)

    # ── 保存 ──────────────────────────────────────────────

    def save_trace(self, trace: Trace) -> str:
        """将一条 SDK Trace 对象存到数据库。

        转换路径:
            SDK Trace → TraceRecord (ORM) → SQLite
            SDK TraceStep → StepRecord (ORM) → SQLite

        Returns:
            trace_id 字符串
        """
        with Session(self.engine) as session:
            # 1. 创建 Trace 记录
            trace_record = TraceRecord(
                id=trace.id,
                task=trace.task,
                agent_name=trace.agent_name,
                model=trace.model,
                start_time=trace.start_time,
                end_time=trace.end_time,
                total_tokens=trace.total_tokens,
                total_cost=trace.total_cost,
                tools_called=",".join(trace.tools_called),
            )

            # 2. 创建 Step 记录
            for step in trace.steps:
                step_record = StepRecord(
                    id=step.id,
                    trace_id=trace.id,
                    sequence=step.sequence,
                    phase=step.phase.value,
                    timestamp=step.timestamp,
                    decision_json=step.decision.model_dump_json()
                    if step.decision else None,
                    action_json=step.action.model_dump_json()
                    if step.action else None,
                    observation=step.observation,
                    confidence=step.confidence,
                    token_used=step.token_used,
                )
                session.add(step_record)

            session.add(trace_record)
            session.commit()
            return trace.id

    # ── 查询列表 (增强版: 筛选 + 分页) ─────────────────────

    def list_traces(
        self,
        agent_name: str | None = None,
        model: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> dict:
        """列出 Trace 摘要, 支持筛选和分页。

        Args:
            agent_name: 按 Agent 名称筛选 (可选)
            model: 按模型筛选 (可选)
            offset: 偏移量 (分页用, 默认 0)
            limit: 每页数量 (默认 50, 最大 200)

        Returns:
            {"total": 总共多少条, "items": [...摘要...]}

        为什么返回 dict 而不是 list?
            前端做分页需要知道 total 总数, 只返回 list 不够。
        """
        with Session(self.engine) as session:
            query = session.query(TraceRecord)

            # 动态筛选: 只有传了参数才加 WHERE 条件
            if agent_name:
                query = query.filter_by(agent_name=agent_name)
            if model:
                query = query.filter_by(model=model)

            # 先查总数 (用于分页)
            total = query.count()

            # 再查当前页
            records = (
                query
                .order_by(TraceRecord.start_time.desc())
                .offset(offset)
                .limit(min(limit, 200))
                .all()
            )

            return {
                "total": total,
                "offset": offset,
                "limit": limit,
                "items": [_trace_summary(r) for r in records],
            }

    # ── 统计 ──────────────────────────────────────────────

    def get_stats(self) -> dict:
        """返回全局统计数据, 用于 Dashboard 总览。

        包含:
            - 总 Trace 数
            - 各 Agent 的调用次数
            - 各模型的使用次数
            - 最常用的工具
            - 平均 Token 消耗
        """
        with Session(self.engine) as session:
            all_traces = session.query(TraceRecord).all()

            if not all_traces:
                return {"total_traces": 0}

            # 按 agent_name 分组计数
            agent_counts: dict[str, int] = {}
            # 按 model 分组计数
            model_counts: dict[str, int] = {}
            # 工具使用统计
            tool_counter: dict[str, int] = {}
            total_tokens = 0
            total_time_ms = 0.0

            for t in all_traces:
                agent_counts[t.agent_name] = agent_counts.get(t.agent_name, 0) + 1
                model_counts[t.model] = model_counts.get(t.model, 0) + 1
                total_tokens += t.total_tokens

                if t.end_time:
                    total_time_ms += (t.end_time - t.start_time).total_seconds() * 1000

                # 统计工具
                if t.tools_called:
                    for tool in t.tools_called.split(","):
                        tool = tool.strip()
                        if tool:
                            tool_counter[tool] = tool_counter.get(tool, 0) + 1

            # 工具按使用次数排序
            top_tools = sorted(tool_counter.items(), key=lambda x: x[1], reverse=True)[:10]

            return {
                "total_traces": len(all_traces),
                "total_tokens": total_tokens,
                "avg_tokens_per_trace": round(total_tokens / len(all_traces), 1),
                "avg_time_ms_per_trace": round(total_time_ms / len(all_traces), 1),
                "agents": agent_counts,
                "models": model_counts,
                "top_tools": [{"tool": name, "count": c} for name, c in top_tools],
            }

    # ── 查询单个 ──────────────────────────────────────────

    def get_trace(self, trace_id: str) -> Trace | None:
        """查询一条完整的 Trace (包含所有步骤)。

        转换路径:
            SQLite → TraceRecord (ORM) → SDK Trace (Pydantic)
        """
        with Session(self.engine) as session:
            record = session.query(TraceRecord).filter_by(id=trace_id).first()
            if record is None:
                return None
            return _to_sdk_trace(record)

    # ── 删除 ──────────────────────────────────────────────

    def delete_trace(self, trace_id: str) -> bool:
        """删除一条 Trace 及其所有步骤。"""
        with Session(self.engine) as session:
            record = session.query(TraceRecord).filter_by(id=trace_id).first()
            if record is None:
                return False
            session.delete(record)
            session.commit()
            return True


# ── 内部转换函数 ────────────────────────────────────────────

def _trace_summary(record: TraceRecord) -> dict:
    """Trace 摘要, 用于列表展示。"""
    return {
        "id": record.id,
        "task": record.task,
        "agent_name": record.agent_name,
        "model": record.model,
        "start_time": record.start_time.isoformat(),
        "end_time": record.end_time.isoformat() if record.end_time else None,
        "total_tokens": record.total_tokens,
        "total_cost": record.total_cost,
        "tools_called": record.tools_called,
        "step_count": len(record.steps),
    }


def _to_sdk_trace(record: TraceRecord) -> Trace:
    """将数据库记录还原为 SDK 的 Trace 对象。

    JSON 字段的反序列化:
        record.decision_json (str) → Decision (Pydantic)
        record.action_json (str)   → Action (Pydantic)
    """
    steps: list[TraceStep] = []
    for sr in record.steps:
        # 从 JSON 字符串还原 Pydantic 对象
        decision = Decision.model_validate_json(sr.decision_json) if sr.decision_json else None
        action = Action.model_validate_json(sr.action_json) if sr.action_json else None

        step = TraceStep(
            id=sr.id,
            sequence=sr.sequence,
            phase=StepPhase(sr.phase),
            timestamp=sr.timestamp,
            decision=decision,
            action=action,
            observation=sr.observation,
            confidence=sr.confidence,
            token_used=sr.token_used,
        )
        steps.append(step)

    return Trace(
        id=record.id,
        task=record.task,
        agent_name=record.agent_name,
        model=record.model,
        steps=steps,
        start_time=record.start_time,
        end_time=record.end_time,
        total_tokens=record.total_tokens,
        total_cost=record.total_cost,
        tools_called=record.tools_called.split(",") if record.tools_called else [],
    )
