# 后端 API 契约

本文档记录当前后端已实现接口。运行时 AI 接口已接入 FastAPI + LangChain + DeepSeek 服务层，已提供健康检查、压力分析、SQLite 事件档案、沟通模拟、沟通复盘、复盘历史和事件档案 AI 心晴见解接口；第三阶段之后已补充本地 Vite 代理、FastAPI CORS、LangGraph SQLite 会话记忆、真实流式模拟接入和复盘字段兼容。

## 安全边界

- 本项目输出仅用于宿舍关系压力趋势提示和沟通训练建议。
- 系统不进行心理疾病诊断、医学判断或人格评价。
- 当用户描述中出现高压力、暴力风险、严重失眠等情况时，返回内容应提示用户寻求辅导员、心理老师、家人或可信任同学等现实支持。

## 本地联调约定

本地开发推荐启动后端在 `http://127.0.0.1:8000`，前端 Vite 开发服务器通过 `/api` 代理访问后端。执行以下命令前，请先按 `README.md` 安装后端依赖并准备 Python 环境：

```bash
cd backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```bash
cd frontend
npm install
npm run dev
```

后端默认允许以下本地前端 origin：

- `http://localhost:5173`
- `http://127.0.0.1:5173`

如需覆盖本地 CORS 允许列表：

```bash
export DORM_HARMONY_CORS_ORIGINS="http://localhost:3000,http://127.0.0.1:7357"
```

运行时数据默认保存在 `backend/.runtime/dorm_harmony.sqlite3`，可通过 `DORM_HARMONY_SQLITE_PATH` 覆盖。该变量按后端进程当前工作目录解析。该 SQLite 文件包含事件档案、LangGraph 会话记忆和复盘历史。旧版 `DORM_HARMONY_EVENT_STORE_PATH` 仅用于首次导入旧 JSON 事件档案。

## 已实现接口

### GET /health

用途：检查 FastAPI 服务是否可访问。

响应示例：

```json
{
  "status": "ok"
}
```

### POST /api/analyze

用途：接收宿舍事件记录，返回压力评分、风险等级、主要来源、趋势提示和沟通建议。

请求字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `event_type` | string | 事件类型：`noise`、`schedule`、`hygiene`、`cost`、`privacy`、`emotion` |
| `severity` | number | 严重程度，整数 1-5 |
| `frequency` | string | 发生频率：`occasional`、`weekly_multiple`、`daily` |
| `emotion` | string | 当前主情绪，兼容旧字段：`irritable`、`anxious`、`wronged`、`angry`、`helpless`、`depressed` |
| `emotions` | string[] | 可选，多情绪选择，最多 6 项；不传时由 `emotion` 或 `primary_emotion` 补齐 |
| `primary_emotion` | string | 可选，主情绪；如果同时传 `emotion`，两者必须一致，且必须包含在 `emotions` 中 |
| `has_communicated` | boolean | 是否已经沟通过 |
| `has_conflict` | boolean | 是否已经出现争吵、冷战或关系恶化 |
| `description` | string | 事件描述，去除首尾空白后不能为空，最长 500 字符 |

请求示例：

```json
{
  "event_type": "noise",
  "severity": 4,
  "frequency": "weekly_multiple",
  "emotion": "anxious",
  "emotions": [
    "anxious",
    "wronged"
  ],
  "primary_emotion": "anxious",
  "has_communicated": false,
  "has_conflict": true,
  "description": "舍友晚上打游戏声音很大，影响睡眠。"
}
```

响应字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `pressure_score` | number | 0-100 压力值 |
| `risk_level` | string | 风险等级代码：`stable`、`pressure`、`high`、`severe` |
| `risk_label` | string | 风险等级中文标签 |
| `main_sources` | string[] | 主要压力来源 |
| `emotion_keywords` | string[] | 当前情绪关键词 |
| `trend_message` | string | 冲突风险趋势提示 |
| `suggestion` | string | 沟通建议 |
| `recommend_simulation` | boolean | 是否建议进入沟通演练 |
| `disclaimer` | string | 非诊断性安全提示 |

响应示例：

```json
{
  "pressure_score": 76,
  "risk_level": "high",
  "risk_label": "冲突风险较高",
  "main_sources": [
    "噪音冲突",
    "发生频率较高",
    "尚未有效沟通",
    "已出现争吵或冷战"
  ],
  "emotion_keywords": [
    "焦虑"
  ],
  "trend_message": "当前压力值为 76，处于“冲突风险较高”状态。问题可能正在积累，建议先练习表达方式，再选择合适时机沟通。",
  "suggestion": "建议先进行沟通演练，练习表达方式，再选择双方情绪相对平稳的时间进行现实沟通。",
  "recommend_simulation": true,
  "disclaimer": "本结果仅用于宿舍关系压力趋势提示，不作为心理诊断依据、医学诊断或人格评价依据。如压力持续升高或出现暴力风险、严重失眠等情况，请及时联系辅导员、心理老师、家人或可信任同学。"
}
```

