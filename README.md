# Relationship-Engine

> AI 不应该只是回答问题——它应该帮你经营所有关系。

## 这是什么？

一个 AI 关系管理引擎。它能：

- 🧠 **记住一切** — 每个人的喜好、生日、你们的故事
- 📊 **追踪关系** — 关系阶段、升温/降温、关键事件
- 💬 **对话记忆** — 记住你们聊过的每一件事
- 💡 **主动建议** — 在合适的时间提醒你该做什么
- 🎯 **人设管理** — 为每个人建立完整的画像

## 快速开始

```bash
# 安装依赖
pip install -e .

# 配置
cp .env.example .env
# 编辑 .env 填入你的 OpenAI API Key

# 启动
python -m src.main
```

打开浏览器访问 `http://localhost:8080`

## 项目结构

```
Relationship-Engine/
├── src/
│   ├── memory/          # 记忆系统
│   ├── relationship/    # 关系追踪
│   ├── conversation/    # 对话记忆
│   ├── engine/          # AI 引擎核心
│   ├── api/             # Web API
│   └── web/             # 前端页面
├── data/                # 持久化数据
├── config/              # 配置
└── tests/               # 测试
```

## 部署到阿里云

```bash
# 在服务器上
git clone https://github.com/Suncatoo2/Relationship-Engine.git
cd Relationship-Engine
pip install -e .
cp .env.example .env
# 编辑 .env
python -m src.main
```

## License

MIT
