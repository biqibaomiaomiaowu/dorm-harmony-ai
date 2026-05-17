from datetime import date, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.archive_analysis import analyze_archive_pressure
from app.event_store import InMemoryEventStore, JsonEventStore
from app.schemas import EventRecordCreate


DISALLOWED_SOURCE_BREAKDOWN_LABELS = {
    "发生频率较高",
    "尚未有效沟通",
    "已出现争吵或冷战",
}


def test_event_record_create_requires_event_date_as_date():
    record = EventRecordCreate(
        event_date="2026-05-15",
        event_type="noise",
        severity=4,
        frequency="weekly_multiple",
        emotion="anxious",
        has_communicated=False,
        has_conflict=True,
        description="舍友晚上打游戏声音很大，影响睡眠。",
    )

    assert record.event_date == date(2026, 5, 15)


def test_event_record_create_rejects_future_event_date():
    with pytest.raises(ValidationError):
        EventRecordCreate(
            event_date=date.today() + timedelta(days=1),
            event_type="noise",
            severity=4,
            frequency="weekly_multiple",
            emotion="anxious",
            has_communicated=False,
            has_conflict=True,
            description="舍友晚上打游戏声音很大，影响睡眠。",
        )


def test_in_memory_event_store_lists_by_event_date_desc_then_created_at_desc():
    store = InMemoryEventStore()
    older_date_event = EventRecordCreate(
        event_date="2026-05-14",
        event_type="noise",
        severity=3,
        frequency="occasional",
        emotion="irritable",
        has_communicated=True,
        has_conflict=False,
        description="旧事件。",
    )
    same_day_first_event = EventRecordCreate(
        event_date="2026-05-15",
        event_type="noise",
        severity=4,
        frequency="weekly_multiple",
        emotion="anxious",
        has_communicated=False,
        has_conflict=True,
        description="同日先记录事件。",
    )
    same_day_second_event = same_day_first_event.model_copy(
        update={"description": "同日后记录事件。"}
    )

    saved_older_date = store.add(older_date_event)
    saved_same_day_first = store.add(same_day_first_event)
    saved_same_day_second = store.add(same_day_second_event)

    saved_older_date.created_at = datetime(2026, 5, 16, 9, tzinfo=timezone.utc)
    saved_same_day_first.created_at = datetime(2026, 5, 15, 8, tzinfo=timezone.utc)
    saved_same_day_second.created_at = datetime(2026, 5, 15, 9, tzinfo=timezone.utc)

    assert store.list() == [
        saved_same_day_second,
        saved_same_day_first,
        saved_older_date,
    ]


def test_json_event_store_instances_share_path_level_lock(tmp_path):
    store_path = tmp_path / "events.json"

    first_store = JsonEventStore(store_path)
    second_store = JsonEventStore(store_path)

    assert first_store._lock is second_store._lock


def test_json_event_store_persists_models_sorted_and_cleans_temporary_files(tmp_path):
    store_path = tmp_path / "events.json"
    store = JsonEventStore(store_path)
    older_date_event = EventRecordCreate(
        event_date="2026-05-14",
        event_type="noise",
        severity=3,
        frequency="occasional",
        emotion="irritable",
        has_communicated=True,
        has_conflict=False,
        description="旧事件。",
    )
    same_day_first_event = EventRecordCreate(
        event_date="2026-05-15",
        event_type="noise",
        severity=4,
        frequency="weekly_multiple",
        emotion="anxious",
        has_communicated=False,
        has_conflict=True,
        description="同日先记录事件。",
    )
    same_day_second_event = same_day_first_event.model_copy(
        update={"description": "同日后记录事件。"}
    )

    saved_older_date = store.add(older_date_event)
    saved_same_day_first = store.add(same_day_first_event)
    saved_same_day_second = store.add(same_day_second_event)
    saved_older_date.created_at = datetime(2026, 5, 16, 9, tzinfo=timezone.utc)
    saved_same_day_first.created_at = datetime(2026, 5, 15, 8, tzinfo=timezone.utc)
    saved_same_day_second.created_at = datetime(2026, 5, 15, 9, tzinfo=timezone.utc)
    store._write_events([saved_older_date, saved_same_day_first, saved_same_day_second])

    restored_events = JsonEventStore(store_path).list()

    assert [event.id for event in restored_events] == [
        saved_same_day_second.id,
        saved_same_day_first.id,
        saved_older_date.id,
    ]
    assert restored_events[0].event_date == date(2026, 5, 15)
    assert restored_events[0].created_at == datetime(2026, 5, 15, 9, tzinfo=timezone.utc)
    assert restored_events[0].single_analysis.pressure_score == 76
    assert not list(tmp_path.glob("*.tmp"))


def test_archive_pressure_single_event_stays_close_to_single_score():
    store = InMemoryEventStore()
    store.add(EventRecordCreate(
        event_date=date(2026, 5, 15),
        event_type="noise",
        severity=4,
        frequency="weekly_multiple",
        emotion="anxious",
        has_communicated=False,
        has_conflict=True,
        description="舍友晚上打游戏声音很大，影响睡眠。",
    ))

    result = analyze_archive_pressure(store.list(), today=date(2026, 5, 15))

    assert result.pressure_score == 76
    assert result.risk_level == "high"
    assert result.event_count == 1


