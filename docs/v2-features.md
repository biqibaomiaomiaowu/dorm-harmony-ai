# V2/V3 功能说明

本文档记录当前 V2 与 V3 已落地功能、对应页面/API 和运行限制。V2 以“事件档案”为核心，把单次事件记录升级为可持续查看、汇总分析、参与 AI 模拟和复盘的演示级闭环；V3 在此基础上把运行时数据迁移到 SQLite，接入真实流式模拟，并将沟通复盘升级为可保存、可导出、可复练的产品化页面。

## 页面与流程

| 页面 | 路由 | 核心功能 |
| --- | --- | --- |
| 首页 | `/` | 展示产品定位、核心流程和运行增强功能入口 |
| 事件记录 | `/record` | 记录事件日期、类型、严重程度、频率、多情绪、主情绪、沟通状态、冲突状态和描述 |
| 事件档案 | `/archive` | 查看已保存事件、单条压力快照、情绪标签和删除入口 |
| 宿舍总压力分析 | `/analysis` | 基于事件档案生成总压力值、风险等级、主要来源、趋势图、趋势提示和 AI 心晴见解 |
| AI 沟通模拟 | `/simulate` | 选择/自定义场景，配置舍友画像，接入事件档案上下文，使用 `/api/simulate/stream` 进行多轮流式模拟 |
| 沟通复盘 | `/review` | 基于模拟对话生成表达总结、表现评分、风险提醒、多条改写建议、沟通计划，并支持历史、导出、对话弹窗和再练一次 |

## 已实现功能

| 功能 | 实现说明 | 主要接口/文件 |
| --- | --- | --- |
| 事件档案 | `POST /api/events` 保存事件，`GET /api/events` 按 `event_date desc, created_at desc` 返回，`DELETE /api/events/{id}` 删除事件；V3 默认写入 SQLite，并在首次启动时导入旧 JSON 档案 | `backend/app/event_store.py`、`frontend/src/data/eventArchive.ts`、`frontend/src/views/EventArchiveView.vue` |
| 总压力分析 | `GET /api/events/analysis` 基于全部事件重新计算当前宿舍关系总压力，包含近 30 天数量、事件类型贡献和趋势提示 | `backend/app/archive_analysis.py`、`docs/scoring-model.md`、`frontend/src/views/AnalysisView.vue` |
| 压力趋势图 | 分析页使用 ECharts 将事件档案压力变化展示为趋势图，空数据时显示固定空态 | `frontend/src/views/AnalysisView.vue` |
| 多情绪记录 | 事件记录支持 `emotions` 多选和 `primary_emotion` 主情绪，同时兼容旧 `emotion` 字段 | `backend/app/schemas.py`、`frontend/src/views/RecordView.vue` |
| 事件档案 AI 心晴见解 | `POST /api/events/insight` 基于当前档案和总压力分析生成 `insight`、`care_suggestion`、`communication_focus` 和安全提示 | `backend/app/main.py`、`backend/app/ai_prompts.py`、`frontend/src/views/AnalysisView.vue` |
| 自定义舍友 | 模拟页支持 1-5 位舍友，预设或自定义标签、头像和 0-5 画像属性 | `backend/app/schemas.py`、`frontend/src/views/SimulationView.vue` |
| 多轮流式模拟 | `/api/simulate/stream` 以 NDJSON 返回 `start`、`reply`、`final` 事件；前端通过 `useSimulationSession.ts` 消费流并逐条展示回复 | `backend/app/main.py`、`frontend/src/composables/useSimulationSession.ts`、`frontend/src/data/week1.ts`、`frontend/src/views/SimulationView.vue` |
| SQLite 会话记忆 | `conversation_id`、`turn_id`、`is_continuation` 和 `max_replies` 基于 LangGraph SQLite checkpointer 持久化；重启后同一 SQLite 文件仍可继续会话 | `backend/app/ai_service.py`、`backend/app/main.py` |
| 固定会话失效态 | 当 continuation 或复盘传入不存在的 `conversation_id` 时，后端返回 `400`，前端显示“会话失效”错误态并提供一键重新开始 | `backend/app/main.py`、`frontend/src/composables/useSimulationSession.ts`、`frontend/src/views/SimulationView.vue` |
| 复盘评分与沟通计划 | `/api/review` 支持通过 `conversation_id` 读取 SQLite 会话记忆，也兼容直接传 `dialogue`；响应包含 `performance_scores`、`rewrite_suggestions`、`communication_plan` 和 Demo 标识 | `backend/app/schemas.py`、`backend/app/ai_service.py`、`frontend/src/views/ReviewView.vue` |
| 复盘历史 | 真实 `/api/review` 成功后保存报告；`GET /api/reviews` 返回最近摘要，`GET /api/reviews/{review_id}` 返回详情 | `backend/app/review_store.py`、`backend/app/main.py`、`frontend/src/data/reviewHistory.ts`、`frontend/src/views/ReviewView.vue` |
| 复盘产品化 | 复盘页支持 Markdown/PNG 导出、历史切换、原话 vs 推荐话术突出展示、沟通计划卡片、再练一次和对话记录入口卡片/弹窗 | `frontend/src/views/ReviewView.vue`、`frontend/src/data/reviewHistory.ts` |

## 当前限制

- 运行时事件档案、会话记忆和复盘历史默认保存在 `backend/.runtime/dorm_harmony.sqlite3`，可通过 `DORM_HARMONY_SQLITE_PATH` 覆盖。它适合本地演示，不提供账号体系、云端同步、多用户隔离、权限控制、云端备份或管理后台。
- V3 会在默认 SQLite 初始化时尝试导入旧 `backend/.runtime/events.json`。`DORM_HARMONY_EVENT_STORE_PATH` 仅用于旧 JSON 导入兼容，不再作为默认写入位置。
- 会话记忆已经从单进程内存升级为 LangGraph SQLite checkpointer；后端重启后同一 SQLite 文件内的 `conversation_id` 可继续用于 continuation 和复盘。切换 SQLite 文件、清空 `.runtime` 或传入不存在的旧 id 时仍会提示找不到对应对话，并要求重新演练。
- 浏览器刷新后前端可能恢复 `localStorage` 中的 `conversation_id`，但真实会话内容以 SQLite 为准。
- 未配置 `DEEPSEEK_API_KEY` 或兼容 `OPENAI_API_KEY` 时，`/api/simulate`、`/api/simulate/stream`、`/api/review` 和 `/api/events/insight` 返回 `503`；前端演示兜底只用于页面展示，不代表后端真实 AI 生成成功。
- 本项目不进行心理疾病诊断、医学判断或人格评价；所有压力值和 AI 文案仅用于宿舍关系压力趋势提示与沟通训练建议。
