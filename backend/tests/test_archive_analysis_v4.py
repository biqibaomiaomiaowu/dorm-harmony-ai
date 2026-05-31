from datetime import date

from app import archive_metrics
from app.archive_analysis import analyze_archive_pressure
from app.event_store import InMemoryEventStore
from app.schemas import EventRecordCreate
from app.scoring import analyze_pressure


def _add_event(
    store: InMemoryEventStore,
    *,
    event_date: date,
    event_type: str = "noise",
    severity: int = 4,
    frequency: str = "weekly_multiple",
    emotion: str = "anxious",
    emotions: list[str] | None = None,
    has_communicated: bool = False,
    has_conflict: bool = True,
    description: str = "舍友晚上打游戏声音很大，影响睡眠。",
):
    return store.add(
        EventRecordCreate(
            event_date=event_date,
            event_type=event_type,
            severity=severity,
            frequency=frequency,
            emotion=emotion,
            emotions=emotions or [],
            primary_emotion=emotion,
            has_communicated=has_communicated,
            has_conflict=has_conflict,
            description=description,
        )
    )


def test_empty_archive_returns_empty_period_metrics_and_no_training_recommendation():
    result = analyze_archive_pressure([], today=date(2026, 5, 15), period_days=7)

    assert result.period_days == 7
    assert result.risk_level == "stable"
    assert result.active_period_count == 0
    assert result.active_30d_count == 0
    assert result.trend_points == []
    assert result.emotion_distribution == []
    assert result.source_insights == []
    assert result.event_insight is None
    assert result.training_recommendation is None


def test_single_event_returns_one_trend_point_and_low_sample_explanation():
    store = InMemoryEventStore()
    _add_event(store, event_date=date(2026, 5, 15))

    result = analyze_archive_pressure(
        store.list(),
        today=date(2026, 5, 15),
        period_days=15,
    )

    assert result.period_days == 15
    assert result.active_period_count == 1
    assert len(result.trend_points) == 1
    assert result.trend_points[0].date == "2026-05-15"
    assert result.trend_points[0].pressure_score == 76
    assert result.trend_points[0].event_count == 1
    assert "记录较少" in result.trend_explanation or "初步参考" in result.trend_explanation


def test_period_days_changes_active_period_count_but_keeps_active_30d_count():
    store = InMemoryEventStore()
    _add_event(store, event_date=date(2026, 5, 15), description="今天的噪音事件。")
    _add_event(store, event_date=date(2026, 4, 25), description="20 天前的噪音事件。")
    _add_event(store, event_date=date(2026, 4, 5), description="40 天前的噪音事件。")

    result_7d = analyze_archive_pressure(
        store.list(),
        today=date(2026, 5, 15),
        period_days=7,
    )
    result_30d = analyze_archive_pressure(
        store.list(),
        today=date(2026, 5, 15),
        period_days=30,
    )

    assert result_7d.active_period_count == 1
    assert result_30d.active_period_count == 2
    assert result_7d.active_30d_count == 2
    assert result_30d.active_30d_count == 2
    assert result_7d.pressure_score == result_30d.pressure_score


def test_trend_points_are_date_sorted_and_average_same_day_scores():
    store = InMemoryEventStore()
    first_same_day = _add_event(
        store,
        event_date=date(2026, 5, 10),
        severity=2,
        frequency="occasional",
        emotion="helpless",
        has_communicated=True,
        has_conflict=False,
        description="公共桌面偶尔有点乱，已经提醒过一次。",
    )
    second_same_day = _add_event(
        store,
        event_date=date(2026, 5, 10),
        severity=5,
        frequency="daily",
        emotion="angry",
        has_communicated=False,
        has_conflict=True,
        description="晚上持续很吵，已经影响休息。",
    )
    later_event = _add_event(
        store,
        event_date=date(2026, 5, 12),
        severity=3,
        frequency="weekly_multiple",
        emotion="anxious",
        has_communicated=False,
        has_conflict=False,
        description="午休时外放短视频。",
    )

    result = analyze_archive_pressure(
        store.list(),
        today=date(2026, 5, 15),
        period_days=7,
    )

    expected_same_day_score = round(
        (
            analyze_pressure(first_same_day).pressure_score
            + analyze_pressure(second_same_day).pressure_score
        )
        / 2
    )
    assert [point.date for point in result.trend_points] == [
        "2026-05-10",
        "2026-05-12",
    ]
    assert result.trend_points[0].event_count == 2
    assert result.trend_points[0].pressure_score == expected_same_day_score
    assert result.trend_points[1].event_count == 1
    assert result.trend_points[1].pressure_score == analyze_pressure(later_event).pressure_score


def test_multi_point_trend_explanation_detects_rise_and_drop():
    rising_store = InMemoryEventStore()
    _add_event(
        rising_store,
        event_date=date(2026, 5, 10),
        severity=1,
        frequency="occasional",
        emotion="helpless",
        has_communicated=True,
        has_conflict=False,
        description="公共区域偶尔有点乱，已经沟通过。",
    )
    _add_event(
        rising_store,
        event_date=date(2026, 5, 14),
        severity=5,
        frequency="daily",
        emotion="angry",
        has_communicated=False,
        has_conflict=True,
        description="最近连续几天凌晨很吵，已经争吵。",
    )

    rising_result = analyze_archive_pressure(
        rising_store.list(),
        today=date(2026, 5, 15),
        period_days=7,
    )

    dropping_store = InMemoryEventStore()
    _add_event(
        dropping_store,
        event_date=date(2026, 5, 10),
        severity=5,
        frequency="daily",
        emotion="angry",
        has_communicated=False,
        has_conflict=True,
        description="前几天凌晨很吵，发生了争执。",
    )
    _add_event(
        dropping_store,
        event_date=date(2026, 5, 14),
        severity=1,
        frequency="occasional",
        emotion="helpless",
        has_communicated=True,
        has_conflict=False,
        description="后来只是偶尔有一点声音，已经提醒过。",
    )

    dropping_result = analyze_archive_pressure(
        dropping_store.list(),
        today=date(2026, 5, 15),
        period_days=7,
    )

    assert "上升" in rising_result.trend_explanation
    assert "下降" in dropping_result.trend_explanation


