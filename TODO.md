# 待办清单 — v0.3.0 路线图

> **生成日期**: 2026-06-19
> **更新日期**: 2026-06-21(Day 10 UI 优化完成)
> **项目**: 研途萤火(yantu)
> **来源**: 5 个改进方向的深度分析(详见 `PROGRESS.md` 当前状态 + 后续对话)
> **当前版本**: ✅ **v0.3.0-beta + Day 10 UI 优化 + Day 10 修复项** (PR-2 4 子项 + UI 6 改造项 + 4 bug 修复,159/161 pytest,Chrome DevTools 实测通过)
> **目标版本**: v0.3.0-rc(Day 11:存量空壳 session 清理 + 移动端适配 + JSX 副本同步自动化)

---

## 📊 总览

| 优先级 | 数量 | 总工作量 | 关键收益 |
|---|---|---|---|
| 🔥 P0 | 2 项 | 2-3 天 | 数据正确性 + 核心定位 |
| 🎯 P1 | 2 项 | 2-4 天 | 内容深度 + 用户信任 |
| 📦 P2 | 2 项 | 1.5-2 天 | 体验完善 |
| **合计** | **6 项** | **5.5-9 天** | — |

---

## 🔥 P0 — 必须做(本周)

### TODO-1. 修复字段名不一致 bug(JSX vs Model)

**类型**: 🐛 Bug fix
**工作量**: ~1 小时
**风险**: 低(纯字段重命名)
**优先级理由**: 用户在设置页改了 "数学避开" / "英语分数",**实际上数据库存不进去** — 隐性数据丢失 bug

**问题定位**:
| JSX 字段 | Model 字段 | 一致性 |
|---|---|---|
| `initScores.english` | `ScoreRecord.english_2` | ❌ 不一致 |
| `initPrefs.business_keywords` | `UserPreferences.specialty_keywords` | ❌ 不一致 |
| `initPrefs.exclude_985` | `UserPreferences.avoid_985` | ❌ 不一致 |

**改动清单**:
- [ ] `public/elements/ProfileEditor.jsx` 字段名全部对齐 `models.py`
- [ ] 写 1 个 pytest 模拟 `save_profile` action payload,验证 `update_profile()` 后数据库值正确
- [ ] 给 `update_profile()` 加 Pydantic 验证失败的 warning log(防止字段再次漂移)

**验收标准**:
- [ ] pytest 全过
- [ ] `/settings` 页面改"英语分数 70",刷新 chat 后 `to_prompt()` 显示 "英语二 70"
- [ ] `models.py` 字段名 = JSX 字段名 = SQLite JSON 字段名

---

### TODO-2. 长短期记忆架构

**类型**: 🏗️ 架构升级(P0 级 = 产品定位)
**工作量**: 2-3 天
**风险**: 中(影响 LangGraph 核心)
**优先级理由**: "个人助理" 区别于 "工具" 的核心特征。重启 Chainlit 后用户问"昨天我问的清华分数线呢",**答不上来就不是助理**

#### TODO-2a. 短期记忆:MemorySaver → AsyncSqliteSaver

**工作量**: ~2 小时

- [ ] `src/yantu/data/db.py` 加 `get_async_engine()` / `async_session()`
- [ ] `src/yantu/graph/agent.py` 改 `MemorySaver()` → `AsyncSqliteSaver.from_conn_string(str(settings.data_dir / "checkpoints.db"))`
- [ ] 处理 lifespan context manager(`async with AsyncSqliteSaver.from_conn_string(...) as checkpointer:`)
- [ ] 验证 `thread_id` 在重启后仍能拉回历史

#### TODO-2b. 长期记忆:memory_extractor + memory 表

**工作量**: 1-2 天

