# 舍友心晴

《舍友心晴：大学生宿舍压力预警与沟通演练助手》是一款面向大学生宿舍关系的网页版 AI 心理支持工具。项目聚焦宿舍关系压力、沟通回避和冲突积累等常见场景，当前完整流程为“事件记录 -> 事件档案 -> 宿舍总压力分析 -> AI 沟通演练 -> 沟通复盘报告”，帮助用户在真实沟通前进行低风险表达练习。

当前仓库已完成前后端核心 Demo、V2 运行增强、V3 持久化/复盘产品化和 V4 演练/分析升级：已实现 `GET /health`、`POST /api/analyze`、`POST /api/events`、`GET /api/events`、`DELETE /api/events/{id}`、`GET /api/events/analysis`、`GET /api/training/catalog`、`POST /api/events/insight`、`POST /api/simulate`、`POST /api/simulate/stream`、`POST /api/review`、`GET /api/reviews` 和 `GET /api/reviews/{review_id}`。前端已包含首页、事件记录、宿舍总压力分析、事件档案、AI 沟通演练总入口、场景训练、自定义演练和沟通复盘页面；AI 接口通过 LangChain 调用 DeepSeek 官方 OpenAI 兼容 API，并使用结构化响应供前端展示。本地开发已补充 Vite `/api` 代理、FastAPI 本地 CORS、SQLite 事件档案、LangGraph SQLite 会话记忆、真实流式模拟接入、复盘历史保存和复盘报告导出。

本项目不进行心理疾病诊断，不评价用户或舍友的人格状态，只提供宿舍关系压力趋势提示和沟通训练建议。

## 项目定位

| 项目 | 内容 |
| --- | --- |
| 作品名称 | 舍友心晴：大学生宿舍压力预警与沟通演练助手 |
| 作品类型 | 心理健康方向网页版应用 / AI 智能体交互 Demo |
| 面向场景 | 大学生宿舍关系、宿舍压力、人际沟通训练 |
| 目标用户 | 存在宿舍沟通压力、矛盾积累或冲突回避的大学生 |
| 目标技术路线 | Vue + Python FastAPI + LangChain + SQLite；当前已落地 FastAPI + 规则评分模型 + LangChain/DeepSeek 后端 AI 接口 + SQLite 事件档案和会话记忆 |
| 目标核心流程 | 宿舍事件记录 -> 事件档案 -> 宿舍总压力分析 -> AI 沟通演练（场景训练 / 自定义演练） -> 沟通复盘报告；当前已实现完整前端页面、真实后端接口和本地联调配置 |

## 核心功能范围与当前状态

| 功能模块 | 当前状态 | 说明 |
| --- | --- | --- |
| 宿舍事件记录字段 | 已实现并 V2 扩展 | 用户可按接口字段提交事件日期、事件类型、严重程度、发生频率、多情绪/主情绪、沟通状态、冲突升级情况和简短描述 |
| 事件档案 | V3 已实现 | 事件记录会写入后端本地 SQLite，可在 `/archive` 查看、删除，并作为总压力分析和 AI 心晴见解的数据来源 |
| 压力晴雨表 | 第一阶段已实现后端规则分析 | 根据事件信息生成 0-100 的压力值、风险等级、主要矛盾来源和系统建议 |
| 宿舍总压力分析 | V4 已实现 | 基于事件档案按 7/15/30/90 天当前周期生成总压力值、趋势、主要压力来源、情绪分布、事件洞察、推荐场景训练和 AI 心晴见解 |
| 多情绪记录 | V2 已实现 | 事件记录支持 `emotions` 多选和 `primary_emotion` 主情绪，兼容旧 `emotion` 字段 |
| AI 沟通演练 | V4 已实现 | 总入口下包含固定分步场景训练和保留原能力的自定义演练；后端通过 LangChain/DeepSeek 生成可配置舍友回复，支持事件档案上下文、SQLite 会话记忆、流式前端展示和多轮演练 |
| 沟通复盘报告 | V4 已实现 | 后端通过 LangChain/DeepSeek 分析模拟对话，输出表达优点、潜在问题、表现评分、多条改写建议、沟通计划，并保存复盘历史；复盘来源可区分场景训练和自定义演练，支持 Markdown 导出和再次演练 |

## 目标典型使用流程

