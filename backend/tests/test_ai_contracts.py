from datetime import date, datetime

import pytest
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

import app.schemas as schemas
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
SIMULATE_SAFETY_NOTE = (
    "本回复仅用于宿舍沟通演练，不代表真实舍友想法，不进行心理诊断，"
    "不进行医学判断，不进行人格评价。如有现实安全风险，请联系辅导员、"
    "心理老师、家人或可信任同学。"
)
REVIEW_SAFETY_NOTE = (
    "本复盘仅用于沟通训练建议，不代表真实舍友想法，不进行心理诊断，"
    "不进行医学判断，不进行人格评价。如压力持续升高，请寻求现实支持或联系辅导员、心理老师。"
)
REVIEW_REWRITE_SUGGESTIONS = [
    {
        "message_index": 0,
        "original_message": "你能不能小声点？",
        "issue": "请求较笼统。",
        "suggested_message": "我最近睡眠受影响，能不能 11 点后戴耳机？",
        "reason": "把影响和行动说清楚。",
    }
]


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


def test_analyze_request_keeps_legacy_emotion_as_primary_emotion():
    request = AnalyzeRequest(
        event_type="noise",
        severity=4,
        frequency="weekly_multiple",
        emotion="anxious",
        has_communicated=False,
        has_conflict=True,
        description="舍友晚上打游戏声音很大。",
    )

    assert request.emotion == "anxious"
    assert request.primary_emotion == "anxious"
    assert request.emotions == ["anxious"]


def test_analyze_request_rejects_conflicting_primary_emotion_and_legacy_emotion():
    with pytest.raises(ValidationError):
        AnalyzeRequest(
            event_type="noise",
            severity=4,
            frequency="weekly_multiple",
            emotion="angry",
            emotions=["anxious", "angry"],
            primary_emotion="anxious",
            has_communicated=False,
            has_conflict=True,
            description="舍友晚上打游戏声音很大。",
        )


def test_simulate_request_supports_continuation_without_user_message_and_max_replies():
    request = SimulateRequest(
        conversation_id="conversation-1",
        scenario="噪音冲突",
        is_continuation=True,
        max_replies=1,
    )

    assert request.user_message is None
    assert request.is_continuation is True
    assert request.max_replies == 1


def test_simulate_request_requires_user_message_for_new_user_turn():
    with pytest.raises(ValidationError):
        SimulateRequest(scenario="噪音冲突")


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


def test_review_request_accepts_dynamic_roommate_dialogue_speakers():
    request = ReviewRequest(
        scenario="自定义舍友沟通",
        dialogue=[
            {"speaker": "user", "message": "我想商量一下晚上的声音。"},
            {"speaker": "roommate_custom_4", "message": "我尽量注意。"},
        ],
    )

    assert request.dialogue[1].speaker == "roommate_custom_4"


def test_roommate_profile_accepts_presets_and_custom_traits():
    direct = schemas.RoommateProfile(
        id="roommate_a",
        name="舍友 A",
        personality_tag="直接型",
        tag_mode="preset",
        preset_key="direct",
        avatar="nailong",
    )
    custom = schemas.RoommateProfile(
        id="roommate_quiet_custom",
        name="小林",
        personality_tag="慢热型",
        tag_mode="custom",
        avatar="capybara_lulu",
        traits={
            "directness": 2,
            "emotional_reactivity": 1,
            "avoidance": 4,
            "empathy": 3,
            "solution_willingness": 2,
            "boundary_sensitivity": 5,
        },
    )

    assert direct.traits.directness == 5
    assert direct.traits.emotional_reactivity == 3
    assert direct.traits.avoidance == 1
    assert direct.traits.empathy == 2
    assert direct.traits.solution_willingness == 3
    assert direct.traits.boundary_sensitivity == 4
    assert direct.avatar == "nailong"
    assert custom.traits.boundary_sensitivity == 5
    assert custom.avatar == "capybara_lulu"


def test_roommate_profile_rejects_custom_without_complete_traits():
    with pytest.raises(ValidationError):
        schemas.RoommateProfile(
            id="roommate_quiet_custom",
            name="小林",
            personality_tag="慢热型",
            tag_mode="custom",
        )

    with pytest.raises(ValidationError):
        schemas.RoommateProfile(
            id="roommate_quiet_custom",
            name="小林",
            personality_tag="慢热型",
            tag_mode="custom",
            traits={
                "directness": 2,
                "emotional_reactivity": 1,
                "avoidance": 4,
                "empathy": 3,
                "solution_willingness": 2,
            },
        )


