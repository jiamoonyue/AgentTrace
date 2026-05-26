"""
游客助手 Agent — 演示 AgentTrace 的实际使用方式。

这个文件是一个完全独立的 Agent 项目。它不依赖 AgentTrace 的源码目录，
只需要 pip install agenttrace 后就能运行。

使用方式:
    终端 1: agenttrace start          ← 启动监控后台
    终端 2: python travel_agent.py   ← 运行 Agent
    浏览器: http://localhost:3000     ← 看决策树

AgentTrace 接入只需要 3 个东西:
    1. @trace_agent 装饰器
    2. LLMTracer
    3. tracer.step() + tracer.execute()
"""

import json
import os
import sys

# ── 真实使用时, 用户只需这两行 import ──
from agenttrace_sdk import trace_agent, LLMTracer
from agenttrace_engine.llm.client import LLMClient


# ═══════════════════════════════════════════════════════════
#  以下是用户自己的业务代码 —— 旅游助手的工具和逻辑
# ═══════════════════════════════════════════════════════════

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_flights",
            "description": "搜索航班信息, 返回航班号、价格、时间",
            "parameters": {
                "type": "object",
                "properties": {
                    "from_city": {"type": "string", "description": "出发城市"},
                    "to_city": {"type": "string", "description": "目的地城市"},
                    "date": {"type": "string", "description": "日期, 格式 YYYY-MM-DD"},
                },
                "required": ["from_city", "to_city", "date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_weather",
            "description": "查询城市天气",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名"},
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_attractions",
            "description": "获取城市热门景点推荐",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名"},
                },
                "required": ["city"],
            },
        },
    },
]


def search_flights(from_city, to_city, date):
    """模拟航班搜索。可替换为真实 API。"""
    flights = {
        ("北京", "上海"): [
            {"flight": "MU5101", "time": "08:00-10:30", "price": 890},
            {"flight": "CA1835", "time": "12:00-14:20", "price": 760},
        ],
        ("北京", "三亚"): [
            {"flight": "HU7079", "time": "07:30-11:00", "price": 1520},
            {"flight": "CZ6712", "time": "14:00-17:30", "price": 1380},
        ],
    }
    key = (from_city, to_city)
    if key in flights:
        return json.dumps(flights[key], ensure_ascii=False)
    return f"找到 3 个从{from_city}到{to_city}的航班, 价格 ¥800-1500"


def check_weather(city):
    """模拟天气查询。可替换为和风天气 API。"""
    weathers = {
        "上海": "晴, 26°C, 微风, 适合出行",
        "三亚": "多云, 32°C, 海风3级, 适合海滩活动",
        "北京": "晴, 28°C, 轻度雾霾",
        "成都": "阴, 22°C, 适宜户外",
    }
    return weathers.get(city, f"{city}: 晴, 20-28°C, 适合旅游")


def get_attractions(city):
    """模拟景点推荐。可替换为携程/马蜂窝 API。"""
    attractions = {
        "上海": ["外滩 (4.8⭐)", "迪士尼乐园 (4.9⭐)", "南京路步行街 (4.5⭐)"],
        "三亚": ["亚龙湾 (4.8⭐)", "天涯海角 (4.5⭐)", "南山寺 (4.6⭐)"],
        "北京": ["故宫 (4.9⭐)", "长城 (4.8⭐)", "颐和园 (4.7⭐)"],
    }
    places = attractions.get(city, ["本地热门景点1", "本地热门景点2", "本地热门景点3"])
    return f"{city}热门景点: " + ", ".join(places)


TOOL_MAP = {
    "search_flights": search_flights,
    "check_weather": check_weather,
    "get_attractions": get_attractions,
}


# ═══════════════════════════════════════════════════════════
#  Agent 主函数 — 只有 3 行 AgentTrace 代码
# ═══════════════════════════════════════════════════════════

@trace_agent(agent_name="travel_bot", model="deepseek-chat")
def travel_agent(user_query: str):
    """旅游助手: 查航班、天气、景点, 帮用户规划行程。"""

    client = LLMClient()
    tracer = LLMTracer(chat_fn=client.chat_with_tools)  # ← 第 1 行

    messages = [
        {
            "role": "system",
            "content": (
                "你是一个专业的旅游规划助手。帮助用户查询航班、天气、景点, "
                "并给出合理的旅行建议。用中文回复, 格式清晰。"
            ),
        },
        {"role": "user", "content": user_query},
    ]

    for _ in range(5):
        response = tracer.step(messages, TOOLS)  # ← 第 2 行: 调 LLM + 自动记录

        if response["content"] and not response["tool_calls"]:
            print(f"\n[旅行助手] {response['content']}")
            return

        if response["tool_calls"]:
            for tc in response["tool_calls"]:
                tool_func = TOOL_MAP.get(tc["name"])
                result = tracer.execute(tc["name"], tc["arguments"], TOOL_MAP)  # ← 第 3 行
                print(f"[Tool] {tc['name']}({tc['arguments']}) → {result[:60]}...")

                messages.append({
                    "role": "assistant", "content": response["content"],
                    "tool_calls": [{
                        "id": tc["id"], "type": "function",
                        "function": {"name": tc["name"],
                                     "arguments": json.dumps(tc["arguments"])},
                    }],
                })
                messages.append({
                    "role": "tool", "tool_call_id": tc["id"], "content": result,
                })

    print("\n[旅行助手] 已尽力规划, 请查看建议。")


# ═══════════════════════════════════════════════════════════

def main():
    import httpx

    question = "我计划6月15日从北京去三亚旅游3天, 帮我查航班、天气和景点"

    print(f"用户: {question}\n")
    trace = travel_agent(question)

    print(f"\n── Trace: {trace.id} ──")
    print(f"  步骤: {len(trace.steps)} | 工具: {trace.tools_called}")
    print(f"  Token: {trace.total_tokens} | 耗时: {trace.total_time_ms:.0f}ms")

    # 上传到 Engine
    try:
        r = httpx.post(
            "http://localhost:8000/api/traces",
            json=trace.model_dump(mode="json"),
            timeout=5,
        )
        if r.status_code == 201:
            print(f"  ✓ 已上传 Engine → http://localhost:3000")
    except Exception:
        print(f"  Engine 未启动, 运行 'agenttrace start'")


if __name__ == "__main__":
    main()