## V3 事件档案接口

### POST /api/events

状态：已实现。保存一条事件档案记录到 SQLite，后端同步调用 `analyze_pressure()` 生成单条事件压力快照。

请求字段：继承 `POST /api/analyze` 全部字段，并增加：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `event_date` | string | 事件发生日期，格式 `YYYY-MM-DD`，不能是未来日期 |

请求示例：

```json
{
  "event_date": "2026-05-15",
  "event_type": "noise",
  "severity": 4,
  "frequency": "weekly_multiple",
  "emotion": "anxious",
  "emotions": [
    "anxious",
    "wronged"
  ],
  "primary_emotion": "anxious",
  "has_communicated": false,
  "has_conflict": true,
  "description": "舍友晚上打游戏声音很大，影响睡眠。"
}
```

响应字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | 后端生成的事件 id |
| `created_at` | string | 后端创建时间，ISO datetime |
| `event_date` | string | 事件发生日期 |
| `event_type` / `severity` / `frequency` / `emotion` / `emotions` / `primary_emotion` / `has_communicated` / `has_conflict` / `description` | mixed | 与请求字段一致，已完成校验和归一化 |
| `single_analysis` | object | 单条事件压力分析，字段同 `AnalyzeResponse` |

### GET /api/events

状态：已实现。返回当前本地 SQLite 事件档案，不调用 AI 服务。

响应字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `events` | object[] | 事件列表，按 `event_date desc, created_at desc` 排序 |

响应示例：

```json
{
  "events": [
    {
      "id": "event-id",
      "event_date": "2026-05-15",
      "event_type": "noise",
      "severity": 4,
      "frequency": "weekly_multiple",
      "emotion": "anxious",
      "emotions": [
        "anxious",
        "wronged"
      ],
      "primary_emotion": "anxious",
      "has_communicated": false,
      "has_conflict": true,
      "description": "舍友晚上打游戏声音很大，影响睡眠。",
      "created_at": "2026-05-15T12:00:00Z",
      "single_analysis": {
        "pressure_score": 76,
        "risk_level": "high",
        "risk_label": "冲突风险较高",
        "main_sources": [
          "噪音冲突",
          "发生频率较高",
          "尚未有效沟通",
          "已出现争吵或冷战"
        ],
        "emotion_keywords": [
          "焦虑"
        ],
        "trend_message": "当前压力值为 76，处于“冲突风险较高”状态。问题可能正在积累，建议先练习表达方式，再选择合适时机沟通。",
        "suggestion": "建议先进行沟通演练，练习表达方式，再选择双方情绪相对平稳的时间进行现实沟通。",
        "recommend_simulation": true,
        "disclaimer": "本结果仅用于宿舍关系压力趋势提示，不作为心理诊断依据、医学诊断或人格评价依据。如压力持续升高或出现暴力风险、严重失眠等情况，请及时联系辅导员、心理老师、家人或可信任同学。"
      }
    }
  ]
}
```

### DELETE /api/events/{id}

状态：已实现。删除一条事件档案记录；删除后前端应重新请求事件档案、总压力分析和 AI 心晴见解。

响应语义：

| 场景 | HTTP 状态码 | 说明 |
| --- | --- | --- |
| 删除成功 | `204` | 无响应体 |
| 事件不存在 | `404` | 返回 `事件档案不存在或已被删除。` |

### GET /api/events/analysis

状态：已实现。后端读取当前事件档案，并按当前评分模型重新计算总压力分析。

请求参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `range_days` | number | 否 | 压力趋势、当前周期事件数、情绪分布、事件洞察和训练推荐使用的周期天数；仅支持 `7`、`15`、`30`、`90`，默认 `30` |

错误语义：

| 场景 | HTTP 状态码 | 说明 |
| --- | --- | --- |
| `range_days` 不在支持范围内 | `422` | 返回 `range_days must be one of 7, 15, 30, 90` |

