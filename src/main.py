"""Relationship Engine - MCP Server 入口

支持两种运行模式：
  python -m src.main              → stdio 模式（Claude Desktop 等本地 AI）
  python -m src.main --http       → HTTP 模式（远程部署，任何 AI 可调用）
"""

import os
import sys
from dotenv import load_dotenv


def main():
    load_dotenv()

    if "--http" in sys.argv:
        # HTTP 模式 — 远程部署到阿里云
        from .mcp_server import mcp
        host = os.getenv("HOST", "0.0.0.0")
        port = int(os.getenv("PORT", "8080"))
        print(f"💘 Relationship Engine MCP Server (HTTP)")
        print(f"   Listening on http://{host}:{port}")
        mcp.run(transport="streamable_http", host=host, port=port)
    else:
        # stdio 模式 — 本地 AI 客户端直连
        from .mcp_server import mcp
        mcp.run()


if __name__ == "__main__":
    main()
