import pytest

from app.training_catalog import (
    build_opening_suggestion,
    build_training_catalog_response,
    get_category,
    get_difficulty,
    get_scenario,
    get_target,
    scenarios_for_category,
)


EXPECTED_CATEGORIES = [
    {"id": "noise", "label": "噪音冲突"},
    {"id": "schedule", "label": "作息冲突"},
    {"id": "hygiene", "label": "卫生冲突"},
    {"id": "cost", "label": "费用冲突"},
    {"id": "privacy", "label": "隐私边界"},
    {"id": "emotion", "label": "情绪冲突"},
]

EXPECTED_SCENARIOS = [
    {"category_id": "noise", "id": "noise_game_night", "title": "晚上打游戏声音太大"},
    {"category_id": "noise", "id": "noise_video_noon", "title": "午休时外放短视频"},
    {"category_id": "schedule", "id": "schedule_lights_out_chat", "title": "熄灯后还在聊天"},
    {"category_id": "schedule", "id": "schedule_morning_wash", "title": "早起洗漱声音太大"},
    {"category_id": "hygiene", "id": "hygiene_trash", "title": "垃圾很久没人倒"},
    {"category_id": "hygiene", "id": "hygiene_shared_desk", "title": "公共桌面长期杂乱"},
    {"category_id": "cost", "id": "cost_utility_split", "title": "水电费分摊不清"},
    {"category_id": "cost", "id": "cost_public_items", "title": "公共用品总是一个人买"},
    {"category_id": "privacy", "id": "privacy_borrow_items", "title": "舍友未经允许拿东西"},
    {"category_id": "privacy", "id": "privacy_visitors", "title": "舍友经常带朋友进宿舍"},
    {"category_id": "emotion", "id": "emotion_cold_war", "title": "争吵后冷战"},
    {"category_id": "emotion", "id": "emotion_tone_uncomfortable", "title": "对方说话语气让人不舒服"},
]

EXPECTED_TARGETS = [
    {"id": "express_feeling", "label": "表达感受"},
    {"id": "make_request", "label": "提出请求"},
    {"id": "negotiate_rule", "label": "协商规则"},
    {"id": "respond_objection", "label": "回应反驳"},
    {"id": "repair_relationship", "label": "缓和关系"},
]

EXPECTED_DIFFICULTIES = [
    {"id": "beginner", "label": "初级", "description": "1位温和舍友，适合第一次练习"},
    {"id": "intermediate", "label": "中级", "description": "2位舍友会解释或轻微反驳"},
    {
        "id": "advanced",
        "label": "高级",
        "description": "4位舍友会固执反驳、责任转移、冷处理或表面答应不承诺",
    },
    {
        "id": "challenge",
        "label": "挑战",
        "description": "5位舍友多人反问、站队、推诿、冷处理和责任转移交织",
    },
]


def test_training_catalog_matches_canonical_v4_contract():
    catalog = build_training_catalog_response()

    assert [category.model_dump() for category in catalog.categories] == EXPECTED_CATEGORIES
    assert [scenario.model_dump() for scenario in catalog.scenarios] == EXPECTED_SCENARIOS
    assert [target.model_dump() for target in catalog.targets] == EXPECTED_TARGETS
    assert [difficulty.model_dump() for difficulty in catalog.difficulties] == EXPECTED_DIFFICULTIES

    assert len(catalog.scenarios) == 12
    assert len(catalog.targets) == 5
    assert len(catalog.difficulties) == 4
    assert [category.id for category in catalog.categories] == [
        "noise",
        "schedule",
        "hygiene",
        "cost",
        "privacy",
        "emotion",
    ]


def test_each_training_scenario_references_an_existing_category():
    catalog = build_training_catalog_response()
    category_ids = {category.id for category in catalog.categories}

    assert all(scenario.category_id in category_ids for scenario in catalog.scenarios)


def test_training_catalog_lookup_helpers_return_expected_items():
    assert get_category("noise").model_dump() == EXPECTED_CATEGORIES[0]
    assert get_scenario("noise_game_night").model_dump() == EXPECTED_SCENARIOS[0]
    assert get_target("express_feeling").model_dump() == EXPECTED_TARGETS[0]
    assert get_difficulty("beginner").model_dump() == EXPECTED_DIFFICULTIES[0]
    assert [scenario.id for scenario in scenarios_for_category("noise")] == [
        "noise_game_night",
        "noise_video_noon",
    ]


def test_build_opening_suggestion_is_deterministic_mild_and_concrete():
    first = build_opening_suggestion(
        "noise",
        "noise_game_night",
        "express_feeling",
        "beginner",
    )
    second = build_opening_suggestion(
        "noise",
        "noise_game_night",
        "express_feeling",
        "beginner",
    )

    assert first == second
    assert first.strip()
    assert "晚上打游戏声音太大" in first
    assert "表达感受" in first
    assert "有点影响" in first
    assert "声音" in first
    assert "小一点" in first or "调低" in first
    assert "诊断" not in first


@pytest.mark.parametrize(
    ("helper", "invalid_id"),
    [
        (get_category, "missing_category"),
        (get_scenario, "missing_scenario"),
        (get_target, "missing_target"),
        (get_difficulty, "missing_difficulty"),
        (scenarios_for_category, "missing_category"),
    ],
)
def test_training_catalog_helpers_raise_value_error_for_invalid_ids(helper, invalid_id):
    with pytest.raises(ValueError):
        helper(invalid_id)


def test_build_opening_suggestion_raises_value_error_for_invalid_ids():
    with pytest.raises(ValueError):
        build_opening_suggestion(
            "missing_category",
            "noise_game_night",
            "express_feeling",
            "beginner",
        )

    with pytest.raises(ValueError):
        build_opening_suggestion(
            "noise",
            "missing_scenario",
            "express_feeling",
            "beginner",
        )

    with pytest.raises(ValueError):
        build_opening_suggestion(
            "noise",
            "noise_game_night",
            "missing_target",
            "beginner",
        )

    with pytest.raises(ValueError):
        build_opening_suggestion(
            "noise",
            "noise_game_night",
            "express_feeling",
            "missing_difficulty",
        )
