from datetime import date, datetime

import pytest
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from app.ai_prompts import (
    ARCHIVE_INSIGHT_SYSTEM_PROMPT,
    REVIEW_SYSTEM_PROMPT,
    SIMULATE_SYSTEM_PROMPT,
    build_archive_insight_messages,
    build_review_messages,
    build_simulate_messages,
)
from app.demo_data import DEMO_SCENARIOS
from app.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    ArchiveInsightResponse,
    ArchiveAnalysisResponse,
    DialogueMessage,
    EventRecord,
    EventRecordCreate,
    ReviewRequest,
    ReviewResponse,
    RoommateReply,
    SimulateRequest,
    SimulateResponse,
)


REVIEW_PERFORMANCE_SCORES = {"clarity": 82, "empathy": 76, "resolution": 71}


def test_analyze_response_rejects_unknown_risk_level():
    with pytest.raises(ValidationError):
        AnalyzeResponse(
            pressure_score=90,
            risk_level="critical",
            risk_label="未知风险",
            main_sources=["噪音冲突"],
            emotion_keywords=["焦虑"],
            trend_message="当前压力较高。",
            suggestion="建议先进行沟通演练。",
            recommend_simulation=True,
            disclaimer="本结果不作为心理诊断依据。",
        )


def test_simulate_request_trims_optional_context_to_none():
    request = SimulateRequest(
        scenario="  舍友晚上打游戏声音较大，影响睡眠  ",
        user_message="  能不能晚上小声一点？  ",
        risk_level="high",
        context="   ",
    )

    assert request.scenario == "舍友晚上打游戏声音较大，影响睡眠"
    assert request.user_message == "能不能晚上小声一点？"
    assert request.context is None


def test_simulate_request_normalizes_blank_risk_level_to_none():
    request = SimulateRequest(
        scenario="噪音冲突",
        user_message="能不能晚上小声一点？",
        risk_level="   ",
    )

    assert request.risk_level is None


def test_simulate_request_accepts_prior_dialogue_for_continuous_conversation():
    request = SimulateRequest(
        scenario="舍友晚上打游戏声音很大，影响睡眠。",
        user_message="那我们能不能约定 11 点后戴耳机？",
        risk_level="high",
        dialogue=[
            {"speaker": "user", "message": "晚上能不能小声一点？"},
            {"speaker": "roommate_a", "message": "我也没开很大声吧。"},
        ],
    )

    assert len(request.dialogue) == 2
    assert request.dialogue[1].speaker == "roommate_a"


def test_simulate_request_rejects_unknown_risk_level():
    with pytest.raises(ValidationError):
        SimulateRequest(
            scenario="噪音冲突",
            user_message="能不能晚上小声一点？",
            risk_level="critical",
        )


def test_simulate_request_rejects_blank_user_message():
    with pytest.raises(ValidationError):
        SimulateRequest(scenario="噪音冲突", user_message="   ")


def test_simulate_response_requires_three_fixed_roommate_roles():
    response = SimulateResponse(
        replies=[
            RoommateReply(roommate="舍友 A", personality="直接型", message="我也没开很大声吧。"),
            RoommateReply(roommate="舍友 B", personality="回避型", message="这个之后再说吧。"),
            RoommateReply(roommate="舍友 C", personality="调和型", message="我们可以定个休息规则。"),
        ],
        safety_note="本回复仅用于宿舍沟通演练，不代表真实舍友想法，不进行心理诊断，不进行医学判断，不进行人格评价。如有现实安全风险，请联系辅导员、心理老师、家人或可信任同学。",
    )

    assert [(reply.roommate, reply.personality) for reply in response.replies] == [
        ("舍友 A", "直接型"),
        ("舍友 B", "回避型"),
        ("舍友 C", "调和型"),
    ]


def test_simulate_response_rejects_missing_fixed_role():
    with pytest.raises(ValidationError):
        SimulateResponse(
            replies=[
                RoommateReply(roommate="舍友 A", personality="直接型", message="我也没开很大声吧。"),
                RoommateReply(roommate="舍友 C", personality="调和型", message="我们可以定个休息规则。"),
            ],
            safety_note="本回复仅用于宿舍沟通演练，不代表真实舍友想法，不进行心理诊断，不进行医学判断，不进行人格评价。如有现实安全风险，请联系辅导员。",
        )


