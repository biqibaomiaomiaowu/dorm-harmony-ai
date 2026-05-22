from datetime import date, datetime
import sys
import types

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

import app.ai_service as ai_service
from app.ai_service import (
    AISettings,
    AIOutputStructureError,
    AIServiceConfigurationError,
    AIServiceUnavailableError,
    DormHarmonyAIService,
    LangChainDeepSeekRunner,
    load_ai_settings,
)
from app.schemas import (
    AnalyzeResponse,
    ArchiveAnalysisResponse,
    ArchiveInsightResponse,
    DialogueMessage,
    EventRecord,
    ReviewRequest,
    ReviewResponse,
    RoommateReply,
    default_roommate_profiles,
    SimulateRequest,
    SimulateResponse,
)


SIMULATE_SAFETY_NOTE = (
    "本回复仅用于宿舍沟通演练，不代表真实舍友想法，"
    "不进行心理诊断、不进行医学判断、不进行人格评价。"
    "如有现实安全风险，请联系辅导员、心理老师、家人或可信任同学。"
)
REVIEW_SAFETY_NOTE = (
    "本复盘仅用于沟通训练建议，不代表真实舍友想法，"
    "不进行心理诊断、不进行医学判断、不进行人格评价。"
    "如压力持续升高，请寻求现实支持或联系辅导员、心理老师。"
)
ARCHIVE_INSIGHT_SAFETY_NOTE = (
    "本建议仅用于沟通训练建议，不代表真实舍友想法，"
    "不进行心理诊断、不进行医学判断、不进行人格评价。"
    "如压力持续升高，请联系辅导员或心理老师寻求现实支持。"
)
REVIEW_PERFORMANCE_SCORES = {"clarity": 82, "empathy": 76, "resolution": 71}
REVIEW_REWRITE_SUGGESTIONS = [
    {
        "message_index": 0,
        "original_message": "晚上能不能小声一点？",
        "issue": "请求较笼统，容易被理解成指责。",
        "suggested_message": "我最近睡眠受影响，能不能 11 点后戴耳机？",
        "reason": "先说明影响，再提出具体可执行的调整。",
    }
]


def make_review_response_payload():
    return {
        "summary": "用户表达了睡眠受影响的事实，整体语气较温和。",
        "strengths": ["说明了具体影响"],
        "risks": ["可以进一步明确时间范围"],
        "performance_scores": REVIEW_PERFORMANCE_SCORES,
        "rewrite_suggestions": REVIEW_REWRITE_SUGGESTIONS,
        "rewritten_message": "我最近睡眠受影响，能不能 11 点后戴耳机？",
        "next_steps": ["选择双方情绪平稳的时间沟通"],
        "safety_note": REVIEW_SAFETY_NOTE,
    }


@pytest.fixture(autouse=True)
def isolate_project_env_file(monkeypatch, tmp_path):
    from app import env as env_module

    monkeypatch.setattr(env_module, "DEFAULT_ENV_FILE", tmp_path / ".env.missing")
    if "langchain_deepseek" not in sys.modules:
        module = types.ModuleType("langchain_deepseek")

        class PlaceholderChatDeepSeek:
            pass

        module.ChatDeepSeek = PlaceholderChatDeepSeek
        monkeypatch.setitem(sys.modules, "langchain_deepseek", module)


class ScriptedMultiAgentRunner:
    def __init__(
        self,
        *,
        plan=None,
        replies=None,
        review_response=None,
    ):
        self.plan = plan if plan is not None else [{"roommate_id": "roommate_a"}]
        self.replies = list(
            replies
            if replies is not None
            else [
                {
                    "roommate_id": "roommate_a",
                    "roommate": "舍友 A",
                    "personality": "直接型",
                    "message": "我也没开很大声吧，但可以试着戴耳机。",
                }
            ]
        )
        self.review_response = review_response or make_review_response_payload()
        self.plan_calls = []
        self.reply_calls = []
        self.latest_review_dialogue = []

    def plan_simulation_replies(self, request, history, archive_context_summary=None):
        self.plan_calls.append(
            {
                "request": request,
                "history": list(history),
                "archive_context_summary": archive_context_summary,
            }
        )
        return ai_service.SpeakerPlanResponse(replies=self.plan)

    def generate_roommate_reply(
        self,
        request,
        history,
        archive_context_summary,
        same_turn_replies,
        roommate,
    ):
        self.reply_calls.append(
            {
                "request": request,
                "history": list(history),
                "archive_context_summary": archive_context_summary,
                "same_turn_replies": list(same_turn_replies),
                "roommate": roommate,
            }
        )
        if not self.replies:
            raise RuntimeError("no scripted reply left")
        return RoommateReply(**self.replies.pop(0))

    def generate_review(self, request, dialogue):
        self.latest_review_dialogue = list(dialogue)
        return ReviewResponse(**self.review_response)

    def generate_archive_insight(self, events, analysis):
        return ArchiveInsightResponse(
            insight="近 30 天噪音事件集中出现，主要压力来自休息边界被反复打断。",
            care_suggestion="先照顾睡眠和情绪稳定，再选择白天提出具体规则。",
            communication_focus=["围绕 11 点后的安静规则沟通"],
            safety_note=ARCHIVE_INSIGHT_SAFETY_NOTE,
        )

    def latest_history_contains(self, text):
        return any(
            text in str(message.message)
            for call in self.plan_calls + self.reply_calls
            for message in call["history"]
        )


class FakeRunner(ScriptedMultiAgentRunner):
    pass


class BrokenRunner:
    def plan_simulation_replies(self, request, history, archive_context_summary=None):
        raise RuntimeError("network exploded with secret sk-test")

    def generate_roommate_reply(
        self,
        request,
        history,
        archive_context_summary,
        same_turn_replies,
        roommate,
    ):
        raise RuntimeError("network exploded with secret sk-test")

    def generate_review(self, request, dialogue):
        raise RuntimeError("network exploded with secret sk-test")

    def generate_archive_insight(self, events, analysis):
        raise RuntimeError("network exploded with secret sk-test")