响应字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `pressure_score` | number | 0-100 总压力值 |
| `risk_level` | string | 风险等级代码：`stable`、`pressure`、`high`、`severe` |
| `risk_label` | string | 风险等级中文标签 |
| `main_sources` | string[] | 主要压力来源，来自 `source_breakdown[].label` |
| `emotion_keywords` | string[] | 当前情绪关键词 |
| `trend_message` | string | 事件档案压力趋势提示 |
| `suggestion` | string | 下一步沟通或求助建议 |
| `recommend_simulation` | boolean | 是否建议进入沟通演练 |
| `disclaimer` | string | 非诊断性安全提示 |
| `event_count` | number | 事件档案总条数 |
| `active_30d_count` | number | 近 30 天事件数 |
| `source_breakdown` | object[] | 按用户记录的 `event_type` 聚合后的压力贡献占比 |
| `source_breakdown[].label` | string | 事件类型中文标签：噪音冲突、作息冲突、卫生冲突、费用冲突、隐私边界、情绪冲突 |
| `source_breakdown[].percent` | number | 该事件类型贡献占比，返回项合计为 100 |
| `source_breakdown[].contribution` | number | 该事件类型的压力贡献，按 `analyze_pressure(event).pressure_score * recency_weight` 聚合 |
| `period_days` | number | 当前周期天数，对应请求的 `range_days` |
| `active_period_count` | number | 当前周期内事件数；切换 `range_days` 时该字段会随周期变化 |
| `trend_points` | object[] | 当前周期内按日期聚合的压力趋势点；无数据时为空数组 |
| `trend_points[].date` | string | 趋势点日期，格式为 `YYYY-MM-DD` |
| `trend_points[].pressure_score` | number | 当天事件压力分均值，0-100；同日多事件按当前评分模型重算后取平均 |
| `trend_points[].event_count` | number | 当天事件数量 |
| `trend_explanation` | string | 根据当前周期趋势点生成的解释；0 或 1 个点时会提示记录不足 |
| `source_insights` | object[] | 压力来源的排名、占比和解释，来源于 `source_breakdown` |
| `source_insights[].rank` | number | 压力来源排名，从 1 开始 |
| `source_insights[].label` | string | 压力来源中文标签 |
| `source_insights[].percent` | number | 该来源贡献占比 |
| `source_insights[].contribution` | number | 该来源压力贡献值 |
| `source_insights[].event_count` | number | 该来源在档案中的事件数量 |
| `source_insights[].recent_event_date` | string/null | 该来源最近一次事件日期，格式为 `YYYY-MM-DD` |
| `source_insights[].explanation` | string | 来源占比、事件数和最近日期的客观解释 |
| `main_source_conclusion` | string | 主要压力来源结论 |
| `emotion_distribution` | object[] | 当前周期内情绪分布，按出现次数降序；无数据时为空数组 |
| `emotion_distribution[].emotion` | string | 情绪代码：`irritable`、`anxious`、`wronged`、`angry`、`helpless`、`depressed` |
| `emotion_distribution[].label` | string | 情绪中文标签 |
| `emotion_distribution[].count` | number | 当前周期内该情绪出现次数；单条事件内重复情绪去重 |
| `emotion_distribution[].percent` | number | 当前周期内该情绪占比，返回项合计为 100 |
| `event_insight` | object/null | 当前周期内事件事实摘要；周期内无事件时为 `null` |
| `event_insight.period_days` | number | 摘要对应周期天数 |
| `event_insight.period_event_count` | number | 摘要对应周期内事件数 |
| `event_insight.top_emotions` | string[] | 当前周期内出现较多的情绪中文标签，最多 3 项 |
| `event_insight.top_event_types` | string[] | 当前周期内出现较多的事件类型中文标签，最多 3 项 |
| `event_insight.communicated_count` | number | 当前周期内已沟通事件数 |
| `event_insight.uncommunicated_count` | number | 当前周期内未沟通事件数 |
| `event_insight.conflict_count` | number | 当前周期内已出现直接冲突的事件数 |
| `event_insight.summary` | string | 只基于事件事实的客观摘要，不做心理诊断、医学判断或人格评价 |
| `training_recommendation` | object/null | 基于当前周期事件和总压力分析生成的固定场景训练推荐；周期内无事件时为 `null` |
| `training_recommendation.category_id` | string | 推荐训练分类 id |
| `training_recommendation.category_label` | string | 推荐训练分类中文标签 |
| `training_recommendation.scenario_id` | string | 推荐具体场景 id |
| `training_recommendation.scenario_title` | string | 推荐具体场景标题 |
| `training_recommendation.target_id` | string | 推荐训练目标 id |
| `training_recommendation.target_label` | string | 推荐训练目标中文标签 |
| `training_recommendation.difficulty_id` | string | 推荐训练难度 id |
| `training_recommendation.difficulty_label` | string | 推荐训练难度中文标签 |
| `training_recommendation.difficulty_description` | string | 推荐训练难度说明 |
| `training_recommendation.reason` | string | 推荐原因，基于主要来源、周期事件数和风险等级 |
| `training_recommendation.opening_suggestion` | string | 推荐开场白，可由前端直接带入场景训练 |
| `training_recommendation.safety_note` | string | 非诊断性边界和现实支持提示；高压力状态会强调辅导员、宿管、心理老师等现实支持 |

