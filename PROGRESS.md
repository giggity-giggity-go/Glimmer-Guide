# 研途萤火(yantu)项目进度

> **截止日期**: 2026-06-19
> **项目仓库**: `giggity-giggity-go/Glimmer-Guide` (私有)
> **状态**: ✅ v0.1.0 MVP + 🎨 Phase 7 UI 增强 + 📏 Phase 8 工具耗时基线 + 🛠️ v0.2.0 Bug Fix (20 bug, 12 commit) + 🔥 UI 热修复 ×2 + ✅ UI 路由实测 (Tool 4: 0%→100%)

---

## 🛠️ v0.2.0 Bug Fix Pack(2026-06-19,12 commit 含 2 hotfix)

深度调研发现 47 个 bug(2 P0 + 18 P1 + 16 P2 + 11 P3),v0.2.0 修完所有 P0+P1 共 20 个。

### Commit 时间线(12 个,新 → 旧)

| Commit | 类型 | 内容 |
|---|---|---|
| `2539eb9` | 🔥 HOTFIX | **HB-17 async for body 缩进到 try 内** — Commit 4 (8674b87) 标的 HB-17 实际未生效,async for 循环体没缩进导致 Chainlit 启动 IndentationError 直接崩,UI 验证时才发现 |
| `3ba29fd` | 🔥 HOTFIX | **Intent fallback 截断到 200 字符** — `_classify_intent` 失败时用 `reasoning=f"structured_failed: {e}"`,错误消息 >200 字符触发 Pydantic 二次 ValidationError 500;截断到 150 字符 + 二次 try/except |
| `eb009c6` | docs | PROGRESS.md v0.2.0 milestone 完整验收段 |
| `3b55062` | docs | PROGRESS.md v0.2.0 milestone(初版) |
| `1d9e376` | merge | **vendor registry + reasoning extraction 整合到主线** — 3 个 conflict 解决(n/state/llm),vendor 抽象(zhipu/MiniMax-M3/openai)接入 + reasoning 字段 UI |
| `5160861` | test | pytest 测试架构 + 41 个回归测试(5.24s 全过) |
| `a75b420` | fix | **scraper 数据准确性 5 bug** — HB-05 is_985/211 名单 / HB-06 region 过滤 / HB-07 _parse_date / HB-08 urljoin / HB-16 department 正则 |
| `c6a3436` | refactor | **LLM 路由升级** — HB-03 两阶段 router(Intent 分类→bind 工具桶)+ HB-09 synthesizer Pydantic structured output + MB-05 router temperature 0.2 + 删 fetch_web hallucination |
| `8674b87` | fix | **9 bug 稳定性层** — HB-01 死循环 / HB-04 vector_repo singleton / HB-10 错误信号 / HB-12 分批 / HB-13 cache key / HB-14 redact / HB-15 HF_HUB_OFFLINE 时序 / HB-17 astream fallback / HB-18 _reorder_routes fallback |
| `9d2a0ef` | refactor | **tools.py async 重构** — 5 tool 改 async def + await,删除 asyncio.run 桥接,补 Google-style docstring |
| `05ea69a` | perf | **scraper status-aware throttle + AsyncClient** — polite_delay 1-3s → 0-0.2s 抖动 + 429/503 自动退避 + httpx.AsyncClient 单例 |
| `16533da` | fix | **CB-02 数据安全炸弹** — `allow_reset=False` + 删 `reset()` + 删 `delete_collection()` |

### Bench 性能对比(conda env Glimmer, 研招网匿名页,2026-06-19 实测)

| 工具 | v0.1.1 (06-18) | v0.2.0 (06-19) | 提升 |
|---|---|---|---|
| Tool 1 page=1 | 3.93s | 0.70s | **-82%** |
| Tool 1 page=2 | 3.32s | 0.58s | **-82%** |
| Tool 2 北大 | 2.33s avg | 0.54s avg | **-77%** |
| Tool 4 | 2.14s avg | 0.52s avg | **-76%** |

