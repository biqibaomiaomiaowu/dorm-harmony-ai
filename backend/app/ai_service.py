"""封装 LangChain/DeepSeek 调用、配置读取和结构化输出校验。"""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
import os
import re
from typing import Annotated, Protocol, TypedDict, TypeVar
from uuid import uuid4

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field, ValidationError, field_validator

from app.ai_prompts import (
    build_roommate_reply_messages,
    build_archive_insight_messages,
    build_review_messages,
    build_speaker_plan_messages,
)
from app.env import load_project_env
from app.schemas import (
    ArchiveAnalysisResponse,
    ArchiveInsightResponse,
    DialogueMessage,
    EventRecord,
    ReviewPerformanceScores,
    ReviewRequest,
    ReviewResponse,
    ReviewRewriteSuggestion,
    RoommateProfile,
    RoommateReply,
    SimulateRequest,
    SimulateResponse,
)


class AIServiceConfigurationError(RuntimeError):
    """表示本地 AI 服务配置缺失或配置值非法。"""

    pass


class AIServiceUnavailableError(RuntimeError):
    """表示已配置 AI 服务但上游调用暂时不可用。"""

    pass


class AIOutputStructureError(AIServiceUnavailableError):
    """表示模型返回内容无法通过后端结构化响应校验。"""

    pass


class ConversationMemoryNotFoundError(AIServiceUnavailableError):
    """表示指定 conversation_id 的短期记忆不存在。"""

    pass


class ReviewDialogueInvalidError(AIServiceUnavailableError):
    """表示复盘对话缺少可分析的用户发言。"""

    pass


@dataclass(frozen=True)
class AISettings:
    """封装一次 LLM 调用所需的连接、模型和超时配置。"""

    api_key: str
    model: str
    base_url: str
    timeout: float


class AIRunner(Protocol):
    """定义 AI 运行器必须提供的结构化多智能体生成能力。"""

    def plan_simulation_replies(
        self,
        request: SimulateRequest,
        history: list[DialogueMessage],
        archive_context_summary: str | None = None,
    ) -> "SpeakerPlanResponse":
        """规划本轮需要发言的虚拟舍友和顺序。"""
        raise NotImplementedError

    def generate_roommate_reply(
        self,
        request: SimulateRequest,
        history: list[DialogueMessage],
        archive_context_summary: str | None,
        same_turn_replies: list[RoommateReply],
        roommate: RoommateProfile,
    ) -> RoommateReply:
        """根据规划为指定虚拟舍友生成一条回复。"""
        raise NotImplementedError

    def generate_review(
        self,
        request: ReviewRequest,
        dialogue: list[DialogueMessage],
    ) -> object:
        """根据对话复盘请求生成结构化沟通复盘报告。"""
        raise NotImplementedError

    def generate_archive_insight(
        self,
        events: list[EventRecord],
        analysis: ArchiveAnalysisResponse,
    ) -> ArchiveInsightResponse:
        """根据事件档案和总压力分析生成结构化心晴见解。"""
        raise NotImplementedError


OutputModel = TypeVar("OutputModel", bound=BaseModel)
_STRUCTURE_ERROR_MESSAGE = "AI 输出结构异常，请稍后重试。"
_UNAVAILABLE_ERROR_MESSAGE = "AI 服务暂时不可用，请稍后重试。"
_MEMORY_NOT_FOUND_MESSAGE = "未找到对应的模拟对话，请回到模拟页重新演练。"
_REVIEW_DIALOGUE_INVALID_MESSAGE = "复盘对话中缺少用户发言，请先完成一次模拟对话。"
_DEFAULT_LLM_BASE_URL = "https://api.deepseek.com"
_DEFAULT_LLM_MODEL = "deepseek-v4-flash"
SIMULATE_SAFETY_NOTE = (
    "本回复仅用于宿舍沟通演练，不代表真实舍友想法，不进行心理诊断，"
    "不进行医学判断，不进行人格评价。如有现实安全风险，请联系辅导员或心理老师寻求现实支持。"
)
REVIEW_SAFETY_NOTE = (
    "本复盘仅用于沟通训练建议，不代表真实舍友想法，不进行心理诊断，"
    "不进行医学判断，不进行人格评价。如压力持续升高，请寻求现实支持或联系辅导员、心理老师。"
)
_REVIEW_ORIGINAL_MESSAGE_MAX_LENGTH = 500
_REVIEW_SUGGESTED_MESSAGE_MAX_LENGTH = 500
_REVIEW_ISSUE_MAX_LENGTH = 300
_REVIEW_REASON_MAX_LENGTH = 300
_IMPROVABLE_USER_MESSAGE_KEYWORDS = (
    "傻",
    "闭嘴",
    "滚",
    "有病",
    "烦死",
    "烦不烦",
    "吵死",
    "别吵",
    "别搞",
    "无语",
    "受不了",
    "凭什么",
    "你能不能",
    "算了",
    "随便",
    "懒得",
    "不说了",
)


