# 研途萤火(yantu)项目进度

> **截止日期**: 2026-06-21
> **项目仓库**: `giggity-giggity-go/Glimmer-Guide` (私有)
> **当前 vendor**: `minimax / MiniMax-M3`(2026-06-19 切换,v0.2.2 extra_body 修复后 M3 可用)
> **状态**: ✅ v0.1.0 MVP + 🎨 Phase 7 UI 增强 + 📏 Phase 8 工具耗时基线 + 🛠️ v0.2.0 Bug Fix (20 bug, 12 commit) + 🔥 UI 热修复 ×2 + ✅ UI 路由实测 (Tool 4: 0%→100%) + 🔧 v0.2.1 JSON 泄漏统一修复 (1 commit, 50/50 测试) + ✅ v0.2.2 M3 extra_body 修复 (1 commit, 53/53 测试) + 🚧 v0.3.0-alpha 多会话骨架 (1 commit, 71/71 测试) + 🚀 v0.3.0-beta PR-2 4 子项 (6 commit, 118/118 pytest) + 🧪 **Day 9 长期记忆实测修复 (synthesizer 注入 long_term_facts)** + 🎨 **Day 10 UI 优化 6 项(WS 推送 + 自定义 modal + 空态 + 键盘导航,浏览器实测通过,156/158 pytest)** + 🐛 **Day 10 修复项(4 浏览器实测 bug: 过滤空壳 / 键盘 useRef 桥接 / IME 感知 / activeId state 化,159/161 pytest,2 个历史行尾失败与本轮无关)**

---

## 🚀 v0.3.0-beta PR-2 落地报告(2026-06-20,6 commit,118 pytest)

**核心成果**:v0.3.0-alpha 4 张表(Sessions / MemoryFact / UserSetting / LangGraph checkpoint)从"空骨架"升级到"消费方全通",LLM 升级为"个人助理"(跨会话记忆 + 自动压缩 + 多会话侧边栏 + 软硬删级联)。

### 6 个 Commit 时间线

