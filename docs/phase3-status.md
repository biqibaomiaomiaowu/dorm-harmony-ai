# 第三阶段联调优化与开发收尾状态

本文档记录第三阶段后端、接口、AI、技术说明、策划文档和开发限制收尾情况。第三阶段之后的 V2/V3 增量已补充事件档案、宿舍总压力分析、事件档案 AI 心晴见解、SQLite 会话记忆、真实流式模拟、复盘历史和相关前端页面；历史状态说明以本文档的 V3 更新段落为准。

## 范围边界

本阶段朱春雯负责：

- `B3-1` 接口联调结果记录
- `B3-2` 后端问题修复记录
- `B3-3` 技术说明
- `B3-4` 最终策划文档一致性整理
- `B3-5` 开发限制说明

完整网页 Demo 是共同任务。当前仓库已完成前后端核心页面、Vite `/api` 代理、后端 CORS、SQLite 事件档案、LangGraph SQLite 会话记忆、复盘历史和 AI 接口契约；真实 AI 结果仍依赖后端服务启动以及 `DEEPSEEK_API_KEY` 或兼容的 `OPENAI_API_KEY`。

## 当前状态

| 任务编号 | 当前状态 | 证据 |
| --- | --- | --- |
| B3-1 完成接口联调 | 已完成静态联调准备；V3 已补充事件档案、流式模拟和复盘历史相关接口 | `frontend/vite.config.ts` 已配置 `/api` 代理到 `http://127.0.0.1:8000`；`backend/app/main.py` 已允许本地 Vite origin；`frontend/src/data/eventArchive.ts`、`frontend/src/data/week1.ts` 和 `frontend/src/data/reviewHistory.ts` 使用相对 `/api` 路径 |
| B3-2 修复后端问题 | 已完成本轮后端兼容修复 | `backend/app/schemas.py` 兼容当前前端复盘页展示型 speaker 与旧事件类型；`backend/tests/test_api.py` 覆盖 CORS、复盘 payload 兼容、extra 字段拒绝和风险别名收窄 |
| B3-3 整理技术说明 | 已完成并 V3 更新 | 本文档、`README.md`、`docs/backend-api-contract.md`、`docs/scoring-model.md`、`docs/v2-features.md` 已串联 FastAPI、评分模型、SQLite 事件档案、LangChain Prompt、AI 服务、SQLite 会话记忆、复盘历史和安全边界 |
| B3-4 完善最终策划文档 | 已完成当前实现校准 | `docs/sheyou-xinqing-planning.md` 已补充当前真实接口、事件档案和运行限制 |
| B3-5 整理开发限制说明 | 已完成 | 本文档集中记录 Demo 数据范围、AI 输出依赖、本地 SQLite 存储、会话失效边界和验证限制 |

## 接口联调结果

| 接口 | 当前结论 | 说明 |
| --- | --- | --- |
| `GET /health` | 后端可用性接口已实现 | 用于确认 FastAPI 服务启动状态 |
| `POST /api/analyze` | 已实现并兼容旧单事件评分流程 | 后端返回结构化单事件压力分析；保存事件时会同步生成单条压力快照 |
| `POST /api/events` / `GET /api/events` / `DELETE /api/events/{id}` | V3 已实现 | 使用本地 SQLite 存储事件档案，支持保存、读取和删除，并兼容导入旧 JSON 事件档案 |
| `GET /api/events/analysis` | V3 已实现 | 基于事件档案内全部记录重新计算宿舍总压力 |
| `POST /api/events/insight` | V3 已实现 | 基于事件档案和总压力分析调用 DeepSeek 生成 AI 心晴见解 |
| `POST /api/simulate` | V3 已扩展 | 支持动态舍友画像、事件档案上下文、SQLite 会话记忆和多轮模拟 |
| `POST /api/simulate/stream` | V3 已接入页面 | 以 NDJSON 输出 `start`、`reply`、`final`；模拟页通过 `useSimulationSession.ts` 直接消费流式接口 |
| `POST /api/review` | V3 已扩展 | 支持 `conversation_id` 复盘、多条改写建议、沟通计划和真实复盘历史保存，同时继续拒绝未授权 extra 字段 |
| `GET /api/reviews` / `GET /api/reviews/{review_id}` | V3 已实现 | 返回复盘历史摘要和单条复盘详情 |

## 后端问题修复记录