**数据模型**(`src/yantu/data/models.py` 加):
```python
class MemoryFact(Base):
    """长期记忆事实(LLM 抽取的结构化记忆)"""
    __tablename__ = "memory_facts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(50), index=True, default="default")
    fact_type: Mapped[str] = mapped_column(String(50), index=True)
    # fact_type 取值:school_mentioned / score_reported / preference_changed /
    #                 exam_subject / timeline_event / open_question
    fact_value: Mapped[dict] = mapped_column(JSON)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    source_thread: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_accessed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

**抽取逻辑**(`src/yantu/graph/memory_extractor.py` 新建):
- [ ] 每轮对话结束后,后台 task 跑 LLM(summary 类 prompt,提取 facts)
- [ ] facts 写 `memory_facts` 表
- [ ] 去重:同 fact_type + 相似 fact_value 不重复存
- [ ] 抽取 prompt 模板:`"从以下对话中提取用户提到的关键事实(学校/分数/偏好/科目/时间),返回 JSON list"`

**注入逻辑**(`src/yantu/utils/llm.py` 改 `get_user_profile_prompt`):
- [ ] 读最近 30 条 `memory_facts`
- [ ] 加 `recent_topics` 字段到 `to_prompt()` 输出
- [ ] LLM 在 system prompt 看到 "你记得用户之前问了清华"

**UI 展示**(`public/elements/MemoryPanel.jsx` 新建 + `/settings` 加 tab):
- [ ] 列出所有 facts(按 fact_type 分组)
- [ ] 用户可手动删除错误记忆
- [ ] "❌ 这不是我说的" 按钮 → 删除 fact + 记录 negative feedback

**验收标准**:
- [ ] pytest 全过(含 memory 抽取单测)
- [ ] Chainlit 重启后,问"我刚才问了哪个学校"能答出来
- [ ] `/settings` 显示记忆列表,可增删
- [ ] memory_extractor 在 background task,不阻塞 UI 响应

---

## 🎯 P1 — 应该做(本月)

### TODO-3. RAG 改造:按 heading chunker + export/import

**类型**: 🔧 重构
**工作量**: 1-2 天
**风险**: 中(需重新索引所有数据)

#### TODO-3a. 按 heading 切 chunk(替代字符级切)

**当前**:`chunker.py` 中文字符级 512+64,**标题识别失效**(md_parser 解析的 title_path 不传给 chunker)

- [ ] `src/yantu/ingest/chunker.py` 加 `chunk_by_heading()` 入口
- [ ] MD 文件按 `^#{1,6} ` 切分,每个 heading 块内再做段落切
- [ ] PDF 文件利用 `pdf_parser.parse_pdf()` 返回的 `title_path`(已有但没传到 chunker)
- [ ] Chunk metadata 加 `school_name / year / doc_type / chapter_path`(从文件路径 + 内容推断)
- [ ] 保留旧 `chunk_text()` 作 fallback,加 `chunk_strategy: str = "heading"` 参数切换

- [ ] 写 3 个 pytest:MD 边界 case / PDF 多级 heading / fallback 路径

#### TODO-3b. RAG 数据 export / import

**用户痛点**: "保存到本地 万一删除了怎么办"

- [ ] 新建 `src/yantu/cli/rag.py` 命令:`python -m yantu.cli.rag export /path/to/snapshot.tar.gz`
  - 打包 `data/chroma/` + `data/yantu.db` + `seeds/` 元数据
- [ ] `python -m yantu.cli.rag import /path/to/snapshot.tar.gz` 解包恢复
- [ ] 加 `where={"school_name": X}` / `where={"year": 2026}` 过滤到 `search_local` 工具签名
- [ ] 写 2 个 pytest:export 完整性 / import 后 count() 一致

**验收标准**:
- [ ] pytest 全过
- [ ] export → delete chroma → import → search_local 返回相同结果
- [ ] chunk metadata 含 school_name,可在 where 过滤

---

### TODO-4. 学科代码 + 统考科目代码表

**类型**: 📊 数据建设
**工作量**: 1-2 天(其中数据采集占大半)
**风险**: 低(纯静态数据)

#### TODO-4a. 14 学科门类 → 一级学科 → 二级学科 三级树

**新增**:`src/yantu/data/disciplines.json`(参考 `school_classification.json` 写法)
```json
{
  "_meta": "数据源:研招网 /zyk/ SSR + 教育部学位中心学科目录",
  "majors": [
    {"code": "01", "name": "哲学", "first_level": [
      {"code": "0101", "name": "哲学", "second_level": [
        {"code": "010101", "name": "马克思主义哲学", "type": "学硕"},
        ...
      ]}
    ]},
    ...
  ]
}
```

