# 研途萤火(yantu)项目进度

> **截止日期**: 2026-06-15
> **项目仓库**: `giggity-giggity-go/Glimmer-Guide` (私有)
> **状态**: ✅ v0.1.0 MVP 端到端跑通

---

## 🎯 项目目标

为 2026 考研人(用户画像:政英 127 / 数学 29 / 408 47 / 095136 农信专硕)打造的**个人助理级**智能体,聚焦"报名前"的预研:

1. 把已收集的 PDF / 调研报告变成**可语义检索的知识库**
2. 实时抓取**研招网 5 个公开入口**做交叉验证
3. 基于**自定义用户画像**做冲稳保推荐
4. 提供 **Chainlit Web UI** 对话式访问

---

## ✅ 已完成(6 阶段 + 修复)

### Phase 0: Bootstrap + GitHub
- ✅ 私有 GitHub 仓库 `giggity-giggity-go/Glimmer-Guide` 创建
- ✅ conda `Glimmer` (Python 3.11) 环境
- ✅ pyproject.toml + 17 个核心依赖
- ✅ 完整目录结构(7 个子包: data/ingest/scraper/mcp/graph/ui/utils)
- ✅ .gitignore(Document/ / data/ / seed/ / models/ 都排除)

### Phase 0.5: 用户画像模块
- ✅ Pydantic `UserProfile` 模型(5 大类:personal/scores/preferences/regions/timeline)
- ✅ SQLite 单行存储 + 热更新(`update_profile({...})`)
- ✅ 渲染为 LangGraph system prompt
- ✅ 5 个验证测试通过(init/get/update/reset/export)

### Phase 1: 本地数据摄入
- ✅ PDF 解析(`pypdf` 按页,自动识别 doc_type/school/year)
- ✅ Markdown 解析(标题栈切片,保留路径)
- ✅ 文本切片(字符级 256-768 + 64 overlap)
- ✅ Chroma 持久化 + bge-small-zh-v1.5 中文嵌入
- ✅ 10 个 seed 文件 → **204 个 chunks** 索引
- ✅ search "CCNU 复试分数线" top-1 命中 257/33/33/50/50

### Phase 2: yanzhao-mcp + 研招网爬虫
- ✅ Scrapling 0.4.9 强依赖 playwright → **改用 httpx + parsel**(零新依赖)
- ✅ 5 个 tool 全部匿名可达(实测 2026-06-15):
  1. `query_school_library` — `/sch/` 院校库(20 校/页, 47 页)
  2. `get_school_info` — `/sch/schoolInfo--schId-{id}.dhtml` 院校详情
  3. `get_disciplines` — 14 门类(硬编码,因 /zyk/ 是 Vue SPA)
  4. `get_recruitment_notices` — `/kyzx/zsjz/` 全国简章(80/页, 25 页)
  5. `search_local` — Chroma 语义检索
- ✅ 1-3s 随机间隔防 IP 限速
- ✅ MCP stdio server 注册成功

**研招网 2026 关键发现**:
- `/zsml/queryAction.do` 旧接口 → **404**(已转登录或废弃)
- `/zsml/` `/zyk/` 是 Vue 2 SPA,数据 JS 渲染
- `/zyk/specialityDetail.do` 触发**滑块验证码**(2026 新增)
- `/zsml/a/dw.do` 强制登录
- `/sch/` `/sch/schoolInfo--schId-*.dhtml` `/kyzx/zsjz/` 仍匿名可达

### Phase 3: LangGraph Agent
- ✅ AgentState (TypedDict) 5 字段
- ✅ 4 节点:`router` (LLM 决策) → `tools` (ToolNode) → `synthesizer` (LLM 综合)
- ✅ MemorySaver checkpoint(自用场景够用,重启 Chainlit 才丢会话)
- ✅ SqliteSaver 试过但有 langgraph 1.2.5 兼容问题(见"已知问题")

### Phase 4: Chainlit Web UI
- ✅ `on_chat_start` 启动时 warmup embedder + 显示用户画像
- ✅ `on_message` 调 astream_events,tool 调用可视化(cl.Step)
- ✅ `action_callback` "edit_profile" 修改用户画像
- ✅ LLM 流式 token 累积
- ✅ **HTTP 200 OK** 在 localhost:8000

### Phase 5: 打磨 + 文档
- ✅ README 完整(快速开始 + 结构 + E2E 测试命令)
- ✅ 修 embedder FutureWarning
- ✅ E2E 烟雾测试通过

---

## 🔧 修复历史(开发中发现)