def test_simulate_response_rejects_unsafe_safety_note():
    with pytest.raises(ValidationError):
        SimulateResponse(
            replies=[
                RoommateReply(roommate="舍友 A", personality="直接型", message="我也没开很大声吧。"),
                RoommateReply(roommate="舍友 B", personality="回避型", message="这个之后再说吧。"),
                RoommateReply(roommate="舍友 C", personality="调和型", message="我们可以定个休息规则。"),
            ],
            safety_note="祝你沟通顺利。",
        )


def test_simulate_response_rejects_safety_note_missing_virtual_roommate_boundary():
    with pytest.raises(ValidationError):
        SimulateResponse(
            replies=[
                RoommateReply(roommate="舍友 A", personality="直接型", message="我也没开很大声吧。"),
                RoommateReply(roommate="舍友 B", personality="回避型", message="这个之后再说吧。"),
                RoommateReply(roommate="舍友 C", personality="调和型", message="我们可以定个休息规则。"),
            ],
            safety_note="本回复仅用于宿舍沟通演练，不进行心理诊断，不进行医学判断，不进行人格评价。如有现实安全风险，请联系辅导员。",
        )


def test_simulate_response_rejects_safety_note_missing_rehearsal_purpose():
    with pytest.raises(ValidationError):
        SimulateResponse(
            replies=[
                RoommateReply(roommate="舍友 A", personality="直接型", message="我也没开很大声吧。"),
                RoommateReply(roommate="舍友 B", personality="回避型", message="这个之后再说吧。"),
                RoommateReply(roommate="舍友 C", personality="调和型", message="我们可以定个休息规则。"),
            ],
            safety_note="不代表真实舍友想法，不进行心理诊断，不进行医学判断，不进行人格评价。如有现实安全风险，请联系辅导员。",
        )


def test_review_request_requires_at_least_one_dialogue_message():
    with pytest.raises(ValidationError):
        ReviewRequest(scenario="噪音冲突", dialogue=[])


def test_review_request_rejects_more_than_twenty_dialogue_messages():
    with pytest.raises(ValidationError):
        ReviewRequest(
            scenario="噪音冲突",
            dialogue=[
                DialogueMessage(speaker="user", message=f"第 {index} 条消息")
                for index in range(21)
            ],
        )


def test_review_request_rejects_unapproved_original_event_fields():
    with pytest.raises(ValidationError):
        ReviewRequest(
            scenario="噪音冲突",
            dialogue=[DialogueMessage(speaker="user", message="晚上能不能小声一点？")],
            original_event={
                "event_type": "noise",
                "full_browser_payload": {"unbounded": ["raw"]},
            },
        )


def test_review_request_rejects_overlong_original_event_text():
    with pytest.raises(ValidationError):
        ReviewRequest(
            scenario="噪音冲突",
            dialogue=[DialogueMessage(speaker="user", message="晚上能不能小声一点？")],
            original_event={
                "event_type": "noise",
                "description": "声音很大" * 200,
            },
        )


def test_review_request_accepts_controlled_original_event_summary():
    request = ReviewRequest(
        scenario="噪音冲突",
        dialogue=[DialogueMessage(speaker="user", message="晚上能不能小声一点？")],
        original_event={
            "event_type": "noise",
            "frequency": "daily",
            "risk_level": "high",
            "pressure_score": 76,
            "description": "舍友连续几天晚上打游戏，影响睡眠。",
        },
    )

    assert request.original_event is not None
    assert request.original_event.event_type == "noise"
    assert request.original_event.frequency == "daily"
    assert request.original_event.risk_level == "high"
    assert request.original_event.pressure_score == 76
    assert request.original_event.description == "舍友连续几天晚上打游戏，影响睡眠。"


def test_build_review_messages_serializes_controlled_original_event():
    request = ReviewRequest(
        scenario="噪音冲突",
        dialogue=[DialogueMessage(speaker="user", message="晚上能不能小声一点？")],
        original_event={
            "event_type": "noise",
            "frequency": "daily",
            "risk_level": "high",
            "pressure_score": 76,
        },
    )

    messages = build_review_messages(request)

    message_content = str(messages[-1].content)
    assert '"event_type": "noise"' in message_content
    assert '"frequency": "daily"' in message_content
    assert '"pressure_score": 76' in message_content


def test_build_simulate_messages_includes_prior_dialogue_before_current_message():
    request = SimulateRequest(
        scenario="舍友晚上打游戏声音很大，影响睡眠。",
        user_message="那我们能不能约定 11 点后戴耳机？",
        dialogue=[
            {"speaker": "user", "message": "晚上能不能小声一点？"},
            {"speaker": "roommate_a", "message": "我也没开很大声吧。"},
        ],
    )

    messages = build_simulate_messages(request)

    message_content = str(messages[-1].content)
    assert "如果 dialogue 非空，请把本次 user_message 视为同一场景下的下一轮对话" in message_content
    assert "user: 晚上能不能小声一点？" in message_content
    assert "roommate_a: 我也没开很大声吧。" in message_content
    assert message_content.index("roommate_a: 我也没开很大声吧。") < message_content.index(
        "user_message: 那我们能不能约定 11 点后戴耳机？"
    )