def test_roommate_profile_rejects_id_outside_roommate_namespace():
    with pytest.raises(ValidationError):
        schemas.RoommateProfile(
            id="quiet_custom",
            name="小林",
            personality_tag="慢热型",
            tag_mode="custom",
            traits={
                "directness": 2,
                "emotional_reactivity": 1,
                "avoidance": 4,
                "empathy": 3,
                "solution_willingness": 2,
                "boundary_sensitivity": 5,
            },
        )


def test_roommate_profile_accepts_trait_bounds_and_rejects_out_of_range_traits():
    minimum = schemas.RoommateProfile(
        id="roommate_minimum_custom",
        name="小周",
        personality_tag="低反应型",
        tag_mode="custom",
        traits={
            "directness": 0,
            "emotional_reactivity": 0,
            "avoidance": 0,
            "empathy": 0,
            "solution_willingness": 0,
            "boundary_sensitivity": 0,
        },
    )
    maximum = schemas.RoommateProfile(
        id="roommate_maximum_custom",
        name="小吴",
        personality_tag="高反应型",
        tag_mode="custom",
        traits={
            "directness": 5,
            "emotional_reactivity": 5,
            "avoidance": 5,
            "empathy": 5,
            "solution_willingness": 5,
            "boundary_sensitivity": 5,
        },
    )

    assert minimum.traits.directness == 0
    assert maximum.traits.boundary_sensitivity == 5

    with pytest.raises(ValidationError):
        schemas.RoommateProfile(
            id="roommate_invalid_custom",
            name="小许",
            personality_tag="越界型",
            tag_mode="custom",
            traits={
                "directness": 6,
                "emotional_reactivity": 3,
                "avoidance": 2,
                "empathy": 3,
                "solution_willingness": 4,
                "boundary_sensitivity": 5,
            },
        )


def test_simulate_request_defaults_to_three_roommates_and_rejects_duplicate_ids():
    request = SimulateRequest(scenario="噪音冲突", user_message="能不能小声一点？")

    assert [roommate.id for roommate in request.roommates] == [
        "roommate_a",
        "roommate_b",
        "roommate_c",
    ]
    assert [roommate.preset_key for roommate in request.roommates] == [
        "direct",
        "avoidant",
        "harmony",
    ]
    assert [roommate.avatar for roommate in request.roommates] == [
        "nailong",
        "capybara_lulu",
        "baobaolong",
    ]

    with pytest.raises(ValidationError):
        SimulateRequest(
            scenario="噪音冲突",
            user_message="能不能小声一点？",
            roommates=[
                {
                    "id": "same",
                    "name": "舍友 A",
                    "personality_tag": "直接型",
                    "tag_mode": "preset",
                    "preset_key": "direct",
                },
                {
                    "id": "same",
                    "name": "舍友 B",
                    "personality_tag": "回避型",
                    "tag_mode": "preset",
                    "preset_key": "avoidant",
                },
            ],
        )


def test_simulate_request_assigns_missing_roommate_avatars_and_rejects_duplicate_avatars():
    request = SimulateRequest(
        scenario="噪音冲突",
        user_message="能不能小声一点？",
        roommates=[
            {
                "id": "roommate_a",
                "name": "舍友 A",
                "personality_tag": "直接型",
                "tag_mode": "preset",
                "preset_key": "direct",
            },
            {
                "id": "roommate_b",
                "name": "舍友 B",
                "personality_tag": "回避型",
                "tag_mode": "preset",
                "preset_key": "avoidant",
                "avatar": "patrick",
            },
        ],
    )

    assert [roommate.avatar for roommate in request.roommates] == ["nailong", "patrick"]

    with pytest.raises(ValidationError):
        SimulateRequest(
            scenario="噪音冲突",
            user_message="能不能小声一点？",
            roommates=[
                {
                    "id": "roommate_a",
                    "name": "舍友 A",
                    "personality_tag": "直接型",
                    "tag_mode": "preset",
                    "preset_key": "direct",
                    "avatar": "nailong",
                },
                {
                    "id": "roommate_b",
                    "name": "舍友 B",
                    "personality_tag": "回避型",
                    "tag_mode": "preset",
                    "preset_key": "avoidant",
                    "avatar": "nailong",
                },
            ],
        )