1. 用户进入首页，点击“记录一次宿舍事件”。
2. 用户填写宿舍事件信息，例如“舍友晚上打游戏声音太大”。
3. 系统生成压力值、风险等级、主要原因和建议。
4. 用户可进入事件档案查看记录，也可进入宿舍总压力分析查看整体趋势。
5. 用户进入 AI 沟通演练，可选择固定场景训练，也可进入自定义演练配置舍友画像并输入沟通话术。
6. AI 舍友按画像和 SQLite 会话记忆多轮回应。
7. 用户完成练习后，系统生成沟通复盘报告、表现评分、沟通计划和多条优化话术；用户可查看历史复盘、导出报告，或按来源回到场景训练/自定义演练再练一次。

## 技术方案

项目目标采用前后端分离架构。当前后端已落地 FastAPI 接口层、压力评分模块、SQLite 事件档案、安全提示逻辑、LangChain Prompt、DeepSeek 官方 OpenAI 兼容结构化调用、LangGraph SQLite 会话记忆和复盘历史；前端已落地完整页面路由和本地 `/api` 代理。

```text
用户浏览器
  -> Vue 前端页面
  -> Python FastAPI 后端
  -> 压力评分模块 / SQLite 运行时存储 / LangChain AI 模块
  -> DeepSeek 官方 API
```

当前运行范围为 Vue 3 + FastAPI + 规则评分模型 + SQLite 事件档案/会话记忆/复盘历史 + LangChain/DeepSeek AI 服务。SQLite 运行时文件是本地 Demo 存储，不包含账号体系、云端同步或多用户隔离。

### 前端目标模块

| 模块 | 当前状态 | 说明 |
| --- | --- | --- |
| 首页模块 | 已实现 | 展示作品名称、核心定位、流程入口和运行增强功能入口 |
| 事件记录模块 | 已实现 | 收集事件日期、类型、频率、严重程度、多情绪、沟通状态、冲突状态和描述 |
| 事件档案模块 | V3 已实现 | 展示已保存事件、单条压力快照、删除入口，并可跳转总压力分析 |
| 压力分析模块 | V4 已实现 | 展示基于事件档案的宿舍总压力、周期趋势、主要压力来源、情绪分布、事件洞察、推荐场景训练、AI 心晴见解和建议 |
| AI 沟通演练模块 | V4 已实现 | `/rehearsal` 下包含场景训练和自定义演练；自定义演练保留场景选择/自定义、舍友画像、事件档案上下文、流式多轮回复、对话缓存和会话失效一键重开 |
| 复盘报告模块 | V4 已实现 | 展示复盘来源、表达总结、表现评分、原话 vs 推荐话术、沟通计划、复盘历史、对话记录弹窗、Markdown 导出和按来源再次演练 |

### 后端模块

| 模块 | 当前状态 | 说明 |
| --- | --- | --- |
| API 接口层 | V4 已实现 | 已提供健康检查、单事件分析、事件档案、周期总压力分析、训练目录、AI 心晴见解、沟通演练、流式演练、复盘和复盘历史接口；前端已配置本地 Vite 代理，后端已支持本地 CORS |
| 压力评分模块 | 第一阶段已实现 | 根据规则模型计算压力值和风险等级 |
| 安全边界模块 | 第一阶段已实现基础提示 | 对压力分析输出加入非诊断性提示和求助建议 |
| 事件档案存储模块 | V3 已实现 | 使用本地 SQLite 保存演示事件，默认路径为 `backend/.runtime/dorm_harmony.sqlite3`，可通过 `DORM_HARMONY_SQLITE_PATH` 覆盖；首次启动会尝试导入旧 JSON 档案 |
| LangChain 模块 | V3 已实现 | 管理提示词模板、动态舍友画像、事件档案摘要、LangGraph SQLite 会话记忆和 AI 调用流程 |
| AI 服务模块 | V3 已实现 | 调用 DeepSeek `deepseek-v4-flash` 生成多角色回复、复盘建议、沟通计划和事件档案心晴见解，缺少本地 API Key 时返回 `503` |
| 复盘历史模块 | V4 已实现 | 使用 SQLite 保存每次真实复盘报告，并从请求快照持久化场景训练/自定义演练来源元信息，提供历史列表和详情接口 |

## 推荐接口设计

