"""前后端接口契约和 AI 结构化输出模型。"""

from datetime import date, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EventType(StrEnum):
    """用户可记录的宿舍关系事件类型。"""

    NOISE = "noise"
    SCHEDULE = "schedule"
    HYGIENE = "hygiene"
    COST = "cost"
    PRIVACY = "privacy"
    EMOTION = "emotion"


class EventFrequency(StrEnum):
    """宿舍关系事件在现实中发生的频率等级。"""

    OCCASIONAL = "occasional"
    WEEKLY_MULTIPLE = "weekly_multiple"
    DAILY = "daily"


class Emotion(StrEnum):
    """用户记录事件时可选择的主要情绪。"""

    IRRITABLE = "irritable"
    ANXIOUS = "anxious"
    WRONGED = "wronged"
    ANGRY = "angry"
    HELPLESS = "helpless"
    DEPRESSED = "depressed"


class AnalyzeRequest(BaseModel):
    """单条宿舍事件压力分析接口的请求体。"""

    event_type: EventType
    severity: int = Field(ge=1, le=5)
    frequency: EventFrequency
    emotion: Emotion
    has_communicated: bool
    has_conflict: bool
    description: str = Field(max_length=500)

    @field_validator("description", mode="before")
    @classmethod
    def trim_and_require_description(cls, value: str) -> str:
        """清理事件描述首尾空白，并拒绝空描述。"""
        if not isinstance(value, str):
            raise ValueError("description must be a string")

        description = value.strip()
        if not description:
            raise ValueError("description must not be empty")

        return description


AnalyzeRiskLevel = Literal["stable", "pressure", "high", "severe"]


class AnalyzeResponse(BaseModel):
    """单条宿舍事件压力分析接口的结构化响应。"""

    pressure_score: int
    risk_level: AnalyzeRiskLevel
    risk_label: str
    main_sources: list[str]
    emotion_keywords: list[str]
    trend_message: str
    suggestion: str
    recommend_simulation: bool
    disclaimer: str


class EventRecordCreate(AnalyzeRequest):
    """创建事件档案记录时使用的请求体。"""

    event_date: date

    @field_validator("event_date")
    @classmethod
    def reject_future_event_date(cls, value: date) -> date:
        """拒绝未来日期，避免档案趋势分析出现反向时间权重。"""
        if value > date.today():
            raise ValueError("event_date must not be in the future")

        return value


class EventRecord(EventRecordCreate):
    """已持久化的事件档案记录，包含单条事件评分快照。"""

    id: str
    created_at: datetime
    single_analysis: AnalyzeResponse


class EventArchiveResponse(BaseModel):
    """事件档案列表接口的响应体。"""

    events: list[EventRecord]


class SourceBreakdown(BaseModel):
    """档案总压力中单个压力来源的贡献占比。"""

    label: str
    percent: int
    contribution: float


class ArchiveAnalysisResponse(AnalyzeResponse):
    """事件档案总压力分析接口的结构化响应。"""

    event_count: int
    active_30d_count: int
    source_breakdown: list[SourceBreakdown]


class ArchiveInsightResponse(BaseModel):
    """AI 基于事件档案生成的结构化心晴见解。"""

    insight: str
    care_suggestion: str
    communication_focus: list[str] = Field(min_length=1)
    safety_note: str

    @field_validator("insight", "care_suggestion", "safety_note", mode="before")
    @classmethod
    def trim_and_require_text(cls, value: str) -> str:
        """清理 AI 文本字段首尾空白，并拒绝空字符串。"""
        if not isinstance(value, str):
            raise ValueError("field must be a string")

        text = value.strip()
        if not text:
            raise ValueError("field must not be empty")

        return text

    @field_validator("communication_focus")
    @classmethod
    def require_non_empty_focus_items(cls, value: list[str]) -> list[str]:
        """确保沟通重点列表中的每一项都是非空文本。"""
        cleaned_items: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise ValueError("communication_focus items must be strings")

            cleaned_item = item.strip()
            if not cleaned_item:
                raise ValueError("communication_focus items must not be empty")
            cleaned_items.append(cleaned_item)

        return cleaned_items

    @field_validator("safety_note", mode="after")
    @classmethod
    def validate_safety_note(cls, value: str) -> str:
        """校验档案见解保留非诊断和现实支持等安全边界。"""
        return _validate_safety_note_boundaries(value)


RoommateName = Literal["舍友 A", "舍友 B", "舍友 C"]
RoommatePersonality = Literal["直接型", "回避型", "调和型"]
DialogueSpeaker = Literal["user", "roommate_a", "roommate_b", "roommate_c", "system"]