说明：

- `pressure_score`、`risk_level`、`risk_label`、`main_sources`、`source_breakdown` 和 `active_30d_count` 保持全档案/近 30 天兼容口径；切换 `range_days` 不会让左侧总压力指数按周期跳变。
- `active_period_count`、`trend_points`、`emotion_distribution`、`event_insight` 和 `training_recommendation` 使用当前 `range_days` 周期。
- 档案汇总和趋势点都按当前评分模型调用 `analyze_pressure(event)` 重算；`EventRecord.single_analysis` 只作为事件创建时的快照保留。
- `发生频率较高`、`尚未有效沟通`、`已出现争吵或冷战` 仍会通过单条事件压力分影响贡献值，但不会作为 `source_breakdown` 的独立类别返回。

## AI 与 V3 模拟/复盘接口

以下内容为当前已实现 AI 接口。`/api/simulate`、`/api/simulate/stream`、`/api/events/insight` 与 `/api/review` 运行时通过 LangChain 调用 DeepSeek 官方 OpenAI 兼容 API，并返回便于前端展示的结构化响应。模拟与复盘可通过 LangGraph SQLite 会话记忆读取同一 `conversation_id` 的历史对话。

### POST /api/simulate

状态：已实现，V3 已扩展为动态舍友画像、事件档案上下文、LangGraph SQLite 会话记忆和多轮模拟。运行时通过 LangChain 调用 DeepSeek `deepseek-v4-flash`；缺少 `DEEPSEEK_API_KEY` 且没有兼容的 `OPENAI_API_KEY` 时返回 `503`。

请求字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `conversation_id` | string | 可选，后端 SQLite 会话 id；继续已有会话时传入 |
| `turn_id` | string | 可选，前端生成的用户回合 id，用于同一轮模拟的上下文提示 |
| `scenario` | string | 宿舍沟通场景，最长 300 字符 |
| `user_message` | string | 用户准备表达的话术，最长 500 字符；`is_continuation=false` 时必填 |
| `risk_level` | string | 可选，来自 `/api/analyze` 的风险等级，枚举为 `stable` / `pressure` / `high` / `severe` |
| `context` | string | 可选，补充背景，最长 500 字符 |
| `dialogue` | object[] | 可选，历史对话，最多 20 条；为空或不传时按单轮模拟处理 |
| `dialogue[].speaker` | string | 发言者，枚举为 `user` / `system` / 任意 `roommate_*` id；兼容前端中文展示名 |
| `dialogue[].message` | string | 单条对话内容，最长 500 字符 |
| `roommates` | object[] | 可选，1-5 位舍友画像；不传时使用默认三位舍友 |
| `roommates[].id` | string | 舍友 id，必须以 `roommate_` 开头，且在本次请求内唯一 |
| `roommates[].name` | string | 展示名，1-20 字符 |
| `roommates[].personality_tag` | string | 性格标签，1-20 字符 |
| `roommates[].tag_mode` | string | `preset` 或 `custom` |
| `roommates[].preset_key` | string | `tag_mode=preset` 时必填，枚举 `direct` / `avoidant` / `harmony` |
| `roommates[].traits` | object | `tag_mode=custom` 时必填，包含 6 个 0-5 数值属性 |
| `roommates[].avatar` | string | 可选头像 key：`nailong`、`capybara_lulu`、`baobaolong`、`patrick`、`spongebob`；同次请求内不可重复 |
| `use_event_archive` | boolean | 可选，是否让后端读取事件档案摘要作为模拟上下文 |
| `is_continuation` | boolean | 可选，是否为同一 `conversation_id` 下的 continuation 请求；为 `true` 时必须传 `conversation_id`，且允许没有 `user_message` |
| `max_replies` | number | 可选，本次最多返回回复条数，0-15 |

响应字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `conversation_id` | string | 后端返回的 SQLite 会话 id，复盘可继续使用 |
| `replies` | object[] | 虚拟舍友回复，最多 15 条 |
| `replies[].roommate_id` | string | 对应 `roommates[].id` |
| `replies[].roommate` | string | 舍友展示名 |
| `replies[].personality` | string | 舍友性格标签 |
| `replies[].message` | string | 回复内容，最长 500 字符 |
| `archive_context_used` | boolean | 本次是否实际接入事件档案摘要 |
| `archive_context_summary` | string | 可选，后端传入 AI 的受控事件档案摘要，最长 500 字符 |
| `safety_note` | string | 非诊断性安全提示 |

