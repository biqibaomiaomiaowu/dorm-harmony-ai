import type {
  TrainingDifficultyId,
  TrainingScenarioId,
  TrainingTargetId,
} from '@/data/trainingCatalog'

export interface TrainingScenarioUiMeta {
  scenario_id: TrainingScenarioId
  headline: string
  resistance: string
  focus: string
  suggested_target_ids: TrainingTargetId[]
  suggested_difficulty_ids: TrainingDifficultyId[]
  complexity: 1 | 2 | 3 | 4 | 5
  tags: string[]
}

const trainingScenarioUiMetaById: Record<TrainingScenarioId, TrainingScenarioUiMeta> = {
  noise_game_night: {
    scenario_id: 'noise_game_night',
    headline: '晚间休息边界',
    resistance: '对方可能强调自己只是放松，或觉得音量没那么大。',
    focus: '把休息影响说具体，并提出耳机或时间段方案。',
    suggested_target_ids: ['express_feeling', 'make_request', 'respond_objection'],
    suggested_difficulty_ids: ['beginner', 'intermediate', 'advanced'],
    complexity: 3,
    tags: ['噪音', '休息', '边界'],
  },
  noise_video_noon: {
    scenario_id: 'noise_video_noon',
    headline: '午休安静需求',
    resistance: '对方可能解释只是刷一会儿，或认为白天不用太安静。',
    focus: '说明午休恢复的重要性，把请求落到音量和耳机选择。',
    suggested_target_ids: ['express_feeling', 'make_request'],
    suggested_difficulty_ids: ['beginner', 'intermediate'],
    complexity: 2,
    tags: ['噪音', '午休', '请求'],
  },
  schedule_lights_out_chat: {
    scenario_id: 'schedule_lights_out_chat',
    headline: '熄灯后的共同规则',
    resistance: '对方可能觉得聊天不算吵，或说大家都偶尔这样。',
    focus: '把熄灯规则和实际影响分开讲，推动形成可执行约定。',
    suggested_target_ids: ['negotiate_rule', 'respond_objection'],
    suggested_difficulty_ids: ['intermediate', 'advanced', 'challenge'],
    complexity: 5,
    tags: ['作息', '规则', '多人'],
  },
  schedule_morning_wash: {
    scenario_id: 'schedule_morning_wash',
    headline: '早起动线协调',
    resistance: '对方可能说自己已经很赶，难以完全避免声音。',
    focus: '承认对方时间压力，同时协商提前准备和降低噪音。',
    suggested_target_ids: ['make_request', 'negotiate_rule'],
    suggested_difficulty_ids: ['beginner', 'intermediate'],
    complexity: 3,
    tags: ['作息', '早起', '协调'],
  },
  hygiene_trash: {
    scenario_id: 'hygiene_trash',
    headline: '垃圾轮值恢复',
    resistance: '对方可能说不是自己丢的，或把责任推给其他人。',
    focus: '避免追责升级，先解决当前垃圾，再约定轮值方式。',
    suggested_target_ids: ['negotiate_rule', 'respond_objection'],
    suggested_difficulty_ids: ['intermediate', 'advanced', 'challenge'],
    complexity: 5,
    tags: ['卫生', '责任', '轮值'],
  },
  hygiene_shared_desk: {
    scenario_id: 'hygiene_shared_desk',
    headline: '公共桌面归位',
    resistance: '对方可能认为只是临时放置，或不觉得影响公共使用。',
    focus: '把公共区域的使用权说清楚，协商用后归位标准。',
    suggested_target_ids: ['make_request', 'negotiate_rule'],
    suggested_difficulty_ids: ['beginner', 'intermediate', 'advanced'],
    complexity: 3,
    tags: ['卫生', '公共空间', '秩序'],
  },
  cost_utility_split: {
    scenario_id: 'cost_utility_split',
    headline: '费用分摊透明',
    resistance: '对方可能质疑账单、算法或自己是否应该承担。',
    focus: '把账单证据、分摊规则和结算时间讲清楚。',
    suggested_target_ids: ['negotiate_rule', 'respond_objection'],
    suggested_difficulty_ids: ['intermediate', 'advanced', 'challenge'],
    complexity: 5,
    tags: ['费用', '账单', '规则'],
  },
  cost_public_items: {
    scenario_id: 'cost_public_items',
    headline: '公共用品公平购买',
    resistance: '对方可能觉得金额小，或默认有人顺手买。',
    focus: '把长期累积的不公平说出来，提出记账或轮流购买。',
    suggested_target_ids: ['express_feeling', 'negotiate_rule'],
    suggested_difficulty_ids: ['beginner', 'intermediate', 'advanced'],
    complexity: 3,
    tags: ['费用', '公共用品', '公平'],
  },
  privacy_borrow_items: {
    scenario_id: 'privacy_borrow_items',
    headline: '私人物品同意边界',
    resistance: '对方可能觉得关系熟所以不用每次问。',
    focus: '明确不是拒绝帮助，而是需要先征得同意。',
    suggested_target_ids: ['express_feeling', 'make_request', 'respond_objection'],
    suggested_difficulty_ids: ['intermediate', 'advanced', 'challenge'],
    complexity: 5,
    tags: ['隐私', '物品', '同意'],
  },
  privacy_visitors: {
    scenario_id: 'privacy_visitors',
    headline: '访客提前告知',
    resistance: '对方可能认为带朋友是个人自由，或临时来不及通知。',
    focus: '平衡对方社交需求和宿舍成员的休息学习边界。',
    suggested_target_ids: ['negotiate_rule', 'respond_objection'],
    suggested_difficulty_ids: ['intermediate', 'advanced', 'challenge'],
    complexity: 5,
    tags: ['隐私', '访客', '边界'],
  },
  emotion_cold_war: {
    scenario_id: 'emotion_cold_war',
    headline: '冷战后的复沟通',
    resistance: '对方可能继续回避，或只给很短的回应。',
    focus: '降低开场压力，先恢复可对话状态，再谈具体事件。',
    suggested_target_ids: ['repair_relationship', 'express_feeling'],
    suggested_difficulty_ids: ['beginner', 'intermediate', 'advanced'],
    complexity: 3,
    tags: ['情绪', '冷处理', '修复'],
  },
  emotion_tone_uncomfortable: {
    scenario_id: 'emotion_tone_uncomfortable',
    headline: '语气不适的表达',
    resistance: '对方可能说自己没有恶意，或认为你太敏感。',
    focus: '用具体话语和感受描述影响，请求更平和的表达方式。',
    suggested_target_ids: ['express_feeling', 'make_request', 'repair_relationship'],
    suggested_difficulty_ids: ['beginner', 'intermediate', 'advanced'],
    complexity: 3,
    tags: ['情绪', '语气', '修复'],
  },
}

export function getTrainingScenarioUiMeta(
  scenarioId: TrainingScenarioId,
): TrainingScenarioUiMeta {
  return trainingScenarioUiMetaById[scenarioId]
}
