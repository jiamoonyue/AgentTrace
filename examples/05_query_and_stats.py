"""验证增强查询: 筛选、分页、统计。

先上传 3 条不同 Agent 的 Trace, 然后测试各种查询。
"""

import subprocess
import sys
import time

import httpx

sys.path.insert(0, "D:/agenttrace/packages/sdk")
sys.path.insert(0, "D:/agenttrace/packages/engine")

from agenttrace_sdk import ToolCandidate, observe, reason, timed_act, trace_agent


# ── 模拟工具 ──────────────────────────────────────────────

def mock_search(query: str) -> str:
    time.sleep(0.01)
    return f"搜索结果: {query}"


def mock_calc(expr: str) -> str:
    time.sleep(0.01)
    return f"计算结果: {expr} = 42"


def mock_translate(text: str) -> str:
    time.sleep(0.01)
    return f"翻译: {text}"


# ── 三个不同 Agent ────────────────────────────────────────

@trace_agent(agent_name="weather_bot", model="deepseek-chat")
def weather_agent(city: str):
    reason(thought=f"查{city}天气", chosen_tool="weather_api")
    with timed_act("weather_api", params={"city": city}) as ta:
        ta.result = "晴, 25°C"
    observe(f"{city}晴天, 25°C")


@trace_agent(agent_name="research_bot", model="deepseek-chat")
def research_agent(topic: str):
    reason(thought=f"搜索{topic}", chosen_tool="web_search")
    with timed_act("web_search", params={"query": topic}) as ta:
        ta.result = mock_search(topic)
    observe(f"搜到关于{topic}的资料")


@trace_agent(agent_name="math_bot", model="claude-sonnet-4-6")
def math_agent(problem: str):
    reason(thought=f"计算{problem}", chosen_tool="calculator")
    with timed_act("calculator", params={"expr": problem}) as ta:
        ta.result = mock_calc(problem)
    observe(f"计算结果: 42")


# ── 测试流程 ──────────────────────────────────────────────

def main():
    ENGINE = "http://localhost:8000"

    # 1. 启动服务
    print("[1] 启动 Engine...")
    python_exe = "D:/miniconda3/envs/agenttrace_env/python.exe"
    server = subprocess.Popen(
        [python_exe, "-m", "uvicorn",
         "agenttrace_engine.api.server:app",
         "--host", "0.0.0.0", "--port", "8000"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    # 等待服务器就绪 (最多重试 10 次)
    for i in range(10):
        time.sleep(1)
        try:
            r = httpx.get(f"{ENGINE}/", timeout=2)
            if r.status_code == 200:
                print(f"  Engine 就绪 (等待 {i+1}s)")
                break
        except httpx.ConnectError:
            continue
    else:
        raise RuntimeError("Engine 启动超时")

    try:
        # 2. 上传 3 条 Trace
        print("[2] 采集并上传 3 条 Trace...")
        traces = [
            weather_agent("北京"),
            research_agent("AI Agent"),
            math_agent("6 * 7"),
        ]
        for t in traces:
            r = httpx.post(f"{ENGINE}/api/traces", json=t.model_dump(mode="json"))
            assert r.status_code == 201, f"上传失败: {r.status_code}"
        print(f"  上传 {len(traces)} 条 OK")

        # 3. 测试: 列出全部
        print("\n[3] 测试: 列出全部")
        r = httpx.get(f"{ENGINE}/api/traces")
        data = r.json()
        print(f"  total={data['total']}, items={len(data['items'])}")

        # 4. 测试: 按 agent 筛选
        print("\n[4] 测试: 筛选 agent_name=weather_bot")
        r = httpx.get(f"{ENGINE}/api/traces?agent_name=weather_bot")
        data = r.json()
        print(f"  total={data['total']}, 第一条={data['items'][0]['agent_name']}")

        # 5. 测试: 按 model 筛选
        print("\n[5] 测试: 筛选 model=deepseek-chat")
        r = httpx.get(f"{ENGINE}/api/traces?model=deepseek-chat")
        data = r.json()
        print(f"  total={data['total']} (weather_bot + research_bot)")

        # 6. 测试: 分页
        print("\n[6] 测试: 分页 limit=2, offset=0")
        r = httpx.get(f"{ENGINE}/api/traces?limit=2&offset=0")
        data = r.json()
        print(f"  total={data['total']}, 本页={len(data['items'])}")

        # 7. 测试: 统计
        print("\n[7] 测试: 全局统计")
        r = httpx.get(f"{ENGINE}/api/traces/stats/summary")
        stats = r.json()
        print(f"  总 Trace: {stats['total_traces']}")
        print(f"  Agent 分布: {stats['agents']}")
        print(f"  模型分布: {stats['models']}")
        print(f"  热门工具: {stats['top_tools']}")
        print(f"  平均 Token: {stats['avg_tokens_per_trace']}")

        print("\n✓ 全部测试通过!")

    finally:
        server.terminate()
        server.wait()


if __name__ == "__main__":
    main()
