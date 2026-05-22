"""AI 沟通模拟和复盘的 Prompt 构造。"""

import json

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from app.schemas import (
    ArchiveAnalysisResponse,
    DialogueMessage,
    EventRecord,
    ReviewRequest,
    RoommateProfile,
    RoommateReply,
    SimulateRequest,
    emotion_display_label,
)


SAFETY_BOUNDARY_TEXT = (
    "你只处理大学宿舍关系沟通场景，提供沟通演练和沟通训练建议。"
    "不进行心理疾病诊断，不进行医学判断，不进行人格评价。"
    "不得输出攻击、威胁、羞辱、操控或报复性建议。"
    "当内容涉及高压力、暴力风险、严重失眠或现实安全风险时，"
    "提醒用户联系辅导员、心理老师、家人或可信任同学，寻求现实支持。"
    "所有回复都不代表真实舍友想法，只用于安全、温和、具体、可执行的表达练习。"
)

# 系统 Prompt 固定安全边界和输出结构，避免模型返回无法被 Pydantic 解析的自由文本。
SIMULATE_SYSTEM_PROMPT = (
    "你是“舍友心晴”AI 沟通演练助手。本任务是 AI communication rehearsal，"
    "帮助用户在大学宿舍关系沟通场景中预演不同舍友可能的回应。"
    f"{SAFETY_BOUNDARY_TEXT}"
    "默认虚拟舍友示例包括舍友 A/直接型、舍友 B/回避型、舍友 C/调和型，"
    "但实际发言必须以请求中的 roommates 为准。"
    "每轮每位舍友可回复 0-3 条，允许 A -> C -> A -> B 等穿插顺序。"
    "输出必须符合动态结构化字段：roommate_id、roommate、personality、message。"
    "safety_note 必须包含：仅用于宿舍沟通演练、不代表真实舍友想法、"
    "不进行心理诊断或不进行心理疾病诊断、不进行医学判断、不进行人格评价、"
    "辅导员或心理老师或现实支持。"
    "请只输出一个合法 JSON object，不要输出 Markdown、解释或额外文本。"
    "JSON 回复字段示例："
    '{"roommate_id":"roommate_a","roommate":"舍友 A","personality":"直接型",'
    '"message":"温和、具体、可执行的回复"}'
    "不要使用 role、name、type 等其他字段名。"
    "语言要温和、具体、可执行。"
)

SPEAKER_PLAN_SYSTEM_PROMPT = (
    "你是“舍友心晴”AI 多智能体发言规划器。本任务是 speaker planner。"
    f"{SAFETY_BOUNDARY_TEXT}"
    "请根据用户本轮表达、历史对话、同一请求中的 roommates 与可选事件档案摘要，"
    "规划本轮哪些虚拟舍友发言以及发言顺序。"
    "默认普通冲突可规划 3-7 条发言；如果情境已经自然收束，也可以规划 0 条；"
    "最多规划 15 条。"
    "规划必须体现多智能体：后发言的舍友可以被先发言舍友激活、反驳、补充或调和；"
    "同一舍友可以在其他舍友发言后再次出现，例如 A -> C -> A -> B。"
    "不要机械地让每个舍友只说一条，也不要固定 A/B/C 顺序。"
    "每位舍友本轮最多出现 3 次，所有 roommate_id 必须来自请求中的 roommates，"
    "如果请求提供 max_replies，replies 长度不得超过 max_replies。"
    "请只输出一个合法 JSON object，不要输出 Markdown、解释或额外文本。"
    'JSON 必须严格使用：{"replies":[{"roommate_id":"roommate_a"}]}。'
)

ROOMMATE_REPLY_SYSTEM_PROMPT = (
    "你是“舍友心晴”AI 舍友回复生成器。本任务是 per-roommate reply generation。"
    f"{SAFETY_BOUNDARY_TEXT}"
    "请只为当前指定的一个虚拟舍友生成一条回复。"
    "回复必须参考历史对话、当前用户发言、事件档案摘要和本轮已生成的前序舍友回复，"
    "并符合该舍友的 personality_tag 和 traits。"
    "请只输出一个合法 JSON object，不要输出 Markdown、解释或额外文本。"
    "JSON 必须严格使用："
    '{"roommate_id":"roommate_a","roommate":"舍友 A","personality":"直接型","message":"回复内容"}。'
)