def test_archive_insight_response_requires_actionable_safety_bounded_fields():
    response = ArchiveInsightResponse(
        insight="近 30 天噪音事件集中出现，主要压力来自休息边界被反复打断。",
        care_suggestion="先照顾睡眠和情绪稳定，再选择白天提出具体规则。",
        communication_focus=["围绕 11 点后的安静规则沟通", "先确认对方是否能接受耳机方案"],
        safety_note=(
            "本建议仅用于沟通训练建议，不代表真实舍友想法，不进行心理诊断，"
            "不进行医学判断，不进行人格评价；如压力持续升高，请联系辅导员或心理老师寻求现实支持。"
        ),
    )

    assert response.communication_focus[0] == "围绕 11 点后的安静规则沟通"


def test_archive_insight_response_rejects_empty_focus_item():
    with pytest.raises(ValidationError):
        ArchiveInsightResponse(
            insight="近 30 天噪音事件集中出现。",
            care_suggestion="先照顾睡眠和情绪稳定。",
            communication_focus=["   "],
            safety_note=(
                "本建议仅用于沟通训练建议，不代表真实舍友想法，不进行心理诊断，"
                "不进行医学判断，不进行人格评价；如压力持续升高，请联系辅导员或心理老师寻求现实支持。"
            ),
        )


def test_archive_insight_response_rejects_unsafe_safety_note():
    with pytest.raises(ValidationError):
        ArchiveInsightResponse(
            insight="近 30 天噪音事件集中出现。",
            care_suggestion="先照顾睡眠和情绪稳定。",
            communication_focus=["围绕 11 点后的安静规则沟通"],
            safety_note="祝你沟通顺利。",
        )


def test_build_archive_insight_messages_serializes_events_and_analysis():
    event_payload = EventRecordCreate(
        event_date=date(2026, 5, 15),
        event_type="noise",
        severity=4,
        frequency="weekly_multiple",
        emotion="anxious",
        has_communicated=False,
        has_conflict=True,
        description="舍友晚上打游戏声音很大，影响睡眠。",
    )
    event = EventRecord(
        **event_payload.model_dump(),
        id="event-1",
        created_at=datetime(2026, 5, 15, 8, 0, 0),
        single_analysis=AnalyzeResponse(
            pressure_score=76,
            risk_level="high",
            risk_label="冲突风险较高",
            main_sources=["噪音冲突"],
            emotion_keywords=["焦虑"],
            trend_message="当前压力值为 76。",
            suggestion="建议先进行沟通演练。",
            recommend_simulation=True,
            disclaimer="本结果不作为心理诊断依据。",
        ),
    )
    analysis = ArchiveAnalysisResponse(
        pressure_score=76,
        risk_level="high",
        risk_label="冲突风险较高",
        main_sources=["噪音冲突"],
        emotion_keywords=["焦虑"],
        trend_message="事件档案共记录 1 条事件。",
        suggestion="建议先进行沟通演练。",
        recommend_simulation=True,
        disclaimer="本结果不作为心理诊断依据。",
        event_count=1,
        active_30d_count=1,
        source_breakdown=[],
    )

    messages = build_archive_insight_messages([event], analysis)

    message_content = str(messages[-1].content)
    assert "events:" in message_content
    assert "archive_analysis:" in message_content
    assert "舍友晚上打游戏声音很大" in message_content
    assert '"event_date": "2026-05-15"' in message_content
    assert '"event_type": "noise"' in message_content
    assert '"severity": 4' in message_content
    assert '"frequency": "weekly_multiple"' in message_content
    assert '"emotion": "anxious"' in message_content
    assert '"has_communicated": false' in message_content
    assert '"has_conflict": true' in message_content
    assert '"description": "舍友晚上打游戏声音很大，影响睡眠。"' in message_content
    assert '"pressure_score": 76' in message_content
    assert "event-1" not in message_content
    assert "created_at" not in message_content
    assert "single_analysis" not in message_content
    assert "本结果不作为心理诊断依据" not in message_content
    assert "disclaimer" not in message_content


