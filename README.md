<div align="center">

<img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python" />
<img src="https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI" />
<img src="https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black" alt="React" />
<img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License" />
<img src="https://img.shields.io/badge/version-0.1.0-blue?style=flat-square" alt="Version" />

<br/>
<br/>

```
 █████╗  ██████╗ ███████╗███╗   ██╗████████╗██████╗ ██████╗  █████╗  ██████╗███████╗
██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝██╔══██╗██╔══██╗██╔══██╗██╔════╝██╔════╝
███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║   ██████╔╝██████╔╝███████║██║     █████╗
██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║   ██╔══██╗██╔══██╗██╔══██║██║     ██╔══╝
██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║   ██║  ██║██║  ██║██║  ██║╚██████╗███████╗
╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚══════╝
```

### Chrome DevTools for AI Agents

**让每一个 Agent 决策都透明、可追溯、可调试**

[Quick Start](#quick-start) · [Features](#features) · [Architecture](#architecture) · [API](#api-reference) · [Examples](#examples) · [Roadmap](#roadmap)

</div>

---

## Table of Contents

- [What is AgentTrace?](#what-is-agenttrace)
- [The Problem It Solves](#the-problem-it-solves)
- [Quick Start](#quick-start)
- [Features](#features)
  - [SDK — Trace Collection](#1-sdk--trace-collection)
  - [Engine — Storage & Query API](#2-engine--storage--query-api)
  - [Dashboard — Visualization](#3-dashboard--visualization)
  - [Debug Agent — AI-Powered Diagnosis](#4-debug-agent--ai-powered-diagnosis)
  - [CLI — Command Line Tool](#5-cli--command-line-tool)
- [Architecture](#architecture)
- [Core Concepts](#core-concepts)
  - [ReAct Trace Data Model](#react-trace-data-model)
  - [Decision Path](#decision-path)
- [API Reference](#api-reference)
- [Examples](#examples)
- [Tech Stack](#tech-stack)
- [Roadmap](#roadmap)
- [Development](#development)
- [License](#license)

---

## What is AgentTrace?

**AgentTrace** is an open-source observability and debugging tool for AI Agents. It captures every decision an agent makes — what it thought, which tools it considered, why it chose one over another, how long each action took, and how many tokens were consumed — then visualizes the entire decision chain as an interactive tree in a web dashboard.

Think of it as **Chrome DevTools for AI Agents**: when your agent behaves unexpectedly, rather than staring at raw logs, you open AgentTrace and see exactly where and why it went wrong.

### How It Works (30 seconds)

```python
# Step 1: Add 2 lines to your agent
from agenttrace_sdk import trace_agent, LLMTracer

@trace_agent(agent_name="travel_bot", model="deepseek-chat")
def my_agent(query):
    tracer = LLMTracer(chat_fn=client.chat_with_tools)
    response = tracer.step(messages, TOOLS)           # LLM call + auto-log
    result = tracer.execute("tool", args, TOOL_MAP)    # tool call + auto-log

# Step 2: Run
trace = my_agent("Plan a trip to Tokyo")

# Step 3: Open http://localhost:3000 — see the decision tree
```

---

## The Problem It Solves

| Without AgentTrace | With AgentTrace |
|---|---|
| "Why did the agent call `web_search` 5 times?" — no idea | Decision tree shows every call with timestamps and results |
| "Which step consumed the most tokens?" — can't tell | Per-step token breakdown, total cost estimation |
| "The agent failed. Where should I fix the prompt?" — guesswork | Debug Agent pinpoints the failing step and suggests prompt changes |
| "Is my ReAct loop actually working?" — trust the LLM output | `decision_path: R→A→O→R→A→O→R` — verifiable at a glance |
| "I changed the prompt. Is it better now?" — gut feeling | Side-by-side A/B comparison with diff metrics |
| "Agent X vs Agent Y on the same task?" — run both and squint at logs | `GET /api/traces/compare?a=X&b=Y` — automated comparison |

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- A DeepSeek API key (or any OpenAI-compatible API)

### Installation

```bash
# Clone
git clone https://github.com/yourname/agenttrace.git
cd agenttrace

# Install Python packages
pip install -e packages/sdk -e packages/engine

# Install Dashboard dependencies
cd packages/dashboard && npm install && cd ../..

# Configure your API key
cp .env.example .env
# Edit .env: DEEPSEEK_API_KEY=sk-your-key-here
```

### Start Services

```bash
# Terminal 1: Start the Engine (storage + API)
agenttrace start

# Terminal 2: Start the Dashboard (React frontend)
cd packages/dashboard && npm run dev
```

Open **http://localhost:3000** — the dashboard is ready to receive traces.

### Run Your First Trace

```bash
# Terminal 3: Run the travel agent example
python examples/travel_agent_demo.py

# Refresh the dashboard — your first trace appears
```

---

## Features

### 1. SDK — Trace Collection

The Python SDK provides the instrumentation layer. Agents call these functions during execution, and the SDK automatically structures every decision into a traceable format.

#### Decorator Mode (recommended)

```python
from agenttrace_sdk import trace_agent, LLMTracer

@trace_agent(agent_name="research_bot", model="deepseek-chat")
def research_agent(query):
    tracer = LLMTracer(chat_fn=client.chat_with_tools)
    messages = [{"role": "system", "content": "You are a research assistant."},
                {"role": "user", "content": query}]

    for _ in range(5):
        response = tracer.step(messages, TOOLS)           # Auto-records REASONING + tokens
        if not response["tool_calls"]:
            return response["content"]                     # LLM answered directly
        for tc in response["tool_calls"]:
            result = tracer.execute(tc["name"], tc["arguments"], TOOL_MAP)
            # Auto-records ACTING (with latency) + OBSERVING
```

#### Manual Mode (full control)

```python
from agenttrace_sdk import trace_agent, reason, act, observe, timed_act

@trace_agent(agent_name="bot", model="gpt-4")
def my_agent(query):
    reason(thought="Need to search", chosen_tool="web_search")

    with timed_act("web_search", params={"q": query}) as ta:
        result = search(query)
        ta.result = result           # Auto-calculates latency_ms

    observe(f"Found: {result}")
```

#### LangChain Auto-Callback (zero-code integration)

```python
from agenttrace_sdk.callbacks.langchain import AgentTraceCallback
from langchain.agents import AgentExecutor

callback = AgentTraceCallback(agent_name="lc_bot", model="gpt-4")
executor = AgentExecutor(agent=agent, tools=tools, callbacks=[callback])
executor.invoke({"input": "What's the weather?"})

trace = callback.trace  # Full Trace object, no manual instrumentation needed
```

#### Key SDK Capabilities

| Feature | API | What It Records |
|---------|-----|-----------------|
| LLM reasoning | `tracer.step()` | thought, chosen tool, tool candidates with scores, rejected alternatives, prompt snapshot, token count |
| Tool execution | `tracer.execute()` / `timed_act` | tool name, params, result, latency (auto-timed), error (auto-captured) |
| Observation | `observe()` | interpretation of tool output |
| Self-evaluation | `evaluate()` | confidence score (0-1) |
| Trace lifecycle | `@trace_agent` + `trace.finalize()` | auto-creates Trace, assigns step sequence numbers, calculates summary stats |

---

### 2. Engine — Storage & Query API

The Engine is a FastAPI service that persists traces to SQLite (or PostgreSQL) and provides a REST API for querying.

#### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/traces` | Upload a trace |
| `GET` | `/api/traces` | List traces with filtering & pagination |
| `GET` | `/api/traces/{id}` | Get full trace with all steps |
| `GET` | `/api/traces/{id}/diagnose` | AI-powered diagnosis report |
| `GET` | `/api/traces/{id}/export?format=csv` | Export trace as CSV (Excel-ready) |
| `GET` | `/api/traces/{id}/export?format=json` | Export trace as JSON |
| `GET` | `/api/traces/compare?a=X&b=Y` | Side-by-side comparison of two traces |
| `GET` | `/api/traces/stats/summary` | Global stats: agent distribution, model usage, top tools |
| `DELETE` | `/api/traces/{id}` | Delete a trace |

#### Query Filters

```bash
# Filter by agent name
GET /api/traces?agent_name=travel_bot

# Filter by model
GET /api/traces?model=deepseek-chat

# Pagination
GET /api/traces?offset=0&limit=20

# Combined
GET /api/traces?agent_name=bot&model=gpt-4&limit=10
```

#### Start / Status

```bash
agenttrace start              # Start engine on port 8000
agenttrace start --port 8080  # Custom port
agenttrace start --reload     # Hot-reload for development
agenttrace status             # Check if engine is running
```

Swagger docs available at **http://localhost:8000/docs**.

---

### 3. Dashboard — Visualization

A React-based web interface for exploring agent traces.

#### Three-Panel Layout

```
┌──────────────────────────────────────────────────────────────┐
│  AgentTrace                    Traces: 12  Tokens: 45,230    │
├──────────────┬──────────────────────────┬────────────────────┤
│              │                          │                    │
│  Trace List  │   Decision Tree          │   Step Details     │
│  (left)      │   (center)               │   (right)          │
│              │                          │                    │
│  Filter bar  │   R ──→ A ──→ O         │   · Thought        │
│  [-] agent   │   │                      │   · Tool candidates│
│  Trace 1     │   └──→ A ──→ O ──→ R    │   · Chosen tool    │
│  Trace 2     │         (failed)    │    │   · Rejected alts  │
│  Trace 3     │                     └─→  │   · Token count    │
│              │   [ReactFlow]            │   · Latency        │
│  ← 1/3 →    │   draggable · zoomable   │   · Confidence bar  │
│              │   nodes color-coded      │   · Raw JSON       │
│              │                          │                    │
│              ├──────────────────────────┤                    │
│              │  ◉─◉─◉─◉─◉─◉─◉─◉─◉    │                    │
│              │  Timeline Replay Slider  │                    │
└──────────────┴──────────────────────────┴────────────────────┘
```

#### Features

- **Trace List**: Filter by agent name, paginated, click to select
- **Decision Tree**: ReactFlow-powered visualization with color-coded nodes (R=blue, A=green, O=yellow, E=purple), animated edges, zoom/pan/drag
- **Step Details**: On node click — full thought content, candidate tools with confidence scores, rejected alternatives, tool parameters, results, errors, confidence bar
- **Timeline Replay**: Slider at bottom — drag to replay decisions step by step, future steps are greyed out
- **AI Diagnosis**: Purple "AI Diagnose" button → Debug Agent analyzes the trace and shows issues inline (health score, root causes, fix suggestions)
- **Export**: One-click CSV download for any trace

---

### 4. Debug Agent — AI-Powered Diagnosis

The Debug Agent is a meta-agent: **an agent that analyzes other agents' traces** to find bugs and suggest improvements. It operates in two layers:

#### Layer 1: Algorithmic Analyzer (no LLM required)

Detects 6 anomaly patterns automatically:

| Pattern | Detection Rule | Severity |
|---------|---------------|----------|
| **Repeated calls** | Same tool invoked 3+ consecutive times | `high` |
| **Tool failures** | `action.error` is not null | `high` |
| **Low confidence** | `confidence < 0.5` | `medium` |
| **Missing fallback** | Failed tool with no subsequent fallback attempt | `medium` |
| **Token waste** | Single step consumes >50% of total tokens | `medium` |
| **High latency** | Tool call exceeds 3× average or 2s threshold | `low` |

#### Layer 2: LLM-Powered Diagnosis

The analyzer output is sent to an LLM with a structured prompt. The LLM returns a JSON report:

```json
{
  "diagnosis": "Agent stuck in web_search loop: 4 identical calls with no stopping condition",
  "severity": "critical",
  "score": 35,
  "root_causes": [
    "Missing stop condition in agent prompt",
    "No max_retries configured for web_search tool"
  ],
  "prompt_suggestions": [
    "Add to system prompt: 'If a tool returns similar results 3 times, summarize and stop'"
  ],
  "architecture_suggestions": [
    "Add retry limit to tool configuration",
    "Implement early-stopping based on result similarity"
  ]
}
```

#### API & Dashboard Integration

```bash
# API
GET /api/traces/{id}/diagnose

# Dashboard: click "AI Diagnose" button on any trace
```

The health score and severity badge appear directly in the dashboard header. Individual issues are shown as colored chips below the info bar.

---

### 5. CLI — Command Line Tool

```bash
$ agenttrace --help

usage: agenttrace {start,status}

Commands:
  start     Start the Engine server
  status    Check if Engine is running

Options:
  start --port 8080     Custom port (default: 8000)
  start --reload        Hot-reload for development
  status --port 8080    Check specific port
```

---

## Architecture

```
                          ┌────────────────────┐
                          │    Your Agent Code  │
                          │                    │
                          │  @trace_agent(...) │
                          │  tracer.step()     │
                          │  tracer.execute()  │
                          └────────┬───────────┘
                                   │ import agenttrace_sdk
                                   ▼
┌──────────────────────────────────────────────────────────────┐
│                       AgentTrace                             │
│                                                              │
│  ┌─────────────────┐  ┌──────────────────┐  ┌─────────────┐ │
│  │   SDK (Python)   │  │ Engine (FastAPI)  │  │  Dashboard  │ │
│  │                  │  │                  │  │  (React)    │ │
│  │  models.py       │  │  api/server.py   │  │             │ │
│  │  decorators.py   │  │  routes/         │  │  TraceList  │ │
│  │  tracer.py       │  │  storage/        │  │  DecisTree  │ │
│  │  callbacks/      │  │  llm/            │  │  StepDetail │ │
│  │                  │  │  debug_agent/    │  │  Timeline   │ │
│  │                  │  │                  │  │             │ │
│  │  Data Collection │──▶  Storage + API   │◀─│  Browser    │ │
│  │  Trace modeling  │  │  SQLite/PG       │  │  :3000      │ │
│  │  Auto-instrument │  │  :8000           │  │             │ │
│  └─────────────────┘  └──────────────────┘  └─────────────┘ │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### Data Flow

```
Agent executes ReAct cycle
        │
        ▼
tracer.step() ──→ reason() ──→ TraceStep(REASONING) ──┐
tracer.execute() ──→ timed_act() ──→ TraceStep(ACTING)  ├──→ Trace ──→ Engine
                    observe() ──→ TraceStep(OBSERVING) ──┘         │
                                                                    ▼
                                                              SQLite / PostgreSQL
                                                                    │
                                                                    ▼
                                                              Dashboard :3000
```

---

## Core Concepts

### ReAct Trace Data Model

AgentTrace models every agent execution as a **ReAct trace** — a sequence of Reasoning → Acting → Observing steps:

```
Trace                           Complete execution record
├── id                          Unique trace identifier (trace_xxxxxxxxxxxx)
├── task                        User query or task description
├── agent_name / model          Which agent, which LLM
├── start_time / end_time       Execution boundaries
├── total_tokens / total_cost   Aggregate metrics
├── tools_called                List of tools invoked
├── decision_path               Compact representation (e.g., "R→A→O→R→A→O→R")
├── react_cycles                Count of complete R→A→O cycles
│
└── steps: list[TraceStep]
    │
    ├── TraceStep (REASONING)
    │   ├── timestamp
    │   ├── token_used
    │   └── Decision
    │       ├── thought                     What the agent was thinking
    │       ├── tool_candidates[]           All tools considered
    │       │   └── ToolCandidate {name, score, reason}
    │       ├── rejected_alternatives[]     Rejected approaches (free text)
    │       ├── chosen_tool                 Final selection
    │       ├── decision_rationale          Why this choice
    │       ├── prompt_snapshot             Full prompt at decision time
    │       └── context_window_usage_pct    Context window pressure
    │
    ├── TraceStep (ACTING)
    │   └── Action
    │       ├── tool_name                   Which tool
    │       ├── tool_type                   "function" | "mcp" | "rest_api"
    │       ├── params                      Tool arguments
    │       ├── result_snippet              Tool output (truncated)
    │       ├── latency_ms                  Auto-measured duration
    │       └── error                       Exception if failed
    │
    ├── TraceStep (OBSERVING)
    │   └── observation                     Interpretation of tool result
    │
    └── TraceStep (EVALUATING)
        └── confidence                      Self-assessed confidence (0.0-1.0)
```

### Decision Path

The `decision_path` is a compact string representing the entire ReAct execution. Each character maps to a step phase:

| Char | Phase | Meaning |
|:----:|-------|---------|
| `R` | Reasoning | Agent thought about what to do |
| `A` | Acting | Agent called a tool |
| `O` | Observing | Agent interpreted the tool's output |
| `E` | Evaluating | Agent self-assessed confidence |

Example: `R→A→O→R→A→O→R` means the agent went through 2 complete ReAct cycles, then did a final reasoning step to compose the answer.

---

## API Reference

### Upload a Trace

```http
POST /api/traces
Content-Type: application/json

{
  "id": "trace_abc123",
  "task": "What's the weather in Beijing?",
  "agent_name": "weather_bot",
  "model": "deepseek-chat",
  "steps": [
    {
      "id": "step_001", "sequence": 1, "phase": "reasoning",
      "decision": { "thought": "Need weather API", "chosen_tool": "weather_api" }
    },
    {
      "id": "step_002", "sequence": 2, "phase": "acting",
      "action": { "tool_name": "weather_api", "params": {"city":"Beijing"}, "latency_ms": 320 }
    }
  ],
  "start_time": "2025-06-15T10:00:00",
  "total_tokens": 850
}
```

**Response:** `201 Created`
```json
{"status": "ok", "trace_id": "trace_abc123"}
```

### List Traces

```http
GET /api/traces?agent_name=weather_bot&model=deepseek-chat&offset=0&limit=20
```

**Response:** `200 OK`
```json
{
  "total": 42,
  "offset": 0,
  "limit": 20,
  "items": [
    {
      "id": "trace_abc123",
      "task": "What's the weather in Beijing?",
      "agent_name": "weather_bot",
      "model": "deepseek-chat",
      "start_time": "2025-06-15T10:00:00",
      "total_tokens": 850,
      "tools_called": "weather_api",
      "step_count": 5
    }
  ]
}
```

### AI Diagnosis

```http
GET /api/traces/{id}/diagnose
```

**Response:** `200 OK`
```json
{
  "analysis": {
    "summary": {
      "health": "warning",
      "issue_count": 2
    },
    "issues": [
      {
        "type": "repeated_calls",
        "severity": "high",
        "description": "Tool 'web_search' called 3+ consecutive times",
        "suggestion": "Add stop condition to prompt"
      }
    ]
  },
  "llm_report": {
    "diagnosis": "Agent stuck in web_search loop...",
    "severity": "critical",
    "score": 35,
    "root_causes": ["..."],
    "prompt_suggestions": ["..."]
  }
}
```

### Compare Two Traces

```http
GET /api/traces/compare?a=trace_001&b=trace_002
```

**Response:** `200 OK`
```json
{
  "a": { "total_tokens": 850, "total_steps": 5, "decision_path": "R→A→O→R" },
  "b": { "total_tokens": 1200, "total_steps": 8, "decision_path": "R→A→O→R→A→O→R" },
  "diff": {
    "tokens": 350,
    "steps": 3,
    "tools_a_only": [],
    "tools_b_only": ["web_search"],
    "decision_path_same": false
  }
}
```

### Export

```http
GET /api/traces/{id}/export?format=csv
```

**Response:** `200 OK` — CSV file with columns: sequence, phase, thought, tool, params, result, latency_ms, confidence, token_used

### Global Stats

```http
GET /api/traces/stats/summary
```

**Response:** `200 OK`
```json
{
  "total_traces": 156,
  "total_tokens": 245000,
  "avg_tokens_per_trace": 1570.5,
  "avg_time_ms_per_trace": 3200.0,
  "agents": {"weather_bot": 80, "travel_bot": 76},
  "models": {"deepseek-chat": 156},
  "top_tools": [
    {"tool": "web_search", "count": 230},
    {"tool": "weather_api", "count": 180}
  ]
}
```

---

## Examples

All examples are in the `examples/` directory:

| File | Description | Requires API? |
|------|-------------|:---:|
| `01_basic_trace.py` | Manually create a Trace with TraceSteps | No |
| `02_decorator_trace.py` | `@trace_agent` decorator with mock ReAct | No |
| `03_timed_act.py` | Auto-timing with `timed_act` context manager | No |
| `04_sdk_to_engine.py` | End-to-end: SDK → POST to Engine → GET back | No |
| `05_query_and_stats.py` | Filter, paginate, and stats queries | No |
| `06_deepseek_agent.py` | Real ReAct Agent powered by DeepSeek | Yes |
| `travel_agent_demo.py` | Complete travel planner: flights + weather + attractions | Yes |
| `test_debug_agent.py` | Debug Agent diagnosis on a buggy trace | Yes |

### Example: Travel Agent Output

```
User: 我计划6月15日从北京去三亚旅游3天

Agent → search_flights(北京→三亚, 6/15) → 2 flights found
Agent → check_weather(三亚) → 32°C, sunny
Agent → get_attractions(三亚) → 亚龙湾(4.8) 天涯海角(4.5) 南山寺(4.6)
Agent → Generates complete 3-day itinerary with flight table and weather tips

Trace: 8 steps, 2067 tokens, R→A→O→A→O→A→O→R
```

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **SDK** | Python 3.11+, Pydantic v2, contextvars | Data models, decorators, auto-tracing |
| **Engine** | FastAPI, SQLAlchemy, Uvicorn | REST API, ORM, async server |
| **Storage** | SQLite (default), PostgreSQL-ready | Trace persistence |
| **Dashboard** | React 18, Vite, ReactFlow, TailwindCSS | Interactive visualization |
| **LLM Client** | httpx, OpenAI-compatible API | DeepSeek/OpenAI/Claude/all OpenAI-compatible |
| **CLI** | Python argparse | `agenttrace start` / `agenttrace status` |
| **Packaging** | Hatchling, pip editable installs | `pip install agenttrace` |

---

## Roadmap

- [x] SDK: Data models (Trace, TraceStep, Decision, Action)
- [x] SDK: `@trace_agent` decorator + `reason()`/`act()`/`observe()`
- [x] SDK: `timed_act` context manager (auto-timing)
- [x] SDK: `LLMTracer` (auto-trace LLM calls)
- [x] Engine: FastAPI + SQLite + CRUD
- [x] Engine: Filtering, pagination, stats
- [x] Engine: Export (JSON/CSV)
- [x] Engine: A/B comparison endpoint
- [x] Dashboard: React + ReactFlow decision tree
- [x] Dashboard: Three-panel layout (list / tree / detail)
- [x] Dashboard: Timeline replay slider
- [x] Dashboard: AI diagnosis integration
- [x] CLI: `agenttrace start` / `agenttrace status`
- [x] LLM Integration: DeepSeek (OpenAI-compatible)
- [x] LangChain: Auto-callback handler
- [x] Debug Agent: Algorithmic anomaly detection (6 patterns)
- [x] Debug Agent: LLM-powered diagnosis reports
- [ ] PyPI publication (`pip install agenttrace`)
- [ ] AutoGen callback integration
- [ ] Real-time streaming trace (WebSocket)
- [ ] Prompt A/B comparison UI in Dashboard
- [ ] Multi-agent topology visualization
- [ ] Alerting: Slack/email on agent failure
- [ ] PostgreSQL support for production deployments
- [ ] Docker Compose one-command setup

---

## Development

```bash
# Setup
git clone https://github.com/yourname/agenttrace.git
cd agenttrace
conda create -n agenttrace python=3.11 -y
conda activate agenttrace
pip install -e packages/sdk -e packages/engine
cd packages/dashboard && npm install && cd ../..

# Development servers
agenttrace start --reload &          # Engine (port 8000, hot-reload)
cd packages/dashboard && npm run dev # Dashboard (port 3000, HMR)

# Run tests
python examples/test_debug_agent.py  # Debug Agent test
python examples/05_query_and_stats.py # API test
```

### Project Structure

```
agenttrace/
├── README.md
├── LICENSE
├── .env.example
├── .gitignore
├── pyproject.toml
│
├── packages/
│   ├── sdk/                          # pip: agenttrace-sdk
│   │   ├── pyproject.toml
│   │   └── agenttrace_sdk/
│   │       ├── __init__.py
│   │       ├── models.py             # Trace, TraceStep, Decision, Action
│   │       ├── decorators.py         # @trace_agent, reason(), act(), timed_act
│   │       ├── tracer.py             # LLMTracer (auto-trace)
│   │       └── callbacks/
│   │           └── langchain.py      # LangChain auto-callback
│   │
│   ├── engine/                       # pip: agenttrace
│   │   ├── pyproject.toml
│   │   └── agenttrace_engine/
│   │       ├── cli.py                # agenttrace CLI
│   │       ├── api/
│   │       │   ├── server.py         # FastAPI entry point
│   │       │   └── routes/
│   │       │       └── traces.py     # All API routes (9 endpoints)
│   │       ├── storage/
│   │       │   ├── models.py         # SQLAlchemy ORM
│   │       │   └── repository.py     # Data access layer
│   │       ├── llm/
│   │       │   ├── config.py         # .env loader
│   │       │   └── client.py         # DeepSeek / OpenAI client
│   │       └── debug_agent/
│   │           ├── analyzer.py       # Anomaly detection (no LLM)
│   │           └── agent.py          # LLM diagnosis engine
│   │
│   └── dashboard/                    # npm package
│       ├── package.json
│       ├── vite.config.js
│       ├── tailwind.config.js
│       └── src/
│           ├── main.jsx
│           ├── App.jsx               # Three-panel layout + state
│           ├── api.js                # Engine API client
│           └── components/
│               ├── TraceList.jsx      # Left panel
│               ├── DecisionTree.jsx   # Center: ReactFlow + diagnosis
│               ├── StepDetail.jsx     # Right panel
│               └── TimelineSlider.jsx # Bottom: replay slider
│
└── examples/
    ├── 01_basic_trace.py
    ├── 02_decorator_trace.py
    ├── 03_timed_act.py
    ├── 04_sdk_to_engine.py
    ├── 05_query_and_stats.py
    ├── 06_deepseek_agent.py
    ├── travel_agent_demo.py
    └── test_debug_agent.py
```

---

## License

MIT © 2025

---

## Acknowledgments

AgentTrace is inspired by:

- [AgentGuide](https://github.com/adongwanai/AgentGuide) — Comprehensive AI Agent learning guide
- [LangChain](https://github.com/langchain-ai/langchain) — LLM application framework
- [ReactFlow](https://reactflow.dev/) — Node-based visualization library
- Chrome DevTools — The gold standard for debugging tools

---

<div align="center">

**Made with ❤️ for the Agent developer community**

[Report Bug](https://github.com/yourname/agenttrace/issues) · [Request Feature](https://github.com/yourname/agenttrace/issues) · [Star on GitHub](https://github.com/yourname/agenttrace)

</div>