| 接口 | 方法 | 功能 |
| --- | --- | --- |
| `/health` | GET | 检查后端服务是否可访问 |
| `/api/analyze` | POST | 接收宿舍事件记录，返回压力值、风险等级和建议 |
| `/api/events` | POST | 保存一条事件档案记录，并同步生成单条压力快照 |
| `/api/events` | GET | 获取当前本地 SQLite 事件档案 |
| `/api/events/{id}` | DELETE | 删除一条事件档案记录 |
| `/api/events/analysis` | GET | 基于事件档案当前周期返回宿舍总压力分析，支持 `range_days=7/15/30/90`，默认 30 |
| `/api/training/catalog` | GET | 返回 V4 固定场景训练分类、具体场景、目标、难度和推荐开场白目录 |
| `/api/events/insight` | POST | 基于事件档案当前周期和同周期总压力分析生成 AI 心晴见解，支持 `range_days=7/15/30/90`，默认 30；当前周期无事件返回 `400` |
| `/api/simulate` | POST | 接收用户话术、场景、舍友画像和可选事件档案上下文，返回 AI 舍友回复 |
| `/api/simulate/stream` | POST | 以 NDJSON 输出模拟开始、回复和最终结果事件 |
| `/api/review` | POST | 接收 `conversation_id` 或对话记录，返回沟通复盘报告并保存真实复盘历史 |
| `/api/reviews` | GET | 获取最近复盘报告摘要 |
| `/api/reviews/{review_id}` | GET | 获取单条复盘报告详情 |

完整字段契约见 [后端 API 契约](./docs/backend-api-contract.md)。

## 后端本地运行

后端命令根目录为 `backend/`，要求 Python >=3.11。

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

AI 接口需要配置。后端会通过 `python-dotenv` 自动读取仓库根目录 `.env`：

```env
DEEPSEEK_API_KEY=你的 DeepSeek API Key
DORM_HARMONY_LLM_BASE_URL=https://api.deepseek.com
DORM_HARMONY_LLM_MODEL=deepseek-v4-flash
DORM_HARMONY_LLM_TIMEOUT=20
DORM_HARMONY_SQLITE_PATH=.runtime/dorm_harmony.sqlite3
```

`.env` 必须放在仓库根目录，不要提交到仓库。真实环境变量优先级高于 `.env`。`OPENAI_API_KEY` 仅作为旧配置兼容 fallback。未配置任一 Key 时，`/api/simulate`、`/api/simulate/stream`、`/api/review` 和 `/api/events/insight` 会返回 `503`，不会返回模板伪结果。DeepSeek 官方 V4 Flash 的 API 模型名是 `deepseek-v4-flash`。

运行时数据默认保存在 `backend/.runtime/dorm_harmony.sqlite3`，其中包含事件档案、LangGraph 会话记忆和复盘历史。可用 `DORM_HARMONY_SQLITE_PATH` 指向其他 SQLite 文件；该变量按后端进程当前工作目录解析，如果按上面的命令从 `backend/` 目录启动后端，相对路径会按 `backend/` 解析。旧版 `DORM_HARMONY_EVENT_STORE_PATH` 仅用于首次迁移旧 JSON 事件档案，不再作为默认事件档案写入位置。

后端测试：

```bash
cd backend
pytest
```

本地完整流程开发时，先启动后端，再启动前端。前端 Vite 会把 `/api/*` 转发到 `http://127.0.0.1:8000`：

```bash
cd backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```bash
cd frontend
npm install
npm run dev
```

如果前端不走 Vite 代理而是跨端口直连后端，后端默认允许 `http://localhost:5173` 和 `http://127.0.0.1:5173`。如需调整：

```bash
export DORM_HARMONY_CORS_ORIGINS="http://localhost:3000,http://127.0.0.1:7357"
```

可用接口：

- `GET /health`
- `POST /api/analyze`
- `POST /api/events`
- `GET /api/events`
- `DELETE /api/events/{id}`
- `GET /api/events/analysis`
- `GET /api/training/catalog`
- `POST /api/events/insight`
- `POST /api/simulate`
- `POST /api/simulate/stream`
- `POST /api/review`
- `GET /api/reviews`
- `GET /api/reviews/{review_id}`

后端说明文档：

- [后端 API 契约](./docs/backend-api-contract.md)
- [压力评分模型](./docs/scoring-model.md)
- [第一阶段后端基础状态](./docs/phase1-status.md)
- [第二阶段后端 AI 状态](./docs/phase2-status.md)
- [第三阶段联调优化与开发收尾状态](./docs/phase3-status.md)

## 压力评分模型

压力值采用 0-100 分区间，评分结果仅用于宿舍关系压力趋势提示。

| 指标 | 权重 | 说明 |
| --- | --- | --- |
| 事件严重程度 | 30% | 事件对用户生活和情绪的影响程度 |
| 发生频率 | 25% | 同类问题是否反复出现 |
| 情绪强度 | 25% | 用户当前情绪的负面强度 |
| 沟通状态 | 10% | 是否已经进行过有效沟通 |
| 冲突升级情况 | 10% | 是否已经出现争吵、冷战或关系恶化 |

