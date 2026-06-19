# 多会话侧边栏 + 长短期记忆完整落地方案

> **版本**: v0.3.0 候选设计
> **日期**: 2026-06-19
> **作者**: Claude (Brainstorming session)
> **状态**: 📝 草案待评审
> **项目**: 研途萤火(yantu)

---

## 1. 目标与对标

### 1.1 产品目标

把 yantu 从"工具型问答"升级到"个人助理" ——
1. **多会话并存**: 用户同时聊"选学校"、"复试准备"、"分数线查询",互不污染
2. **重启不丢**: 关闭 Chainlit 第二天打开,昨天对话完整可继续
3. **跨会话记忆**: "我数学不好" 在所有会话生效,不用每次说
4. **对话不爆**: 长对话自动压缩,Token 不超限

### 1.2 对标参考

| 参考 | 借鉴点 | 我们的差异化 |
|---|---|---|
| **豆包** | 左侧侧边栏 + 历史对话 + 搜索 + 重命名 | 持久化到本地(无云依赖) |
| **Kimi** | 侧边栏分组 / 收藏 / 长文上下文处理 | 用户画像优先注入 |
| **DeepSeek** | 推理折叠块 / 流式响应 / 简洁 UI | 推理可追溯,跳到原始消息 |
| **ChatGPT** | 跨会话记忆(2025-04)/ 临时聊天 / 关闭记忆 | **可手动删除记忆** + 事实溯源 |
| **Claude.ai** | Projects 分组(2024) / Artifacts / 引用原文 | 项目级持久化(类似) |
| **Claude-Mem** (开源) | Bun Worker 后台压缩 / 6 hook / SQLite+Chroma / 渐进注入(50 条)/ 500 token 摘要 | **基于 LangGraph Checkpointer**(不绕开框架) |

### 1.3 范围与非目标

**In scope**:
- 短期记忆(LangGraph Checkpointer + thread_id + 滑动窗口压缩)
- 长期记忆(结构化 facts + 向量检索注入)
- 左侧侧边栏 UI(多会话列表)
- 设置页面集成(上下文长度滑块 / 记忆管理)

**Out of scope(本版本)**:
- 多用户系统(单用户本地应用)
- 跨设备同步(本地落盘,后续可做 export/import)
- 多模态记忆(图/文件)
- 项目分组(ChatGPT Projects 等价物 → v0.4.0)

---

## 2. 架构图(文字描述)

### 2.1 整体分层

```
┌─────────────────────────────────────────────────────────────────┐
│  Chainlit UI 层  (src/yantu/ui/)                                │
│  ┌──────────┐  ┌────────────────────────┐  ┌──────────────┐    │
│  │ Sidebar  │  │   Chat Main            │  │ Settings     │    │
│  │ (会话列) │  │   (当前 thread)         │  │  /settings   │    │
│  │  ┌─────┐ │  │  ┌──────────────────┐  │  │  记忆面板    │    │
│  │  │+ 新 │ │  │  │ CollapsibleReason│  │  │  滑块        │    │
│  │  ├─────┤ │  │  ├──────────────────┤  │  │              │    │
│  │  │会话1│ │  │  │ messages stream  │  │  └──────────────┘    │
│  │  │会话2│ │  │  └──────────────────┘  │                       │
│  │  │...  │ │  └────────────────────────┘                       │
│  │  └─────┘ │                                                     │
│  └──────────┘                                                     │
│       │                                                            │
│       ▼ JSX ↔ FastAPI REST                                        │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  app.py  (Chainlit + FastAPI router)                       │   │
│  │   on_chat_start / on_message / action_callback             │   │
│  │   GET  /sessions          ← sidebar 拉会话列表             │   │
│  │   POST /sessions          ← 新建会话                       │   │
│  │   DELETE /sessions/{tid}  ← 删除会话                       │   │
│  │   PATCH /sessions/{tid}   ← 重命名/固定/置顶                │   │
│  │   POST /sessions/{tid}/switch ← 切换 active thread_id       │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
       │
       ▼ Session Manager (新建: src/yantu/session/manager.py)
       │
┌─────────────────────────────────────────────────────────────────┐
│  LangGraph 层  (src/yantu/graph/)                                │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  agent.py  — build_agent()                                │   │
│  │    checkpointer = AsyncSqliteSaver(                        │   │
│  │      conn="data/checkpoints.db",                          │   │
│  │      serde=JsonPlusSerializer()                           │   │
│  │    )                                                      │   │
│  │    config = {"configurable": {"thread_id": "abc123"}}     │   │
│  └──────────────────────────────────────────────────────────┘   │
│       │                                                            │
│       ▼ State (AgentState)                                         │
│       │ messages: [HumanMessage, AIMessage, ToolMessage, ...]     │
│       │ user_query: str                                            │
│       │ + long_term_facts: list[dict]  (注入层)                    │
│       │ + context_window_size: int    (滑动窗口配置)               │
│       │                                                            │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  nodes.py                                                  │   │
│  │    ┌─────────────────────────────────────────────────┐    │   │
│  │    │ router (现有) + 改造点:                          │    │   │
│  │    │   - 读 state["long_term_facts"] → 注入 system    │    │   │
│  │    │   - 在进入工具调用前触发 _compress_context()     │    │   │
│  │    └─────────────────────────────────────────────────┘    │   │
│  │    ┌─────────────────────────────────────────────────┐    │   │
│  │    │ compressor (新建): 滑动窗口压缩                  │    │   │
│  │    │   - 检测 token 数 → 超阈值则触发 LLM 摘要         │    │   │
│  │    │   - 老消息合并成 1 条 SystemMessage(summary)       │    │   │
│  │    │   - 保留最近 N 条原文(可配)                       │    │   │
│  │    └─────────────────────────────────────────────────┘    │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
       │                                                            │
       ▼ Memory Layer (新建: src/yantu/memory/)                    │
  ┌──────────────────────────────────────────────────────────┐    │
  │  ┌────────────────┐  ┌────────────────┐  ┌──────────────┐ │    │
  │  │  Extractor     │  │  Store         │  │  Retriever   │ │    │
  │  │  (后台 async)  │  │  (SQLite+Chroma│  │  (注入用)    │ │    │
  │  │                │  │                │  │              │ │    │
  │  │  LLM 抽取:     │  │  facts 表      │  │  query →     │ │    │
  │  │  user_query +  │  │  embeddings 表 │  │  top-K facts │ │    │
  │  │  messages →    │  │                │  │              │ │    │
  │  │  fact list     │  │  Chroma        │  │              │ │    │
  │  └────────────────┘  └────────────────┘  └──────────────┘ │    │
  └──────────────────────────────────────────────────────────┘    │
       │                                                            │
       ▼ Storage Layer                                              │
  ┌──────────────────────────────────────────────────────────┐   │
  │  data/                                                     │   │
  │   ├── yantu.db          (SQLite — 用户画像 + facts + 元数据)│   │
  │   ├── chroma/           (Chroma — long-term 向量)         │   │
  │   └── checkpoints.db    (SQLite — LangGraph checkpointer)  │   │
  └──────────────────────────────────────────────────────────┘   │
```