def test_simulate_request_accepts_one_to_five_roommates_and_rejects_out_of_range_counts():
    one_roommate = SimulateRequest(
        scenario="噪音冲突",
        user_message="能不能小声一点？",
        roommates=[
            {
                "id": "roommate_a",
                "name": "舍友 A",
                "personality_tag": "直接型",
                "tag_mode": "preset",
                "preset_key": "direct",
            }
        ],
    )
    five_roommates = SimulateRequest(
        scenario="噪音冲突",
        user_message="能不能小声一点？",
        roommates=[
            {
                "id": f"roommate_{index}",
                "name": f"舍友 {index}",
                "personality_tag": "调和型",
                "tag_mode": "preset",
                "preset_key": "harmony",
            }
            for index in range(5)
        ],
    )

    assert len(one_roommate.roommates) == 1
    assert len(five_roommates.roommates) == 5

    with pytest.raises(ValidationError):
        SimulateRequest(
            scenario="噪音冲突",
            user_message="能不能小声一点？",
            roommates=[],
        )

    with pytest.raises(ValidationError):
        SimulateRequest(
            scenario="噪音冲突",
            user_message="能不能小声一点？",
            roommates=[
                {
                    "id": f"roommate_{index}",
                    "name": f"舍友 {index}",
                    "personality_tag": "直接型",
                    "tag_mode": "preset",
                    "preset_key": "direct",
                }
                for index in range(6)
            ],
        )


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


def test_simulate_response_allows_zero_to_fifteen_dynamic_replies():
    empty_response = SimulateResponse(
        conversation_id="conversation-1",
        replies=[],
        safety_note=SIMULATE_SAFETY_NOTE,
    )
    full_response = SimulateResponse(
        conversation_id="conversation-1",
        replies=[
            RoommateReply(
                roommate_id=f"roommate_{index % 5}",
                roommate=f"舍友 {index % 5}",
                personality="自定义",
                message=f"第 {index} 条回复。",
            )
            for index in range(15)
        ],
        safety_note=SIMULATE_SAFETY_NOTE,
    )

    assert empty_response.conversation_id == "conversation-1"
    assert empty_response.replies == []
    assert len(full_response.replies) == 15


def test_simulate_response_rejects_more_than_fifteen_dynamic_replies():
    with pytest.raises(ValidationError):
        SimulateResponse(
            conversation_id="conversation-1",
            replies=[
                RoommateReply(
                    roommate_id=f"roommate_{index}",
                    roommate=f"舍友 {index}",
                    personality="自定义",
                    message="我知道了。",
                )
                for index in range(16)
            ],
            safety_note=SIMULATE_SAFETY_NOTE,
        )


def test_simulate_response_rejects_unsafe_safety_note():
    with pytest.raises(ValidationError):
        SimulateResponse(
            conversation_id="conversation-1",
            replies=[
                RoommateReply(
                    roommate_id="roommate_a",
                    roommate="舍友 A",
                    personality="直接型",
                    message="我也没开很大声吧。",
                ),
            ],
            safety_note="祝你沟通顺利。",
        )


def test_simulate_response_rejects_safety_note_missing_virtual_roommate_boundary():
    with pytest.raises(ValidationError):
        SimulateResponse(
            conversation_id="conversation-1",
            replies=[
                RoommateReply(
                    roommate_id="roommate_a",
                    roommate="舍友 A",
                    personality="直接型",
                    message="我也没开很大声吧。",
                ),
            ],
            safety_note="本回复仅用于宿舍沟通演练，不进行心理诊断，不进行医学判断，不进行人格评价。如有现实安全风险，请联系辅导员。",
        )


def test_simulate_response_rejects_safety_note_missing_rehearsal_purpose():
    with pytest.raises(ValidationError):
        SimulateResponse(
            conversation_id="conversation-1",
            replies=[
                RoommateReply(
                    roommate_id="roommate_a",
                    roommate="舍友 A",
                    personality="直接型",
                    message="我也没开很大声吧。",
                ),
            ],
            safety_note="不代表真实舍友想法，不进行心理诊断，不进行医学判断，不进行人格评价。如有现实安全风险，请联系辅导员。",
        )


def test_review_request_supports_conversation_id_without_dialogue():
    request = ReviewRequest(scenario="噪音冲突", conversation_id="conversation-1")

    assert request.conversation_id == "conversation-1"
    assert request.dialogue == []


