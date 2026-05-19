import pytest
from pydantic import ValidationError

from app.schemas import AnalyzeRequest, Emotion, EventFrequency, EventType
from app.scoring import analyze_pressure


def test_analyze_pressure_scores_typical_night_noise_conflict():
    request = AnalyzeRequest(
        event_type=EventType.NOISE,
        severity=4,
        frequency=EventFrequency.WEEKLY_MULTIPLE,
        emotion=Emotion.ANXIOUS,
        has_communicated=False,
        has_conflict=True,
        description="舍友晚上打游戏声音很大，已经连续影响我睡眠好几次。",
    )

    result = analyze_pressure(request)

    assert result.pressure_score == 76
    assert result.risk_level == "high"
    assert result.risk_label == "冲突风险较高"
    assert result.emotion_keywords == ["焦虑"]
    assert result.recommend_simulation is True
    assert "噪音冲突" in result.main_sources
    assert "沟通演练" in result.suggestion
    assert "不作为心理诊断依据" in result.disclaimer


def test_analyze_pressure_marks_low_risk_for_occasional_communicated_issue():
    request = AnalyzeRequest(
        event_type=EventType.HYGIENE,
        severity=1,
        frequency=EventFrequency.OCCASIONAL,
        emotion=Emotion.HELPLESS,
        has_communicated=True,
        has_conflict=False,
        description="这周公共区域有点乱，但我们已经沟通过一次。",
    )

    result = analyze_pressure(request)

    assert result.pressure_score == 28
    assert result.risk_level == "stable"
    assert result.risk_label == "关系平稳"
    assert result.recommend_simulation is False
    assert "继续保持" in result.suggestion


def test_analyze_request_trims_description():
    request = AnalyzeRequest(
        event_type=EventType.HYGIENE,
        severity=1,
        frequency=EventFrequency.OCCASIONAL,
        emotion=Emotion.HELPLESS,
        has_communicated=True,
        has_conflict=False,
        description="  公共区域有点乱  ",
    )

    assert request.description == "公共区域有点乱"


def test_analyze_request_accepts_multiple_emotions_and_primary_emotion():
    request = AnalyzeRequest(
        event_type=EventType.NOISE,
        severity=4,
        frequency=EventFrequency.WEEKLY_MULTIPLE,
        emotion=Emotion.HELPLESS,
        emotions=[Emotion.HELPLESS, Emotion.ANGRY, Emotion.WRONGED],
        primary_emotion=Emotion.HELPLESS,
        has_communicated=False,
        has_conflict=True,
        description="舍友晚上打游戏声音很大，我很无奈也有点生气。",
    )

    result = analyze_pressure(request)

    assert request.emotion == Emotion.HELPLESS
    assert request.primary_emotion == Emotion.HELPLESS
    assert request.emotions == [Emotion.HELPLESS, Emotion.ANGRY, Emotion.WRONGED]
    assert result.emotion_keywords == ["无奈", "愤怒", "委屈"]
    assert result.pressure_score > 70


def test_analyze_request_deduplicates_emotions_and_keeps_primary_in_selection():
    request = AnalyzeRequest(
        event_type=EventType.NOISE,
        severity=3,
        frequency=EventFrequency.OCCASIONAL,
        emotions=[Emotion.ANGRY, Emotion.HELPLESS, Emotion.ANGRY],
        primary_emotion=Emotion.HELPLESS,
        has_communicated=True,
        has_conflict=False,
        description="我有点生气，也很无奈。",
    )

    assert request.emotion == Emotion.HELPLESS
    assert request.primary_emotion == Emotion.HELPLESS
    assert request.emotions == [Emotion.ANGRY, Emotion.HELPLESS]


def test_analyze_request_rejects_primary_emotion_outside_emotions():
    with pytest.raises(ValidationError):
        AnalyzeRequest(
            event_type=EventType.NOISE,
            severity=3,
            frequency=EventFrequency.OCCASIONAL,
            emotions=[Emotion.ANGRY, Emotion.WRONGED],
            primary_emotion=Emotion.HELPLESS,
            has_communicated=True,
            has_conflict=False,
            description="我有点生气，也很委屈。",
        )


def test_analyze_pressure_keeps_frontend_emotion_labels_for_helpless_and_depressed():
    helpless = AnalyzeRequest(
        event_type=EventType.HYGIENE,
        severity=1,
        frequency=EventFrequency.OCCASIONAL,
        emotion=Emotion.HELPLESS,
        has_communicated=True,
        has_conflict=False,
        description="这周公共区域有点乱，但我们已经沟通过一次。",
    )
    depressed = helpless.model_copy(update={"emotion": Emotion.DEPRESSED})

    assert analyze_pressure(helpless).emotion_keywords == ["无奈"]
    assert analyze_pressure(depressed).emotion_keywords == ["压抑"]


def test_analyze_request_rejects_blank_description():
    with pytest.raises(ValidationError):
        AnalyzeRequest(
            event_type=EventType.HYGIENE,
            severity=1,
            frequency=EventFrequency.OCCASIONAL,
            emotion=Emotion.HELPLESS,
            has_communicated=True,
            has_conflict=False,
            description="   ",
        )


def test_analyze_request_rejects_too_long_description():
    with pytest.raises(ValidationError):
        AnalyzeRequest(
            event_type=EventType.HYGIENE,
            severity=1,
            frequency=EventFrequency.OCCASIONAL,
            emotion=Emotion.HELPLESS,
            has_communicated=True,
            has_conflict=False,
            description="a" * 501,
        )


def test_analyze_request_rejects_non_string_description_as_validation_error():
    with pytest.raises(ValidationError):
        AnalyzeRequest(
            event_type=EventType.HYGIENE,
            severity=1,
            frequency=EventFrequency.OCCASIONAL,
            emotion=Emotion.HELPLESS,
            has_communicated=True,
            has_conflict=False,
            description=123,
        )


def test_phase2_scoring_regression_keeps_inputs_distinct():
    low_request = AnalyzeRequest(
        event_type=EventType.HYGIENE,
        severity=1,
        frequency=EventFrequency.OCCASIONAL,
        emotion=Emotion.HELPLESS,
        has_communicated=True,
        has_conflict=False,
        description="公共区域偶尔有点乱，但已经沟通过。",
    )
    high_request = AnalyzeRequest(
        event_type=EventType.NOISE,
        severity=5,
        frequency=EventFrequency.DAILY,
        emotion=Emotion.DEPRESSED,
        has_communicated=False,
        has_conflict=True,
        description="舍友每天深夜打游戏，长期影响睡眠并已经冷战。",
    )

    low_result = analyze_pressure(low_request)
    high_result = analyze_pressure(high_request)

    assert low_result.pressure_score < high_result.pressure_score
    assert low_result.risk_level == "stable"
    assert high_result.risk_level == "severe"
