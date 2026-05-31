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
    id: 'roommate_advanced_direct',
    name: '舍友 A',
    personality_tag: '直接表达型',
    tag_mode: 'custom',
    avatar: 'nailong',
    traits: {
      directness: 5,
      emotional_reactivity: 3,
      avoidance: 1,
      empathy: 2,
      solution_willingness: 3,
      boundary_sensitivity: 4,
    },
  },
  {
    id: 'roommate_advanced_avoidant',
    name: '舍友 B',
    personality_tag: '回避拖延型',
    tag_mode: 'custom',
    avatar: 'capybara_lulu',
    traits: {
      directness: 1,
      emotional_reactivity: 2,
      avoidance: 5,
      empathy: 2,
      solution_willingness: 1,
      boundary_sensitivity: 3,
    },
  },
  {
    id: 'roommate_advanced_boundary_deflect',
    name: '舍友 C',
    personality_tag: '边界强/推卸型',
    tag_mode: 'custom',
    avatar: 'baobaolong',
    traits: {
      directness: 4,
      emotional_reactivity: 3,
      avoidance: 3,
      empathy: 1,
      solution_willingness: 2,
      boundary_sensitivity: 5,
    },
  },
]

const challengeRoommates: RoommateProfile[] = [
  {
    id: 'roommate_challenge_questioner',
    name: '舍友 A',
    personality_tag: '直接质疑型',
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
    id: 'roommate_challenge_avoidant',
    name: '舍友 B',
    personality_tag: '回避转移型',
    tag_mode: 'custom',
    avatar: 'capybara_lulu',
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
    id: 'roommate_challenge_deflector',
    name: '舍友 C',
    personality_tag: '推卸责任型',
    tag_mode: 'custom',
    avatar: 'baobaolong',
    traits: {
      directness: 4,
      emotional_reactivity: 4,
      avoidance: 4,
      empathy: 1,
      solution_willingness: 1,
      boundary_sensitivity: 4,
    },
  },
  {
    id: 'roommate_challenge_mediator',
    name: '舍友 D',
    personality_tag: '调停缓和型',
    tag_mode: 'custom',
    avatar: 'patrick',
    traits: {
      directness: 3,
      emotional_reactivity: 1,
      avoidance: 1,
      empathy: 5,
      solution_willingness: 5,
      boundary_sensitivity: 3,
    },
  },
  {
    id: 'roommate_challenge_pragmatic',
    name: '舍友 E',
    personality_tag: '现实补充型',
    tag_mode: 'custom',
    avatar: 'spongebob',
    traits: {
      directness: 3,
      emotional_reactivity: 2,
      avoidance: 2,
      empathy: 3,
      solution_willingness: 3,
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
    '难度策略：高级，3 位虚拟舍友参与；直接型、回避型、边界强/推卸型更明显，提高角色强度和对话复杂度。保持安全边界，不输出攻击、羞辱、操控或人格评价。',
  challenge:
    '难度策略：挑战，4-5 位虚拟舍友参与，明确体现多人复杂度；允许出现直接质疑、回避、推卸、调停等交织回应，但仍禁止攻击、羞辱、操控、人格评价、威胁或歧视，只提高沟通复杂度，不降低安全边界。',
}

const replyPolicyByDifficulty: Record<TrainingDifficultyId, ScenarioReplyPolicy> = {
  beginner: { min: 1, max: 2 },
  intermediate: { min: 2, max: 4 },
  advanced: { min: 3, max: 5 },
  challenge: { min: 4, max: 7 },
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