### 2.2 数据流向(用户发新消息时)

```
用户点击侧边栏 "会话 #5"
        │
        ▼
JSX fetch('POST /sessions/abc123/switch')
        │
        ▼
FastAPI: 把 thread_id="abc123" 写入 user_session
        │
        ▼
Chainlit 加载该 thread 的历史消息(history view)
        │
        ▼
用户输入新问题
        │
        ▼
app.py @cl.on_message:
    1. cl.user_session.get("thread_id") → "abc123"
    2. 调用 retriever.retrieve(query=msg, k=10)
       → 返回 top-10 facts (来自跨所有 session 的 facts 表)
    3. 把 facts 注入 inputs["long_term_facts"]
    4. agent.astream_events(inputs, config={thread_id: "abc123"})
       │
       ▼ LangGraph:
       a. router node:
          - 读 state["long_term_facts"] → 拼到 system prompt
          - _compress_context(): 检测 token 数, 超阈值 → LLM 摘要
       b. 工具调用(原有逻辑)
       c. synthesizer(原有逻辑)
       │
       ▼ 后台异步任务 (asyncio.create_task):
          extractor.extract(
              thread_id="abc123",
              user_query=msg,
              last_response=state["response"]
          )
          → LLM 抽取 1-N 个 facts
          → store.upsert(facts)  # SQLite + Chroma
```

### 2.3 滑动窗口压缩时机

```
每次 router 节点执行前:
  ┌─────────────────────────────────────────────┐
  │ token_count = count_tokens(state["messages"])│
  │ if token_count > context_window:            │
  │   compressed = _compress(messages)          │
  │   state["messages"] = compressed            │
  │   state["compressed_summary"] = ...         │
  │   log("⚠️ Context compressed: 8000 → 3000")│
  └─────────────────────────────────────────────┘

context_window 默认 30000 tokens, 用户可在 /settings 滑块调整 5000-100000
```

---

## 3. 存储选型

### 3.1 决策矩阵

| 组件 | 候选方案 | 决策 | 理由 |
|---|---|---|---|
| **LangGraph Checkpointer** | MemorySaver / AsyncSqliteSaver / PostgresSaver | **AsyncSqliteSaver** | 单用户本地应用,SQLite 零依赖;Async 不阻塞 Chainlit |
| **长期记忆元数据** | SQLite JSON / MongoDB / Postgres | **SQLite(JSON)** | 已有 SQLAlchemy + yantu.db,统一 stack |
| **长期记忆向量** | Chroma / FAISS / Qdrant | **Chroma(复用 `recruit_2026` 同 client)** | 已有 `data/chroma/` + bge embedder,新增 `long_term_memory` collection 与 `recruit_2026` 隔离但共享 client(避免双 client 锁) |
| **会话元数据** | 同 yantu.db 新表 | **yantu.db 新表 `sessions`** | 单一 SQLite 避免多文件 |
| **会话摘要** | 同 yantu.db | **yantu.db 新表 `session_summaries`** | 便于侧边栏显示 |
| **Embedding** | bge-small-zh-v1.5 (现有) | **沿用** | 已 cached,512 dim |
| **Embedding 队列** | 同步 / Celery / asyncio.Queue | **asyncio.Queue + 后台 worker** | 单进程无需 Celery |

### 3.2 不引入的依赖

| 不引入 | 理由 |
|---|---|
| Redis | 单机本地,无跨进程需求 |
| Celery | 同步 / asyncio 够用 |
| Mem0 / Zep 等商业 memory 服务 | 永久本地 + 数据自控 |
| Claude-Mem 的 Bun Worker | 我们已有 LangGraph,沿用其 Checkpointer 即可,不再造 worker |

### 3.3 存储路径

```
D:\WORKSTATION\Glimmer Guide\data\
├── yantu.db           (用户画像 + schools + notices + references + user_profile + **新增 sessions / session_summaries / memory_facts**)
├── chroma/            (复用现有 singleton client)
│   ├── recruit_2026      (已有 — 本地资料库,seed/ 扫描)
│   ├── long_term_memory  (新增 — 跨会话 facts)
│   └── disciplines       (预留 — v0.3.x 学科代码)
└── checkpoints.db     (新增: LangGraph AsyncSqliteSaver)
```

---

## 4. 数据表结构

### 4.1 新增 3 张表(在 `src/yantu/data/models.py`)

```python
from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, Text, JSON, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column


# ==================== 会话层 ====================

class Session(Base):
    """会话元数据(侧边栏列表用)

    thread_id 是 LangGraph Checkpointer 的会话隔离键,
    这里存人类可读的标题 + 元数据,UI 层不直接用 thread_id 当显示文本。
    """
    __tablename__ = "sessions"

    thread_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(50), default="default", index=True)
    title: Mapped[str] = mapped_column(String(100), default="新会话")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), index=True
    )
    # 用户操作
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    # 统计(从 LangGraph checkpointer 反查得到,缓存)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    last_tokens: Mapped[int] = mapped_column(Integer, default=0)
    # 上下文压缩状态(最后一次)
    compressed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    compression_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_sessions_user_updated", "user_id", "updated_at"),
        Index("ix_sessions_user_pinned", "user_id", "is_pinned", "updated_at"),
    )


class SessionSummary(Base):
    """会话摘要(LLM 周期性生成,供侧边栏快速预览)

    区别于 Session.compression_summary:
    - compression_summary = LangGraph 压缩的内部状态(系统级)
    - summary = 人类可读的会话进展(用户级,"我们在对比清华 vs 北大的分数线")
    """
    __tablename__ = "session_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    thread_id: Mapped[str] = mapped_column(String(36), index=True)
    turn_number: Mapped[int] = mapped_column(Integer)  # 第几轮生成
    summary: Mapped[str] = mapped_column(Text)  # ~200 字
    topics: Mapped[list] = mapped_column(JSON, default=list)  # ["清华", "分数线"]
    key_questions: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ==================== 长期记忆层 ====================

class MemoryFact(Base):
    """长期记忆事实(LLM 抽取的结构化记忆)

    fact_type 取值:
    - user_attribute: 用户固有属性(数学不好 / 目标清华)
    - preference: 偏好(避开 985 / 喜欢表格)
    - conversation_outcome: 对话结论(决定考清华计算机)
    - open_question: 未解决问题(下次继续)
    - person_mention: 提到的人/校/专业
    - timeline_event: 时间相关事件(报名 10 月)
    """
    __tablename__ = "memory_facts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(50), default="default", index=True)
    fact_type: Mapped[str] = mapped_column(String(50), index=True)
    fact_value: Mapped[dict] = mapped_column(JSON)  # 灵活结构
    # 标准化字段(便于检索)
    subject: Mapped[Optional[str]] = mapped_column(String(200), index=True, nullable=True)
    # 例如 fact_value={"school": "清华", "major": "计算机", "decision": "排除"}
    # subject = "清华"
    keywords: Mapped[list] = mapped_column(JSON, default=list)  # ["清华", "计算机"]
    # 元数据
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    source_thread: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    # 生命周期
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_accessed_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    access_count: Mapped[int] = mapped_column(Integer, default=0)
    # 用户操作(对应 ChatGPT "这不对")
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    user_corrected_value: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_facts_user_subject", "user_id", "subject"),
        Index("ix_facts_user_type", "user_id", "fact_type"),
    )


class UserSetting(Base):
    """用户设置(替代 yantu.config 单文件,迁移历史配置)

    单行(id="default"),但用 key-value JSON 便于扩展。
    """
    __tablename__ = "user_settings"

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default="default")
    # 上下文配置
    context_window_tokens: Mapped[int] = mapped_column(Integer, default=30000)
    context_keep_recent_messages: Mapped[int] = mapped_column(Integer, default=10)
    # 长期记忆配置
    memory_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    memory_injection_count: Mapped[int] = mapped_column(Integer, default=10)
    memory_extract_every_n_turns: Mapped[int] = mapped_column(Integer, default=3)
    # UI 配置
    sidebar_default_view: Mapped[str] = mapped_column(String(20), default="recent")
    # 其他(预留扩展)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
```

