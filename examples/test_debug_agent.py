"""Debug Agent 测试:
1. 创建一条包含已知问题的 Trace
2. 用 TraceAnalyzer 检测问题
3. 用 DebugAgent 生成 LLM 诊断报告
"""

import sys
sys.path.insert(0, "D:/agenttrace/packages/sdk")
sys.path.insert(0, "D:/agenttrace/packages/engine")

from agenttrace_sdk import (
    Trace, TraceStep, StepPhase, Decision, Action, ToolCandidate
)
from agenttrace_engine.debug_agent.analyzer import analyze as algo_analyze
from agenttrace_engine.debug_agent.agent import diagnose


def make_buggy_trace() -> Trace:
    """构造一条包含多个已知问题的 Trace:
    - web_search 连续调了 4 次 (死循环)
    - external_api 调用失败
    - 步骤 2 置信度很低
    """
    trace = Trace(
        task="分析特斯拉股价",
        agent_name="test_bot",
        model="deepseek-chat",
    )

    # 正常的推理
    trace.add_step(TraceStep(phase=StepPhase.REASONING, token_used=300, decision=Decision(
        thought="需要搜索特斯拉新闻",
        tool_candidates=[
            ToolCandidate(name="web_search", score=0.9),
            ToolCandidate(name="financial_api", score=0.8),
        ],
        rejected_alternatives=["直接问用户——不专业"],
        chosen_tool="web_search",
        decision_rationale="web_search 最直接",
    )))
    trace.add_step(TraceStep(phase=StepPhase.ACTING, action=Action(
        tool_name="web_search", params={"query": "特斯拉"},
        result_snippet="特斯拉股价 $278", latency_ms=320,
    )))
    trace.add_step(TraceStep(phase=StepPhase.OBSERVING, observation="搜到股价信息"))

    # 低置信度
    trace.add_step(TraceStep(
        phase=StepPhase.EVALUATING, confidence=0.35
    ))

    # 第二次 web_search (重复!)
    trace.add_step(TraceStep(phase=StepPhase.REASONING, token_used=350, decision=Decision(
        thought="信息不够，再搜一次",
        chosen_tool="web_search",
    )))
    trace.add_step(TraceStep(phase=StepPhase.ACTING, action=Action(
        tool_name="web_search", params={"query": "特斯拉"},
        result_snippet="同样的结果", latency_ms=310,
    )))
    trace.add_step(TraceStep(phase=StepPhase.OBSERVING, observation="结果相似"))

    # 第三次 web_search (死循环!)
    trace.add_step(TraceStep(phase=StepPhase.REASONING, token_used=400, decision=Decision(
        thought="还是不够，再搜",
        chosen_tool="web_search",
    )))
    trace.add_step(TraceStep(phase=StepPhase.ACTING, action=Action(
        tool_name="web_search", params={"query": "特斯拉"},
        result_snippet="依然相似", latency_ms=305,
    )))
    trace.add_step(TraceStep(phase=StepPhase.OBSERVING, observation="结果还是相似"))

    # 第四次! 死循环确认
    trace.add_step(TraceStep(phase=StepPhase.REASONING, token_used=450, decision=Decision(
        thought="再试一次...",
        chosen_tool="web_search",
    )))
    trace.add_step(TraceStep(phase=StepPhase.ACTING, action=Action(
        tool_name="web_search", params={"query": "特斯拉"},
        result_snippet="完全相同", latency_ms=300,
    )))
    trace.add_step(TraceStep(phase=StepPhase.OBSERVING, observation="没有新信息"))

    # 失败的工具调用
    trace.add_step(TraceStep(phase=StepPhase.ACTING, action=Action(
        tool_name="external_api",
        tool_type="rest_api",
        params={"endpoint": "/v2/price"},
        error="Timeout: 连接超时",
        latency_ms=5000,
    )))

    trace.finalize()
    return trace


def main():
    print("=" * 60)
    print("Debug Agent 测试")
    print("=" * 60)

    trace = make_buggy_trace()
    print(f"\n构造测试 Trace: {trace.id}")
    print(f"  步骤: {len(trace.steps)}")
    print(f"  工具: {trace.tools_called}")
    print(f"  决策路径: {trace.decision_path}")

    # 测试 1: 纯算法分析
    print("\n── 测试 1: TraceAnalyzer (纯算法) ──")
    result = algo_analyze(trace)
    print(f"  健康状态: {result['summary']['health']}")
    print(f"  发现问题: {result['summary']['issue_count']} 个")
    for issue in result["issues"]:
        print(f"    [{issue['severity']}] {issue['type']}: {issue['description'][:60]}...")

    # 验证
    issue_types = [i["type"] for i in result["issues"]]
    assert "repeated_calls" in issue_types, "应该检测到重复调用"
    assert "tool_failure" in issue_types, "应该检测到工具失败"
    assert "low_confidence" in issue_types, "应该检测到低置信度"
    assert "high_latency" in issue_types, "应该检测到高延迟"
    print("  ✓ 所有已知问题均被检测")

    # 测试 2: Debug Agent (LLM)
    print("\n── 测试 2: DebugAgent (LLM 分析) ──")
    try:
        report = diagnose(trace)
        if report.get("llm_report") and not report["llm_report"].get("error_parsing"):
            llm = report["llm_report"]
            print(f"  诊断: {llm.get('diagnosis', 'N/A')[:100]}")
            print(f"  严重度: {llm.get('severity')}")
            print(f"  评分: {llm.get('score', 'N/A')}/100")
            if llm.get("root_causes"):
                print(f"  根因: {llm['root_causes'][0][:80]}")
            print(f"  Token: {report.get('tokens_used', 'N/A')}")
            print("  ✓ LLM 诊断报告生成成功")
        else:
            print(f"  仅算法分析: {report.get('error', 'LLM 返回格式异常')}")
    except Exception as e:
        print(f"  LLM 诊断跳过: {e} (继续用算法分析)")

    print("\n✓ Debug Agent 测试完成")


if __name__ == "__main__":
    main()
