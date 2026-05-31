import type { TrainingDifficultyId } from '@/data/trainingCatalog'
import type { RoommateProfile, RoommateTraits } from '@/data/week1'

export interface ScenarioReplyPolicy {
  min: number
  max: number
}

type ScenarioDifficultyInput = TrainingDifficultyId | undefined

const beginnerRoommates: RoommateProfile[] = [
  {
    id: 'roommate_beginner_listener',
    name: '舍友 A',
    personality_tag: '温和倾听型',
    tag_mode: 'custom',
    avatar: 'nailong',
    traits: {
      directness: 2,
      emotional_reactivity: 1,
      avoidance: 1,
      empathy: 5,
      solution_willingness: 5,
      boundary_sensitivity: 3,
    },
  },
]

const intermediateRoommates: RoommateProfile[] = [
  {
    id: 'roommate_intermediate_explainer',
    name: '舍友 A',
    personality_tag: '解释型',
    tag_mode: 'custom',
    avatar: 'nailong',
    traits: {
      directness: 3,
      emotional_reactivity: 2,
      avoidance: 2,
      empathy: 3,
      solution_willingness: 3,
      boundary_sensitivity: 3,
    },
  },
  {
    id: 'roommate_intermediate_mild_objection',
    name: '舍友 B',
    personality_tag: '轻微反驳型',
    tag_mode: 'custom',
    avatar: 'capybara_lulu',
    traits: {
      directness: 4,
      emotional_reactivity: 2,
      avoidance: 1,
      empathy: 2,
      solution_willingness: 2,
      boundary_sensitivity: 4,
    },
  },
]

const advancedRoommates: RoommateProfile[] = [
  {
    id: 'roommate_advanced_stubborn_objection',
    name: '舍友 A',
    personality_tag: '固执反驳型',
    tag_mode: 'custom',
    avatar: 'nailong',
    traits: {
      directness: 5,
      emotional_reactivity: 4,
      avoidance: 1,
      empathy: 1,
      solution_willingness: 1,
      boundary_sensitivity: 5,
    },
  },
  {
    id: 'roommate_advanced_responsibility_shift',
    name: '舍友 B',
    personality_tag: '责任转移型',
    tag_mode: 'custom',
    avatar: 'capybara_lulu',
    traits: {
      directness: 4,
      emotional_reactivity: 3,
      avoidance: 4,
      empathy: 1,
      solution_willingness: 1,
      boundary_sensitivity: 4,
    },
  },
  {
    id: 'roommate_advanced_cold_delay',
    name: '舍友 C',
    personality_tag: '冷处理拖延型',
    tag_mode: 'custom',
    avatar: 'baobaolong',
    traits: {
      directness: 1,
      emotional_reactivity: 2,
      avoidance: 5,
      empathy: 1,
      solution_willingness: 1,
      boundary_sensitivity: 3,
    },
  },
  {
    id: 'roommate_advanced_surface_agree',
    name: '舍友 D',
    personality_tag: '表面答应不承诺型',
    tag_mode: 'custom',
    avatar: 'patrick',
    traits: {
      directness: 2,
      emotional_reactivity: 2,
      avoidance: 4,
      empathy: 2,
      solution_willingness: 1,
      boundary_sensitivity: 3,
    },
  },
]

const challengeRoommates: RoommateProfile[] = [
  {
    id: 'roommate_challenge_forceful_objection',
    name: '舍友 A',
    personality_tag: '强势反驳型',
    tag_mode: 'custom',
    avatar: 'nailong',
    traits: {
      directness: 5,
      emotional_reactivity: 4,
      avoidance: 1,
      empathy: 1,
      solution_willingness: 2,
      boundary_sensitivity: 5,
    },
  },
  {
    id: 'roommate_challenge_passive_aggressive',
    name: '舍友 B',
    personality_tag: '阴阳怪气型',
    tag_mode: 'custom',
    avatar: 'capybara_lulu',
    traits: {
      directness: 4,
      emotional_reactivity: 4,
      avoidance: 2,
      empathy: 1,
      solution_willingness: 1,
      boundary_sensitivity: 5,
    },
  },
  {
    id: 'roommate_challenge_cold_avoidance',
    name: '舍友 C',
    personality_tag: '冷处理回避型',
    tag_mode: 'custom',
    avatar: 'baobaolong',
    traits: {
      directness: 1,
      emotional_reactivity: 3,
      avoidance: 5,
      empathy: 1,
      solution_willingness: 1,
      boundary_sensitivity: 3,
    },
  },
  {
    id: 'roommate_challenge_group_siding',
    name: '舍友 D',
    personality_tag: '拉群站队型',
    tag_mode: 'custom',
    avatar: 'patrick',
    traits: {
      directness: 5,
      emotional_reactivity: 4,
      avoidance: 2,
      empathy: 1,
      solution_willingness: 1,
      boundary_sensitivity: 5,
    },
  },
  {
    id: 'roommate_challenge_responsibility_shift',
    name: '舍友 E',
    personality_tag: '责任转移型',
    tag_mode: 'custom',
    avatar: 'spongebob',
    traits: {
      directness: 4,
      emotional_reactivity: 4,
      avoidance: 4,
      empathy: 1,
      solution_willingness: 1,
      boundary_sensitivity: 4,
    },
  },
]

