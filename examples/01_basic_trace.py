"""验证 AgentTrace 数据模型是否能正确表示 ReAct 循环。

用"查天气"这个最简单场景跑通 Trace → TraceStep → Decision/Action 的完整链路。
"""

from agenttrace_sdk import Trace, TraceStep, StepPhase, Decision, Action, ToolCandidate


def main():
    # ── 1. 创建一条 Trace（一次 Agent 任务执行） ──
    trace = Trace(
        task="北京今天天气怎么样？",
        agent_name="weather_bot",
        model="claude-sonnet-4-6",
    )
    print(f"创建 Trace: {trace.id}")
    print(f"任务: {trace.task}")

    # ── 2. 第一轮 ReAct: Reasoning → Acting → Observing ──

    # Step 1: Reasoning（思考）
    step1 = TraceStep(
        phase=StepPhase.REASONING,
        token_used=320,
        decision=Decision(
            thought="用户问北京天气，需要调用天气查询工具",
            prompt_snapshot="[System] 你是一个天气助手...\n[User] 北京今天天气怎么样？",
            context_window_usage_pct=15.0,
            tool_candidates=[
                ToolCandidate(name="weather_api", score=0.95, reason="直接查天气"),
                ToolCandidate(name="web_search", score=0.40, reason="也能查但不够直接"),
            ],
            rejected_alternatives=["让用户自己去查——不满足 Agent 职责"],
            chosen_tool="weather_api",
            decision_rationale="weather_api 是最直接的工具,评分最高",
        ),
    )
    trace.add_step(step1)

    # Step 2: Acting（执行）
    step2 = TraceStep(
        phase=StepPhase.ACTING,
        token_used=80,
        action=Action(
            tool_name="weather_api",
            tool_type="function",
            params={"city": "北京"},
            result_snippet='{"city":"北京","weather":"晴","temp":25}',
            latency_ms=320,
        ),
    )
    trace.add_step(step2)

    # Step 3: Observing（观察结果）
    step3 = TraceStep(
        phase=StepPhase.OBSERVING,
        token_used=150,
        observation="北京今天晴天，气温 25°C，适合户外活动",
    )
    trace.add_step(step3)

    # Step 4: Evaluating（自我评估）
    step4 = TraceStep(
        phase=StepPhase.EVALUATING,
        token_used=100,
        confidence=0.95,
    )
    trace.add_step(step4)

    # ── 3. 结束 Trace，自动统计 ──
    trace.finalize()

    # ── 4. 输出结果 ──
    print(f"\n完成! 共 {len(trace.steps)} 个步骤")
    print(f"ReAct 循环轮次: {trace.react_cycles}")
    print(f"决策路径: {trace.decision_path}")
    print(f"总 Token: {trace.total_tokens}")
    print(f"总耗时: {trace.total_time_ms:.0f}ms")
    print(f"调用工具: {trace.tools_called}")


if __name__ == "__main__":
    main()
