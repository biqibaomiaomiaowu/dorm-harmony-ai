from datetime import date, datetime
import sys
import types

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

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


class FakeRunner:
    def generate_simulation(self, request):
        return SimulateResponse(
            replies=[
                RoommateReply(
                    roommate="舍友 A",
                    personality="直接型",
                    message="我也没开很大声吧，但可以试着戴耳机。",
                ),
                RoommateReply(
                    roommate="舍友 B",
                    personality="回避型",
                    message="这个事情我现在不太想聊，但可以晚点再说。",
                ),
                RoommateReply(
                    roommate="舍友 C",
                    personality="调和型",
                    message="我们可以一起定一个晚上安静时间。",
                ),
            ],
            safety_note=SIMULATE_SAFETY_NOTE,
        )

    def generate_review(self, request):
        return ReviewResponse(
            summary="用户表达了睡眠受影响的事实，整体语气较温和。",
            strengths=["说明了具体影响"],
            risks=["可以进一步明确时间范围"],
            performance_scores=REVIEW_PERFORMANCE_SCORES,
            rewritten_message="我最近睡眠状态不太好，晚上 11 点后能不能戴耳机或调低音量？",
            next_steps=["选择双方情绪平稳的时间沟通"],
            safety_note=REVIEW_SAFETY_NOTE,
        )

    def generate_archive_insight(self, events, analysis):
        return ArchiveInsightResponse(
            insight="近 30 天噪音事件集中出现，主要压力来自休息边界被反复打断。",
            care_suggestion="先照顾睡眠和情绪稳定，再选择白天提出具体规则。",
            communication_focus=["围绕 11 点后的安静规则沟通"],
            safety_note=ARCHIVE_INSIGHT_SAFETY_NOTE,
        )


class BrokenRunner:
    def generate_simulation(self, request):
        raise RuntimeError("network exploded with secret sk-test")

    def generate_review(self, request):
        raise RuntimeError("network exploded with secret sk-test")

    def generate_archive_insight(self, events, analysis):
        raise RuntimeError("network exploded with secret sk-test")


class BadShapeRunner:
    def generate_simulation(self, request):
        return {"replies": []}

    def generate_review(self, request):
        return {"summary": "missing fields"}

    def generate_archive_insight(self, events, analysis):
        return {"insight": "missing fields"}