### Bug 1: Scrapling 0.4.9 强依赖 playwright
- **症状**: 导入 `scrapling` 时 `ModuleNotFoundError: No module named 'playwright'`
- **原因**: Scrapling 0.4.x 把 playwright 作为硬依赖(导入期需要)
- **解决**: 改用 `httpx` + `parsel`(已在依赖中),零新依赖
- **影响**: Phase 2 改写 endpoints.py + client.py

### Bug 2: 研招网 Vue SPA + URL 变更
- **症状**: `/zsml/queryAction.do` 返回 404
- **原因**: 2026 研招网升级为 Vue 2 SPA,旧 .do 接口转登录
- **解决**: 改用 `/sch/` `/kyzx/zsjz/` 等静态 HTML 入口

### Bug 3: langgraph 1.2.5 SqliteSaver async 限制
- **症状**: `NotImplementedError: The SqliteSaver does not support async methods`
- **原因**: langgraph 1.2.5 把 SqliteSaver 标记为 sync,async 用 AsyncSqliteSaver
- **解决**: 改用 `MemorySaver`(自用可接受,重启 Chainlit 才丢会话)

### Bug 4: Chroma 1.5.x Rust bindings 多线程 bug
- **症状**: `AttributeError: 'RustBindingsAPI' object has no attribute 'bindings'` / `KeyError: 'D:\\...\\chroma'`
- **原因**: Chroma 1.5.x 的 Rust bindings 在 LangGraph ToolNode thread executor 跨线程崩溃
- **解决**: vector_repo 改用**启动时一次性加载到内存 + EphemeralClient**(完全 in-memory,线程安全)
- **影响**: 重新设计 vector_repo.py,失去 in-process 写入能力(只读)

### Bug 5: MiniMax M3 真实存在(我之前判断错误)
- **症状**: 需求文档写 "MiniMax-M3",本地知识库说 "无 M3"
- **原因**: 本地知识库是 M2.7 时代的过时版本
- **解决**: 实时拉官网 `https://platform.minimaxi.com/docs/guides/models-intro`,确认 M3 是 **2026 新发布的 1M 上下文 Frontier Coding 模型**
- **教训**: AI 知识有截止,关键技术细节必须验证官网

### Bug 6: MiniMax base_url 我之前是错的
- **症状**: 写 `.env.example` 时 placeholder 是 `api.MiniMax.com`
- **原因**: 我编的占位符,实际是 `api.minimaxi.com`
- **解决**: 写正确域名

### Bug 7: `client.reset()` 会**清空数据库**!
- **症状**: 测试时 count=0,数据丢失
- **原因**: Chroma 的 `reset()` 是 destructive,不是 close
- **解决**: 移除所有 `client.reset()` 调用,改用 `del client`

### Bug 8: LLM temperature=0.3 触发 MiniMax 范围错误
- **症状**: MiniMax 要求 `0 < x <= 1`
- **解决**: 改成 0.7

### Bug 9: chromadb 0.6.3 不兼容 1.5.x 数据格式
- **症状**: 降级到 0.6.3 后 KeyError: '_type'
- **解决**: 重新升回 1.5.9,改用 in-memory 策略

---

## 🎯 v0.1.0 MVP 验收(用户实操)

| 测试 | 结果 |
|---|---|
| Chainlit 启动 | ✅ HTTP 200, 2.8s 响应 |
| 页面渲染 | ✅ 标题 "研途萤火",完整用户画像显示,4 个示例 query |
| Query "CCNU 复试分数线多少?" | ✅ M3 调 search_local + 实时抓 yz.chsi.com.cn,1715 字符综合回答,带 2 个信源 |
| Tool 调用可视化 | ✅ LangGraph 工具节点正确执行 |
| 流式输出 | ✅ 累积到 final answer |

---

## 🛡️ 信息查询边界(明确遵守)

**只做"报名前"的预研,严格不爬**:
- ❌ 成绩查询(`/apply/cjcx/`)
- ❌ 调剂信息(`/sytj/`)
- ❌ 录取名单(`/zsgs/`)
- ❌ 复试名单(`/zsgs/listZszc--infoId-...`)
- ❌ 个人信息(身份证/手机号)

**法律依据**: 《刑法》285 条(非法侵入计算机信息系统罪)、253-1 条(侵犯公民个人信息罪 3-7 年)

---

## 📊 性能指标