### 4.2 Chroma 新增 collection(复用现有 singleton client)

**现状盘点**(2026-06-19 实测):
- `chromadb.PersistentClient` singleton 已在 `src/yantu/data/vector_repo.py:28` 实现,带 lock + atexit 关闭
- 已有 collection: `recruit_2026`(用户 PDF/MD 资料库,本地 RAG)
- embedder 复用: `yantu.utils.embedder.embed_texts / embed_query`(bge-small-zh-v1.5,512 dim,已 cached)
- 现有 `add_documents / search / count` 三个公开 API **已支持 `collection_name` 参数**,直接传名字即可

**v0.3.0 collection 拓扑**(3 个职责分离):

| Collection | 职责 | 来源 | 嵌入 |
|---|---|---|---|
| `recruit_2026` | 用户本地资料库(招生章程/分数线 PDF 等) | `ingest_seed()` 扫描 `seeds/` | bge |
| `long_term_memory` ← **新增** | 跨会话长期记忆 facts | `extractor` 异步抽取 | bge |
| `disciplines` ← **预留 v0.3.x** | 学科代码语义检索(配合 TODO-4) | TODO-4 建设 | bge |

**改动**:`src/yantu/data/vector_repo.py` 加 4 行(常量 + helper,**复用 `_get_singleton_client`**):

```python
# 顶部加常量(已有 recruit_2026 默认值,这里只加新名字)
LONG_TERM_MEMORY_COLLECTION = "long_term_memory"

# 加 helper(复用现有 client + 现有 _get_collection)
def get_long_term_memory_collection():
    """长期记忆向量 collection — 复用 singleton client(不开第二个 client)"""
    return _get_collection(_get_singleton_client(), LONG_TERM_MEMORY_COLLECTION)
```

**调用约定**:
- `vector_repo.add_documents(..., collection_name=vector_repo.LONG_TERM_MEMORY_COLLECTION)`
- `vector_repo.search(query, k, where, collection_name=vector_repo.LONG_TERM_MEMORY_COLLECTION)`
- **不要新建 `chromadb.PersistentClient` 实例**(双 client 会双倍磁盘锁,违背 HB-04 设计)

每条 MemoryFact 对应 1 条 Chroma 文档:
- `id` = `fact-{memory_facts.id}`
- `document` = fact 的人读文本(e.g. "用户数学不好,避开数学")
- `embedding` = bge 嵌入(沿用 `embed_texts`)
- `metadata` = `{user_id, fact_type, subject, memory_facts_id, created_at, is_deleted}`

**风险提示**(R-4 已列):每次 retriever 走 `where={"user_id": "default"}` 在 facts < 1000 时 < 50ms,无需优化;超 5000 后考虑按月分 collection(后续 v0.4 优化项,本期不做)。

---

## 5. LangGraph 集成代码

### 5.1 Checkpointer 接入(`src/yantu/graph/agent.py` 改造)

```python
"""LangGraph Agent 编译 — 多会话 + 长短期记忆集成

v0.3.0 变更:
- MemorySaver → AsyncSqliteSaver(checkpoints.db)
- thread_id 由 user_session 管理(单用户多会话)
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import AsyncIterator

from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from yantu.config import settings
from yantu.graph.nodes import (
    make_router_node,
    make_synthesizer_node,
    make_tool_node,
    should_continue,
)
from yantu.graph.state import AgentState
from yantu.utils.logger import logger


# v0.3.0: AsyncSqliteSaver 单例 lifespan 管理
_SAVER: AsyncSqliteSaver | None = None


async def get_checkpointer() -> AsyncSqliteSaver:
    """单例 AsyncSqliteSaver — lifespan context manager
    
    用法:
        async with get_checkpointer() as cp:
            agent = build_agent_with(cp)
    """
    global _SAVER
    if _SAVER is None:
        ckpt_path = settings.data_dir / "checkpoints.db"
        ckpt_path.parent.mkdir(parents=True, exist_ok=True)
        # AsyncSqliteSaver 是 context manager,必须 setup() 一次建表
        _SAVER = AsyncSqliteSaver.from_conn_string(str(ckpt_path))
        await _SAVER.setup()  # noqa
        logger.info(f"AsyncSqliteSaver initialized at {ckpt_path}")
    return _SAVER


@lru_cache(maxsize=1)
def _build_graph():
    """编译图(不带 checkpointer,checkpointer 在 lifespan 里注入)"""
    g = StateGraph(AgentState)
    g.add_node("router", make_router_node())
    g.add_node("tools", make_tool_node())
    g.add_node("synthesizer", make_synthesizer_node())
    g.add_edge(START, "router")
    g.add_conditional_edges(
        "router", should_continue,
        {"tools": "tools", "synthesize": "synthesizer"},
    )
    g.add_edge("tools", "router")
    g.add_edge("synthesizer", END)
    return g


async def get_agent(thread_id: str):
    """获取绑定 thread_id 的 agent(每次调用传入 checkpointer)
    
    v0.3.0: 由于 AsyncSqliteSaver 是 lifespan context manager,
    每次 Chainlit 请求要 reuse 同一个 saver 实例。
    """
    saver = await get_checkpointer()
    graph = _build_graph()
    return graph.compile(checkpointer=saver)
```

### 5.2 State 扩展(`src/yantu/graph/state.py`)

