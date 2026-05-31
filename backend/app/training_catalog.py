"""V4 沟通训练固定目录和目录查询 helper。"""

from app.schemas import (
    TrainingCatalogResponse,
    TrainingCategory,
    TrainingDifficulty,
    TrainingScenario,
    TrainingTarget,
)


CATEGORIES: tuple[TrainingCategory, ...] = (
    TrainingCategory(id="noise", label="噪音冲突"),
    TrainingCategory(id="schedule", label="作息冲突"),
    TrainingCategory(id="hygiene", label="卫生冲突"),
    TrainingCategory(id="cost", label="费用冲突"),
    TrainingCategory(id="privacy", label="隐私边界"),
    TrainingCategory(id="emotion", label="情绪冲突"),
)

SCENARIOS: tuple[TrainingScenario, ...] = (
    TrainingScenario(
        category_id="noise",
        id="noise_game_night",
        title="晚上打游戏声音太大",
    ),
    TrainingScenario(
        category_id="noise",
        id="noise_video_noon",
        title="午休时外放短视频",
    ),
    TrainingScenario(
        category_id="schedule",
        id="schedule_lights_out_chat",
        title="熄灯后还在聊天",
    ),
    TrainingScenario(
        category_id="schedule",
        id="schedule_morning_wash",
        title="早起洗漱声音太大",
    ),
    TrainingScenario(
        category_id="hygiene",
        id="hygiene_trash",
        title="垃圾很久没人倒",
    ),
    TrainingScenario(
        category_id="hygiene",
        id="hygiene_shared_desk",
        title="公共桌面长期杂乱",
    ),
    TrainingScenario(
        category_id="cost",
        id="cost_utility_split",
        title="水电费分摊不清",
    ),
    TrainingScenario(
        category_id="cost",
        id="cost_public_items",
        title="公共用品总是一个人买",
    ),
    TrainingScenario(
        category_id="privacy",
        id="privacy_borrow_items",
        title="舍友未经允许拿东西",
    ),
    TrainingScenario(
        category_id="privacy",
        id="privacy_visitors",
        title="舍友经常带朋友进宿舍",
    ),
    TrainingScenario(
        category_id="emotion",
        id="emotion_cold_war",
        title="争吵后冷战",
    ),
    TrainingScenario(
        category_id="emotion",
        id="emotion_tone_uncomfortable",
        title="对方说话语气让人不舒服",
    ),
)

TARGETS: tuple[TrainingTarget, ...] = (
    TrainingTarget(id="express_feeling", label="表达感受"),
    TrainingTarget(id="make_request", label="提出请求"),
    TrainingTarget(id="negotiate_rule", label="协商规则"),
    TrainingTarget(id="respond_objection", label="回应反驳"),
    TrainingTarget(id="repair_relationship", label="缓和关系"),
)

DIFFICULTIES: tuple[TrainingDifficulty, ...] = (
    TrainingDifficulty(
        id="beginner",
        label="初级",
        description="1位温和舍友，适合第一次练习",
    ),
    TrainingDifficulty(
        id="intermediate",
        label="中级",
        description="2位舍友会解释或轻微反驳",
    ),
    TrainingDifficulty(
        id="advanced",
        label="高级",
        description="4位舍友会固执反驳、责任转移、冷处理或表面答应不承诺",
    ),
    TrainingDifficulty(
        id="challenge",
        label="挑战",
        description="5位舍友多人反问、站队、推诿、冷处理和责任转移交织",
    ),
)

_SCENARIO_REQUEST_DIRECTIONS: dict[str, str] = {
    "noise_game_night": "把游戏声音调低一点，或者在晚上休息时段戴上耳机",
    "noise_video_noon": "午休时把外放声音关小，或者改用耳机",
    "schedule_lights_out_chat": "熄灯后把聊天移到宿舍外，或者降低音量",
    "schedule_morning_wash": "早起洗漱时尽量轻一点，并提前整理会发出声音的物品",
    "hygiene_trash": "今天先一起把垃圾带下去，再约定之后的轮值方式",
    "hygiene_shared_desk": "一起把公共桌面清出来，并约定用完后及时归位",
    "cost_utility_split": "把账单和分摊方式对齐清楚，再按大家认可的规则结算",
    "cost_public_items": "公共用品先记账或轮流购买，避免总是由一个人承担",
    "privacy_borrow_items": "以后拿东西前先问一声，得到同意后再使用",
    "privacy_visitors": "带朋友来宿舍前提前说一声，并避开大家休息或学习时间",
    "emotion_cold_war": "找一个不急的时候先恢复沟通，把这次不舒服的点说开",
    "emotion_tone_uncomfortable": "说话时尽量放缓语气，也给彼此一点解释空间",
}


def get_category(category_id: str) -> TrainingCategory:
    """按 ID 读取训练类别，无效 ID 抛出 ValueError。"""
    for category in CATEGORIES:
        if category.id == category_id:
            return category
    raise ValueError(f"Unknown training category id: {category_id}")


def get_scenario(scenario_id: str) -> TrainingScenario:
    """按 ID 读取训练场景，无效 ID 抛出 ValueError。"""
    for scenario in SCENARIOS:
        if scenario.id == scenario_id:
            return scenario
    raise ValueError(f"Unknown training scenario id: {scenario_id}")


def get_target(target_id: str) -> TrainingTarget:
    """按 ID 读取训练目标，无效 ID 抛出 ValueError。"""
    for target in TARGETS:
        if target.id == target_id:
            return target
    raise ValueError(f"Unknown training target id: {target_id}")


def get_difficulty(difficulty_id: str) -> TrainingDifficulty:
    """按 ID 读取训练难度，无效 ID 抛出 ValueError。"""
    for difficulty in DIFFICULTIES:
        if difficulty.id == difficulty_id:
            return difficulty
    raise ValueError(f"Unknown training difficulty id: {difficulty_id}")


def scenarios_for_category(category_id: str) -> list[TrainingScenario]:
    """返回某个类别下的全部训练场景。"""
    get_category(category_id)
    return [scenario for scenario in SCENARIOS if scenario.category_id == category_id]


def build_opening_suggestion(
    category_id: str,
    scenario_id: str,
    target_id: str,
    difficulty_id: str,
) -> str:
    """生成确定性的温和开场建议；仅用于沟通训练，不做诊断。"""
    category = get_category(category_id)
    scenario = get_scenario(scenario_id)
    target = get_target(target_id)
    difficulty = get_difficulty(difficulty_id)
    if scenario.category_id != category.id:
        raise ValueError(
            f"Scenario {scenario_id} does not belong to category {category_id}"
        )

    request_direction = _SCENARIO_REQUEST_DIRECTIONS[scenario.id]
    return (
        f"可以试着这样开场：我想围绕“{scenario.title}”这件事练习“{target.label}”。"
        f"最近它有点影响我的休息和状态，想和你温和地对齐一下。"
        f"能不能麻烦你{request_direction}？"
        f"这次按“{difficulty.label}”难度来练，先把具体感受和请求说清楚。"
    )


def build_training_catalog_response() -> TrainingCatalogResponse:
    """构建 V4 固定训练目录响应。"""
    return TrainingCatalogResponse(
        categories=list(CATEGORIES),
        scenarios=list(SCENARIOS),
        targets=list(TARGETS),
        difficulties=list(DIFFICULTIES),
    )
