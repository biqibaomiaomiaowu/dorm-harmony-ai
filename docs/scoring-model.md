# 压力评分模型

本文档记录第一阶段 `/api/analyze` 使用的规则评分模型。当前模型不调用 LangChain 或大模型，仅根据用户提交的结构化字段计算压力值。

## 输入指标

| 指标 | 来源字段 | 原始取值 | 规则分 |
| --- | --- | --- | --- |
| 事件严重程度 | `severity` | 1-5 | `severity * 20` |
| 发生频率 | `frequency` | `occasional` / `weekly_multiple` / `daily` | 30 / 70 / 100 |
| 情绪强度 | `emotion` | `helpless` / `anxious` / `wronged` / `irritable` / `angry` / `depressed` | 30 / 58 / 62 / 68 / 86 / 90 |
| 沟通状态 | `has_communicated` | `true` / `false` | 30 / 100 |
| 冲突升级情况 | `has_conflict` | `false` / `true` | 40 / 100 |

## 权重

| 指标 | 权重 |
| --- | --- |
| 事件严重程度 | 30% |
| 发生频率 | 25% |
| 情绪强度 | 25% |
| 沟通状态 | 10% |
| 冲突升级情况 | 10% |

计算公式：

```text
pressure_score = round(
  severity_score * 0.30
  + frequency_score * 0.25
  + emotion_score * 0.25
  + communication_score * 0.10
  + conflict_score * 0.10
)
```

## 风险区间

| 压力值 | `risk_level` | `risk_label` | 说明 |
| --- | --- | --- | --- |
| 0-30 | `stable` | 关系平稳 | 当前压力较低，可继续保持日常沟通 |
| 31-60 | `pressure` | 存在压力 | 宿舍关系存在一定摩擦，建议及时沟通 |
| 61-80 | `high` | 冲突风险较高 | 问题可能正在积累，建议先进行沟通演练 |
| 81-100 | `severe` | 高压力状态 | 建议优先确保安全，并寻求现实支持 |

## 典型示例

夜间噪音案例：

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

分项计算：

| 指标 | 规则分 | 权重 | 加权分 |
| --- | --- | --- | --- |
| 严重程度 4 | 80 | 30% | 24 |
| 每周多次 | 70 | 25% | 17.5 |
| 焦虑 | 58 | 25% | 14.5 |
| 尚未沟通 | 100 | 10% | 10 |
| 已有冲突 | 100 | 10% | 10 |

合计为 76，风险等级为 `high`，中文标签为“冲突风险较高”。该结果只表示宿舍关系压力趋势，不作为心理诊断、医学诊断或人格评价依据。

## 事件档案总压力模型

事件档案总压力用于 `GET /api/events/analysis`，输入为已经记录的全部事件。模型先复用单事件
`analyze_pressure()` 计算每条事件的 `single_score_i`，再结合事件日期评估当前档案压力。

### 时间权重

| 距离事件发生天数 | `recency_weight_i` |
| --- | --- |
| `days_since_event <= 7` | 1.00 |
| `8 <= days_since_event <= 14` | 0.85 |
| `15 <= days_since_event <= 30` | 0.70 |
| `31 <= days_since_event <= 60` | 0.50 |
| `days_since_event > 60` | 0.30 |

### 总压力公式

```text
weighted_average =
  sum(single_score_i * recency_weight_i) / max(sum(recency_weight_i), 1)

active_30d_count = count(events where days_since_event <= 30)
event_type_count = count(distinct event_type in all events)

accumulation_bonus =
  min(15, round(5 * ln(1 + max(active_30d_count - 1, 0))))

diversity_bonus =
  min(8, 2 * max(event_type_count - 1, 0))

archive_pressure_score =
  clamp(round(weighted_average + accumulation_bonus + diversity_bonus), 0, 100)
```

`max(sum(recency_weight_i), 1)` 用于表达“当前压力”的衰减：只有旧事件时，低时间权重不会在分母中被完全抵消；近期单条事件仍保持接近单事件分数。

### 主要压力来源贡献

`source_breakdown` 只按用户记录的 `event_type` 聚合压力贡献。每条事件仍先通过
`analyze_pressure()` 计算单条压力分，因此发生频率、是否有效沟通、是否出现争吵或冷战
会影响 `single_score_i`；但这些因素不会再作为独立来源标签返回。

事件类型标签：

| `event_type` | `source_breakdown[].label` |
| --- | --- |
| `noise` | 噪音冲突 |
| `schedule` | 作息冲突 |
| `hygiene` | 卫生冲突 |
| `cost` | 费用冲突 |
| `privacy` | 隐私边界 |
| `emotion` | 情绪冲突 |

对每条事件累加贡献：

```text
event_type_label contribution += single_score_i * recency_weight_i
```

按贡献值从高到低返回所有贡献值大于 0 的事件类型标签，先四舍五入为百分比，再把百分比差值调整到贡献最大的来源，确保返回的来源百分比总和严格等于 100。

### 预期行为

| 情况 | 预期 |
| --- | --- |
| 单条近期事件 | 总压力接近该事件单事件分数，不额外放大；夜间噪音示例为 76，风险等级为 `high` |
| 近期多次事件 | 近 30 天多条事件会触发累计加成，不同事件类型会触发少量多源加成，可能进入 `severe` |
| 旧事件 | 60 天前事件仍有低权重影响，但不会主导当前压力 |
| 无事件 | 返回 `pressure_score=0`、`risk_level=stable`、`risk_label=关系平稳`，并提示先记录事件 |