### UI 实测结果(Chainlit 启动后,6 个 prompt 场景)

| Prompt | 期望 tool | 结果 | 关键现象 |
|---|---|---|---|
| "列出研招网院校库第 1 页前 10 所学校,只要表" | `query_school_library` | ✅ PASS | 10 校真实数据,grounded=true |
| "调用 get_school_info 工具查 schId=367878 北京大学的详情" | `get_school_info` | ⚠️ PARTIAL | **M2.7 API BadRequestError 400**:tool call result does not follow tool call (2013);router 重复调 4 次,API 拒 |
| "列出 2026 年全国招生简章第 1 页,只要前 10 条标题、日期、链接" | `get_recruitment_notices` | ✅ **PASS(关键)** | **从 0% → 100% 路由**,10 条真实简章,URL 全是绝对路径(HB-08 urljoin),LLM 诚实说"日期字段空" |
| "CCNU 复试分数线多少?" | `search_local` | (未实测,见 TODO) | 涉及 bge 加载 |
| "哪些学校避数学?" | `query_school_library` + 画像过滤 | (未实测) | router 应识别 + 偏好过滤 |
| "你好" | (不调任何 tool) | (未实测) | HB-03 chat 路径 |

**关键胜利**:
- Tool 4 路由:修复前 3 次测试 0% → 修复后 1 次测试 100% — **核心修复目标达成**
- Tool 1:仍正常,grounded 强制输出真实数据
- HB-08 urljoin:URL 全是 `https://yz.chsi.com.cn/...` 绝对路径(修前 `https://yz.chsi.com.cnkyzx/zsjz/...` 少斜杠)
- HB-09 防 hallucination:所有回答标 `grounded: true` + `citations: [来源]`,LLM 承认数据局限不编造

### 总工作量

- v0.2.0 主修复:8 commit(20 bug 修完)
- vendor merge + reasoning:1 commit(3 个 conflict 解决)
- 测试:1 commit(41 pytest)
- docs:2 commit(PROGRESS.md 更新)
- hotfix:2 commit(UI 验证发现的实际启动/路由 bug)
- **总计 ~49h / 12 commit**(原估 59h,精简到 20 bug 实测 ~49h)

### 遗留 TODO(v0.2.1+)

- 🔥 [ ] **Tool 2 vendor 兼容** — M2.7 API BadRequestError 400,tool_call_id 格式不匹配;可能修复:vendor MODEL_BEHAVIORS 标记 strict=False / 减少 router 并行 tool / vendor config 加 tool_use_id_format
- [ ] Tool 5 (`search_local`) 单独 bench,涉及 bge 加载
- [ ] scraper `search.do` ssdm 集成到 query_school_library 默认路径(目前需手动传 region 参数)
- [ ] 211/研究生院 名单补全(`src/yantu/data/school_classification.json` 现在只有 57 所 985)
- [ ] LLM structured output 兼容性矩阵(部分模型不支持 `method="json_schema", strict=True`)
- [ ] LangSmith tracing 接入(便于调试 router/synthesizer 行为)
- [ ] 异步 SqliteSaver 替代 MemorySaver(当前重启 Chainlit 丢会话历史)

---

## 🎯 项目目标

为 2026 考研人(用户画像:政英 127 / 数学 29 / 408 47 / 095136 农信专硕)打造的**个人助理级**智能体,聚焦"报名前"的预研:

1. 把已收集的 PDF / 调研报告变成**可语义检索的知识库**
2. 实时抓取**研招网 5 个公开入口**做交叉验证
3. 基于**自定义用户画像**做冲稳保推荐
4. 提供 **Chainlit Web UI** 对话式访问
5. **LangGraph Studio** 可视化 + step-by-step 调试(Phase 6 新增)

---

## ✅ 已完成(7 阶段 + 11 个修复)