# 兼容前端展示文案，进入 AI 服务前统一收敛为后端稳定枚举。
FRONTEND_DIALOGUE_SPEAKER_ALIASES = {
    "我": "user",
    "你": "user",
    "用户": "user",
    "系统": "system",
    "舍友 A": "roommate_a",
    "舍友A": "roommate_a",
    "舍友 A（直接型）": "roommate_a",
    "舍友 A(直接型)": "roommate_a",
    "舍友 B": "roommate_b",
    "舍友B": "roommate_b",
    "舍友 B（回避型）": "roommate_b",
    "舍友 B(回避型)": "roommate_b",
    "舍友 C": "roommate_c",
    "舍友C": "roommate_c",
    "舍友 C（调和型）": "roommate_c",
    "舍友 C(调和型)": "roommate_c",
}

# 旧演示数据和当前 UI 的事件 id 不完全一致，这里只做显式白名单归一化。
FRONTEND_REVIEW_EVENT_TYPE_ALIASES = {
    "noise_conflict": "noise",
    "schedule_conflict": "schedule",
    "hygiene_conflict": "hygiene",
    "expense_conflict": "cost",
    "cost_conflict": "cost",
    "privacy_boundary": "privacy",
    "privacy_conflict": "privacy",
    "emotional_conflict": "emotion",
    "emotion_conflict": "emotion",
}
ANALYSIS_ONLY_EVENT_TYPE_ALIASES = {
    "risk-stable",
    "risk-pressure",
    "risk-high",
    "risk-severe",
}


def _validate_safety_note_boundaries(value: str) -> str:
    """校验 AI 输出仍保留项目要求的安全边界。"""
    if not isinstance(value, str):
        raise ValueError("safety_note must be a string")

    safety_note = value.strip()
    if not safety_note:
        raise ValueError("safety_note must not be empty")

    has_diagnosis_boundary = (
        "不进行心理诊断" in safety_note or "不进行心理疾病诊断" in safety_note
    )
    has_required_boundaries = (
        has_diagnosis_boundary
        and "不进行医学判断" in safety_note
        and "不进行人格评价" in safety_note
    )
    has_reality_support = any(
        phrase in safety_note for phrase in ("辅导员", "心理老师", "现实支持")
    )
    has_rehearsal_purpose = (
        "仅用于宿舍沟通演练" in safety_note or "仅用于沟通训练建议" in safety_note
    )
    has_virtual_roommate_boundary = "不代表真实舍友想法" in safety_note

    if (
        not has_required_boundaries
        or not has_reality_support
        or not has_rehearsal_purpose
        or not has_virtual_roommate_boundary
    ):
        raise ValueError("safety_note must include phase-2 safety boundaries")

    return safety_note


class DialogueMessage(BaseModel):
    """模拟或复盘中一条标准化对话消息。"""

    model_config = ConfigDict(extra="forbid")

    speaker: DialogueSpeaker
    message: str = Field(max_length=500)

    @field_validator("speaker", mode="before")
    @classmethod
    def normalize_frontend_speaker_alias(cls, value: str) -> str:
        """把前端展示用 speaker 文案归一为后端稳定枚举值。"""
        if not isinstance(value, str):
            raise ValueError("speaker must be a string")

        speaker = value.strip()
        return FRONTEND_DIALOGUE_SPEAKER_ALIASES.get(speaker, speaker)

    @field_validator("message", mode="before")
    @classmethod
    def trim_and_require_message(cls, value: str) -> str:
        """清理对话内容首尾空白，并拒绝空消息。"""
        if not isinstance(value, str):
            raise ValueError("message must be a string")

        message = value.strip()
        if not message:
            raise ValueError("message must not be empty")

        return message


class SimulateRequest(BaseModel):
    """AI 沟通模拟接口的请求体。"""

    scenario: str = Field(max_length=300)
    user_message: str = Field(max_length=500)
    risk_level: AnalyzeRiskLevel | None = None
    context: str | None = Field(default=None, max_length=500)
    dialogue: list[DialogueMessage] = Field(default_factory=list, max_length=20)

    @field_validator("scenario", "user_message", mode="before")
    @classmethod
    def trim_and_require_text(cls, value: str) -> str:
        """清理必填文本字段首尾空白，并拒绝空字符串。"""
        if not isinstance(value, str):
            raise ValueError("field must be a string")

        text = value.strip()
        if not text:
            raise ValueError("field must not be empty")

        return text

    @field_validator("risk_level", mode="before")
    @classmethod
    def trim_optional_risk_level(cls, value: str | None) -> str | None:
        """把空白风险等级视为未提供，非空值交给枚举校验。"""
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("risk_level must be a string")

        risk_level = value.strip()
        return risk_level or None

    @field_validator("context", mode="before")
    @classmethod
    def trim_optional_context(cls, value: str | None) -> str | None:
        """清理可选补充背景，空白内容统一归一为 None。"""
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("context must be a string")

        context = value.strip()
        return context or None


class RoommateReply(BaseModel):
    """AI 模拟中单个虚拟舍友的结构化回复。"""

    roommate: RoommateName
    personality: RoommatePersonality
    message: str = Field(max_length=500)

    @field_validator("message", mode="before")
    @classmethod
    def trim_and_require_message(cls, value: str) -> str:
        """清理虚拟舍友回复内容，并拒绝空回复。"""
        if not isinstance(value, str):
            raise ValueError("message must be a string")

        message = value.strip()
        if not message:
            raise ValueError("message must not be empty")

        return message