class SpeakerPlanItem(BaseModel):
    """发言规划中单个待回复舍友。"""

    roommate_id: str = Field(min_length=1, max_length=64)

    @field_validator("roommate_id", mode="before")
    @classmethod
    def trim_and_require_roommate_id(cls, value: str) -> str:
        """清理待发言舍友 id，并拒绝空字符串。"""
        if not isinstance(value, str):
            raise ValueError("roommate_id must be a string")

        roommate_id = value.strip()
        if not roommate_id:
            raise ValueError("roommate_id must not be empty")

        return roommate_id


class SpeakerPlanResponse(BaseModel):
    """发言规划器的结构化输出。"""

    replies: list[SpeakerPlanItem] = Field(default_factory=list, max_length=15)


class ReviewRewriteSuggestionDraft(BaseModel):
    """AI 复盘话术建议草稿，允许服务层后处理修正。"""

    message_index: object | None = None
    original_message: object | None = None
    issue: object | None = None
    suggested_message: object | None = None
    reason: object | None = None


class ReviewPerformanceScoresDraft(BaseModel):
    """AI 复盘评分草稿，允许缺项后由服务层兜底。"""

    clarity: object | None = None
    empathy: object | None = None
    resolution: object | None = None


class ReviewDraftResponse(BaseModel):
    """AI 复盘草稿响应；最终仍会收敛为严格 ReviewResponse。"""

    summary: object | None = None
    strengths: list[object] | None = None
    risks: list[object] | None = None
    performance_scores: ReviewPerformanceScoresDraft | None = None
    rewrite_suggestions: list[ReviewRewriteSuggestionDraft] | None = None
    rewritten_message: object | None = None
    next_steps: list[object] | None = None
    safety_note: object | None = None


class _ConversationState(TypedDict):
    messages: Annotated[list, add_messages]


def _create_memory_graph(checkpointer: InMemorySaver):
    """创建一个只用于 LangGraph checkpointer 存取消息的极小图。"""

    def passthrough(state: _ConversationState) -> dict[str, list]:
        return {}

    graph = StateGraph(_ConversationState)
    graph.add_node("passthrough", passthrough)
    graph.add_edge(START, "passthrough")
    graph.add_edge("passthrough", END)
    return graph.compile(checkpointer=checkpointer)


class ConversationMemory:
    """基于 LangGraph InMemorySaver 的单进程短期会话记忆。"""

    def __init__(self, checkpointer: InMemorySaver | None = None) -> None:
        self.checkpointer = checkpointer or InMemorySaver()
        self._graph = _create_memory_graph(self.checkpointer)
        self._conversation_ids: set[str] = set()
        self._latest_turn_ids: dict[str, str] = {}

    def start_conversation(self, conversation_id: str | None = None) -> str:
        """创建或登记一条短期会话。"""
        resolved_id = (conversation_id or str(uuid4())).strip()
        if not resolved_id:
            resolved_id = str(uuid4())
        self._conversation_ids.add(resolved_id)
        return resolved_id

    def has_conversation(self, conversation_id: str) -> bool:
        """判断当前进程内是否登记过该会话。"""
        return conversation_id in self._conversation_ids

    def mark_latest_turn(self, conversation_id: str, turn_id: str | None) -> None:
        """记录当前会话最新用户回合，用于丢弃过期 continuation。"""
        if turn_id:
            self._latest_turn_ids[conversation_id] = turn_id

    def is_latest_turn(self, conversation_id: str, turn_id: str | None) -> bool:
        """判断请求是否仍属于当前最新用户回合。"""
        if not turn_id:
            return True
        return self._latest_turn_ids.get(conversation_id) in {None, turn_id}

    def append_user_message(self, conversation_id: str, message: str) -> None:
        """追加用户消息。"""
        self._append_message(conversation_id, HumanMessage(content=message))

    def append_roommate_message(
        self,
        conversation_id: str,
        roommate_id: str,
        roommate: str,
        personality: str,
        message: str,
        turn_id: str | None = None,
    ) -> None:
        """追加虚拟舍友消息。"""
        self._append_message(
            conversation_id,
            AIMessage(
                content=message,
                name=roommate_id,
                additional_kwargs={
                    "speaker": roommate_id,
                    "roommate": roommate,
                    "personality": personality,
                    "turn_id": turn_id,
                },
            ),
        )

    def get_dialogue(self, conversation_id: str, limit: int = 50) -> list[DialogueMessage]:
        """读取短期记忆中的对话，最多返回最近 limit 条。"""
        if not self.has_conversation(conversation_id):
            raise ConversationMemoryNotFoundError(_MEMORY_NOT_FOUND_MESSAGE)

        messages = self._get_messages(conversation_id)
        return [_message_to_dialogue(message) for message in messages[-limit:]]

    def get_roommate_reply_counts_since_last_user(
        self,
        conversation_id: str,
        turn_id: str | None = None,
    ) -> Counter[str]:
        """统计最近一轮用户发言后，各舍友已写入的回复数。"""
        if not self.has_conversation(conversation_id):
            raise ConversationMemoryNotFoundError(_MEMORY_NOT_FOUND_MESSAGE)

        counts: Counter[str] = Counter()
        for message in reversed(self._get_messages(conversation_id)):
            if isinstance(message, HumanMessage):
                break
            speaker = message.name or message.additional_kwargs.get("speaker")
            if not isinstance(speaker, str) or not speaker.startswith("roommate_"):
                continue
            message_turn_id = message.additional_kwargs.get("turn_id")
            if turn_id is not None and message_turn_id != turn_id:
                continue
            counts[speaker] += 1

        return counts

    def _append_message(self, conversation_id: str, message: BaseMessage) -> None:
        self.start_conversation(conversation_id)
        self._graph.update_state(
            self._config(conversation_id),
            {"messages": [message]},
        )

    def _get_messages(self, conversation_id: str) -> list[BaseMessage]:
        state = self._graph.get_state(self._config(conversation_id))
        return list(state.values.get("messages", []))

    def _config(self, conversation_id: str) -> dict[str, dict[str, str]]:
        return {"configurable": {"thread_id": conversation_id}}