class BadShapeRunner:
    def plan_simulation_replies(self, request, history, archive_context_summary=None):
        return {"replies": [{"roommate_id": ""}]}

    def generate_roommate_reply(
        self,
        request,
        history,
        archive_context_summary,
        same_turn_replies,
        roommate,
    ):
        return {"roommate": "舍友 A", "personality": "直接型", "message": "missing id"}

    def generate_review(self, request, dialogue):
        return {"summary": "missing fields"}

    def generate_archive_insight(self, events, analysis):
        return {"insight": "missing fields"}


class DictRunner:
    def plan_simulation_replies(self, request, history, archive_context_summary=None):
        return {"replies": [{"roommate_id": "roommate_a"}]}

    def generate_roommate_reply(
        self,
        request,
        history,
        archive_context_summary,
        same_turn_replies,
        roommate,
    ):
        return {
            "roommate_id": "roommate_a",
            "roommate": "舍友 A",
            "personality": "直接型",
            "message": "我确实声音可能有点大，可以把音量调低。",
        }

    def generate_review(self, request, dialogue):
        return {
            "summary": "用户表达了休息需求，语气相对清楚。",
            "strengths": ["说明了受影响的具体时间"],
            "risks": ["可以避免使用绝对化指责"],
            "performance_scores": REVIEW_PERFORMANCE_SCORES,
            "rewrite_suggestions": REVIEW_REWRITE_SUGGESTIONS,
            "rewritten_message": "晚上 11 点后我需要休息，能不能一起把声音降下来？",
            "next_steps": ["选择白天双方都方便的时间再确认规则"],
            "safety_note": REVIEW_SAFETY_NOTE,
        }

    def generate_archive_insight(self, events, analysis):
        return {
            "insight": "近 30 天噪音事件集中出现，主要压力来自休息边界被反复打断。",
            "care_suggestion": "先照顾睡眠和情绪稳定，再选择白天提出具体规则。",
            "communication_focus": ["围绕 11 点后的安静规则沟通"],
            "safety_note": ARCHIVE_INSIGHT_SAFETY_NOTE,
        }


class ExplodingStructuredLLM:
    def invoke(self, messages):
        raise RuntimeError("provider failed with sk-test")


class ExplodingChatDeepSeek:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def with_structured_output(self, schema, **kwargs):
        return ExplodingStructuredLLM()


class CapturingStructuredLLM:
    def __init__(self, schema):
        self.schema = schema

    def invoke(self, messages):
        schema_name = getattr(self.schema, "__name__", "")
        if schema_name == "SpeakerPlanResponse":
            return {"replies": [{"roommate_id": "roommate_a"}]}

        if self.schema is RoommateReply:
            return {
                "roommate_id": "roommate_a",
                "roommate": "舍友 A",
                "personality": "直接型",
                "message": "我确实声音可能有点大，可以把音量调低。",
            }

        if schema_name == "ReviewDraftResponse":
            return make_review_response_payload()

        if self.schema is ArchiveInsightResponse:
            return {
                "insight": "近 30 天噪音事件集中出现，主要压力来自休息边界被反复打断。",
                "care_suggestion": "先照顾睡眠和情绪稳定，再选择白天提出具体规则。",
                "communication_focus": ["围绕 11 点后的安静规则沟通"],
                "safety_note": ARCHIVE_INSIGHT_SAFETY_NOTE,
            }

        raise AssertionError(f"unexpected structured schema {self.schema}")


class CapturingChatDeepSeek:
    latest_kwargs = None
    latest_structured_kwargs = None
    latest_structured_schemas = []
    latest_messages = None
    all_messages = []

    def __init__(self, **kwargs):
        CapturingChatDeepSeek.latest_kwargs = kwargs

    def with_structured_output(self, schema, **kwargs):
        CapturingChatDeepSeek.latest_structured_kwargs = kwargs
        CapturingChatDeepSeek.latest_structured_schemas.append(schema)
        return CapturingStructuredLLM(schema)


class CapturingInvokeStructuredLLM(CapturingStructuredLLM):
    def invoke(self, messages):
        CapturingChatDeepSeek.latest_messages = messages
        CapturingChatDeepSeek.all_messages.append(messages)
        return super().invoke(messages)


class CapturingInvokeChatDeepSeek(CapturingChatDeepSeek):
    def with_structured_output(self, schema, **kwargs):
        CapturingChatDeepSeek.latest_structured_kwargs = kwargs
        CapturingChatDeepSeek.latest_structured_schemas.append(schema)
        return CapturingInvokeStructuredLLM(schema)


def assert_exception_chain_is_sanitized(error):
    assert "sk-test" not in str(error)
    assert error.__cause__ is None
    assert error.__context__ is None
    assert "sk-test" not in str(error.__cause__)
    assert "sk-test" not in str(error.__context__)


