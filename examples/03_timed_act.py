"""验证 timed_act: 自动计时的工具调用记录。

对比:
    旧写法(5行): 手动 start → 调工具 → 手动算耗时 → 调 act()
    新写法(3行): with timed_act(...) as ta: → 调工具 → ta.result = ...

另外演示: 工具出错时自动捕获异常信息。
"""

import time

from agenttrace_sdk import (
    ToolCandidate,
    evaluate,
    observe,
    reason,
    timed_act,
    trace_agent,
)


# ── 模拟工具函数 ──────────────────────────────────────────────

def db_query(sql: str) -> list[dict]:
    """模拟数据库查询。"""
    time.sleep(0.03)
    return [{"name": "特斯拉", "price": 278.9}]


def risky_api(endpoint: str) -> dict:
    """模拟一个会失败的 API。"""
    time.sleep(0.02)
    raise ConnectionError(f"无法连接到 {endpoint}")


# ── Agent ───────────────────────────────────────────────────

@trace_agent(agent_name="auto_timed_bot", model="deepseek-chat")
def analysis_agent(query: str):
    """演示 timed_act 用法。"""

    # ══════ 正常工具调用 (自动计时) ══════

    reason(
        thought="需要从数据库查询股票信息",
        tool_candidates=[
            ToolCandidate(name="db_query", score=0.95, reason="直接从数据库取"),
        ],
        chosen_tool="db_query",
        decision_rationale="数据库有最新的结构化数据",
    )

    with timed_act("db_query", params={"sql": "SELECT * FROM stocks WHERE name='TSLA'"}) as ta:
        rows = db_query("SELECT * FROM stocks WHERE name='TSLA'")
        ta.result = str(rows)   # 在 with 块内设置返回值

    observe(f"查到 {len(rows)} 条记录: {rows[0]['name']} ${rows[0]['price']}")

    evaluate(confidence=0.95)

    # ══════ 会失败的工具调用 (自动捕获错误) ══════

    reason(
        thought="还需要从第三方 API 获取实时数据做交叉验证",
        tool_candidates=[
            ToolCandidate(name="external_api", score=0.80, reason="实时数据源"),
        ],
        chosen_tool="external_api",
        decision_rationale="交叉验证提高数据可信度",
    )

    try:
        with timed_act("external_api", params={"endpoint": "https://api.example.com/v2/price"}) as ta:
            result = risky_api("https://api.example.com/v2/price")
            ta.result = str(result)
    except ConnectionError:
        # 异常被 timed_act 记录后继续传播到这里, 我们决定降级处理
        pass

    observe("外部 API 调用失败，使用数据库结果作为唯一数据源")

    evaluate(confidence=0.70)  # 置信度降低, 因为没有交叉验证


# ── 运行 ─────────────────────────────────────────────────────

def main():
    trace = analysis_agent("查询特斯拉当前股价")

    print("=" * 60)
    print("AgentTrace: 自动计时 验证")
    print("=" * 60)
    print(f"决策路径: {trace.decision_path}")
    print(f"工具调用: {', '.join(trace.tools_called)}")
    print()

    for step in trace.steps:
        if step.action:
            status = "失败" if step.action.error else "成功"
            print(f"  [{step.sequence}] {step.action.tool_name}")
            print(f"        耗时: {step.action.latency_ms}ms (自动记录)")
            print(f"        状态: {status}")
            if step.action.error:
                print(f"        错误: {step.action.error}")
            if step.action.result_snippet:
                print(f"        结果: {step.action.result_snippet}")
            print()


if __name__ == "__main__":
    main()