请求示例：

```json
{
  "scenario": "舍友晚上打游戏声音较大，影响睡眠",
  "user_message": "我想和你商量一下，晚上能不能把游戏声音调小一点，我最近睡眠受影响比较明显。",
  "risk_level": "high",
  "context": "用户尚未正式沟通过，但已经因为噪音问题感到焦虑。",
  "use_event_archive": true,
  "max_replies": 3,
  "roommates": [
    {
      "id": "roommate_a",
      "name": "舍友 A",
      "personality_tag": "直接型",
      "tag_mode": "preset",
      "preset_key": "direct",
      "avatar": "nailong"
    },
    {
      "id": "roommate_b",
      "name": "舍友 B",
      "personality_tag": "回避型",
      "tag_mode": "preset",
      "preset_key": "avoidant",
      "avatar": "capybara_lulu"
    },
    {
      "id": "roommate_c",
      "name": "舍友 C",
      "personality_tag": "调和型",
      "tag_mode": "preset",
      "preset_key": "harmony",
      "avatar": "baobaolong"
    }
  ],
  "dialogue": [
    {
      "speaker": "user",
      "message": "晚上能不能小声一点？"
    },
    {
      "speaker": "roommate_a",
      "message": "我也没开很大声吧。"
    }
  ]
}
```

连续对话语义：当 `dialogue` 非空时，后端会把本次 `user_message` 视为同一场景下的下一轮对话，提示 AI 不要重启场景，也不要重复上一轮已经说过的内容。

响应示例：

```json
{
  "conversation_id": "conversation-1",
  "replies": [
    {
      "roommate_id": "roommate_a",
      "roommate": "舍友 A",
      "personality": "直接型",
      "message": "我也没开很大声吧，不过如果真的影响你了，我可以试着戴耳机。"
    },
    {
      "roommate_id": "roommate_b",
      "roommate": "舍友 B",
      "personality": "回避型",
      "message": "这个事情之后再说吧，我现在不太想聊。"
    },
    {
      "roommate_id": "roommate_c",
      "roommate": "舍友 C",
      "personality": "调和型",
      "message": "我们可以一起定个休息时间规则，尽量别互相影响。"
    }
  ],
  "archive_context_used": true,
  "archive_context_summary": "事件档案：总事件 2 条，近 30 天 2 条；主要压力来源：噪音冲突；风险：high/冲突风险较高；最近事件：noise，严重程度 4，主要情绪 焦虑，情绪 焦虑、委屈，未沟通，有冲突，描述：舍友晚上打游戏声音很大，影响睡眠。",
  "safety_note": "本回复仅用于宿舍沟通演练，不代表真实舍友想法，不进行心理诊断，不进行医学判断，不进行人格评价。如沟通压力持续升高或出现现实安全风险，请联系辅导员、心理老师或其他现实支持。"
}
```

### POST /api/simulate/stream

状态：已实现，并已由前端模拟页接入。在保留 `/api/simulate` 完整 JSON 契约的基础上输出 `start`、若干 `reply` 和 `final` 事件。后端仍先生成并校验完整 `SimulateResponse`，避免输出半截结构化错误。

请求字段：与 `POST /api/simulate` 完全一致，包括可选 `conversation_id`、`roommates`、`use_event_archive`、`is_continuation`、`max_replies` 和 `dialogue` 字段。

响应格式：`application/x-ndjson`，每行一个 JSON object。

事件顺序：

```json
{"type":"start","conversation_id":"conversation-1"}
{"type":"reply","reply":{"roommate_id":"roommate_a","roommate":"舍友 A","personality":"直接型","message":"我也没开很大声吧，不过如果真的影响你了，我可以试着戴耳机。"}}
{"type":"reply","reply":{"roommate_id":"roommate_b","roommate":"舍友 B","personality":"回避型","message":"这个事情之后再说吧，我现在不太想聊。"}}
{"type":"final","response":{"conversation_id":"conversation-1","replies":[{"roommate_id":"roommate_a","roommate":"舍友 A","personality":"直接型","message":"我也没开很大声吧，不过如果真的影响你了，我可以试着戴耳机。"},{"roommate_id":"roommate_b","roommate":"舍友 B","personality":"回避型","message":"这个事情之后再说吧，我现在不太想聊。"}],"archive_context_used":true,"archive_context_summary":"事件档案：总事件 2 条，近 30 天 2 条；主要压力来源：噪音冲突。","safety_note":"本回复仅用于宿舍沟通演练，不代表真实舍友想法，不进行心理诊断，不进行医学判断，不进行人格评价。如沟通压力持续升高或出现现实安全风险，请联系辅导员、心理老师或其他现实支持。"}}
```

