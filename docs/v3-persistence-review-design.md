# 舍友心晴 V3 持久化与复盘产品化设计

## 背景

当前项目已经具备完整演示链路：事件记录、事件档案、总压力分析、AI 沟通模拟和沟通复盘。现有问题集中在“演示可跑”到“产品闭环可靠”的差距：

- 事件档案仍使用本地 JSON 文件，适合演示但不适合持续迭代。
- AI 模拟会话记忆使用 LangGraph `InMemorySaver`，后端重启后 `conversation_id` 无法继续用于模拟或复盘。
- 后端已提供 `/api/simulate/stream`，前端也有 helper，但模拟页实际仍使用普通 `/api/simulate` 单条请求循环。
- `SimulationView.vue` 同时承担页面状态、模拟请求、排队、重试、缓存和 UI 控制，复杂度偏高。
- 复盘页只展示当前复盘结果，缺少历史保存、导出、话术对比、沟通计划和“再练一次”的产品化闭环。
- 分析页使用仪表和来源条展示当前状态，缺少真正按时间变化的趋势图。

## 目标

本轮迭代把 V2 演示闭环升级为 V3 本地产品闭环：

1. 事件档案从 JSON 文件迁移到 SQLite。
2. 后端会话记忆不再是内存态，改用 LangGraph SQLite checkpointer 持久化。
3. 前端模拟页真正接入 `/api/simulate/stream`。
4. 模拟复杂逻辑抽到 `useSimulationSession.ts`。
5. continuation 或旧会话出错时展示固定错误态 UI：会话失效后一键重新开始。
6. 分析页展示真实趋势图。
7. 复盘报告继续产品化：支持导出图片或 Markdown、复盘历史、原话 vs 推荐话术强化、沟通计划卡片、对话记录入口卡片与弹窗、用推荐话术再练一次。

## 非目标

本轮不引入账号体系、云端同步、多用户权限、数据库迁移框架、后台管理台或心理诊断能力。SQLite 是本地 Demo 级持久化层，不承诺生产级并发、高可用或数据恢复。

## 后端设计

### SQLite 运行时路径

新增统一运行时 SQLite 路径：

- 默认路径：`backend/.runtime/dorm_harmony.sqlite3`
- 环境变量：`DORM_HARMONY_SQLITE_PATH`

事件档案、复盘历史和 LangGraph checkpoint 默认写入同一个 SQLite 文件。`backend/.runtime/` 已被 `.gitignore` 忽略，不提交运行时数据。

### 事件档案存储

保留 `InMemoryEventStore` 供测试使用，新增 `SQLiteEventStore` 作为默认实现。`JsonEventStore` 不再作为 FastAPI 默认存储，但可删除或仅保留兼容测试迁移参考。

SQLite 表 `events`：

| 字段 | 说明 |
| --- | --- |
| `id TEXT PRIMARY KEY` | 事件 id |
| `event_date TEXT NOT NULL` | `YYYY-MM-DD` |
| `created_at TEXT NOT NULL` | ISO datetime |
| `event_type TEXT NOT NULL` | 事件类型枚举值 |
| `severity INTEGER NOT NULL` | 1-5 |
| `frequency TEXT NOT NULL` | 频率枚举值 |
| `emotion TEXT NOT NULL` | 主情绪兼容字段 |
| `emotions_json TEXT NOT NULL` | 多情绪 JSON 数组 |
| `primary_emotion TEXT NOT NULL` | 主情绪 |
| `has_communicated INTEGER NOT NULL` | 0/1 |
| `has_conflict INTEGER NOT NULL` | 0/1 |
| `description TEXT NOT NULL` | 事件描述 |
| `single_analysis_json TEXT NOT NULL` | 单条分析 JSON |

存储接口行为保持不变：

- `add()` 写入事件和 `single_analysis`。
- `list()` 按 `event_date DESC, created_at DESC` 返回。
- `delete()` 删除指定 id，返回布尔值。

### JSON 档案迁移

首次使用 `SQLiteEventStore` 时，如果 SQLite `events` 表为空，且旧默认 JSON 路径 `backend/.runtime/events.json` 存在，则执行一次兼容导入：

- 读取 JSON 数组并用 `EventRecord.model_validate()` 校验。
- 将合法记录写入 SQLite，保持原 `id`、`created_at` 和 `single_analysis`。
- 导入成功后不删除 JSON 文件，而是写入 `runtime_migrations` 表记录 `json_events_imported`，避免重复导入。
- 如果 JSON 文件损坏或字段不合法，不阻塞后端启动；记录迁移错误到日志，写入 `json_events_import_failed` 迁移标记，接口继续使用 SQLite 空档案，避免每次启动重复报同一份坏数据。

### LangGraph SQLite 会话记忆

后端新增依赖 `langgraph-checkpoint-sqlite>=3.0.3,<4`。当前稳定版 3.0.3 支持 `SqliteSaver`，并要求启用安全反序列化限制，因此后端在创建 checkpointer 前设置：

```python
os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")
```

会话记忆使用：