```python
class AgentState(TypedDict, total=False):
    # ... 原有字段 ...
    messages: Annotated[list[AnyMessage], add_messages]
    user_query: str
    intent: IntentType
    tool_calls: list[dict]
    tool_results: Annotated[list[dict], operator.add]
    response: str
    citations: list[dict]
    grounded: bool
    reasoning: Annotated[str, operator.add]
    reasoning_tokens: int

    # ============ v0.3.0 新增 ============
    # 长期记忆注入(从 retrieve 读)
    long_term_facts: list[dict]  # top-K facts,带 metadata
    # 上下文压缩标记
    is_compressed: bool  # 本轮是否触发了压缩
    compressed_summary: str  # 压缩产生的 summary
    # 配置
    context_window_tokens: int
    context_keep_recent: int
```

### 5.3 滑动窗口压缩节点(`src/yantu/graph/compressor.py` 新建)

```python
"""上下文压缩器 — 滑动窗口 + LLM 摘要

策略:
1. 读 user_settings.context_window_tokens(默认 30000)
2. 用 tiktoken 估算 messages 总 token
3. 超阈值 → 保留最近 N 条原文 + 老消息 LLM 摘要合并成 1 条 SystemMessage
4. 写回 state["messages"] + state["compressed_summary"]
"""
from __future__ import annotations

from typing import Sequence

from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage
from langchain_core.messages.utils import count_tokens_approximately

from yantu.graph.state import AgentState
from yantu.utils.llm import get_llm
from yantu.utils.logger import logger


# v0.3.0: 提示模板(摘要时给 LLM 的指令)
_SUMMARIZE_PROMPT = """你是对话摘要器。请把以下对话历史压缩为不超过 800 字的客观摘要,
保留:1) 用户问过的关键问题 2) 已得出的结论 / 数据 3) 用户表达的偏好与约束
不要编造未出现的事实,直接陈述即可。

对话历史:
{messages}


摘要:"""


async def _summarize_old_messages(old_messages: Sequence[BaseMessage]) -> str:
    """用 LLM 把老消息压成摘要字符串"""
    formatted = []
    for m in old_messages:
        role = m.type if hasattr(m, "type") else "unknown"
        content = m.content if isinstance(m.content, str) else str(m.content)
        formatted.append(f"[{role}] {content}")
    msgs_text = "\n".join(formatted)
    # 截断防 OOM
    if len(msgs_text) > 60000:
        msgs_text = msgs_text[:60000] + "\n... (已截断)"

    llm = get_llm(temperature=0.0)
    ai = await llm.ainvoke([HumanMessage(content=_SUMMARIZE_PROMPT.format(messages=msgs_text))])
    return ai.content if isinstance(ai.content, str) else str(ai.content)


async def compress_context_if_needed(state: AgentState) -> AgentState:
    """router 节点执行前调用 — 超出 token 阈值则压缩

    Returns:
        新 state(messages 已被替换)
    """
    messages = state.get("messages", [])
    if not messages:
        return state

    window = state.get("context_window_tokens", 30000)
    keep_recent = state.get("context_keep_recent", 10)

    current_tokens = count_tokens_approximately(messages)
    if current_tokens <= window:
        return state  # 未超阈值

    logger.warning(
        f"Context compression triggered: {current_tokens} tokens > {window}, "
        f"messages={len(messages)}, keep_recent={keep_recent}"
    )

    # 保留最近 N 条,压前面的
    if len(messages) <= keep_recent:
        logger.warning(f"Cannot compress: only {len(messages)} messages, < keep_recent")
        return state

    old = messages[:-keep_recent]
    recent = messages[-keep_recent:]

    summary = await _summarize_old_messages(old)
    logger.info(f"Old messages compressed: {len(old)} msgs → summary_chars={len(summary)}")

    # 把摘要作为 SystemMessage 插到 recent 之前
    summary_msg = SystemMessage(
        content=f"[本对话早期内容摘要]\n{summary}\n[摘要结束]"
    )
    new_messages = [summary_msg] + list(recent)
    new_tokens = count_tokens_approximately(new_messages)
    logger.info(
        f"Compression done: {current_tokens} → {new_tokens} tokens "
        f"({100 * new_tokens / current_tokens:.1f}%)"
    )
    return {
        **state,
        "messages": new_messages,
        "is_compressed": True,
        "compressed_summary": summary,
    }
```

### 5.4 长期记忆 Extractor(`src/yantu/memory/extractor.py` 新建)

```python
"""长期记忆抽取器 — 后台异步任务

触发时机: 每次 on_message 完成后(不阻塞 UI)
输入: thread_id + 最近 N 条 messages + 当前 user_query
输出: 1-N 条 facts, 写入 SQLite + Chroma
"""
from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime
from typing import Sequence

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from sqlalchemy.orm import Session

from yantu.data.db import session_scope
from yantu.data.models import MemoryFact
from yantu.data import vector_repo
from yantu.utils.llm import get_llm
from yantu.utils.logger import logger
from yantu.utils.embedder import embed_texts


_EXTRACT_PROMPT = """你是记忆抽取助手。从以下对话中提取需要长期记住的事实。

fact_type 取值:
- user_attribute: 用户固有属性(数学不好 / 目标清华 / 本科是 985)
- preference: 偏好(避开 985 / 喜欢看表格 / 不要政治题)
- conversation_outcome: 对话结论(决定考清华 / 排除复旦)
- open_question: 未解决问题(下次继续问 XX 校分数线)
- person_mention: 提到的人/校/专业(清华计算机 / 张老师)
- timeline_event: 时间事件(10 月报名 / 12 月初试)

输出 JSON 数组,每项包含:
{{"fact_type": "...", "subject": "...", "keywords": ["..."], "fact_value": {{...}}, "confidence": 0.0-1.0}}

只输出 JSON,不要解释。

对话:
{conversation}

JSON:"""


def _format_messages(messages: Sequence[BaseMessage]) -> str:
    out = []
    for m in messages[-20:]:  # 只看最近 20 条
        role = m.type if hasattr(m, "type") else "unknown"
        content = m.content if isinstance(m.content, str) else str(m.content)
        out.append(f"[{role}] {content[:1000]}")  # 单条 1000 字符截断
    return "\n".join(out)


def _parse_llm_json(text: str) -> list[dict]:
    """从 LLM 输出解析 JSON(可能含 markdown fence)"""
    text = text.strip()
    # 抽 ```json ... ``` 内部
    m = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
    if m:
        text = m.group(1)
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return [r for r in result if isinstance(r, dict)]
    except json.JSONDecodeError:
        logger.warning(f"Memory extractor JSON parse failed: {text[:200]}")
    return []


async def extract_facts_async(
    thread_id: str,
    user_query: str,
    last_messages: Sequence[BaseMessage],
    user_id: str = "default",
) -> list[int]:
    """异步抽取事实(后台 task 调用,不阻塞 UI)

    Returns:
        新写入的 fact id 列表(便于 caller 调试)
    """
    try:
        conversation = _format_messages(last_messages)
        llm = get_llm(temperature=0.0)
        ai = await llm.ainvoke([
            HumanMessage(content=_EXTRACT_PROMPT.format(conversation=conversation))
        ])
        content = ai.content if isinstance(ai.content, str) else str(ai.content)
        facts_data = _parse_llm_json(content)
        if not facts_data:
            return []

        ids = await _persist_facts(facts_data, user_id, thread_id)
        logger.info(f"Memory extracted: thread={thread_id}, facts={len(ids)}")
        return ids
    except Exception as e:
        logger.exception(f"Memory extraction failed: {e}")
        return []


async def _persist_facts(
    facts_data: list[dict],
    user_id: str,
    thread_id: str,
) -> list[int]:
    """写 SQLite + Chroma"""
    if not facts_data:
        return []

    ids = []
    texts = []
    metadatas = []
    for f in facts_data:
        # SQLite
        with session_scope() as s:
            record = MemoryFact(
                user_id=user_id,
                fact_type=f.get("fact_type", "preference"),
                subject=f.get("subject"),
                keywords=f.get("keywords", []),
                fact_value=f.get("fact_value", {}),
                confidence=f.get("confidence", 1.0),
                source_thread=thread_id,
            )
            s.add(record)
            s.flush()
            fact_id = record.id
            ids.append(fact_id)

        # Chroma 文档 = 人类可读 fact 字符串
        human_text = _fact_to_human_text(f)
        texts.append(human_text)
        metadatas.append({
            "user_id": user_id,
            "fact_type": f.get("fact_type", ""),
            "subject": f.get("subject", ""),
            "memory_facts_id": fact_id,
            "is_deleted": False,
        })

    # 批量嵌入
    if texts:
        embeddings = embed_texts(texts)
        vector_repo.add_documents(
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=[f"fact-{fid}" for fid in ids],
            collection_name=vector_repo.LONG_TERM_MEMORY_COLLECTION,
        )
    return ids


def _fact_to_human_text(f: dict) -> str:
    """fact dict → 自然语言文本(供 embedding)"""
    ftype = f.get("fact_type", "")
    subject = f.get("subject", "")
    value = f.get("fact_value", {})
    keywords = " ".join(f.get("keywords", []))
    base = f"[{ftype}] {subject}: {json.dumps(value, ensure_ascii=False)}"
    if keywords:
        base += f" ({keywords})"
    return base
```