REVIEW_SYSTEM_PROMPT = (
    "你是“舍友心晴”AI 沟通复盘助手。本任务是 communication review，"
    "帮助用户复盘大学宿舍关系沟通场景中的表达方式。"
    f"{SAFETY_BOUNDARY_TEXT}"
    "请输出结构化 ReviewResponse，包括 summary、strengths、risks、"
    "performance_scores、rewrite_suggestions、rewritten_message、next_steps、"
    "communication_plan 和 safety_note。"
    "rewrite_suggestions 必须从完整 dialogue 中筛选用户表达不够好的话术，"
    "所有表达不好的用户发言都必须给出建议话术，不要只选择一条，"
    "这些建议只能对应 speaker=user 消息，"
    "至少选择 1 条，不要固定选择最后一句；如果整体表达较好，也选择最值得进一步优化的一句。"
    "message_index 必须对应原始 dialogue 中该用户发言的 0 基下标。"
    "只能选择 speaker=user 的消息，original_message 必须来自对应原文，"
    "不能选择虚拟舍友或系统消息，也不能编造 dialogue 中不存在的原话。"
    "performance_scores 是表现总结评分，必须包含 clarity、empathy、resolution 三个字段，"
    "分别表示表达清晰度、共情能力、问题解决度，值必须是 0-100 的整数。"
    "communication_plan 必须包含 opening、specific_request、fallback_plan 三段："
    "opening 是用户下一次现实沟通的温和开场白，specific_request 是具体请求，"
    "fallback_plan 是对方暂时不同意或沟通受阻时的兜底方案。"
    "safety_note 必须包含：仅用于沟通训练建议、不代表真实舍友想法、"
    "不进行心理诊断或不进行心理疾病诊断、不进行医学判断、不进行人格评价、"
    "辅导员或心理老师或现实支持。"
    "请只输出一个合法 JSON object，不要输出 Markdown、解释或额外文本。"
    "JSON 必须严格使用以下字段结构："
    '{"summary":"一句话概括用户表达方式","strengths":["具体优点"],'
    '"risks":["需要避免的沟通风险"],'
    '"performance_scores":{"clarity":80,"empathy":75,"resolution":70},'
    '"rewrite_suggestions":[{"message_index":0,"original_message":"原话",'
    '"issue":"问题","suggested_message":"改写话术","reason":"理由"}],'
    '"rewritten_message":"更温和、具体、可执行的改写话术",'
    '"next_steps":["下一步现实沟通建议"],'
    '"communication_plan":{"opening":"开场白","specific_request":"具体请求","fallback_plan":"兜底方案"},'
    '"safety_note":"本复盘仅用于沟通训练建议，不代表真实舍友想法，不进行心理诊断，不进行医学判断，不进行人格评价。如压力持续升高，请寻求现实支持或联系辅导员、心理老师。"}'
    "strengths、risks、next_steps 都必须至少包含一条非空字符串。"
    "建议必须温和、具体、可执行，并强调现实沟通边界。"
)

ARCHIVE_INSIGHT_SYSTEM_PROMPT = (
    "你是“舍友心晴”AI 心晴见解助手。本任务是 archive insight，"
    "帮助用户从已记录的大学宿舍关系事件档案中总结压力来源、照顾建议和沟通重点。"
    f"{SAFETY_BOUNDARY_TEXT}"
    "请输出结构化 ArchiveInsightResponse，包括 insight、care_suggestion、"
    "communication_focus 和 safety_note。"
    "communication_focus 必须至少包含一条非空字符串，每条都要具体、可执行。"
    "safety_note 必须包含：仅用于沟通训练建议、不代表真实舍友想法、"
    "不进行心理诊断或不进行心理疾病诊断、不进行医学判断、不进行人格评价、"
    "辅导员或心理老师或现实支持。"
    "请只输出一个合法 JSON object，不要输出 Markdown、解释或额外文本。"
    "JSON 必须严格使用以下字段结构："
    '{"insight":"基于事件档案的一段心晴见解",'
    '"care_suggestion":"照顾情绪和现实安全的建议",'
    '"communication_focus":["下一次沟通最需要聚焦的事项"],'
    '"safety_note":"本建议仅用于沟通训练建议，不代表真实舍友想法，不进行心理诊断，不进行医学判断，不进行人格评价。如压力持续升高，请联系辅导员或心理老师寻求现实支持。"}'
    "不要编造不存在的事件，不要做医学、心理疾病或人格判断。"
)