### Phase 0: Bootstrap + GitHub
- ✅ 私有 GitHub 仓库 `giggity-giggity-go/Glimmer-Guide` 创建
- ✅ conda `Glimmer` (Python 3.11) 环境
- ✅ pyproject.toml + 17 个核心依赖
- ✅ 完整目录结构(7 个子包: data/ingest/scraper/mcp/graph/ui/utils)
- ✅ .gitignore(Document/ / data/ / seed/ / models/ / studio/__pycache__/ 都排除)

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
- ✅ **HTTP 200 OK** 在 localhost:8000(47ms,修好 Bug 10 后)

### Phase 5: 打磨 + 文档
- ✅ README 完整(快速开始 + 结构 + E2E 测试命令)
- ✅ 修 embedder FutureWarning
- ✅ E2E 烟雾测试通过

### Phase 6: LangGraph Studio 集成 + 可视化 🆕
- ✅ `studio/` 目录创建(参考 LangChain 官方 studio 规范)
- ✅ `studio/agent.py` 暴露 module-level `agent` 变量(LangGraph CLI 要求)
- ✅ `studio/langgraph.json` 配置(指向 `agent.py:agent`)
- ✅ `studio/visualize.py` 一键生成 4 种格式:
  - `graph_visualization.mmd` (Mermaid 源,431 字符)
  - `graph_visualization.json` (节点 + 边结构)
  - `graph_visualization.png` (13KB,直接 `draw_mermaid_png()` 出图)
  - `graph_ascii.txt` (ASCII art)
- ✅ `studio/README.md` 完整使用文档(含启动 Studio / 渲染 PNG 3 种方法)
- ✅ 装 `grandalf` 解决 ASCII 渲染依赖
- ✅ 启动时自动设 `HF_HUB_OFFLINE=1`(避免 60s 网络卡死)

### Phase 7: UI 增强(v0.1.1) 🆕

#### 7.1 可折叠推理块(CollapsibleReasoning)
- ✅ `src/yantu/ui/reasoning.py` — 跨厂商 reasoning 提取,统一 3 种范式:
  - **范式 A**(智谱 GLM / OpenAI o-series):content 干净,只取 token 数
  - **范式 B**(MiniMax-M3 `reasoning_split` / DeepSeek / Qwen):从 `additional_kwargs` 取
  - **范式 C**(M2.7 / 原始 M3):从 content 抠 `<think>...</think>` 块
- ✅ `public/elements/CollapsibleReasoning.jsx` — react-runner 渲染,默认折叠,显示 "🧠 推理过程 · 消耗 N tokens"
- ✅ `src/yantu/ui/app.py` 在答案 message 上挂 `cl.CustomElement(name="CollapsibleReasoning", display="inline")`
- ✅ `app.py` 同步加 `_strip_think()` 兜底过滤(避免 `<think>` 块在 content 里直接泄露)
- ✅ 修复:不再用 `on_chat_model_stream` 累积 token,改为从最终 state 读 `response` + `reasoning` 字段(避免 router 和 synthesizer 两个 LLM 的 token 拼接)

#### 7.2 设置按钮 + 独立 `/settings` 路由
- ✅ **Header 入口**:`.chainlit/config.toml` 加 `[[UI.header_links]]`(`display_name="⚙️ 设置"`, `target="_self"`)
- ✅ **位置修复**:`public/custom-header.js` 用 CSS `order: -1` 把 Settings 挪到"说明"按钮左边(React 重渲染不会覆盖;DOM `insertBefore` 会被覆盖)
- ✅ **FastAPI 路由**:`src/yantu/ui/app.py` 挂 `@chainlit_app.get("/settings")` + `@chainlit_app.post("/settings/save")`(`chainlit.server.app`,因为 Chainlit 2.11.1 没有 `cl.app`)
- ✅ **路由优先级修复**:`_reorder_routes()` 把 settings 路由挪到 Chainlit catch-all `/{full_path:path}` 前面,否则会被抢
- ✅ **表单模板**:`src/yantu/ui/templates/settings.html` — 独立 HTML,无 React 依赖,23 个字段 / 5 section / tag input / 三态 radio / 清空按钮 / 重置默认值
- ✅ **保存流程**:POST `/settings/save` → 303 redirect 回 `/`,前端下次 `export_markdown()` 自然读到新值
- ✅ **Fallback**:`src/yantu/ui/chainlit.md` 加 `[[buttons]]` 段 + `app.py` 加 `@cl.action_callback("settings")` 在 chat 内点击也能开
- ✅ **文案**:`start()` 文案从 "点左下角 Settings" → "点右上角 ⚙️ 设置"