### 5.5 长期记忆 Retriever(`src/yantu/memory/retriever.py` 新建)

```python
"""长期记忆检索器 — query → top-K facts

策略:
1. 用 bge embed query
2. Chroma search top-K(默认 10)
3. 过滤 is_deleted=False
4. 更新 last_accessed_at / access_count
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import update

from yantu.data import vector_repo
from yantu.data.db import session_scope
from yantu.data.models import MemoryFact
from yantu.utils.embedder import embed_query


async def retrieve_relevant_facts(
    query: str,
    user_id: str = "default",
    k: int = 10,
) -> list[dict]:
    """检索相关长期记忆

    Returns:
        list of dicts (MemoryFact.model_dump())
    """
    if not query.strip():
        return []

    try:
        emb = embed_query(query)
        results = vector_repo.search(
            query=query,
            k=k,
            where={"user_id": user_id, "is_deleted": False},
            collection_name=vector_repo.LONG_TERM_MEMORY_COLLECTION,
        )
    except Exception as e:
        # Chroma 启动失败等
        from yantu.utils.logger import logger
        logger.warning(f"Long-term memory retrieval failed: {e}")
        return []

    if not results:
        return []

    fact_ids = []
    out = []
    for r in results:
        mid = r.get("metadata", {}).get("memory_facts_id")
        if mid is None:
            continue
        fact_ids.append(mid)
        out.append({
            "id": mid,
            "document": r.get("document", ""),
            "metadata": r.get("metadata", {}),
            "distance": r.get("distance"),
        })

    # 更新 access 统计(异步,不阻塞)
    if fact_ids:
        try:
            with session_scope() as s:
                s.execute(
                    update(MemoryFact)
                    .where(MemoryFact.id.in_(fact_ids))
                    .values(
                        last_accessed_at=datetime.utcnow(),
                        access_count=MemoryFact.access_count + 1,
                    )
                )
        except Exception:
            pass

    return out
```

### 5.6 Router 节点改造(`src/yantu/graph/nodes.py` 关键片段)

```python
async def make_router_node_async():
    """v0.3.0: router 在执行前先压缩 + 注入长期记忆"""

    async def router(state: AgentState) -> AgentState:
        query = state.get("user_query", "")

        # Step 1: 上下文压缩(异步)
        from yantu.graph.compressor import compress_context_if_needed
        compressed_state = await compress_context_if_needed(state)

        # Step 2: 长期记忆检索(异步)
        from yantu.memory.retriever import retrieve_relevant_facts
        from yantu.data.user_settings import get_settings
        settings = get_settings()
        if settings.memory_enabled:
            facts = await retrieve_relevant_facts(
                query=query,
                k=settings.memory_injection_count,
            )
            compressed_state["long_term_facts"] = facts

        # Step 3: 原 router 逻辑(Intent 分类 + bind tools)
        intent = _classify_intent(query)
        tools = TOOL_BUCKETS.get(intent.target, [])
        if not tools:
            return {**compressed_state, "intent": intent.target}

        llm = get_llm(temperature=0.2)
        llm_with_tools = llm.bind_tools(tools)

        # 拼 system prompt: 原 prompt + 长期记忆
        system_content = _system_with_profile()
        if compressed_state.get("long_term_facts"):
            facts_text = _format_facts(compressed_state["long_term_facts"])
            system_content += f"\n\n[长期记忆(用户跨会话的偏好与历史)]\n{facts_text}\n"

        msgs = [SystemMessage(content=system_content)]
        if compressed_state.get("messages"):
            msgs.extend(compressed_state["messages"])
        msgs.append(HumanMessage(content=query))

        ai = llm_with_tools.invoke(msgs)
        _r = extract_reasoning(ai)

        return {
            **compressed_state,
            "messages": [ai],
            "intent": intent.target,
            "reasoning": _r.text + ("\n" if _r.text else ""),
            "reasoning_tokens": _r.tokens,
        }

    return router


def _format_facts(facts: list[dict]) -> str:
    """把 facts list 格式化成可注入文本"""
    lines = []
    for i, f in enumerate(facts, 1):
        doc = f.get("document", "")
        meta = f.get("metadata", {})
        lines.append(f"{i}. {doc}")
    return "\n".join(lines)
```

### 5.7 Session Manager(`src/yantu/session/manager.py` 新建)

