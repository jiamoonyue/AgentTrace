"""Trace 相关 API 路由。

接口:
    POST   /api/traces              - 上传一条 Trace
    GET    /api/traces              - 列出 Trace (支持筛选 + 分页)
    GET    /api/traces/compare      - A/B 对比两条 Trace
    GET    /api/traces/stats/summary - 全局统计数据
    GET    /api/traces/{id}         - 查询单条 Trace (完整)
    GET    /api/traces/{id}/export  - 导出 (JSON/CSV)
    GET    /api/traces/{id}/diagnose - AI 诊断
    DELETE /api/traces/{id}         - 删除一条 Trace
"""

from fastapi import APIRouter, HTTPException, Query

from agenttrace_engine.storage.repository import TraceRepository
from agenttrace_sdk.models import Trace

router = APIRouter(prefix="/api/traces", tags=["traces"])

# 全局仓库实例 (在 server.py 里注入)
_repo: TraceRepository | None = None


def set_repository(repo: TraceRepository) -> None:
    """注入 Repository 实例。"""
    global _repo
    _repo = repo


def get_repository() -> TraceRepository:
    """获取 Repository 实例。"""
    if _repo is None:
        raise RuntimeError("Repository 未初始化, 请先调用 set_repository()")
    return _repo


@router.post("", status_code=201)
def upload_trace(trace: Trace):
    """上传一条 Agent 执行轨迹。

    请求体就是 SDK Trace 的 JSON 格式。
    SDK 用户可以直接 trace.model_dump_json() 发过来。
    """
    repo = get_repository()
    trace_id = repo.save_trace(trace)
    return {"status": "ok", "trace_id": trace_id}


@router.get("")
def list_traces(
    agent_name: str | None = Query(None, description="按 Agent 名称筛选"),
    model: str | None = Query(None, description="按 LLM 模型筛选"),
    offset: int = Query(0, ge=0, description="偏移量"),
    limit: int = Query(50, ge=1, le=200, description="每页数量"),
):
    """列出 Trace 摘要, 支持筛选和分页。

    查询参数都是可选的:
        ?agent_name=weather_bot    → 只看 weather_bot 的轨迹
        ?model=deepseek-chat       → 只看用 DeepSeek 的轨迹
        ?offset=50&limit=50        → 第二页
        ?agent_name=bot&model=gpt  → 组合筛选
    """
    repo = get_repository()
    return repo.list_traces(
        agent_name=agent_name,
        model=model,
        offset=offset,
        limit=limit,
    )


# /stats 路由必须在 /{trace_id} 之前注册, 否则 FastAPI 会把 "stats" 当成 trace_id
@router.get("/compare")
def compare_traces(a: str, b: str):
    """A/B 对比两条 Trace。

    查询参数:
        ?a=trace_id_1&b=trace_id_2

    返回两边的关键指标差异:
        - Token 消耗对比
        - 步骤数对比
        - 工具选择对比
        - 决策路径对比
        - 耗时对比
    """
    repo = get_repository()
    trace_a = repo.get_trace(a)
    trace_b = repo.get_trace(b)

    if not trace_a:
        raise HTTPException(status_code=404, detail=f"Trace A ({a}) 不存在")
    if not trace_b:
        raise HTTPException(status_code=404, detail=f"Trace B ({b}) 不存在")

    return {
        "a": _trace_metrics(trace_a),
        "b": _trace_metrics(trace_b),
        "diff": {
            "tokens": trace_b.total_tokens - trace_a.total_tokens,
            "steps": len(trace_b.steps) - len(trace_a.steps),
            "time_ms": round(trace_b.total_time_ms - trace_a.total_time_ms, 1),
            "tools_a_only": list(set(trace_a.tools_called) - set(trace_b.tools_called)),
            "tools_b_only": list(set(trace_b.tools_called) - set(trace_a.tools_called)),
            "decision_path_same": trace_a.decision_path == trace_b.decision_path,
        },
    }


def _trace_metrics(trace):
    """提取一条 Trace 的关键指标。"""
    return {
        "id": trace.id,
        "agent_name": trace.agent_name,
        "model": trace.model,
        "task": trace.task,
        "total_tokens": trace.total_tokens,
        "total_steps": len(trace.steps),
        "tools_called": trace.tools_called,
        "decision_path": trace.decision_path,
        "total_time_ms": trace.total_time_ms,
        "react_cycles": trace.react_cycles,
    }


@router.get("/stats/summary")
def get_stats():
    """获取全局统计数据。

    返回:
        - 总 Trace 数
        - 各 Agent 调用次数
        - 各模型使用次数
        - 最常用的 10 个工具
        - 平均 Token 和耗时
    """
    repo = get_repository()
    return repo.get_stats()


@router.get("/{trace_id}/export")
def export_trace(trace_id: str, format: str = "json"):
    """导出 Trace 数据。

    支持格式:
        json  → 完整 JSON (默认)
        csv   → 步骤表格 (可导入 Excel)
    """
    import csv
    import io
    from fastapi.responses import StreamingResponse

    repo = get_repository()
    trace = repo.get_trace(trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail=f"Trace {trace_id} 不存在")

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["sequence", "phase", "thought", "tool", "params",
                          "result", "latency_ms", "confidence", "token_used"])
        for step in trace.steps:
            writer.writerow([
                step.sequence, step.phase.value,
                step.decision.thought[:200] if step.decision else "",
                step.action.tool_name if step.action else "",
                str(step.action.params) if step.action else "",
                step.action.result_snippet or "" if step.action else step.observation or "",
                step.action.latency_ms or "" if step.action else "",
                step.confidence or "",
                step.token_used,
            ])
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={trace_id}.csv"},
        )

    # JSON: 完整导出
    return trace.model_dump(mode="json")


@router.get("/{trace_id}/diagnose")
def diagnose_trace(trace_id: str):
    """对一条 Trace 执行 AI 诊断。

    返回:
        - analysis: 纯算法检测到的问题
        - llm_report: LLM 深度分析报告 (含评分和修复建议)
    """
    from agenttrace_engine.debug_agent import diagnose

    repo = get_repository()
    trace = repo.get_trace(trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail=f"Trace {trace_id} 不存在")
    return diagnose(trace)


@router.get("/{trace_id}")
def get_trace(trace_id: str):
    """获取一条 Trace 的完整数据, 包含所有步骤。"""
    repo = get_repository()
    trace = repo.get_trace(trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail=f"Trace {trace_id} 不存在")
    return trace.model_dump(mode="json")


@router.delete("/{trace_id}")
def delete_trace(trace_id: str):
    """删除一条 Trace 及其所有步骤。"""
    repo = get_repository()
    deleted = repo.delete_trace(trace_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Trace {trace_id} 不存在")
    return {"status": "deleted", "trace_id": trace_id}