def _message_to_dialogue(message: BaseMessage) -> DialogueMessage:
    """把 LangChain 消息转为复盘使用的 DialogueMessage。"""
    if isinstance(message, HumanMessage):
        return DialogueMessage(speaker="user", message=str(message.content))

    speaker = message.name or message.additional_kwargs.get("speaker") or "system"
    try:
        return DialogueMessage(speaker=speaker, message=str(message.content))
    except ValidationError:
        return DialogueMessage.model_construct(speaker=speaker, message=str(message.content))


def load_ai_settings() -> AISettings:
    """读取 AI 配置；优先使用 DeepSeek Key，保留旧 OpenAI Key 兼容。"""
    load_project_env()

    api_key = (
        os.getenv("DEEPSEEK_API_KEY", "").strip()
        or os.getenv("OPENAI_API_KEY", "").strip()
    )
    if not api_key:
        raise AIServiceConfigurationError(
            "AI 服务未配置：请设置 DEEPSEEK_API_KEY（推荐）或 OPENAI_API_KEY（兼容旧配置）。"
        )

    timeout_text = os.getenv("DORM_HARMONY_LLM_TIMEOUT", "20").strip()
    try:
        timeout = float(timeout_text)
    except ValueError:
        raise AIServiceConfigurationError(
            "AI 服务未配置：DORM_HARMONY_LLM_TIMEOUT 必须是数字。"
        ) from None

    if timeout <= 0:
        raise AIServiceConfigurationError(
            "AI 服务未配置：DORM_HARMONY_LLM_TIMEOUT 必须大于 0。"
        )

    return AISettings(
        api_key=api_key,
        model=os.getenv("DORM_HARMONY_LLM_MODEL", _DEFAULT_LLM_MODEL).strip()
        or _DEFAULT_LLM_MODEL,
        base_url=os.getenv("DORM_HARMONY_LLM_BASE_URL", _DEFAULT_LLM_BASE_URL).strip()
        or _DEFAULT_LLM_BASE_URL,
        timeout=timeout,
    )


class LangChainDeepSeekRunner:
    """通过 LangChain 调用 DeepSeek，并按 Pydantic schema 解析输出。"""

    def __init__(self, settings: AISettings | None = None) -> None:
        """初始化 DeepSeek 调用配置；未传入时从环境变量加载。"""
        self._settings = settings or load_ai_settings()
        self.model = self._settings.model

    def plan_simulation_replies(
        self,
        request: SimulateRequest,
        history: list[DialogueMessage],
        archive_context_summary: str | None = None,
    ) -> SpeakerPlanResponse:
        """构造发言规划 Prompt 并返回结构化规划结果。"""
        return self._invoke_structured(
            SpeakerPlanResponse,
            build_speaker_plan_messages(request, history, archive_context_summary),
        )

    def generate_roommate_reply(
        self,
        request: SimulateRequest,
        history: list[DialogueMessage],
        archive_context_summary: str | None,
        same_turn_replies: list[RoommateReply],
        roommate: RoommateProfile,
    ) -> RoommateReply:
        """构造单个舍友回复 Prompt 并返回结构化回复。"""
        return self._invoke_structured(
            RoommateReply,
            build_roommate_reply_messages(
                request,
                history,
                archive_context_summary,
                same_turn_replies,
                roommate,
            ),
        )

    def generate_review(
        self,
        request: ReviewRequest,
        dialogue: list[DialogueMessage],
    ) -> ReviewDraftResponse:
        """构造复盘 Prompt 并返回结构化沟通复盘结果。"""
        return self._invoke_structured(
            ReviewDraftResponse,
            build_review_messages(request, dialogue),
        )

    def generate_archive_insight(
        self,
        events: list[EventRecord],
        analysis: ArchiveAnalysisResponse,
    ) -> ArchiveInsightResponse:
        """构造档案见解 Prompt 并返回结构化心晴见解。"""
        return self._invoke_structured(
            ArchiveInsightResponse,
            build_archive_insight_messages(events, analysis),
        )

    def _invoke_structured(
        self, schema: type[OutputModel], messages: Sequence[BaseMessage]
    ) -> OutputModel:
        """调用模型的 JSON 模式，并把异常收敛为前端可理解的错误。"""
        public_error: AIServiceUnavailableError | None = None
        result: object | None = None

        try:
            # 延迟导入让无 API Key 的测试环境也能构造服务对象。
            from langchain_deepseek import ChatDeepSeek

            llm = ChatDeepSeek(
                model=self._settings.model,
                temperature=0.3,
                timeout=self._settings.timeout,
                max_retries=1,
                api_key=self._settings.api_key,
                api_base=self._settings.base_url,
            )
            structured_llm = llm.with_structured_output(schema, method="json_mode")
            result = structured_llm.invoke(messages)
        except ValidationError:
            public_error = AIOutputStructureError(_STRUCTURE_ERROR_MESSAGE)
        except Exception:
            # 不把供应商异常、网络细节或潜在密钥内容暴露给前端。
            public_error = AIServiceUnavailableError(_UNAVAILABLE_ERROR_MESSAGE)

        if public_error is not None:
            raise public_error

        return _ensure_model_instance(result, schema)