错误语义：配置缺失仍返回 `503`；缺失或失效的 `conversation_id` 返回 `400`；LangChain / DeepSeek 调用失败或 AI 输出结构异常仍返回 `502`。这些错误会在流开始前以普通 HTTP 错误返回，不会输出半截 NDJSON。

### POST /api/events/insight

状态：已实现。基于当前事件档案和 `/api/events/analysis` 的总压力分析调用 DeepSeek `deepseek-v4-flash`，生成结构化 AI 心晴见解。

请求字段：无请求体。后端从当前事件档案读取已记录事件，并在服务端重新计算总压力分析。

响应字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `insight` | string | 基于事件档案的心晴见解，不能为空 |
| `care_suggestion` | string | 照顾情绪、睡眠和现实安全的建议，不能为空 |
| `communication_focus` | string[] | 下一次沟通最需要聚焦的事项，至少 1 条，每条不能为空 |
| `safety_note` | string | 非诊断性安全提示，必须包含“不代表真实舍友想法”“不进行心理诊断/心理疾病诊断”“不进行医学判断”“不进行人格评价”和现实支持提示 |

响应示例：

```json
{
  "insight": "近 30 天记录的事件主要集中在夜间噪音，当前压力更多来自休息边界被持续打断。",
  "care_suggestion": "建议先保证睡眠和情绪恢复，再选择白天情绪稳定时提出 11 点后的安静规则。",
  "communication_focus": [
    "明确 11 点后的耳机或低音量规则",
    "用具体影响表达需求，避免直接评价对方"
  ],
  "safety_note": "本建议仅用于沟通训练建议，不代表真实舍友想法，不进行心理诊断，不进行医学判断，不进行人格评价。如压力持续升高，请联系辅导员或心理老师寻求现实支持。"
}
```

错误语义：

| 场景 | HTTP 状态码 | 说明 |
| --- | --- | --- |
| 当前没有事件档案 | `400` | 返回 `请先记录至少一条事件后再生成 AI 心晴见解。` |
| 未配置 `DEEPSEEK_API_KEY` 或兼容的 `OPENAI_API_KEY` | `503` | AI 服务未配置，不返回模板伪结果 |
| LangChain / DeepSeek 调用失败 | `502` | 上游模型调用失败 |
| AI 输出结构异常或 `safety_note` 不符合安全边界 | `502` | 模型输出无法解析为 `ArchiveInsightResponse`，或安全提示缺少必要边界 |

### POST /api/review

状态：已实现，V3 已扩展为支持 `conversation_id` 复盘、多条话术改写建议、沟通计划和复盘历史保存。运行时通过 LangChain 调用 DeepSeek `deepseek-v4-flash`；缺少 `DEEPSEEK_API_KEY` 且没有兼容的 `OPENAI_API_KEY` 时返回 `503`。

请求字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `conversation_id` | string | 可选，优先从后端 SQLite 会话记忆读取模拟对话；不传时使用 `dialogue` |
| `scenario` | string | 沟通场景，最长 300 字符 |
| `dialogue` | object[] | 用户与虚拟舍友的对话记录，最多 50 条；未传 `conversation_id` 时需要提供有效对话 |
| `dialogue[].speaker` | string | 发言者，枚举为 `user` / `system` / 任意 `roommate_*` id；兼容前端中文展示名 |
| `dialogue[].message` | string | 单条对话内容，最长 500 字符 |
| `original_event` | object | 可选，受控原始事件摘要；只允许 `event_type`、`severity`、`frequency`、`emotion`、`emotions`、`primary_emotion`、`has_communicated`、`has_conflict`、`pressure_score`、`risk_level`、`risk_label`、`description`，禁止提交任意大 JSON 或未授权字段 |

第三阶段兼容说明：

- 标准契约以 `user`、`system` 和 `roommate_*` 为准；默认三位舍友仍使用 `roommate_a`、`roommate_b`、`roommate_c`。
- 为兼容当前前端复盘页展示文本，后端会在校验前把 `你`、`用户`、`我` 归一化为 `user`，把 `舍友 A` / `舍友A` / `舍友 A（直接型）` 等归一化为 `roommate_a`，`舍友 B` 系列归一化为 `roommate_b`，`舍友 C` 系列归一化为 `roommate_c`，`系统` 归一化为 `system`。
- `original_event.event_type` 标准值仍为 `noise`、`schedule`、`hygiene`、`cost`、`privacy`、`emotion`。后端兼容 `noise_conflict`、`schedule_conflict`、`hygiene_conflict`、`expense_conflict`、`privacy_boundary`、`emotional_conflict` 等旧前端值。
- 分析页派生的 `risk-stable`、`risk-pressure`、`risk-high`、`risk-severe` 不作为真实事件类型传给 AI，会归一化为 `None`；未知 `risk-*` 值仍返回 `422`。
- `ReviewRequest`、`dialogue[]` 和 `original_event` 均拒绝未授权 extra 字段。