风险等级划分：

| 压力值 | 状态名称 | 说明 |
| --- | --- | --- |
| 0-30 | 关系平稳 | 当前压力较低，可继续保持日常沟通 |
| 31-60 | 存在压力 | 宿舍关系存在一定摩擦，建议及时沟通 |
| 61-80 | 冲突风险较高 | 问题可能正在积累，建议先进行沟通演练 |
| 81-100 | 高压力状态 | 建议优先寻求现实支持，如辅导员、心理老师或可信任同学 |

## AI 沟通演练与复盘

以下内容为 AI 已实现能力：`/api/simulate`、`/api/simulate/stream`、`/api/review` 和 `/api/events/insight` 通过 LangChain 调用 DeepSeek 官方 API，并返回便于前端展示的结构化数据。V4 已将前端入口升级为 AI 沟通演练，包含固定分步场景训练和自定义演练；复盘请求支持 `source_meta`，可在报告和历史中区分“场景训练”与“自定义演练”。

系统设定三个虚拟舍友角色：

| 角色 | 性格设定 | 典型反应 |
| --- | --- | --- |
| 舍友 A | 直接型，容易反驳 | “我也没多大声吧，你是不是太敏感了？” |
| 舍友 B | 回避型，不愿正面沟通 | “这个事情之后再说吧。” |
| 舍友 C | 调和型，愿意缓和关系 | “我们是不是可以一起定个规则？” |

AI 输出需要遵循以下原则：

- 固定场景：限定为大学宿舍关系沟通。
- 固定角色：保持舍友 A、B、C 的性格差异。
- 固定格式：返回便于前端解析的结构化数据。
- 非诊断性：不输出心理疾病判断，不评价舍友人格。
- 可操作性：建议必须具体、温和、可执行。
- 结构化响应的 `safety_note` 必须包含非诊断、非医学判断、非人格评价、不代表真实舍友想法，以及辅导员、心理老师或现实支持提示。

## V4 功能与当前限制

V4 已实现 AI 沟通演练总入口、固定场景训练、自定义演练保留、复盘来源元信息、7/15/30/90 天压力分析、主要压力来源、情绪分布、事件洞察和推荐场景训练。V2/V3 的事件档案、多情绪记录、自定义舍友、多轮流式模拟、事件档案 AI 心晴见解、复盘评分、复盘历史、报告导出和再练一次仍保留，详细说明见 [V2/V3 功能说明](./docs/v2-features.md)。

当前限制：

- 事件档案、会话记忆和复盘历史使用后端本地 SQLite 文件保存，默认路径为 `backend/.runtime/dorm_harmony.sqlite3`；适合本地 Demo，不提供账号体系、云端同步、多用户隔离、权限控制或云端备份。
- AI 会话记忆不再是内存态，后端重启后同一 SQLite 文件内的 `conversation_id` 可继续用于 continuation 和复盘；但切换 SQLite 文件、清理 `.runtime` 或使用不存在的旧 id 时，前端会进入“会话失效”固定错误态，并提供一键重新开始。
- 浏览器刷新后，前端会从 `localStorage` 恢复部分页面缓存和 `conversation_id`；真正的会话内容以 SQLite 为准。
- 未配置 `DEEPSEEK_API_KEY` 或兼容 `OPENAI_API_KEY` 时，真实 AI 接口返回 `503`；前端可能展示本地演示兜底，但不代表后端真实 AI 生成成功。

## 开发计划

本项目采用 6 天集中开发 + 第 7 天线上提交材料整理的安排。前 6 天专注网页 Demo 开发、联调和开发文档，第 7 天单独完成产品演示视频、宣传海报、创意与场景说明及线上提交材料检查。