class DormHarmonyAIService:
    """FastAPI 依赖使用的 AI 服务门面，统一错误和结构校验语义。"""

    def __init__(
        self,
        runner: AIRunner | None = None,
        memory: ConversationMemory | None = None,
    ) -> None:
        """保存可替换的 AI 运行器，方便接口测试注入 fake runner。"""
        self._runner = runner
        self._memory = memory or ConversationMemory()

    def _get_runner(self) -> AIRunner:
        """懒加载默认 LangChain Runner，避免无 Key 环境提前失败。"""
        if self._runner is None:
            self._runner = LangChainDeepSeekRunner()
        return self._runner

    def simulate(
        self,
        request: SimulateRequest,
        archive_context_summary: str | None = None,
    ) -> SimulateResponse:
        """生成沟通模拟结果，并保证返回值符合 SimulateResponse。"""
        public_error: AIServiceUnavailableError | None = None
        result: object | None = None

        try:
            result = self._simulate_with_memory(request, archive_context_summary)
        except AIServiceConfigurationError:
            raise
        except ConversationMemoryNotFoundError:
            raise
        except AIOutputStructureError:
            public_error = AIOutputStructureError(_STRUCTURE_ERROR_MESSAGE)
        except AIServiceUnavailableError:
            public_error = AIServiceUnavailableError(_UNAVAILABLE_ERROR_MESSAGE)
        except ValidationError:
            public_error = AIOutputStructureError(_STRUCTURE_ERROR_MESSAGE)
        except Exception:
            public_error = AIServiceUnavailableError(_UNAVAILABLE_ERROR_MESSAGE)

        if public_error is not None:
            raise public_error

        return _ensure_model_instance(result, SimulateResponse)

    def review(self, request: ReviewRequest) -> ReviewResponse:
        """生成沟通复盘结果，并保证返回值符合 ReviewResponse。"""
        public_error: AIServiceUnavailableError | None = None
        result: object | None = None

        try:
            dialogue = self._resolve_review_dialogue(request)
            self._validate_review_dialogue_has_user_message(dialogue)
            draft = _ensure_review_draft_instance(
                self._get_runner().generate_review(request, dialogue)
            )
            result = self._build_review_response_from_draft(request, draft, dialogue)
        except AIServiceConfigurationError:
            raise
        except ConversationMemoryNotFoundError:
            raise
        except ReviewDialogueInvalidError:
            raise
        except AIOutputStructureError:
            public_error = AIOutputStructureError(_STRUCTURE_ERROR_MESSAGE)
        except AIServiceUnavailableError:
            public_error = AIServiceUnavailableError(_UNAVAILABLE_ERROR_MESSAGE)
        except ValidationError:
            public_error = AIOutputStructureError(_STRUCTURE_ERROR_MESSAGE)
        except Exception:
            public_error = AIServiceUnavailableError(_UNAVAILABLE_ERROR_MESSAGE)

        if public_error is not None:
            raise public_error

        return _ensure_model_instance(result, ReviewResponse)

    def _simulate_with_memory(
        self,
        request: SimulateRequest,
        archive_context_summary: str | None = None,
    ) -> SimulateResponse:
        """使用短期记忆和多智能体 runner 完成一轮模拟。"""
        conversation_id = self._resolve_conversation_id(request)
        if not request.is_continuation:
            self._memory.mark_latest_turn(conversation_id, request.turn_id)
        legacy_dialogue = (
            request.dialogue
            if request.conversation_id is None and request.dialogue
            else []
        )
        history = (
            list(legacy_dialogue)
            if legacy_dialogue
            else self._memory.get_dialogue(conversation_id)
        )
        existing_turn_counts = (
            Counter()
            if legacy_dialogue or not request.is_continuation
            else self._memory.get_roommate_reply_counts_since_last_user(
                conversation_id,
                turn_id=request.turn_id,
            )
        )

        runner = self._get_runner()
        plan = _ensure_model_instance(
            runner.plan_simulation_replies(request, history, archive_context_summary),
            SpeakerPlanResponse,
        )
        roommate_by_id = {roommate.id: roommate for roommate in request.roommates}
        planned_replies = self._planned_replies_for_request(plan, request)
        self._validate_planned_replies(planned_replies, roommate_by_id, existing_turn_counts)

        same_turn_replies: list[RoommateReply] = []
        for item in planned_replies.replies:
            roommate = roommate_by_id[item.roommate_id]
            reply = _ensure_model_instance(
                runner.generate_roommate_reply(
                    request,
                    history,
                    archive_context_summary,
                    same_turn_replies,
                    roommate,
                ),
                RoommateReply,
            )
            self._validate_generated_reply(
                reply,
                item.roommate_id,
                roommate_by_id,
                same_turn_replies,
                existing_turn_counts,
            )
            reply = _normalize_roommate_reply(reply, roommate_by_id)
            same_turn_replies.append(reply)

        if request.is_continuation and not self._memory.is_latest_turn(
            conversation_id,
            request.turn_id,
        ):
            return SimulateResponse(
                conversation_id=conversation_id,
                replies=[],
                archive_context_used=archive_context_summary is not None,
                archive_context_summary=archive_context_summary,
                safety_note=SIMULATE_SAFETY_NOTE,
            )

        if legacy_dialogue:
            self._migrate_legacy_dialogue(conversation_id, legacy_dialogue, request.roommates)
        if not request.is_continuation and request.user_message is not None:
            self._memory.append_user_message(conversation_id, request.user_message)
        for reply in same_turn_replies:
            self._memory.append_roommate_message(
                conversation_id,
                reply.roommate_id,
                reply.roommate,
                reply.personality,
                reply.message,
                turn_id=request.turn_id,
            )

        return SimulateResponse(
            conversation_id=conversation_id,
            replies=same_turn_replies,
            archive_context_used=archive_context_summary is not None,
            archive_context_summary=archive_context_summary,
            safety_note=SIMULATE_SAFETY_NOTE,
        )

    def _resolve_conversation_id(self, request: SimulateRequest) -> str:
        """解析本轮模拟使用的 conversation_id。"""
        if request.conversation_id:
            if not self._memory.has_conversation(request.conversation_id):
                raise ConversationMemoryNotFoundError(_MEMORY_NOT_FOUND_MESSAGE)
            return self._memory.start_conversation(request.conversation_id)

        return self._memory.start_conversation()

    def _resolve_review_dialogue(self, request: ReviewRequest) -> list[DialogueMessage]:
        """复盘优先读取后端记忆，未提供会话 id 时使用 legacy dialogue。"""
        if request.conversation_id:
            return self._memory.get_dialogue(request.conversation_id, limit=50)

        return request.dialogue[-50:]

    def _validate_review_dialogue_has_user_message(
        self,
        dialogue: list[DialogueMessage],
    ) -> None:
        """复盘必须至少包含一条用户发言，避免把客户端空状态伪装成 AI 502。"""
        if not any(message.speaker == "user" for message in dialogue):
            raise ReviewDialogueInvalidError(_REVIEW_DIALOGUE_INVALID_MESSAGE)

    def _planned_replies_for_request(
        self,
        plan: SpeakerPlanResponse,
        request: SimulateRequest,
    ) -> SpeakerPlanResponse:
        """按请求的单步上限裁剪 planner 输出。"""
        if request.max_replies is None:
            return plan

        return SpeakerPlanResponse(replies=plan.replies[: request.max_replies])

    def _migrate_legacy_dialogue(
        self,
        conversation_id: str,
        dialogue: list[DialogueMessage],
        roommates: list[RoommateProfile],
    ) -> None:
        """把旧客户端携带的历史对话迁移进新会话记忆。"""
        roommate_by_id = {roommate.id: roommate for roommate in roommates}
        for message in dialogue:
            if message.speaker == "user":
                self._memory.append_user_message(conversation_id, message.message)
                continue

            roommate = roommate_by_id.get(message.speaker)
            if roommate is None:
                self._memory.append_roommate_message(
                    conversation_id,
                    message.speaker,
                    message.speaker,
                    "系统",
                    message.message,
                )
                continue

            self._memory.append_roommate_message(
                conversation_id,
                roommate.id,
                roommate.name,
                roommate.personality_tag,
                message.message,
            )

    def _validate_planned_replies(
        self,
        plan: SpeakerPlanResponse,
        roommate_by_id: dict[str, RoommateProfile],
        existing_counts: Counter[str] | None = None,
    ) -> None:
        """校验 planner 输出只引用当前请求舍友，且每人最多 3 次。"""
        planned_ids = [item.roommate_id for item in plan.replies]
        _validate_roommate_ids_and_counts(planned_ids, roommate_by_id, existing_counts)

    def _validate_generated_reply(
        self,
        reply: RoommateReply,
        expected_roommate_id: str,
        roommate_by_id: dict[str, RoommateProfile],
        same_turn_replies: list[RoommateReply],
        existing_counts: Counter[str] | None = None,
    ) -> None:
        """校验生成回复必须对应当前 planner item，且每人最多 3 次。"""
        if reply.roommate_id != expected_roommate_id:
            raise AIOutputStructureError(_STRUCTURE_ERROR_MESSAGE)

        reply_ids = [existing.roommate_id for existing in same_turn_replies]
        reply_ids.append(reply.roommate_id)
        _validate_roommate_ids_and_counts(reply_ids, roommate_by_id, existing_counts)

    def _build_review_response_from_draft(
        self,
        request: ReviewRequest,
        draft: ReviewDraftResponse,
        dialogue: list[DialogueMessage],
    ) -> ReviewResponse:
        """把 AI 宽松草稿收敛为严格 ReviewResponse，避免可修正输出变成 502。"""
        suggestions = _normalize_review_suggestions(draft.rewrite_suggestions or [], dialogue)
        rewritten_message = _clean_text(draft.rewritten_message)
        if rewritten_message is None:
            rewritten_message = suggestions[0].suggested_message

        payload = {
            "summary": _clean_text(draft.summary)
            or f"本次复盘围绕“{request.scenario}”中的表达方式，重点关注语气、具体请求和后续协商。",
            "strengths": _sanitize_text_list(
                draft.strengths or [],
                fallback=["已经尝试把自己的感受或诉求说出来。"],
            ),
            "risks": _sanitize_text_list(
                draft.risks or [],
                fallback=["后续沟通中要避免笼统指责，尽量把影响和请求说具体。"],
            ),
            "performance_scores": _normalize_review_scores(draft.performance_scores),
            "rewrite_suggestions": suggestions,
            "rewritten_message": rewritten_message,
            "next_steps": _sanitize_text_list(
                draft.next_steps or [],
                fallback=["选择双方情绪较平稳的时间，围绕一个具体可执行的调整继续沟通。"],
            ),
            "safety_note": _normalize_review_safety_note(draft.safety_note),
        }

        return ReviewResponse(**payload)

    def archive_insight(
        self,
        events: list[EventRecord],
        analysis: ArchiveAnalysisResponse,
    ) -> ArchiveInsightResponse:
        """生成事件档案 AI 见解，并保证返回值符合 ArchiveInsightResponse。"""
        public_error: AIServiceUnavailableError | None = None
        result: object | None = None

        try:
            result = self._get_runner().generate_archive_insight(events, analysis)
        except AIServiceConfigurationError:
            raise
        except AIOutputStructureError:
            public_error = AIOutputStructureError(_STRUCTURE_ERROR_MESSAGE)
        except AIServiceUnavailableError:
            public_error = AIServiceUnavailableError(_UNAVAILABLE_ERROR_MESSAGE)
        except ValidationError:
            public_error = AIOutputStructureError(_STRUCTURE_ERROR_MESSAGE)
        except Exception:
            public_error = AIServiceUnavailableError(_UNAVAILABLE_ERROR_MESSAGE)

        if public_error is not None:
            raise public_error

        return _ensure_model_instance(result, ArchiveInsightResponse)