```python
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver

conn = sqlite3.connect(path, check_same_thread=False)
checkpointer = SqliteSaver(conn)
checkpointer.setup()
```

`ConversationMemory` 改为支持两种 checkpointer：

- 测试可继续注入 `InMemorySaver` 或自定义 checkpointer。
- 默认运行时通过 `ConversationMemory.sqlite(path)` 创建 SQLite connection 和 `SqliteSaver`，由 `ConversationMemory` 持有连接生命周期。
- 不使用 `SqliteSaver.from_conn_string()` 的返回值作为长期对象，因为官方接口返回 context manager；如需使用该方法，必须显式进入上下文并保持上下文生命周期。

为了避免只有 checkpoint 而没有会话登记信息，新增自管元数据表 `conversation_meta`：

| 字段 | 说明 |
| --- | --- |
| `conversation_id TEXT PRIMARY KEY` | 会话 id |
| `created_at TEXT NOT NULL` | 创建时间 |
| `updated_at TEXT NOT NULL` | 更新时间 |
| `latest_turn_id TEXT` | 当前最新用户回合 id |

`ConversationMemory.has_conversation()` 不再依赖进程内 set，而是查询 `conversation_meta`。`mark_latest_turn()` 写入 `latest_turn_id`。`append_user_message()` 和 `append_roommate_message()` 每次写 checkpoint 后更新 `updated_at`。这样后端重启后，同一个 `conversation_id` 可以继续用于 continuation 和 `/api/review`。

SQLite checkpointer 只作为本地演示和小项目持久化方案使用。默认连接设置 `PRAGMA busy_timeout = 5000` 和 `PRAGMA journal_mode = WAL`，降低本地并发读写冲突；不承诺生产多进程扩展能力。

### 复盘历史存储

新增 `ReviewHistoryStore`，默认 SQLite 实现，保存每次非 demo 复盘报告。

SQLite 表 `review_reports`：

| 字段 | 说明 |
| --- | --- |
| `id TEXT PRIMARY KEY` | 复盘报告 id |
| `created_at TEXT NOT NULL` | 生成时间 |
| `conversation_id TEXT` | 可为空，兼容直接传 dialogue 的复盘 |
| `scenario TEXT NOT NULL` | 场景 |
| `request_json TEXT NOT NULL` | 复盘请求 |
| `response_json TEXT NOT NULL` | 复盘响应 |
| `dialogue_json TEXT NOT NULL` | 实际用于复盘的对话 |
| `summary TEXT NOT NULL` | 摘要冗余字段 |
| `score_clarity INTEGER NOT NULL` | 表达清晰度 |
| `score_empathy INTEGER NOT NULL` | 共情能力 |
| `score_resolution INTEGER NOT NULL` | 问题解决度 |

新增接口：

- `GET /api/reviews`：按 `created_at DESC` 返回历史复盘摘要。
- `GET /api/reviews/{review_id}`：返回单条复盘详情。

`POST /api/review` 保持响应体兼容，不强制增加字段。前端生成复盘成功后可再请求历史，也可由后端在响应里保留原字段不变，避免破坏现有页面。

为了让复盘历史稳定保存真实对话，`DormHarmonyAIService.review()` 内部会先解析出实际用于复盘的 `dialogue`，再返回带有 `dialogue` 的服务层结果，或提供公开方法 `resolve_review_dialogue(request)` 给路由复用。路由层不得调用私有 `_resolve_review_dialogue()`。测试 fake service 场景下，如果无法从服务层取得 dialogue，则回退保存 request 中的 `dialogue`；仍为空时保存空数组并让详情页显示“历史记录缺少对话快照”。

### 复盘响应增强

扩展 `ReviewResponse`，保持旧字段兼容，新增可选字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `communication_plan` | object | 沟通计划卡片 |

`communication_plan` 包含：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `opening` | string | 开场白 |
| `specific_request` | string | 具体请求 |
| `fallback_plan` | string | 兜底方案 |

后端从 AI 草稿中优先取该字段；如果模型缺项，则根据第一条 `rewrite_suggestions` 和 `next_steps` 生成兜底计划，保证前端始终可展示。

## 前端设计

### 模拟逻辑 composable

新增 `frontend/src/composables/useSimulationSession.ts`，把当前 `SimulationView.vue` 中的会话状态、请求构造、stream 事件处理、排队、缓存和错误态迁出。

Composable 对外提供：

- `conversationMessages`
- `conversationId`
- `isSubmitting`
- `submitError`
- `sessionErrorState`
- `generationStatus`
- `queuedUserMessages`
- `canEnterReview`
- `sendMessage(message)`
- `resetConversation()`
- `retryFromExpiredSession(message?)`

`SimulationView.vue` 保留页面结构、舍友编辑、场景管理和模板展示，不再直接管理 AI 请求循环。

### Stream 接入

模拟页使用 `submitSimulationStreamRequest()` 调 `/api/simulate/stream`。后端按 `start -> reply* -> final` 返回 NDJSON：

