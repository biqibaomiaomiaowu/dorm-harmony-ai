# 后端 API 契约

本文档记录当前后端已实现接口。运行时 AI 接口已接入 FastAPI + LangChain + DeepSeek 服务层，已提供健康检查、压力分析、事件档案、沟通模拟、沟通复盘和事件档案 AI 心晴见解接口；第三阶段已补充本地 Vite 代理、FastAPI CORS 和复盘字段兼容。

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
| `emotion` | string | 当前情绪：`irritable`、`anxious`、`wronged`、`angry`、`helpless`、`depressed` |
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

## v2 事件档案接口

### GET /api/events/analysis

状态：已实现。后端读取当前事件档案，并按当前评分模型重新计算总压力分析。

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

说明：`发生频率较高`、`尚未有效沟通`、`已出现争吵或冷战` 仍会通过单条事件压力分影响贡献值，但不会作为 `source_breakdown` 的独立类别返回。

## 第二阶段已实现 AI 接口

以下内容为第二阶段朱春雯后端 AI 已实现接口。`/api/simulate` 与 `/api/review` 运行时通过 LangChain 调用 DeepSeek 官方 OpenAI 兼容 API，并返回便于前端展示的结构化响应。

### POST /api/simulate

状态：第二阶段已实现。运行时通过 LangChain 调用 DeepSeek `deepseek-v4-flash`；缺少 `DEEPSEEK_API_KEY` 且没有兼容的 `OPENAI_API_KEY` 时返回 `503`。

请求字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `scenario` | string | 宿舍沟通场景，最长 300 字符 |
| `user_message` | string | 用户准备表达的话术，最长 500 字符 |
| `risk_level` | string | 可选，来自 `/api/analyze` 的风险等级，枚举为 `stable` / `pressure` / `high` / `severe` |
| `context` | string | 可选，补充背景，最长 500 字符 |
| `dialogue` | object[] | 可选，历史对话，最多 20 条；为空或不传时按单轮模拟处理 |
| `dialogue[].speaker` | string | 发言者，枚举为 `user` / `roommate_a` / `roommate_b` / `roommate_c` / `system` |
| `dialogue[].message` | string | 单条对话内容，最长 500 字符 |

响应字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `replies` | object[] | 多个虚拟舍友回复 |
| `safety_note` | string | 非诊断性安全提示 |

请求示例：

```json
{
  "scenario": "舍友晚上打游戏声音较大，影响睡眠",
  "user_message": "我想和你商量一下，晚上能不能把游戏声音调小一点，我最近睡眠受影响比较明显。",
  "risk_level": "high",
  "context": "用户尚未正式沟通过，但已经因为噪音问题感到焦虑。",
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
  "replies": [
    {
      "roommate": "舍友 A",
      "personality": "直接型",
      "message": "我也没开很大声吧，不过如果真的影响你了，我可以试着戴耳机。"
    },
    {
      "roommate": "舍友 B",
      "personality": "回避型",
      "message": "这个事情之后再说吧，我现在不太想聊。"
    },
    {
      "roommate": "舍友 C",
      "personality": "调和型",
      "message": "我们可以一起定个休息时间规则，尽量别互相影响。"
    }
  ],
  "safety_note": "本回复仅用于宿舍沟通演练，不代表真实舍友想法，不进行心理诊断，不进行医学判断，不进行人格评价。如沟通压力持续升高或出现现实安全风险，请联系辅导员、心理老师或其他现实支持。"
}
```

### POST /api/simulate/stream

状态：在保留 `/api/simulate` 完整 JSON 契约的基础上新增。该接口用于前端模拟页按顺序展示三位虚拟舍友回复；后端仍先生成并校验完整 `SimulateResponse`，再按舍友 A、舍友 B、舍友 C 的顺序输出事件。

请求字段：与 `POST /api/simulate` 完全一致，包括可选 `dialogue` 历史对话字段。

响应格式：`application/x-ndjson`，每行一个 JSON object。

事件顺序：

