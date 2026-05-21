# V2 功能说明

本文档记录当前 V2 已落地功能、对应页面/API 和运行限制。V2 以“事件档案”为核心，把单次事件记录升级为可持续查看、汇总分析、参与 AI 模拟和复盘的演示级闭环。

## 页面与流程

| 页面 | 路由 | 核心功能 |
| --- | --- | --- |
| 首页 | `/` | 展示产品定位、核心流程和 V2 功能入口 |
| 事件记录 | `/record` | 记录事件日期、类型、严重程度、频率、多情绪、主情绪、沟通状态、冲突状态和描述 |
| 事件档案 | `/archive` | 查看已保存事件、单条压力快照、情绪标签和删除入口 |
| 宿舍总压力分析 | `/analysis` | 基于事件档案生成总压力值、风险等级、主要来源、趋势提示和 AI 心晴见解 |
| AI 沟通模拟 | `/simulate` | 选择/自定义场景，配置舍友画像，接入事件档案上下文，进行多轮模拟 |
| 沟通复盘 | `/review` | 基于模拟对话生成表达总结、表现评分、风险提醒、多条改写建议和后续行动建议 |

## 已实现 V2 功能

| 功能 | 实现说明 | 主要接口/文件 |
| --- | --- | --- |
| 事件档案 | `POST /api/events` 保存事件，`GET /api/events` 按 `event_date desc, created_at desc` 返回，`DELETE /api/events/{id}` 删除事件 | `backend/app/event_store.py`、`frontend/src/data/eventArchive.ts`、`frontend/src/views/EventArchiveView.vue` |
| 总压力分析 | `GET /api/events/analysis` 基于全部事件重新计算当前宿舍关系总压力，包含近 30 天数量、事件类型贡献和趋势提示 | `backend/app/archive_analysis.py`、`docs/scoring-model.md`、`frontend/src/views/AnalysisView.vue` |
| 多情绪记录 | 事件记录支持 `emotions` 多选和 `primary_emotion` 主情绪，同时兼容旧 `emotion` 字段 | `backend/app/schemas.py`、`frontend/src/views/RecordView.vue` |
| 事件档案 AI 心晴见解 | `POST /api/events/insight` 基于当前档案和总压力分析生成 `insight`、`care_suggestion`、`communication_focus` 和安全提示 | `backend/app/main.py`、`backend/app/ai_prompts.py`、`frontend/src/views/AnalysisView.vue` |
| 自定义舍友 | 模拟页支持 1-5 位舍友，预设或自定义标签、头像和 0-5 画像属性 | `backend/app/schemas.py`、`frontend/src/views/SimulationView.vue` |
| 多轮模拟 | `/api/simulate` 使用 `conversation_id`、`turn_id`、`is_continuation` 和 `max_replies` 支持短期会话记忆；前端逐条请求并展示多轮回复 | `backend/app/ai_service.py`、`frontend/src/views/SimulationView.vue` |
| 流式模拟接口 | `/api/simulate/stream` 以 NDJSON 返回 `start`、`reply`、`final` 事件，接口契约已保留给流式展示 | `backend/app/main.py`、`frontend/src/data/week1.ts` |
| 复盘评分 | `/api/review` 支持通过 `conversation_id` 读取短期记忆，也兼容直接传 `dialogue`；响应包含 `performance_scores` 和 `rewrite_suggestions` | `backend/app/schemas.py`、`frontend/src/views/ReviewView.vue` |

## 当前限制

- 事件档案使用本地 JSON 文件保存，默认路径为 `backend/.runtime/events.json`，可通过 `DORM_HARMONY_EVENT_STORE_PATH` 覆盖。它适合本地演示，不提供账号体系、云端同步、多用户隔离、权限控制或数据库迁移。
- JSON 存储会使用线程锁和 POSIX 文件锁保护读改写，但仍不是生产数据库；并发、高可用和数据恢复不在当前 Demo 范围内。
- 会话记忆使用后端单进程内存保存，`conversation_id` 只在当前 FastAPI 进程内有效；后端重启、切换进程或传入旧 `conversation_id` 后，模拟/复盘会提示找不到对应对话。
- 浏览器刷新后前端可能恢复 `localStorage` 中的 `conversation_id`，但 conversation memory 只保存在后端单进程内，不能靠刷新持久化；后端重启、切换进程或旧 id 会导致 memory 丢失，需要重新演练。
- 未配置 `DEEPSEEK_API_KEY` 或兼容 `OPENAI_API_KEY` 时，`/api/simulate`、`/api/simulate/stream`、`/api/review` 和 `/api/events/insight` 返回 `503`；前端演示兜底只用于页面展示，不代表后端真实 AI 生成成功。
- 本项目不进行心理疾病诊断、医学判断或人格评价；所有压力值和 AI 文案仅用于宿舍关系压力趋势提示与沟通训练建议。