const roommatePolicyByDifficulty: Record<TrainingDifficultyId, RoommateProfile[]> = {
  beginner: beginnerRoommates,
  intermediate: intermediateRoommates,
  advanced: advancedRoommates,
  challenge: challengeRoommates,
}

const difficultyContextById: Record<TrainingDifficultyId, string> = {
  beginner:
    '难度策略：初级，仅 1 位虚拟舍友参与；对方温和、愿意听，反驳弱，适合第一次练习表达。保持安全边界，不输出攻击、羞辱、操控或人格评价。',
  intermediate:
    '难度策略：中级，2 位虚拟舍友参与；一位偏解释型，一位轻微反驳型，让用户练习澄清请求和回应小幅异议。保持安全边界，不输出攻击、羞辱、操控或人格评价。',
  advanced:
    '难度策略：高级，4 位虚拟舍友参与；固执反驳、责任转移、冷处理拖延、表面答应不承诺并存，提高角色强度和对话复杂度。保持安全边界，不输出辱骂、威胁、羞辱、歧视、操控或人格评价。',
  challenge:
    '难度策略：挑战，5 位虚拟舍友参与，明确体现多人反问、站队、推诿、冷处理、转移责任交织；不得输出辱骂、威胁、羞辱、歧视、操控或人格评价，只提高沟通复杂度，不降低安全边界。',
}

const difficultyPressureProfileById: Record<TrainingDifficultyId, string> = {
  beginner: '1 位温和舍友低压回应，主要练习把感受和请求说完整。',
  intermediate: '2 位舍友带来解释和轻微反驳，压力来自澄清事实与回应小幅异议。',
  advanced: '4 位舍友分别固执反驳、责任转移、冷处理拖延、表面答应不承诺，压力来自持续追问、边界确认和具体承诺。',
  challenge:
    '5 位舍友将多人反问、站队、推诿、冷处理、转移责任交织出现，压力来自同时保持表达清晰、边界稳定和安全沟通。',
}

const replyPolicyByDifficulty: Record<TrainingDifficultyId, ScenarioReplyPolicy> = {
  beginner: { min: 1, max: 2 },
  intermediate: { min: 2, max: 4 },
  advanced: { min: 4, max: 7 },
  challenge: { min: 6, max: 10 },
}

function normalizeDifficultyId(difficultyId: ScenarioDifficultyInput): TrainingDifficultyId {
  return difficultyId ?? 'beginner'
}

function cloneTraits(traits: RoommateTraits): RoommateTraits {
  return { ...traits }
}

function cloneRoommate(roommate: RoommateProfile): RoommateProfile {
  return {
    ...roommate,
    traits: cloneTraits(roommate.traits),
  }
}

export function buildScenarioTrainingRoommates(
  difficultyId: ScenarioDifficultyInput,
): RoommateProfile[] {
  return roommatePolicyByDifficulty[normalizeDifficultyId(difficultyId)].map(cloneRoommate)
}

export function buildScenarioDifficultyContext(difficultyId: ScenarioDifficultyInput): string {
  return difficultyContextById[normalizeDifficultyId(difficultyId)]
}

export function getScenarioReplyPolicy(difficultyId: ScenarioDifficultyInput): ScenarioReplyPolicy {
  return { ...replyPolicyByDifficulty[normalizeDifficultyId(difficultyId)] }
}

export function summarizeScenarioRoommates(roommates: RoommateProfile[]): string {
  return roommates.map((roommate) => `${roommate.name}（${roommate.personality_tag}）`).join('、')
}

export function getScenarioDifficultyPressureProfile(
  difficultyId: ScenarioDifficultyInput,
): string {
  return difficultyPressureProfileById[normalizeDifficultyId(difficultyId)]
}