def test_review_request_rejects_more_than_fifty_dialogue_messages():
    request = ReviewRequest(
        scenario="噪音冲突",
        dialogue=[
            DialogueMessage(speaker="user", message=f"第 {index} 条消息")
            for index in range(50)
        ],
    )

    assert len(request.dialogue) == 50

    with pytest.raises(ValidationError):
        ReviewRequest(
            scenario="噪音冲突",
            dialogue=[
                DialogueMessage(speaker="user", message=f"第 {index} 条消息")
                for index in range(51)
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


def test_build_review_messages_marks_missing_source_meta():
    request = ReviewRequest(
        scenario="噪音冲突",
        dialogue=[DialogueMessage(speaker="user", message="晚上能不能小声一点？")],
    )

    messages = build_review_messages(request)

    assert "source_meta: 未提供" in str(messages[-1].content)


def test_build_review_messages_includes_scenario_training_source_meta():
    request = ReviewRequest(
        scenario="舍友晚上打游戏声音很大，影响睡眠。",
        dialogue=[DialogueMessage(speaker="user", message="能不能晚上小声一点？")],
        source_meta={
            "mode": "scenario_training",
            "category_id": "noise",
            "category_label": "噪音冲突",
            "scenario_id": "noise_game_night",
            "scenario_title": "训练场景：晚上打游戏声音太大",
            "target_id": "make_request",
            "target_label": "训练目标：提出具体请求",
            "difficulty_id": "intermediate",
            "difficulty_label": "训练难度：中级",
            "difficulty_description": "在对方轻微反驳时继续保持温和、具体的请求。",
        },
    )

    messages = build_review_messages(request)

    message_content = str(messages[-1].content)
    assert "source_meta:" in message_content
    assert "scenario_training" in message_content
    assert "训练场景" in message_content
    assert "训练目标" in message_content
    assert "训练难度" in message_content
    assert "difficulty_description" in message_content
    assert "在对方轻微反驳时继续保持温和、具体的请求" in message_content


def test_review_system_prompt_bounds_source_meta_usage():
    assert "source_meta" in REVIEW_SYSTEM_PROMPT
    assert "仅用于理解复盘来源和训练目标" in REVIEW_SYSTEM_PROMPT
    assert (
        "source_meta 不代表真实舍友想法，不进行心理诊断、不进行医学判断、不进行人格评价"
        in REVIEW_SYSTEM_PROMPT
    )


def test_build_review_messages_includes_custom_rehearsal_source_meta():
    request = ReviewRequest(
        scenario="我想练习如何和舍友沟通临时带朋友来宿舍的问题。",
        dialogue=[DialogueMessage(speaker="user", message="下次带朋友来之前能不能先说一声？")],
        source_meta={
            "mode": "custom_rehearsal",
            "scenario": "自定义场景：临时带朋友来宿舍前先沟通。",
            "roommate_summary": "roommate_summary：舍友平时比较直接，容易觉得我小题大做。",
        },
    )

    messages = build_review_messages(request)

    message_content = str(messages[-1].content)
    assert "source_meta:" in message_content
    assert "custom_rehearsal" in message_content
    assert "自定义场景" in message_content
    assert "roommate_summary" in message_content
    assert "舍友平时比较直接" in message_content


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
        period_days=7,
        active_period_count=1,
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
    assert '"primary_emotion": "anxious"' in message_content
    assert '"emotions": ["anxious"]' in message_content
    assert '"emotion_labels": ["焦虑"]' in message_content
    assert '"has_communicated": false' in message_content
    assert '"has_conflict": true' in message_content
    assert '"description": "舍友晚上打游戏声音很大，影响睡眠。"' in message_content
    assert '"pressure_score": 76' in message_content
    assert '"period_days": 7' in message_content
    assert '"active_period_count": 1' in message_content
    assert "active_30d_count" not in message_content
    assert "event-1" not in message_content
    assert "created_at" not in message_content
    assert "single_analysis" not in message_content
    assert "本结果不作为心理诊断依据" not in message_content
    assert "disclaimer" not in message_content


def test_build_archive_insight_messages_serializes_multi_emotion_labels():
    event_payload = EventRecordCreate(
        event_date=date(2026, 5, 15),
        event_type="hygiene",
        severity=2,
        frequency="occasional",
        emotion="helpless",
        emotions=["helpless", "depressed"],
        primary_emotion="helpless",
        has_communicated=True,
        has_conflict=False,
        description="公共区域有点乱，我很无奈也有些压抑。",
    )
    event = EventRecord(
        **event_payload.model_dump(),
        id="event-1",
        created_at=datetime(2026, 5, 15, 8, 0, 0),
        single_analysis=AnalyzeResponse(
            pressure_score=34,
            risk_level="pressure",
            risk_label="存在压力",
            main_sources=["卫生习惯差异"],
            emotion_keywords=["无奈", "压抑"],
            trend_message="当前压力值为 34。",
            suggestion="建议尽早沟通。",
            recommend_simulation=False,
            disclaimer="本结果不作为心理诊断依据。",
        ),
    )
    analysis = ArchiveAnalysisResponse(
        pressure_score=34,
        risk_level="pressure",
        risk_label="存在压力",
        main_sources=["卫生冲突"],
        emotion_keywords=["无奈", "压抑"],
        trend_message="事件档案共记录 1 条事件。",
        suggestion="建议尽早沟通。",
        recommend_simulation=False,
        disclaimer="本结果不作为心理诊断依据。",
        event_count=1,
        active_30d_count=1,
        source_breakdown=[],
    )

    messages = build_archive_insight_messages([event], analysis)

    message_content = str(messages[-1].content)
    assert '"emotion_labels": ["无奈", "压抑"]' in message_content
    assert "无助" not in message_content
    assert "低落" not in message_content


def test_review_response_requires_actionable_lists():
    response = ReviewResponse(
        summary="用户表达了睡眠受影响的事实，整体语气较温和。",
        strengths=["说明了具体影响"],
        risks=["可以进一步明确时间范围"],
        performance_scores=REVIEW_PERFORMANCE_SCORES,
        rewrite_suggestions=REVIEW_REWRITE_SUGGESTIONS,
        rewritten_message="我最近睡眠状态不太好，晚上 11 点后能不能戴耳机或调低音量？",
        next_steps=["选择双方情绪平稳的时间沟通"],
        safety_note=REVIEW_SAFETY_NOTE,
    )

    assert response.strengths == ["说明了具体影响"]
    assert response.performance_scores.clarity == 82
    assert response.performance_scores.empathy == 76
    assert response.performance_scores.resolution == 71
    assert response.rewrite_suggestions[0].message_index == 0


def test_review_response_requires_rewrite_suggestions():
    with pytest.raises(ValidationError):
        ReviewResponse(
            summary="用户表达了睡眠受影响的事实，整体语气较温和。",
            strengths=["说明了具体影响"],
            risks=["可以进一步明确时间范围"],
            performance_scores=REVIEW_PERFORMANCE_SCORES,
            rewritten_message="我最近睡眠状态不太好，晚上 11 点后能不能戴耳机或调低音量？",
            next_steps=["选择双方情绪平稳的时间沟通"],
            safety_note=REVIEW_SAFETY_NOTE,
        )


def test_review_response_rejects_empty_actionable_lists():
    with pytest.raises(ValidationError):
        ReviewResponse(
            summary="用户表达了睡眠受影响的事实，整体语气较温和。",
            strengths=[],
            risks=["可以进一步明确时间范围"],
            performance_scores=REVIEW_PERFORMANCE_SCORES,
            rewrite_suggestions=REVIEW_REWRITE_SUGGESTIONS,
            rewritten_message="我最近睡眠状态不太好，晚上 11 点后能不能戴耳机或调低音量？",
            next_steps=["选择双方情绪平稳的时间沟通"],
            safety_note=REVIEW_SAFETY_NOTE,
        )


def test_review_response_rejects_performance_scores_outside_0_to_100():
    with pytest.raises(ValidationError):
        ReviewResponse(
            summary="用户表达了睡眠受影响的事实，整体语气较温和。",
            strengths=["说明了具体影响"],
            risks=["可以进一步明确时间范围"],
            performance_scores={"clarity": 101, "empathy": 76, "resolution": 71},
            rewrite_suggestions=REVIEW_REWRITE_SUGGESTIONS,
            rewritten_message="我最近睡眠状态不太好，晚上 11 点后能不能戴耳机或调低音量？",
            next_steps=["选择双方情绪平稳的时间沟通"],
            safety_note=REVIEW_SAFETY_NOTE,
        )


def test_review_response_rejects_unsafe_safety_note():
    with pytest.raises(ValidationError):
        ReviewResponse(
            summary="用户表达了睡眠受影响的事实，整体语气较温和。",
            strengths=["说明了具体影响"],
            risks=["可以进一步明确时间范围"],
            performance_scores=REVIEW_PERFORMANCE_SCORES,
            rewrite_suggestions=REVIEW_REWRITE_SUGGESTIONS,
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
            rewrite_suggestions=REVIEW_REWRITE_SUGGESTIONS,
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
            rewrite_suggestions=REVIEW_REWRITE_SUGGESTIONS,
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
    assert "所有表达不好的用户发言" in REVIEW_SYSTEM_PROMPT


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
