"""端到端验证: SDK 采集 → HTTP 上传 Engine → 查询。

流程:
    1. 启动 Engine 服务 (后台)
    2. SDK 装饰器采集 Trace
    3. httpx 把 Trace JSON POST 到 Engine
    4. GET 查回来, 验证数据完整
"""

import subprocess
import time
import sys

import httpx

# 把 SDK 和 Engine 加入路径
sys.path.insert(0, "D:/agenttrace/packages/sdk")
sys.path.insert(0, "D:/agenttrace/packages/engine")

from agenttrace_sdk import ToolCandidate, observe, reason, timed_act, trace_agent


# ── 模拟工具 ──────────────────────────────────────────────

def search_web(query: str) -> str:
    time.sleep(0.02)
    return f"搜索结果: 关于'{query}'的3条信息..."


def summarize(text: str) -> str:
    time.sleep(0.03)
    return f"摘要: {text[:50]}..."


# ── Agent ───────────────────────────────────────────────

@trace_agent(agent_name="research_bot", model="deepseek-chat")
def research_agent(topic: str):
    """搜索某个话题并生成摘要。"""

    reason(
        thought=f"需要搜索'{topic}'相关的信息",
        tool_candidates=[
            ToolCandidate(name="web_search", score=0.95, reason="获取最新信息"),
        ],
        chosen_tool="web_search",
        decision_rationale="web_search 是最直接的搜索工具",
    )

    with timed_act("web_search", params={"query": topic}) as ta:
        result = search_web(topic)
        ta.result = result

    observe(f"搜索完成, 获取到关于'{topic}'的信息")

    reason(
        thought="搜索到了原始信息, 需要生成简洁摘要",
        tool_candidates=[
            ToolCandidate(name="summarizer", score=0.90, reason="文本摘要工具"),
        ],
        chosen_tool="summarizer",
        decision_rationale="summarizer 专门做文本摘要",
    )

    with timed_act("summarizer", params={"text": result}) as ta:
        summary = summarize(result)
        ta.result = summary

    observe(f"摘要生成完成")


# ── 主流程 ────────────────────────────────────────────────

def main():
    ENGINE_URL = "http://localhost:8000"

    # 1. 启动 Engine 服务
    print("[1/4] 启动 Engine 服务...")
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn",
         "agenttrace_engine.api.server:app",
         "--host", "0.0.0.0", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(2)  # 等服务器启动

    try:
        # 2. 执行 Agent → 得到 Trace
        print("[2/4] 执行 Agent 并采集 Trace...")
        trace = research_agent("AI Agent 发展趋势")
        print(f"  → Trace ID: {trace.id}")
        print(f"  → Steps: {len(trace.steps)}")
        print(f"  → 决策路径: {trace.decision_path}")

        # 3. POST 上传到 Engine
        print("[3/4] 上传 Trace 到 Engine...")
        response = httpx.post(
            f"{ENGINE_URL}/api/traces",
            json=trace.model_dump(mode="json"),
        )
        print(f"  → 状态: {response.status_code}")
        print(f"  → 响应: {response.json()}")

        # 4. GET 查回来验证
        print("[4/4] 从 Engine 查询 Trace...")
        response = httpx.get(f"{ENGINE_URL}/api/traces/{trace.id}")
        assert response.status_code == 200, f"查询失败: {response.status_code}"
        data = response.json()
        print(f"  → 查回 Steps: {len(data['steps'])}")
        print(f"  → 查回工具: {data['tools_called']}")

        # 列列表
        response = httpx.get(f"{ENGINE_URL}/api/traces?limit=10")
        print(f"\n  Engine 中总共 {len(response.json())} 条 Trace")

        print("\n✓ 端到端验证通过!")

    finally:
        server.terminate()
        server.wait()


if __name__ == "__main__":
    main()