| 问题 | 修复方式 | 验证 |
| --- | --- | --- |
| Vite 前端使用 `/api/*` 相对路径，但本地开发时无法直接到 FastAPI | `frontend/vite.config.ts` 增加 `/api` dev proxy；`backend/app/main.py` 增加本地 CORS origin | `npm run verify:v2`；`backend/tests/test_api.py` CORS preflight 用例 |
| 复盘页可能发送 `你`、`舍友 A（直接型）` 等展示型 speaker | `DialogueMessage` 在校验前归一化为 `user`、`roommate_a`、`roommate_b`、`roommate_c`、`system` | 捕获型 fake service 测试断言 AI service 收到标准 speaker |
| 复盘页可能发送 `noise_conflict`、`privacy_boundary` 等旧事件类型 | `ReviewOriginalEvent.event_type` 在校验前归一化为后端标准事件类型 | 接口测试覆盖 `expense_conflict`、`privacy_boundary`、`emotional_conflict` |
| 分析页派生的 `risk-high` 不应作为真实事件类型传给 AI | 仅允许 `risk-stable`、`risk-pressure`、`risk-high`、`risk-severe` 归一为 `None`；其他 `risk-*` 仍返回 `422` | 接口测试覆盖 `risk-high` 通过配置检查、`risk-critical` 返回 `422` |
| 复盘请求不应吞掉未知浏览器状态 | `ReviewRequest`、`DialogueMessage`、`ReviewOriginalEvent` 均禁止 extra 字段 | 接口测试覆盖顶层 extra 和 dialogue extra 返回 `422` |

## 技术说明

- FastAPI 入口在 `backend/app/main.py`，提供 `GET /health`、`POST /api/analyze`、事件档案接口、总压力分析接口、事件档案 AI 心晴见解接口、`POST /api/simulate`、`POST /api/simulate/stream`、`POST /api/review`、`GET /api/reviews` 和 `GET /api/reviews/{review_id}`。
- 压力评分模型在 `backend/app/scoring.py`，按严重程度、发生频率、情绪、沟通状态和冲突升级情况计算 0-100 压力值。
- 事件档案存储在 `backend/app/event_store.py`，默认使用 SQLite 文件 `backend/.runtime/dorm_harmony.sqlite3`，可通过 `DORM_HARMONY_SQLITE_PATH` 覆盖；旧 `DORM_HARMONY_EVENT_STORE_PATH` 仅用于 JSON 导入兼容。
- AI Prompt 在 `backend/app/ai_prompts.py`，限定大学宿舍沟通场景，支持动态舍友画像、事件档案摘要和非诊断性输出约束。
- AI 服务在 `backend/app/ai_service.py`，通过 LangChain/DeepSeek 结构化输出，并使用 LangGraph SQLite checkpointer 维护会话记忆；缺少 `DEEPSEEK_API_KEY` 且没有兼容的 `OPENAI_API_KEY` 时返回 `503`，AI 调用失败或结构异常返回 `502`。
- 复盘历史存储在 `backend/app/review_store.py`，默认写入同一个 SQLite 文件，并由 `GET /api/reviews` 和 `GET /api/reviews/{review_id}` 提供读取。
- 本地前端开发服务器通过 Vite `/api` 代理访问 `http://127.0.0.1:8000` 的 FastAPI。

## 开发限制说明

- AI 模拟和复盘依赖 `DEEPSEEK_API_KEY`。`OPENAI_API_KEY` 仅作为旧配置兼容 fallback；无 Key 时接口不会伪造成功结果。
- 当前演示数据只覆盖噪音冲突、卫生分工、隐私边界等典型宿舍场景，不代表真实用户数据采集。
- 事件档案、会话记忆和复盘历史使用本地 SQLite 文件保存，适合本地 Demo；不提供账号体系、云端同步、多用户隔离、云端备份、权限控制或管理后台。
- 会话记忆不再是内存态；后端重启后同一 SQLite 文件内的 `conversation_id` 可继续使用。切换 SQLite 文件、清空 `.runtime` 或传入不存在的旧 id 时，模拟/复盘会提示会话失效，需要重新演练。
- 本项目仅提供宿舍关系压力趋势提示和沟通训练建议，不进行心理疾病诊断、医学判断或人格评价。
- 页面截图、演示视频、宣传海报、响应式 UI 细节属于曹乐或第 7 天材料任务，不在本次后端收尾中完成。

## 验证记录

当前分支后端验证命令：

```bash
cd backend
.venv/bin/python -m pytest -q
```

结果以当前执行为准。warning 主要来自 LangGraph 依赖的 pending deprecation 提示。

当前分支前端静态校验命令：

```bash
cd frontend
npm run build
npm run verify:v2
```

`verify:v2` 已追加 V3 静态回归检查：模拟页不再直接调用旧 `submitSimulationRequest`，`useSimulationSession.ts` 使用 `submitSimulationStreamRequest`，复盘页提供对话记录入口卡片/弹窗且不把完整对话长列表常驻页面。
