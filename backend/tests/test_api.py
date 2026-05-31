import inspect
import json
from datetime import date, timedelta

import pytest

import app.ai_service as ai_service
from app.ai_service import (
    AIServiceConfigurationError,
    AIServiceUnavailableError,
    ConversationMemoryNotFoundError,
    DormHarmonyAIService,
)
from app.event_store import InMemoryEventStore
from app.main import (
    _get_cors_origins,
    app,
    get_ai_service,
    get_event_store,
    get_review_history_store,
    archive_insight,
    review,
    simulate,
)
from app.review_store import SQLiteReviewHistoryStore
from app.safety import SAFETY_DISCLAIMER
from app.schemas import (
    ArchiveInsightResponse,
    DialogueMessage,
    EventRecordCreate,
    ReviewRequest,
    ReviewResponse,
    RoommateReply,
    SimulateResponse,
)
from tests.api_test_client import ApiTestClient


client = ApiTestClient(app)
REVIEW_PERFORMANCE_SCORES = {"clarity": 82, "empathy": 76, "resolution": 71}
REVIEW_REWRITE_SUGGESTIONS = [
    {
        "message_index": 0,
        "original_message": "能不能晚上小声一点？",
        "issue": "请求还可以更具体。",
        "suggested_message": "我最近 11 点后比较需要休息，可以麻烦你那之后降低音量吗？",
        "reason": "把影响、时间和行动请求说清楚。",
    }
]


class FakeAIService:
    def simulate(self, request, archive_context_summary=None):
        return SimulateResponse(
            conversation_id=request.conversation_id or "conversation-1",
            replies=[
                RoommateReply(
                    roommate_id="roommate_a",
                    roommate="舍友 A",
                    personality="直接型",
                    message="我知道你觉得吵，我会注意音量。",
                ),
                RoommateReply(
                    roommate_id="roommate_b",
                    roommate="舍友 B",
                    personality="回避型",
                    message="我可能没意识到已经影响你了，可以再提醒我。",
                ),
                RoommateReply(
                    roommate_id="roommate_c",
                    roommate="舍友 C",
                    personality="调和型",
                    message="我们可以一起约定 11 点后的安静时间。",
                ),
            ],
            archive_context_used=archive_context_summary is not None,
            archive_context_summary=archive_context_summary,
            safety_note=(
                "仅用于宿舍沟通演练，不代表真实舍友想法，不进行心理诊断，"
                "不进行医学判断，不进行人格评价；如冲突升级请寻求辅导员或心理老师等现实支持。"
            ),
        )

    def review(self, request):
        return ReviewResponse(
            summary="表达了睡眠受影响的具体困扰。",
            strengths=["说明了具体时间和影响", "语气保持克制"],
            risks=["可能让对方觉得被指责"],
            performance_scores=REVIEW_PERFORMANCE_SCORES,
            rewrite_suggestions=REVIEW_REWRITE_SUGGESTIONS,
            rewritten_message="我最近 11 点后比较需要休息，可以麻烦你那之后降低音量吗？",
            next_steps=["先约定安静时段", "必要时请辅导员协助沟通"],
            safety_note=(
                "仅用于沟通训练建议，不代表真实舍友想法，不进行心理诊断，"
                "不进行医学判断，不进行人格评价；如持续困扰请联系辅导员或心理老师获得现实支持。"
            ),
        )

    def archive_insight(self, events, analysis):
        return ArchiveInsightResponse(
            insight="事件主要集中在夜间噪音，当前压力更多来自休息边界被持续打断。",
            care_suggestion="先保证睡眠和情绪恢复，再选择白天提出 11 点后的安静规则。",
            communication_focus=["明确 11 点后的耳机规则", "用具体影响表达需求"],
            safety_note=(
                "仅用于沟通训练建议，不代表真实舍友想法，不进行心理诊断，"
                "不进行医学判断，不进行人格评价；如压力持续升高请联系辅导员或心理老师寻求现实支持。"
            ),
        )


class MissingKeyService:
    def simulate(self, request, archive_context_summary=None):
        raise AIServiceConfigurationError(
            "AI 服务未配置：请设置 DEEPSEEK_API_KEY（推荐）或 OPENAI_API_KEY（兼容旧配置）。"
        )

    def review(self, request):
        raise AIServiceConfigurationError(
            "AI 服务未配置：请设置 DEEPSEEK_API_KEY（推荐）或 OPENAI_API_KEY（兼容旧配置）。"
        )

    def archive_insight(self, events, analysis):
        raise AIServiceConfigurationError(
            "AI 服务未配置：请设置 DEEPSEEK_API_KEY（推荐）或 OPENAI_API_KEY（兼容旧配置）。"
        )


class BrokenAIService:
    def simulate(self, request, archive_context_summary=None):
        raise AIServiceUnavailableError("AI 服务暂时不可用，请稍后重试。")

    def review(self, request):
        raise AIServiceUnavailableError("AI 服务暂时不可用，请稍后重试。")

    def archive_insight(self, events, analysis):
        raise AIServiceUnavailableError("AI 服务暂时不可用，请稍后重试。")


class MissingMemoryService:
    def simulate(self, request, archive_context_summary=None):
        raise ConversationMemoryNotFoundError("未找到对应的模拟对话，请回到模拟页重新演练。")

    def review(self, request):
        raise ConversationMemoryNotFoundError("未找到对应的模拟对话，请回到模拟页重新演练。")

    def archive_insight(self, events, analysis):
        raise AssertionError("archive_insight should not be called")


class CapturingSimulateService(FakeAIService):
    def __init__(self):
        self.simulate_request = None
        self.archive_context_summary = None

    def simulate(self, request, archive_context_summary=None):
        self.simulate_request = request
        self.archive_context_summary = archive_context_summary
        return super().simulate(request, archive_context_summary=archive_context_summary)


class CapturingArchiveInsightService(FakeAIService):
    def __init__(self):
        self.archive_insight_called = False
        self.received_events = None
        self.received_analysis = None

    def archive_insight(self, events, analysis):
        self.archive_insight_called = True
        self.received_events = list(events)
        self.received_analysis = analysis
        return super().archive_insight(events, analysis)


class UnsafeArchiveInsightRunner:
    def generate_simulation(self, request):
        raise AssertionError("simulate should not be called")

    def generate_review(self, request):
        raise AssertionError("review should not be called")

    def generate_archive_insight(self, events, analysis):
        return {
            "insight": "事件主要集中在夜间噪音。",
            "care_suggestion": "先保证睡眠和情绪恢复。",
            "communication_focus": ["明确 11 点后的耳机规则"],
            "safety_note": "祝你沟通顺利。",
        }


class CapturingReviewService(FakeAIService):
    def __init__(self):
        self.review_request = None

    def review(self, request):
        self.review_request = request
        return super().review(request)


class RouteMemoryRunner:
    plan_histories = []

    def __init__(self, *args, **kwargs):
        pass

    def plan_simulation_replies(self, request, history, archive_context_summary=None):
        self.__class__.plan_histories.append(list(history))
        return ai_service.SpeakerPlanResponse(replies=[{"roommate_id": "roommate_a"}])

    def generate_roommate_reply(
        self,
        request,
        history,
        archive_context_summary,
        same_turn_replies,
        roommate,
    ):
        return RoommateReply(
            roommate_id="roommate_a",
            roommate="舍友 A",
            personality="直接型",
            message="我会注意音量。",
        )

    def generate_review(self, request, dialogue):
        return FakeAIService().review(request)

    def generate_archive_insight(self, events, analysis):
        return FakeAIService().archive_insight(events, analysis)