- [ ] 抓 13 大学科门类 + 130+ 一级学科 + 600+ 二级学科(数据源公开)
- [ ] `src/yantu/data/models.py` 加 Pydantic `DisciplineTree` 模型
- [ ] `get_disciplines()` 工具升级:返回 **门类 + 一级学科** 两层(原版只有门类)
- [ ] 新增 `get_first_level_disciplines(category_code: str)` 工具
- [ ] router intent 加 `discipline_lookup` 桶(用户问"考什么"时走这个)
- [ ] 写 5 个 pytest:数据加载 / 模型验证 / 工具返回格式

#### TODO-4b. 统考科目代码表

**新增**:`src/yantu/data/exam_subjects.json`
```json
{
  "_meta": "数据源:研招网 /zyk/ 考试科目章节",
  "公共课": [
    {"code": "101", "name": "思想政治理论", "type": "必考"},
    {"code": "201", "name": "英语一", "type": "选考"},
    {"code": "204", "name": "英语二", "type": "选考"},
    {"code": "301", "name": "数学一", "type": "选考"},
    {"code": "302", "name": "数学二", "type": "选考"},
    {"code": "303", "name": "数学三", "type": "选考"}
  ],
  "统考专业课": [
    {"code": "199", "name": "管理类综合能力", "category": "管理类联考"},
    {"code": "311", "name": "教育学专业基础", "category": "教育学联考"},
    {"code": "396", "name": "经济类综合能力", "category": "经济类联考"},
    {"code": "342", "name": "农业知识综合四", "category": "农学联考"}
  ]
}
```

- [ ] 抓 ~50 个统考科目代码(数据源公开)
- [ ] `UserProfile.personal.target_exam_subjects: list[str]` 加字段(用户选的科目代码)
- [ ] `to_prompt()` 注入:"考生选考: 101 思政 / 204 英二 / 342 农综四"
- [ ] LLM 看到用户问 "我考 396", 知道是经济类联考
- [ ] 写 3 个 pytest:数据加载 / 字段注入 / 关键词匹配

**验收标准**:
- [ ] pytest 全过
- [ ] 用户在 /settings 选 "342", chat 内问 "342 考什么" 能答
- [ ] `get_disciplines()` 返回 14 门类 + ~130 一级学科

---

## 📦 P2 — 可以做(下月)

### TODO-5. Program 维度工具(扩展 search_local)

**类型**: 🛠️ 工具扩展
**工作量**: ~半天
**风险**: 低

- [ ] `search_local` 工具签名加 `school_name: Optional[str] = None` / `year: Optional[int] = None` 参数
- [ ] `vector_repo.search()` 加 `where={"school_name": X}` 透传
- [ ] chunk metadata 必须含 school_name(依赖 TODO-3a)
- [ ] 写 2 个 pytest:where 过滤生效 / 无 school_name 时 backward compatible

**验收标准**:
- [ ] 用户问 "CCNU 复试分数线" 走 `search_local(school_name="华中师范大学", query="复试分数线")`

---

### TODO-6. 表单合并(JSX 补全 OR 删除 settings.html)

**类型**: 🎨 UI 重构
**工作量**: ~1 天
**风险**: 中(涉及 Chainlit 渲染)

**决策点**: 二选一

**选项 A(推荐)**:JSX 补全 + 删除 settings.html
- [ ] `ProfileEditor.jsx` 补齐:考试年份 / 学习方式 / 学位类型 / 目标学科代码 / 目标院校列表 / 地区偏好 / 时间轴 / 排除 985 / 统考科目
- [ ] 删除 `src/yantu/ui/templates/settings.html`(660 行)
- [ ] 删 `app.py` 的 `/settings` / `/settings/save` 路由
- [ ] 只在 chat 内通过 `cl.CustomElement` 编辑

**选项 B**:HTML 拆分 + 共用 schema
- [ ] `settings.html` 拆 3 个 partial + 共享 schema JSON
- [ ] JSX 改为只读视图(预览用)
- [ ] 编辑只在 /settings 页面做

**验收标准**:
- [ ] 所有 UserProfile 字段都能在 UI 上编辑
- [ ] JSX vs HTML vs Model 字段名 100% 一致(回到 TODO-1)
- [ ] pytest 全过

---

## 🗓️ 建议执行顺序

