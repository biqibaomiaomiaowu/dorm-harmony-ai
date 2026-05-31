import type { RehearsalSourceMeta } from '@/data/week1'

export type TrainingCategoryId = 'noise' | 'schedule' | 'hygiene' | 'cost' | 'privacy' | 'emotion'

export type TrainingScenarioId =
  | 'noise_game_night'
  | 'noise_video_noon'
  | 'schedule_lights_out_chat'
  | 'schedule_morning_wash'
  | 'hygiene_trash'
  | 'hygiene_shared_desk'
  | 'cost_utility_split'
  | 'cost_public_items'
  | 'privacy_borrow_items'
  | 'privacy_visitors'
  | 'emotion_cold_war'
  | 'emotion_tone_uncomfortable'

export type TrainingTargetId =
  | 'express_feeling'
  | 'make_request'
  | 'negotiate_rule'
  | 'respond_objection'
  | 'repair_relationship'

export type TrainingDifficultyId = 'beginner' | 'intermediate' | 'advanced' | 'challenge'

export interface TrainingCategory {
  id: TrainingCategoryId
  label: string
}

export interface TrainingScenario {
  category_id: TrainingCategoryId
  id: TrainingScenarioId
  title: string
}

export interface TrainingTarget {
  id: TrainingTargetId
  label: string
}

export interface TrainingDifficulty {
  id: TrainingDifficultyId
  label: string
  description: string
}

export interface TrainingSelection {
  category_id: TrainingCategoryId
  scenario_id: TrainingScenarioId
  target_id: TrainingTargetId
  difficulty_id: TrainingDifficultyId
}

export const trainingCategories: TrainingCategory[] = [
  { id: 'noise', label: '噪音冲突' },
  { id: 'schedule', label: '作息冲突' },
  { id: 'hygiene', label: '卫生冲突' },
  { id: 'cost', label: '费用冲突' },
  { id: 'privacy', label: '隐私边界' },
  { id: 'emotion', label: '情绪冲突' },
]

export const trainingScenarios: TrainingScenario[] = [
  { category_id: 'noise', id: 'noise_game_night', title: '晚上打游戏声音太大' },
  { category_id: 'noise', id: 'noise_video_noon', title: '午休时外放短视频' },
  { category_id: 'schedule', id: 'schedule_lights_out_chat', title: '熄灯后还在聊天' },
  { category_id: 'schedule', id: 'schedule_morning_wash', title: '早起洗漱声音太大' },
  { category_id: 'hygiene', id: 'hygiene_trash', title: '垃圾很久没人倒' },
  { category_id: 'hygiene', id: 'hygiene_shared_desk', title: '公共桌面长期杂乱' },
  { category_id: 'cost', id: 'cost_utility_split', title: '水电费分摊不清' },
  { category_id: 'cost', id: 'cost_public_items', title: '公共用品总是一个人买' },
  { category_id: 'privacy', id: 'privacy_borrow_items', title: '舍友未经允许拿东西' },
  { category_id: 'privacy', id: 'privacy_visitors', title: '舍友经常带朋友进宿舍' },
  { category_id: 'emotion', id: 'emotion_cold_war', title: '争吵后冷战' },
  { category_id: 'emotion', id: 'emotion_tone_uncomfortable', title: '对方说话语气让人不舒服' },
]

export const trainingTargets: TrainingTarget[] = [
  { id: 'express_feeling', label: '表达感受' },
  { id: 'make_request', label: '提出请求' },
  { id: 'negotiate_rule', label: '协商规则' },
  { id: 'respond_objection', label: '回应反驳' },
  { id: 'repair_relationship', label: '缓和关系' },
]

export const trainingDifficulties: TrainingDifficulty[] = [
  { id: 'beginner', label: '初级', description: '1 位温和舍友，愿意听你说，反驳较弱' },
  { id: 'intermediate', label: '中级', description: '2 位舍友，一位解释，一位轻微反驳' },
  { id: 'advanced', label: '高级', description: '3 位舍友，直接、回避和边界/推卸反应更明显' },
  { id: 'challenge', label: '挑战', description: '4-5 位舍友，多人质疑、回避、推卸与调停交织' },
]

