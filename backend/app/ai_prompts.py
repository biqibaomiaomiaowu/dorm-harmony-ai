"""AI 沟通模拟和复盘的 Prompt 构造。"""

import json

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from app.schemas import ArchiveAnalysisResponse, EventRecord, ReviewRequest, SimulateRequest


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
    "请固定输出三位虚拟舍友角色，并保持顺序："
    "舍友 A/直接型：表达直接，可能反驳，但不得攻击或羞辱；"
    "舍友 B/回避型：倾向回避冲突，但回复必须有实际信息；"
    "舍友 C/调和型：愿意缓和关系，并提出可执行规则。"
    "输出必须符合结构化 SimulateResponse：replies 三条和 safety_note。"
    "safety_note 必须包含：仅用于宿舍沟通演练、不代表真实舍友想法、"
    "不进行心理诊断或不进行心理疾病诊断、不进行医学判断、不进行人格评价、"
    "辅导员或心理老师或现实支持。"
    "请只输出一个合法 JSON object，不要输出 Markdown、解释或额外文本。"
    "JSON 必须严格使用以下字段结构和固定顺序："
    '{"replies":[{"roommate":"舍友 A","personality":"直接型","message":"温和、具体、可执行的回复"},'
    '{"roommate":"舍友 B","personality":"回避型","message":"温和、具体、可执行的回复"},'
    '{"roommate":"舍友 C","personality":"调和型","message":"温和、具体、可执行的回复"}],'
    '"safety_note":"本回复仅用于宿舍沟通演练，不代表真实舍友想法，不进行心理诊断，不进行医学判断，不进行人格评价。如有现实安全风险，请联系辅导员或心理老师寻求现实支持。"}'
    "不要使用 role、name、type 等其他字段名。"
    "语言要温和、具体、可执行。"
)

REVIEW_SYSTEM_PROMPT = (
    "你是“舍友心晴”AI 沟通复盘助手。本任务是 communication review，"
    "帮助用户复盘大学宿舍关系沟通场景中的表达方式。"
    f"{SAFETY_BOUNDARY_TEXT}"
    "请输出结构化 ReviewResponse，包括 summary、strengths、risks、"
    "performance_scores、rewritten_message、next_steps 和 safety_note。"
    "performance_scores 是表现总结评分，必须包含 clarity、empathy、resolution 三个字段，"
    "分别表示表达清晰度、共情能力、问题解决度，值必须是 0-100 的整数。"
    "safety_note 必须包含：仅用于沟通训练建议、不代表真实舍友想法、"
    "不进行心理诊断或不进行心理疾病诊断、不进行医学判断、不进行人格评价、"
    "辅导员或心理老师或现实支持。"
    "请只输出一个合法 JSON object，不要输出 Markdown、解释或额外文本。"
    "JSON 必须严格使用以下字段结构："
    '{"summary":"一句话概括用户表达方式","strengths":["具体优点"],'
    '"risks":["需要避免的沟通风险"],'
    '"performance_scores":{"clarity":80,"empathy":75,"resolution":70},'
    '"rewritten_message":"更温和、具体、可执行的改写话术",'
    '"next_steps":["下一步现实沟通建议"],'
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


def build_simulate_messages(request: SimulateRequest) -> list[BaseMessage]:
    """把模拟请求拆成 LangChain system/human 两类消息。"""
    context = request.context if request.context is not None else "无补充背景"
    risk_level = request.risk_level if request.risk_level is not None else "未提供"
    dialogue_lines = "\n".join(
        f"{message.speaker}: {message.message}" for message in request.dialogue
    )
    dialogue_text = dialogue_lines if dialogue_lines else "无历史对话"
    human_prompt = (
        "请基于以下用户输入生成三位固定舍友角色的结构化回复。\n"
        "如果 dialogue 非空，请把本次 user_message 视为同一场景下的下一轮对话，"
        "不要重启场景，不要重复上一轮已经说过的内容。\n"
        f"scenario: {request.scenario}\n"
        f"dialogue:\n{dialogue_text}\n"
        f"user_message: {request.user_message}\n"
        f"risk_level: {risk_level}\n"
        f"context: {context}"
    )

    return [SystemMessage(content=SIMULATE_SYSTEM_PROMPT), HumanMessage(content=human_prompt)]


def build_review_messages(request: ReviewRequest) -> list[BaseMessage]:
    """把复盘请求拆成 LangChain system/human 两类消息。"""
    dialogue_lines = "\n".join(
        f"{message.speaker}: {message.message}" for message in request.dialogue
    )
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
        f"scenario: {request.scenario}\n"
        f"dialogue:\n{dialogue_lines}\n"
        f"original_event: {original_event}"
    )

    return [SystemMessage(content=REVIEW_SYSTEM_PROMPT), HumanMessage(content=human_prompt)]


def build_archive_insight_messages(
    events: list[EventRecord],
    analysis: ArchiveAnalysisResponse,
) -> list[BaseMessage]:
    """把事件档案和总压力分析拆成 LangChain 消息。"""
    serialized_events = json.dumps(
        [
            event.model_dump(
                include=ARCHIVE_INSIGHT_EVENT_FIELDS,
                mode="json",
            )
            for event in events
        ],
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