class DictRunner:
    def generate_simulation(self, request):
        return {
            "replies": [
                {
                    "roommate": "舍友 A",
                    "personality": "直接型",
                    "message": "我确实声音可能有点大，可以把音量调低。",
                },
                {
                    "roommate": "舍友 B",
                    "personality": "回避型",
                    "message": "我先记一下，之后我们可以再具体说。",
                },
                {
                    "roommate": "舍友 C",
                    "personality": "调和型",
                    "message": "我们可以约定晚上 11 点后戴耳机。",
                },
            ],
            "safety_note": SIMULATE_SAFETY_NOTE,
        }

    def generate_review(self, request):
        return {
            "summary": "用户表达了休息需求，语气相对清楚。",
            "strengths": ["说明了受影响的具体时间"],
            "risks": ["可以避免使用绝对化指责"],
            "performance_scores": REVIEW_PERFORMANCE_SCORES,
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

    def with_structured_output(self, schema):
        return ExplodingStructuredLLM()


class CapturingStructuredLLM:
    def __init__(self, schema):
        self.schema = schema

    def invoke(self, messages):
        if self.schema is ArchiveInsightResponse:
            return {
                "insight": "近 30 天噪音事件集中出现，主要压力来自休息边界被反复打断。",
                "care_suggestion": "先照顾睡眠和情绪稳定，再选择白天提出具体规则。",
                "communication_focus": ["围绕 11 点后的安静规则沟通"],
                "safety_note": ARCHIVE_INSIGHT_SAFETY_NOTE,
            }

        return {
            "replies": [
                {
                    "roommate": "舍友 A",
                    "personality": "直接型",
                    "message": "我确实声音可能有点大，可以把音量调低。",
                },
                {
                    "roommate": "舍友 B",
                    "personality": "回避型",
                    "message": "我先记一下，之后我们可以再具体说。",
                },
                {
                    "roommate": "舍友 C",
                    "personality": "调和型",
                    "message": "我们可以约定晚上 11 点后戴耳机。",
                },
            ],
            "safety_note": SIMULATE_SAFETY_NOTE,
        }


class CapturingChatDeepSeek:
    latest_kwargs = None
    latest_structured_kwargs = None
    latest_messages = None

    def __init__(self, **kwargs):
        CapturingChatDeepSeek.latest_kwargs = kwargs

    def with_structured_output(self, schema, **kwargs):
        CapturingChatDeepSeek.latest_structured_kwargs = kwargs
        return CapturingStructuredLLM(schema)


class CapturingInvokeStructuredLLM(CapturingStructuredLLM):
    def invoke(self, messages):
        CapturingChatDeepSeek.latest_messages = messages
        return super().invoke(messages)


class CapturingInvokeChatDeepSeek(CapturingChatDeepSeek):
    def with_structured_output(self, schema, **kwargs):
        CapturingChatDeepSeek.latest_structured_kwargs = kwargs
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


def test_service_returns_simulation_from_runner():
    request = SimulateRequest(scenario="噪音冲突", user_message="晚上能不能小声一点？")
    service = DormHarmonyAIService(runner=FakeRunner())

    response = service.simulate(request)

    assert [reply.roommate for reply in response.replies] == ["舍友 A", "舍友 B", "舍友 C"]
    assert "不进行心理诊断" in response.safety_note


def test_service_returns_review_from_runner():
    request = ReviewRequest(
        scenario="噪音冲突",
        dialogue=[DialogueMessage(speaker="user", message="晚上能不能小声一点？")],
    )
    service = DormHarmonyAIService(runner=FakeRunner())

    response = service.review(request)

    assert response.strengths
    assert response.performance_scores.clarity == 82
    assert "不进行心理诊断" in response.safety_note


def test_service_returns_archive_insight_from_runner(archive_events_and_analysis):
    events, analysis = archive_events_and_analysis
    service = DormHarmonyAIService(runner=FakeRunner())

    response = service.archive_insight(events, analysis)

    assert isinstance(response, ArchiveInsightResponse)
    assert "噪音事件" in response.insight
    assert response.communication_focus == ["围绕 11 点后的安静规则沟通"]


def test_service_normalizes_simulation_dict_from_runner():
    request = SimulateRequest(scenario="噪音冲突", user_message="晚上能不能小声一点？")
    service = DormHarmonyAIService(runner=DictRunner())

    response = service.simulate(request)

    assert isinstance(response, SimulateResponse)
    assert response.replies[0].roommate == "舍友 A"
    assert response.replies[2].message == "我们可以约定晚上 11 点后戴耳机。"


def test_service_normalizes_review_dict_from_runner():
    request = ReviewRequest(
        scenario="噪音冲突",
        dialogue=[DialogueMessage(speaker="user", message="晚上能不能小声一点？")],
    )
    service = DormHarmonyAIService(runner=DictRunner())

    response = service.review(request)

    assert isinstance(response, ReviewResponse)
    assert response.summary == "用户表达了休息需求，语气相对清楚。"
    assert response.performance_scores.empathy == 76
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
    service = DormHarmonyAIService(runner=BrokenRunner())

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
    service = DormHarmonyAIService(runner=BadShapeRunner())

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
        runner.generate_simulation(request)

    assert_exception_chain_is_sanitized(exc_info.value)


def test_langchain_runner_passes_deepseek_configuration_to_chat_deepseek(monkeypatch):
    CapturingChatDeepSeek.latest_kwargs = None
    CapturingChatDeepSeek.latest_structured_kwargs = None
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

    response = runner.generate_simulation(request)

    assert response.replies[0].roommate == "舍友 A"
    assert CapturingChatDeepSeek.latest_kwargs == {
        "model": "deepseek-v4-flash",
        "temperature": 0.3,
        "timeout": 20.0,
        "max_retries": 1,
        "api_key": "deepseek-key",
        "api_base": "https://api.deepseek.com",
    }
    assert CapturingChatDeepSeek.latest_structured_kwargs == {"method": "json_mode"}


def test_langchain_runner_sends_json_contract_prompt(monkeypatch):
    CapturingChatDeepSeek.latest_messages = None
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

    runner.generate_simulation(request)

    assert CapturingChatDeepSeek.latest_messages is not None
    system_messages = [
        str(message.content)
        for message in CapturingChatDeepSeek.latest_messages
        if isinstance(message, SystemMessage)
    ]
    assert any("JSON" in content for content in system_messages)
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
