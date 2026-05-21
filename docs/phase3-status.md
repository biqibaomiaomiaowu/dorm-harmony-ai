# 第三阶段联调优化与开发收尾状态

本文档记录第三阶段后端、接口、AI、技术说明、策划文档和开发限制收尾情况。第三阶段之后的 V2 增量已补充事件档案、宿舍总压力分析、事件档案 AI 心晴见解、短期会话记忆和相关前端页面；历史状态说明以本文档的 V2 更新段落为准。

## 范围边界

本阶段朱春雯负责：

- `B3-1` 接口联调结果记录
- `B3-2` 后端问题修复记录
- `B3-3` 技术说明
- `B3-4` 最终策划文档一致性整理
- `B3-5` 开发限制说明

完整网页 Demo 是共同任务。当前仓库已完成前后端核心页面、Vite `/api` 代理、后端 CORS、事件档案 JSON 存储和 AI 接口契约；真实 AI 结果仍依赖后端服务启动以及 `DEEPSEEK_API_KEY` 或兼容的 `OPENAI_API_KEY`。

## 当前状态

| 任务编号 | 当前状态 | 证据 |
| --- | --- | --- |
| B3-1 完成接口联调 | 已完成静态联调准备；V2 已补充事件档案相关接口 | `frontend/vite.config.ts` 已配置 `/api` 代理到 `http://127.0.0.1:8000`；`backend/app/main.py` 已允许本地 Vite origin；`frontend/src/data/eventArchive.ts` 和 `frontend/src/data/week1.ts` 使用相对 `/api` 路径 |
| B3-2 修复后端问题 | 已完成本轮后端兼容修复 | `backend/app/schemas.py` 兼容当前前端复盘页展示型 speaker 与旧事件类型；`backend/tests/test_api.py` 覆盖 CORS、复盘 payload 兼容、extra 字段拒绝和风险别名收窄 |
| B3-3 整理技术说明 | 已完成并 V2 更新 | 本文档、`README.md`、`docs/backend-api-contract.md`、`docs/scoring-model.md`、`docs/v2-features.md` 已串联 FastAPI、评分模型、事件档案 JSON 存储、LangChain Prompt、AI 服务和安全边界 |
| B3-4 完善最终策划文档 | 已完成当前实现校准 | `docs/sheyou-xinqing-planning.md` 已补充当前 V2 真实接口、事件档案和运行限制 |
| B3-5 整理开发限制说明 | 已完成 | 本文档集中记录 Demo 数据范围、AI 输出依赖、本地 JSON 存储、单进程会话记忆和验证限制 |

## 接口联调结果

| 接口 | 当前结论 | 说明 |
| --- | --- | --- |
| `GET /health` | 后端可用性接口已实现 | 用于确认 FastAPI 服务启动状态 |
| `POST /api/analyze` | 已实现并兼容旧单事件评分流程 | 后端返回结构化单事件压力分析；V2 主流程保存事件时会同步生成单条压力快照 |
| `POST /api/events` / `GET /api/events` / `DELETE /api/events/{id}` | V2 已实现 | 使用本地 JSON 存储事件档案，支持保存、读取和删除 |
| `GET /api/events/analysis` | V2 已实现 | 基于事件档案内全部记录重新计算宿舍总压力 |
| `POST /api/events/insight` | V2 已实现 | 基于事件档案和总压力分析调用 DeepSeek 生成 AI 心晴见解 |
| `POST /api/simulate` | V2 已扩展 | 支持动态舍友画像、事件档案上下文、短期会话记忆和多轮模拟 |
| `POST /api/simulate/stream` | V2 已实现契约 | 以 NDJSON 输出 `start`、`reply`、`final`；页面层当前保留 helper，主模拟页使用逐条 `/api/simulate` 请求 |
| `POST /api/review` | V2 已扩展 | 支持 `conversation_id` 复盘和多条改写建议，同时继续拒绝未授权 extra 字段 |

## 后端问题修复记录