class SimulateResponse(BaseModel):
    """AI 沟通模拟接口的结构化响应。"""

    replies: list[RoommateReply]
    safety_note: str

    @field_validator("safety_note", mode="before")
    @classmethod
    def validate_safety_note(cls, value: str) -> str:
        """校验模拟结果保留非诊断和虚拟舍友边界。"""
        return _validate_safety_note_boundaries(value)

    @model_validator(mode="after")
    def require_fixed_roommate_roles(self) -> "SimulateResponse":
        """保证三位虚拟舍友的角色顺序稳定，方便前端固定展示。"""
        expected_roles = [
            ("舍友 A", "直接型"),
            ("舍友 B", "回避型"),
            ("舍友 C", "调和型"),
        ]
        actual_roles = [(reply.roommate, reply.personality) for reply in self.replies]

        if actual_roles != expected_roles:
            raise ValueError("replies must contain fixed roommate roles in order")

        return self


class ReviewOriginalEvent(BaseModel):
    """复盘时携带的原始事件摘要，用于给 AI 提供上下文。"""

    model_config = ConfigDict(extra="forbid")

    event_type: EventType | None = None
    severity: int | None = Field(default=None, ge=1, le=5)
    frequency: EventFrequency | None = None
    emotion: Emotion | None = None
    has_communicated: bool | None = None
    has_conflict: bool | None = None
    pressure_score: int | None = Field(default=None, ge=0, le=100)
    risk_level: AnalyzeRiskLevel | None = None
    risk_label: str | None = Field(default=None, max_length=50)
    description: str | None = Field(default=None, max_length=300)

    @field_validator("event_type", mode="before")
    @classmethod
    def normalize_frontend_event_type_alias(cls, value: str | None) -> str | None:
        """把前端旧事件类型别名归一为后端事件枚举。"""
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("event_type must be a string")

        event_type = value.strip()
        if not event_type or event_type in ANALYSIS_ONLY_EVENT_TYPE_ALIASES:
            return None

        return FRONTEND_REVIEW_EVENT_TYPE_ALIASES.get(event_type, event_type)

    @field_validator("risk_label", "description", mode="before")
    @classmethod
    def trim_optional_text(cls, value: str | None) -> str | None:
        """清理可选文本字段，空白内容统一归一为 None。"""
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("field must be a string")

        text = value.strip()
        return text or None


class ReviewRequest(BaseModel):
    """AI 沟通复盘接口的请求体。"""

    model_config = ConfigDict(extra="forbid")

    scenario: str = Field(max_length=300)
    dialogue: list[DialogueMessage] = Field(min_length=1, max_length=20)
    original_event: ReviewOriginalEvent | None = None

    @field_validator("scenario", mode="before")
    @classmethod
    def trim_and_require_scenario(cls, value: str) -> str:
        """清理复盘场景文本首尾空白，并拒绝空场景。"""
        if not isinstance(value, str):
            raise ValueError("scenario must be a string")

        scenario = value.strip()
        if not scenario:
            raise ValueError("scenario must not be empty")

        return scenario


class ReviewPerformanceScores(BaseModel):
    """AI 复盘表现总结中的三项结构化评分。"""

    model_config = ConfigDict(extra="forbid")

    clarity: int = Field(ge=0, le=100)
    empathy: int = Field(ge=0, le=100)
    resolution: int = Field(ge=0, le=100)


class ReviewResponse(BaseModel):
    """AI 沟通复盘接口的结构化响应。"""

    summary: str
    strengths: list[str] = Field(min_length=1)
    risks: list[str] = Field(min_length=1)
    performance_scores: ReviewPerformanceScores
    rewritten_message: str
    next_steps: list[str] = Field(min_length=1)
    safety_note: str

    @field_validator("summary", "rewritten_message", "safety_note", mode="before")
    @classmethod
    def trim_and_require_text(cls, value: str) -> str:
        """清理复盘文本字段首尾空白，并拒绝空字符串。"""
        if not isinstance(value, str):
            raise ValueError("field must be a string")

        text = value.strip()
        if not text:
            raise ValueError("field must not be empty")

        return text

    @field_validator("safety_note", mode="after")
    @classmethod
    def validate_safety_note(cls, value: str) -> str:
        """校验复盘结果保留非诊断和现实支持等安全边界。"""
        return _validate_safety_note_boundaries(value)

    @field_validator("strengths", "risks", "next_steps")
    @classmethod
    def require_non_empty_items(cls, value: list[str]) -> list[str]:
        """确保复盘列表字段至少包含可展示的非空文本项。"""
        cleaned_items: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise ValueError("list items must be strings")

            cleaned_item = item.strip()
            if not cleaned_item:
                raise ValueError("list items must not be empty")
            cleaned_items.append(cleaned_item)

        return cleaned_items
