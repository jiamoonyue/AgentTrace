"""DebugAgent — 用 LLM 分析 Trace 并生成诊断报告。

流程:
    1. TraceAnalyzer 提取异常模式 (纯算法, 不需要 LLM)
    2. DebugAgent 将异常模式 + Trace 摘要发给 LLM
    3. LLM 生成人类可读的诊断报告 + 改进建议

与 AgentTrace 其他部分的关系:
    Debug Agent 本身也是一个 Agent —— 它"调试"其他 Agent。
    这体现了 AgentTrace 的核心理念: 用 Agent 理解 Agent。
"""

import json

from agenttrace_engine.llm.client import LLMClient
from agenttrace_engine.debug_agent.analyzer import analyze
from agenttrace_sdk.models import Trace

DEBUG_SYSTEM_PROMPT = """你是一个 Agent 调试专家。你的任务是分析 Agent 执行轨迹，诊断问题，并给出可操作的改进建议。

分析维度:
    1. 决策质量: Agent 的推理是否合理? 工具选择是否正确?
    2. 效率: Token 消耗是否合理? 是否有冗余步骤?
    3. 鲁棒性: 遇到错误时是否有兜底策略?
    4. 可优化点: Prompt、工具设计、循环控制等方面

输出格式 (JSON):
{
    "diagnosis": "一句话总结诊断结果",
    "severity": "healthy" | "warning" | "critical",
    "root_causes": ["根因1", "根因2"],
    "issues_detail": [
        {"problem": "问题描述", "impact": "影响", "fix": "修复方案"}
    ],
    "prompt_suggestions": ["Prompt 改进建议1", ...],
    "architecture_suggestions": ["架构改进建议1", ...],
    "score": 0-100 (综合评分)
}
"""


def diagnose(trace: Trace) -> dict:
    """分析 Trace 并生成诊断报告。

    Args:
        trace: SDK Trace 对象

    Returns:
        诊断报告 dict, 包含:
        - analysis: TraceAnalyzer 的纯算法分析结果
        - llm_report: LLM 生成的诊断报告 (如果 LLM 可用)
        - error: 错误信息 (如果 LLM 不可用)
    """
    # 第一步: 纯算法分析
    analysis = analyze(trace)

    # 第二步: LLM 深度分析
    try:
        client = LLMClient()
    except ValueError:
        return {
            "analysis": analysis,
            "llm_report": None,
            "error": "LLM 不可用 (未配置 API Key), 仅返回算法分析结果",
        }

    # 构建给 LLM 的上下文
    trace_summary = {
        "agent": trace.agent_name,
        "model": trace.model,
        "task": trace.task,
        "steps": len(trace.steps),
        "tokens": trace.total_tokens,
        "tools": trace.tools_called,
        "decision_path": trace.decision_path,
        "time_ms": trace.total_time_ms,
    }

    # 提取关键的思考内容
    key_thoughts = []
    for s in trace.steps:
        if s.decision:
            key_thoughts.append({
                "step": s.sequence,
                "phase": "reasoning",
                "thought": s.decision.thought[:200],
                "chosen_tool": s.decision.chosen_tool,
            })
        elif s.action:
            key_thoughts.append({
                "step": s.sequence,
                "phase": "acting",
                "tool": s.action.tool_name,
                "latency_ms": s.action.latency_ms,
                "error": s.action.error,
            })

    user_message = f"""请分析以下 Agent 执行轨迹:

## 基本信息
{json.dumps(trace_summary, ensure_ascii=False, indent=2)}

## 自动检测到的问题
{json.dumps(analysis['issues'], ensure_ascii=False, indent=2)}

## 详细步骤
{json.dumps(key_thoughts, ensure_ascii=False, indent=2)}

请输出 JSON 格式的诊断报告。"""

    try:
        response = client.chat(
            messages=[
                {"role": "system", "content": DEBUG_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.3,
        )
        llm_report = json.loads(response["content"])
    except (json.JSONDecodeError, Exception) as e:
        # LLM 返回的不是合法 JSON, 用文本兜底
        llm_report = {
            "diagnosis": response.get("content", str(e))[:200],
            "severity": analysis["summary"]["health"],
            "error_parsing": True,
        }

    return {
        "analysis": analysis,
        "llm_report": llm_report,
        "tokens_used": response.get("tokens", {}).get("total", 0),
    }