def assert_llm_key_hint(detail):
    assert "DEEPSEEK_API_KEY" in detail
    assert "OPENAI_API_KEY" in detail


def create_noise_event_for_archive():
    return client.post(
        "/api/events",
        json={
            "event_date": date.today().isoformat(),
            "event_type": "noise",
            "severity": 4,
            "frequency": "weekly_multiple",
            "emotion": "anxious",
            "has_communicated": False,
            "has_conflict": True,
            "description": "舍友晚上打游戏声音很大，影响睡眠。",
        },
    )


@pytest.fixture(autouse=True)
def clear_dependency_overrides(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "DORM_HARMONY_SQLITE_PATH",
        str(tmp_path / "dorm_harmony.sqlite3"),
    )
    monkeypatch.setenv(
        "DORM_HARMONY_EVENT_STORE_PATH",
        str(tmp_path / "missing-events.json"),
    )
    app.dependency_overrides.pop(get_ai_service, None)
    app.dependency_overrides.pop(get_event_store, None)
    app.dependency_overrides.pop(get_review_history_store, None)
    yield
    app.dependency_overrides.pop(get_ai_service, None)
    app.dependency_overrides.pop(get_event_store, None)
    app.dependency_overrides.pop(get_review_history_store, None)


def test_health_endpoint_returns_ok_status():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_training_catalog_endpoint_returns_v4_catalog():
    response = client.get("/api/training/catalog")

    assert response.status_code == 200
    data = response.json()

    assert [category["id"] for category in data["categories"]] == [
        "noise",
        "schedule",
        "hygiene",
        "cost",
        "privacy",
        "emotion",
    ]
    assert [scenario["id"] for scenario in data["scenarios"]] == [
        "noise_game_night",
        "noise_video_noon",
        "schedule_lights_out_chat",
        "schedule_morning_wash",
        "hygiene_trash",
        "hygiene_shared_desk",
        "cost_utility_split",
        "cost_public_items",
        "privacy_borrow_items",
        "privacy_visitors",
        "emotion_cold_war",
        "emotion_tone_uncomfortable",
    ]
    assert [target["id"] for target in data["targets"]] == [
        "express_feeling",
        "make_request",
        "negotiate_rule",
        "respond_objection",
        "repair_relationship",
    ]
    assert [difficulty["id"] for difficulty in data["difficulties"]] == [
        "beginner",
        "intermediate",
        "advanced",
        "challenge",
    ]

    assert len(data["categories"]) == 6
    assert len(data["scenarios"]) == 12
    assert len(data["targets"]) == 5
    assert len(data["difficulties"]) == 4
    assert all(category["label"].strip() for category in data["categories"])
    assert all(scenario["title"].strip() for scenario in data["scenarios"])
    assert all(target["label"].strip() for target in data["targets"])
    assert all(difficulty["label"].strip() for difficulty in data["difficulties"])


