"""Relationship Event OS — 入口

运行模式：
  python -m src.main              → MCP stdio 模式（Claude Desktop 等）
  python -m src.main --http       → MCP HTTP 模式（远程部署）
  python -m src.main --web        → Web 聊天模式（浏览器）
"""

import os
import sys
from dotenv import load_dotenv


def main():
    load_dotenv()

    if "--web" in sys.argv:
        import uvicorn
        host = os.getenv("HOST", "0.0.0.0")
        port = int(os.getenv("PORT", "8080"))
        print(f"Relationship Event OS — Web 模式")
        print(f"http://localhost:{port}")
        uvicorn.run("src.web_server:app", host=host, port=port, reload=True)
    elif "--http" in sys.argv:
        from .mcp_server import mcp
        host = os.getenv("HOST", "0.0.0.0")
        port = int(os.getenv("PORT", "8080"))
        print(f"Relationship Event OS — MCP HTTP 模式")
        print(f"http://{host}:{port}")
        mcp.run(transport="streamable_http", host=host, port=port)
    else:
        from .mcp_server import mcp
        mcp.run()


if __name__ == "__main__":
    main()