响应字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `summary` | string | 表达总结 |
| `strengths` | string[] | 表达优点 |
| `risks` | string[] | 潜在问题 |
| `performance_scores` | object | 表现总结评分 |
| `performance_scores.clarity` | number | 表达清晰度，0-100 整数 |
| `performance_scores.empathy` | number | 共情能力，0-100 整数 |
| `performance_scores.resolution` | number | 问题解决度，0-100 整数 |
| `rewrite_suggestions` | object[] | 多条话术改写建议，至少 1 条 |
| `rewrite_suggestions[].message_index` | number | 被改写的用户消息在对话中的索引 |
| `rewrite_suggestions[].original_message` | string | 原始用户话术 |
| `rewrite_suggestions[].issue` | string | 该话术的主要问题 |
| `rewrite_suggestions[].suggested_message` | string | 建议改写版本 |
| `rewrite_suggestions[].reason` | string | 改写原因 |
| `rewritten_message` | string | 优化话术 |
| `next_steps` | string[] | 后续行动建议 |
| `communication_plan` | object | 自动生成的沟通计划卡片 |
| `communication_plan.opening` | string | 开场白 |
| `communication_plan.specific_request` | string | 具体请求 |
| `communication_plan.fallback_plan` | string | 兜底方案 |
| `safety_note` | string | 非诊断性安全提示 |
| `is_demo` | boolean | 是否为本地演示兜底结果 |
| `demo_notice` | string | 演示兜底说明；真实 AI 成功时为空字符串 |

请求示例：

```json
{
  "scenario": "舍友晚上打游戏声音较大，影响睡眠",
  "conversation_id": "conversation-1",
  "dialogue": [
    {
      "speaker": "user",
      "message": "我想和你商量一下，晚上能不能把游戏声音调小一点，我最近睡眠受影响比较明显。"
    },
    {
      "speaker": "roommate_a",
      "message": "我也没开很大声吧，不过如果真的影响你了，我可以试着戴耳机。"
    }
  ],
  "original_event": {
    "event_type": "noise",
    "emotion": "anxious",
    "emotions": [
      "anxious",
      "wronged"
    ],
    "primary_emotion": "anxious",
    "risk_level": "high",
    "pressure_score": 76
  }
}
```

响应示例：

```json
{
  "summary": "用户表达了噪音对睡眠的影响，并使用了商量式语气，整体较温和。",
  "strengths": [
    "说明了具体影响，没有直接指责对方",
    "使用了请求和协商语气"
  ],
  "risks": [
    "可以进一步明确希望调整的时间范围",
    "如果对方回避，需要预留下一次沟通时间"
  ],
  "performance_scores": {
    "clarity": 82,
    "empathy": 76,
    "resolution": 71
  },
  "rewrite_suggestions": [
    {
      "message_index": 0,
      "original_message": "我想和你商量一下，晚上能不能把游戏声音调小一点，我最近睡眠受影响比较明显。",
      "issue": "可以进一步明确希望调整的时间范围。",
      "suggested_message": "我想和你商量一下，晚上 11 点后能不能戴耳机或调低音量？我最近睡眠受影响比较明显，也想一起找个不影响你娱乐的办法。",
      "reason": "把时间、需求和共同解决意图说清楚，减少被理解成指责的可能。"
    }
  ],
  "rewritten_message": "我想和你商量一下，晚上 11 点后能不能戴耳机或调低音量？我最近睡眠受影响比较明显，也想一起找个不影响你娱乐的办法。",
  "next_steps": [
    "选择双方情绪平稳的时间沟通",
    "提出具体可执行的休息时间规则",
    "如果多次沟通无效，可以寻求辅导员或宿舍管理员协助"
  ],
  "communication_plan": {
    "opening": "我想和你商量一个最近影响我睡眠的小问题。",
    "specific_request": "晚上 11 点后能不能戴耳机或把游戏声音调低？",
    "fallback_plan": "如果你那时还需要玩游戏，我们可以一起约一个安静时间，或先试一周再调整。"
  },
  "safety_note": "本复盘仅用于沟通训练建议，不代表真实舍友想法，不进行心理疾病诊断，不进行医学判断，不进行人格评价。如压力持续升高，请联系辅导员、心理老师或其他现实支持。",
  "is_demo": false,
  "demo_notice": ""
}
```