def test_trend_points_use_current_scoring_instead_of_stale_event_snapshot():
    store = InMemoryEventStore()
    event = _add_event(store, event_date=date(2026, 5, 15))
    event.single_analysis.pressure_score = 1

    result = analyze_archive_pressure(
        store.list(),
        today=date(2026, 5, 15),
        period_days=7,
    )

    current_score = analyze_pressure(event).pressure_score
    assert result.trend_points[0].pressure_score == current_score
    assert result.source_breakdown[0].contribution == float(current_score)


def test_build_trend_points_reuses_supplied_scores_without_recalculating(monkeypatch):
    store = InMemoryEventStore()
    event = _add_event(store, event_date=date(2026, 5, 15))

    def fail_if_recalculated(_event):
        raise AssertionError("build_trend_points should reuse supplied pressure scores")

    monkeypatch.setattr(archive_metrics, "analyze_pressure", fail_if_recalculated)

    trend_points = archive_metrics.build_trend_points(
        store.list(),
        today=date(2026, 5, 15),
        period_days=7,
        pressure_scores={event.id: 42},
    )

    assert trend_points[0].pressure_score == 42


def test_source_insights_follow_breakdown_rank_and_include_explanations():
    store = InMemoryEventStore()
    _add_event(store, event_date=date(2026, 5, 15), event_type="noise")
    _add_event(
        store,
        event_date=date(2026, 5, 14),
        event_type="hygiene",
        severity=2,
        frequency="occasional",
        emotion="helpless",
        has_communicated=True,
        has_conflict=False,
        description="公共区域偶尔没人整理，但已经协商过一次。",
    )

    result = analyze_archive_pressure(store.list(), today=date(2026, 5, 15))

    assert [source.rank for source in result.source_insights] == [1, 2]
    assert [source.label for source in result.source_insights] == ["噪音冲突", "卫生冲突"]
    assert sum(source.percent for source in result.source_insights) == 100
    assert all(source.contribution >= 0 for source in result.source_insights)
    assert all(source.event_count >= 1 for source in result.source_insights)
    assert all(source.recent_event_date is not None for source in result.source_insights)
    assert all(source.explanation for source in result.source_insights)
    assert result.main_source_conclusion


def test_emotion_distribution_counts_unique_multi_emotion_selection_with_labels():
    store = InMemoryEventStore()
    _add_event(
        store,
        event_date=date(2026, 5, 15),
        event_type="hygiene",
        severity=2,
        frequency="occasional",
        emotion="helpless",
        emotions=["helpless", "depressed", "helpless"],
        has_communicated=True,
        has_conflict=False,
        description="公共区域有点乱，我很无奈也有些压抑。",
    )
    _add_event(
        store,
        event_date=date(2026, 5, 14),
        event_type="privacy",
        severity=3,
        frequency="weekly_multiple",
        emotion="helpless",
        emotions=[],
        has_communicated=False,
        has_conflict=False,
        description="舍友未经允许拿东西，我很无奈。",
    )

    result = analyze_archive_pressure(store.list(), today=date(2026, 5, 15))
    distribution_by_emotion = {
        item.emotion: item
        for item in result.emotion_distribution
    }

    assert distribution_by_emotion["helpless"].label == "无奈"
    assert distribution_by_emotion["depressed"].label == "压抑"
    assert distribution_by_emotion["helpless"].count == 2
    assert distribution_by_emotion["depressed"].count == 1
    assert sum(item.percent for item in result.emotion_distribution) == 100


def test_noise_source_recommends_noise_training_category():
    store = InMemoryEventStore()
    _add_event(store, event_date=date(2026, 5, 15), event_type="noise")
    _add_event(store, event_date=date(2026, 5, 13), event_type="noise")

    result = analyze_archive_pressure(store.list(), today=date(2026, 5, 15))

    assert result.training_recommendation is not None
    assert result.training_recommendation.category_id == "noise"
    assert result.training_recommendation.category_label == "噪音冲突"
    assert result.training_recommendation.scenario_id.startswith("noise_")


def test_high_pressure_training_recommendation_contains_real_support_and_not_challenge():
    store = InMemoryEventStore()
    _add_event(
        store,
        event_date=date(2026, 5, 15),
        event_type="schedule",
        severity=5,
        frequency="daily",
        emotion="angry",
        has_communicated=False,
        has_conflict=True,
        description="舍友长期凌晨开灯洗漱，已经多次影响休息。",
    )
    _add_event(
        store,
        event_date=date(2026, 5, 14),
        event_type="noise",
        severity=5,
        frequency="daily",
        emotion="depressed",
        has_communicated=False,
        has_conflict=True,
        description="晚上持续很吵，我已经很压抑。",
    )

    result = analyze_archive_pressure(store.list(), today=date(2026, 5, 15))

    assert result.risk_level in {"high", "severe"}
    assert result.training_recommendation is not None
    assert result.training_recommendation.difficulty_id != "challenge"
    assert any(
        phrase in result.training_recommendation.safety_note
        for phrase in ("现实支持", "辅导员", "心理老师")
    )
