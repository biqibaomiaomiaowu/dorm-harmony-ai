import asyncio
import sqlite3

import httpx
import pytest

from app.main import app, get_ai_service, get_review_history_store
from app.review_store import SQLiteReviewHistoryStore
from app.schemas import ReviewRequest, ReviewResponse


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
SCENARIO_TRAINING_SOURCE_META = {
    "mode": "scenario_training",
    "category_id": "noise",
    "category_label": "噪音冲突",
    "scenario_id": "noise_game_night",
    "scenario_title": "晚上打游戏声音太大",
    "target_id": "make_request",
    "target_label": "提出请求",
    "difficulty_id": "intermediate",
    "difficulty_label": "中级",
    "difficulty_description": "在对方轻微反驳时继续保持温和、具体的请求。",
}
CUSTOM_REHEARSAL_SOURCE_META = {
    "mode": "custom_rehearsal",
    "scenario": "我想练习如何和舍友沟通临时带朋友来宿舍的问题。",
    "roommate_summary": "舍友平时比较直接，容易觉得我小题大做。",
}


class CapturingReviewService:
    def __init__(self):
        self.review_request = None

    def review(self, request):
        self.review_request = request
        return make_review_response()


def make_review_response() -> ReviewResponse:
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


async def _request(method: str, url: str, **kwargs) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        response = await client.request(method, url, **kwargs)
        await response.aread()
        return response


def api_request(method: str, url: str, **kwargs) -> httpx.Response:
    return asyncio.run(_request(method, url, **kwargs))


@pytest.fixture(autouse=True)
def clear_dependency_overrides(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "DORM_HARMONY_SQLITE_PATH",
        str(tmp_path / "dorm_harmony.sqlite3"),
    )
    app.dependency_overrides.pop(get_ai_service, None)
    app.dependency_overrides.pop(get_review_history_store, None)
    yield
    app.dependency_overrides.pop(get_ai_service, None)
    app.dependency_overrides.pop(get_review_history_store, None)


def test_review_endpoint_accepts_scenario_training_source_meta():
    service = CapturingReviewService()
    app.dependency_overrides[get_ai_service] = lambda: service

    response = api_request(
        "POST",
        "/api/review",
        json={
            "conversation_id": "conversation-scenario-training",
            "scenario": "舍友晚上打游戏声音很大，影响睡眠。",
            "source_meta": SCENARIO_TRAINING_SOURCE_META,
            "dialogue": [
                {"speaker": "user", "message": "能不能晚上小声一点？"},
            ],
        },
    )

    assert response.status_code == 200
    assert service.review_request is not None
    assert service.review_request.source_meta is not None
    assert service.review_request.source_meta.mode == "scenario_training"
    assert (
        service.review_request.source_meta.scenario_id
        == SCENARIO_TRAINING_SOURCE_META["scenario_id"]
    )


def test_review_endpoint_accepts_legacy_scenario_training_source_meta_without_difficulty_description():
    service = CapturingReviewService()
    app.dependency_overrides[get_ai_service] = lambda: service
    legacy_source_meta = {
        key: value
        for key, value in SCENARIO_TRAINING_SOURCE_META.items()
        if key != "difficulty_description"
    }

    response = api_request(
        "POST",
        "/api/review",
        json={
            "conversation_id": "conversation-legacy-scenario-training",
            "scenario": "舍友晚上打游戏声音很大，影响睡眠。",
            "source_meta": legacy_source_meta,
            "dialogue": [
                {"speaker": "user", "message": "能不能晚上小声一点？"},
            ],
        },
    )

    assert response.status_code == 200
    assert service.review_request is not None
    assert service.review_request.source_meta is not None
    assert service.review_request.source_meta.mode == "scenario_training"
    assert service.review_request.source_meta.difficulty_description is None