真实 `/api/review` 成功且 `is_demo=false` 时，后端会将报告写入 SQLite 复盘历史。若历史写入失败，接口仍返回本次复盘结果，并在后端日志记录持久化错误。

### GET /api/reviews

状态：已实现。返回最近复盘报告摘要，默认最多 20 条，`limit` 最大按 50 截断。

查询参数：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `limit` | number | 可选，最少 1，默认 20，超过 50 时按 50 处理 |

响应字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `reports` | object[] | 按 `created_at desc` 返回的复盘摘要 |
| `reports[].id` | string | 复盘报告 id |
| `reports[].created_at` | string | 创建时间，ISO datetime |
| `reports[].conversation_id` | string \| null | 关联模拟会话 id |
| `reports[].scenario` | string | 沟通场景 |
| `reports[].summary` | string | 复盘摘要 |
| `reports[].score_clarity` | number | 表达清晰度评分 |
| `reports[].score_empathy` | number | 共情能力评分 |
| `reports[].score_resolution` | number | 问题解决度评分 |

响应示例：

```json
{
  "reports": [
    {
      "id": "review-1",
      "created_at": "2026-05-22T08:00:00Z",
      "conversation_id": "conversation-1",
      "scenario": "舍友晚上打游戏声音较大，影响睡眠",
      "summary": "用户表达较温和，但需要更明确提出时间边界。",
      "score_clarity": 82,
      "score_empathy": 76,
      "score_resolution": 71
    }
  ]
}
```

### GET /api/reviews/{review_id}

状态：已实现。返回单条复盘报告详情，包含当次请求、响应和最多最近 50 条对话快照。

响应字段：继承 `GET /api/reviews` 单条摘要字段，并增加：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `request` | object | 当次 `/api/review` 请求快照 |
| `response` | object | 当次 `/api/review` 响应快照 |
| `dialogue` | object[] | 保存复盘时使用的对话快照，最多 50 条 |

错误语义：

| 场景 | HTTP 状态码 | 说明 |
| --- | --- | --- |
| 复盘历史不存在 | `404` | 返回 `复盘历史不存在或已被删除。` |

## 错误语义

| 场景 | HTTP 状态码 | 说明 |
| --- | --- | --- |
| 请求字段非法 | `422` | FastAPI / Pydantic 校验失败，返回字段级错误信息 |
| conversation memory 不存在 | `400` | `/api/simulate`、`/api/simulate/stream` 或 `/api/review` 传入旧 `conversation_id` 时，提示重新演练 |
| 当前没有事件档案 | `400` | `/api/events/insight` 在没有事件记录时返回 `请先记录至少一条事件后再生成 AI 心晴见解。` |
| 删除不存在事件 | `404` | `DELETE /api/events/{id}` 返回 `事件档案不存在或已被删除。` |
| 复盘历史不存在 | `404` | `GET /api/reviews/{review_id}` 返回 `复盘历史不存在或已被删除。` |
| 未配置 `DEEPSEEK_API_KEY` 或兼容的 `OPENAI_API_KEY` | `503` | AI 服务未配置，`/api/simulate`、`/api/simulate/stream`、`/api/review` 和 `/api/events/insight` 不返回模板伪结果 |
| LangChain / DeepSeek 调用失败 | `502` | 上游模型调用失败，后端返回 AI 服务调用失败语义 |
| AI 输出结构不符合契约或安全边界 | `502` | 模型输出无法解析为接口约定结构，或 `safety_note` 缺少必要安全边界，后端返回 AI 输出结构错误语义 |

注意：前端在无 `DEEPSEEK_API_KEY` 或兼容 `OPENAI_API_KEY` 时可能展示本地演示兜底，但后端真实接口语义仍是 `503`，不代表 AI 接口真实生成成功。

## 当前运行限制

- 事件档案、会话记忆和复盘历史使用后端本地 SQLite 文件保存，默认路径为 `backend/.runtime/dorm_harmony.sqlite3`；可用 `DORM_HARMONY_SQLITE_PATH` 覆盖。该存储适合本地 Demo，不提供账号体系、云端同步、多用户隔离、权限控制或云端备份能力。
- 会话记忆不再是单进程内存态，后端重启后同一 SQLite 文件内的 `conversation_id` 可继续用于 continuation 和复盘；切换 SQLite 文件、清空 `.runtime` 或传入不存在的旧 id 后，仍会返回 `400` 并提示重新演练。
- 浏览器刷新后前端可能恢复 `localStorage` 中的 `conversation_id`，但真实会话内容以 SQLite 为准。
- 本接口契约不包含真实用户身份、权限、后台管理或长期个人数据管理能力。