ARCHIVE_INSIGHT_EVENT_FIELDS = {
    "event_date",
    "event_type",
    "severity",
    "frequency",
    "emotion",
    "emotions",
    "primary_emotion",
    "has_communicated",
    "has_conflict",
    "description",
}
ARCHIVE_INSIGHT_ANALYSIS_FIELDS = {
    "pressure_score",
    "risk_level",
    "risk_label",
    "main_sources",
    "emotion_keywords",
    "trend_message",
    "suggestion",
    "recommend_simulation",
    "event_count",
    "active_30d_count",
    "source_breakdown",
}


def _serialize_dialogue(dialogue: list[DialogueMessage]) -> str:
    """把标准对话消息序列化为 prompt 中稳定的行格式。"""
    dialogue_lines = "\n".join(
        f"{message.speaker}: {message.message}" for message in dialogue
    )
    return dialogue_lines if dialogue_lines else "无历史对话"


def _serialize_roommates(roommates: list[RoommateProfile]) -> str:
    """把舍友画像序列化为受控 JSON，供规划器和回复生成器使用。"""
    return json.dumps(
        [roommate.model_dump(mode="json", exclude={"avatar"}) for roommate in roommates],
        ensure_ascii=False,
        sort_keys=True,
    )


def _serialize_same_turn_replies(replies: list[RoommateReply]) -> str:
    """把本轮已生成回复序列化，供后续舍友看到前序发言。"""
    if not replies:
        return "[]"
    return json.dumps(
        [reply.model_dump(mode="json") for reply in replies],
        ensure_ascii=False,
        sort_keys=True,
    )


def _serialize_indexed_dialogue(dialogue: list[DialogueMessage]) -> str:
    """把复盘对话序列化为带原始 0 基下标的行格式。"""
    if not dialogue:
        return "无历史对话"

    return "\n".join(
        f"[{index}] {message.speaker}: {message.message}"
        for index, message in enumerate(dialogue)
    )


def build_speaker_plan_messages(
    request: SimulateRequest,
    history: list[DialogueMessage],
    archive_context_summary: str | None = None,
) -> list[BaseMessage]:
    """构造发言规划器的 LangChain 消息。"""
    context = request.context if request.context is not None else "无补充背景"
    risk_level = request.risk_level if request.risk_level is not None else "未提供"
    archive_context = archive_context_summary or "未接入事件档案摘要"
    user_message = request.user_message or "无新增用户发言，请基于最新历史继续判断是否还有舍友需要回应"
    max_replies = request.max_replies if request.max_replies is not None else 15
    human_prompt = (
        "请规划本轮需要发言的虚拟舍友和顺序。\n"
        f"scenario: {request.scenario}\n"
        f"history:\n{_serialize_dialogue(history)}\n"
        f"user_message: {user_message}\n"
        f"is_continuation: {request.is_continuation}\n"
        f"max_replies: {max_replies}\n"
        f"risk_level: {risk_level}\n"
        f"context: {context}\n"
        f"archive_context_summary: {archive_context}\n"
        f"roommates:\n{_serialize_roommates(request.roommates)}"
    )

    return [
        SystemMessage(content=SPEAKER_PLAN_SYSTEM_PROMPT),
        HumanMessage(content=human_prompt),
    ]


def build_roommate_reply_messages(
    request: SimulateRequest,
    history: list[DialogueMessage],
    archive_context_summary: str | None,
    same_turn_replies: list[RoommateReply],
    roommate: RoommateProfile,
) -> list[BaseMessage]:
    """构造单个虚拟舍友回复生成器的 LangChain 消息。"""
    context = request.context if request.context is not None else "无补充背景"
    risk_level = request.risk_level if request.risk_level is not None else "未提供"
    archive_context = archive_context_summary or "未接入事件档案摘要"
    user_message = request.user_message or "无新增用户发言，请基于最新历史和本轮前序舍友发言继续回应"
    human_prompt = (
        "请为 current_roommate 生成一条结构化回复。\n"
        f"scenario: {request.scenario}\n"
        f"history:\n{_serialize_dialogue(history)}\n"
        f"user_message: {user_message}\n"
        f"is_continuation: {request.is_continuation}\n"
        f"risk_level: {risk_level}\n"
        f"context: {context}\n"
        f"archive_context_summary: {archive_context}\n"
        f"same_turn_replies: {_serialize_same_turn_replies(same_turn_replies)}\n"
        f"current_roommate: {json.dumps(roommate.model_dump(mode='json', exclude={'avatar'}), ensure_ascii=False, sort_keys=True)}"
    )

    return [
        SystemMessage(content=ROOMMATE_REPLY_SYSTEM_PROMPT),
        HumanMessage(content=human_prompt),
    ]


