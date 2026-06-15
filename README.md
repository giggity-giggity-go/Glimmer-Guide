# 研途萤火 (yantu)

> 个人考研智能体 · LangGraph + Chainlit + Scrapling

## 🎯 这是什么

为考研人打造的**个人助理级**智能体:
1. 把已收集的 PDF / 调研报告变成**可语义检索的知识库**
2. 实时抓取**研招网 5 个公开入口**做交叉验证
3. 基于**自定义用户画像**做冲稳保推荐

## ✨ 核心特性

- 💬 **Chainlit Web UI** (localhost:8000) — 对话式访问,工具调用可视化
- 🔍 **Chroma 向量库** + bge-small-zh-v1.5 — 本地语义检索
- 🕷️ **Scrapling** 匿名抓取 5 个研招网入口
- 👤 **可自定义用户画像** — Pydantic 模型 + SQLite,运行时热更新
- 🛡️ **隐私优先** — 不爬任何成绩/调剂/录取数据,严格自用

## 🛠️ 技术栈

| 层 | 选型 |
|---|---|
| Agent | LangGraph (3-4 节点) |
| LLM | MiniMax-M3 (ChatOpenAI 兼容) |
| Web UI | Chainlit |
| 爬虫 | Scrapling (Fetcher) |
| 向量库 | Chroma (嵌入式) |
| Embedding | BAAI/bge-small-zh-v1.5 |
| 存储 | SQLite + SQLAlchemy |
| MCP | yanzhao-mcp (5 tools,自建) |

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
# 编辑 .env 填入 LLM_API_KEY

# 4. 初始化项目
bash scripts/bootstrap.sh

# 5. 摄入个人调研资料(可选)
python -m scripts.ingest_seed

# 6. 启动 Chainlit UI
chainlit run src/yantu/ui/app.py
```

打开浏览器访问 `http://localhost:8000`。

## 📁 项目结构

```
src/yantu/
├── config.py              # 配置加载
├── data/                  # 数据访问层 (SQLite + Chroma)
├── ingest/                # PDF/MD 解析 + 索引
├── scraper/               # 研招网爬虫
├── mcp/                   # yanzhao-mcp
├── graph/                 # LangGraph Agent
├── ui/                    # Chainlit
└── utils/                 # 工具
```

## 🛡️ 信息查询边界(重要)

**只做"报名前"的预研**,明确排除:
- ❌ 成绩查询
- ❌ 调剂信息
- ❌ 录取名单 / 复试名单
- ❌ 个人信息(身份证/手机号)

## 📜 许可证

MIT