```python
"""会话管理 — 侧边栏 CRUD + thread_id 切换

设计要点:
- thread_id = UUID4(36 字符)
- title 默认 "新会话",首次发消息后用 LLM 生成标题
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select, update

from yantu.data.db import session_scope
from yantu.data.models import Session
from yantu.utils.logger import logger


def create_session(user_id: str = "default", title: str = "新会话") -> str:
    """新建会话,返回 thread_id"""
    thread_id = str(uuid.uuid4())
    with session_scope() as s:
        s.add(Session(
            thread_id=thread_id,
            user_id=user_id,
            title=title,
        ))
    logger.info(f"Session created: thread_id={thread_id}")
    return thread_id


def list_sessions(
    user_id: str = "default",
    include_archived: bool = False,
    limit: int = 100,
) -> list[dict]:
    """列出活跃会话(侧边栏用)"""
    with session_scope() as s:
        stmt = (
            select(Session)
            .where(Session.user_id == user_id)
            .order_by(Session.is_pinned.desc(), Session.updated_at.desc())
            .limit(limit)
        )
        if not include_archived:
            stmt = stmt.where(Session.is_archived == False)  # noqa
        rows = s.execute(stmt).scalars().all()
        return [r.__dict__ | {"_sa_instance_state": None} for r in rows]


def rename_session(thread_id: str, new_title: str) -> bool:
    with session_scope() as s:
        row = s.get(Session, thread_id)
        if row:
            row.title = new_title[:100]
            return True
    return False


def toggle_pin(thread_id: str) -> bool:
    with session_scope() as s:
        row = s.get(Session, thread_id)
        if row:
            row.is_pinned = not row.is_pinned
            return row.is_pinned
    return False


def archive_session(thread_id: str) -> bool:
    """归档(软删除)"""
    with session_scope() as s:
        row = s.get(Session, thread_id)
        if row:
            row.is_archived = True
            return True
    return False


def touch_session(thread_id: str, message_count_delta: int = 1):
    """每条消息后更新会话元数据"""
    with session_scope() as s:
        s.execute(
            update(Session)
            .where(Session.thread_id == thread_id)
            .values(
                updated_at=datetime.utcnow(),
                message_count=Session.message_count + message_count_delta,
            )
        )


def get_session(thread_id: str) -> Optional[dict]:
    with session_scope() as s:
        row = s.get(Session, thread_id)
        if row:
            d = row.__dict__.copy()
            d.pop("_sa_instance_state", None)
            return d
    return None
```

### 5.8 app.py 主循环改造(关键片段)

```python
@cl.on_chat_start
async def start():
    """新会话:从列表选一个 OR 创建新"""
    # 读用户上次会话(从 cookie / cl.user_session 不持久)
    # 或者直接给个"选择会话" UI
    sessions = list_sessions()

    # 显示侧边栏元素(JSX 拉取)
    await cl.Message(
        content="👋 研途萤火",
        elements=[
            cl.CustomElement(
                name="SessionSidebar",
                props={
                    "sessions": sessions,
                    "activeThreadId": None,  # 新会话
                },
                display="side",
            )
        ],
    ).send()

    # 默认行为:如无 active session,新建一个
    thread_id = create_session()
    cl.user_session.set("thread_id", thread_id)
    agent = await get_agent(thread_id)
    cl.user_session.set("agent", agent)


@cl.on_message
async def main(message: cl.Message):
    thread_id = cl.user_session.get("thread_id")
    agent = cl.user_session.get("agent")

    # 读最新 messages(从 LangGraph checkpointer)
    config = {"configurable": {"thread_id": thread_id}}
    inputs = {"user_query": message.content, "messages": [HumanMessage(content=message.content)]}

    # 注入长期记忆(异步)
    from yantu.memory.retriever import retrieve_relevant_facts
    facts = await retrieve_relevant_facts(query=message.content)
    inputs["long_term_facts"] = facts
    # ... 注入 settings ...

    # 流式
    async for event in agent.astream_events(inputs, config=config, version="v2"):
        # ... (原有 tool step 处理) ...
        pass

    # 渲染响应(原有)
    final = await agent.aget_state(config)
    state_values = final.values or {}
    response_text = _strip_think(state_values.get("response", ""))
    # ... 构造 elements ...

    await cl.Message(content=response_text, elements=elements).send()

    # 异步触发后台 memory extraction(不阻塞)
    asyncio.create_task(
        extract_facts_async(
            thread_id=thread_id,
            user_query=message.content,
            last_messages=state_values.get("messages", []),
        )
    )

    # 更新会话元数据
    touch_session(thread_id, message_count_delta=2)  # user + ai
```

### 5.9 FastAPI 路由(`app.py` 加)

```python
@chainlit_app.get("/api/sessions")
async def api_list_sessions():
    return {"sessions": list_sessions()}


@chainlit_app.post("/api/sessions")
async def api_create_session(payload: dict):
    title = payload.get("title", "新会话")
    thread_id = create_session(title=title)
    return {"thread_id": thread_id}


@chainlit_app.patch("/api/sessions/{thread_id}")
async def api_update_session(thread_id: str, payload: dict):
    if "title" in payload:
        rename_session(thread_id, payload["title"])
    if "is_pinned" in payload:
        # 直接 set,不走 toggle
        with session_scope() as s:
            row = s.get(Session, thread_id)
            if row:
                row.is_pinned = payload["is_pinned"]
    if "is_archived" in payload:
        archive_session(thread_id) if payload["is_archived"] else None
    return {"ok": True}


@chainlit_app.delete("/api/sessions/{thread_id}")
async def api_delete_session(thread_id: str):
    """删除 session + 清理 LangGraph checkpoint(可选)"""
    archive_session(thread_id)
    # 真正删 checkpoint:用 AsyncSqliteSaver.delete_thread(thread_id)
    return {"ok": True}


@chainlit_app.post("/api/sessions/{thread_id}/switch")
async def api_switch_session(thread_id: str):
    """切换 active thread(写入 user_session 不在 REST,前端 JSX 配合)"""
    # 前端拿到 thread_id,后续 on_message 会用它
    return {"thread_id": thread_id}
```

---

## 6. 前端会话交互逻辑

### 6.1 侧边栏 JSX(`public/elements/SessionSidebar.jsx` 新建)

