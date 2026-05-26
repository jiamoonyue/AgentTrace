"""TraceAnalyzer — 纯算法检测 Trace 中的问题模式 (不需要 LLM)。

检测的异常模式:
    - 重复调用: 同一工具连续调 3+ 次 (可能死循环)
    - 工具失败: action.error 不为空
    - 低置信度: confidence < 0.5
    - 高延迟: 单次工具调用超过阈值
    - Token 浪费: 某步 Token 占比过高
    - 缺少兜底: 失败后没有 fallback 策略
"""

from agenttrace_sdk.models import Trace, TraceStep, StepPhase


def analyze(trace: Trace) -> dict:
    """分析 Trace, 返回结构化的问题列表。"""
    issues = []

    issues.extend(_detect_repeated_calls(trace))
    issues.extend(_detect_failures(trace))
    issues.extend(_detect_low_confidence(trace))
    issues.extend(_detect_high_latency(trace))
    issues.extend(_detect_token_waste(trace))
    issues.extend(_detect_missing_fallback(trace))

    # 严重程度排序
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    issues.sort(key=lambda x: severity_order.get(x["severity"], 99))

    return {
        "trace_id": trace.id,
        "agent_name": trace.agent_name,
        "model": trace.model,
        "summary": {
            "total_steps": len(trace.steps),
            "total_tokens": trace.total_tokens,
            "tools_called": trace.tools_called,
            "decision_path": trace.decision_path,
            "total_time_ms": trace.total_time_ms,
            "issue_count": len(issues),
            "health": _health_score(issues),
        },
        "issues": issues,
    }


def _detect_repeated_calls(trace: Trace) -> list[dict]:
    """检测重复的工具调用。"""
    issues = []
    actions = [s for s in trace.steps if s.action]
    tool_sequence = [a.action.tool_name for a in actions]

    # 滑动窗口: 同一工具连续出现 3+ 次
    for i in range(len(tool_sequence) - 2):
        window = tool_sequence[i:i + 3]
        if len(set(window)) == 1:
            issues.append({
                "type": "repeated_calls",
                "severity": "high",
                "tool": window[0],
                "at_steps": f"[{actions[i].sequence}] → [{actions[i].sequence} + 2]",
                "description": f"工具 '{window[0]}' 连续调用了 3+ 次，可能存在死循环或缺少停止条件",
                "suggestion": "在 Agent Prompt 中添加停止条件: '如果同一工具连续返回相似结果 3 次，请停止并基于已有信息回答'",
            })
            break

    return issues


def _detect_failures(trace: Trace) -> list[dict]:
    """检测工具调用失败。"""
    issues = []
    for step in trace.steps:
        if step.action and step.action.error:
            issues.append({
                "type": "tool_failure",
                "severity": "high",
                "tool": step.action.tool_name,
                "at_step": step.sequence,
                "error": step.action.error,
                "description": f"步骤 {step.sequence}: 工具 '{step.action.tool_name}' 调用失败",
                "suggestion": f"为工具 '{step.action.tool_name}' 添加重试机制或 fallback 策略",
            })
    return issues


def _detect_low_confidence(trace: Trace) -> list[dict]:
    """检测低置信度步骤。"""
    issues = []
    for step in trace.steps:
        if step.confidence is not None and step.confidence < 0.5:
            issues.append({
                "type": "low_confidence",
                "severity": "medium",
                "at_step": step.sequence,
                "confidence": step.confidence,
                "description": f"步骤 {step.sequence}: 置信度仅 {step.confidence:.0%}，Agent 对自己的决策不确定",
                "suggestion": "检查此步的 Prompt 和上下文，可能缺少关键信息导致 Agent 犹豫",
            })
    return issues


def _detect_high_latency(trace: Trace) -> list[dict]:
    """检测高延迟工具调用 (> 2000ms 或超出平均 3 倍)。"""
    actions = [(s, s.action) for s in trace.steps if s.action and s.action.latency_ms]
    if not actions:
        return []

    avg_latency = sum(a.latency_ms for _, a in actions) / len(actions)
    threshold = max(2000, avg_latency * 3)

    issues = []
    for step, action in actions:
        if action.latency_ms and action.latency_ms > threshold:
            issues.append({
                "type": "high_latency",
                "severity": "low",
                "tool": action.tool_name,
                "at_step": step.sequence,
                "latency_ms": action.latency_ms,
                "avg_latency_ms": round(avg_latency),
                "description": f"步骤 {step.sequence}: '{action.tool_name}' 耗时 {action.latency_ms}ms，远超平均 {avg_latency:.0f}ms",
                "suggestion": "检查工具实现是否有性能问题，或考虑添加缓存",
            })
    return issues


def _detect_token_waste(trace: Trace) -> list[dict]:
    """检测 Token 浪费模式。"""
    issues = []
    if trace.total_tokens == 0:
        return issues

    reasoning_steps = [s for s in trace.steps if s.decision and s.token_used > 0]
    for step in reasoning_steps:
        pct = step.token_used / trace.total_tokens * 100
        if pct > 50:
            issues.append({
                "type": "token_waste",
                "severity": "medium",
                "at_step": step.sequence,
                "token_pct": round(pct, 1),
                "description": f"步骤 {step.sequence}: 单步消耗 {step.token_used} Token (占总量的 {pct:.1f}%)",
                "suggestion": "检查此步的 system prompt 是否过长，或消息历史是否堆积过多无关内容",
            })
    return issues


def _detect_missing_fallback(trace: Trace) -> list[dict]:
    """检测失败后是否有 fallback。"""
    issues = []
    failed_tools = [
        (s, s.action.tool_name)
        for s in trace.steps
        if s.action and s.action.error
    ]
    for step, tool_name in failed_tools:
        # 检查失败之后是否有替代策略
        later_steps = [s for s in trace.steps if s.sequence > step.sequence]
        has_fallback = any(
            s.decision and "fallback" in (s.decision.thought or "").lower()
            or s.decision and "替代" in (s.decision.thought or "")
            for s in later_steps
        )
        if not has_fallback:
            issues.append({
                "type": "missing_fallback",
                "severity": "medium",
                "tool": tool_name,
                "at_step": step.sequence,
                "description": f"步骤 {step.sequence}: '{tool_name}' 失败后没有 fallback 策略",
                "suggestion": f"为 '{tool_name}' 添加备用工具或降级方案",
            })
    return issues


def _health_score(issues: list[dict]) -> str:
    """根据问题数量和严重程度给出健康评分。"""
    critical = sum(1 for i in issues if i["severity"] == "critical")
    high = sum(1 for i in issues if i["severity"] == "high")
    medium = sum(1 for i in issues if i["severity"] == "medium")

    if critical + high == 0 and medium == 0:
        return "healthy"
    if critical == 0 and high <= 1:
        return "warning"
    if critical >= 1 or high >= 3:
        return "critical"
    return "warning"