def test_archive_pressure_accumulates_recent_multiple_events():
    store = InMemoryEventStore()
    store.add(EventRecordCreate(
        event_date=date(2026, 5, 15),
        event_type="noise",
        severity=4,
        frequency="weekly_multiple",
        emotion="anxious",
        has_communicated=False,
        has_conflict=True,
        description="舍友晚上打游戏声音很大。",
    ))
    store.add(EventRecordCreate(
        event_date=date(2026, 5, 14),
        event_type="hygiene",
        severity=4,
        frequency="daily",
        emotion="angry",
        has_communicated=False,
        has_conflict=True,
        description="公共区域长期没人打扫，已经吵过。",
    ))
    store.add(EventRecordCreate(
        event_date=date(2026, 5, 13),
        event_type="privacy",
        severity=3,
        frequency="weekly_multiple",
        emotion="wronged",
        has_communicated=False,
        has_conflict=False,
        description="舍友未经允许拿用私人物品。",
    ))

    result = analyze_archive_pressure(store.list(), today=date(2026, 5, 15))

    assert result.pressure_score >= 80
    assert result.risk_level == "severe"
    assert result.active_30d_count == 3
    assert result.source_breakdown[0].percent > 0


def test_archive_source_breakdown_uses_event_type_pressure_contributions_only():
    store = InMemoryEventStore()
    store.add(EventRecordCreate(
        event_date=date(2026, 5, 15),
        event_type="noise",
        severity=4,
        frequency="weekly_multiple",
        emotion="anxious",
        has_communicated=False,
        has_conflict=True,
        description="舍友晚上打游戏声音很大，影响睡眠。",
    ))
    store.add(EventRecordCreate(
        event_date=date(2026, 5, 15),
        event_type="hygiene",
        severity=2,
        frequency="occasional",
        emotion="helpless",
        has_communicated=True,
        has_conflict=False,
        description="公共区域偶尔没人整理，但已经协商过一次。",
    ))

    result = analyze_archive_pressure(store.list(), today=date(2026, 5, 15))

    source_by_label = {source.label: source for source in result.source_breakdown}
    assert list(source_by_label) == ["噪音冲突", "卫生冲突"]
    assert DISALLOWED_SOURCE_BREAKDOWN_LABELS.isdisjoint(source_by_label)
    assert source_by_label["噪音冲突"].contribution == 76
    assert source_by_label["卫生冲突"].contribution == 34
    assert source_by_label["噪音冲突"].percent == 69
    assert source_by_label["卫生冲突"].percent == 31
    assert sum(source.percent for source in result.source_breakdown) == 100


def test_archive_source_breakdown_returns_all_recorded_event_type_contributions():
    store = InMemoryEventStore()
    store.add(EventRecordCreate(
        event_date=date(2026, 5, 15),
        event_type="schedule",
        severity=3,
        frequency="daily",
        emotion="angry",
        has_communicated=False,
        has_conflict=True,
        description="舍友长期凌晨开灯洗漱，已经多次影响休息。",
    ))
    store.add(EventRecordCreate(
        event_date=date(2026, 5, 15),
        event_type="noise",
        severity=4,
        frequency="weekly_multiple",
        emotion="anxious",
        has_communicated=False,
        has_conflict=True,
        description="舍友晚上打游戏声音很大，影响睡眠。",
    ))
    store.add(EventRecordCreate(
        event_date=date(2026, 5, 15),
        event_type="cost",
        severity=3,
        frequency="weekly_multiple",
        emotion="wronged",
        has_communicated=True,
        has_conflict=False,
        description="公共用品费用分摊总是说不清，心里有些委屈。",
    ))
    store.add(EventRecordCreate(
        event_date=date(2026, 5, 15),
        event_type="hygiene",
        severity=2,
        frequency="occasional",
        emotion="helpless",
        has_communicated=True,
        has_conflict=False,
        description="公共区域偶尔没人整理，但已经协商过一次。",
    ))

    result = analyze_archive_pressure(store.list(), today=date(2026, 5, 15))

    labels = [source.label for source in result.source_breakdown]
    assert labels == ["作息冲突", "噪音冲突", "费用冲突", "卫生冲突"]
    assert DISALLOWED_SOURCE_BREAKDOWN_LABELS.isdisjoint(labels)
    assert [
        source.contribution
        for source in result.source_breakdown
    ] == sorted(
        (source.contribution for source in result.source_breakdown),
        reverse=True,
    )
    assert sum(source.percent for source in result.source_breakdown) == 100


def test_archive_pressure_old_event_has_lower_current_weight():
    store = InMemoryEventStore()
    store.add(EventRecordCreate(
        event_date=date(2026, 2, 1),
        event_type="noise",
        severity=5,
        frequency="daily",
        emotion="depressed",
        has_communicated=False,
        has_conflict=True,
        description="很久之前的严重噪音冲突。",
    ))

    result = analyze_archive_pressure(store.list(), today=date(2026, 5, 15))

    assert result.pressure_score < 80
    assert result.active_30d_count == 0


def test_archive_pressure_empty_archive_prompts_to_record_event_first():
    result = analyze_archive_pressure([], today=date(2026, 5, 15))

    assert result.pressure_score == 0
    assert result.risk_level == "stable"
    assert result.risk_label == "关系平稳"
    assert "先记录事件" in result.suggestion
