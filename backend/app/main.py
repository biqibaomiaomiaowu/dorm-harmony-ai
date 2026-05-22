"""FastAPI 应用入口，负责路由、CORS 和服务层错误映射。"""

from contextlib import asynccontextmanager
import json
import logging
import os
from threading import Lock

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.ai_service import (
    AIServiceConfigurationError,
    AIServiceUnavailableError,
    ConversationMemory,
    ConversationMemoryNotFoundError,
    DormHarmonyAIService,
    ReviewDialogueInvalidError,
)
from app.archive_analysis import analyze_archive_pressure
from app.env import load_project_env
from app.event_store import EventStore, SQLiteEventStore, get_default_sqlite_path
from app.review_store import SQLiteReviewHistoryStore
from app.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    ArchiveAnalysisResponse,
    ArchiveInsightResponse,
    EventArchiveResponse,
    EventRecord,
    EventRecordCreate,
    ReviewHistoryResponse,
    ReviewReportDetail,
    ReviewRequest,
    ReviewResponse,
    SimulateRequest,
    SimulateResponse,
    emotion_display_label,
)
from app.scoring import analyze_pressure


load_project_env()
logger = logging.getLogger(__name__)


def _get_cors_origins() -> list[str]:
    """默认允许本地 Vite 访问，也支持环境变量覆盖部署域名。"""
    configured_origins = os.getenv("DORM_HARMONY_CORS_ORIGINS", "")
    origins = [
        origin.strip()
        for origin in configured_origins.split(",")
        if origin.strip()
    ]
    return origins or ["http://localhost:5173", "http://127.0.0.1:5173"]


_SHARED_CONVERSATION_MEMORY: ConversationMemory | None = None
_SHARED_CONVERSATION_MEMORY_LOCK = Lock()


def get_shared_conversation_memory() -> ConversationMemory:
    """懒加载共享会话记忆，避免模块 import 时写入运行时 SQLite。"""
    global _SHARED_CONVERSATION_MEMORY
    with _SHARED_CONVERSATION_MEMORY_LOCK:
        if _SHARED_CONVERSATION_MEMORY is None:
            _SHARED_CONVERSATION_MEMORY = ConversationMemory.sqlite(get_default_sqlite_path())
        return _SHARED_CONVERSATION_MEMORY