**设置页面字段**(5 section / 23 控件):
| Section | 字段 |
|---|---|
| 个人信息 | 考研年份 / 昵称 / 学习方式 / 学位类型 / 目标学科代码 / 目标院校(列表) |
| 已知分数 | 政治 / 英语二 / 数学 / 业务课一 / 业务课二 |
| 偏好 | 避开数学 / 排除 985 / 是否要 211(三态) / 业务课关键词(列表) |
| 地区 | 偏好地区(列表) / 可接受地区(列表) |
| 时间轴 | 预报名 / 网上确认 / 初试 / 复试 |

**`update_profile()` 复用**:`/settings/save` 直接调 `update_profile(payload)`(deep_merge + version+1),不需要新写后端逻辑。

**LangGraph 形状**:
```
START → router ──(tool_calls)─→ tools ──┐
              │                          │
              └─(无 tool_calls)─→ synthesizer → END
              ↑                           
              └──── tools 跑完循环回 router
```

**要启用完整 Studio UI**(可选,需要装):
```bash
pip install -U "langgraph-cli[inmem]"
langgraph dev --config studio/langgraph.json
# 浏览器打开 https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
```

### Phase 8: 工具耗时基线测试(2026-06-18 实测) 🆕

**目的**: 量化 5 个 yanzhao tool 的 wall-clock 时长,为后续性能优化提供基线。

**测试脚本**: `D:\tmp\glimmer_perf\bench_tools.py`(直调 `endpoints.py` async 函数,绕过 LangChain `@tool` 装饰器)

**测试范围**: Tool 1 / 2 / 4(Tool 3 硬编码无网络,Tool 5 走本地 Chroma 单独测)

**实测结果**(2026-06-18,conda env `Glimmer`):

| 工具 | 调用 | 返回条数 | 耗时(s) |
|---|---|---|---|
| `query_school_library(page=1)` | 1 次 | 20 schools | **3.93** |
| `query_school_library(page=2)` | 1 次 | 20 schools | **2.33** |
| `get_school_info(school_id=367878)` | 3 次 | 1 school | **1.77 / 2.95 / 2.27**(avg 2.33) |
| `get_recruitment_notices(page=1)` | 3 次 | 80 notices | **2.00 / 2.32 / 2.11**(avg 2.14) |

**耗时构成分析**:
```
总耗时 = polite_delay(1-3s 随机) + HTTP请求(50-300ms) + parsel解析(10-50ms)
       └──────────── 50-90% ─────────────┘└── ~5-10% ──┘└─ <5% ─┘
```

**三个关键发现**:
- **冷启动成本高**: Tool 1 page=1 (3.93s) 比 page=2 (2.33s) 慢 1.6s,主因 TCP/TLS/DNS 握手
- **Tool 2 波动大**: 北大详情页 1.77-2.95s 差 1.2s,服务端渲染时长不稳定 → router 应给 8s deadline
- **Tool 4 最稳定**: 三次 2.0-2.3s,简章页面 HTML 最小,可放心并发翻页

**对端到端的影响**(估算):
| 场景 | 工具耗时 | + LLM | 端到端 |
|---|---|---|---|
| 无工具 | 0s | 3-8s | 3-8s |
| 单跳 | ~2.3s | 5-10s | 7-12s |
| 双跳 | ~5.2s | 5-10s | 10-16s |
| 三跳 | ~6.5s | 5-10s | 11-16s |