```
Week 1
├── Day 1 (上午)    TODO-1 字段名 bug fix(~1h)
├── Day 1 (下午)    TODO-2a SqliteSaver(~2h)
├── Day 2-4         TODO-2b 长期记忆(架构 + 抽取 + UI)
Week 2
├── Day 1-2         TODO-3a heading chunker
├── Day 2 (下午)    TODO-3b export/import
├── Day 3-4         TODO-4a 学科代码表(数据采集 + 工具)
├── Day 5           TODO-4b 统考科目代码
Week 3
├── Day 1 (上午)    TODO-5 search_local 扩展
├── Day 1 (下午)    TODO-6 表单合并
├── Day 2           全量 pytest + 端到端实测 + PROGRESS.md 更新
```

---

## 📌 跨任务依赖

```
TODO-1 ──┐
         ├── (无依赖,可立即开始)
         │
TODO-2a ─┤
         ├── (无依赖,可立即开始)
         │
TODO-2b ─┤
         │
TODO-3a ─┤──→ TODO-5(TODO-5 依赖 TODO-3a 的 chunk metadata)
         │
TODO-3b ─┤
         │
TODO-4a ─┤
         │
TODO-4b ─┤
         │
TODO-6  ─┘
```

---

## ⚠️ 不在本清单范围(明确推迟)

- ❌ **Tool 5 search_local 单独 bench** — TODO-3a 完成后自动覆盖
- ❌ **scraper search.do ssdm 默认集成** — 当前已支持 region 参数
- ❌ **211/研究生院 名单补全** — TODO-4 同期顺手补到 `school_classification.json`
- ❌ **LangSmith tracing 接入** — 调试工具,等长记忆做完再加
- ❌ **M3 Intent classifier 400 修复** — 不阻塞 P0/P1,等 TODO-2 做完再回头看
- ❌ **Tool 2 vendor 兼容** — 同上

---

## ✅ Day 10 完成项(2026-06-21)— UI 优化 6 项

> 本章节记录 2026-06-21 单日完成的 UI 优化工作。所有项已通过 Chrome DevTools 浏览器实测 + pytest 验证。

### Day 10-1. 首条消息才建 Session(✅ 完成)

**问题**:旧版 `@cl.on_chat_start` 每次进页面都无条件 `create_session()`,产生 17 个空壳 session 污染侧边栏。

**改动**:
- [x] `src/yantu/ui/app.py:on_chat_start` — 删除 `create_session()`,`thread_id = None`,加 `send_window_message("sessions_ready")`
- [x] `src/yantu/ui/app.py:on_message` 头部 — 加 deleted-active 兜底 + 首条消息时 `create_session()` + WS 推送 `sessions_changed:created`

**实测**:Chainlit 3 次 `on_chat_start` 后 DB 仍 17 个 session(无空壳);发"你好"后 DB → 18(`thread_id=8508ae27`)

---

### Day 10-2. WS 推送 session 列表变更(✅ 完成)

**问题**:旧版 `SessionSidebar.jsx` 每 5s 轮询 `/api/sessions`,新建/重命名/删除 UI 要等 5s 才更新。

**改动**:
- [x] `app.py` 8 处 `send_window_message`(ready + 4 callback + 3 on_message)
- [x] `public/custom-header.js` 末尾追加 WS→DOM 桥(`window.message → sessions-updated` 转发)
- [x] `SessionSidebar.jsx` useState 化 sessions + 30s 兜底轮询 + 事件驱动 onEvt

**实测**:dispatch `sessions-updated` 立即触发 `/api/sessions` fetch;侧边栏从 17 → 18 实时更新

---

### Day 10-3. 自定义删除确认 Modal(✅ 完成)

**问题**:旧版 `handleDelete` 用浏览器原生 `confirm()`,用户体验差(无 3 选项区分归档/硬删)

**改动**:
- [x] `SessionSidebar.jsx:ConfirmDeleteModal` 子组件 — 360px 居中卡片,3 按钮(取消/📦 归档/永久删除)
- [x] 替换 `handleDelete` 不再调原生 `confirm()`,改 `setConfirmDelete({session: s})`

**实测**:点击 ⋮ → 删除,看到"删除会话"标题 + 双引号包裹目标 + "归档/永久删除" 说明文案 + 3 按钮

---

### Day 10-4. 首屏空态 + +新对话智能隐藏(✅ 完成)

**问题**:旧版空态文案简陋("暂无会话"),且 +新对话 按钮空态时仍然显示。

