"""事件档案总压力分析模型。"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from math import log

from app.safety import SAFETY_DISCLAIMER
from app.schemas import (
    AnalyzeRiskLevel,
    ArchiveAnalysisResponse,
    EventRecord,
    EventType,
    SourceBreakdown,
)
from app.scoring import analyze_pressure


ARCHIVE_EVENT_TYPE_LABELS: dict[EventType, str] = {
    EventType.NOISE: "噪音冲突",
    EventType.SCHEDULE: "作息冲突",
    EventType.HYGIENE: "卫生冲突",
    EventType.COST: "费用冲突",
    EventType.PRIVACY: "隐私边界",
    EventType.EMOTION: "情绪冲突",
}


def analyze_archive_pressure(
    events: list[EventRecord],
    today: date | None = None,
) -> ArchiveAnalysisResponse:
    """汇总事件档案，返回当前宿舍关系总压力。

    档案汇总按当前规则调用 analyze_pressure() 重算，以便评分模型调整后整体口径一致。
    """
    analysis_date = today or date.today()
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
        )

    weighted_score_sum = 0.0
    weight_sum = 0.0
    active_30d_count = 0
    event_types = set()
    source_contributions: dict[str, float] = defaultdict(float)
    emotion_keywords: list[str] = []

    for event in events:
        days_since_event = max((analysis_date - event.event_date).days, 0)
        recency_weight = _recency_weight(days_since_event)
        single_analysis = analyze_pressure(event)

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

        source_label = ARCHIVE_EVENT_TYPE_LABELS[event.event_type]
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

    return ArchiveAnalysisResponse(
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
    )


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