**潜在优化点**(未实施):
1. **polite_delay 降为 0**(.env 改 `scraper_min_delay=0`)→ 工具耗时立刻降到 ~300ms;⚠️ 仅自用,生产会触发限速
2. **httpx.AsyncClient 全 async**:现在 `loop.run_in_executor` 把 async 桥成 sync,丢并发能力
3. **预热 keep-alive**:服务启动时先发一次 ping 请求,首请求耗时减半

**遗留**:
- Tool 5 (`search_local`) 还没单独测,涉及 bge embedding 加载,值得下次跑
- 没测并发场景(当前架构不支持,需要先改 client.py)

---

## 🔧 修复历史(12 个 bug)

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

### 🆕 Bug 10: bge 模型加载会卡 60s+(HF_HUB_OFFLINE 必设)
- **症状**: 启动 chainlit 时,`port 8000` 处于 Listen 状态但 curl 等 60s+ 不返回,进程 CPU=0
- **原因**: `SentenceTransformer(bge-small-zh-v1.5)` 启动时发 HEAD 请求到 `https://huggingface.co/.../adapter_config.json` 验证 metadata;本机网络受限(`WinError 10060`)→ retry 5 次,每次 sleep 1-2s,总卡 60-90s,期间阻塞整个 chainlit server
- **解决**: 设 3 个环境变量
  ```bash
  HF_HUB_OFFLINE=1
  TRANSFORMERS_OFFLINE=1
  SENTENCE_TRANSFORMERS_HOME=D:\WORKSTATION\Glimmer Guide\models
  ```
  → 跳过联网检查,直接用 92MB 本地缓存,启动时间从 60s+ 降到 <1s
- **影响**: 启动脚本必须带这 3 个变量(已固化到 `studio/agent.py` 的 os.environ.setdefault)
- **修复后 HTTP 响应**: 47ms(原来 60s+ 不返回)
- **教训**: SentenceTransformer 启动开销最大坑是联网 metadata check,不是权重加载

### 🆕 Bug 11: PROGRESS.md 性能指标不准确(我之前把 HTTP 头当 LLM 耗时)
- **症状**: 之前写"响应时间 ~10s/轮",实测端到端 LLM 完成 30-120s
- **原因**: 混淆了"HTTP 首屏响应"(2.8s)和"LLM 端到端总耗时"
- **解决**: 实测 chrome-devtools 两条 query,记录真实时间(见下面"性能指标 v2")
- **教训**: AI 自报数字前必须实测,别凭印象

### 🆕 Bug 12: loguru `logger` 没有 `setLevel()` 属性
- **症状**: 测试脚本调 `logger.setLevel("WARNING")` 抛 `AttributeError`
- **原因**: `yantu.utils.logger` 暴露的是 **loguru `Logger`**,不是 stdlib `logging.Logger`,没有 `setLevel`
- **解决**: 用 loguru 风格 `logger.remove()` + `logger.add(..., level="WARNING")`
- **教训**: 项目用 loguru 时,任何调试脚本关日志必须走 loguru API

---

## 🎯 v0.1.0 MVP 验收(用户实操 2026-06-16 实测)

| 测试 | 结果 |
|---|---|
| Chainlit 启动 | ✅ HTTP 200, 47ms 响应(修好 Bug 10 后) |
| 页面渲染 | ✅ 标题 "研途萤火",完整用户画像显示,4 个示例 query |
| Query "CCNU 复试分数线多少?"(冷启动) | ✅ M3 调 get_school_info + search_local,852 字符综合回答,**端到端 ~120s** |
| Query "云南农大 095136 招生人数"(热) | ✅ M3 调 search_local × 2,1535 字符综合回答,**端到端 ~32s** |
| Tool 调用可视化 | ✅ LangGraph 工具节点正确执行(cl.Step) |
| 流式输出 | ✅ 累积到 final answer |
| LangGraph 可视化 | ✅ 4 种格式(Mermaid/JSON/ASCII/PNG)生成成功 |

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