def test_review_endpoint_accepts_custom_rehearsal_source_meta():
    service = CapturingReviewService()
    app.dependency_overrides[get_ai_service] = lambda: service

    response = api_request(
        "POST",
        "/api/review",
        json={
            "scenario": "我想练习如何和舍友沟通临时带朋友来宿舍的问题。",
            "source_meta": CUSTOM_REHEARSAL_SOURCE_META,
            "dialogue": [
                {"speaker": "user", "message": "下次带朋友来之前能不能先说一声？"},
            ],
        },
    )

    assert response.status_code == 200
    assert service.review_request is not None
    assert service.review_request.source_meta is not None
    assert service.review_request.source_meta.mode == "custom_rehearsal"
    assert (
        service.review_request.source_meta.roommate_summary
        == CUSTOM_REHEARSAL_SOURCE_META["roommate_summary"]
    )


def test_review_history_returns_source_meta_in_summary_and_detail(tmp_path):
    store = SQLiteReviewHistoryStore(tmp_path / "reviews.sqlite3")
    app.dependency_overrides[get_ai_service] = lambda: CapturingReviewService()
    app.dependency_overrides[get_review_history_store] = lambda: store

    create = api_request(
        "POST",
        "/api/review",
        json={
            "conversation_id": "conversation-source-meta",
            "scenario": "舍友晚上打游戏声音很大，影响睡眠。",
            "source_meta": SCENARIO_TRAINING_SOURCE_META,
            "dialogue": [
                {"speaker": "user", "message": "能不能晚上小声一点？"},
                {"speaker": "roommate_a", "message": "我会注意音量。"},
            ],
        },
    )
    listing = api_request("GET", "/api/reviews")
    report = listing.json()["reports"][0]
    detail = api_request("GET", f"/api/reviews/{report['id']}")

    assert create.status_code == 200
    assert listing.status_code == 200
    assert report["source_meta"] == SCENARIO_TRAINING_SOURCE_META
    assert detail.status_code == 200
    assert detail.json()["source_meta"] == SCENARIO_TRAINING_SOURCE_META
    assert detail.json()["request"]["source_meta"] == SCENARIO_TRAINING_SOURCE_META


def test_review_endpoint_keeps_legacy_request_without_source_meta():
    service = CapturingReviewService()
    app.dependency_overrides[get_ai_service] = lambda: service

    response = api_request(
        "POST",
        "/api/review",
        json={
            "scenario": "舍友晚上打游戏声音很大，影响睡眠。",
            "dialogue": [
                {"speaker": "user", "message": "能不能晚上小声一点？"},
            ],
        },
    )

    assert response.status_code == 200
    assert service.review_request is not None
    assert service.review_request.source_meta is None


def test_review_history_list_ignores_invalid_source_meta(tmp_path):
    db_path = tmp_path / "reviews.sqlite3"
    store = SQLiteReviewHistoryStore(db_path)
    app.dependency_overrides[get_review_history_store] = lambda: store
    response = make_review_response()

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO review_reports (
                id,
                created_at,
                conversation_id,
                scenario,
                request_json,
                response_json,
                dialogue_json,
                summary,
                score_clarity,
                score_empathy,
                score_resolution
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "review-invalid-source-meta",
                "2026-05-31T10:00:00+00:00",
                "conversation-invalid-source-meta",
                "历史坏数据",
                '{"scenario":"历史坏数据","source_meta":{"mode":"scenario_training"}}',
                response.model_dump_json(),
                "[]",
                response.summary,
                response.performance_scores.clarity,
                response.performance_scores.empathy,
                response.performance_scores.resolution,
            ),
        )

    listing = api_request("GET", "/api/reviews")
    detail = api_request("GET", "/api/reviews/review-invalid-source-meta")

    assert listing.status_code == 200
    assert listing.json()["reports"][0]["source_meta"] is None
    assert detail.status_code == 200
    assert detail.json()["source_meta"] is None
    assert detail.json()["request"]["source_meta"] is None


def test_review_history_detail_aligns_top_level_source_meta_with_request(tmp_path):
    store = SQLiteReviewHistoryStore(tmp_path / "reviews.sqlite3")
    request = ReviewRequest(
        conversation_id="conversation-direct-store",
        scenario="舍友晚上打游戏声音很大，影响睡眠。",
        source_meta=CUSTOM_REHEARSAL_SOURCE_META,
    )
    detail = store.add(request, make_review_response(), [])

    assert detail.source_meta == request.source_meta