| 问题 | 修复方式 | 验证 |
| --- | --- | --- |
| Vite 前端使用 `/api/*` 相对路径，但本地开发时无法直接到 FastAPI | `frontend/vite.config.ts` 增加 `/api` dev proxy；`backend/app/main.py` 增加本地 CORS origin | `node scripts/verify-phase3.mjs`；`backend/tests/test_api.py` CORS preflight 用例 |
| 复盘页可能发送 `你`、`舍友 A（直接型）` 等展示型 speaker | `DialogueMessage` 在校验前归一化为 `user`、`roommate_a`、`roommate_b`、`roommate_c`、`system` | 捕获型 fake service 测试断言 AI service 收到标准 speaker |
| 复盘页可能发送 `noise_conflict`、`privacy_boundary` 等旧事件类型 | `ReviewOriginalEvent.event_type` 在校验前归一化为后端标准事件类型 | 接口测试覆盖 `expense_conflict`、`privacy_boundary`、`emotional_conflict` |
| 分析页派生的 `risk-high` 不应作为真实事件类型传给 AI | 仅允许 `risk-stable`、`risk-pressure`、`risk-high`、`risk-severe` 归一为 `None`；其他 `risk-*` 仍返回 `422` | 接口测试覆盖 `risk-high` 通过配置检查、`risk-critical` 返回 `422` |
| 复盘请求不应吞掉未知浏览器状态 | `ReviewRequest`、`DialogueMessage`、`ReviewOriginalEvent` 均禁止 extra 字段 | 接口测试覆盖顶层 extra 和 dialogue extra 返回 `422` |

## 技术说明

- FastAPI 入口在 `backend/app/main.py`，提供 `GET /health`、`POST /api/analyze`、事件档案接口、总压力分析接口、事件档案 AI 心晴见解接口、`POST /api/simulate`、`POST /api/simulate/stream` 和 `POST /api/review`。
- 压力评分模型在 `backend/app/scoring.py`，按严重程度、发生频率、情绪、沟通状态和冲突升级情况计算 0-100 压力值。
- 事件档案存储在 `backend/app/event_store.py`，默认使用 `backend/.runtime/events.json`，可通过 `DORM_HARMONY_EVENT_STORE_PATH` 覆盖。
- AI Prompt 在 `backend/app/ai_prompts.py`，限定大学宿舍沟通场景，支持动态舍友画像、事件档案摘要和非诊断性输出约束。
- AI 服务在 `backend/app/ai_service.py`，通过 LangChain/DeepSeek 结构化输出并维护单进程短期会话记忆；缺少 `DEEPSEEK_API_KEY` 且没有兼容的 `OPENAI_API_KEY` 时返回 `503`，AI 调用失败或结构异常返回 `502`。
- 本地前端开发服务器通过 Vite `/api` 代理访问 `http://127.0.0.1:8000` 的 FastAPI。

## 开发限制说明

- AI 模拟和复盘依赖 `DEEPSEEK_API_KEY`。`OPENAI_API_KEY` 仅作为旧配置兼容 fallback；无 Key 时接口不会伪造成功结果。
- 当前演示数据只覆盖噪音冲突、卫生分工、隐私边界等典型宿舍场景，不代表真实用户数据采集。
- 事件档案使用本地 JSON 文件保存，适合本地 Demo；不提供账号体系、云端同步、多用户隔离、生产数据库、权限控制或管理后台。
- 会话记忆只保存在当前 FastAPI 进程内；刷新前端页面可能保留 `conversation_id` 缓存，但后端重启或切换进程后 conversation memory 会丢失，需要重新演练。
- 本项目仅提供宿舍关系压力趋势提示和沟通训练建议，不进行心理疾病诊断、医学判断或人格评价。
- 页面截图、演示视频、宣传海报、响应式 UI 细节属于曹乐或第 7 天材料任务，不在本次后端收尾中完成。

## 验证记录

当前分支后端验证命令：

```bash
cd backend
PYTHONPATH=. .venv/bin/pytest -s tests/test_api.py tests/test_event_archive.py tests/test_ai_contracts.py
```

结果：`116 passed, 1 warning`。warning 来自 LangGraph 依赖的 pending deprecation 提示。

当前分支前端静态校验命令：

```bash
cd frontend
node scripts/verify-phase2.mjs
node scripts/verify-phase3.mjs
node scripts/verify-v2.mjs
```

当前结果：三个静态脚本未通过。失败项主要来自脚本仍检查旧版模拟页/复盘页字符串、streaming-first 页面调用路径和若干旧 CSS 断言；当前页面层主流程使用逐条 `POST /api/simulate` 请求，`/api/simulate/stream` 已实现后端契约并保留前端 helper，但未在 `SimulationView.vue` 页面层直接调用。

完整 Vue build 或浏览器端真实 smoke 仍需在前端依赖完整安装后单独执行。