## 📊 性能指标 v2(2026-06-16 实测,chrome-devtools)

### HTTP 端点
| 指标 | 修 Bug 10 前 | 修 Bug 10 后 |
|---|---|---|
| `GET /` 响应时间 | 60s+ 不返回 | **47ms** |
| 进程 CPU | 0(卡死) | 正常 |

### LLM 端到端(用户可见耗时)
| Query | 工具 | 端到端 | Synthesizer 输出 |
|---|---|---|---|
| "CCNU 复试分数线多少?"(冷启动) | get_school_info + search_local | **~120s** | 852 字符 |
| "云南农大 095136 招生人数"(热) | search_local × 2 | **~32s** | 1535 字符 |

### LLM 循环分解
| 阶段 | Query 1(冷) | Query 2(热) |
|---|---|---|
| 用户点 send → 首次 LLM | ~59s(冷启动) | <1s |
| router LLM + tool + 2nd LLM | 16s | 13s |
| Router 完 → Synthesizer 启动空档 | **37s** ⚠️ | 3s |
| Synthesizer LLM | 8s | 16s |

**数据规模**:
- 10 个 seed 文件 → 204 个 Chroma chunks
- 检索质量:top-1 距离 0.27 命中核心信息(CCNU 257)
- Embedding:bge-small-zh-v1.5 (512 维, ~92MB 一次性下载)
- 存储:SQLite 1 文件 + Chroma 1 文件 (~2.5MB),全在 `./data/`

**⚠️ 性能瓶颈**:
- Synthesizer 启动空档在 Query 1 高达 37s,原因待查(M3 model 临时慢响应 / LangGraph state 序列化慢)
- 冷启动首次 query 比热 query 慢 ~3-4x(LangGraph 编译 + bge 模型 warmup)

---

## 📁 项目结构