@pytest.fixture
def archive_events_and_analysis():
    event = EventRecord(
        id="event-1",
        created_at=datetime(2026, 5, 15, 8, 0, 0),
        event_date=date(2026, 5, 15),
        event_type="noise",
        severity=4,
        frequency="weekly_multiple",
        emotion="anxious",
        has_communicated=False,
        has_conflict=True,
        description="舍友晚上打游戏声音很大，影响睡眠。",
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

    return [event], analysis


def test_load_ai_settings_requires_llm_api_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(AIServiceConfigurationError) as exc_info:
        load_ai_settings()

    assert "DEEPSEEK_API_KEY" in str(exc_info.value)
    assert "OPENAI_API_KEY" in str(exc_info.value)


def test_load_ai_settings_loads_project_env_file(monkeypatch, tmp_path):
    from app import env as env_module

    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "DEEPSEEK_API_KEY=dotenv-root-key",
                "DORM_HARMONY_LLM_MODEL=deepseek-v4-flash",
                "DORM_HARMONY_LLM_TIMEOUT=31",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(env_module, "DEFAULT_ENV_FILE", env_file)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DORM_HARMONY_LLM_MODEL", raising=False)
    monkeypatch.delenv("DORM_HARMONY_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("DORM_HARMONY_LLM_TIMEOUT", raising=False)

    settings = load_ai_settings()

    assert settings.api_key == "dotenv-root-key"
    assert settings.model == "deepseek-v4-flash"
    assert settings.timeout == 31.0


def test_load_ai_settings_uses_deepseek_defaults(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DORM_HARMONY_LLM_MODEL", raising=False)
    monkeypatch.delenv("DORM_HARMONY_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("DORM_HARMONY_LLM_TIMEOUT", raising=False)

    settings = load_ai_settings()

    assert settings.api_key == "deepseek-key"
    assert settings.model == "deepseek-v4-flash"
    assert settings.base_url == "https://api.deepseek.com"
    assert settings.timeout == 20.0


def test_load_ai_settings_prefers_deepseek_key_over_legacy_openai_key(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-key")
    monkeypatch.setenv("OPENAI_API_KEY", "legacy-openai-key")
    monkeypatch.delenv("DORM_HARMONY_LLM_MODEL", raising=False)
    monkeypatch.delenv("DORM_HARMONY_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("DORM_HARMONY_LLM_TIMEOUT", raising=False)

    settings = load_ai_settings()

    assert settings.api_key == "deepseek-key"
    assert settings.model == "deepseek-v4-flash"
    assert settings.base_url == "https://api.deepseek.com"
    assert settings.timeout == 20.0


def test_load_ai_settings_keeps_legacy_openai_key_fallback(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "legacy-openai-key")
    monkeypatch.delenv("DORM_HARMONY_LLM_MODEL", raising=False)
    monkeypatch.delenv("DORM_HARMONY_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("DORM_HARMONY_LLM_TIMEOUT", raising=False)

    settings = load_ai_settings()

    assert settings.api_key == "legacy-openai-key"
    assert settings.model == "deepseek-v4-flash"
    assert settings.base_url == "https://api.deepseek.com"
    assert settings.timeout == 20.0


def test_load_ai_settings_allows_base_url_override(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-key")
    monkeypatch.setenv("DORM_HARMONY_LLM_BASE_URL", "https://example.test/openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DORM_HARMONY_LLM_MODEL", raising=False)
    monkeypatch.delenv("DORM_HARMONY_LLM_TIMEOUT", raising=False)

    settings = load_ai_settings()

    assert settings.base_url == "https://example.test/openai"
    assert settings.timeout == 20.0


def test_conversation_memory_uses_langgraph_in_memory_saver():
    from langgraph.checkpoint.memory import InMemorySaver

    memory = ai_service.ConversationMemory()

    assert isinstance(memory.checkpointer, InMemorySaver)


def test_conversation_memory_persists_with_sqlite_checkpointer(tmp_path):
    db_path = tmp_path / "memory.sqlite3"
    first_memory = ai_service.ConversationMemory.sqlite(db_path)
    service = DormHarmonyAIService(runner=FakeRunner(), memory=first_memory)

    first = service.simulate(
        SimulateRequest(
            scenario="噪音冲突",
            user_message="晚上能不能小声一点？",
        )
    )

    second_memory = ai_service.ConversationMemory.sqlite(db_path)
    dialogue = second_memory.get_dialogue(first.conversation_id)

    assert any(
        line.speaker == "user" and "小声" in line.message
        for line in dialogue
    )


def test_conversation_memory_persists_latest_turn_with_sqlite(tmp_path):
    db_path = tmp_path / "memory.sqlite3"
    first_memory = ai_service.ConversationMemory.sqlite(db_path)
    conversation_id = first_memory.start_conversation()

    first_memory.mark_latest_turn(conversation_id, "turn-1")

    second_memory = ai_service.ConversationMemory.sqlite(db_path)

    assert second_memory.is_latest_turn(conversation_id, "turn-1") is True
    assert second_memory.is_latest_turn(conversation_id, "turn-2") is False


def test_service_returns_conversation_id_and_persists_turn_memory():
    request = SimulateRequest(scenario="噪音冲突", user_message="晚上能不能小声一点？")
    runner = ScriptedMultiAgentRunner(
        plan=[{"roommate_id": "roommate_a"}],
        replies=[
            {
                "roommate_id": "roommate_a",
                "roommate": "舍友 A",
                "personality": "直接型",
                "message": "我会注意。",
            },
            {
                "roommate_id": "roommate_a",
                "roommate": "舍友 A",
                "personality": "直接型",
                "message": "那 11 点后我戴耳机。",
            },
        ],
    )
    service = DormHarmonyAIService(runner=runner, memory=ai_service.ConversationMemory())

    first = service.simulate(request)
    second = service.simulate(
        SimulateRequest(
            conversation_id=first.conversation_id,
            scenario="噪音冲突",
            user_message="那 11 点后戴耳机可以吗？",
        )
    )

    assert first.conversation_id
    assert second.conversation_id == first.conversation_id
    assert runner.latest_history_contains("晚上能不能小声一点？")
    assert runner.latest_history_contains("我会注意。")


def test_simulate_with_missing_conversation_id_raises_memory_not_found():
    service = DormHarmonyAIService(
        runner=FakeRunner(),
        memory=ai_service.ConversationMemory(),
    )

    with pytest.raises(ai_service.ConversationMemoryNotFoundError):
        service.simulate(
            SimulateRequest(
                conversation_id="missing",
                scenario="噪音冲突",
                user_message="继续刚才的话题。",
            )
        )


def test_service_returns_simulation_from_runner():
    request = SimulateRequest(scenario="噪音冲突", user_message="晚上能不能小声一点？")
    service = DormHarmonyAIService(runner=FakeRunner(), memory=ai_service.ConversationMemory())

    response = service.simulate(request)

    assert response.conversation_id
    assert [reply.roommate for reply in response.replies] == ["舍友 A"]
    assert response.replies[0].roommate_id == "roommate_a"
    assert "不进行心理诊断" in response.safety_note


def test_service_rejects_unknown_planned_roommate_id():
    request = SimulateRequest(scenario="噪音冲突", user_message="晚上能不能小声一点？")
    runner = ScriptedMultiAgentRunner(plan=[{"roommate_id": "unknown"}])
    service = DormHarmonyAIService(runner=runner, memory=ai_service.ConversationMemory())

    with pytest.raises(AIOutputStructureError):
        service.simulate(request)


def test_service_rejects_planned_roommate_more_than_three_times():
    request = SimulateRequest(scenario="噪音冲突", user_message="晚上能不能小声一点？")
    runner = ScriptedMultiAgentRunner(
        plan=[{"roommate_id": "roommate_a"} for _ in range(4)],
        replies=[
            {
                "roommate_id": "roommate_a",
                "roommate": "舍友 A",
                "personality": "直接型",
                "message": f"第 {index} 条回复。",
            }
            for index in range(4)
        ],
    )
    service = DormHarmonyAIService(runner=runner, memory=ai_service.ConversationMemory())

    with pytest.raises(AIOutputStructureError):
        service.simulate(request)


def test_service_rejects_generated_reply_when_it_mismatches_planner_item():
    request = SimulateRequest(scenario="噪音冲突", user_message="晚上能不能小声一点？")
    runner = ScriptedMultiAgentRunner(
        plan=[{"roommate_id": "roommate_a"}],
        replies=[
            {
                "roommate_id": "roommate_b",
                "roommate": "舍友 B",
                "personality": "回避型",
                "message": "我先不说了。",
            }
        ],
    )
    service = DormHarmonyAIService(runner=runner, memory=ai_service.ConversationMemory())

    with pytest.raises(AIOutputStructureError):
        service.simulate(request)


def test_service_rejects_generated_roommate_more_than_three_times():
    request = SimulateRequest(
        scenario="噪音冲突",
        user_message="晚上能不能小声一点？",
        roommates=[
            {
                "id": f"roommate_{index}",
                "name": f"舍友 {index}",
                "personality_tag": "自定义",
                "tag_mode": "custom",
                "traits": {
                    "directness": 2,
                    "emotional_reactivity": 2,
                    "avoidance": 2,
                    "empathy": 2,
                    "solution_willingness": 2,
                    "boundary_sensitivity": 2,
                },
            }
            for index in range(4)
        ],
    )
    runner = ScriptedMultiAgentRunner(
        plan=[{"roommate_id": f"roommate_{index}"} for index in range(4)],
        replies=[
            {
                "roommate_id": "roommate_0",
                "roommate": "舍友 0",
                "personality": "自定义",
                "message": f"第 {index} 条回复。",
            }
            for index in range(4)
        ],
    )
    service = DormHarmonyAIService(runner=runner, memory=ai_service.ConversationMemory())

    with pytest.raises(AIOutputStructureError):
        service.simulate(request)


def test_service_limits_planned_replies_for_step_generation():
    request = SimulateRequest(
        scenario="噪音冲突",
        user_message="晚上能不能小声一点？",
        max_replies=1,
    )
    runner = ScriptedMultiAgentRunner(
        plan=[
            {"roommate_id": "roommate_a"},
            {"roommate_id": "roommate_c"},
            {"roommate_id": "roommate_a"},
        ],
        replies=[
            {
                "roommate_id": "roommate_a",
                "roommate": "舍友 A",
                "personality": "直接型",
                "message": "我会先把音量调低。",
            },
            {
                "roommate_id": "roommate_c",
                "roommate": "舍友 C",
                "personality": "调和型",
                "message": "我们可以定个规则。",
            },
        ],
    )
    service = DormHarmonyAIService(runner=runner, memory=ai_service.ConversationMemory())

    response = service.simulate(request)

    assert len(response.replies) == 1
    assert response.replies[0].roommate_id == "roommate_a"
    assert len(runner.reply_calls) == 1


def test_service_does_not_write_user_message_when_generation_fails():
    memory = ai_service.ConversationMemory()
    conversation_id = memory.start_conversation()
    request = SimulateRequest(
        conversation_id=conversation_id,
        scenario="噪音冲突",
        user_message="晚上能不能小声一点？",
    )
    runner = ScriptedMultiAgentRunner(plan=[{"roommate_id": "roommate_a"}], replies=[])
    service = DormHarmonyAIService(runner=runner, memory=memory)

    with pytest.raises(AIServiceUnavailableError):
        service.simulate(request)

    assert memory.get_dialogue(conversation_id) == []


def test_service_continuation_does_not_append_extra_user_message():
    memory = ai_service.ConversationMemory()
    conversation_id = memory.start_conversation()
    memory.append_user_message(conversation_id, "晚上能不能小声一点？")
    memory.append_roommate_message(
        conversation_id,
        "roommate_a",
        "舍友 A",
        "直接型",
        "我会注意。",
    )
    request = SimulateRequest(
        conversation_id=conversation_id,
        scenario="噪音冲突",
        is_continuation=True,
        max_replies=1,
    )
    runner = ScriptedMultiAgentRunner(
        plan=[{"roommate_id": "roommate_c"}],
        replies=[
            {
                "roommate_id": "roommate_c",
                "roommate": "舍友 C",
                "personality": "调和型",
                "message": "我们可以一起定 11 点后的规则。",
            }
        ],
    )
    service = DormHarmonyAIService(runner=runner, memory=memory)

    response = service.simulate(request)
    dialogue = memory.get_dialogue(conversation_id)

    assert response.replies[0].roommate_id == "roommate_c"
    assert [message.speaker for message in dialogue] == [
        "user",
        "roommate_a",
        "roommate_c",
    ]


def test_service_allows_empty_planner_and_writes_user_message():
    request = SimulateRequest(scenario="噪音冲突", user_message="我先想一想怎么说。")
    memory = ai_service.ConversationMemory()
    runner = ScriptedMultiAgentRunner(plan=[], replies=[])
    service = DormHarmonyAIService(runner=runner, memory=memory)

    response = service.simulate(request)
    dialogue = memory.get_dialogue(response.conversation_id)

    assert response.replies == []
    assert len(dialogue) == 1
    assert dialogue[0].speaker == "user"
    assert dialogue[0].message == "我先想一想怎么说。"


def test_service_does_not_write_user_message_when_generation_fails():
    memory = ai_service.ConversationMemory()
    conversation_id = memory.start_conversation()
    memory.append_user_message(conversation_id, "第一轮先沟通。")
    service = DormHarmonyAIService(runner=BrokenRunner(), memory=memory)

    with pytest.raises(AIServiceUnavailableError):
        service.simulate(
            SimulateRequest(
                conversation_id=conversation_id,
                scenario="噪音冲突",
                user_message="第二轮不要重复写入。",
            )
        )

    dialogue = memory.get_dialogue(conversation_id)
    assert [message.message for message in dialogue] == ["第一轮先沟通。"]


def test_continuation_does_not_append_user_message_and_respects_max_replies():
    memory = ai_service.ConversationMemory()
    conversation_id = memory.start_conversation()
    memory.append_user_message(conversation_id, "晚上能不能小声一点？")
    memory.append_roommate_message(
        conversation_id,
        "roommate_a",
        "舍友 A",
        "直接型",
        "我会注意。",
    )
    runner = ScriptedMultiAgentRunner(
        plan=[
            {"roommate_id": "roommate_a"},
            {"roommate_id": "roommate_c"},
        ],
        replies=[
            {
                "roommate_id": "roommate_a",
                "roommate": "舍友 A",
                "personality": "直接型",
                "message": "那我 11 点后戴耳机。",
            },
            {
                "roommate_id": "roommate_c",
                "roommate": "舍友 C",
                "personality": "调和型",
                "message": "我们可以约一个安静时间。",
            },
        ],
    )
    service = DormHarmonyAIService(runner=runner, memory=memory)

    response = service.simulate(
        SimulateRequest(
            conversation_id=conversation_id,
            scenario="噪音冲突",
            is_continuation=True,
            max_replies=1,
        )
    )
    dialogue = memory.get_dialogue(conversation_id)

    assert [reply.roommate_id for reply in response.replies] == ["roommate_a"]
    assert len(runner.reply_calls) == 1
    assert [message.speaker for message in dialogue] == ["user", "roommate_a", "roommate_a"]


def test_service_returns_review_from_runner():
    request = ReviewRequest(
        scenario="噪音冲突",
        dialogue=[DialogueMessage(speaker="user", message="晚上能不能小声一点？")],
    )
    service = DormHarmonyAIService(runner=FakeRunner(), memory=ai_service.ConversationMemory())

    response = service.review(request)

    assert response.strengths
    assert response.performance_scores.clarity == 82
    assert response.rewrite_suggestions[0].message_index == 0
    assert response.communication_plan.opening
    assert response.communication_plan.specific_request
    assert response.communication_plan.fallback_plan
    assert "不进行心理诊断" in response.safety_note


def test_review_with_dialogue_result_exposes_actual_dialogue():
    service = DormHarmonyAIService(runner=FakeRunner(), memory=ai_service.ConversationMemory())

    result = service.review_with_dialogue(
        ReviewRequest(
            scenario="噪音冲突",
            dialogue=[DialogueMessage(speaker="user", message="晚上能不能小声一点？")],
        )
    )

    assert result.response.summary
    assert result.dialogue[0].speaker == "user"
    assert result.dialogue[0].message == "晚上能不能小声一点？"


def test_resolve_review_dialogue_is_public_for_routes():
    service = DormHarmonyAIService(runner=FakeRunner(), memory=ai_service.ConversationMemory())

    dialogue = service.resolve_review_dialogue(
        ReviewRequest(
            scenario="噪音冲突",
            dialogue=[DialogueMessage(speaker="user", message="晚上能不能小声一点？")],
        )
    )

    assert dialogue[0].speaker == "user"


def test_review_uses_memory_dialogue_and_returns_multi_rewrites():
    memory = ai_service.ConversationMemory()
    conversation_id = memory.start_conversation()
    memory.append_user_message(conversation_id, "你能不能别吵了？")
    memory.append_roommate_message(
        conversation_id,
        "roommate_a",
        "舍友 A",
        "直接型",
        "我也没多大声。",
    )
    memory.append_user_message(conversation_id, "算了。")
    runner = ScriptedMultiAgentRunner(
        review_response={
            **make_review_response_payload(),
            "rewrite_suggestions": [
                {
                    **REVIEW_REWRITE_SUGGESTIONS[0],
                    "original_message": "你能不能别吵了？",
                },
                {
                    "message_index": 2,
                    "original_message": "算了。",
                    "issue": "表达过于收束，容易中断沟通。",
                    "suggested_message": "我们可以晚点再说，但我希望今天能定一个安静时间。",
                    "reason": "保留缓冲，同时说明希望解决的问题。",
                },
            ],
        }
    )
    service = DormHarmonyAIService(runner=runner, memory=memory)

    response = service.review(
        ReviewRequest(conversation_id=conversation_id, scenario="噪音冲突")
    )

    assert len(response.rewrite_suggestions) == 2
    assert runner.latest_review_dialogue[0].message == "你能不能别吵了？"
    assert runner.latest_review_dialogue[1].speaker == "roommate_a"
    assert runner.latest_review_dialogue[2].message == "算了。"


def test_review_normalizes_rewrite_suggestion_index_by_unique_original_message():
    runner = ScriptedMultiAgentRunner(
        review_response={
            **make_review_response_payload(),
            "rewrite_suggestions": [
                {
                    **REVIEW_REWRITE_SUGGESTIONS[0],
                    "message_index": 1,
                    "original_message": "算了。",
                }
            ],
        }
    )
    service = DormHarmonyAIService(runner=runner, memory=ai_service.ConversationMemory())

    response = service.review(
        ReviewRequest(
            scenario="噪音冲突",
            dialogue=[
                DialogueMessage(speaker="user", message="你能不能别吵了？"),
                DialogueMessage(speaker="roommate_a", message="我会注意。"),
                DialogueMessage(speaker="user", message="算了。"),
            ],
        )
    )

    assert response.rewrite_suggestions[0].message_index == 2


def test_review_normalizes_rewrite_suggestion_index_by_user_turn_for_repeated_messages():
    runner = ScriptedMultiAgentRunner(
        review_response={
            **make_review_response_payload(),
            "rewrite_suggestions": [
                {
                    **REVIEW_REWRITE_SUGGESTIONS[0],
                    "message_index": 1,
                    "original_message": "你能不能别吵了？",
                }
            ],
        }
    )
    service = DormHarmonyAIService(runner=runner, memory=ai_service.ConversationMemory())

    response = service.review(
        ReviewRequest(
            scenario="噪音冲突",
            dialogue=[
                DialogueMessage(speaker="user", message="你能不能别吵了？"),
                DialogueMessage(speaker="roommate_a", message="我没有很大声。"),
                DialogueMessage(speaker="user", message="你能不能别吵了？"),
            ],
        )
    )

    assert response.rewrite_suggestions[0].message_index == 2
    assert response.rewrite_suggestions[0].original_message == "你能不能别吵了？"


def test_review_recovers_empty_rewrite_suggestions_from_ai_draft():
    class DraftRunner:
        def generate_review(self, request, dialogue):
            return {
                **make_review_response_payload(),
                "rewrite_suggestions": [],
                "safety_note": "本建议仅供参考。",
            }

    runner = DraftRunner()
    service = DormHarmonyAIService(runner=runner, memory=ai_service.ConversationMemory())

    response = service.review(
        ReviewRequest(
            scenario="噪音冲突",
            dialogue=[
                DialogueMessage(speaker="user", message="你能不能别吵了？"),
                DialogueMessage(speaker="roommate_a", message="我没有很大声。"),
                DialogueMessage(speaker="user", message="算了，不说了。"),
            ],
        )
    )

    assert response.rewrite_suggestions
    assert response.rewrite_suggestions[0].message_index in {0, 2}
    assert "仅用于沟通训练建议" in response.safety_note
    assert "不代表真实舍友想法" in response.safety_note


def test_review_recovers_nullable_and_mixed_ai_draft_fields():
    class DraftRunner:
        def generate_review(self, request, dialogue):
            return {
                "summary": None,
                "strengths": None,
                "risks": ["可以更具体", 123],
                "performance_scores": {"clarity": 101, "empathy": None, "resolution": -4},
                "rewrite_suggestions": [None, "bad", {"message_index": 0}],
                "rewritten_message": None,
                "next_steps": None,
                "safety_note": None,
            }

    service = DormHarmonyAIService(runner=DraftRunner(), memory=ai_service.ConversationMemory())

    response = service.review(
        ReviewRequest(
            scenario="噪音冲突",
            dialogue=[DialogueMessage(speaker="user", message="你能不能别吵了？")],
        )
    )

    assert response.summary
    assert response.risks == ["可以更具体"]
    assert response.performance_scores.clarity == 100
    assert response.performance_scores.empathy == 72
    assert response.performance_scores.resolution == 0
    assert response.rewrite_suggestions[0].message_index == 0
    assert "仅用于沟通训练建议" in response.safety_note


def test_review_response_includes_fallback_communication_plan():
    class DraftRunnerWithoutPlan:
        def generate_review(self, request, dialogue):
            return make_review_response_payload()

    service = DormHarmonyAIService(
        runner=DraftRunnerWithoutPlan(),
        memory=ai_service.ConversationMemory(),
    )

    response = service.review(
        ReviewRequest(
            scenario="噪音冲突",
            dialogue=[DialogueMessage(speaker="user", message="晚上能不能小声一点？")],
        )
    )

    assert response.communication_plan.opening
    assert "11 点后" in response.communication_plan.specific_request
    assert response.communication_plan.fallback_plan


def test_service_normalizes_generated_reply_identity_to_requested_roommate_profile():
    request = SimulateRequest(scenario="噪音冲突", user_message="晚上能不能小声一点？")
    runner = ScriptedMultiAgentRunner(
        replies=[
            {
                "roommate_id": "roommate_a",
                "roommate": "舍友 B",
                "personality": "回避型",
                "message": "我会注意一下。",
            }
        ],
    )
    service = DormHarmonyAIService(runner=runner, memory=ai_service.ConversationMemory())

    response = service.simulate(request)

    assert response.replies[0].roommate == "舍友 A"
    assert response.replies[0].personality == "直接型"


def test_service_rejects_generated_reply_for_different_planned_roommate():
    request = SimulateRequest(scenario="噪音冲突", user_message="晚上能不能小声一点？")
    runner = ScriptedMultiAgentRunner(
        plan=[{"roommate_id": "roommate_a"}],
        replies=[
            {
                "roommate_id": "roommate_b",
                "roommate": "舍友 B",
                "personality": "回避型",
                "message": "我再想想。",
            }
        ],
    )
    service = DormHarmonyAIService(runner=runner, memory=ai_service.ConversationMemory())

    with pytest.raises(AIOutputStructureError):
        service.simulate(request)


def test_review_recovers_rewrite_suggestion_for_non_user_or_mismatched_message():
    runner = ScriptedMultiAgentRunner(
        review_response={
            **make_review_response_payload(),
            "rewrite_suggestions": [
                {
                    **REVIEW_REWRITE_SUGGESTIONS[0],
                    "message_index": 1,
                    "original_message": "舍友原话。",
                }
            ],
        }
    )
    service = DormHarmonyAIService(runner=runner, memory=ai_service.ConversationMemory())

    response = service.review(
        ReviewRequest(
            scenario="噪音冲突",
            dialogue=[
                DialogueMessage(speaker="user", message="晚上能不能小声一点？"),
                DialogueMessage(speaker="roommate_a", message="舍友原话。"),
            ],
        )
    )

    assert response.rewrite_suggestions[0].message_index == 0
    assert response.rewrite_suggestions[0].original_message == "晚上能不能小声一点？"


def test_review_backfills_obviously_improvable_user_messages_when_ai_selects_subset():
    runner = ScriptedMultiAgentRunner(
        review_response={
            **make_review_response_payload(),
            "rewrite_suggestions": [
                {
                    **REVIEW_REWRITE_SUGGESTIONS[0],
                    "message_index": 0,
                    "original_message": "你能不能别吵了？",
                }
            ],
        }
    )
    service = DormHarmonyAIService(runner=runner, memory=ai_service.ConversationMemory())

    response = service.review(
        ReviewRequest(
            scenario="噪音冲突",
            dialogue=[
                DialogueMessage(speaker="user", message="你能不能别吵了？"),
                DialogueMessage(speaker="roommate_a", message="我会注意。"),
                DialogueMessage(speaker="user", message="算了。"),
            ],
        )
    )

    assert [suggestion.message_index for suggestion in response.rewrite_suggestions] == [0, 2]
    assert response.rewrite_suggestions[1].original_message == "算了。"


def test_review_recovers_malformed_index_and_string_scores_from_ai_draft():
    class DraftRunner:
        def generate_review(self, request, dialogue):
            return {
                **make_review_response_payload(),
                "performance_scores": {
                    "clarity": "88",
                    "empathy": "高",
                    "resolution": "64.6",
                },
                "rewrite_suggestions": [
                    {
                        "message_index": "第一条",
                        "original_message": "你能不能别吵了？",
                        "issue": None,
                        "suggested_message": None,
                        "reason": None,
                    }
                ],
            }

    service = DormHarmonyAIService(runner=DraftRunner(), memory=ai_service.ConversationMemory())

    response = service.review(
        ReviewRequest(
            scenario="噪音冲突",
            dialogue=[
                DialogueMessage(speaker="user", message="你能不能别吵了？"),
                DialogueMessage(speaker="roommate_a", message="我会注意。"),
                DialogueMessage(speaker="user", message="算了。"),
            ],
        )
    )

    assert response.performance_scores.clarity == 88
    assert response.performance_scores.empathy == 72
    assert response.performance_scores.resolution == 65
    assert [suggestion.message_index for suggestion in response.rewrite_suggestions] == [0, 2]
    assert all(suggestion.suggested_message for suggestion in response.rewrite_suggestions)


def test_review_by_missing_conversation_id_raises_memory_not_found():
    service = DormHarmonyAIService(
        runner=FakeRunner(),
        memory=ai_service.ConversationMemory(),
    )

    with pytest.raises(ai_service.ConversationMemoryNotFoundError):
        service.review(ReviewRequest(conversation_id="missing", scenario="噪音冲突"))


def test_review_keeps_legacy_dialogue_fallback():
    runner = ScriptedMultiAgentRunner()
    service = DormHarmonyAIService(runner=runner, memory=ai_service.ConversationMemory())

    response = service.review(
        ReviewRequest(
            scenario="噪音冲突",
            dialogue=[DialogueMessage(speaker="user", message="晚上能不能小声一点？")],
        )
    )

    assert response.rewrite_suggestions
    assert runner.latest_review_dialogue[0].message == "晚上能不能小声一点？"


def test_service_returns_archive_insight_from_runner(archive_events_and_analysis):
    events, analysis = archive_events_and_analysis
    service = DormHarmonyAIService(runner=FakeRunner())

    response = service.archive_insight(events, analysis)

    assert isinstance(response, ArchiveInsightResponse)
    assert "噪音事件" in response.insight
    assert response.communication_focus == ["围绕 11 点后的安静规则沟通"]


def test_service_normalizes_simulation_dict_from_runner():
    request = SimulateRequest(scenario="噪音冲突", user_message="晚上能不能小声一点？")
    service = DormHarmonyAIService(runner=DictRunner(), memory=ai_service.ConversationMemory())

    response = service.simulate(request)

    assert isinstance(response, SimulateResponse)
    assert response.replies[0].roommate == "舍友 A"
    assert response.replies[0].message == "我确实声音可能有点大，可以把音量调低。"


def test_service_normalizes_review_dict_from_runner():
    request = ReviewRequest(
        scenario="噪音冲突",
        dialogue=[DialogueMessage(speaker="user", message="晚上能不能小声一点？")],
    )
    service = DormHarmonyAIService(runner=DictRunner(), memory=ai_service.ConversationMemory())

    response = service.review(request)

    assert isinstance(response, ReviewResponse)
    assert response.summary == "用户表达了休息需求，语气相对清楚。"
    assert response.performance_scores.empathy == 76
    assert response.rewrite_suggestions[0].message_index == 0
    assert response.next_steps == ["选择白天双方都方便的时间再确认规则"]


def test_service_normalizes_archive_insight_dict_from_runner(archive_events_and_analysis):
    events, analysis = archive_events_and_analysis
    service = DormHarmonyAIService(runner=DictRunner())

    response = service.archive_insight(events, analysis)

    assert isinstance(response, ArchiveInsightResponse)
    assert response.communication_focus == ["围绕 11 点后的安静规则沟通"]
    assert "不进行心理诊断" in response.safety_note


def test_service_sanitizes_runner_failures():
    request = SimulateRequest(scenario="噪音冲突", user_message="晚上能不能小声一点？")
    service = DormHarmonyAIService(runner=BrokenRunner(), memory=ai_service.ConversationMemory())

    with pytest.raises(AIServiceUnavailableError) as exc_info:
        service.simulate(request)

    assert "AI 服务暂时不可用" in str(exc_info.value)
    assert_exception_chain_is_sanitized(exc_info.value)


def test_service_sanitizes_archive_insight_runner_failures(archive_events_and_analysis):
    events, analysis = archive_events_and_analysis
    service = DormHarmonyAIService(runner=BrokenRunner())

    with pytest.raises(AIServiceUnavailableError) as exc_info:
        service.archive_insight(events, analysis)

    assert "AI 服务暂时不可用" in str(exc_info.value)
    assert_exception_chain_is_sanitized(exc_info.value)


def test_service_rejects_invalid_runner_shape():
    request = SimulateRequest(scenario="噪音冲突", user_message="晚上能不能小声一点？")
    service = DormHarmonyAIService(runner=BadShapeRunner(), memory=ai_service.ConversationMemory())

    with pytest.raises(AIOutputStructureError) as exc_info:
        service.simulate(request)

    assert_exception_chain_is_sanitized(exc_info.value)


def test_service_rejects_invalid_archive_insight_runner_shape(archive_events_and_analysis):
    events, analysis = archive_events_and_analysis
    service = DormHarmonyAIService(runner=BadShapeRunner())

    with pytest.raises(AIOutputStructureError) as exc_info:
        service.archive_insight(events, analysis)

    assert "AI 输出结构异常" in str(exc_info.value)
    assert_exception_chain_is_sanitized(exc_info.value)


def test_langchain_runner_sanitizes_provider_failure(monkeypatch):
    monkeypatch.setattr("langchain_deepseek.ChatDeepSeek", ExplodingChatDeepSeek)
    runner = LangChainDeepSeekRunner(
        settings=AISettings(
            api_key="test-key",
            model="deepseek-v4-flash",
            base_url="https://api.deepseek.com",
            timeout=20.0,
        )
    )
    request = SimulateRequest(scenario="噪音冲突", user_message="晚上能不能小声一点？")

    with pytest.raises(AIServiceUnavailableError) as exc_info:
        runner.plan_simulation_replies(request, history=[])

    assert_exception_chain_is_sanitized(exc_info.value)


def test_langchain_runner_passes_deepseek_configuration_to_chat_deepseek(monkeypatch):
    CapturingChatDeepSeek.latest_kwargs = None
    CapturingChatDeepSeek.latest_structured_kwargs = None
    CapturingChatDeepSeek.latest_structured_schemas = []
    monkeypatch.setattr("langchain_deepseek.ChatDeepSeek", CapturingChatDeepSeek)
    runner = LangChainDeepSeekRunner(
        settings=AISettings(
            api_key="deepseek-key",
            model="deepseek-v4-flash",
            base_url="https://api.deepseek.com",
            timeout=20.0,
        )
    )
    request = SimulateRequest(scenario="噪音冲突", user_message="晚上能不能小声一点？")

    response = runner.plan_simulation_replies(request, history=[])

    assert response.replies[0].roommate_id == "roommate_a"
    assert CapturingChatDeepSeek.latest_kwargs == {
        "model": "deepseek-v4-flash",
        "temperature": 0.3,
        "timeout": 20.0,
        "max_retries": 1,
        "api_key": "deepseek-key",
        "api_base": "https://api.deepseek.com",
    }
    assert CapturingChatDeepSeek.latest_structured_kwargs == {"method": "json_mode"}
    assert CapturingChatDeepSeek.latest_structured_schemas[-1].__name__ == (
        "SpeakerPlanResponse"
    )


def test_langchain_runner_sends_json_contract_prompt(monkeypatch):
    CapturingChatDeepSeek.latest_messages = None
    CapturingChatDeepSeek.all_messages = []
    CapturingChatDeepSeek.latest_structured_schemas = []
    monkeypatch.setattr("langchain_deepseek.ChatDeepSeek", CapturingInvokeChatDeepSeek)
    runner = LangChainDeepSeekRunner(
        settings=AISettings(
            api_key="deepseek-key",
            model="deepseek-v4-flash",
            base_url="https://api.deepseek.com",
            timeout=20.0,
        )
    )
    request = SimulateRequest(scenario="噪音冲突", user_message="晚上能不能小声一点？")

    plan = runner.plan_simulation_replies(request, history=[])
    reply = runner.generate_roommate_reply(
        request,
        history=[],
        archive_context_summary=None,
        same_turn_replies=[],
        roommate=default_roommate_profiles()[0],
    )
    review = runner.generate_review(
        ReviewRequest(scenario="噪音冲突"),
        dialogue=[DialogueMessage(speaker="user", message="晚上能不能小声一点？")],
    )

    assert plan.replies[0].roommate_id == "roommate_a"
    assert reply.roommate_id == "roommate_a"
    assert review.rewrite_suggestions
    assert CapturingChatDeepSeek.all_messages
    system_messages = [
        str(message.content)
        for messages in CapturingChatDeepSeek.all_messages
        for message in messages
        if isinstance(message, SystemMessage)
    ]
    schema_names = [schema.__name__ for schema in CapturingChatDeepSeek.latest_structured_schemas]
    assert "SpeakerPlanResponse" in schema_names
    assert "RoommateReply" in schema_names
    assert "ReviewDraftResponse" in schema_names
    assert any("JSON" in content for content in system_messages)
    assert any("rewrite_suggestions" in content for content in system_messages)
    assert any("完整 dialogue" in content for content in system_messages)
    assert any("不要固定选择最后一句" in content for content in system_messages)
    assert any("speaker=user" in content for content in system_messages)
    assert any("不能选择虚拟舍友或系统消息" in content for content in system_messages)
    assert any("roommate_id" in content for content in system_messages)
    assert any('"roommate"' in content for content in system_messages)
    assert any('"personality"' in content for content in system_messages)


def test_langchain_runner_sends_archive_insight_schema_and_prompt(
    monkeypatch,
    archive_events_and_analysis,
):
    CapturingChatDeepSeek.latest_messages = None
    CapturingChatDeepSeek.latest_structured_kwargs = None
    monkeypatch.setattr("langchain_deepseek.ChatDeepSeek", CapturingInvokeChatDeepSeek)
    runner = LangChainDeepSeekRunner(
        settings=AISettings(
            api_key="deepseek-key",
            model="deepseek-v4-flash",
            base_url="https://api.deepseek.com",
            timeout=20.0,
        )
    )
    events, analysis = archive_events_and_analysis

    response = runner.generate_archive_insight(events, analysis)

    assert isinstance(response, ArchiveInsightResponse)
    assert CapturingChatDeepSeek.latest_structured_kwargs == {"method": "json_mode"}
    assert CapturingChatDeepSeek.latest_messages is not None
    system_messages = [
        str(message.content)
        for message in CapturingChatDeepSeek.latest_messages
        if isinstance(message, SystemMessage)
    ]
    human_messages = [
        str(message.content)
        for message in CapturingChatDeepSeek.latest_messages
        if isinstance(message, HumanMessage)
    ]
    assert any("ArchiveInsightResponse" in content for content in system_messages)
    assert any("archive insight" in content for content in system_messages)
    assert any("events:" in content for content in human_messages)
    assert any("archive_analysis:" in content for content in human_messages)


def test_default_service_constructs_without_llm_api_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    service = DormHarmonyAIService()
    request = SimulateRequest(scenario="噪音冲突", user_message="晚上能不能小声一点？")

    with pytest.raises(AIServiceConfigurationError):
        service.simulate(request)


def test_langchain_runner_can_be_constructed_with_settings(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    runner = LangChainDeepSeekRunner(settings=load_ai_settings())

    assert runner.model == "deepseek-v4-flash"
