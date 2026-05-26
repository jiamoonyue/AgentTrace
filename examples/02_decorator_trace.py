"""验证 @trace_agent 装饰器: 模拟一个"股价分析 Agent"的完整 ReAct 流程。

这个示例不调用真实 LLM，而是手动模拟 Agent 的思考过程，
演示 trace_agent / reason / act / observe / evaluate 的用法。
"""

import time

from agenttrace_sdk import (
    ToolCandidate,
    act,
    evaluate,
    observe,
    reason,
    trace_agent,
)


# ── 模拟工具函数 ──────────────────────────────────────────────

def mock_stock_api(symbol: str) -> dict:
    """模拟股价查询 API。"""
    time.sleep(0.05)  # 模拟网络延迟
    return {
        "symbol": "TSLA",
        "price": 278.90,
        "change_pct": +3.2,
        "volume": 82_000_000,
    }


def mock_news_api(symbol: str) -> list[dict]:
    """模拟新闻查询 API。"""
    time.sleep(0.08)
    return [
        {"title": "特斯拉发布新款自动驾驶系统", "sentiment": "positive"},
        {"title": "分析师上调目标价至 $320", "sentiment": "positive"},
    ]


def mock_report_gen(title: str, content: str) -> str:
    """模拟 PDF 报告生成。"""
    time.sleep(0.12)
    return f"/output/{title}.pdf"


# ── Agent 函数 ───────────────────────────────────────────────

@trace_agent(agent_name="stock_analyst", model="deepseek-chat")
def stock_analysis_agent(query: str):
    """股价分析 Agent: 查股价 → 查新闻 → 生成报告。"""

    # ══════ 第一轮 ReAct: 查股价 ══════

    reason(
        thought="用户需要分析特斯拉股价。首先需要获取实时股价数据，"
                "以了解当前价格和涨跌情况。",
        tool_candidates=[
            ToolCandidate(name="stock_api", score=0.95, reason="直接获取实时股价"),
            ToolCandidate(name="web_search", score=0.30, reason="能查到但不是实时数据"),
        ],
        rejected_alternatives=["让用户自己提供股价数据——不符合 Agent 的主动服务定位"],
        chosen_tool="stock_api",
        decision_rationale="stock_api 是专业的金融数据接口，准确性和实时性都优于通用搜索",
    )

    stock_data = mock_stock_api("TSLA")
    act(
        tool_name="stock_api",
        params={"symbol": "TSLA"},
        result=f"TSLA ${stock_data['price']}, 涨幅 {stock_data['change_pct']}%",
        latency_ms=52,
        tool_type="function",
    )

    observe(
        f"特斯拉当前股价 ${stock_data['price']}，涨幅 {stock_data['change_pct']}%。"
        f"价格上涨说明市场情绪积极，需要进一步了解上涨原因。"
    )

    evaluate(confidence=0.90)

    # ══════ 第二轮 ReAct: 查新闻 ══════

    reason(
        thought="股价上涨 3.2%，需要了解背后的驱动因素。"
                "查询相关新闻可以找到上涨原因，为后续报告提供论据支撑。",
        tool_candidates=[
            ToolCandidate(name="news_api", score=0.90, reason="获取相关新闻"),
            ToolCandidate(name="web_search", score=0.60, reason="也能找到新闻但不够结构化"),
        ],
        chosen_tool="news_api",
        decision_rationale="news_api 返回结构化新闻数据，方便后续报告引用",
    )

    news = mock_news_api("TSLA")
    act(
        tool_name="news_api",
        params={"symbol": "TSLA"},
        result=f"获取到 {len(news)} 条新闻，均为正面",
        latency_ms=78,
    )

    observe(
        f"获取到 {len(news)} 条相关新闻："
        f"'{news[0]['title']}'、'{news[1]['title']}'。"
        f"全部为正面消息，与股价上涨逻辑一致。"
    )

    evaluate(confidence=0.92)

    # ══════ 第三轮 ReAct: 生成报告 ══════

    reason(
        thought="已经掌握了股价数据和上涨原因，现在需要生成一份结构化的分析报告。"
                "报告应包含：股价概览、上涨原因、风险评估。",
        tool_candidates=[
            ToolCandidate(name="report_generator", score=0.95, reason="生成 PDF 报告"),
        ],
        chosen_tool="report_generator",
        decision_rationale="任务要求是'写简报'，必须生成文档",
    )

    report_path = mock_report_gen("TSLA_分析简报",
        f"特斯拉股价 ${stock_data['price']}，涨幅 {stock_data['change_pct']}%。"
        f"利好因素：{news[0]['title']}、{news[1]['title']}。"
    )
    act(
        tool_name="report_generator",
        params={"title": "TSLA_分析简报", "format": "PDF"},
        result=f"报告已生成: {report_path}",
        latency_ms=125,
    )

    observe(
        f"报告生成成功，路径: {report_path}。"
        f"报告包含股价数据、新闻分析和风险评估三个部分。"
    )

    evaluate(confidence=0.96)

    # 函数自然结束, @trace_agent 会自动 finalize


# ── 运行 ─────────────────────────────────────────────────────

def main():
    trace = stock_analysis_agent("帮我分析特斯拉最近的股价，并生成一份简报")

    print("=" * 60)
    print("AgentTrace 轨迹报告")
    print("=" * 60)
    print(f"Trace ID:     {trace.id}")
    print(f"Agent:        {trace.agent_name}")
    print(f"Model:        {trace.model}")
    print(f"Task:         {trace.task}")
    print(f"Steps:        {len(trace.steps)}")
    print(f"ReAct 循环:   {trace.react_cycles} 轮")
    print(f"决策路径:     {trace.decision_path}")
    print(f"调用工具:     {', '.join(trace.tools_called)}")
    print(f"总 Token:     {trace.total_tokens}")
    print(f"总耗时:       {trace.total_time_ms:.0f}ms")
    print()

    # 逐步展示
    for step in trace.steps:
        phase_label = {
            "reasoning": "思考",
            "acting": "行动",
            "observing": "观察",
            "evaluating": "评估",
        }[step.phase.value]

        if step.decision:
            print(f"  [{step.sequence}] {phase_label} → {step.decision.thought[:60]}...")
        elif step.action:
            print(f"  [{step.sequence}] {phase_label} → 调用 {step.action.tool_name}"
                  f"({step.action.latency_ms}ms)")
        elif step.observation:
            print(f"  [{step.sequence}] {phase_label} → {step.observation[:60]}...")
        elif step.confidence:
            print(f"  [{step.sequence}] {phase_label} → 置信度 {step.confidence:.0%}")


if __name__ == "__main__":
    main()