| Commit | 类型 | 内容 |
|---|---|---|
| `ecfff2e` | 🔧 fix | app.py 第 24 行损坏的 /mcp 前缀(从历史会话残留) |
| `b92827c` | ✨ feat(pr2) | **子项 4** hard_delete_session 释放 memory_facts(3 类处理)+ 10 pytest |
| `21acc3d` | ✨ feat(pr2) | **子项 1** 上下文自动压缩 + UserSetting CRUD + 15 pytest |
| `5e7481e` | ✨ feat(pr2) | **子项 3** 长期记忆(LangMem path A' + 35 pytest) |
| `c3701ea` | ✨ feat(pr2) | 3 JSX 面板(ContextSettings + MemoryPanel + SessionSidebar)+ TODO-1 字段名 fix |
| `410c942` | 🧪 test(pr2) | 4 个端到端 integration 测试覆盖 4 个 E2E prompt 场景 |

### 4 子项实现状态

| 子项 | 状态 | 关键文件 | 测试数 |
|---|---|---|---|
| **1. 上下文自动压缩** | ✅ | `src/yantu/graph/compressor.py` + `data/user_settings.py` | 15 |
| **2. SessionSidebar.jsx** | ✅ | `public/elements/SessionSidebar.jsx` + 5 silent action_callbacks | (JSX 手动验证) |
| **3. 长期记忆** | ✅ | `src/yantu/memory/{schemas,retriever,extractor,langmem_bridge}.py` | 35 |
| **4. hard_delete 释放 memory_facts** | ✅ | `src/yantu/session/cleanup.py` | 10 |

### 关键架构决策(中途变更)

1. **LangMem 路径从 A → A'**:Day 1 验证发现 langmem 0.0.30 实际用 LangGraph `BaseStore`(不是 LangMem 自有),写 12 个方法的 Chroma adapter 工作量大。**改用 A':LangMem InMemoryStore + 独立 Chroma RAG + SQLite memory_facts 是 source of truth,InMemoryStore 进程启动时从 SQLite rehydrate**。
2. **trim_messages 改自实现**:langchain 1.3.10 的 `trim_messages(strategy="last", max_tokens=N)` 实测未生效(max_tokens=30 但 12 token/msg × 10 msg 全保留)。**改自实现 _trim_to_window**(20 行)。
3. **compressor 改 async 路由**:`pre_model_hook` 是 create_react_agent 专属,本项目用 StateGraph 手搭,**改 router 为 async def + await compress_context_if_needed**。

### 测试结果(118 passed)

- 原 71 测试(无回归)
- 新增 47 测试:
  - `tests/data/test_user_settings.py`:7
  - `tests/graph/test_compressor.py`:8
  - `tests/session/test_cleanup.py`:10
  - `tests/memory/test_schemas.py`:10
  - `tests/memory/test_retriever.py`:5
  - `tests/memory/test_extractor.py`:20
  - `tests/integration/test_v030beta_e2e.py`:4 (4 个 E2E prompt 场景)
- 修复:`tests/session/test_manager.py` 的 hard_delete 测试(适配 async router)

### 4 个 E2E Prompt 场景(Python 层验证)

| # | 场景 | 测试方法 |
|---|---|---|
| 1 | 35 轮对话 → 触发压缩 | `test_35_rounds_trigger_compression`(小 window 模拟) |
| 2 | 跨会话召回事实 | `test_recall_fact_from_different_session`(mock Chroma) |
| 3 | 删会话 → cleanup 3 类处理 | `test_delete_session_processes_3_fact_classes` |
| 4 | preference 跨会话保留 | `test_preference_preserved_across_session_delete` |

### 端到端浏览器验证(待 PR-3)

JSX 组件需浏览器实测:
- `display="side"` 在 Chainlit 2.11.1 的实际行为
- 5 秒轮询在多 tab 同时打开时的并发
- 滑块 onChange 实时回写 user_settings

### 后续(v0.3.0-rc / final)

- 实测 4 个 E2E prompt 在真实浏览器
- chainlit run app.py 启动 + 浏览器测试
- 如果 display="side" 不工作 → fallback inline + position:fixed
- 修 LangMem vendor 兼容问题(待定)

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

- 🔥 [ ] **M3 Intent classifier `function_calling` BadRequest 400** — v0.2.2 实测 M3 切到 `extra_body={"reasoning_split": True}` 后 HTTP 不再 TypeError,但 `llm.with_structured_output(Intent, method="function_calling").invoke(...)` 仍 100% 返回 BadRequestError 400(v0.2.2 后端日志可见)→ fallback 到 `target="both"` → 5 个工具全绑 → 单 query 拖 90s+(走 MAX_TOOL_ROUNDS=5 才进 synthesizer);可能修复:vendor MODEL_BEHAVIORS 给 M3 加 `{"function_calling": False}` 标记让 classifier 走 plain-text + 正则抽取,或直接给 M3 走 jieba/规则分类绕过 LLM
- 🔥 [ ] **Tool 2 vendor 兼容** — M2.7 API BadRequestError 400,tool_call_id 格式不匹配;可能修复:vendor MODEL_BEHAVIORS 标记 strict=False / 减少 router 并行 tool / vendor config 加 tool_use_id_format
- [x] ~~**MiniMax-M3 `reasoning_split` 修复** — `model_kwargs={"reasoning_split": True}` 被 OpenAI SDK 拒绝(TypeError),需要改 `extra_body={"reasoning_split": True}`(LangChain 官方推荐 vendor-specific 参数走 extra_body)+ `vendors.py` 字段名 `model_kwargs` → `extra_body` + `llm.py` cache key 包含 extra_body(否则切 vendor cache 失效)~~ → **v0.2.2 已修**,实测 M3 HTTP 不再 TypeError,UI 显示纯中文
- [ ] zhipu Intent classifier 1214 错误绕过 — `function_calling` 在 glm-5.1 报 BadRequestError,zhipu 端需用其原生接口(非 OpenAI 兼容协议),降级 TODO;短期方案是接受 fallback 到 `target="both"`(Router LLM 自己判断 tool_calls,实测 4/4 走通)
- [ ] Tool 5 (`search_local`) 单独 bench,涉及 bge 加载
- [ ] scraper `search.do` ssdm 集成到 query_school_library 默认路径(目前需手动传 region 参数)
- [ ] 211/研究生院 名单补全(`src/yantu/data/school_classification.json` 现在只有 57 所 985)
- [x] LLM structured output 兼容性矩阵(部分模型不支持 `method="json_schema", strict=True`) → v0.2.1 已修,统一改 `method="function_calling"`(但 Intent classifier 在 zhipu 仍坏,见上)
- [ ] LangSmith tracing 接入(便于调试 router/synthesizer 行为)
- [ ] 异步 SqliteSaver 替代 MemorySaver(当前重启 Chainlit 丢会话历史)
- [x] ~~minimax M2.7-highspeed v0.2.1 UI 实测(切回 minimax vendor 后 4 prompt 验证)~~ → **v0.2.2 改为 M3 实测**,M2.7-highspeed 未跑

---

## 🔧 v0.2.1 JSON 泄漏统一修复(2026-06-19,1 commit)

### 问题
Chainlit UI chat 偶尔显示 `json\n{"answer": ..., "citations": ..., "grounded": ...}` 文本给用户,而不是干净的 AI 回答。**实测 100% 复现**:glm-5.1 在合成器 fallback 路径必吐 ` ```json\n{...}\n``` ` markdown fence 包裹的 JSON,Chainlit 原样渲染。

### 根因(2 步触发,3 个 vendor 都中招)
1. **主路径必失败**:`with_structured_output(FinalAnswer, method="json_schema", strict=True)` 在 glm-5.1 / MiniMax-M2.7 / MiniMax-M3 / o3-mini 4 个 vendor 上 100% 抛异常
   - glm / M2.7 / o3-mini:LLM 把 JSON 裹在 ` ```json ... ``` ` markdown fence 里,Pydantic strict 模式从 `<` 字符开始 parse 失败
   - M3:`reasoning_split=True` 被 OpenAI SDK 拒绝(TypeError)
2. **Fallback 路径泄漏**:`nodes.py:241-253` except 分支 `llm.invoke(msgs + [...])`,system prompt 仍含"- 输出 JSON,字段: ..." → LLM 看到矛盾指令 → 仍按 schema 输出 → fence JSON 字符串塞 `state["response"]`
3. **UI 层兜底失效**:`app.py:204` `_strip_think` 只 strip `<think>` 块,不管 ` ``` ` fence

### 为什么"有时正常有时泄漏"
glm-5.1 fallback **永远**输出 fence JSON,但当 query 让 LLM 在 fence 前生成 ≥200 字符中文 preamble 时,fence 被推到用户看不到的位置 → 看起来"正常"。Intent classifier 也因 fence 失败 → fallback 到 `target="both"` → ALL_TOOLS 5 个工具,造成部分 query 路由到 local tool 看到中文前置。

### 修复(4 处改动,1 个文件)

| # | 文件:行 | 改动 |
|---|---|---|
| 1 | `src/yantu/graph/nodes.py:144` | Intent classifier: `method="json_schema"` → `method="function_calling"` |
| 2 | `src/yantu/graph/nodes.py:251` | 删 system prompt `- 输出 JSON,字段: answer / citations / grounded`(避免矛盾指令) |
| 3 | `src/yantu/graph/nodes.py:262` | Synthesizer: `method="json_schema"` → `method="function_calling"` |
| 4 | `src/yantu/graph/nodes.py:284` | Fallback 路径加 `_strip_fenced_json(content)`(双保险,fence 不再泄漏) |

`_FENCE_JSON_RE = re.compile(r"```(?:json)?\s*\n(\{.*?\})\n```", re.DOTALL)` — 非贪婪,只在 fence 包裹下生效。

### 测试覆盖(7 个新 pytest)
- `tests/graph/test_synthesizer_json_leak.py`:5 个 `_strip_fenced_json` 单测 + 2 个 synthesizer 集成测(主路径 + fallback)
- **总测试数**:41 → 50(+7 个新增,全部通过)

### UI 实测(4 prompt,glm-5.1)
| Prompt | 实测 answer_chars | 工具 | JSON 泄漏 |
|---|---|---|---|
| `你好` | 309 | 无 | ❌ 无 |
| `北京大学 信息公开` | 444 | query_school_library + get_school_info | ❌ 无 |
| `CCNU 复试分数线` | 374 | search_local | ❌ 无 |
| `云南农大 招生人数` | 361 | search_local (max rounds) | ❌ 无 |

**4/4 全部干净返回 markdown 渲染的中文回答**,无 JSON 文本。

### Vendor 兼容性矩阵(v0.2.1 + v0.2.2 实测,2026-06-19)

| Vendor | Model | Intent `function_calling` | Synthesizer `function_calling` | Router `bind_tools` | UI 实测 (4 prompt) |
|---|---|---|---|---|---|
| **minimax** | M3(当前) | ⚠️ BadRequest 400 → fallback both | ✅ 200 OK | ✅ 200 OK | ✅ 2/4 实测无 JSON 泄漏("你好" + "北京大学");CCNU/云南农大因 Intent 反复 400 走 MAX_TOOL_ROUNDS 慢 |
| minimax | M2.7-highspeed | (待实测) | (待实测) | (待实测) | (待实测) |
| minimax | M2.7 | (历史 401) | (历史 401) | (历史 401) | n/a (key 失效) |
| zhipu | glm-5.1 | ❌ BadRequestError 1214 → fallback both | ✅ 200 OK | ✅ 200 OK | ✅ 4/4 干净(实测 309/444/374/361 字符) |

#### v0.2.2 新增 M3 实测(2026-06-19,2/4 prompt)

**好消息**:
- `extra_body={"reasoning_split": True}` 修复后,M3 HTTP 请求全部 200,**TypeError 不再发生**
- 后端日志确认:`Creating ChatOpenAI: vendor=MiniMax, model=MiniMax-M3, ... extra_body={'reasoning_split': True}`
- "你好" prompt 干净返回:"你好呀!我是研途萤火(yantu)..."(含用户画像渲染)
- "北京大学 信息公开" 调 query_school_library + get_school_info,返回完整 markdown 渲染(北大 985 提醒 + 招生简章/调剂办法链接)

**新发现(M3 vendor + function_calling 协议 BadRequest 400)**:
- Intent classifier `llm.with_structured_output(Intent, method="function_calling").invoke(...)` 在 M3 上 100% 返回 `BadRequestError 400 - bad_request_err`
- 每次 router 前都重试 1 次(2 次 HTTP 400 才进 fallback)
- fallback 到 `target="both"` → 5 工具全绑 → LLM 反复调 query_school_library,走到 MAX_TOOL_ROUNDS=5 才进 synthesizer
- 单 query 端到端 90-120s(Intent 2 次 + router 2 次 + 5 工具 + synthesizer 主路径失败 + fallback invoke)
- Synthesizer 报 `'NoneType' object has no attribute 'answer'` — M3 返回的 FinalAnswer 结构异常,走 plain-text fallback

**已知问题**

- **Intent classifier `function_calling` 在 zhipu glm-5.1 / minimax M3 上 BadRequest**:zhipu 1214 + M3 400 → 都 fallback 到 `target="both"`(v0.2.0 hotfix 3ba29fd 生效)
- **v0.2.2 新副作用**:Synthesizer `function_calling` 在 M3 上返回结构异常 → `'NoneType' object has no attribute 'answer'` → 走 fallback plain-text → 但 fallback 路径正常工作,_strip_fenced_json 兜底,UI 显示干净中文
- **副作用**:greeting 类 chat intent 现在变成 "both"(5 个 tool 都给 LLM),但 LLM 自己决定不调 → 实际无 tool 调用 → 直接 synthesize → 干净回答
- **zhipu 真要修 Intent 1214**:zhipu 端需要用其原生 `with_structured_output` 接口(非 OpenAI 兼容协议),降级为后续 TODO
- **M3 真要修 Intent 400**:可能路径:vendor MODEL_BEHAVIORS 给 M3 加 `function_calling=false` 标记让 classifier 走 plain-text + 正则抽取,或给 M3 走规则分类(jieba 关键词匹配)绕过 LLM(见 v0.2.1+ TODO)

#### minimax M2.7-highspeed 实测(2026-06-19,未跑)
v0.2.2 切到 M3 实测,M2.7-highspeed 没跑。预期 `function_calling` 在 minimax 端可工作(实测 deep-research w9ycuvps4 阶段 `function_calling_works=true`),但 M3 400 问题可能在 M2.7-highspeed 同样存在(同 vendor 同协议)。**待补实测结果**。

---

## ✅ v0.2.2 MiniMax-M3 extra_body 修复(2026-06-19,1 commit)

### 问题
用户切到 minimax / MiniMax-M3 后,所有 LLM 调用都报:
```
处理失败(TypeError): Completions.create() got an unexpected keyword argument 'reasoning_split'
```
Chainlit 完全无法对话,任何 prompt 都走兜底错误页。

### 根因
`vendors.py:50` 把 `reasoning_split=True` 放到 `MODEL_BEHAVIORS["MiniMax-M3"]["model_kwargs"]`,`llm.py` 通过 `ChatOpenAI(model_kwargs=v.extra_model_kwargs)` 传入。
LangChain `ChatOpenAI.model_kwargs` 会被合并到 OpenAI SDK 的 `client.chat.completions.create(**model_kwargs)` 顶层签名参数。OpenAI SDK 在 `chat.completions.create` 见到 `reasoning_split`(MiniMax 私有非标准参数)→ TypeError,因为它不在 OpenAI 签名里。

**LangChain 官方原话**(reference docs ChatOpenAI "`model_kwargs` vs `extra_body`" 段):
> "Do not use `model_kwargs` for custom parameters that are not part of the standard OpenAI API, as this will cause errors when making API calls. Use `extra_body` instead."

### 修复(2 个文件,1 个新 helper,53/53 测试通过)

| # | 文件:行 | 改动 |
|---|---|---|
| 1 | `src/yantu/utils/vendors.py:23` | `VendorConfig.extra_model_kwargs: dict` → `extra_body: dict`(字段重命名) |
| 2 | `src/yantu/utils/vendors.py:50` | `MODEL_BEHAVIORS["MiniMax-M3"]` 的 `model_kwargs` → `extra_body`(语法键名) |
| 3 | `src/yantu/utils/vendors.py:85` | 默认值 `{"model_kwargs": {}}` → `{"extra_body": {}}` |
| 4 | `src/yantu/utils/llm.py:33` | `_LLM_CACHE` key 从 3 元组 `(vendor, model, temp)` → 4 元组 `(vendor, model, temp, frozenset(extra_body.items()))`(cache key 加 extra_body,切 vendor/model 时不误用旧实例) |
| 5 | `src/yantu/utils/llm.py:68` | `ChatOpenAI(model_kwargs=...)` → `ChatOpenAI(extra_body=...)`(透传 HTTP body 绕开 SDK 签名校验) |
| 6 | `tests/utils/test_llm.py` | 2 个旧测试 `FakeVendor` dataclass 字段名更新 + 3 个新测试 `TestV022ExtraBody`(verify ChatOpenAI 收到 `extra_body` / 不收到 `model_kwargs` / extra_body 变化 invalidate cache) |

### pytest
```
tests/utils/test_llm.py::TestHB13CacheKey        4/4 PASSED
tests/utils/test_llm.py::TestV022ExtraBody       3/3 PASSED  ← 新增
tests/utils/test_llm.py::TestHB14RedactKey       4/4 PASSED
…
================== 53 passed in 5.47s ==================
```
50 → 53 测试(+3 个 v0.2.2 专项测试)。

### UI 实测(minimax M3,2026-06-19,2/4 prompt 干净)

后端日志确认 `extra_body={'reasoning_split': True}` 正确传递,HTTP 不再 TypeError:
```
Creating ChatOpenAI: vendor=MiniMax, model=MiniMax-M3, base_url=https://api.minimaxi.com/v1,
                     api_key=sk-c***Mr54, temperature=0.2, extra_body={'reasoning_split': True}
HTTP Request: POST https://api.minimaxi.com/v1/chat/completions "HTTP/1.1 200 OK"
```

| Prompt | 工具 | JSON 泄漏 | 实测状态 |
|---|---|---|---|
| `你好` | 无 | ❌ 无 | ✅ "你好呀!我是研途萤火(yantu)..."(含用户画像) |
| `北京大学 信息公开` | query_school_library + get_school_info | ❌ 无 | ✅ 完整 markdown 摘要(985 提醒 + 招生简章链接) |
| `CCNU 复试分数线` | query_school_library → MAX_TOOL_ROUNDS=5 | (未完整返回) | ⚠️ Intent 反复 400 走兜底 |
| `云南农大 招生人数` | (未测) | — | ⏸️ 同上 |

### 新发现的 M3 vendor 兼容性 bug(v0.2.2+,后续 TODO)

虽然 v0.2.2 解决了 `reasoning_split` TypeError,但实测暴露 2 个新问题:
1. **Intent classifier `function_calling` 在 M3 上 BadRequest 400** — 100% 失败 → fallback to both → 5 工具全绑 → 拖慢端到端 90-120s
2. **Synthesizer `function_calling` 在 M3 上 `'NoneType' object has no attribute 'answer'`** — M3 返回结构异常 → fallback plain-text → 但 `_strip_fenced_json` 兜底工作,UI 仍显示干净中文

详见上面 "Vendor 兼容性矩阵" 段 "v0.2.2 新增 M3 实测" 段。

### 总工作量
- 代码:1 commit(2 文件改动 + 1 个新测试类)
- pytest:53 passed(50 旧 + 3 新)
- UI 实测:2/4 prompt 干净(其余因新发现 M3 Intent 400 拖慢,未跑完整 4 prompt)
- **总计 ~30 min**(根因直接由错误信息给出,LangChain docs 确认 extra_body 方案)

---

## 🚧 v0.3.0-alpha 多会话骨架(2026-06-19,1 commit)

### 目标

把 yantu 从"工具型"升级到"个人助理"的第一阶段:**多会话并存 + 重启不丢**。长期记忆、侧边栏 JSX、上下文压缩等放 PR-2/3。

### 改动清单(7 文件 / 1 commit)

| # | 文件 | 改动 | 关键点 |
|---|---|---|---|
| 1 | `src/yantu/data/models.py` | +3 表(`Session` / `MemoryFact` / `UserSetting`) | Session 表存侧边栏元数据;`MemoryFact` / `UserSetting` 表预留给 PR-2 |
| 2 | `src/yantu/data/db.py` | `init_db()` 末尾加 `PRAGMA journal_mode=WAL` + `PRAGMA busy_timeout=5000` + 触发 checkpointer.setup() | WAL 模式避免 extractor 后台写阻塞 LangGraph checkpoint |
| 3 | `src/yantu/graph/agent.py` | `MemorySaver` → `SqliteSaver(sqlite3.Connection)`;删 `@lru_cache(maxsize=1)`;`_open_saver()` 复用 `db._engine.raw_connection()` | 关键:langgraph-checkpoint-sqlite 3.x 的 `from_conn_string` 是 ctxmgr,改用 `SqliteSaver(conn)` 直接构造;复用同一连接避免双 conn 锁竞争 |
| 4 | `src/yantu/data/vector_repo.py` | +`LONG_TERM_MEMORY_COLLECTION` 常量 + `get_long_term_memory_collection()` helper | **复用现有 `_get_singleton_client`**(不开第二个 client,遵守 HB-04);与 `recruit_2026` 职责分离但共享 client |
| 5 | `src/yantu/session/manager.py`(新) | 9 个 CRUD 函数:create / list / get / rename / toggle_pin / archive / unarchive / hard_delete / touch | thread_id = UUID4 hex 前 8 位;`hard_delete_session` 跨 3 个 LangGraph checkpoint 表原生 SQL 删除 |
| 6 | `src/yantu/session/__init__.py`(新) | 包标记 + 公开 9 个函数 | — |
| 7 | `src/yantu/ui/app.py` | `on_chat_start` 改用 `create_session`;+5 个 action_callback(new_session / switch_session / rename_session / toggle_pin / delete_session)+ `GET /api/sessions` REST;`_reorder_routes()` 扩到 `/api/` 前缀 | hard_delete 走 action_callback 的 `payload.hard=True` 触发 |
| 8 | `tests/session/test_manager.py`(新) | 18 个 pytest,覆盖 thread_id 唯一性 / CRUD / archive / pin 排序 / touch / hard_delete 真删 checkpoint / list limit | tmp_path 隔离 db,monkeypatch 替换 `db._engine`(settings 是 frozen 不能直接 patch)|

### 端到端验证(2026-06-19 实测)

| 步骤 | 结果 |
|---|---|
| 进程 A:`create_session` + `agent.invoke` 发 2 条 user_query | thread=`3af0cd3b`,DB 写入 8 个 checkpoint 行 |
| 进程 B:重新启动,新 agent 实例,`get_state` 同 thread_id | messages count=4,user_query=`['我是北大考生', '复试分数线多少']` ✅ |
| `curl /api/sessions` | 返回真实 JSON,2 个会话可见 ✅ |
| `hard_delete_session` 后查 DB | Session 行 + checkpoints/checkpoint_writes/checkpoint_blobs 3 表全部清空 ✅ |

### 关键技术发现

| 发现 | 影响 |
|---|---|
| `SqliteSaver.from_conn_string()` 返 contextmanager | agent.py 必须用 `SqliteSaver(conn)` 直接构造 |
| `_engine.raw_connection()` 拿底层 sqlite3.Connection | 让 SqliteSaver 与 ORM 共享同一连接(避免 WAL 下双 conn 写锁) |
| Settings 是 frozen dataclass | 测试 fixture 不能 monkeypatch `settings.sqlite_path`,改替换 `db._engine` |
| `_reorder_routes()` 原只挪 `/settings`,新加 `/api/sessions` 被 catch-all 抢 | 改用前缀白名单 `("/settings", "/api/")` 一次解决 |

### pytest

- 53 → **71 passed**(45 旧 + 18 新 + 8 已有,无回归)
- 18 个新测试全部通过(含 `test_hard_delete_removes_checkpoint_rows` 验证跨 3 表真删)

### 风险 & 已知限制

- ⚠️ **PR-1 不含侧边栏 UI**:Session 元数据已持久化,但 JSX sidebar 留到 PR-2;目前 `/api/sessions` 已有数据可拉,前端未消费
- ⚠️ **M3 Intent classifier BadRequest 400 仍未修**(v0.2.2 TODO P1),新流程不受影响(router fallback 仍可用,只是慢)
- ⚠️ **LLM 长记忆 facts 未抽取**:PR-1 只是骨架,长期记忆抽取(retriever + extractor)在 PR-2

### v0.3.0 路线图(剩余)

- [ ] **v0.3.0-beta**:长期记忆(extractor + retriever)+ 侧边栏 JSX + 设置记忆 tab(~3 天)
- [ ] **v0.3.0-final**:上下文滑动窗口压缩(compressor)+ 4 pytest(~2 天)

完整方案见 `docs/superpowers/specs/2026-06-19-multi-session-memory-design.md` + `C:\Users\steven\.claude\plans\fancy-knitting-journal.md`

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

### 🆕 Bug 13: PyCharm Run Configuration 漏 HF_HUB_OFFLINE 等环境变量(2026-06-19 实测)
- **症状**: PyCharm 启动 chainlit 后,(a) Settings 按钮 UI 异常(⚙️ 图标缺失) (b) Tool call step 不显示 (`on_tool_start` event 没注册) (c) `.env` 没加载 → 后端日志显示 `key_present=False` 或 vendor 走 zhipu 默认
- **原因**: PyCharm Run Configuration 默认只设 `PYTHONUNBUFFERED=1`,缺 3 个关键 env vars:
  - `HF_HUB_OFFLINE=1` → bge 加载卡 60s+(`SentenceTransformer` 启动时 HEAD huggingface.co 验证 metadata)
  - `TRANSFORMERS_OFFLINE=1` → 同上,sentence_transformers 还要查这个
  - `SENTENCE_TRANSFORMERS_HOME=D:\WORKSTATION\Glimmer Guide\models` → 不指本地 cache 目录,sentence_transformers 会找错位置
- **解决**: PyCharm Run → Edit Configurations → 选 `app` → Environment variables 填 `PYTHONUNBUFFERED=1;HF_HUB_OFFLINE=1;TRANSFORMERS_OFFLINE=1;SENTENCE_TRANSFORMERS_HOME=D:\WORKSTATION\Glimmer Guide\models`,**Working directory 必须用项目根**(`D:\WORKSTATION\Glimmer Guide`,不是 `src\yantu\ui`),**`.env` 文件路径**必须显式填 `D:/WORKSTATION/Glimmer Guide/.env`
- **验证**: 启动后立即看后端第一行 `LLM resolved: vendor=... base_url=... key_present=True`(key_present=True 证明 .env 加载成功)
- **教训**: PyCharm Run Configuration **不会**自动继承项目级 env vars;terminal 里 `export` 的 env 在 PyCharm Run 里**不生效**(PyCharm 用独立 env);bug 表现隐蔽(不是崩溃,只是行为异常)

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
1. **HF_HUB_OFFLINE 必设**:启动 chainlit / studio 都必须设 3 个环境变量,否则 bge 加载卡 60s+(见 Bug 10);**PyCharm Run Configuration 漏设是 2026-06-19 实测高频踩坑**(见 Bug 13),务必在 Run → Edit Configurations → Environment variables 显式填
2. **ChromDB 写入**: vector_repo 当前是只读 in-memory 模式,新增 chunks 需要重启 Chainlit
3. **LangGraph 持久化**: ~~MemorySaver,重启 Chainlit 丢会话~~ → **v0.3.0-alpha 已修**(SqliteSaver + Session 表),重启会话完整保留
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

Run → Edit Configurations → 选 `app` 配置 → 改下面 3 个字段:

| 字段 | 值 |
|---|---|
| **Working directory** | `D:\WORKSTATION\Glimmer Guide`(项目根,不要用 `src\yantu\ui`!) |
| **Environment variables** | `PYTHONUNBUFFERED=1;HF_HUB_OFFLINE=1;TRANSFORMERS_OFFLINE=1;SENTENCE_TRANSFORMERS_HOME=D:\WORKSTATION\Glimmer Guide\models` |
| **.env file path** | `D:/WORKSTATION/Glimmer Guide/.env` |
| **Python interpreter** | Project default (Python 3.11) = `D:\ProgramData\Anaconda_envs\envs\Glimmer\python.exe` |
| **Script path** | `D:/WORKSTATION/Glimmer Guide/src/yantu/ui/app.py` |
| **Add content roots to PYTHONPATH** | ✅ 勾选 |

**3 个常见踩坑**(见 Bug 13):
1. **漏 HF_HUB_OFFLINE=1** → bge 加载卡 60s+ 不返回,Tool call step 不显示(`on_tool_start` event 注册失败)
2. **Working directory 用 `src\yantu\ui\`** → `.env` 找不到(vendor/API key 走 default)+ `.chainlit/config.toml` 找不到(⚙️ 设置按钮 UI 异常)+ Tool call step 不显示
3. **漏 .env 路径** → 同上

**判断是否配错**:启动后立即看后端日志第一行,应该看到 `LLM resolved: vendor=minimax (MiniMax) model=MiniMax-M3 base_url=https://api.minimaxi.com/v1 key_present=True`。如果 `key_present=False` 或 vendor 是 `zhipu`(默认),说明 .env 没加载。

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

## 🎨 Day 10 UI 优化(2026-06-21,1 工作日,156/158 pytest)

**核心成果**:从"功能完成"升级到"专业 AI 客户端的交互体验"。侧边栏不再有空壳 session 污染,新建/重命名/置顶/删除都有实时反馈,删除有自定义 modal + 三选项(归档/永久/取消),首屏空态 + 键盘导航对齐豆包/DeepSeek 模式。

### 6 个改造项 — 完整清单

| # | 改造项 | 状态 | 关键文件 | 收益 |
|---|---|---|---|---|
| 1 | **首条消息才建 session** | ✅ | `src/yantu/ui/app.py:on_chat_start + on_message` | 不再产生空壳 session(进页面不发消息 DB 不增加) |
| 2 | **WS 推送 sessions_changed** | ✅ | `app.py:8 处 send_window_message` + `public/custom-header.js` WS→DOM 桥 + `SessionSidebar.jsx` 30s 兜底轮询 | 替代 5s 轮询的延迟感,新建/重命名/置顶/删除立即反映 |
| 3 | **自定义删除 modal** | ✅ | `SessionSidebar.jsx:ConfirmDeleteModal` | 替代原生 `confirm()`,3 按钮(归档/永久删除/取消)对齐豆包模式 |
| 4 | **首屏空态 + +新对话智能隐藏** | ✅ | `SessionSidebar.jsx:L455-457` | 📭 emoji + 标题 + 提示语,空态时 +新对话按钮自动隐藏 |
| 5 | **键盘导航** | ✅ | `SessionSidebar.jsx:focusIdx state + flatList useMemo + useEffect` | ↑/↓ 移动蓝色 outline,Enter 切换,Cmd+1..9 跳第 N 个,不抢输入框焦点 |
| 6 | **端到端 + 浏览器实测** | ✅ | Chrome DevTools + `test_session_sidebar_visual.py` | 156/158 pytest + 浏览器实测 8/9 项通过 |

### 关键决策(中途变更)

1. **从 5s 轮询 → 30s 兜底 + WS 推送**:原 5s 轮询每次都会闪烁,改事件驱动后 UI 反应 < 100ms;30s 兜底保 WS 断(Chainlit 重启)时仍能同步
2. **WS→DOM 桥放 `custom-header.js`**:react-runner 不暴露 socket/listenFor,只能在浏览器原生 `window.addEventListener('message', ...)` 监听,然后 `dispatchEvent('sessions-updated')` 转发给 React 组件
3. **删除 modal 放主 return 根 div 内**(不是 portal):UI 简单优先,margin/overlay 都不影响 React 渲染
4. **键盘导航只动 focusIdx**(不抢 `tabIndex`):焦点状态用 inline style `outline: 2px solid #0969da`,不影响屏幕阅读器

### 浏览器实测验证清单(8/9 通过)

| # | 验证项 | 状态 | 证据 |
|---|---|---|---|
| 1 | 进页面不发消息,DB Session 表无新增 | ✅ | 3 次 on_chat_start 后 DB 仍 17(无 create_session 调用) |
| 2 | 首条消息后 DB 多一行,thread_id 是新 hex8 | ✅ | 发"你好"后 DB 17→18,thread_id=8508ae27 |
| 3 | WS 推送链路 | ✅ | dispatch sessions-updated → fetch /api/sessions 立即触发(侧边栏 17→18 实时更新) |
| 4 | **自定义 confirm 模态框(非浏览器原生)** | ✅ | 截图实测:360px 卡片 + "删除会话" 标题 + 3 按钮 + 说明文案 |
| 5 | 三按钮分别走 archive / hard_delete / cancel | ✅ | onArchive/onHardDelete/onCancel 三个 handler 全部 hit |
| 6 | **↑/↓ 在列表移动高亮** | ✅ | 按 ↓ 后 sidebar 第 13 个 div 出现 `outline: rgb(9, 105, 218) solid 2px`;再按 → 位置 16 |
| 7 | Cmd+1 切第一条 | ⚠️ | React handler 注册到位(`/^[1-9]$/.test(e.key)` 静态就位),但 OS Ctrl+1 路由给浏览器切 tab |
| 8 | 30s 兜底轮询 | ✅ | JSX L57 `setInterval(poll, 30000)` + 验证脚本 `/api/sessions` 拉取链路正常 |
| 9 | 首屏空态显示 📭 | ✅ 静态 | grep 验证 L455-457 emoji + 标题 + 提示语 |

### 测试结果(156/158 pytest)

- 原 156 测试(无回归)
- **新通过**:`test_session_sidebar_visual.py:test_has_polling` 从 5000 改成 30000;3 个 Day 8 过严断言(ITEM_HEIGHT/WIDTH/WIDTH_COLLAPSED)改成匹配 Day 9 inline style
- 2 个基线失败(`test_memory_panel_identical` / `test_profile_editor_identical`):属于本工作范围之外的 JSX 副本同步问题,Day 9 inline style 重构时就遗留

### 改动文件清单

- **改**:`src/yantu/ui/app.py` — 8 处 send_window_message + on_chat_start 不 create_session + on_message 加 deleted-active 兜底 + 首条消息 create + WS push
- **改**:`public/custom-header.js` — 末尾追加 WS→DOM 桥接 IIFE(`window.message → sessions-updated` 转发)
- **改**:`src/yantu/ui/.chainlit/public/elements/SessionSidebar.jsx` + `public/elements/SessionSidebar.jsx`(副本同步)— useState 化 sessions + ConfirmDeleteModal 子组件 + 键盘导航 + 空态 + 30s 兜底
- **改**:`tests/test_session_sidebar_visual.py` — 4 个 Day 8 过严断言更新到匹配 Day 9 inline style(5000→30000、ITEM_HEIGHT/WIDTH/WIDTH_COLLAPSED 改成 inline 数值匹配)

### 后续(Day 11+)

- 存量 17 个空壳 session 人工清理(计划方案定稿时约定,本工作不处理)
- JSX 副本同步自动化(目前手动 cp;`test_session_sidebar_visual.py` 字节级同步断言)
- `cl.send_window_message` 在 Chainlit 2.12+ 是否仍可用(目前 2.11.1 OK)
- 移动端键盘导航适配(目前 `INPUT/TEXTAREA` 守卫主要面向桌面)

---

## 🐛 Day 10 修复项 — 浏览器实测暴露的 4 个新 bug(2026-06-22,159/161 pytest)

> **来源**:用户在 PyCharm 启动后实测发现 Day 10 6 改造项落地后**仍有 4 个 UX 问题**。本章节是修复项,**不是新功能**。Day 10 6 改造项保持不变。

### 4 bug 根因 + 修复

| Bug | 根因 | 修复 | pytest 断言 |
|---|---|---|---|
| **1. 侧边栏显示 18 个但当前只有 1 个对话** | `manager.py:list_sessions` 不过滤 `message_count=0` 的历史空壳 | `list_sessions` 加 `min_message_count` 参数(默认 0 向后兼容);`app.py:/api/sessions` 默认传 1;前端 `useMemo` 软过滤兜底 | `test_list_filters_empty_shells_by_default_min_count` + `test_list_min_message_count_zero_disables_filter` + `test_list_min_message_count_higher_threshold` + `test_bug1_filters_empty_sessions` |
| **2. 侧边栏折叠后页面不响应** | 键盘导航 useEffect deps `[flatList, focusIdx]` 每次 buckets 变就 unmount/remount `document.keydown`,与 layout thrashing 竞争 | `flatListRef` + `focusIdxRef` 桥接,handler 空 deps 只挂一次,内部走 ref 拿最新值 | `test_bug2_keyboard_handler_uses_ref` |
| **3. 搜索框无法使用** | Ctrl K handler 的 `e.preventDefault()` 在中文 IME composition 中也派发,抢走焦点;`visibility: hidden` 折叠态不响应 | Ctrl K handler 加 `isComposing` / `keyCode === 229` 守卫;input 加 `onCompositionStart/End` 显式同步搜索值 | `test_bug3_ime_aware_ctrl_k` |
| **4. 点击会话无法切换** | `const activeId = props.activeId` 是普通变量不是 state;react-runner 不重 mount,prop 变了 const 不会重读,导致 active 高亮不更新 | `activeId` 改 `useState` + 订阅 `sessions-updated` 事件识别 `detail.action` 本地更新 | `test_bug4_activeid_is_state` |

### 关键代码改动

| 文件 | 改动 |
|---|---|
| `src/yantu/session/manager.py:38-70` | `list_sessions` 加 `min_message_count: int = 0` 参数 |
| `src/yantu/ui/app.py:651-657` | `/api/sessions` 默认传 `min_message_count=1` |
| `src/yantu/ui/.chainlit/public/elements/SessionSidebar.jsx` | 4 处:① L19-32 activeId 改 useState ② L35-39 前端 nonEmptySessions 软过滤 ③ L67-71 IME 守卫 ④ L111-160 键盘 useRef 桥接 + sessions-updated action 分支 |
| `public/elements/SessionSidebar.jsx` | 同步副本(字节级一致) |
| `tests/test_session_sidebar_visual.py` | 加 4 个 `test_bug*` 断言 |
| `tests/session/test_manager.py:TestList` | 加 3 个 `test_list_min_message_count_*` 断言 |

### 浏览器实测证据

| 验证项 | 修复前 | 修复后 |
|---|---|---|
| `/api/sessions` 返回总数 | 18(包含空壳) | 5(全部 `message_count >= 2`) |
| 底部"X 个会话"显示 | 18 | 5 |
| 空壳 session 出现 | 是 | 否 |
| 键盘 handler unmount/remount 频率 | 每次 buckets 变(高) | 只在 mount 时挂一次(低) |
| IME 中文输入抢焦点 | 是 | 否(已守卫) |
| 点击会话后 active 高亮 | 不更新 | 立即更新(state 化 + WS 同步) |

### 测试结果

- **159/161 pytest 通过**(原 156/158 + 7 个新断言全过 - 2 个新增但过严断言修过 + 2 个历史行尾失败与本轮无关)
- **SessionSidebar JSX 副本字节级一致**(`test_session_sidebar_identical` PASSED)
- 4 个新 `test_bug*` 断言全过
- 3 个新 `test_list_min_message_count_*` 断言全过

### 风险与回滚

| 修复 | 风险 | 回滚 |
|---|---|---|
| `min_message_count=1` 误过滤用户期待看到的空 session | 默认 0 不变,只在 `/api/sessions` 传 1 | `app.py:654` 删 `min_message_count=1` 参数 |
| ref 桥接后 React 18b StrictMode 双调用 | handler 幂等,生产无影响 | 删 `useRef + useEffect` 改回 `[flatList, focusIdx]` deps |
| `props.activeId` useEffect deps 引用稳定 | 主要靠 onEvt detail 分支兜底 | 删 useEffect 同步,只靠 onEvt |
| IME 守卫误伤正常输入 | `isComposing || keyCode === 229` 是 web 标准 | 删 3 行 IME 检查 |

---

## 🎯 Day 11 — 折叠 UI 重构(transform 滑出 + FAB 浮动按钮,豆包风格)

> **来源**:用户反馈"折叠会连着整个对话一起被收,不是单独的收起侧边栏"。根因是 Day 10 用 `width: 60px` 收缩 sidebar + body `padding-left: 60px` 联动 → 主对话跟着"被挤"。
> **目标**:对齐豆包/DeepSeek 折叠模式 — sidebar 用 `transform: translateX(-220px)` 滑出 title 列(留 60px avatar 列在屏左),主对话 `margin-left` 跟着 280 ↔ 60,不再 body padding 联动。

### 改动清单(2026-06-22,1 工作日,168/170 pytest)

| 改动 | 文件 | 行数 | 说明 |
|---|---|---|---|
| sidebar 折叠 `width:60px` → `transform: translateX(-220px)` | `public/custom-header.js` | L36-66 | 留 60px avatar 列在屏左,豆包风格 |
| 主对话区 `body padding-left` → `.chainlit-container margin-left` | `public/custom-header.js` | L69-83 | 折叠时归 60px,不再"整个对话一起被收" |
| 新增 `#sidebar-toggle-fab` 浮动按钮 | `public/custom-header.js` | L94-128 | fixed 在屏左,展开 292px / 折叠 72px,200ms 过渡 |
| Ctrl+B / Cmd+B 全局快捷键 | `public/custom-header.js` | L150-167 | 对齐 VS Code,输入框内不抢 |
| sidebar 内部 ◀/▶ 折叠按钮删除 | `src/yantu/ui/.chainlit/public/elements/SessionSidebar.jsx` | L467-472 | 改由 FAB + Ctrl+B 触发 |
| sidebar 底部 ⏵/⏸ 折叠按钮删除 | `src/yantu/ui/.chainlit/public/elements/SessionSidebar.jsx` | L561-565 | 同上 |
| sidebar `width: collapsed ? 60 : 280` 写死 280 | `src/yantu/ui/.chainlit/public/elements/SessionSidebar.jsx` | L300-311 | CSS transform 取代 width 切换 |
| 监听 `sidebar:toggle` 事件 | `src/yantu/ui/.chainlit/public/elements/SessionSidebar.jsx` | L200-210 | useRef 桥接,handler 空 deps |

### 验证清单

- [x] pytest 168/170 通过(2 个失败是 MemoryPanel/ProfileEditor 行尾 CRLF 历史问题,与 Day 11 无关)
- [x] Day 11 新增 5 个断言全部通过(`test_day11_*` / `TestCustomHeaderDay11::*`)
- [x] sidebar DOM width 永远 280px,折叠时 transform 滑出 title 列
- [x] 主对话区 `margin-left` 280 ↔ 60 同步
- [x] FAB 浮动按钮 fixed 在屏左,展开 292px / 折叠 72px,200ms 过渡
- [x] Ctrl+B / Cmd+B 全局快捷键(输入框内不抢)
- [x] SessionSidebar 不再含内部 ◀/▶ / ⏵/⏸ 折叠按钮

### 关键文件清单

- **改:** `public/custom-header.js`(CSS transform 滑出 + FAB 注入 + Ctrl+B)
- **改:** `src/yantu/ui/.chainlit/public/elements/SessionSidebar.jsx`(sidebarStyle 写死 280 + 监听 sidebar:toggle + 删内部按钮)
- **改:** `public/elements/SessionSidebar.jsx`(同步副本)
- **改:** `tests/test_session_sidebar_visual.py`(新增 8 个 Day 11 断言)
- **不改:** `src/yantu/ui/app.py`(WS 推送接口不动,FAB 自己 dispatch event)

### 设计取舍

| 选项 | 选择 | 原因 |
|---|---|---|
| transform: translateX(-220px) vs translateX(-280px) | **-220px** | 完全滑出 = sidebar 不可见,但 60px avatar 列仍可点切换会话(豆包风格) |
| main margin-left vs body padding-left | **margin-left** | body padding 会让整页 content 跟着缩,main margin 只影响主对话区 |
| FAB 在 sidebar 内 vs FAB fixed | **fixed 在屏左** | sidebar 滑出后按钮仍可见可点,符合豆包期望 |
| FAB 在屏左 12px vs 72px | **展开 292 / 折叠 72** | 展开时贴着 sidebar 右边,折叠后贴着 60px avatar 列右边,视觉一致 |

### 风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| FAB 注入时机晚于 sidebar 渲染,首次展开 FAB 不在位 | `injectFab` 在 `init()` 里同步执行,DOM 已 ready 时立即生效 | 把 FAB 移到 SessionSidebar JSX 内渲染 |
| `margin-left: 280px` 被 Chainlit 自有 CSS 覆盖 | 用 `!important` + 多个 selector(`.chainlit-container, #main, main`) | 改回 `body padding-left: 280px` 旧方案 |
| Ctrl+B 与浏览器原生快捷键冲突 | 输入框内主动 `return`(不抢焦点),且 `!e.shiftKey && !e.altKey` 防误触 | 删 Ctrl+B 监听,只保留 FAB |
| FAB DOM 与 sidebar transform 不同步导致按钮位置抖动 | `body[data-sidebar-collapsed]` 与 `[data-sidebar-collapsed]` 同步切换,共享 200ms transition | 删 FAB,改回 sidebar 内按钮 |

### 🐛 Day 11 hotfix — CSS selector 误匹配 body(FAB 被拖屏外)

> **来源**:用户重启服务后实测发现 — 折叠 FAB 无法点击(`Failed to interact with the element`),且 Chainlit 默认 UI 元素位置错乱(疑似与自定义 sidebar 重叠)

**根因**:
- SessionSidebar React state 切换时给 `document.body` 也设了 `data-sidebar-collapsed="1"`(沿用 Day 10 同步逻辑)
- custom-header.js CSS selector `[data-sidebar-collapsed="1"]` 无差别匹配任何带这个 attribute 的元素,**包括 body**
- body 被 `transform: translateX(-220px)` 整体偏移 → FAB 作为 body 子元素跟着跑到屏外(`rect.x = -148px`)
- 真实 click 永远打不到 FAB(报错 `The element did not become interactive`)
- Chainlit 默认 UI 元素(虽然被 hidden)位置也被 body transform 错位 → 视觉上"重叠"

**修复**:
- `[data-sidebar-collapsed="1"]` → `[data-sidebar="1"][data-sidebar-collapsed="1"]`(限定 sidebar 自己)
- 加 `test_day11_transform_selector_scoped_to_sidebar` 防回归(解析 CSS rule,验证含 transform 的 selector 必须同时限定 `[data-sidebar="1"]`)

**验证**:
- body `transform: -220px` → `none`
- FAB `rect.x = -148` → `292`(展开)/ `72`(折叠)
- 真实 click FAB 成功触发折叠/展开
- pytest 6/6 Day 11 断言全过(含新防回归断言)

### 🐛 Day 11 hotfix 2 — body class 替代 attribute,根因彻底消除

> **来源**:第一次 hotfix (c83a5ee) 只加了 CSS selector 前缀,但根因未消除 — SessionSidebar 仍在给 body 设 attribute,未来任何新 CSS rule 用这个 attribute 都会再次误匹配 body

**修复方案**:
- SessionSidebar: `setAttribute('data-sidebar-collapsed', '1')` → `classList.toggle('sidebar-collapsed', collapsed)`
- custom-header.js CSS 5 处:`body[data-sidebar-collapsed="1"]` → `body.sidebar-collapsed`
- custom-header.js JS:MutationObserver `attributeFilter: ['data-sidebar-collapsed']` → `['class']`
- `syncBodyPadding()` 改为检测 sidebar attr + body class 双向兜底

**为什么 class 比 attribute 安全**:
- CSS `[attr]` 选择器无差别匹配任何带 attribute 的元素(body 也被匹配 → 整页偏移)
- CSS `.class` 选择器只匹配**显式**有那个 class 的元素
- `classList.toggle()` 是 boolean 操作,不会误设错元素

**测试**:
- `test_hotfix2_no_body_setattribute_collapsed`: SessionSidebar 不再 setAttribute data-sidebar-collapsed
- `test_day11_hotfix2_uses_class_not_body_attribute`: CSS 改用 body.sidebar-collapsed class selector
- pytest 36/38 通过(2 个历史 CRLF 行尾失败与本轮无关)

### 🐛 Day 11 hotfix 3 — FAB z-index 必须 > #header z-index(否则 header 拦截 click)

> **来源**:用户重启服务实测 + Playwright 验证 — body 不再被 transform,FAB rect.x 也正确,但**真实 mouse click 仍失败**(Playwright 报 `<div id="header"> intercepts pointer events`)

**根因**:
- Chainlit 的 `#header` `z-index: 100`,width **1036px**(覆盖整个顶部)
- FAB 之前 `z-index: 60`(< header)
- FAB 位置 `(292, 12) → (324, 44)` 完全在 header 区域内
- `document.elementsFromPoint(308, 28)` 顶层元素是 `#header`,真实 click 永远命中 header
- FAB 收不到 click 事件 → React state 不变 → 体感"无法折叠"

**修复**:
- FAB `z-index: 60` → `150`(> header 100,但 < Chainlit modal 200)
- 加 `test_day11_hotfix3_fab_zindex_above_header` 防回归

**验证(Playwright 真实 mouse click)**:
- 折叠前:body class `""`,sidebar transform `(0,0)`,FAB `left: 292`,icon `☰`
- **真实 click FAB**:body class → `"sidebar-collapsed"`,sidebar transform → `-220`,FAB `left: 72`,icon `✕`
- 再次 click:全部归位
- pytest 8/8 Day 11 + hotfix 断言全过

**关键教训**:
> z-index 不只是"显示层级",也决定 click 事件路由。FAB 视觉上在 sidebar 右边,但 DOM 层面被 header 覆盖,真实 click 永远走 header → React 不响应。

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