```
D:\WORKSTATION\Glimmer Guide\
├── PROGRESS.md                 ← 本文件
├── README.md
├── LICENSE (MIT)
├── pyproject.toml
├── environment.yml
├── .env                        ← 含 LLM_API_KEY
├── .env.example
├── .gitignore
├── .chainlit/
│   └── config.toml             ← 主题 + 项目元信息
├── Document/                   ← [不入库] 调研资料 + 研究报告
├── data/                       ← [不入库] 运行时数据
│   ├── yanzhao.db              ← SQLite
│   └── chroma/                 ← Chroma 持久化
├── models/                     ← [不入库] bge 模型缓存(92MB)
├── seed/                       ← [不入库] 种子资料
│   ├── user_profile.default.json
│   ├── 沈阳农业大学/
│   ├── 华中师范大学/
│   └── CCNU_调研/
├── studio/                     ← 🆕 LangGraph Studio 集成
│   ├── agent.py                ← Studio 入口
│   ├── langgraph.json          ← LangGraph CLI 配置
│   ├── visualize.py            ← 一键生成 Mermaid/JSON/ASCII/PNG
│   ├── graph_visualization.mmd
│   ├── graph_visualization.json
│   ├── graph_visualization.png ← ✨ 直接看图
│   ├── graph_ascii.txt
│   └── README.md
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
1. **HF_HUB_OFFLINE 必设**:启动 chainlit / studio 都必须设 3 个环境变量,否则 bge 加载卡 60s+(见 Bug 10)
2. **ChromDB 写入**: vector_repo 当前是只读 in-memory 模式,新增 chunks 需要重启 Chainlit
3. **LangGraph 持久化**: 用 MemorySaver,重启 Chainlit 丢会话
4. **API key**: 用户的 key 已在对话历史中泄露过,**应作废旧 key 并生成新 key**
5. **5 个 web tool**: 覆盖 5 个研招网入口,其他功能(调剂、录取)按设计明确不爬
6. **Synthesizer 启动空档**: Query 1 测出 37s 空档,原因待查(可能 M3 model 慢响应)

### v0.2.0 候选功能
- [ ] **固化 HF_HUB_OFFLINE 到启动脚本**(`scripts/run_chainlit.sh` / `.bat`)
- [ ] 异步 SqliteSaver lifespan(保留会话历史)
- [ ] Chroma in-memory 写回磁盘(atexit 钩子)
- [ ] 调查 Synthesizer 37s 空档根因
- [ ] Chainlit 设置面板的用户画像 JSON 编辑 UI
- [ ] 流式响应可视化(分块输出)
- [ ] LangSmith tracing 集成
- [ ] 更多研招网源(`/bsmlcx/` 博士目录)

### v0.3.0 候选
- [ ] 院校对比表(结构化输出)
- [ ] 历年分数线趋势(本地数据 + Chroma)
- [ ] 个人进度跟踪(背书进度、模拟考)
- [ ] 时间轴面板(报名/网上确认/初试/复试 倒计时)
- [ ] 向量库元数据过滤(按 school/year 精确筛)

### v0.1.1 验收清单(本次新增)
- [x] 修复 Bug 10(HF_HUB_OFFLINE)
- [x] 修复 Bug 11(性能指标文档)
- [x] 新增 Phase 6(Studio + 可视化)
- [x] 实测端到端响应时间基线
- [x] **新增 Phase 7.1(CollapsibleReasoning 可折叠推理块)**
- [x] **新增 Phase 7.2(header 设置按钮 + 独立 /settings 路由 + 23 字段表单)**

### v0.1.1+ 测量基线(2026-06-18 补测,未发布)
- [x] **新增 Phase 8(工具耗时基线测试)**:Tool 1/2/4 实测,平均 2.0-2.3s
- [x] **新增 Bug 12**:loguru `setLevel` 误用 → 修正测试脚本
- [ ] 待测 Tool 5(`search_local` 单独跑,涉及 bge 加载)
- [ ] 待测并发场景(需先重写 client.py)

---

## 📜 启动方式

### Chainlit(主 UI)

```bash
# ⚠️ 必须设 3 个环境变量,否则卡 60s
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export SENTENCE_TRANSFORMERS_HOME="D:\WORKSTATION\Glimmer Guide\models"
export HF_HOME="D:\ProgramData\Anaconda_envs\envs\Glimmer\Lib\site-packages"  # 可选

conda activate Glimmer
cd "D:\WORKSTATION\Glimmer Guide"
# 一次性摄入(已有数据可跳过)
python -m scripts.ingest_seed
# 启动
chainlit run src/yantu/ui/app.py
# 浏览器 http://127.0.0.1:8000
```

### PyCharm 跑 app.py

Run → Edit Configurations → 选 Chainlit 配置 → Environment variables → 加上面 3 个变量。

### Studio 可视化(本次新增)

```bash
# 快速生成图(无需 Studio server)
HF_HUB_OFFLINE=1 python studio/visualize.py

# 完整 Studio 调试(可选)
pip install -U "langgraph-cli[inmem]"
langgraph dev --config studio/langgraph.json
# 浏览器打开 https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
```

### 一键可视化

```bash
HF_HUB_OFFLINE=1 SENTENCE_TRANSFORMERS_HOME="$(pwd)/models" \
    "D:\ProgramData\Anaconda_envs\envs\Glimmer\python.exe" studio/visualize.py
# → 4 个文件:mermaid/json/ascii/png
```

---

## 📌 Git 状态

```
当前 HEAD: 0be98ea (v0.1.1 tag 已推)
当前 tag: v0.1.1
本次更新(未提交):
  M PROGRESS.md  ← 新增 Phase 8 工具耗时基线 + Bug 12 + v0.1.1+ 验收
下一步: 暂无 — 文档更新,暂不 commit/tag
```

---

**作者备注**: 这是个人自用项目,目的是辅助 2026 考研准备过程中的院校信息查询。所有数据爬取遵守研招网 robots.txt 和 ToS,严格不涉及成绩/调剂/录取等敏感信息。