const scenarioRequestDirections: Record<TrainingScenarioId, string> = {
  noise_game_night: '把游戏声音调低一点，或者在晚上休息时段戴上耳机',
  noise_video_noon: '午休时把外放声音关小，或者改用耳机',
  schedule_lights_out_chat: '熄灯后把聊天移到宿舍外，或者降低音量',
  schedule_morning_wash: '早起洗漱时尽量轻一点，并提前整理会发出声音的物品',
  hygiene_trash: '今天先一起把垃圾带下去，再约定之后的轮值方式',
  hygiene_shared_desk: '一起把公共桌面清出来，并约定用完后及时归位',
  cost_utility_split: '把账单和分摊方式对齐清楚，再按大家认可的规则结算',
  cost_public_items: '公共用品先记账或轮流购买，避免总是由一个人承担',
  privacy_borrow_items: '以后拿东西前先问一声，得到同意后再使用',
  privacy_visitors: '带朋友来宿舍前提前说一声，并避开大家休息或学习时间',
  emotion_cold_war: '找一个不急的时候先恢复沟通，把这次不舒服的点说开',
  emotion_tone_uncomfortable: '说话时尽量放缓语气，也给彼此一点解释空间',
}

export const catalogIdSignature = [
  trainingCategories.map((item) => item.id).join(','),
  trainingScenarios.map((item) => item.id).join(','),
  trainingTargets.map((item) => item.id).join(','),
  trainingDifficulties.map((item) => item.id).join(','),
].join('|')

export function getTrainingCategory(id: string | undefined): TrainingCategory | undefined {
  return trainingCategories.find((category) => category.id === id)
}

export function getTrainingScenario(id: string | undefined): TrainingScenario | undefined {
  return trainingScenarios.find((scenario) => scenario.id === id)
}

export function getTrainingTarget(id: string | undefined): TrainingTarget | undefined {
  return trainingTargets.find((target) => target.id === id)
}

export function getTrainingDifficulty(id: string | undefined): TrainingDifficulty | undefined {
  return trainingDifficulties.find((difficulty) => difficulty.id === id)
}

export function scenariosForCategory(categoryId: string | undefined): TrainingScenario[] {
  if (!getTrainingCategory(categoryId)) {
    return []
  }

  return trainingScenarios.filter((scenario) => scenario.category_id === categoryId)
}

export function buildOpeningSuggestion(selection: Partial<TrainingSelection>): string | undefined {
  const category = getTrainingCategory(selection.category_id)
  const scenario = getTrainingScenario(selection.scenario_id)
  const target = getTrainingTarget(selection.target_id)
  const difficulty = getTrainingDifficulty(selection.difficulty_id)

  if (!category || !scenario || !target || !difficulty || scenario.category_id !== category.id) {
    return undefined
  }

  return (
    `可以试着这样开场：我想围绕“${scenario.title}”这件事练习“${target.label}”。` +
    '最近它有点影响我的休息和状态，想和你温和地对齐一下。' +
    `能不能麻烦你${scenarioRequestDirections[scenario.id]}？` +
    `这次按“${difficulty.label}”难度来练，先把具体感受和请求说清楚。`
  )
}

export function buildScenarioTrainingSourceMeta(
  selection: Partial<TrainingSelection>,
): RehearsalSourceMeta | undefined {
  const category = getTrainingCategory(selection.category_id)
  const scenario = getTrainingScenario(selection.scenario_id)
  const target = getTrainingTarget(selection.target_id)
  const difficulty = getTrainingDifficulty(selection.difficulty_id)

  if (!category || !scenario || !target || !difficulty || scenario.category_id !== category.id) {
    return undefined
  }

  return {
    mode: 'scenario_training',
    category_id: category.id,
    category_label: category.label,
    scenario_id: scenario.id,
    scenario_title: scenario.title,
    target_id: target.id,
    target_label: target.label,
    difficulty_id: difficulty.id,
    difficulty_label: difficulty.label,
    difficulty_description: difficulty.description,
  }
}