```json
{"type":"start"}
{"type":"reply","reply":{"roommate":"舍友 A","personality":"直接型","message":"我也没开很大声吧，不过如果真的影响你了，我可以试着戴耳机。"}}
{"type":"reply","reply":{"roommate":"舍友 B","personality":"回避型","message":"这个事情之后再说吧，我现在不太想聊。"}}
{"type":"reply","reply":{"roommate":"舍友 C","personality":"调和型","message":"我们可以一起定个休息时间规则，尽量别互相影响。"}}
{"type":"final","response":{"replies":[{"roommate":"舍友 A","personality":"直接型","message":"我也没开很大声吧，不过如果真的影响你了，我可以试着戴耳机。"},{"roommate":"舍友 B","personality":"回避型","message":"这个事情之后再说吧，我现在不太想聊。"},{"roommate":"舍友 C","personality":"调和型","message":"我们可以一起定个休息时间规则，尽量别互相影响。"}],"safety_note":"本回复仅用于宿舍沟通演练，不代表真实舍友想法，不进行心理诊断，不进行医学判断，不进行人格评价。如沟通压力持续升高或出现现实安全风险，请联系辅导员、心理老师或其他现实支持。"}}
```

错误语义：配置缺失仍返回 `503`；LangChain / DeepSeek 调用失败或 AI 输出结构异常仍返回 `502`。这些错误会在流开始前以普通 HTTP 错误返回，不会输出半截 NDJSON。

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

状态：第二阶段已实现。运行时通过 LangChain 调用 DeepSeek `deepseek-v4-flash`；缺少 `DEEPSEEK_API_KEY` 且没有兼容的 `OPENAI_API_KEY` 时返回 `503`。

请求字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `scenario` | string | 沟通场景，最长 300 字符 |
| `dialogue` | object[] | 用户与虚拟舍友的对话记录，至少 1 条，最多 20 条 |
| `dialogue[].speaker` | string | 发言者，枚举为 `user` / `roommate_a` / `roommate_b` / `roommate_c` / `system` |
| `dialogue[].message` | string | 单条对话内容，最长 500 字符 |
| `original_event` | object | 可选，受控原始事件摘要；只允许 `event_type`、`severity`、`frequency`、`emotion`、`has_communicated`、`has_conflict`、`pressure_score`、`risk_level`、`risk_label`、`description`，禁止提交任意大 JSON 或未授权字段 |

第三阶段兼容说明：

- 标准契约仍以 `user`、`roommate_a`、`roommate_b`、`roommate_c`、`system` 为准。
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
| `rewritten_message` | string | 优化话术 |
| `next_steps` | string[] | 后续行动建议 |
| `safety_note` | string | 非诊断性安全提示 |

请求示例：

```json
{
  "scenario": "舍友晚上打游戏声音较大，影响睡眠",
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
  "rewritten_message": "我想和你商量一下，晚上 11 点后能不能戴耳机或调低音量？我最近睡眠受影响比较明显，也想一起找个不影响你娱乐的办法。",
  "next_steps": [
    "选择双方情绪平稳的时间沟通",
    "提出具体可执行的休息时间规则",
    "如果多次沟通无效，可以寻求辅导员或宿舍管理员协助"
  ],
  "safety_note": "本复盘仅用于沟通训练建议，不代表真实舍友想法，不进行心理疾病诊断，不进行医学判断，不进行人格评价。如压力持续升高，请联系辅导员、心理老师或其他现实支持。"
}
```

## 错误语义

| 场景 | HTTP 状态码 | 说明 |
| --- | --- | --- |
| 请求字段非法 | `422` | FastAPI / Pydantic 校验失败，返回字段级错误信息 |
| 未配置 `DEEPSEEK_API_KEY` 或兼容的 `OPENAI_API_KEY` | `503` | AI 服务未配置，`/api/simulate`、`/api/review` 和 `/api/events/insight` 不返回模板伪结果 |
| LangChain / DeepSeek 调用失败 | `502` | 上游模型调用失败，后端返回 AI 服务调用失败语义 |
| AI 输出结构不符合契约或安全边界 | `502` | 模型输出无法解析为接口约定结构，或 `safety_note` 缺少必要安全边界，后端返回 AI 输出结构错误语义 |

注意：前端在无 `DEEPSEEK_API_KEY` 或兼容 `OPENAI_API_KEY` 时可能展示本地演示兜底，但后端真实接口语义仍是 `503`，不代表 AI 接口真实生成成功。