def _ensure_model_instance(value: object, schema: type[OutputModel]) -> OutputModel:
    """统一把 LangChain 返回值收敛到接口响应模型。"""
    if isinstance(value, schema):
        return value

    if isinstance(value, dict):
        validation_failed = False
        model: OutputModel | None = None
        try:
            model = schema.model_validate(value)
        except ValidationError:
            validation_failed = True

        if validation_failed:
            raise AIOutputStructureError(_STRUCTURE_ERROR_MESSAGE)

        if model is not None:
            return model

    raise AIOutputStructureError(_STRUCTURE_ERROR_MESSAGE)


def _ensure_review_draft_instance(value: object) -> ReviewDraftResponse:
    """把 runner 的复盘输出先收敛为宽松草稿，后续再做业务归一化。"""
    if isinstance(value, ReviewDraftResponse):
        return value

    if isinstance(value, ReviewResponse):
        return ReviewDraftResponse.model_validate(value.model_dump(mode="json"))

    if isinstance(value, dict):
        draft_payload = dict(value)
        if not isinstance(draft_payload.get("rewrite_suggestions"), list):
            draft_payload["rewrite_suggestions"] = []
        else:
            draft_payload["rewrite_suggestions"] = [
                item
                for item in draft_payload["rewrite_suggestions"]
                if isinstance(item, dict)
            ]
        if not isinstance(draft_payload.get("strengths"), list):
            draft_payload["strengths"] = []
        if not isinstance(draft_payload.get("risks"), list):
            draft_payload["risks"] = []
        if not isinstance(draft_payload.get("next_steps"), list):
            draft_payload["next_steps"] = []
        if not isinstance(draft_payload.get("performance_scores"), dict):
            draft_payload["performance_scores"] = None

        try:
            return ReviewDraftResponse.model_validate(draft_payload)
        except ValidationError:
            raise AIOutputStructureError(_STRUCTURE_ERROR_MESSAGE) from None

    raise AIOutputStructureError(_STRUCTURE_ERROR_MESSAGE)