**改动**:
- [x] `SessionSidebar.jsx` 空态分支改成 📭 emoji + "还没有会话" + "在右侧对话框输入第一条消息试试"
- [x] `+新对话` 按钮包 `!buckets.every(b => b.hidden)` 条件,空态时隐藏

**实测**:静态 grep 验证 L455-457 emoji + 标题 + 提示语

---

### Day 10-5. 键盘导航(✅ 完成)

**问题**:侧边栏无法用键盘快捷切换,只能鼠标点击。

**改动**:
- [x] `SessionSidebar.jsx:focusIdx` state + `flatList` useMemo
- [x] useEffect 注册 `ArrowUp/ArrowDown/Enter/Cmd+1..9` 监听
- [x] 输入框焦点守卫(`tag === "INPUT" || tag === "TEXTAREA"`)
- [x] SessionItem 加 `focused` prop,inline style `outline: 2px solid #0969da`

**实测**:按 ↓ 后 sidebar 第 13 个 div 出现 `outline: rgb(9, 105, 218) solid 2px`;再按 ↓ → 位置 16(说明 ↑/↓ 移动高亮生效)。Cmd+1 被 OS 路由给浏览器切 tab,但 React handler 注册到位

---

### Day 10-6. 端到端 + 浏览器实测(✅ 完成)

**改动**:
- [x] `tests/test_session_sidebar_visual.py` 更新 4 个 Day 8 过严断言
- [x] Chrome DevTools 端到端跑 9 项验证(8/9 通过,Cmd+1 受 OS 限制)

**结果**:156/158 pytest 通过(2 个基线失败属于 Day 9 历史遗留的 JSX 副本同步问题,与 Day 10 工作无关)

---

## ✅ Day 10 修复项(2026-06-22)— 浏览器实测 4 bug

> 本章节记录 Day 10 UI 6 改造项落地后,用户在 PyCharm 启动实测暴露的 4 个新 bug 的修复。

### 修复项 1. 过滤空壳 session(✅ 完成)

**问题**:`manager.py:list_sessions` 不过滤 `message_count=0` 的历史空壳,导致侧边栏显示 18 个会话(实际只有 1 个有效)。

**改动**:
- [x] `src/yantu/session/manager.py:38-70` — `list_sessions` 加 `min_message_count: int = 0` 参数(向后兼容)
- [x] `src/yantu/ui/app.py:651-657` — `/api/sessions` 默认传 `min_message_count=1`
- [x] `SessionSidebar.jsx:35-39` — 前端 `useMemo` 软过滤 `nonEmptySessions`(后端 schema 改动时仍安全)
- [x] `SessionSidebar.jsx` buckets + 底部计数改用 `nonEmptySessions`
- [x] `tests/session/test_manager.py` 加 3 个 `test_list_min_message_count_*` 测试
- [x] `tests/test_session_sidebar_visual.py` 加 `test_bug1_filters_empty_sessions`

**实测**:`/api/sessions` 返回 5 个会话(原 18),`message_count` 全部 >= 2,底部"5 个会话"

---

### 修复项 2. 键盘导航 useRef 桥接(✅ 完成)

**问题**:键盘导航 useEffect deps `[flatList, focusIdx]` 每次 buckets 变就 unmount/remount `document.keydown`,与 layout thrashing 竞争导致主线程 long task,体感"折叠后页面不响应"。

**改动**:
- [x] `SessionSidebar.jsx:111-160` — `flatListRef` + `focusIdxRef` 桥接,handler 空 deps 只挂一次,内部走 ref 拿最新值
- [x] `tests/test_session_sidebar_visual.py` 加 `test_bug2_keyboard_handler_uses_ref`

**验证**:原行为不变(↑/↓/Enter/Cmd+1..9 全工作),handler mount 次数从"每次 buckets 变"降到"组件 mount 一次"

---

### 修复项 3. 搜索框 IME 感知(✅ 完成)

**问题**:Ctrl K handler 的 `e.preventDefault()` 在中文 IME composition 中也派发,抢走搜索框焦点;`visibility: hidden` 折叠态不响应输入。

**改动**:
- [x] `SessionSidebar.jsx:67-71` — Ctrl K handler 加 `isComposing || keyCode === 229` 守卫
- [x] `SessionSidebar.jsx:432-435` — 搜索 input 加 `onCompositionStart/End` 显式同步搜索值(拼音/日文输入未结束时让浏览器自然控制,compositionEnd 时手动 setSearchQuery)
- [x] `tests/test_session_sidebar_visual.py` 加 `test_bug3_ime_aware_ctrl_k`

