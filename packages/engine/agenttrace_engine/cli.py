"""AgentTrace CLI — 一行命令启动监控后台。

用法:
    agenttrace start              → 启动 Engine (端口 8000)
    agenttrace start --port 8080  → 自定义端口
    agenttrace status             → 查看服务状态

安装后可用:
    pip install -e .
    agenttrace start
"""

import argparse
import sys


def cmd_start(args):
    """启动 AgentTrace Engine 服务。"""
    import uvicorn

    port = args.port
    print(f"""
╔══════════════════════════════════════════╗
║       AgentTrace Engine v0.1.0          ║
║       Agent 决策轨迹存储与查询服务        ║
╠══════════════════════════════════════════╣
║  API:   http://localhost:{port}          ║
║  Docs:  http://localhost:{port}/docs     ║
║  Dashboard: http://localhost:3000        ║
╚══════════════════════════════════════════╝
""")
    uvicorn.run(
        "agenttrace_engine.api.server:app",
        host="0.0.0.0",
        port=port,
        reload=args.reload,
    )


def cmd_status(args):
    """查看 Engine 服务状态。"""
    import httpx
    port = args.port
    try:
        r = httpx.get(f"http://localhost:{port}/", timeout=3)
        data = r.json()
        print(f"Engine 运行中 (v{data['version']})")
        print(f"  API:   http://localhost:{port}")
        print(f"  Docs:  http://localhost:{port}/docs")
    except Exception:
        print(f"Engine 未运行 (端口 {port})")
        print(f"  启动: agenttrace start")


def main():
    parser = argparse.ArgumentParser(
        prog="agenttrace",
        description="AgentTrace — Agent 决策调试工具"
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # agenttrace start
    start_parser = subparsers.add_parser("start", help="启动 Engine 服务")
    start_parser.add_argument("--port", type=int, default=8000, help="端口 (默认 8000)")
    start_parser.add_argument("--reload", action="store_true", help="开发模式热重载")
    start_parser.set_defaults(func=cmd_start)

    # agenttrace status
    status_parser = subparsers.add_parser("status", help="查看服务状态")
    status_parser.add_argument("--port", type=int, default=8000, help="端口 (默认 8000)")
    status_parser.set_defaults(func=cmd_status)

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