def _clean_text(value: object | None) -> str | None:
    """清理 AI 草稿文本，空白或非字符串统一视为缺失。"""
    if not isinstance(value, str):
        return None

    text = value.strip()
    return text or None


def _sanitize_text_list(values: list[object], fallback: list[str]) -> list[str]:
    """清理 AI 草稿列表，并保证最终至少有一条可展示内容。"""
    cleaned = []
    for value in values:
        text = _clean_text(value)
        if text is not None:
            cleaned.append(text)

    return cleaned or fallback


def _normalize_review_scores(
    scores: ReviewPerformanceScoresDraft | None,
) -> ReviewPerformanceScores:
    """复盘分数缺失或越界时收敛到安全默认值。"""
    return ReviewPerformanceScores(
        clarity=_clamp_score(scores.clarity if scores is not None else None, 75),
        empathy=_clamp_score(scores.empathy if scores is not None else None, 72),
        resolution=_clamp_score(scores.resolution if scores is not None else None, 70),
    )


def _clamp_score(value: object | None, fallback: int) -> int:
    """把 AI 草稿评分归一为 0-100 整数。"""
    if isinstance(value, int | float) and not isinstance(value, bool):
        return max(0, min(100, round(value)))

    if isinstance(value, str):
        try:
            numeric_value = float(value.strip())
        except ValueError:
            return fallback
        return max(0, min(100, round(numeric_value)))

    return fallback


