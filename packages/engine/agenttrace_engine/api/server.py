"""AgentTrace Engine 服务入口。

启动:
    python -m agenttrace_engine.api.server
    # 或:
    uvicorn agenttrace_engine.api.server:app --reload

然后访问:
    http://localhost:8000/docs  → Swagger 文档 (可以在这里直接调 API)
    http://localhost:8000/api/traces → Trace 列表
"""

from fastapi import FastAPI

from agenttrace_engine.api.routes.traces import router as traces_router, set_repository
from agenttrace_engine.storage.repository import TraceRepository

app = FastAPI(
    title="AgentTrace Engine",
    description="Agent 决策轨迹存储与查询服务",
    version="0.1.0",
)

# 注册路由
app.include_router(traces_router)

# 初始化 Repository (默认用 SQLite)
# 实际部署时可以换成 PostgreSQL URL
DATABASE_URL = "sqlite:///agenttrace.db"
repo = TraceRepository(DATABASE_URL)
set_repository(repo)


@app.get("/")
def root():
    return {
        "service": "AgentTrace Engine",
        "version": "0.1.0",
        "docs": "/docs",
        "traces_api": "/api/traces",
    }


# ── 启动入口 ──────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