- `start` 到达时立即记录 `conversation_id`。
- 每个 `reply` 到达时追加到对话列表。
- `final` 到达时补齐 `archive_context_used`、`archive_context_summary` 和 `safety_note`。

如果 stream 请求返回 400 且 detail 包含“未找到对应的模拟对话”，前端进入固定错误态：

- 展示“会话已失效，可能是后端数据被清理或会话不存在。”
- 提供“重新开始”按钮。
- 点击后清除 `conversation_id`、当前缓存和排队消息，保留当前场景、舍友画像和输入框内容。

### 再练一次

复盘页的“再练一次”按钮把推荐话术传回模拟页：

- 使用 query：`/simulate?practice=<encoded>&scenario=<encoded>`
- 模拟页 onMounted 读取 query，预填 `userMessage` 和场景。
- 如果已有旧会话缓存，显示新练习草稿，不自动发送，用户点击发送后创建新会话。

### 趋势图

`GET /api/events` 已返回所有事件和每条 `single_analysis.pressure_score`。分析页基于事件档案生成趋势数据：

- X 轴：事件日期。
- Y 轴：事件压力分数。
- 同一天多条记录取平均分并保留数量。
- 最近 14 个日期点优先展示；不足 14 个展示全部。

使用现有依赖 `echarts`，新增趋势折线图组件或直接在 `AnalysisView.vue` 中初始化图表。图表必须在窗口 resize 时自适应，在组件卸载时销毁实例。

### 复盘产品化

复盘页新增：

1. 复盘历史：展示最近复盘列表，可切换查看历史详情。
2. 导出 Markdown：生成包含场景、时间、表现评分、总结、原话/推荐话术、沟通计划和安全提示的 `.md` 文件。
3. 导出图片：把报告主体 DOM 渲染为图片下载。优先使用浏览器原生 SVG `foreignObject` 或轻量本地实现，不新增大型前端截图依赖；如果浏览器限制导致失败，展示明确错误并保留 Markdown 导出。
4. 原话 vs 推荐话术：强化为左右对比块，原话显示风险点，推荐话术显示原因。
5. 沟通计划卡片：展示“开场白 + 具体请求 + 兜底方案”。
6. 对话记录入口卡片：页面正文不再直接铺开完整对话，而是展示一张摘要入口卡片，包含用户表达轮数、舍友回复数和“查看完整对话”按钮。
7. 对话记录弹窗：点击入口卡片后弹出 modal 展示完整会话记录；支持 Esc 关闭、遮罩点击关闭、焦点回到入口按钮，并使用现有 `Transition` 过渡。
8. 再练一次：使用第一条推荐话术或 `rewritten_message` 进入模拟页。

复盘页新增 UI 必须贴合现有整体风格：粗黑边框、`pop-card` / `pop-shadow`、Material Symbols、弹性进入动画、列表过渡和明确 hover/active 反馈。不要把完整对话列表常驻在主页面，避免挤占复盘核心内容。

## 文档更新

更新以下文档：

- `README.md`：说明 SQLite 运行时、会话持久化和本地限制。
- `docs/backend-api-contract.md`：补充新接口、复盘增强字段、SQLite 配置。
- `docs/v2-features.md`：升级说明为 V3 或补充 V3 章节。
- `docs/phase3-status.md`：标记 stream 已接入前端，不再是保留 helper。

## 测试策略

后端：

- SQLite 事件存储 add/list/delete。
- SQLite 事件存储并发或重复实例读取。
- ConversationMemory 使用 SQLite checkpointer 后，重建实例仍能读取旧会话。
- `/api/simulate/stream` 保持事件顺序和 final 结构。
- `/api/review` 生成报告后写入历史。
- `GET /api/reviews` 和 `GET /api/reviews/{id}` 返回正确数据。

前端：

- `npm run build` 必须通过。
- 现有 verify 脚本可继续运行；如果旧断言与 V3 设计冲突，更新脚本而不是保留过期断言。
- 手动检查模拟页：stream 回复逐条出现、会话失效错误态可一键重开。
- 手动检查复盘页：历史切换、Markdown 导出、图片导出、再练一次预填。
- 手动检查分析页：趋势图非空、resize 后不溢出。

## 风险与处理

- `langgraph-checkpoint-sqlite` 是新增依赖。本轮在 `requirements.txt` 加入版本范围，并在测试中验证 import 和持久化行为。
- SQLite checkpointer 需要管理连接生命周期。默认服务使用单例 `ConversationMemory`，内部持有 SQLite connection 和 checkpointer；测试可以用临时 SQLite 路径创建独立实例。
- 前端图片导出受浏览器安全策略影响。Markdown 导出作为稳定主路径，图片导出失败时给出可恢复提示。
- 旧 JSON 事件档案会在首次打开 SQLite store 时自动导入一次；迁移失败时保留 JSON 文件并继续使用 SQLite 空档案。
- 旧 localStorage 中的模拟缓存可能与 V3 字段不完全一致。前端读取时继续做结构校验，无法识别则清除旧缓存并提示重新开始。