```jsx
// SessionSidebar.jsx
// 挂载: Chainlit message element, display="side"
// 数据源: GET /api/sessions + WS 推送变更
// 交互: 点击切换 / 双击重命名 / 右键菜单 / 拖拽排序

import { useState, useEffect, useCallback } from "react";
import { useChainlit } from "chainlit/react";

export default function SessionSidebar() {
  const { callAction, sendMessage } = useChainlit();
  const initial = props.sessions || [];
  const [sessions, setSessions] = useState(initial);
  const [activeId, setActiveId] = useState(props.activeThreadId);
  const [searchQuery, setSearchQuery] = useState("");
  const [editingId, setEditingId] = useState(null);
  const [editValue, setEditValue] = useState("");

  // 过滤
  const filtered = sessions.filter(s => 
    !searchQuery || s.title.toLowerCase().includes(searchQuery.toLowerCase())
  );
  const pinned = filtered.filter(s => s.is_pinned);
  const recent = filtered.filter(s => !s.is_pinned);

  // 新建会话
  const handleNew = async () => {
    const res = await fetch("/api/sessions", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({title: "新会话"}),
    }).then(r => r.json());
    setSessions([{thread_id: res.thread_id, title: "新会话", updated_at: new Date().toISOString()}, ...sessions]);
    await callAction({name: "switch_session", payload: {thread_id: res.thread_id}});
    setActiveId(res.thread_id);
  };

  // 切换
  const handleSelect = async (tid) => {
    setActiveId(tid);
    await callAction({name: "switch_session", payload: {thread_id: tid}});
  };

  // 重命名
  const handleRename = async (tid, newTitle) => {
    await fetch(`/api/sessions/${tid}`, {
      method: "PATCH",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({title: newTitle}),
    });
    setSessions(sessions.map(s => s.thread_id === tid ? {...s, title: newTitle} : s));
  };

  // 固定 / 取消固定
  const handleTogglePin = async (tid) => {
    await fetch(`/api/sessions/${tid}`, {
      method: "PATCH",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({is_pinned: !sessions.find(s => s.thread_id === tid)?.is_pinned}),
    });
    // 重新拉
    const res = await fetch("/api/sessions").then(r => r.json());
    setSessions(res.sessions);
  };

  // 删除(归档)
  const handleDelete = async (tid) => {
    if (!confirm("确定删除此会话?")) return;
    await fetch(`/api/sessions/${tid}`, {method: "DELETE"});
    setSessions(sessions.filter(s => s.thread_id !== tid));
    if (tid === activeId) handleNew();
  };

  return (
    <div style={{display: "flex", flexDirection: "column", height: "100vh", padding: 12}}>
      <button onClick={handleNew} style={btnPrimaryStyle}>+ 新会话</button>
      
      <input
        type="search"
        placeholder="🔍 搜索会话..."
        value={searchQuery}
        onChange={e => setSearchQuery(e.target.value)}
        style={searchStyle}
      />

      {pinned.length > 0 && (
        <Section title="📌 已固定">
          {pinned.map(s => renderItem(s))}
        </Section>
      )}
      
      <Section title="💬 最近">
        {recent.map(s => renderItem(s))}
      </Section>
    </div>
  );

  function renderItem(s) {
    const isActive = s.thread_id === activeId;
    const isEditing = editingId === s.thread_id;
    return (
      <div 
        key={s.thread_id}
        onClick={() => !isEditing && handleSelect(s.thread_id)}
        onDoubleClick={() => {setEditingId(s.thread_id); setEditValue(s.title);}}
        style={{
          padding: "8px 10px",
          borderRadius: 6,
          cursor: "pointer",
          background: isActive ? "var(--accent-light)" : "transparent",
          marginBottom: 4,
          display: "flex",
          alignItems: "center",
          gap: 8,
        }}
      >
        <span style={{flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap"}}>
          {isEditing ? (
            <input
              autoFocus
              value={editValue}
              onChange={e => setEditValue(e.target.value)}
              onBlur={() => {handleRename(s.thread_id, editValue); setEditingId(null);}}
              onKeyDown={e => {
                if (e.key === "Enter") {handleRename(s.thread_id, editValue); setEditingId(null);}
                if (e.key === "Escape") setEditingId(null);
              }}
              style={{width: "100%"}}
            />
          ) : (
            <>
              {s.title || "新会话"}
              <div style={{fontSize: 11, color: "var(--muted)"}}>
                {new Date(s.updated_at).toLocaleString()}
              </div>
            </>
          )}
        </span>
        <button onClick={(e) => {e.stopPropagation(); handleTogglePin(s.thread_id);}}>
          {s.is_pinned ? "📌" : "📍"}
        </button>
        <button onClick={(e) => {e.stopPropagation(); handleDelete(s.thread_id);}}>
          🗑️
        </button>
      </div>
    );
  }
}

const Section = ({title, children}) => (
  <div style={{marginTop: 12}}>
    <div style={{fontSize: 12, fontWeight: 600, color: "var(--muted)", padding: "4px 8px"}}>
      {title}
    </div>
    {children}
  </div>
);

// styles ...
```

### 6.2 设置页新增"上下文"与"记忆"两 Tab

**位置**: `src/yantu/ui/templates/settings.html` 改造,新增 2 个 tab

```html
<nav class="tabs">
  <button data-tab="profile">👤 个人</button>
  <button data-tab="context" class="active">📏 上下文</button>
  <button data-tab="memory">🧠 记忆</button>
</nav>

<section data-tab-panel="context">
  <fieldset>
    <legend>短期记忆(滑动窗口)</legend>
    <label>
      上下文长度上限:
      <input type="range" name="context_window_tokens" 
             min="5000" max="100000" step="1000" 
             value="30000" />
      <output>30000 tokens</output>
    </label>
    <label>
      保留最近消息条数:
      <input type="range" name="context_keep_recent_messages"
             min="2" max="30" step="1" value="10" />
      <output>10 条</output>
    </label>
    <p class="hint">超出上限会自动用 LLM 摘要压缩,保留关键信息</p>
  </fieldset>
</section>

<section data-tab-panel="memory" hidden>
  <fieldset>
    <legend>长期记忆</legend>
    <label>
      <input type="checkbox" name="memory_enabled" checked />
      启用长期记忆(LLM 自动抽取跨会话关键事实)
    </label>
    <label>
      注入记忆条数:
      <input type="range" name="memory_injection_count"
             min="0" max="30" step="1" value="10" />
      <output>10 条</output>
    </label>
    <label>
      每隔 N 轮抽取:
      <input type="range" name="memory_extract_every_n_turns"
             min="1" max="10" step="1" value="3" />
      <output>3 轮</output>
    </label>
  </fieldset>
  
  <fieldset>
    <legend>已记忆的事实(<span id="fact-count">0</span>)</legend>
    <div id="fact-list"></div>
  </fieldset>
</section>
```

JS: 加载时 `GET /api/memory/facts` + 渲染列表,每条 fact 带"❌ 错误"按钮(调 `DELETE /api/memory/facts/{id}`)

---

## 7. 开发风险清单

### 7.1 高风险(R 级 — 必须解决)

| # | 风险 | 影响 | 缓解措施 |
|---|---|---|---|
| **R-1** | **AsyncSqliteSaver 与现有 MemorySaver 行为差异**:重启后 messages 不在 `state["messages"]`,router 拿到的是空 list | 整条对话链路崩 | 写专项 e2e 测试:发 3 条 → 重启 → 发第 4 条 → 验证 LLM 看到前 3 条 |
| **R-2** | **extractor 后台任务与 UI 竞争**:asyncio.create_task 在 Chainlit message handler 中,handler 返回后 task 可能被取消 | 记忆丢失 | 用 `cl.task` (Chainlit background task) 或在 lifespan 管理后台 worker |
| **R-3** | **滑动窗口压缩时机错位**:`count_tokens_approximately` 估算不准,真实 LLM 接受时仍超限 | 仍然 OOM | 在 synthesizer 前再加一道 `llm.get_num_tokens_from_messages(msgs)` 二次校验 |
| **R-4** | **Chroma where 过滤性能**:每次 retriever 走 `where={"user_id": "default"}`, 单用户多事实后变慢 | 检索 5s+ | metadata 加 HNSW 索引 + 按月分 collection(后续优化) |