def test_analyze_endpoint_returns_structured_pressure_analysis():
    response = client.post(
        "/api/analyze",
        json={
            "event_type": "noise",
            "severity": 4,
            "frequency": "weekly_multiple",
            "emotion": "anxious",
            "has_communicated": False,
            "has_conflict": True,
            "description": "舍友晚上打游戏声音很大，影响睡眠。",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body.keys() == {
        "pressure_score",
        "risk_level",
        "risk_label",
        "main_sources",
        "emotion_keywords",
        "trend_message",
        "suggestion",
        "recommend_simulation",
        "disclaimer",
    }
    assert body["pressure_score"] == 76
    assert body["risk_level"] == "high"
    assert body["risk_label"] == "冲突风险较高"
    assert body["main_sources"] == ["噪音冲突", "发生频率较高", "尚未有效沟通", "已出现争吵或冷战"]
    assert body["emotion_keywords"] == ["焦虑"]
    assert body["recommend_simulation"] is True
    assert "当前压力值为 76" in body["trend_message"]
    assert "沟通演练" in body["suggestion"]
    assert body["disclaimer"] == SAFETY_DISCLAIMER


def test_analyze_endpoint_accepts_multiple_emotions():
    response = client.post(
        "/api/analyze",
        json={
            "event_type": "noise",
            "severity": 4,
            "frequency": "weekly_multiple",
            "emotion": "helpless",
            "emotions": ["helpless", "angry", "helpless"],
            "primary_emotion": "helpless",
            "has_communicated": False,
            "has_conflict": True,
            "description": "舍友晚上打游戏声音很大，我很无奈也有点生气。",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["emotion_keywords"] == ["无奈", "愤怒"]
    assert body["pressure_score"] > 70


def test_create_event_record_returns_saved_event_and_single_analysis():
    app.dependency_overrides[get_event_store] = lambda: InMemoryEventStore()

    response = client.post(
        "/api/events",
        json={
            "event_date": "2026-05-15",
            "event_type": "noise",
            "severity": 4,
            "frequency": "weekly_multiple",
            "emotion": "anxious",
            "has_communicated": False,
            "has_conflict": True,
            "description": "舍友晚上打游戏声音很大，影响睡眠。",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["event_date"] == "2026-05-15"
    assert body["single_analysis"]["pressure_score"] == 76


def test_create_event_record_rejects_future_event_date():
    app.dependency_overrides[get_event_store] = lambda: InMemoryEventStore()

    response = client.post(
        "/api/events",
        json={
            "event_date": date.max.isoformat(),
            "event_type": "noise",
            "severity": 4,
            "frequency": "weekly_multiple",
            "emotion": "anxious",
            "has_communicated": False,
            "has_conflict": True,
            "description": "舍友晚上打游戏声音很大，影响睡眠。",
        },
    )

    assert response.status_code == 422


def test_list_event_records_returns_archive_ordered_by_store():
    event_store = InMemoryEventStore()
    app.dependency_overrides[get_event_store] = lambda: event_store

    first_response = client.post(
        "/api/events",
        json={
            "event_date": "2026-05-14",
            "event_type": "noise",
            "severity": 3,
            "frequency": "occasional",
            "emotion": "irritable",
            "has_communicated": True,
            "has_conflict": False,
            "description": "旧事件。",
        },
    )
    second_response = client.post(
        "/api/events",
        json={
            "event_date": "2026-05-15",
            "event_type": "noise",
            "severity": 4,
            "frequency": "weekly_multiple",
            "emotion": "anxious",
            "has_communicated": False,
            "has_conflict": True,
            "description": "新事件。",
        },
    )
    response = client.get("/api/events")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert response.status_code == 200
    body = response.json()
    assert body.keys() == {"events"}
    assert [event["event_date"] for event in body["events"]] == [
        "2026-05-15",
        "2026-05-14",
    ]
    assert body["events"][0]["single_analysis"]["pressure_score"] == 76


def test_event_analysis_endpoint_returns_archive_pressure_for_shared_store():
    event_store = InMemoryEventStore()
    app.dependency_overrides[get_event_store] = lambda: event_store
    today = date.today().isoformat()

    create_response = client.post(
        "/api/events",
        json={
            "event_date": today,
            "event_type": "noise",
            "severity": 4,
            "frequency": "weekly_multiple",
            "emotion": "anxious",
            "has_communicated": False,
            "has_conflict": True,
            "description": "舍友晚上打游戏声音很大，影响睡眠。",
        },
    )
    response = client.get("/api/events/analysis")

    assert create_response.status_code == 200
    assert response.status_code == 200
    body = response.json()
    assert body["pressure_score"] == 76
    assert body["risk_level"] == "high"
    assert body["main_sources"] == ["噪音冲突"]
    assert body["event_count"] == 1
    assert body["active_30d_count"] == 1
    assert body["source_breakdown"] == [
        {"label": "噪音冲突", "percent": 100, "contribution": 76.0}
    ]
    assert sum(source["percent"] for source in body["source_breakdown"]) == 100
    for source in body["source_breakdown"]:
        assert 0 <= source["percent"] <= 100
        assert source["contribution"] >= 0


def test_event_analysis_endpoint_handles_empty_archive():
    event_store = InMemoryEventStore()
    app.dependency_overrides[get_event_store] = lambda: event_store

    response = client.get("/api/events/analysis")

    assert response.status_code == 200
    body = response.json()
    assert body["pressure_score"] == 0
    assert body["risk_level"] == "stable"
    assert body["event_count"] == 0
    assert body["source_breakdown"] == []
    assert "先记录事件" in body["suggestion"]


def test_event_analysis_endpoint_accepts_supported_range_days():
    event_store = InMemoryEventStore()
    app.dependency_overrides[get_event_store] = lambda: event_store

    for event_date, description in (
        (date.today(), "今天的噪音事件。"),
        (date.today() - timedelta(days=8), "稍早的噪音事件。"),
    ):
        event_store.add(
            EventRecordCreate(
                event_date=event_date,
                event_type="noise",
                severity=4,
                frequency="weekly_multiple",
                emotion="anxious",
                has_communicated=False,
                has_conflict=True,
                description=description,
            )
        )

    default_response = client.get("/api/events/analysis")
    range_7_response = client.get("/api/events/analysis?range_days=7")
    range_90_response = client.get("/api/events/analysis?range_days=90")

    assert default_response.status_code == 200
    assert default_response.json()["period_days"] == 30
    assert range_7_response.status_code == 200
    assert range_90_response.status_code == 200

    range_7_body = range_7_response.json()
    assert range_7_body["period_days"] == 7
    assert range_7_body["active_period_count"] == 1
    for field in (
        "trend_points",
        "trend_explanation",
        "source_insights",
        "main_source_conclusion",
        "emotion_distribution",
        "event_insight",
        "training_recommendation",
    ):
        assert field in range_7_body

    range_90_body = range_90_response.json()
    assert range_90_body["period_days"] == 90
    assert range_90_body["active_period_count"] == 2


def test_event_analysis_range_7_uses_period_events_for_derived_metrics():
    event_store = InMemoryEventStore()
    app.dependency_overrides[get_event_store] = lambda: event_store
    today = date.today()
    recent_event = event_store.add(
        EventRecordCreate(
            event_date=today,
            event_type="noise",
            severity=2,
            frequency="occasional",
            emotion="helpless",
            has_communicated=True,
            has_conflict=False,
            description="今天公共桌面偶尔有点乱，已经提醒过一次。",
        )
    )
    event_store.add(
        EventRecordCreate(
            event_date=today - timedelta(days=8),
            event_type="hygiene",
            severity=5,
            frequency="daily",
            emotion="angry",
            has_communicated=False,
            has_conflict=True,
            description="8 天前公共区域长期没人整理，已经争吵。",
        )
    )

    response = client.get("/api/events/analysis?range_days=7")

    assert response.status_code == 200
    body = response.json()
    expected_score = recent_event.single_analysis.pressure_score
    assert body["event_count"] == 2
    assert body["active_30d_count"] == 2
    assert body["active_period_count"] == 1
    assert body["pressure_score"] == expected_score
    assert body["risk_level"] == recent_event.single_analysis.risk_level
    assert body["main_sources"] == ["噪音冲突"]
    assert body["source_breakdown"] == [
        {
            "label": "噪音冲突",
            "percent": 100,
            "contribution": float(expected_score),
        }
    ]
    assert body["trend_points"] == [
        {
            "date": today.isoformat(),
            "pressure_score": expected_score,
            "event_count": 1,
        }
    ]
    assert "1 个记录日期" in body["trend_explanation"]
    assert body["source_insights"] == [
        {
            "rank": 1,
            "label": "噪音冲突",
            "percent": 100,
            "contribution": float(expected_score),
            "event_count": 1,
            "recent_event_date": today.isoformat(),
            "explanation": (
                f"噪音冲突占档案压力约 100%，共有 1 条相关记录，"
                f"最近一次在 {today.isoformat()}（今天）。"
            ),
        }
    ]
    assert "噪音冲突" in body["main_source_conclusion"]
    assert "卫生冲突" not in body["main_source_conclusion"]
    assert body["emotion_distribution"] == [
        {"emotion": "helpless", "label": "无奈", "count": 1, "percent": 100}
    ]
    assert body["event_insight"]["period_days"] == 7
    assert body["event_insight"]["period_event_count"] == 1
    assert body["event_insight"]["top_event_types"] == ["噪音冲突"]
    assert body["event_insight"]["top_emotions"] == ["无奈"]
    assert body["event_insight"]["conflict_count"] == 0
    assert "卫生冲突" not in body["event_insight"]["summary"]
    assert "愤怒" not in body["event_insight"]["summary"]
    assert body["training_recommendation"]["category_id"] == "noise"
    assert "近 7 天 1 条" in body["trend_message"]


def test_event_analysis_range_7_empty_period_keeps_archive_count_and_stable_metrics():
    event_store = InMemoryEventStore()
    app.dependency_overrides[get_event_store] = lambda: event_store
    today = date.today()
    event_store.add(
        EventRecordCreate(
            event_date=today - timedelta(days=8),
            event_type="hygiene",
            severity=5,
            frequency="daily",
            emotion="angry",
            has_communicated=False,
            has_conflict=True,
            description="8 天前公共区域长期没人整理，已经争吵。",
        )
    )

    response = client.get("/api/events/analysis?range_days=7")

    assert response.status_code == 200
    body = response.json()
    assert body["event_count"] == 1
    assert body["active_30d_count"] == 1
    assert body["active_period_count"] == 0
    assert body["pressure_score"] == 0
    assert body["risk_level"] == "stable"
    assert body["main_sources"] == []
    assert body["emotion_keywords"] == []
    assert body["source_breakdown"] == []
    assert body["emotion_distribution"] == []
    assert body["training_recommendation"] is None
    assert "当前周期内暂无事件记录" in body["trend_message"]


def test_event_analysis_endpoint_rejects_invalid_range_days():
    response = client.get("/api/events/analysis?range_days=14")

    assert response.status_code == 422
    assert response.json()["detail"] == "range_days must be one of 7, 15, 30, 90"


def test_delete_event_record_removes_event_from_archive():
    event_store = InMemoryEventStore()
    app.dependency_overrides[get_event_store] = lambda: event_store

    create_response = client.post(
        "/api/events",
        json={
            "event_date": date.today().isoformat(),
            "event_type": "noise",
            "severity": 4,
            "frequency": "weekly_multiple",
            "emotion": "anxious",
            "has_communicated": False,
            "has_conflict": True,
            "description": "舍友晚上打游戏声音很大，影响睡眠。",
        },
    )
    event_id = create_response.json()["id"]

    delete_response = client.delete(f"/api/events/{event_id}")
    list_response = client.get("/api/events")

    assert create_response.status_code == 200
    assert delete_response.status_code == 204
    assert delete_response.content == b""
    assert list_response.status_code == 200
    assert list_response.json() == {"events": []}


def test_delete_event_record_returns_404_for_missing_event():
    event_store = InMemoryEventStore()
    app.dependency_overrides[get_event_store] = lambda: event_store

    response = client.delete("/api/events/missing-event")

    assert response.status_code == 404
    assert response.json()["detail"] == "事件档案不存在或已被删除。"


def test_event_analysis_recomputes_after_event_deletion():
    event_store = InMemoryEventStore()
    app.dependency_overrides[get_event_store] = lambda: event_store
    today = date.today().isoformat()

    first_response = client.post(
        "/api/events",
        json={
            "event_date": today,
            "event_type": "noise",
            "severity": 4,
            "frequency": "weekly_multiple",
            "emotion": "anxious",
            "has_communicated": False,
            "has_conflict": True,
            "description": "舍友晚上打游戏声音很大，影响睡眠。",
        },
    )
    second_response = client.post(
        "/api/events",
        json={
            "event_date": today,
            "event_type": "hygiene",
            "severity": 2,
            "frequency": "occasional",
            "emotion": "helpless",
            "has_communicated": True,
            "has_conflict": False,
            "description": "公共区域偶尔没人整理，但已经协商过一次。",
        },
    )

    delete_response = client.delete(f"/api/events/{first_response.json()['id']}")
    analysis_response = client.get("/api/events/analysis")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert delete_response.status_code == 204
    assert analysis_response.status_code == 200
    body = analysis_response.json()
    assert body["event_count"] == 1
    assert body["pressure_score"] == second_response.json()["single_analysis"]["pressure_score"]
    assert body["main_sources"] == ["卫生冲突"]


def test_deleting_last_event_resets_analysis_and_blocks_archive_insight():
    event_store = InMemoryEventStore()
    ai_service = CapturingArchiveInsightService()
    app.dependency_overrides[get_event_store] = lambda: event_store
    app.dependency_overrides[get_ai_service] = lambda: ai_service

    create_response = create_noise_event_for_archive()
    delete_response = client.delete(f"/api/events/{create_response.json()['id']}")
    analysis_response = client.get("/api/events/analysis")
    insight_response = client.post("/api/events/insight")

    assert create_response.status_code == 200
    assert delete_response.status_code == 204
    assert analysis_response.status_code == 200
    assert analysis_response.json()["pressure_score"] == 0
    assert analysis_response.json()["event_count"] == 0
    assert insight_response.status_code == 400
    assert ai_service.archive_insight_called is False


def test_cors_preflight_allows_delete_for_local_vite_frontend():
    response = client.options(
        "/api/events/some-event",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "DELETE",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_preflight_allows_local_vite_frontend():
    response = client.options(
        "/api/analyze",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_preflight_allows_local_vite_frontend_by_ip():
    response = client.options(
        "/api/analyze",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


def test_cors_origin_loader_accepts_comma_separated_override(monkeypatch):
    monkeypatch.setenv(
        "DORM_HARMONY_CORS_ORIGINS",
        "http://localhost:3000, http://127.0.0.1:7357",
    )

    assert _get_cors_origins() == ["http://localhost:3000", "http://127.0.0.1:7357"]


def test_analyze_endpoint_rejects_out_of_range_severity():
    response = client.post(
        "/api/analyze",
        json={
            "event_type": "noise",
            "severity": 6,
            "frequency": "daily",
            "emotion": "angry",
            "has_communicated": False,
            "has_conflict": True,
            "description": "测试严重程度越界。",
        },
    )

    assert response.status_code == 422


def test_ai_endpoints_run_as_sync_functions_for_threadpool_execution():
    assert not inspect.iscoroutinefunction(simulate)
    assert not inspect.iscoroutinefunction(archive_insight)
    assert not inspect.iscoroutinefunction(review)


def test_simulate_endpoint_returns_structured_roommate_replies():
    app.dependency_overrides[get_ai_service] = lambda: FakeAIService()

    response = client.post(
        "/api/simulate",
        json={
            "scenario": "舍友晚上打游戏声音很大，影响睡眠。",
            "user_message": "能不能晚上小声一点？",
            "risk_level": "high",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert [reply["roommate"] for reply in body["replies"]] == [
        "舍友 A",
        "舍友 B",
        "舍友 C",
    ]
    assert "不进行心理诊断" in body["safety_note"]


def test_simulate_endpoint_passes_archive_context_summary_when_requested():
    event_store = InMemoryEventStore()
    service = CapturingSimulateService()
    app.dependency_overrides[get_event_store] = lambda: event_store
    app.dependency_overrides[get_ai_service] = lambda: service

    create_response = create_noise_event_for_archive()
    response = client.post(
        "/api/simulate",
        json={
            "scenario": "舍友晚上打游戏声音很大，影响睡眠。",
            "user_message": "能不能晚上小声一点？",
            "risk_level": "high",
            "use_event_archive": True,
        },
    )

    assert create_response.status_code == 200
    assert response.status_code == 200
    summary = service.archive_context_summary
    assert summary is not None
    assert len(summary) <= 500
    for expected_text in [
        "事件档案：总事件 1 条",
        "近 30 天 1 条",
        "主要压力来源：噪音冲突",
        "风险：high/冲突风险较高",
        "最近事件：noise",
        "严重程度 4",
        "主要情绪 焦虑",
        "情绪 焦虑",
        "未沟通",
        "有冲突",
        "舍友晚上打游戏声音很大",
    ]:
        assert expected_text in summary
    body = response.json()
    assert body["archive_context_used"] is True
    assert body["archive_context_summary"] == summary


def test_simulate_endpoint_uses_no_archive_context_when_requested_archive_is_empty():
    event_store = InMemoryEventStore()
    service = CapturingSimulateService()
    app.dependency_overrides[get_event_store] = lambda: event_store
    app.dependency_overrides[get_ai_service] = lambda: service

    response = client.post(
        "/api/simulate",
        json={
            "scenario": "舍友晚上打游戏声音很大，影响睡眠。",
            "user_message": "能不能晚上小声一点？",
            "risk_level": "high",
            "use_event_archive": True,
        },
    )

    assert response.status_code == 200
    assert service.archive_context_summary is None
    body = response.json()
    assert body["archive_context_used"] is False
    assert body["archive_context_summary"] is None


def test_default_ai_service_preserves_memory_across_api_requests(monkeypatch):
    RouteMemoryRunner.plan_histories = []
    monkeypatch.setattr(ai_service, "LangChainDeepSeekRunner", RouteMemoryRunner)

    first_response = client.post(
        "/api/simulate",
        json={
            "scenario": "舍友晚上打游戏声音很大，影响睡眠。",
            "user_message": "第一轮请你小声一点。",
            "risk_level": "high",
        },
    )
    conversation_id = first_response.json()["conversation_id"]
    second_response = client.post(
        "/api/simulate",
        json={
            "conversation_id": conversation_id,
            "scenario": "舍友晚上打游戏声音很大，影响睡眠。",
            "user_message": "那我们 11 点后戴耳机可以吗？",
            "risk_level": "high",
        },
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert second_response.json()["conversation_id"] == conversation_id
    assert any(
        message.message == "第一轮请你小声一点。"
        for history in RouteMemoryRunner.plan_histories
        for message in history
    )


def test_simulate_stream_endpoint_returns_ordered_reply_events():
    app.dependency_overrides[get_ai_service] = lambda: FakeAIService()

    with client.stream(
        "POST",
        "/api/simulate/stream",
        json={
            "scenario": "舍友晚上打游戏声音很大，影响睡眠。",
            "user_message": "能不能晚上小声一点？",
            "risk_level": "high",
        },
    ) as response:
        lines = [line for line in response.iter_lines() if line]

    assert response.status_code == 200

    events = [json.loads(line) for line in lines]
    assert [event["type"] for event in events] == [
        "start",
        "reply",
        "reply",
        "reply",
        "final",
    ]
    assert [event["reply"]["roommate"] for event in events[1:4]] == [
        "舍友 A",
        "舍友 B",
        "舍友 C",
    ]
    assert events[-1]["response"]["replies"][0]["roommate"] == "舍友 A"
    assert "不进行心理诊断" in events[-1]["response"]["safety_note"]


def test_simulate_stream_endpoint_includes_conversation_id_and_archive_context_in_final():
    event_store = InMemoryEventStore()
    service = CapturingSimulateService()
    app.dependency_overrides[get_event_store] = lambda: event_store
    app.dependency_overrides[get_ai_service] = lambda: service

    create_response = create_noise_event_for_archive()
    with client.stream(
        "POST",
        "/api/simulate/stream",
        json={
            "scenario": "舍友晚上打游戏声音很大，影响睡眠。",
            "user_message": "能不能晚上小声一点？",
            "risk_level": "high",
            "use_event_archive": True,
        },
    ) as response:
        lines = [line for line in response.iter_lines() if line]

    assert create_response.status_code == 200
    assert response.status_code == 200
    events = [json.loads(line) for line in lines]
    assert events[0] == {"type": "start", "conversation_id": "conversation-1"}
    assert events[-1]["type"] == "final"
    assert events[-1]["response"]["conversation_id"] == "conversation-1"
    assert events[-1]["response"]["archive_context_used"] is True
    assert events[-1]["response"]["archive_context_summary"] == service.archive_context_summary


def test_simulate_endpoint_archive_context_summary_uses_emotion_labels():
    event_store = InMemoryEventStore()
    service = CapturingSimulateService()
    app.dependency_overrides[get_event_store] = lambda: event_store
    app.dependency_overrides[get_ai_service] = lambda: service

    create_response = client.post(
        "/api/events",
        json={
            "event_date": date.today().isoformat(),
            "event_type": "hygiene",
            "severity": 2,
            "frequency": "occasional",
            "emotion": "helpless",
            "emotions": ["helpless", "depressed"],
            "primary_emotion": "helpless",
            "has_communicated": True,
            "has_conflict": False,
            "description": "公共区域有点乱，我很无奈也有些压抑。",
        },
    )
    response = client.post(
        "/api/simulate",
        json={
            "scenario": "公共卫生沟通",
            "user_message": "我们能不能重新分一下公共区域打扫？",
            "use_event_archive": True,
        },
    )

    assert create_response.status_code == 200
    assert response.status_code == 200
    assert service.archive_context_summary is not None
    assert "情绪 无奈、压抑" in service.archive_context_summary
    assert "无助" not in service.archive_context_summary
    assert "低落" not in service.archive_context_summary


def test_review_endpoint_returns_structured_report():
    app.dependency_overrides[get_ai_service] = lambda: FakeAIService()

    response = client.post(
        "/api/review",
        json={
            "scenario": "舍友晚上打游戏声音很大，影响睡眠。",
            "dialogue": [
                {"speaker": "user", "message": "能不能晚上小声一点？"},
                {"speaker": "roommate_a", "message": "我会注意音量。"},
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["strengths"]
    assert body["risks"]
    assert body["performance_scores"] == REVIEW_PERFORMANCE_SCORES
    assert body["rewrite_suggestions"]
    assert "11 点后" in body["rewritten_message"]
    assert "不进行心理诊断" in body["safety_note"]
    assert body["communication_plan"]["opening"]
    assert body["communication_plan"]["specific_request"]
    assert body["communication_plan"]["fallback_plan"]


def test_review_endpoint_persists_report_history(tmp_path):
    store = SQLiteReviewHistoryStore(tmp_path / "reviews.sqlite3")
    app.dependency_overrides[get_ai_service] = lambda: FakeAIService()
    app.dependency_overrides[get_review_history_store] = lambda: store

    create = client.post(
        "/api/review",
        json={
            "conversation_id": "conversation-1",
            "scenario": "舍友晚上打游戏声音很大，影响睡眠。",
            "roommate_names": {"roommate_a": "小安"},
            "dialogue": [
                {"speaker": "user", "message": "能不能晚上小声一点？"},
                {"speaker": "roommate_a", "message": "我会注意音量。"},
            ],
        },
    )
    listing = client.get("/api/reviews")
    report_id = listing.json()["reports"][0]["id"]
    detail = client.get(f"/api/reviews/{report_id}")

    assert create.status_code == 200
    assert listing.status_code == 200
    assert listing.json()["reports"][0]["conversation_id"] == "conversation-1"
    assert listing.json()["reports"][0]["scenario"] == "舍友晚上打游戏声音很大，影响睡眠。"
    assert listing.json()["reports"][0]["summary"] == "表达了睡眠受影响的具体困扰。"
    assert listing.json()["reports"][0]["score_clarity"] == 82
    assert detail.status_code == 200
    detail_body = detail.json()
    assert detail_body["id"] == report_id
    assert detail_body["request"]["conversation_id"] == "conversation-1"
    assert detail_body["request"]["roommate_names"] == {"roommate_a": "小安"}
    assert detail_body["response"] == create.json()
    assert [message["speaker"] for message in detail_body["dialogue"]] == [
        "user",
        "roommate_a",
    ]


def test_review_endpoint_persists_memory_dialogue_when_request_dialogue_empty(tmp_path):
    store = SQLiteReviewHistoryStore(tmp_path / "reviews.sqlite3")
    memory = ai_service.ConversationMemory()
    conversation_id = memory.start_conversation("conversation-memory")
    memory.append_user_message(conversation_id, "昨天 11 点后游戏声音有点影响我休息。")
    memory.append_roommate_message(
        conversation_id,
        "roommate_a",
        "舍友 A",
        "直接型",
        "我没注意到这么晚了，我会把音量调低。",
    )
    service = DormHarmonyAIService(runner=RouteMemoryRunner(), memory=memory)
    app.dependency_overrides[get_ai_service] = lambda: service
    app.dependency_overrides[get_review_history_store] = lambda: store

    create = client.post(
        "/api/review",
        json={
            "conversation_id": conversation_id,
            "scenario": "舍友晚上打游戏声音很大，影响睡眠。",
            "dialogue": [],
        },
    )
    listing = client.get("/api/reviews")
    report_id = listing.json()["reports"][0]["id"]
    detail = client.get(f"/api/reviews/{report_id}")

    assert create.status_code == 200
    assert detail.status_code == 200
    detail_body = detail.json()
    assert detail_body["request"]["dialogue"] == []
    assert detail_body["dialogue"] == [
        {
            "speaker": "user",
            "message": "昨天 11 点后游戏声音有点影响我休息。",
        },
        {
            "speaker": "roommate_a",
            "message": "我没注意到这么晚了，我会把音量调低。",
        },
    ]


def test_review_endpoint_returns_response_when_history_persistence_fails():
    class FailingReviewHistoryStore:
        def add(self, request, response, dialogue):
            raise OSError("sqlite is unavailable")

    app.dependency_overrides[get_ai_service] = lambda: FakeAIService()
    app.dependency_overrides[get_review_history_store] = lambda: FailingReviewHistoryStore()

    response = client.post(
        "/api/review",
        json={
            "scenario": "舍友晚上打游戏声音很大，影响睡眠。",
            "dialogue": [
                {"speaker": "user", "message": "能不能晚上小声一点？"},
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["summary"] == "表达了睡眠受影响的具体困扰。"


def test_review_endpoint_skips_demo_report_history(tmp_path):
    class DemoAIService(FakeAIService):
        def review(self, request):
            response = super().review(request)
            response.is_demo = True
            response.demo_notice = "演示复盘"
            return response

    store = SQLiteReviewHistoryStore(tmp_path / "reviews.sqlite3")
    app.dependency_overrides[get_ai_service] = lambda: DemoAIService()
    app.dependency_overrides[get_review_history_store] = lambda: store

    response = client.post(
        "/api/review",
        json={
            "scenario": "舍友晚上打游戏声音很大，影响睡眠。",
            "dialogue": [
                {"speaker": "user", "message": "能不能晚上小声一点？"},
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["is_demo"] is True
    assert client.get("/api/reviews").json()["reports"] == []


def test_review_history_list_respects_limit_default_and_max(tmp_path):
    store = SQLiteReviewHistoryStore(tmp_path / "reviews.sqlite3")
    app.dependency_overrides[get_review_history_store] = lambda: store
    response = FakeAIService().review(
        ReviewRequest(
            scenario="噪音冲突",
            dialogue=[DialogueMessage(speaker="user", message="能不能晚上小声一点？")],
        )
    )

    for index in range(55):
        store.add(
            ReviewRequest(
                conversation_id=f"conversation-{index}",
                scenario=f"噪音冲突 {index}",
                dialogue=[DialogueMessage(speaker="user", message=f"第 {index} 次沟通。")],
            ),
            response,
            [DialogueMessage(speaker="user", message=f"第 {index} 次沟通。")],
        )

    default_listing = client.get("/api/reviews")
    limited_listing = client.get("/api/reviews?limit=2")
    capped_listing = client.get("/api/reviews?limit=99")

    assert default_listing.status_code == 200
    assert len(default_listing.json()["reports"]) == 20
    assert limited_listing.status_code == 200
    assert len(limited_listing.json()["reports"]) == 2
    assert capped_listing.status_code == 200
    assert len(capped_listing.json()["reports"]) == 50
    assert capped_listing.json()["reports"][0]["scenario"] == "噪音冲突 54"


def test_review_history_detail_returns_404_for_missing_report(tmp_path):
    store = SQLiteReviewHistoryStore(tmp_path / "reviews.sqlite3")
    app.dependency_overrides[get_review_history_store] = lambda: store

    response = client.get("/api/reviews/missing-report")

    assert response.status_code == 404


def test_review_history_delete_removes_report_and_returns_404_afterward(tmp_path):
    store = SQLiteReviewHistoryStore(tmp_path / "reviews.sqlite3")
    app.dependency_overrides[get_ai_service] = lambda: FakeAIService()
    app.dependency_overrides[get_review_history_store] = lambda: store

    create = client.post(
        "/api/review",
        json={
            "conversation_id": "conversation-delete",
            "scenario": "舍友轮流倒垃圾没有按约定执行。",
            "dialogue": [
                {"speaker": "user", "message": "这周能不能按值日表倒垃圾？"},
                {"speaker": "roommate_a", "message": "可以，我今天补上。"},
            ],
        },
    )
    report_id = client.get("/api/reviews").json()["reports"][0]["id"]
    deleted = client.delete(f"/api/reviews/{report_id}")
    missing_detail = client.get(f"/api/reviews/{report_id}")
    empty_listing = client.get("/api/reviews")
    missing_delete = client.delete("/api/reviews/missing-report")

    assert create.status_code == 200
    assert deleted.status_code == 204
    assert missing_detail.status_code == 404
    assert empty_listing.json()["reports"] == []
    assert missing_delete.status_code == 404


def test_review_endpoint_accepts_frontend_display_payload_until_ai_config_check():
    app.dependency_overrides[get_ai_service] = lambda: MissingKeyService()

    response = client.post(
        "/api/review",
        json={
            "scenario": "舍友晚上打游戏声音很大，影响睡眠。",
            "dialogue": [
                {"speaker": "你", "message": "能不能晚上小声一点？"},
                {"speaker": "舍友 A（直接型）", "message": "我会注意音量。"},
                {"speaker": "舍友 C（调和型）", "message": "我们可以约个安静时间。"},
            ],
            "original_event": {
                "event_type": "noise_conflict",
                "severity": 4,
                "frequency": "weekly_multiple",
                "emotion": "anxious",
                "has_communicated": False,
                "has_conflict": True,
                "description": "舍友晚上打游戏声音很大，影响睡眠。",
            },
        },
    )

    assert response.status_code == 503
    assert_llm_key_hint(response.json()["detail"])


def test_review_endpoint_normalizes_frontend_display_payload_for_ai_service():
    service = CapturingReviewService()
    app.dependency_overrides[get_ai_service] = lambda: service

    response = client.post(
        "/api/review",
        json={
            "scenario": "舍友晚上打游戏声音很大，影响睡眠。",
            "dialogue": [
                {"speaker": "你", "message": "能不能晚上小声一点？"},
                {"speaker": "舍友 A（直接型）", "message": "我会注意音量。"},
                {"speaker": "舍友 B（回避型）", "message": "我再想想。"},
                {"speaker": "舍友 C（调和型）", "message": "我们可以约个安静时间。"},
                {"speaker": "系统", "message": "复盘阶段记录。"},
            ],
            "original_event": {
                "event_type": "noise_conflict",
                "severity": 4,
                "frequency": "weekly_multiple",
                "emotion": "anxious",
                "has_communicated": False,
                "has_conflict": True,
                "description": "舍友晚上打游戏声音很大，影响睡眠。",
            },
        },
    )

    assert response.status_code == 200
    assert service.review_request is not None
    assert [message.speaker for message in service.review_request.dialogue] == [
        "user",
        "roommate_a",
        "roommate_b",
        "roommate_c",
        "system",
    ]
    assert service.review_request.original_event is not None
    assert service.review_request.original_event.event_type == "noise"


def test_review_endpoint_accepts_additional_frontend_aliases_until_ai_config_check():
    app.dependency_overrides[get_ai_service] = lambda: MissingKeyService()

    response = client.post(
        "/api/review",
        json={
            "scenario": "宿舍公共区域使用问题。",
            "dialogue": [
                {"speaker": "我", "message": "我想商量一下公共区域的使用。"},
                {"speaker": "舍友A", "message": "我觉得可以。"},
                {"speaker": "舍友B", "message": "我再想想。"},
                {"speaker": "舍友C", "message": "我们一起定个规则。"},
                {"speaker": "系统", "message": "复盘阶段记录。"},
            ],
            "original_event": {
                "event_type": "expense_conflict",
                "description": "宿舍费用分摊有争议。",
            },
        },
    )

    assert response.status_code == 503
    assert_llm_key_hint(response.json()["detail"])


@pytest.mark.parametrize(
    "event_type",
    ["expense_conflict", "privacy_boundary", "emotional_conflict"],
)
def test_review_endpoint_accepts_spec_event_type_aliases_until_ai_config_check(event_type):
    app.dependency_overrides[get_ai_service] = lambda: MissingKeyService()

    response = client.post(
        "/api/review",
        json={
            "scenario": "宿舍边界问题需要复盘。",
            "dialogue": [
                {"speaker": "用户", "message": "我想复盘一下刚才的沟通。"},
            ],
            "original_event": {
                "event_type": event_type,
                "description": "宿舍边界问题需要复盘。",
            },
        },
    )

    assert response.status_code == 503
    assert_llm_key_hint(response.json()["detail"])


def test_review_endpoint_ignores_analysis_only_event_alias_until_ai_config_check():
    app.dependency_overrides[get_ai_service] = lambda: MissingKeyService()

    response = client.post(
        "/api/review",
        json={
            "scenario": "舍友晚上打游戏声音很大，影响睡眠。",
            "dialogue": [
                {"speaker": "用户", "message": "能不能晚上小声一点？"},
            ],
            "original_event": {
                "event_type": "risk-high",
                "description": "舍友晚上打游戏声音很大，影响睡眠。",
            },
        },
    )

    assert response.status_code == 503
    assert_llm_key_hint(response.json()["detail"])


def test_review_endpoint_rejects_unknown_risk_prefixed_event_alias():
    response = client.post(
        "/api/review",
        json={
            "scenario": "沟通复盘场景",
            "dialogue": [{"speaker": "用户", "message": "我想先说清楚我的睡眠受影响了。"}],
            "original_event": {
                "event_type": "risk-critical",
                "risk_level": "high",
                "pressure_score": 76,
            },
        },
    )

    assert response.status_code == 422


def test_review_endpoint_rejects_extra_top_level_fields():
    response = client.post(
        "/api/review",
        json={
            "scenario": "舍友晚上打游戏声音很大，影响睡眠。",
            "dialogue": [
                {"speaker": "user", "message": "能不能晚上小声一点？"},
            ],
            "debug_payload": {"unexpected": True},
        },
    )

    assert response.status_code == 422


def test_review_endpoint_rejects_extra_dialogue_fields():
    response = client.post(
        "/api/review",
        json={
            "scenario": "舍友晚上打游戏声音很大，影响睡眠。",
            "dialogue": [
                {
                    "speaker": "user",
                    "message": "能不能晚上小声一点？",
                    "ui_label": "你",
                },
            ],
        },
    )

    assert response.status_code == 422


def test_simulate_endpoint_returns_503_when_ai_key_missing():
    app.dependency_overrides[get_ai_service] = lambda: MissingKeyService()

    response = client.post(
        "/api/simulate",
        json={
            "scenario": "舍友晚上打游戏声音很大，影响睡眠。",
            "user_message": "能不能晚上小声一点？",
        },
    )

    assert response.status_code == 503
    assert_llm_key_hint(response.json()["detail"])


def test_review_endpoint_returns_503_when_ai_key_missing():
    app.dependency_overrides[get_ai_service] = lambda: MissingKeyService()

    response = client.post(
        "/api/review",
        json={
            "scenario": "舍友晚上打游戏声音很大，影响睡眠。",
            "dialogue": [
                {"speaker": "user", "message": "能不能晚上小声一点？"},
            ],
        },
    )

    assert response.status_code == 503
    assert_llm_key_hint(response.json()["detail"])


def test_archive_insight_endpoint_returns_400_when_archive_is_empty():
    event_store = InMemoryEventStore()
    ai_service = CapturingArchiveInsightService()
    app.dependency_overrides[get_event_store] = lambda: event_store
    app.dependency_overrides[get_ai_service] = lambda: ai_service

    response = client.post("/api/events/insight")

    assert response.status_code == 400
    assert response.json()["detail"] == "请先记录至少一条事件后再生成 AI 心晴见解。"
    assert ai_service.archive_insight_called is False


def test_archive_insight_range_7_passes_only_period_events_to_ai_service():
    event_store = InMemoryEventStore()
    ai_service = CapturingArchiveInsightService()
    app.dependency_overrides[get_event_store] = lambda: event_store
    app.dependency_overrides[get_ai_service] = lambda: ai_service
    today = date.today()
    recent_event = event_store.add(
        EventRecordCreate(
            event_date=today,
            event_type="noise",
            severity=2,
            frequency="occasional",
            emotion="helpless",
            has_communicated=True,
            has_conflict=False,
            description="今天公共桌面偶尔有点乱，已经提醒过一次。",
        )
    )
    event_store.add(
        EventRecordCreate(
            event_date=today - timedelta(days=8),
            event_type="hygiene",
            severity=5,
            frequency="daily",
            emotion="angry",
            has_communicated=False,
            has_conflict=True,
            description="8 天前公共区域长期没人整理，已经争吵。",
        )
    )

    response = client.post("/api/events/insight?range_days=7")

    assert response.status_code == 200
    assert ai_service.archive_insight_called is True
    assert ai_service.received_events is not None
    assert [event.id for event in ai_service.received_events] == [recent_event.id]
    assert ai_service.received_analysis is not None
    assert ai_service.received_analysis.period_days == 7
    assert ai_service.received_analysis.event_count == 2
    assert ai_service.received_analysis.active_30d_count == 2
    assert ai_service.received_analysis.active_period_count == 1
    assert ai_service.received_analysis.main_sources == ["噪音冲突"]


def test_archive_insight_defaults_to_30_days_for_ai_service_events():
    event_store = InMemoryEventStore()
    ai_service = CapturingArchiveInsightService()
    app.dependency_overrides[get_event_store] = lambda: event_store
    app.dependency_overrides[get_ai_service] = lambda: ai_service
    today = date.today()
    recent_event = event_store.add(
        EventRecordCreate(
            event_date=today,
            event_type="noise",
            severity=2,
            frequency="occasional",
            emotion="helpless",
            has_communicated=True,
            has_conflict=False,
            description="今天公共桌面偶尔有点乱，已经提醒过一次。",
        )
    )
    event_store.add(
        EventRecordCreate(
            event_date=today - timedelta(days=30),
            event_type="hygiene",
            severity=5,
            frequency="daily",
            emotion="angry",
            has_communicated=False,
            has_conflict=True,
            description="30 天前公共区域长期没人整理，已经争吵。",
        )
    )

    response = client.post("/api/events/insight")

    assert response.status_code == 200
    assert ai_service.archive_insight_called is True
    assert ai_service.received_events is not None
    assert [event.id for event in ai_service.received_events] == [recent_event.id]
    assert ai_service.received_analysis is not None
    assert ai_service.received_analysis.period_days == 30
    assert ai_service.received_analysis.event_count == 2
    assert ai_service.received_analysis.active_30d_count == 2
    assert ai_service.received_analysis.active_period_count == 1
    assert ai_service.received_analysis.main_sources == ["噪音冲突"]


def test_archive_insight_range_7_returns_400_when_current_period_is_empty():
    event_store = InMemoryEventStore()
    ai_service = CapturingArchiveInsightService()
    app.dependency_overrides[get_event_store] = lambda: event_store
    app.dependency_overrides[get_ai_service] = lambda: ai_service
    today = date.today()
    event_store.add(
        EventRecordCreate(
            event_date=today - timedelta(days=8),
            event_type="noise",
            severity=4,
            frequency="weekly_multiple",
            emotion="anxious",
            has_communicated=False,
            has_conflict=True,
            description="8 天前舍友晚上打游戏声音很大，影响睡眠。",
        )
    )

    response = client.post("/api/events/insight?range_days=7")

    assert response.status_code == 400
    assert "当前周期内暂无事件，无法生成 AI 心晴见解" in response.json()["detail"]
    assert ai_service.archive_insight_called is False


def test_archive_insight_endpoint_rejects_invalid_range_days():
    event_store = InMemoryEventStore()
    ai_service = CapturingArchiveInsightService()
    app.dependency_overrides[get_event_store] = lambda: event_store
    app.dependency_overrides[get_ai_service] = lambda: ai_service
    event_store.add(
        EventRecordCreate(
            event_date=date.today(),
            event_type="noise",
            severity=4,
            frequency="weekly_multiple",
            emotion="anxious",
            has_communicated=False,
            has_conflict=True,
            description="舍友晚上打游戏声音很大，影响睡眠。",
        )
    )

    response = client.post("/api/events/insight?range_days=14")

    assert response.status_code == 422
    assert response.json()["detail"] == "range_days must be one of 7, 15, 30, 90"
    assert ai_service.archive_insight_called is False


def test_archive_insight_endpoint_returns_503_when_ai_key_missing():
    event_store = InMemoryEventStore()
    app.dependency_overrides[get_event_store] = lambda: event_store
    app.dependency_overrides[get_ai_service] = lambda: MissingKeyService()

    create_response = create_noise_event_for_archive()
    response = client.post("/api/events/insight")

    assert create_response.status_code == 200
    assert response.status_code == 503
    assert_llm_key_hint(response.json()["detail"])


def test_archive_insight_endpoint_returns_502_when_ai_service_fails():
    event_store = InMemoryEventStore()
    app.dependency_overrides[get_event_store] = lambda: event_store
    app.dependency_overrides[get_ai_service] = lambda: BrokenAIService()

    create_response = create_noise_event_for_archive()
    response = client.post("/api/events/insight")

    assert create_response.status_code == 200
    assert response.status_code == 502
    assert "AI 服务暂时不可用" in response.json()["detail"]


def test_archive_insight_endpoint_returns_502_when_safety_note_is_unsafe():
    event_store = InMemoryEventStore()
    app.dependency_overrides[get_event_store] = lambda: event_store
    app.dependency_overrides[get_ai_service] = lambda: DormHarmonyAIService(
        runner=UnsafeArchiveInsightRunner()
    )

    create_response = create_noise_event_for_archive()
    response = client.post("/api/events/insight")

    assert create_response.status_code == 200
    assert response.status_code == 502
    assert "AI 输出结构异常" in response.json()["detail"]


def test_archive_insight_endpoint_returns_structured_ai_insight():
    event_store = InMemoryEventStore()
    app.dependency_overrides[get_event_store] = lambda: event_store
    app.dependency_overrides[get_ai_service] = lambda: FakeAIService()

    create_response = create_noise_event_for_archive()
    response = client.post("/api/events/insight")

    assert create_response.status_code == 200
    assert response.status_code == 200
    body = response.json()
    assert body.keys() == {
        "insight",
        "care_suggestion",
        "communication_focus",
        "safety_note",
    }
    assert "夜间噪音" in body["insight"]
    assert body["communication_focus"]
    assert "不进行心理诊断" in body["safety_note"]


def test_simulate_endpoint_returns_502_when_ai_service_fails():
    app.dependency_overrides[get_ai_service] = lambda: BrokenAIService()

    response = client.post(
        "/api/simulate",
        json={
            "scenario": "舍友晚上打游戏声音很大，影响睡眠。",
            "user_message": "能不能晚上小声一点？",
        },
    )

    assert response.status_code == 502
    assert "AI 服务暂时不可用" in response.json()["detail"]


def test_simulate_endpoint_returns_400_when_conversation_memory_is_missing():
    app.dependency_overrides[get_ai_service] = lambda: MissingMemoryService()

    response = client.post(
        "/api/simulate",
        json={
            "conversation_id": "missing-conversation",
            "scenario": "舍友晚上打游戏声音很大，影响睡眠。",
            "user_message": "能不能晚上小声一点？",
        },
    )

    assert response.status_code == 400
    assert "回到模拟页重新演练" in response.json()["detail"]


def test_simulate_stream_endpoint_returns_503_when_ai_key_missing():
    app.dependency_overrides[get_ai_service] = lambda: MissingKeyService()

    response = client.post(
        "/api/simulate/stream",
        json={
            "scenario": "舍友晚上打游戏声音很大，影响睡眠。",
            "user_message": "能不能晚上小声一点？",
        },
    )

    assert response.status_code == 503
    assert_llm_key_hint(response.json()["detail"])


def test_simulate_stream_endpoint_returns_502_when_ai_service_fails():
    app.dependency_overrides[get_ai_service] = lambda: BrokenAIService()

    response = client.post(
        "/api/simulate/stream",
        json={
            "scenario": "舍友晚上打游戏声音很大，影响睡眠。",
            "user_message": "能不能晚上小声一点？",
        },
    )

    assert response.status_code == 502
    assert "AI 服务暂时不可用" in response.json()["detail"]


def test_simulate_stream_endpoint_returns_400_when_conversation_memory_is_missing():
    app.dependency_overrides[get_ai_service] = lambda: MissingMemoryService()

    response = client.post(
        "/api/simulate/stream",
        json={
            "conversation_id": "missing-conversation",
            "scenario": "舍友晚上打游戏声音很大，影响睡眠。",
            "user_message": "能不能晚上小声一点？",
        },
    )

    assert response.status_code == 400
    assert "回到模拟页重新演练" in response.json()["detail"]


def test_review_endpoint_returns_502_when_ai_service_fails():
    app.dependency_overrides[get_ai_service] = lambda: BrokenAIService()

    response = client.post(
        "/api/review",
        json={
            "scenario": "舍友晚上打游戏声音很大，影响睡眠。",
            "dialogue": [
                {"speaker": "user", "message": "能不能晚上小声一点？"},
            ],
        },
    )

    assert response.status_code == 502
    assert "AI 服务暂时不可用" in response.json()["detail"]


def test_review_endpoint_returns_400_when_conversation_memory_is_missing():
    app.dependency_overrides[get_ai_service] = lambda: MissingMemoryService()

    response = client.post(
        "/api/review",
        json={
            "conversation_id": "missing-conversation",
            "scenario": "舍友晚上打游戏声音很大，影响睡眠。",
        },
    )

    assert response.status_code == 400
    assert "回到模拟页重新演练" in response.json()["detail"]


def test_simulate_endpoint_rejects_blank_message():
    response = client.post(
        "/api/simulate",
        json={
            "scenario": "舍友晚上打游戏声音很大，影响睡眠。",
            "user_message": "   ",
        },
    )

    assert response.status_code == 422