def test_review_response_requires_actionable_lists():
    response = ReviewResponse(
        summary="用户表达了睡眠受影响的事实，整体语气较温和。",
        strengths=["说明了具体影响"],
        risks=["可以进一步明确时间范围"],
        performance_scores=REVIEW_PERFORMANCE_SCORES,
        rewritten_message="我最近睡眠状态不太好，晚上 11 点后能不能戴耳机或调低音量？",
        next_steps=["选择双方情绪平稳的时间沟通"],
        safety_note="本复盘仅用于沟通训练建议，不代表真实舍友想法，不进行心理诊断，不进行医学判断，不进行人格评价。如压力持续升高，请寻求现实支持。",
    )

    assert response.strengths == ["说明了具体影响"]
    assert response.performance_scores.clarity == 82
    assert response.performance_scores.empathy == 76
    assert response.performance_scores.resolution == 71


def test_review_response_rejects_empty_actionable_lists():
    with pytest.raises(ValidationError):
        ReviewResponse(
            summary="用户表达了睡眠受影响的事实，整体语气较温和。",
            strengths=[],
            risks=["可以进一步明确时间范围"],
            performance_scores=REVIEW_PERFORMANCE_SCORES,
            rewritten_message="我最近睡眠状态不太好，晚上 11 点后能不能戴耳机或调低音量？",
            next_steps=["选择双方情绪平稳的时间沟通"],
            safety_note="本复盘仅用于沟通训练建议，不代表真实舍友想法，不进行心理诊断，不进行医学判断，不进行人格评价。如压力持续升高，请寻求现实支持。",
        )


def test_review_response_rejects_performance_scores_outside_0_to_100():
    with pytest.raises(ValidationError):
        ReviewResponse(
            summary="用户表达了睡眠受影响的事实，整体语气较温和。",
            strengths=["说明了具体影响"],
            risks=["可以进一步明确时间范围"],
            performance_scores={"clarity": 101, "empathy": 76, "resolution": 71},
            rewritten_message="我最近睡眠状态不太好，晚上 11 点后能不能戴耳机或调低音量？",
            next_steps=["选择双方情绪平稳的时间沟通"],
            safety_note="本复盘仅用于沟通训练建议，不代表真实舍友想法，不进行心理诊断，不进行医学判断，不进行人格评价。如压力持续升高，请寻求现实支持。",
        )


def test_review_response_rejects_unsafe_safety_note():
    with pytest.raises(ValidationError):
        ReviewResponse(
            summary="用户表达了睡眠受影响的事实，整体语气较温和。",
            strengths=["说明了具体影响"],
            risks=["可以进一步明确时间范围"],
            performance_scores=REVIEW_PERFORMANCE_SCORES,
            rewritten_message="我最近睡眠状态不太好，晚上 11 点后能不能戴耳机或调低音量？",
            next_steps=["选择双方情绪平稳的时间沟通"],
            safety_note="本建议仅供参考。",
        )


def test_review_response_rejects_safety_note_missing_virtual_roommate_boundary():
    with pytest.raises(ValidationError):
        ReviewResponse(
            summary="用户表达了睡眠受影响的事实，整体语气较温和。",
            strengths=["说明了具体影响"],
            risks=["可以进一步明确时间范围"],
            performance_scores=REVIEW_PERFORMANCE_SCORES,
            rewritten_message="我最近睡眠状态不太好，晚上 11 点后能不能戴耳机或调低音量？",
            next_steps=["选择双方情绪平稳的时间沟通"],
            safety_note="本复盘仅用于沟通训练建议，不进行心理诊断，不进行医学判断，不进行人格评价。如压力持续升高，请寻求现实支持。",
        )


def test_review_response_rejects_safety_note_missing_training_purpose():
    with pytest.raises(ValidationError):
        ReviewResponse(
            summary="用户表达了睡眠受影响的事实，整体语气较温和。",
            strengths=["说明了具体影响"],
            risks=["可以进一步明确时间范围"],
            performance_scores=REVIEW_PERFORMANCE_SCORES,
            rewritten_message="我最近睡眠状态不太好，晚上 11 点后能不能戴耳机或调低音量？",
            next_steps=["选择双方情绪平稳的时间沟通"],
            safety_note="不代表真实舍友想法，不进行心理诊断，不进行医学判断，不进行人格评价。如压力持续升高，请寻求现实支持。",
        )