| 阶段 | 时间 | 主要任务 | 阶段交付物 |
| --- | --- | --- | --- |
| 第一阶段：需求确认与基础搭建 | 第 1-2 天 | 明确 Demo 功能范围，设计核心接口字段和压力评分模型；搭建 FastAPI 后端基础结构、Vue 前端基础结构，并完成首页、事件记录页、压力分析页基础版 | 功能范围说明、接口字段草案、压力评分模型说明、后端基础结构、`/api/analyze` 初版、前端基础页面 |
| 第二阶段：核心功能开发 | 第 3-4 天 | 完善 `/api/analyze` 评分逻辑；设计多角色 Prompt；实现 `/api/simulate` 和 `/api/review`；完成 AI 沟通演练基础页面、聊天展示和复盘报告页面 | 压力分析接口完整版、多角色 Prompt、核心接口、AI 沟通演练基础页面、沟通复盘报告页面、前后端对接初版 |
| 第三阶段：联调优化与开发收尾 | 第 5-6 天 | 完成前后端联调，修复主要问题；优化 UI 与响应式展示；跑通完整 Demo，并整理截图和开发说明 | 可完整演示的网页 Demo、联调记录、问题修复记录、最终策划文档、页面截图素材；当前已完成前后端核心页面与接口联调准备 |
| V2/V3 运行增强 | 追加迭代 | 实现事件档案、总压力分析、多情绪、自定义舍友、多轮流式模拟、复盘评分和复盘产品化 | SQLite 事件档案、`/archive` 页面、总压力分析页、趋势图、AI 心晴见解、动态舍友画像、SQLite 会话记忆、复盘历史、复盘导出、沟通计划和再练一次 |
| V4 演练与分析升级 | 追加迭代 | 升级 AI 沟通演练入口、固定场景训练、复盘来源元信息和压力分析页 V4 数据模块 | `/rehearsal`、`/rehearsal/scenario`、`/rehearsal/custom`、周期压力趋势、情绪分布、事件洞察、推荐场景训练、复盘来源展示 |
| 线上提交材料整理 | 第 7 天 | 整理线上提交材料；完成策划文档最终版、产品演示视频、宣传海报、创意与场景说明，并检查文件命名和提交完整性 | 作品策划文档最终版、3 分钟内产品演示视频、宣传海报、500 字以内创意与场景说明、线上提交材料包 |

更详细的任务拆分见 [DEVELOPMENT_PLAN_AND_DELIVERABLES.md](./DEVELOPMENT_PLAN_AND_DELIVERABLES.md)。

## 团队分工

| 成员 | 角色定位 | 主要任务 |
| --- | --- | --- |
| 朱春雯 | 组长、策划文档负责人、后端与 AI 负责人 | 项目统筹、策划文档主笔、FastAPI 后端、压力评分模型、LangChain/DeepSeek 后端 AI 接口、接口设计、安全边界说明 |
| 曹乐 | 前端与展示负责人 | Vue 前端开发、页面原型、UI 设计、图表展示、聊天界面、页面截图、宣传海报、演示视频 |

## 目标线上交付物

| 交付物 | 内容要求 | 负责人 |
| --- | --- | --- |
| 作品策划文档 | 涵盖需求痛点、详细功能介绍、技术方案、开发计划、安全边界 | 朱春雯 |
| 网页 Demo | 可演示事件记录、事件档案、宿舍总压力分析、AI 沟通演练、沟通复盘报告；真实 AI 结果需要前端运行环境与 AI Key 配合验收 | 朱春雯 + 曹乐 |
| 产品演示视频 | 不超过 3 分钟，展示产品功能和操作流程 | 曹乐 |
| 宣传海报 | 展示作品名称、核心痛点、主要功能、操作流程、应用价值 | 曹乐 |
| 创意与场景说明 | 500 字以内，说明作品创意、使用场景和价值 | 朱春雯 |
| 页面截图素材 | 首页、记录页、分析页、模拟页、报告页截图 | 曹乐 |

## 安全与伦理边界

- 本项目不进行心理疾病诊断。
- 本项目不判断用户或舍友是否存在心理问题。
- 系统不输出“某位舍友有问题”“某位舍友心理异常”等人格评价。
- 压力值仅用于宿舍关系压力趋势提示，不作为医学或心理诊断依据。
- 当压力值较高，或用户描述中出现严重冲突、持续失眠、强烈焦虑、暴力风险等情况时，系统应提示用户及时联系辅导员、心理老师、家人或可信任的现实支持资源。
- Demo 阶段不采集真实身份信息，演示数据使用虚拟样例。

## 相关文档

- [开发计划与线上交付物](./DEVELOPMENT_PLAN_AND_DELIVERABLES.md)
- [Git Commit 提交信息规范](./GIT_COMMIT_GUIDELINES.md)
- [后端 API 契约](./docs/backend-api-contract.md)
- [V2/V3 功能说明](./docs/v2-features.md)
- [压力评分模型](./docs/scoring-model.md)
- [第一阶段后端基础状态](./docs/phase1-status.md)
- [第二阶段后端 AI 状态](./docs/phase2-status.md)
- [第三阶段联调优化与开发收尾状态](./docs/phase3-status.md)