def _normalize_review_safety_note(value: object | None) -> str:
    """AI safety_note 不完整时使用项目统一安全边界。"""
    text = _clean_text(value)
    if text is None:
        return REVIEW_SAFETY_NOTE

    try:
        ReviewResponse(
            summary="安全边界校验",
            strengths=["保留有效表达"],
            risks=["避免现实误判"],
            performance_scores=ReviewPerformanceScores(
                clarity=75,
                empathy=75,
                resolution=75,
            ),
            rewrite_suggestions=[
                ReviewRewriteSuggestion(
                    message_index=0,
                    original_message="占位文本",
                    issue="占位问题",
                    suggested_message="占位建议",
                    reason="占位理由",
                )
            ],
            rewritten_message="占位建议",
            next_steps=["继续现实沟通"],
            safety_note=text,
        )
    except ValidationError:
        return REVIEW_SAFETY_NOTE

    return text


def _normalize_review_suggestions(
    suggestions: list[ReviewRewriteSuggestionDraft],
    dialogue: list[DialogueMessage],
) -> list[ReviewRewriteSuggestion]:
    """将 AI 建议定位到真实用户发言；定位失败的建议跳过并补兜底建议。"""
    user_entries = [
        (index, message.message)
        for index, message in enumerate(dialogue)
        if message.speaker == "user"
    ]
    if not user_entries:
        raise AIOutputStructureError(_STRUCTURE_ERROR_MESSAGE)

    normalized: list[ReviewRewriteSuggestion] = []
    used_indexes: set[int] = set()
    for suggestion in suggestions:
        located = _locate_suggested_user_message(suggestion, user_entries)
        if located is None:
            continue

        message_index, original_message = located
        if message_index in used_indexes:
            continue

        used_indexes.add(message_index)
        normalized.append(_build_review_suggestion(message_index, original_message, suggestion))

    if normalized:
        for index, message in user_entries:
            if index in used_indexes or not _should_suggest_rewrite_for_user_message(message):
                continue
            normalized.append(_build_review_suggestion(index, message))

        return normalized

    return [
        _build_review_suggestion(index, message)
        for index, message in user_entries
    ]


def _build_review_suggestion(
    message_index: int,
    original_message: str,
    draft: ReviewRewriteSuggestionDraft | None = None,
) -> ReviewRewriteSuggestion:
    """构造严格话术建议，避免 AI 文本过长或缺字段导致接口 502。"""
    original = _truncate_review_text(
        original_message,
        _REVIEW_ORIGINAL_MESSAGE_MAX_LENGTH,
    )
    draft_issue = _clean_text(draft.issue) if draft is not None else None
    draft_suggested_message = (
        _clean_text(draft.suggested_message) if draft is not None else None
    )
    draft_reason = _clean_text(draft.reason) if draft is not None else None
    issue = _truncate_review_text(
        draft_issue or "这句话可以进一步降低指责感，并补充具体可执行的请求。",
        _REVIEW_ISSUE_MAX_LENGTH,
    )
    suggested_message = _truncate_review_text(
        draft_suggested_message or _build_default_rewrite(original),
        _REVIEW_SUGGESTED_MESSAGE_MAX_LENGTH,
    )
    reason = _truncate_review_text(
        draft_reason or "先说明自己的感受和具体影响，再提出可执行的请求，更容易被回应。",
        _REVIEW_REASON_MAX_LENGTH,
    )

    return ReviewRewriteSuggestion(
        message_index=message_index,
        original_message=original,
        issue=issue,
        suggested_message=suggested_message,
        reason=reason,
    )


