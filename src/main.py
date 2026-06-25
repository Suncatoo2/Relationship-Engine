"""主入口"""

import os
import uvicorn
from dotenv import load_dotenv


def main():
    load_dotenv()
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    print(f"""
╔══════════════════════════════════════╗
║   💘 Relationship Engine v0.1.0     ║
║   AI 关系管理引擎                    ║
║   http://{host}:{port}               ║
╚══════════════════════════════════════╝
""")
    uvicorn.run("src.api:app", host=host, port=port, reload=True)


if __name__ == "__main__":
    main()
