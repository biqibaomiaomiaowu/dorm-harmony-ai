"""事件档案总压力分析模型。"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from math import log

from app.archive_metrics import (
    EVENT_TYPE_LABELS,
    build_emotion_distribution,
    build_event_insight,
    build_main_source_conclusion,
    build_source_insights,
    build_trend_explanation,
    build_trend_points,
    filter_events_by_period,
    normalize_period_days,
    recommend_training,
)
from app.safety import SAFETY_DISCLAIMER
from app.schemas import (
    AnalyzeRiskLevel,
    ArchiveAnalysisResponse,
    EventRecord,
    SourceBreakdown,
)
from app.scoring import analyze_pressure


def analyze_archive_pressure(
    events: list[EventRecord],
    today: date | None = None,
    period_days: int = 30,
) -> ArchiveAnalysisResponse:
    """汇总事件档案，返回当前宿舍关系总压力。

    档案汇总按当前规则调用 analyze_pressure() 重算，以便评分模型调整后整体口径一致。
    """
    analysis_date = today or date.today()
    normalized_period_days = normalize_period_days(period_days)
    if not events:
        return ArchiveAnalysisResponse(
            pressure_score=0,
            risk_level="stable",
            risk_label="关系平稳",
            main_sources=[],
            emotion_keywords=[],
            trend_message="当前还没有记录事件，关系状态暂按“关系平稳”展示。",
            suggestion="请先记录事件，系统会根据事件档案汇总宿舍关系压力。",
            recommend_simulation=False,
            disclaimer=SAFETY_DISCLAIMER,
            event_count=0,
            active_30d_count=0,
            source_breakdown=[],
            period_days=normalized_period_days,
            active_period_count=0,
            trend_points=[],
            trend_explanation=build_trend_explanation([], "stable"),
            source_insights=[],
            main_source_conclusion="",
            emotion_distribution=[],
            event_insight=None,
            training_recommendation=None,
        )

    weighted_score_sum = 0.0
    weight_sum = 0.0
    active_30d_count = 0
    event_types = set()
    source_contributions: dict[str, float] = defaultdict(float)
    emotion_keywords: list[str] = []
    current_pressure_scores: dict[str, int] = {}

    for event in events:
        days_since_event = max((analysis_date - event.event_date).days, 0)
        recency_weight = _recency_weight(days_since_event)
        single_analysis = analyze_pressure(event)
        current_pressure_scores[event.id] = single_analysis.pressure_score

        weighted_score_sum += single_analysis.pressure_score * recency_weight
        weight_sum += recency_weight

        if days_since_event <= 30:
            active_30d_count += 1
        event_types.add(event.event_type)
        emotion_keywords.extend(
            keyword
            for keyword in single_analysis.emotion_keywords
            if keyword not in emotion_keywords
        )

        source_label = EVENT_TYPE_LABELS[event.event_type]
        source_contributions[source_label] += (
            single_analysis.pressure_score * recency_weight
        )

    weighted_average = weighted_score_sum / max(weight_sum, 1.0)
    accumulation_bonus = min(15, round(5 * log(1 + max(active_30d_count - 1, 0))))
    diversity_bonus = min(8, 2 * max(len(event_types) - 1, 0))
    pressure_score = _clamp_score(
        round(weighted_average + accumulation_bonus + diversity_bonus)
    )
    risk_level, risk_label = _risk_for_public_score(pressure_score)
    source_breakdown = _source_breakdown(source_contributions)
    active_period_count = len(
        filter_events_by_period(events, analysis_date, normalized_period_days)
    )
    trend_points = build_trend_points(
        events,
        analysis_date,
        normalized_period_days,
        current_pressure_scores,
    )
    source_insights = build_source_insights(events, source_breakdown, analysis_date)
    response = ArchiveAnalysisResponse(
        pressure_score=pressure_score,
        risk_level=risk_level,
        risk_label=risk_label,
        main_sources=[source.label for source in source_breakdown],
        emotion_keywords=emotion_keywords,
        trend_message=(
            f"事件档案共记录 {len(events)} 条事件，其中近 30 天 {active_30d_count} 条。"
            f"当前总压力值为 {pressure_score}，处于“{risk_label}”状态。"
        ),
        suggestion=_suggestion(pressure_score),
        recommend_simulation=pressure_score >= 61,
        disclaimer=SAFETY_DISCLAIMER,
        event_count=len(events),
        active_30d_count=active_30d_count,
        source_breakdown=source_breakdown,
        period_days=normalized_period_days,
        active_period_count=active_period_count,
        trend_points=trend_points,
        trend_explanation=build_trend_explanation(trend_points, risk_level),
        source_insights=source_insights,
        main_source_conclusion=build_main_source_conclusion(source_insights),
        emotion_distribution=build_emotion_distribution(
            events,
            analysis_date,
            normalized_period_days,
        ),
        event_insight=build_event_insight(
            events,
            analysis_date,
            normalized_period_days,
        ),
    )
    response.training_recommendation = recommend_training(
        events,
        response,
        normalized_period_days,
        analysis_date,
    )

    return response


def _recency_weight(days_since_event: int) -> float:
    """根据事件距今天数返回档案汇总时使用的时间衰减权重。"""
    if days_since_event <= 7:
        return 1.0
    if days_since_event <= 14:
        return 0.85
    if days_since_event <= 30:
        return 0.70
    if days_since_event <= 60:
        return 0.50
    return 0.30


def _clamp_score(score: int) -> int:
    """把汇总压力分数限制在公开展示的 0-100 区间内。"""
    return max(0, min(score, 100))


def _risk_for_public_score(score: int) -> tuple[AnalyzeRiskLevel, str]:
    """把档案总压力分数映射为公开风险等级和中文标签。"""
    if score <= 30:
        return "stable", "关系平稳"
    if score <= 60:
        return "pressure", "存在压力"
    if score <= 80:
        return "high", "冲突风险较高"
    return "severe", "高压力状态"


def _source_breakdown(contributions: dict[str, float]) -> list[SourceBreakdown]:
    """把所有正贡献事件类型转换为百分比拆解。"""
    returned_sources = sorted(
        (
            (label, contribution)
            for label, contribution in contributions.items()
            if contribution > 0
        ),
        key=lambda item: item[1],
        reverse=True,
    )
    if not returned_sources:
        return []

    total = sum(contribution for _, contribution in returned_sources)
    rounded_percents = [
        round(contribution / total * 100)
        for _, contribution in returned_sources
    ]
    percent_delta = 100 - sum(rounded_percents)
    rounded_percents[0] += percent_delta

    return [
        SourceBreakdown(
            label=label,
            percent=percent,
            contribution=contribution,
        )
        for (label, contribution), percent in zip(returned_sources, rounded_percents)
    ]


def _suggestion(score: int) -> str:
    """根据档案总压力分数生成下一步沟通或求助建议。"""
    if score >= 81:
        return "建议优先确保安全，必要时寻求辅导员、宿管或心理老师等现实支持。"
    if score >= 61:
        return "建议先进行沟通演练，再选择双方情绪相对平稳的时间沟通。"
    if score >= 31:
        return "建议尽早围绕具体事件表达感受和需求，避免问题继续积累。"
    return "建议继续保持现有沟通节奏，及时记录新的宿舍相处事件。"