- **数据规模**: 10 个 seed 文件 → 204 个 Chroma chunks
- **检索质量**: top-1 距离 0.27 命中核心信息(CCNU 257)
- **响应时间**: M3 + tool 调用 ~10s/轮(2 轮 tool + 1 轮综合)
- **Embedding**: bge-small-zh-v1.5 (512 维, ~260MB 一次性下载)
- **存储**: SQLite 1 文件 + Chroma 1 文件 (~2.5MB),全在 `./data/`

---

## 📁 项目结构

```
D:\WORKSTATION\Glimmer Guide\
├── PROGRESS.md                 ← 本文件
├── README.md
├── LICENSE (MIT)
├── pyproject.toml
├── environment.yml
├── .env.example
├── .gitignore
├── .chainlit/
│   └── config.toml             ← 主题 + 项目元信息
├── Document/                   ← [不入库] 调研资料 + 研究报告
├── data/                       ← [不入库] 运行时数据
│   ├── yanzhao.db              ← SQLite
│   └── chroma/                 ← Chroma 持久化
├── models/                     ← [不入库] bge 模型缓存
├── seed/                       ← [不入库] 种子资料
│   ├── user_profile.default.json
│   ├── 沈阳农业大学/
│   ├── 华中师范大学/
│   └── CCNU_调研/
├── scripts/
│   ├── bootstrap.sh
│   └── ingest_seed.py
├── src/yantu/
│   ├── __init__.py
│   ├── config.py
│   ├── data/
│   │   ├── db.py
│   │   ├── models.py
│   │   ├── user_profile.py
│   │   └── vector_repo.py       (in-memory 版)
│   ├── ingest/
│   │   ├── pdf_parser.py
│   │   ├── md_parser.py
│   │   ├── chunker.py
│   │   ├── indexer.py
│   │   └── seed_loader.py
│   ├── scraper/
│   │   ├── client.py
│   │   └── endpoints.py
│   ├── mcp/
│   │   └── server.py
│   ├── graph/
│   │   ├── state.py
│   │   ├── tools.py
│   │   ├── nodes.py
│   │   └── agent.py            (MemorySaver)
│   ├── ui/
│   │   └── app.py              (Chainlit)
│   └── utils/
│       ├── llm.py
│       ├── embedder.py
│       └── logger.py
```

---

## ⚠️ 已知限制 & 后续 TODO

### 已知限制
1. **ChromDB 写入**: vector_repo 当前是只读 in-memory 模式,新增 chunks 需要重启 Chainlit
2. **LangGraph 持久化**: 用 MemorySaver,重启 Chainlit 丢会话
3. **API key**: 用户的 key 已在对话历史中泄露过,**应作废旧 key 并生成新 key**
4. **5 个 web tool**: 覆盖 5 个研招网入口,其他功能(调剂、录取)按设计明确不爬

### v0.2.0 候选功能
- [ ] 异步 SqliteSaver lifespan(保留会话历史)
- [ ] Chroma in-memory 写回磁盘(atexit 钩子)
- [ ] Chainlit 设置面板的用户画像 JSON 编辑 UI
- [ ] 流式响应可视化(分块输出)
- [ ] LangSmith tracing 集成
- [ ] 更多研招网源(`/bsmlcx/` 博士目录)

### v0.3.0 候选
- [ ] 院校对比表(结构化输出)
- [ ] 历年分数线趋势(本地数据 + Chroma)
- [ ] 个人进度跟踪(背书进度、模拟考)
- [ ] 时间轴面板(报名/网上确认/初试/复试 倒计时)

---

## 📜 启动方式

```bash
conda activate Glimmer
cd "D:\WORKSTATION\Glimmer Guide"
# 一次性摄入(已有数据可跳过)
python -m scripts.ingest_seed
# 启动
chainlit run src/yantu/ui/app.py
# 浏览器 http://127.0.0.1:8000
```

---

## 📌 Git 状态(预期)

```
9 个 commit on main:
efcbe20 feat: initial project scaffold for yantu (研途萤火)
4e19ac8 feat(phase-0.5): user profile module
f182a0d feat(phase-1): local data ingestion
558a16b feat(phase-2): yanzhao-mcp with 5 anonymous tools
2b46546 feat(phase-3): LangGraph agent
a68150b feat(phase-4): Chainlit Web UI
28172ce feat(phase-5): polish + docs
1836fae fix: Chroma 1.5.x + .env MiniMax-M3
<pending>  docs: PROGRESS.md + v0.1.0-mvp tag
```

---

**作者备注**: 这是个人自用项目,目的是辅助 2026 考研准备过程中的院校信息查询。所有数据爬取遵守研招网 robots.txt 和 ToS,严格不涉及成绩/调剂/录取等敏感信息。