def test_prompts_contain_role_and_safety_boundaries():
    required_phrases = [
        "大学宿舍关系沟通场景",
        "不进行心理疾病诊断",
        "不进行医学判断",
        "不进行人格评价",
        "不得输出攻击",
        "辅导员",
        "心理老师",
    ]

    for phrase in required_phrases:
        assert phrase in SIMULATE_SYSTEM_PROMPT
        assert phrase in REVIEW_SYSTEM_PROMPT
        assert phrase in ARCHIVE_INSIGHT_SYSTEM_PROMPT

    assert "舍友 A" in SIMULATE_SYSTEM_PROMPT
    assert "直接型" in SIMULATE_SYSTEM_PROMPT
    assert "舍友 B" in SIMULATE_SYSTEM_PROMPT
    assert "回避型" in SIMULATE_SYSTEM_PROMPT
    assert "舍友 C" in SIMULATE_SYSTEM_PROMPT
    assert "调和型" in SIMULATE_SYSTEM_PROMPT


def test_prompts_include_schema_accepted_safety_note_phrases():
    assert "仅用于宿舍沟通演练" in SIMULATE_SYSTEM_PROMPT
    assert "仅用于沟通训练建议" in REVIEW_SYSTEM_PROMPT
    assert "仅用于沟通训练建议" in ARCHIVE_INSIGHT_SYSTEM_PROMPT
    assert "不代表真实舍友想法" in SIMULATE_SYSTEM_PROMPT
    assert "不代表真实舍友想法" in REVIEW_SYSTEM_PROMPT
    assert "不代表真实舍友想法" in ARCHIVE_INSIGHT_SYSTEM_PROMPT


def test_prompts_include_deepseek_json_output_contract():
    for prompt in (SIMULATE_SYSTEM_PROMPT, REVIEW_SYSTEM_PROMPT):
        assert "JSON" in prompt
        assert "不要输出 Markdown" in prompt
        assert "safety_note" in prompt

    for field_name in ("roommate", "personality", "message"):
        assert field_name in SIMULATE_SYSTEM_PROMPT

    for field_name in (
        "summary",
        "strengths",
        "risks",
        "performance_scores",
        "clarity",
        "empathy",
        "resolution",
        "rewritten_message",
        "next_steps",
    ):
        assert field_name in REVIEW_SYSTEM_PROMPT


def test_prompt_builders_return_langchain_message_objects():
    simulate_request = SimulateRequest(
        scenario="舍友晚上打游戏声音较大，影响睡眠",
        user_message="我想商量一下晚上能不能小声一点。",
    )
    review_request = ReviewRequest(
        scenario="舍友晚上打游戏声音较大，影响睡眠",
        dialogue=[
            DialogueMessage(speaker="user", message="我想商量一下晚上能不能小声一点。"),
        ],
    )

    simulate_messages = build_simulate_messages(simulate_request)
    review_messages = build_review_messages(review_request)

    assert isinstance(simulate_messages[0], SystemMessage)
    assert isinstance(simulate_messages[1], HumanMessage)
    assert isinstance(review_messages[0], SystemMessage)
    assert isinstance(review_messages[1], HumanMessage)


def test_prompt_builders_include_user_inputs():
    simulate_request = SimulateRequest(
        scenario="舍友晚上打游戏声音较大，影响睡眠",
        user_message="我想商量一下晚上能不能小声一点。",
        risk_level="high",
        context="用户尚未正式沟通。",
    )
    review_request = ReviewRequest(
        scenario="舍友晚上打游戏声音较大，影响睡眠",
        dialogue=[
            DialogueMessage(speaker="user", message="我想商量一下晚上能不能小声一点。"),
            DialogueMessage(speaker="roommate_a", message="我也没开很大声吧。"),
        ],
    )

    simulate_messages = build_simulate_messages(simulate_request)
    review_messages = build_review_messages(review_request)

    assert "我想商量一下晚上能不能小声一点" in str(simulate_messages[-1].content)
    assert "用户尚未正式沟通" in str(simulate_messages[-1].content)
    assert "roommate_a" in str(review_messages[-1].content)
    assert "我也没开很大声吧" in str(review_messages[-1].content)


def test_demo_scenarios_cover_required_phase2_cases():
    scenario_ids = {sample["id"] for sample in DEMO_SCENARIOS}

    assert {"noise_conflict", "hygiene_division", "privacy_boundary"}.issubset(scenario_ids)

    for sample in DEMO_SCENARIOS:
        assert sample["analyze_request"]["description"]
        assert sample["simulate_request"]["scenario"]
        assert sample["simulate_request"]["user_message"]
        assert len(sample["review_request"]["dialogue"]) >= 1
        AnalyzeRequest(**sample["analyze_request"])
        SimulateRequest(**sample["simulate_request"])
        ReviewRequest(**sample["review_request"])
