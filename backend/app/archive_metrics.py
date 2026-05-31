"""事件档案 V4 周期指标和训练推荐纯函数。"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta

from app.schemas import (
    AnalyzeRiskLevel,
    ArchiveAnalysisResponse,
    ArchiveTrendPoint,
    Emotion,
    EmotionDistributionItem,
    EventInsightSummary,
    EventRecord,
    EventType,
    SourceBreakdown,
    SourceInsight,
    TrainingRecommendation,
    emotion_display_label,
)
from app.scoring import analyze_pressure
from app.training_catalog import (
    build_opening_suggestion,
    get_category,
    get_difficulty,
    get_scenario,
    get_target,
    scenarios_for_category,
)


SUPPORTED_RANGE_DAYS = (7, 15, 30, 90)

EVENT_TYPE_LABELS: dict[EventType, str] = {
    EventType.NOISE: "噪音冲突",
    EventType.SCHEDULE: "作息冲突",
    EventType.HYGIENE: "卫生冲突",
    EventType.COST: "费用冲突",
    EventType.PRIVACY: "隐私边界",
    EventType.EMOTION: "情绪冲突",
}
SOURCE_LABEL_TO_CATEGORY = {
    label: event_type.value
    for event_type, label in EVENT_TYPE_LABELS.items()
}
EVENT_TYPE_ORDER = tuple(EventType)


def normalize_period_days(period_days: int) -> int:
    """校验并返回受支持的周期天数。"""
    if period_days not in SUPPORTED_RANGE_DAYS:
        allowed = ", ".join(str(days) for days in SUPPORTED_RANGE_DAYS)
        raise ValueError(f"period_days must be one of {allowed}")
    return period_days


def filter_events_by_period(
    events: list[EventRecord],
    today: date,
    period_days: int,
) -> list[EventRecord]:
    """返回周期内事件，周期包含今天和向前 period_days - 1 天。"""
    normalized_period_days = normalize_period_days(period_days)
    start_date = today - timedelta(days=normalized_period_days - 1)
    return [
        event
        for event in events
        if start_date <= event.event_date <= today
    ]


def build_trend_points(
    events: list[EventRecord],
    today: date,
    period_days: int,
    pressure_scores: dict[str, int] | None = None,
) -> list[ArchiveTrendPoint]:
    """按日期升序构建周期趋势点，同日压力取事件均值。"""
    period_events = filter_events_by_period(events, today, period_days)
    current_pressure_scores = pressure_scores or {}
    score_buckets: dict[date, list[int]] = defaultdict(list)
    for event in period_events:
        if event.id in current_pressure_scores:
            pressure_score = current_pressure_scores[event.id]
        else:
            pressure_score = analyze_pressure(event).pressure_score
        score_buckets[event.event_date].append(pressure_score)

    return [
        ArchiveTrendPoint(
            date=event_date.isoformat(),
            pressure_score=round(sum(scores) / len(scores)),
            event_count=len(scores),
        )
        for event_date, scores in sorted(score_buckets.items())
    ]


def build_trend_explanation(
    trend_points: list[ArchiveTrendPoint],
    risk_level: AnalyzeRiskLevel,
) -> str:
    """根据趋势点生成简短趋势解释。"""
    risk_text = {
        "stable": "关系状态暂时平稳",
        "pressure": "事件压力已有一定积累",
        "high": "冲突风险较高",
        "severe": "当前压力较高",
    }[risk_level]
    if not trend_points:
        return f"当前周期内暂无事件记录，趋势暂以“{risk_text}”作为参考。"
    if len(trend_points) == 1:
        return (
            "当前周期内只有 1 个记录日期，记录较少，趋势仅能作为初步参考；"
            f"当天压力值为 {trend_points[0].pressure_score}。"
        )

    first_score = trend_points[0].pressure_score
    latest_score = trend_points[-1].pressure_score
    if latest_score - first_score >= 8:
        direction = "上升"
        detail = "最近记录的压力值高于周期起点，建议优先处理仍在反复出现的具体事件。"
    elif first_score - latest_score >= 8:
        direction = "下降"
        detail = "最近记录的压力值低于周期起点，可以继续保留已经有效的沟通方式。"
    else:
        direction = "平稳"
        detail = "周期内压力值波动不大，建议持续记录并关注是否出现新的高压事件。"

    return f"周期内趋势整体{direction}，{detail}"


def build_emotion_distribution(
    events: list[EventRecord],
    today: date,
    period_days: int,
) -> list[EmotionDistributionItem]:
    """统计周期内情绪分布，多选情绪在单条事件内去重计数。"""
    period_events = filter_events_by_period(events, today, period_days)
    counts: Counter[Emotion] = Counter()
    for event in period_events:
        for emotion in _unique_event_emotions(event):
            counts[emotion] += 1
    if not counts:
        return []

    sorted_items = _sorted_emotion_counts(counts)
    total = sum(counts.values())
    percents = [round(count / total * 100) for _, count in sorted_items]
    percents[0] += 100 - sum(percents)

    return [
        EmotionDistributionItem(
            emotion=emotion,
            label=emotion_display_label(emotion),
            count=count,
            percent=percent,
        )
        for (emotion, count), percent in zip(sorted_items, percents)
    ]


def build_event_insight(
    events: list[EventRecord],
    today: date,
    period_days: int,
) -> EventInsightSummary | None:
    """构建周期内事件事实摘要，不使用诊断或人格判断表述。"""
    period_events = filter_events_by_period(events, today, period_days)
    if not period_events:
        return None

    emotion_counts: Counter[Emotion] = Counter()
    event_type_counts: Counter[EventType] = Counter()
    for event in period_events:
        event_type_counts[event.event_type] += 1
        for emotion in _unique_event_emotions(event):
            emotion_counts[emotion] += 1

    top_emotions = [
        emotion_display_label(emotion)
        for emotion, _ in _sorted_emotion_counts(emotion_counts)
    ][:3]
    top_event_types = [
        EVENT_TYPE_LABELS[event_type]
        for event_type, _ in _sorted_event_type_counts(event_type_counts)
    ][:3]
    communicated_count = sum(1 for event in period_events if event.has_communicated)
    uncommunicated_count = len(period_events) - communicated_count
    conflict_count = sum(1 for event in period_events if event.has_conflict)

    event_type_text = "、".join(top_event_types) or "暂未形成集中类型"
    emotion_text = "、".join(top_emotions) or "暂未记录情绪"
    summary = (
        f"近 {period_days} 天记录 {len(period_events)} 条事件，"
        f"主要事件类型为{event_type_text}，主要情绪为{emotion_text}；"
        f"已沟通 {communicated_count} 条，未沟通 {uncommunicated_count} 条，"
        f"包含直接冲突 {conflict_count} 条。"
    )

    return EventInsightSummary(
        period_days=period_days,
        period_event_count=len(period_events),
        top_emotions=top_emotions,
        top_event_types=top_event_types,
        communicated_count=communicated_count,
        uncommunicated_count=uncommunicated_count,
        conflict_count=conflict_count,
        summary=summary,
    )


def build_source_insights(
    events: list[EventRecord],
    source_breakdown: list[SourceBreakdown],
    analysis_date: date,
) -> list[SourceInsight]:
    """把来源拆解补充为带排名、事件数和最近日期的解释项。"""
    insights: list[SourceInsight] = []
    for rank, source in enumerate(source_breakdown, start=1):
        matching_events = [
            event
            for event in events
            if EVENT_TYPE_LABELS[event.event_type] == source.label
        ]
        recent_event_date = max(
            (event.event_date for event in matching_events),
            default=None,
        )
        explanation = _source_insight_explanation(
            source,
            len(matching_events),
            recent_event_date,
            analysis_date,
        )
        insights.append(
            SourceInsight(
                rank=rank,
                label=source.label,
                percent=source.percent,
                contribution=source.contribution,
                event_count=len(matching_events),
                recent_event_date=recent_event_date,
                explanation=explanation,
            )
        )
    return insights


def build_main_source_conclusion(source_insights: list[SourceInsight]) -> str:
    """生成主压力来源结论。"""
    if not source_insights:
        return ""

    main_source = source_insights[0]
    if len(source_insights) == 1:
        return (
            f"当前档案中最主要的压力来源是“{main_source.label}”，"
            f"占比约 {main_source.percent}%。"
        )

    second_source = source_insights[1]
    return (
        f"当前档案中最主要的压力来源是“{main_source.label}”，"
        f"占比约 {main_source.percent}%；其次是“{second_source.label}”。"
    )


def recommend_training(
    events: list[EventRecord],
    analysis: ArchiveAnalysisResponse,
    period_days: int,
    today: date,
) -> TrainingRecommendation | None:
    """基于档案事实从 V4 固定目录中选择训练推荐，不调用 AI。"""
    period_events = filter_events_by_period(events, today, period_days)
    if not period_events:
        return None

    category_id = _main_category_id(period_events, analysis)
    category = get_category(category_id)
    relevant_events = [
        event
        for event in period_events
        if event.event_type.value == category_id
    ] or period_events
    scenario_id = _choose_scenario_id(category_id, relevant_events)
    target_id = _choose_target_id(category_id, period_events, analysis.risk_level)
    difficulty_id = _choose_difficulty_id(period_events, analysis.risk_level)

    scenario = get_scenario(scenario_id)
    target = get_target(target_id)
    difficulty = get_difficulty(difficulty_id)
    reason = (
        f"近 {period_days} 天记录 {len(period_events)} 条事件，"
        f"主要来源为“{category.label}”，当前档案状态为“{analysis.risk_label}”；"
        f"建议先练习“{target.label}”，再回到现实沟通。"
    )

    return TrainingRecommendation(
        category_id=category.id,
        category_label=category.label,
        scenario_id=scenario.id,
        scenario_title=scenario.title,
        target_id=target.id,
        target_label=target.label,
        difficulty_id=difficulty.id,
        difficulty_label=difficulty.label,
        difficulty_description=difficulty.description,
        reason=reason,
        opening_suggestion=build_opening_suggestion(
            category.id,
            scenario.id,
            target.id,
            difficulty.id,
        ),
        safety_note=_training_safety_note(analysis.risk_level),
    )


def _unique_event_emotions(event: EventRecord) -> list[Emotion]:
    selected = list(event.emotions or [])
    if not selected and event.emotion is not None:
        selected = [event.emotion]

    unique_emotions: list[Emotion] = []
    for emotion in selected:
        if emotion not in unique_emotions:
            unique_emotions.append(emotion)
    return unique_emotions


def _sorted_emotion_counts(
    counts: Counter[Emotion],
) -> list[tuple[Emotion, int]]:
    return sorted(
        counts.items(),
        key=lambda item: (-item[1], list(Emotion).index(item[0])),
    )


def _sorted_event_type_counts(
    counts: Counter[EventType],
) -> list[tuple[EventType, int]]:
    return sorted(
        counts.items(),
        key=lambda item: (-item[1], EVENT_TYPE_ORDER.index(item[0])),
    )


def _source_insight_explanation(
    source: SourceBreakdown,
    event_count: int,
    recent_event_date: date | None,
    analysis_date: date,
) -> str:
    if recent_event_date is None:
        return f"{source.label}占档案压力约 {source.percent}%，但当前没有可定位的事件日期。"

    days_since = max((analysis_date - recent_event_date).days, 0)
    recent_text = "今天" if days_since == 0 else f"{days_since} 天前"
    return (
        f"{source.label}占档案压力约 {source.percent}%，共有 {event_count} 条相关记录，"
        f"最近一次在 {recent_event_date.isoformat()}（{recent_text}）。"
    )


def _main_category_id(
    period_events: list[EventRecord],
    analysis: ArchiveAnalysisResponse,
) -> str:
    if analysis.source_insights:
        category_id = SOURCE_LABEL_TO_CATEGORY.get(analysis.source_insights[0].label)
        if category_id is not None:
            return category_id
    if analysis.source_breakdown:
        category_id = SOURCE_LABEL_TO_CATEGORY.get(analysis.source_breakdown[0].label)
        if category_id is not None:
            return category_id

    event_type_counts = Counter(event.event_type for event in period_events)
    event_type = _sorted_event_type_counts(event_type_counts)[0][0]
    return event_type.value


def _choose_scenario_id(category_id: str, events: list[EventRecord]) -> str:
    descriptions = " ".join(event.description for event in events)
    scenarios = scenarios_for_category(category_id)
    if category_id == "noise":
        return "noise_video_noon" if "午休" in descriptions else "noise_game_night"
    if category_id == "schedule":
        if any(keyword in descriptions for keyword in ("早起", "洗漱", "早上")):
            return "schedule_morning_wash"
        return "schedule_lights_out_chat"
    if category_id == "hygiene":
        if any(keyword in descriptions for keyword in ("桌面", "公共桌")):
            return "hygiene_shared_desk"
        return "hygiene_trash"
    if category_id == "cost":
        if "公共用品" in descriptions:
            return "cost_public_items"
        return "cost_utility_split"
    if category_id == "privacy":
        if any(keyword in descriptions for keyword in ("朋友", "访客", "进宿舍")):
            return "privacy_visitors"
        return "privacy_borrow_items"
    if category_id == "emotion":
        if any(keyword in descriptions for keyword in ("冷战", "争吵", "吵架")):
            return "emotion_cold_war"
        return "emotion_tone_uncomfortable"
    return scenarios[0].id


def _choose_target_id(
    category_id: str,
    events: list[EventRecord],
    risk_level: AnalyzeRiskLevel,
) -> str:
    descriptions = " ".join(event.description for event in events)
    event_type_counts = Counter(event.event_type for event in events)
    repeated_same_source = max(event_type_counts.values(), default=0) >= 2
    uncommunicated_count = sum(1 for event in events if not event.has_communicated)
    has_conflict = any(event.has_conflict for event in events)

    if category_id == "emotion" or any(
        keyword in descriptions
        for keyword in ("冷战", "语气", "缓和关系", "关系修复")
    ):
        return "repair_relationship"
    if has_conflict and risk_level == "pressure":
        return "respond_objection"
    if repeated_same_source:
        return "negotiate_rule"
    if uncommunicated_count >= max(2, len(events) // 2 + 1):
        if risk_level in {"high", "severe"}:
            return "express_feeling"
        return "make_request"
    return "make_request"


def _choose_difficulty_id(
    events: list[EventRecord],
    risk_level: AnalyzeRiskLevel,
) -> str:
    source_diversity = len({event.event_type for event in events})
    if risk_level == "stable":
        return "beginner"
    if risk_level == "pressure":
        if len(events) >= 5 and source_diversity >= 3:
            return "challenge"
        return "intermediate"
    if risk_level == "high":
        return "intermediate"
    return "beginner"


def _training_safety_note(risk_level: AnalyzeRiskLevel) -> str:
    if risk_level in {"high", "severe"}:
        return (
            "仅用于沟通训练建议，不代表真实舍友想法；当前压力较高，"
            "练习前请先确保自身安全，必要时寻求辅导员、宿管或心理老师等现实支持。"
        )
    return (
        "仅用于沟通训练建议，不代表真实舍友想法；如沟通中压力升高或冲突升级，"
        "请及时寻求辅导员、宿管或心理老师等现实支持。"
    )