### 7.2 中风险(M 级 — 应该解决)

| # | 风险 | 影响 | 缓解 |
|---|---|---|---|
| **M-1** | **session 列表加载延迟**:SQLite 单表查询 100 行可忽略,但 `message_count` 需从 LangGraph checkpointer 实时算 → 100ms+ | 侧边栏卡顿 | 用 `Session.message_count` 缓存,只在消息后 `touch_session` 时 +1 |
| **M-2** | **extractor 误抽取隐私内容**(身份证号 / 真实姓名 / 地址) | 用户数据安全 | 在 extractor 后置规则:正则黑名单(身份证号 / 手机号 / 银行卡),命中即丢弃 + log warning |
| **M-3** | **长期记忆污染**:LLM 抽取错 facts(如"用户讨厌清华"实际是"用户考虑过清华但放弃了") | 误导后续对话 | `confidence < 0.7` 不入库;事实加 `user_corrected_value` 字段,用户可在 UI 修正 |
| **M-4** | **侧边栏 JSX 性能**:100+ 会话时 DOM 渲染卡 | UX 差 | 虚拟滚动(react-window) + 分页加载 |
| **M-5** | **冷启动 Chroma 未就绪**:首次 `vector_repo.search` 触发 collection 创建阻塞 | 首个 query 卡 3-5s | `on_chat_start` 中预热 Chroma collection |
| **M-6** | **extractor 用 vendor LLM 调用产生费用** | 成本 | 设置 `memory_extract_every_n_turns=3`(每 3 轮抽 1 次),而非每轮 |

### 7.3 低风险(L 级 — 观察)

| # | 风险 | 影响 |
|---|---|---|
| L-1 | SQLite 单文件 → 万级 facts 后变慢 | 监控,暂不优化 |
| L-2 | Chroma collection 不自动清理 is_deleted=true 文档 | 磁盘占位,定期 vacuum |
| L-3 | `count_tokens_approximately` 用 `len*0.3` 估算,中文不准 | 微调系数 |
| L-4 | Chainlit `cl.user_session` 在 WebSocket 断后丢失 | 让 thread_id 从 URL 读 |

### 7.4 范围外风险(暂时忽略)

- ❌ 多用户(单用户本地应用,user_id 写死 "default")
- ❌ 跨设备同步(后续 export/import,本版不做)
- ❌ 加密 at rest(本地 OS 用户权限足够)
- ❌ GDPR-style "遗忘权"(删除按钮可解)

---

## 8. 实施路线(分 4 个 PR)

### PR-1: 数据层 + Checkpointer 切换(v0.3.0-alpha)
**~3 天**
- [ ] `models.py` 新增 4 张表 + Alembic 迁移(若用 Alembic, 否则 init_db 兜底)
- [ ] `db.py` 加 `get_async_engine()`
- [ ] `vector_repo.py` 加 `LONG_TERM_MEMORY_COLLECTION` 常量 + `get_long_term_memory_collection()` helper(**复用 `_get_singleton_client`,不开第二个 client**;`add_documents / search / count` 现有 API 已支持 `collection_name` 参数,直接传名字即可,不重写)
- [ ] `agent.py` 改造为 AsyncSqliteSaver + lifespan
- [ ] pytest: checkpoint 跨进程恢复 + thread 隔离
- [ ] **不引入 extractor / retriever / sidebar**(纯底层)

### PR-2: 长期记忆抽取与检索(v0.3.0-beta)
**~3 天**
- [ ] `memory/extractor.py` + `retriever.py`
- [ ] `nodes.py` router 注入 long_term_facts
- [ ] `app.py` 后台触发 `asyncio.create_task(extract_facts_async)`
- [ ] `user_settings` 表 + `/settings` 上下文/记忆 2 tab
- [ ] pytest: extractor JSON 解析 + retriever 注入不阻塞
- [ ] 端到端:发 5 条 → 重启 → 发第 6 条 → LLM 提到"上次说..."

### PR-3: 侧边栏 UI + Session Manager(v0.3.0-rc)
**~3 天**
- [ ] `session/manager.py` CRUD
- [ ] `public/elements/SessionSidebar.jsx`
- [ ] `app.py` 加 `/api/sessions` REST
- [ ] pytest: manager API + sidebar 渲染
- [ ] 端到端:点 +新 → 发 2 条 → 切到旧会话 → 历史加载

### PR-4: 上下文压缩(v0.3.0-final)
**~2 天**
- [ ] `graph/compressor.py`
- [ ] `nodes.py` router 前调用
- [ ] pytest: 触发条件 + 摘要质量
- [ ] 端到端:连发 50 条 → 验证压缩触发 + 后续对话仍连贯

---

## 9. 验收标准

| 维度 | 标准 |
|---|---|
| **功能** | 多会话并存 + 重启保留 + 跨会话记忆 + 自动压缩 全部走通 |
| **测试** | pytest ≥ 70 个(53 现有 + 17 新增),全过 |
| **性能** | 侧边栏加载 < 200ms / 长对话压缩 < 3s / 单 query LLM 调用次数 ≤ 5 |
| **UX** | 侧边栏操作(新建/切换/重命名/固定/删除)无 reload / 记忆管理 UI 可手动增删改 |
| **兼容** | 现有 5 个 tool 调用路径不变 / 53 旧测试全过 |

---

## 10. 待确认决策点

| # | 决策点 | 我的推荐 | 备选 |
|---|---|---|---|
| Q1 | extractor 后台任务载体 | `asyncio.create_task` + lifespan 管理 | Chainlit `cl.task`(社区方案,生态不熟) |
| Q2 | 压缩后老消息处理 | 保留为 SystemMessage(摘要),放在 messages[0] | 直接丢弃,只保留 recent + 摘要(更激进) |
| Q3 | sidebar 渲染方案 | `cl.CustomElement` 挂到 message(沿用现有模式) | 改 Chainlit theme 注入 sidebar(侵入深) |
| Q4 | 记忆注入上限 | 10 条(可配) | 5 条(更省 token) |
| Q5 | session 标题生成 | LLM 用首条 user_query 生成(异步,首次消息后) | 永远用 user_query 前 20 字 |
| Q6 | 删除会话是否清 LangGraph checkpoint | 软删除(archive),保留 30 天可恢复 | 硬删除(永久) |
| Q7 | 是否引入 LangGraph `Pregel` 新 API | 不引入,沿用 StateGraph | 引入(v0.4 再说) |

---

**下一步**: 等用户对 Q1-Q7 决策,再进入 writing-plans 拆任务。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>