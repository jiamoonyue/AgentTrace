"""真正的 ReAct Agent: DeepSeek 决策 + LLMTracer 自动追踪。

和之前版本的区别:
    - 旧版: 手动 reason() → 内容是自己编的"第1轮需要..."
    - 新版: LLMTracer 自动记录 → 内容是 LLM 真正的输出 + 真实 Token 数

    - 旧版: total_tokens = 0
    - 新版: total_tokens = 每轮 LLM 调用的 Token 之和

    - 旧版: 每个 ReAct 循环 ~15 行代码
    - 新版: 每个 ReAct 循环 ~5 行代码
"""

import json
import sys

sys.path.insert(0, "D:/agenttrace/packages/sdk")
sys.path.insert(0, "D:/agenttrace/packages/engine")

from agenttrace_sdk import trace_agent, LLMTracer
from agenttrace_engine.llm.client import LLMClient


# ── 工具定义 ────────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "搜索互联网获取实时信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "执行数学计算",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "数学表达式"}
                },
                "required": ["expression"],
            },
        },
    },
]


def web_search(query: str) -> str:
    """模拟搜索。实际可替换为 SerpAPI / Tavily 等。"""
    knowledge = {
        "北京": "北京市, 人口约2189万。今日天气: 晴, 28°C。",
        "天气": "今日全国大部晴好, 华北气温25-30°C。",
        "AI Agent": "AI Agent 是能自主感知环境、做出决策、执行动作的智能系统。"
                   "ReAct 是核心范式之一, 交替进行 Reasoning 和 Acting。",
        "特斯拉": "特斯拉(TSLA) 最新股价 $278.90, 涨幅 3.2%。",
        "DeepSeek": "DeepSeek 是深度求索公司开发的大语言模型系列, "
                    "API 兼容 OpenAI 格式, 以高性能和低成本著称。",
    }
    for key, value in knowledge.items():
        if key in query:
            return value
    return f"关于'{query}'的搜索结果: 这是一个受关注的话题。"


def calculator(expression: str) -> str:
    """安全计算。"""
    try:
        allowed = set("0123456789+-*/.() ^")
        if not all(c in allowed for c in expression):
            return f"错误: 包含不允许的字符"
        result = eval(expression, {"__builtins__": {}}, {})
        return f"{expression} = {result}"
    except Exception as e:
        return f"计算错误: {e}"


TOOL_MAP = {"web_search": web_search, "calculator": calculator}


# ── ReAct Agent (LLMTracer 自动追踪版) ─────────────────────

@trace_agent(agent_name="deepseek_react_agent", model="deepseek-chat")
def react_agent(query: str):
    """ReAct Agent: DeepSeek 做大脑, LLMTracer 自动记录每一步。"""

    client = LLMClient()
    tracer = LLMTracer(chat_fn=client.chat_with_tools)

    messages = [
        {
            "role": "system",
            "content": (
                "你是一个能使用工具的智能助手。"
                "需要实时信息或计算时调用工具, 知识性问题可以直接回答。"
                "用中文回复。"
            ),
        },
        {"role": "user", "content": query},
    ]

    for _ in range(5):  # 最多 5 轮, 防止死循环
        # ── 一行: 调 LLM + 自动记录 Reasoning ──
        response = tracer.step(messages, TOOLS)

        # 如果 LLM 直接回答 → 结束
        if response["content"] and not response["tool_calls"]:
            print(f"\n[Agent] {response['content'][:200]}...")
            return

        # 如果 LLM 要调工具 → 执行工具 + 自动记录 Acting/Observing
        if response["tool_calls"]:
            for tc in response["tool_calls"]:
                tool_name = tc["name"]
                tool_args = tc["arguments"]

                # ── 一行: 执行工具 + 自动记录 Acting + Observing ──
                result_text = tracer.execute(tool_name, tool_args, TOOL_MAP)

                print(f"[Tool] {tool_name}({tool_args}) → {result_text[:80]}...")

                # 加入消息历史, 供下一轮推理
                messages.append({
                    "role": "assistant",
                    "content": response["content"],
                    "tool_calls": [{
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["arguments"]),
                        },
                    }],
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result_text,
                })

    print("\n[Agent] 达到最大轮数, 基于已有信息回答...")

    # 最后一轮: 让 LLM 基于已有信息总结
    final = client.chat(messages + [
        {"role": "user", "content": "请基于以上信息, 用中文简洁回答。"}
    ])
    print(f"\n[Agent] {final['content'][:200]}...")


# ── 运行 ────────────────────────────────────────────────────

def main():
    import httpx

    print("=" * 60)
    print("AgentTrace + DeepSeek: LLMTracer 自动追踪版")
    print("=" * 60)

    question = "帮我查一下北京今天的天气，然后算一下 28 乘以 3.5 是多少"
    print(f"\n用户: {question}")

    trace = react_agent(question)

    print(f"\n── Trace 摘要 ──")
    print(f"Trace ID:      {trace.id}")
    print(f"ReAct 循环:    {trace.react_cycles} 轮")
    print(f"决策路径:      {trace.decision_path}")
    print(f"调用工具:      {trace.tools_called}")
    print(f"总 Token:      {trace.total_tokens}")  # 现在不会是 0 了!
    print(f"总耗时:        {trace.total_time_ms:.0f}ms")
    print(f"总费用(估算):  ${trace.total_cost:.4f}")

    # 显示每步的关键信息
    print(f"\n── 逐步详情 ──")
    for step in trace.steps:
        if step.decision:
            tool_info = f" → 选工具: {step.decision.chosen_tool}" if step.decision.chosen_tool else " → 直接回答"
            print(f"  [{step.sequence}] R | Token:{step.token_used:>5} | {step.decision.thought[:80]}...{tool_info}")
        elif step.action:
            status = "FAIL" if step.action.error else "OK"
            print(f"  [{step.sequence}] A | {step.action.tool_name}({step.action.latency_ms}ms) [{status}]")
        elif step.observation:
            print(f"  [{step.sequence}] O | {step.observation[:80]}...")

    # 上传 Engine
    try:
        r = httpx.post("http://localhost:8000/api/traces",
                       json=trace.model_dump(mode="json"), timeout=5)
        if r.status_code == 201:
            print(f"\n✓ Trace 已上传 Engine: http://localhost:8000/api/traces/{trace.id}")
    except Exception:
        print(f"\nEngine 未启动, Trace 仅在内存中")


if __name__ == "__main__":
    main()
