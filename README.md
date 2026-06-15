# 研途萤火 (yantu)

> 个人考研智能体 · LangGraph + Chainlit · 研招网信息查询 + 个人调研资料语义检索

## 🎯 这是什么

为考研人打造的**个人助理级**智能体:
1. 把已收集的 PDF / 调研报告变成**可语义检索的知识库**
2. 实时抓取**研招网 5 个公开入口**做交叉验证
3. 基于**自定义用户画像**做冲稳保推荐

## ✨ 核心特性

- 💬 **Chainlit Web UI** (localhost:8000) — 对话式访问,工具调用可视化
- 🔍 **Chroma 向量库** + bge-small-zh-v1.5 — 本地语义检索
- 🕷️ **httpx + parsel** 匿名抓取 5 个研招网入口
- 👤 **可自定义用户画像** — Pydantic 模型 + SQLite,运行时热更新
- 🛡️ **隐私优先** — 不爬任何成绩/调剂/录取数据,严格自用

## 🛠️ 技术栈

| 层 | 选型 |
|---|---|
| Agent | LangGraph (router + tools + synthesizer) |
| LLM | ChatOpenAI 兼容(默认 MiniMax-M3) |
| Web UI | Chainlit 2.11+ |
| 爬虫 | httpx + parsel |
| 向量库 | Chroma (嵌入式) |
| Embedding | BAAI/bge-small-zh-v1.5 |
| 存储 | SQLite + SQLAlchemy |
| 持久化 | langgraph-checkpoint-sqlite |
| MCP | yanzhao-mcp(5 tools,自建 stdio server) |

## 🚀 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/giggity-giggity-go/Glimmer-Guide.git
cd "Glimmer Guide"

# 2. 创建并激活 conda 环境
conda env create -f environment.yml
conda activate Glimmer

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 LLM_API_KEY / LLM_BASE_URL

# 4. 初始化项目
bash scripts/bootstrap.sh

# 5. 摄入个人调研资料(seed/ 已有示例数据)
python -m scripts.ingest_seed

# 6. 启动 Chainlit UI
chainlit run src/yantu/ui/app.py
# 或: yantu
```

打开浏览器访问 `http://localhost:8000`。

### 验证用命令

```bash
# 单元测试:5 个 tool 真实联网
python -c "import sys; sys.path.insert(0, 'src'); \
  from yantu.scraper import endpoints; import asyncio; \
  print(asyncio.run(endpoints.query_school_library(page=1))[:3])"

# 单元测试:本地语义检索
python -c "import sys; sys.path.insert(0, 'src'); \
  from yantu.data.vector_repo import search; \
  [print(h['metadata'].get('source_file')) for h in search('CCNU 复试分数线', k=3)]"

# CLI 烟雾测试
yantu-chat

# MCP server 测试(stdio)
yantu-mcp
```

## 📁 项目结构

```
src/yantu/
├── config.py              # .env 加载
├── data/                  # 数据访问层
│   ├── db.py              # SQLite engine + session
│   ├── models.py          # Pydantic + SQLAlchemy ORM
│   ├── user_profile.py    # 用户画像 CRUD (热更新)
│   └── vector_repo.py     # Chroma 封装
├── ingest/                # 数据摄入
│   ├── pdf_parser.py      # pypdf 提取
│   ├── md_parser.py       # markdown 切片
│   ├── chunker.py         # 字符级切片
│   ├── indexer.py         # Chroma 写入
│   └── seed_loader.py     # 扫描 + 分发
├── scraper/               # 研招网爬虫
│   ├── client.py          # httpx 封装 + 1-3s 间隔
│   └── endpoints.py       # 5 个 endpoint
├── mcp/                   # yanzhao-mcp
│   ├── server.py          # stdio server
│   └── (tools.py 由 graph/tools.py 复用)
├── graph/                 # LangGraph
│   ├── state.py           # AgentState
│   ├── tools.py           # 5 个 LangChain tool
│   ├── nodes.py           # router / tools / synthesizer
│   └── agent.py           # 编译 + checkpoint
├── ui/                    # Chainlit
│   └── app.py             # 对话 + 流式 + 设置面板
└── utils/
    ├── llm.py             # ChatOpenAI 封装
    ├── embedder.py        # bge-small-zh-v1.5
    └── logger.py
```

## 🛡️ 信息查询边界(重要)

**只做"报名前"的预研**,明确排除:
- ❌ 成绩查询
- ❌ 调剂信息
- ❌ 录取名单 / 复试名单
- ❌ 个人信息(身份证/手机号)

## 🧩 5 个 MCP Tools

| Tool | 输入 | 输出 | 来源 |
|---|---|---|---|
| `query_school_library` | page | 20 校/页 | `/sch/` |
| `get_school_info` | school_id | 院校详情 | `/sch/schoolInfo--schId-{id}.dhtml` |
| `get_disciplines` | (无) | 14 门类 | 硬编码(因 /zyk/ 是 Vue SPA) |
| `get_recruitment_notices` | page | 80 简章/页 | `/kyzx/zsjz/` |
| `search_local` | query, k | top-k 命中 | Chroma |

## 📊 性能指标

- 10 个 seed 文件 → 204 个 Chroma chunks
- search_local top-1 命中率:CCNU 257/33/33/50/50 ✅
- 5 个 tool 全部匿名可达,无需登录
- 1-3s 随机间隔(防 IP 限速)
- bge 模型首加载 ~260MB,CPU 可跑

## 📜 许可证

MIT