def close_shared_conversation_memory() -> None:
    """关闭共享 SQLite 会话记忆连接。"""
    global _SHARED_CONVERSATION_MEMORY
    with _SHARED_CONVERSATION_MEMORY_LOCK:
        if _SHARED_CONVERSATION_MEMORY is not None:
            _SHARED_CONVERSATION_MEMORY.close()
            _SHARED_CONVERSATION_MEMORY = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：关闭共享 SQLite 会话记忆连接。"""
    try:
        yield
    finally:
        close_shared_conversation_memory()


app = FastAPI(title="Dorm Harmony AI", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_origins(),
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


def get_ai_service() -> DormHarmonyAIService:
    """FastAPI 依赖注入入口，测试中可覆盖为 fake service。"""
    return DormHarmonyAIService(memory=get_shared_conversation_memory())


def get_event_store() -> SQLiteEventStore:
    """FastAPI 依赖注入入口，测试中可覆盖事件档案存储。"""
    return SQLiteEventStore()


def get_review_history_store() -> SQLiteReviewHistoryStore:
    """FastAPI 依赖注入入口，测试中可覆盖复盘历史存储。"""
    return SQLiteReviewHistoryStore()


def _build_archive_context_summary(event_store: EventStore) -> str | None:
    """为模拟路由生成受控、短文本的事件档案摘要。"""
    events = event_store.list()
    if not events:
        return None

    analysis = analyze_archive_pressure(events)
    recent_event = events[0]
    main_sources = "、".join(analysis.main_sources) or "暂无明确来源"
    communication_status = "已沟通" if recent_event.has_communicated else "未沟通"
    conflict_status = "有冲突" if recent_event.has_conflict else "无冲突"
    recent_description = _truncate_archive_text(recent_event.description, max_length=120)
    emotion_labels = "、".join(
        emotion_display_label(emotion)
        for emotion in (recent_event.emotions or [recent_event.emotion])
        if emotion is not None
    )
    primary_emotion = emotion_display_label(recent_event.primary_emotion or recent_event.emotion)

    summary = (
        f"事件档案：总事件 {analysis.event_count} 条，近 30 天 {analysis.active_30d_count} 条；"
        f"主要压力来源：{main_sources}；"
        f"风险：{analysis.risk_level}/{analysis.risk_label}；"
        f"最近事件：{recent_event.event_type}，严重程度 {recent_event.severity}，"
        f"主要情绪 {primary_emotion}，情绪 {emotion_labels}，"
        f"{communication_status}，{conflict_status}，"
        f"描述：{recent_description}"
    )
    return _truncate_archive_text(summary, max_length=500)


def _truncate_archive_text(text: str, max_length: int) -> str:
    """限制档案摘要片段长度，避免超过 SimulateResponse 字段约束。"""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3].rstrip() + "..."


@app.get("/health")
async def health() -> dict[str, str]:
    """返回后端健康检查状态，不依赖 AI 服务配置。"""
    return {"status": "ok"}


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    """对单条宿舍事件执行规则评分并返回结构化分析结果。"""
    return analyze_pressure(request)


@app.post("/api/events", response_model=EventRecord)
def create_event_record(
    request: EventRecordCreate,
    event_store: EventStore = Depends(get_event_store),
) -> EventRecord:
    """保存一条事件档案，并同步生成单条事件压力分析快照。"""
    return event_store.add(request)


@app.get("/api/events", response_model=EventArchiveResponse)
def list_event_records(
    event_store: EventStore = Depends(get_event_store),
) -> EventArchiveResponse:
    """返回当前事件档案列表，不调用 AI 服务。"""
    return EventArchiveResponse(events=event_store.list())


@app.delete("/api/events/{event_id}", status_code=204)
def delete_event_record(
    event_id: str,
    event_store: EventStore = Depends(get_event_store),
) -> None:
    """删除一条事件档案；派生压力和 AI 见解由前端重新请求。"""
    if not event_store.delete(event_id):
        raise HTTPException(
            status_code=404,
            detail="事件档案不存在或已被删除。",
        )


@app.get("/api/events/analysis", response_model=ArchiveAnalysisResponse)
def analyze_event_archive(
    event_store: EventStore = Depends(get_event_store),
) -> ArchiveAnalysisResponse:
    """汇总事件档案并返回总压力分析，不调用 AI 服务。"""
    return analyze_archive_pressure(event_store.list())


@app.post("/api/events/insight", response_model=ArchiveInsightResponse)
def archive_insight(
    event_store: EventStore = Depends(get_event_store),
    ai_service: DormHarmonyAIService = Depends(get_ai_service),
) -> ArchiveInsightResponse:
    """基于事件档案和总压力分析生成 AI 心晴见解。"""
    events = event_store.list()
    if not events:
        raise HTTPException(
            status_code=400,
            detail="请先记录至少一条事件后再生成 AI 心晴见解。",
        )

    analysis = analyze_archive_pressure(events)
    try:
        return ai_service.archive_insight(events, analysis)
    except AIServiceConfigurationError as exc:
        # 配置缺失是本地部署问题，前端按 503 展示“需要配置 AI 服务”。
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AIServiceUnavailableError as exc:
        # 已配置但模型调用失败或输出异常，按 502 处理为上游服务不可用。
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/simulate", response_model=SimulateResponse)
def simulate(
    request: SimulateRequest,
    ai_service: DormHarmonyAIService = Depends(get_ai_service),
    event_store: EventStore = Depends(get_event_store),
) -> SimulateResponse:
    """调用 AI 服务生成三位虚拟舍友的结构化模拟回复。"""
    try:
        archive_context_summary = (
            _build_archive_context_summary(event_store)
            if request.use_event_archive
            else None
        )
        return ai_service.simulate(request, archive_context_summary=archive_context_summary)
    except AIServiceConfigurationError as exc:
        # 配置缺失是本地部署问题，前端按 503 展示“需要配置 AI 服务”。
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ConversationMemoryNotFoundError as exc:
        # 会话记忆不存在通常表示后端重启或旧 conversation_id，提示前端重新演练。
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AIServiceUnavailableError as exc:
        # 已配置但模型调用失败或输出异常，按 502 处理为上游服务不可用。
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _encode_ndjson_event(event: dict[str, object]) -> str:
    """把一个流式响应事件编码为紧凑 NDJSON 行。"""
    return json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"


@app.post("/api/simulate/stream")
def simulate_stream(
    request: SimulateRequest,
    ai_service: DormHarmonyAIService = Depends(get_ai_service),
    event_store: EventStore = Depends(get_event_store),
) -> StreamingResponse:
    """以 start、reply、final 顺序流式返回沟通模拟结果。"""
    try:
        archive_context_summary = (
            _build_archive_context_summary(event_store)
            if request.use_event_archive
            else None
        )
        result = ai_service.simulate(request, archive_context_summary=archive_context_summary)
    except AIServiceConfigurationError as exc:
        # 配置缺失仍作为普通 HTTP 错误返回，避免前端收到半截流。
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ConversationMemoryNotFoundError as exc:
        # 会话记忆不存在时不进入流体，前端可按普通 400 处理。
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AIServiceUnavailableError as exc:
        # 模型调用失败或结构异常不进入流体，方便前端沿用原兜底逻辑。
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    def event_stream():
        """生成沟通模拟的 NDJSON 事件序列。"""
        yield _encode_ndjson_event(
            {"type": "start", "conversation_id": result.conversation_id}
        )
        for reply in result.replies:
            yield _encode_ndjson_event(
                {"type": "reply", "reply": reply.model_dump(mode="json")}
            )
        yield _encode_ndjson_event(
            {"type": "final", "response": result.model_dump(mode="json")}
        )

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


@app.post("/api/review", response_model=ReviewResponse)
def review(
    request: ReviewRequest,
    ai_service: DormHarmonyAIService = Depends(get_ai_service),
    review_store: SQLiteReviewHistoryStore = Depends(get_review_history_store),
) -> ReviewResponse:
    """调用 AI 服务生成结构化沟通复盘报告。"""
    try:
        review_with_dialogue = getattr(ai_service, "review_with_dialogue", None)
        if callable(review_with_dialogue):
            result = review_with_dialogue(request)
            response = result.response
            dialogue = list(result.dialogue)
        else:
            response = ai_service.review(request)
            dialogue = request.dialogue[-50:]

        if not response.is_demo:
            try:
                review_store.add(request, response, dialogue)
            except Exception:
                logger.exception("Failed to persist review report history")

        return response
    except AIServiceConfigurationError as exc:
        # 配置缺失是本地部署问题，前端按 503 展示“需要配置 AI 服务”。
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ConversationMemoryNotFoundError as exc:
        # 会话记忆不存在通常表示后端重启或旧 conversation_id，提示前端重新演练。
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ReviewDialogueInvalidError as exc:
        # 对话缓存为空或缺少用户发言属于客户端可恢复状态，不应伪装成 AI 上游 502。
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AIServiceUnavailableError as exc:
        # 已配置但模型调用失败或输出异常，按 502 处理为上游服务不可用。
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/reviews", response_model=ReviewHistoryResponse)
def list_review_reports(
    limit: int = Query(default=20, ge=1),
    review_store: SQLiteReviewHistoryStore = Depends(get_review_history_store),
) -> ReviewHistoryResponse:
    """返回最近的沟通复盘历史摘要。"""
    return ReviewHistoryResponse(reports=review_store.list(limit=min(limit, 50)))


@app.get("/api/reviews/{review_id}", response_model=ReviewReportDetail)
def get_review_report(
    review_id: str,
    review_store: SQLiteReviewHistoryStore = Depends(get_review_history_store),
) -> ReviewReportDetail:
    """返回单条沟通复盘历史详情。"""
    report = review_store.get(review_id)
    if report is None:
        raise HTTPException(status_code=404, detail="复盘历史不存在或已被删除。")

    return report