def _should_suggest_rewrite_for_user_message(message: str) -> bool:
    """模型漏选时，用保守关键词补齐明显需要改写的用户发言。"""
    compact_message = _normalize_review_text(message)
    if not compact_message:
        return False

    return any(keyword in compact_message for keyword in _IMPROVABLE_USER_MESSAGE_KEYWORDS)


def _locate_suggested_user_message(
    suggestion: ReviewRewriteSuggestionDraft,
    user_entries: list[tuple[int, str]],
) -> tuple[int, str] | None:
    """兼容模型把 message_index 写成 dialogue 下标或用户发言序号。"""
    original_message = _clean_text(suggestion.original_message)
    suggested_index = _coerce_nonnegative_int(suggestion.message_index)

    if suggested_index is not None:
        exact_entry = next(
            (entry for entry in user_entries if entry[0] == suggested_index),
            None,
        )
        if exact_entry is not None and _text_matches(original_message, exact_entry[1]):
            return exact_entry

        if 0 <= suggested_index < len(user_entries):
            ordinal_entry = user_entries[suggested_index]
            if _text_matches(original_message, ordinal_entry[1]):
                return ordinal_entry

    if original_message is None:
        return None

    exact_matches = [
        entry for entry in user_entries if entry[1] == original_message
    ]
    if len(exact_matches) == 1:
        return exact_matches[0]
    if len(exact_matches) > 1:
        return exact_matches[-1]

    normalized_matches = [
        entry for entry in user_entries if _text_matches(original_message, entry[1])
    ]
    if len(normalized_matches) == 1:
        return normalized_matches[0]
    if len(normalized_matches) > 1:
        return normalized_matches[-1]

    return None


def _coerce_nonnegative_int(value: object | None) -> int | None:
    """兼容模型把下标写成数字字符串；其他异常类型视为缺失。"""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float):
        return int(value) if value >= 0 and value.is_integer() else None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            parsed = int(text)
        except ValueError:
            return None
        return parsed if parsed >= 0 else None

    return None


def _text_matches(candidate: str | None, actual: str) -> bool:
    """比较建议原文与真实用户消息，允许标点和空白差异。"""
    if candidate is None:
        return True

    if candidate == actual:
        return True

    normalized_candidate = _normalize_review_text(candidate)
    normalized_actual = _normalize_review_text(actual)
    return bool(
        normalized_candidate
        and normalized_actual
        and (
            normalized_candidate == normalized_actual
            or normalized_candidate in normalized_actual
            or normalized_actual in normalized_candidate
        )
    )


def _normalize_review_text(value: str) -> str:
    """移除常见空白和中英文标点，用于 AI 输出原文的容错匹配。"""
    return re.sub(r"[\s，。！？、,.!?;；:：“”\"'‘’（）()\[\]【】《》<>…]+", "", value)


def _build_default_rewrite(original_message: str) -> str:
    """给可修正但不完整的 AI 建议生成一条保守改写。"""
    original = _truncate_review_text(original_message, 220)
    quoted_message = original if original == original_message else f"{original}..."
    return _truncate_review_text(
        f"我想把刚才“{quoted_message}”这件事说清楚："
        "我感受到了一些影响，也希望我们能一起约定一个具体、可执行的调整方式。",
        _REVIEW_SUGGESTED_MESSAGE_MAX_LENGTH,
    )


def _truncate_review_text(value: str, max_length: int) -> str:
    """按响应字段上限截断文本，保留非空内容。"""
    text = value.strip()
    if len(text) <= max_length:
        return text

    return text[: max(1, max_length - 3)].rstrip() + "..."


def _validate_roommate_ids_and_counts(
    roommate_ids: list[str],
    roommate_by_id: dict[str, RoommateProfile],
    existing_counts: Counter[str] | None = None,
) -> None:
    """校验本轮回复 id 均来自请求，且单个舍友最多回复 3 条。"""
    unknown_ids = [roommate_id for roommate_id in roommate_ids if roommate_id not in roommate_by_id]
    if unknown_ids:
        raise AIOutputStructureError(_STRUCTURE_ERROR_MESSAGE)

    counts = Counter(existing_counts or {})
    counts.update(roommate_ids)
    if any(count > 3 for count in counts.values()):
        raise AIOutputStructureError(_STRUCTURE_ERROR_MESSAGE)


def _normalize_roommate_reply(
    reply: RoommateReply,
    roommate_by_id: dict[str, RoommateProfile],
) -> RoommateReply:
    """以服务端请求画像为准，避免模型串改舍友名称或性格标签。"""
    roommate = roommate_by_id.get(reply.roommate_id)
    if roommate is None:
        raise AIOutputStructureError(_STRUCTURE_ERROR_MESSAGE)

    return reply.model_copy(
        update={
            "roommate": roommate.name,
            "personality": roommate.personality_tag,
        }
    )


LangChainOpenAIRunner = LangChainDeepSeekRunner