def build_simulate_messages(request: SimulateRequest) -> list[BaseMessage]:
    """把模拟请求拆成 LangChain system/human 两类消息。"""
    context = request.context if request.context is not None else "无补充背景"
    risk_level = request.risk_level if request.risk_level is not None else "未提供"
    dialogue_text = _serialize_dialogue(request.dialogue)
    user_message = request.user_message or "无新增用户发言"
    human_prompt = (
        "请基于以下用户输入生成动态虚拟舍友角色的结构化回复。\n"
        "如果 dialogue 非空，请把本次 user_message 视为同一场景下的下一轮对话，"
        "不要重启场景，不要重复上一轮已经说过的内容。\n"
        f"scenario: {request.scenario}\n"
        f"dialogue:\n{dialogue_text}\n"
        f"user_message: {user_message}\n"
        f"risk_level: {risk_level}\n"
        f"context: {context}"
    )

    return [SystemMessage(content=SIMULATE_SYSTEM_PROMPT), HumanMessage(content=human_prompt)]


def build_review_messages(
    request: ReviewRequest,
    dialogue: list[DialogueMessage] | None = None,
) -> list[BaseMessage]:
    """把复盘请求拆成 LangChain system/human 两类消息。"""
    review_dialogue = request.dialogue if dialogue is None else dialogue
    original_event = (
        json.dumps(
            request.original_event.model_dump(exclude_none=True, mode="json"),
            ensure_ascii=False,
            sort_keys=True,
        )
        if request.original_event is not None
        else "未提供"
    )
    human_prompt = (
        "请基于以下宿舍沟通对话做结构化复盘。\n"
        "dialogue 每行开头的方括号数字就是原始 0 基 message_index。\n"
        f"scenario: {request.scenario}\n"
        f"dialogue:\n{_serialize_indexed_dialogue(review_dialogue)}\n"
        f"original_event: {original_event}"
    )

    return [SystemMessage(content=REVIEW_SYSTEM_PROMPT), HumanMessage(content=human_prompt)]


def build_archive_insight_messages(
    events: list[EventRecord],
    analysis: ArchiveAnalysisResponse,
) -> list[BaseMessage]:
    """把事件档案和总压力分析拆成 LangChain 消息。"""
    serialized_events = json.dumps(
        [_serialize_archive_insight_event(event) for event in events],
        ensure_ascii=False,
        sort_keys=True,
    )
    serialized_analysis = json.dumps(
        analysis.model_dump(
            include=ARCHIVE_INSIGHT_ANALYSIS_FIELDS,
            mode="json",
        ),
        ensure_ascii=False,
        sort_keys=True,
    )
    human_prompt = (
        "请基于以下事件档案和总压力分析生成结构化 AI 心晴见解。\n"
        f"events:\n{serialized_events}\n"
        f"archive_analysis:\n{serialized_analysis}"
    )

    return [
        SystemMessage(content=ARCHIVE_INSIGHT_SYSTEM_PROMPT),
        HumanMessage(content=human_prompt),
    ]


def _serialize_archive_insight_event(event: EventRecord) -> dict[str, object]:
    """序列化事件并附带稳定中文情绪标签，避免模型自行误译。"""
    payload = event.model_dump(
        include=ARCHIVE_INSIGHT_EVENT_FIELDS,
        mode="json",
    )
    selected_emotions = event.emotions or ([event.emotion] if event.emotion else [])
    primary_emotion = event.primary_emotion or event.emotion
    payload["emotion_labels"] = [
        emotion_display_label(emotion) for emotion in selected_emotions
    ]
    if primary_emotion is not None:
        payload["primary_emotion_label"] = emotion_display_label(primary_emotion)

    return payload