**验证**:中文拼音输入"xi'an"正常显示,不被 Ctrl K handler 抢走;单独按 Ctrl K 仍聚焦搜索框

---

### 修复项 4. activeId 改 useState + WS 事件订阅(✅ 完成)

**问题**:`const activeId = props.activeId` 是普通变量不是 state;`react-runner` 不重 mount,prop 改了 const 不会重读,导致用户点击会话后**视觉上 active 高亮不更新**,体感"没切换"。

**改动**:
- [x] `SessionSidebar.jsx:19-32` — `const activeId` 改 `useState` + useEffect 主动同步 prop(react-runner 兜底,主要靠 WS onEvt)
- [x] `SessionSidebar.jsx:74-87` — `sessions-updated` listener 识别 `detail.action`(`switch`/`created`/`hard_delete`/`auto_reset`)本地更新 activeId
- [x] `SessionSidebar.jsx:113-114` — 加 `activeIdRef` 给 onEvt 内部读最新 activeId
- [x] `tests/test_session_sidebar_visual.py` 加 `test_bug4_activeid_is_state`

**验证**:点击会话 A → Network 200 + WS `sessions_changed/switch` 帧推过来 → onEvt 触发 → setActiveId(A) → 视觉上 A 立即高亮

---

## 🎯 Day 11 — 折叠 UI 重构(transform 滑出 + FAB)

> **用户反馈**:折叠会连着整个对话一起被收,不是单独的收起侧边栏
> **根因**:Day 10 用 `width: 60px` + `body padding-left: 60px` 联动 → 主对话跟着"被挤"
> **方案**:对齐豆包 — `transform: translateX(-220px)` 滑出 title 列(留 60px avatar 列)+ main `margin-left` 联动 + FAB 浮动按钮

### Day 11-1. CSS 改造(custom-header.js)

- [x] sidebar `width: 60px` 反模式删除
- [x] sidebar 折叠改 `transform: translateX(-220px)`
- [x] 主对话区 `.chainlit-container` 用 `margin-left: 280px`,折叠归 60px
- [x] `body padding-left: 280px` 反模式删除
- [x] transition 200ms ease 平滑过渡

### Day 11-2. FAB 浮动按钮(custom-header.js)

- [x] `#sidebar-toggle-fab` 注入,fixed 屏左
- [x] 展开时 `left: 292px`(贴着 sidebar 右边),折叠时 `left: 72px`(贴着 60px avatar 列右边)
- [x] 点击 dispatch `window CustomEvent('sidebar:toggle')`
- [x] MutationObserver 同步 FAB icon(☰ ↔ ✕)
- [x] Ctrl+B / Cmd+B 全局快捷键(输入框内不抢)

### Day 11-3. SessionSidebar 改造

- [x] sidebarStyle `width: 280` 写死,不再 `collapsed ? 60 : 280`
- [x] 删除 header 内 ◀/▶ 折叠按钮
- [x] 删除 footer ⏵/⏸ 折叠按钮
- [x] 监听 `sidebar:toggle` 事件 → `setCollapsed`
- [x] `collapsedRef` useRef 桥接避免 React 异步丢 toggle

### Day 11-4. 测试 + 文档

- [x] `tests/test_session_sidebar_visual.py` 加 8 个新断言(Day 11 系列)
- [x] pytest 168/170 通过(2 历史失败与 Day 11 无关)
- [x] PROGRESS.md 加 Day 11 段(改动清单 + 验证清单 + 风险与回滚)
- [x] TODO.md 加 Day 11 段(本段)

**结果**:168/170 pytest 通过,Day 11 新增 8 个断言全部通过,JSX 副本同步一致。等待浏览器实测验证。

---

## 📝 完成定义(每个 TODO 必填)

1. ✅ pytest 全过(新功能有专项测试)
2. ✅ Chainlit UI 实测(至少 2 个 prompt 验证)
3. ✅ PROGRESS.md 加对应版本号 + 改动记录
4. ✅ Git commit + push(等用户授权)
5. ✅ memory 文件夹(若有新经验)写一条 `feedback` 类型的 memory