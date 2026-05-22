export interface AnalyzeRequest {
  event_type: string
  severity: number
  frequency: string
  emotion: string
  emotions?: string[]
  primary_emotion?: string
  has_communicated: boolean
  has_conflict: boolean
  description: string
}

export type AnalyzeRiskLevel = 'stable' | 'pressure' | 'high' | 'severe'

export interface AnalyzeApiResponse {
  pressure_score: number
  risk_level: AnalyzeRiskLevel
  risk_label: string
  main_sources: string[]
  emotion_keywords: string[]
  trend_message: string
  suggestion: string
  recommend_simulation: boolean
  disclaimer: string
}

export interface AnalyzeResult {
  pressure_score: number
  risk_level: AnalyzeRiskLevel
  risk_label: string
  main_reasons: string[]
  main_sources: string[]
  emotion_keywords: string[]
  suggestion: string
  trend_message: string
  recommend_simulation: boolean
  disclaimer: string
  is_demo: boolean
  demo_notice: string
  suggestions: string[]
  safety_notice: string
  trend_notice: string
}

export const LAST_EVENT_STORAGE_KEY = 'dorm-harmony:last-event'
export const ANALYSIS_RESULT_STORAGE_KEY = 'dorm-harmony:analysis-result'
export const SIMULATION_RESULT_STORAGE_KEY = 'dorm-harmony:simulation-result'
export const REVIEW_RESULT_STORAGE_KEY = 'dorm-harmony:review-result'
export const ROOMMATE_PROFILES_STORAGE_KEY = 'dorm-harmony:roommate-profiles:v1'

export type RoommatePresetKey = 'direct' | 'avoidant' | 'harmony'
export type RoommateTagMode = 'preset' | 'custom'
export type RoommateAvatarKey = 'nailong' | 'capybara_lulu' | 'baobaolong' | 'patrick' | 'spongebob'

export interface RoommateTraits {
  directness: number
  emotional_reactivity: number
  avoidance: number
  empathy: number
  solution_willingness: number
  boundary_sensitivity: number
}

export interface RoommateProfile {
  id: string
  name: string
  personality_tag: string
  tag_mode: RoommateTagMode
  preset_key?: RoommatePresetKey
  avatar: RoommateAvatarKey
  traits: RoommateTraits
}

export type ReviewDialogueSpeaker = 'user' | 'system' | `roommate_${string}`

export interface ReviewDialogueLine {
  speaker: ReviewDialogueSpeaker
  message: string
}

export interface SimulationRequest {
  conversation_id?: string
  turn_id?: string
  scenario: string
  user_message?: string
  risk_level?: AnalyzeRiskLevel
  context?: string
  roommates?: RoommateProfile[]
  use_event_archive?: boolean
  is_continuation?: boolean
  max_replies?: number
}

export interface SimulationReply {
  roommate_id: string
  roommate: string
  personality: string
  message: string
}

export interface SimulationResponse {
  conversation_id: string
  replies: SimulationReply[]
  archive_context_used: boolean
  archive_context_summary?: string
  safety_note: string
  is_demo: boolean
  demo_notice: string
}

type SimulationResponsePayload = Omit<SimulationResponse, 'is_demo' | 'demo_notice'> &
  Partial<Pick<SimulationResponse, 'is_demo' | 'demo_notice'>>

export type SimulationStreamEvent =
  | { type: 'start'; conversation_id?: string }
  | { type: 'reply'; reply: SimulationReply }
  | { type: 'final'; response: SimulationResponsePayload }

export interface SimulationStreamHandlers {
  onStart?: (conversationId?: string) => void
  onReply?: (reply: SimulationReply) => void
}

export class SimulationStreamRequestError extends Error {
  recoverable: boolean
  status: number | null
  detail: string

  constructor(
    message: string,
    recoverable = false,
    status: number | null = null,
    detail = message,
  ) {
    super(message)
    this.name = 'SimulationStreamRequestError'
    this.recoverable = recoverable
    this.status = status
    this.detail = detail
  }
}

export class SimulationRequestError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'SimulationRequestError'
  }
}

export interface StoredSimulationResult {
  request: SimulationRequest
  response: SimulationResponse
  dialogue?: ReviewDialogueLine[]
}

export interface ReviewOriginalEvent {
  event_type?: AnalyzeRequestPayload['event_type']
  risk_level?: AnalyzeRiskLevel
  pressure_score?: number
}

export interface ReviewRewriteSuggestion {
  message_index: number
  original_message: string
  issue: string
  suggested_message: string
  reason: string
}

export interface ReviewPerformanceScores {
  clarity: number
  empathy: number
  resolution: number
}

export interface CommunicationPlan {
  opening: string
  specific_request: string
  fallback_plan: string
}

export interface ReviewResponse {
  summary: string
  strengths: string[]
  risks: string[]
  performance_scores: ReviewPerformanceScores
  rewrite_suggestions: ReviewRewriteSuggestion[]
  rewritten_message: string
  next_steps: string[]
  communication_plan: CommunicationPlan
  safety_note: string
  is_demo: boolean
  demo_notice: string
}

type ReviewResponsePayload = Omit<
  ReviewResponse,
  'performance_scores' | 'communication_plan' | 'is_demo' | 'demo_notice'
> &
  Partial<
    Pick<ReviewResponse, 'performance_scores' | 'communication_plan' | 'is_demo' | 'demo_notice'>
  >

export interface ReviewRequest {
  scenario: string
  conversation_id?: string
  dialogue?: ReviewDialogueLine[]
  original_event?: ReviewOriginalEvent
}

export interface StoredReviewResult {
  request: ReviewRequest
  response: ReviewResponse
}

type LegacyEventType =
  | 'noise_conflict'
  | 'schedule_conflict'
  | 'hygiene_conflict'
  | 'expense_conflict'
  | 'privacy_boundary'
  | 'emotional_conflict'

type LegacyFrequency = 'occasionally' | 'weekly' | 'daily'
type LegacyEmotion =
  | 'irritated'
  | 'anxious'
  | 'wronged'
  | 'angry'
  | 'helpless'
  | 'repressed'
  | 'depressed'

interface AnalyzeRequestPayload {
  event_type: 'noise' | 'schedule' | 'hygiene' | 'cost' | 'privacy' | 'emotion'
  severity: number
  frequency: 'occasional' | 'weekly_multiple' | 'daily'
  emotion: 'irritable' | 'anxious' | 'wronged' | 'angry' | 'helpless' | 'depressed'
  emotions?: Array<'irritable' | 'anxious' | 'wronged' | 'angry' | 'helpless' | 'depressed'>
  primary_emotion?: 'irritable' | 'anxious' | 'wronged' | 'angry' | 'helpless' | 'depressed'
  has_communicated: boolean
  has_conflict: boolean
  description: string
}

const EVENT_TYPE_MAP: Record<LegacyEventType, AnalyzeRequestPayload['event_type']> = {
  noise_conflict: 'noise',
  schedule_conflict: 'schedule',
  hygiene_conflict: 'hygiene',
  expense_conflict: 'cost',
  privacy_boundary: 'privacy',
  emotional_conflict: 'emotion',
}

const FREQUENCY_MAP: Record<LegacyFrequency, AnalyzeRequestPayload['frequency']> = {
  occasionally: 'occasional',
  weekly: 'weekly_multiple',
  daily: 'daily',
}

const EMOTION_MAP: Record<string, AnalyzeRequestPayload['emotion']> = {
  irritated: 'irritable',
  irritable: 'irritable',
  anxious: 'anxious',
  wronged: 'wronged',
  angry: 'angry',
  helpless: 'helpless',
  repressed: 'depressed',
  depressed: 'depressed',
  无奈: 'helpless',
  压抑: 'depressed',
}

export const roommatePresetLabels: Record<RoommatePresetKey, string> = {
  direct: '直接型',
  avoidant: '回避型',
  harmony: '调和型',
}

export const roommatePresetTraits: Record<RoommatePresetKey, RoommateTraits> = {
  direct: {
    directness: 5,
    emotional_reactivity: 3,
    avoidance: 1,
    empathy: 2,
    solution_willingness: 3,
    boundary_sensitivity: 4,
  },
  avoidant: {
    directness: 1,
    emotional_reactivity: 2,
    avoidance: 5,
    empathy: 2,
    solution_willingness: 1,
    boundary_sensitivity: 3,
  },
  harmony: {
    directness: 3,
    emotional_reactivity: 1,
    avoidance: 1,
    empathy: 5,
    solution_willingness: 5,
    boundary_sensitivity: 3,
  },
}

export const roommateTraitLabels: Record<keyof RoommateTraits, string> = {
  directness: '表达直接度',
  emotional_reactivity: '情绪反应度',
  avoidance: '回避倾向',
  empathy: '共情倾向',
  solution_willingness: '解决意愿',
  boundary_sensitivity: '边界敏感度',
}

export const roommatePresetOptions: Array<{ key: RoommatePresetKey; label: string }> = [
  { key: 'direct', label: roommatePresetLabels.direct },
  { key: 'avoidant', label: roommatePresetLabels.avoidant },
  { key: 'harmony', label: roommatePresetLabels.harmony },
]

export const roommateAvatarOptions: Array<{
  key: RoommateAvatarKey
  label: string
  shortLabel: string
}> = [
  { key: 'nailong', label: '奶龙', shortLabel: '奶' },
  { key: 'capybara_lulu', label: '水豚噜噜', shortLabel: '噜' },
  { key: 'baobaolong', label: '暴暴龙', shortLabel: '暴' },
  { key: 'patrick', label: '派大星', shortLabel: '派' },
  { key: 'spongebob', label: '海绵宝宝', shortLabel: '绵' },
]

function cloneTraits(traits: RoommateTraits): RoommateTraits {
  return { ...traits }
}

export const defaultRoommates: RoommateProfile[] = [
  {
    id: 'roommate_a',
    name: '舍友 A',
    personality_tag: roommatePresetLabels.direct,
    tag_mode: 'preset',
    preset_key: 'direct',
    avatar: 'nailong',
    traits: cloneTraits(roommatePresetTraits.direct),
  },
  {
    id: 'roommate_b',
    name: '舍友 B',
    personality_tag: roommatePresetLabels.avoidant,
    tag_mode: 'preset',
    preset_key: 'avoidant',
    avatar: 'capybara_lulu',
    traits: cloneTraits(roommatePresetTraits.avoidant),
  },
  {
    id: 'roommate_c',
    name: '舍友 C',
    personality_tag: roommatePresetLabels.harmony,
    tag_mode: 'preset',
    preset_key: 'harmony',
    avatar: 'baobaolong',
    traits: cloneTraits(roommatePresetTraits.harmony),
  },
]

export function createDefaultRoommates(): RoommateProfile[] {
  return defaultRoommates.map((roommate) => ({
    ...roommate,
    traits: cloneTraits(roommate.traits),
  }))
}

function clampTrait(value: unknown): number {
  const numberValue = Number(value)
  if (!Number.isFinite(numberValue)) {
    return 2
  }

  return Math.max(0, Math.min(5, Math.round(numberValue)))
}

function isPresetKey(value: unknown): value is RoommatePresetKey {
  return value === 'direct' || value === 'avoidant' || value === 'harmony'
}

function isRoommateAvatarKey(value: unknown): value is RoommateAvatarKey {
  return roommateAvatarOptions.some((option) => option.key === value)
}

function isRoommateTraits(value: unknown): value is RoommateTraits {
  return (
    isRecord(value) &&
    typeof value.directness === 'number' &&
    typeof value.emotional_reactivity === 'number' &&
    typeof value.avoidance === 'number' &&
    typeof value.empathy === 'number' &&
    typeof value.solution_willingness === 'number' &&
    typeof value.boundary_sensitivity === 'number'
  )
}

export function normalizeRoommates(value: unknown): RoommateProfile[] {
  if (!Array.isArray(value)) {
    return createDefaultRoommates()
  }

  const seenIds = new Set<string>()
  const seenAvatars = new Set<RoommateAvatarKey>()
  const normalized = value
    .map((item, index): RoommateProfile | null => {
      if (!isRecord(item)) {
        return null
      }

      const rawId = typeof item.id === 'string' ? item.id.trim() : ''
      const fallbackId = `roommate_custom_${index + 1}`
      const normalizedRawId = rawId.replace(/\s+/g, '_')
      const idSource = normalizedRawId || fallbackId
      const id = idSource.startsWith('roommate_') ? idSource : `roommate_${idSource}`
      if (seenIds.has(id)) {
        return null
      }
      seenIds.add(id)

      const rawName = typeof item.name === 'string' ? item.name.trim() : ''
      const name = rawName || `舍友 ${index + 1}`
      const tagMode = item.tag_mode === 'custom' ? 'custom' : 'preset'
      const presetKey = isPresetKey(item.preset_key) ? item.preset_key : 'direct'
      const rawAvatar = isRoommateAvatarKey(item.avatar) ? item.avatar : undefined
      const avatar =
        rawAvatar && !seenAvatars.has(rawAvatar)
          ? rawAvatar
          : roommateAvatarOptions.find((option) => !seenAvatars.has(option.key))?.key
      if (!avatar) {
        return null
      }
      seenAvatars.add(avatar)

      if (tagMode === 'preset') {
        return {
          id,
          name,
          personality_tag: roommatePresetLabels[presetKey],
          tag_mode: 'preset',
          preset_key: presetKey,
          avatar,
          traits: cloneTraits(roommatePresetTraits[presetKey]),
        }
      }

      const rawTag =
        typeof item.personality_tag === 'string' && item.personality_tag.trim()
          ? item.personality_tag.trim()
          : '自定义'
      const sourceTraits = isRoommateTraits(item.traits) ? item.traits : roommatePresetTraits.direct

      return {
        id,
        name,
        personality_tag: rawTag,
        tag_mode: 'custom',
        avatar,
        traits: {
          directness: clampTrait(sourceTraits.directness),
          emotional_reactivity: clampTrait(sourceTraits.emotional_reactivity),
          avoidance: clampTrait(sourceTraits.avoidance),
          empathy: clampTrait(sourceTraits.empathy),
          solution_willingness: clampTrait(sourceTraits.solution_willingness),
          boundary_sensitivity: clampTrait(sourceTraits.boundary_sensitivity),
        },
      }
    })
    .filter((roommate): roommate is RoommateProfile => roommate !== null)
    .slice(0, 5)

  if (normalized.length < 1) {
    return createDefaultRoommates()
  }

  return normalized
}

export function mapEventTypeToAnalyzeApi(
  value: string,
): AnalyzeRequestPayload['event_type'] | undefined {
  const eventType = value.trim()

  if (Object.hasOwn(EVENT_TYPE_MAP, eventType)) {
    return EVENT_TYPE_MAP[eventType as LegacyEventType]
  }

  if (
    eventType === 'noise' ||
    eventType === 'schedule' ||
    eventType === 'hygiene' ||
    eventType === 'cost' ||
    eventType === 'privacy' ||
    eventType === 'emotion'
  ) {
    return eventType
  }

  return undefined
}

export function mapRoommateToReviewSpeaker(
  roommate: string,
  roommateId?: string,
): ReviewDialogueSpeaker {
  const normalizedId = roommateId?.trim()
  if (normalizedId) {
    return normalizedId.startsWith('roommate_')
      ? (normalizedId as ReviewDialogueSpeaker)
      : (`roommate_${normalizedId}` as ReviewDialogueSpeaker)
  }

  const normalized = roommate.trim()
  const compact = normalized.replace(/\s+/g, '')

  if (
    compact === '舍友A' ||
    compact.toLowerCase() === 'roommatea' ||
    compact.toLowerCase() === 'roommate_a'
  ) {
    return 'roommate_a'
  }

  if (
    compact === '舍友B' ||
    compact.toLowerCase() === 'roommateb' ||
    compact.toLowerCase() === 'roommate_b'
  ) {
    return 'roommate_b'
  }

  if (
    compact === '舍友C' ||
    compact.toLowerCase() === 'roommatec' ||
    compact.toLowerCase() === 'roommate_c'
  ) {
    return 'roommate_c'
  }

  return 'system'
}

export const eventTypeOptions = [
  { value: 'schedule_conflict', label: '作息冲突', icon: 'schedule' },
  { value: 'hygiene_conflict', label: '卫生冲突', icon: 'cleaning_services' },
  { value: 'noise_conflict', label: '噪音冲突', icon: 'volume_up' },
  { value: 'expense_conflict', label: '费用冲突', icon: 'payments' },
  { value: 'privacy_boundary', label: '隐私边界', icon: 'visibility_off' },
  { value: 'emotional_conflict', label: '情绪冲突', icon: 'mood_bad' },
]

export const frequencyOptions = [
  { value: 'occasionally', label: '偶尔', icon: 'looks_one' },
  { value: 'weekly', label: '每周多次', icon: 'calendar_month' },
  { value: 'daily', label: '几乎每天', icon: 'event_repeat' },
]

export const emotionOptions = [
  { value: 'irritated', label: '烦躁', icon: 'sentiment_dissatisfied' },
  { value: 'anxious', label: '焦虑', icon: 'psychology' },
  { value: 'wronged', label: '委屈', icon: 'sentiment_sad' },
  { value: 'angry', label: '愤怒', icon: 'sentiment_extremely_dissatisfied' },
  { value: 'helpless', label: '无奈', icon: 'sentiment_neutral' },
  { value: 'depressed', label: '压抑', icon: 'sentiment_stressed' },
]

export const simulationScenarios = [
  '舍友晚上打游戏太吵',
  '公共卫生长期无人打扫',
  '舍友未经允许使用私人物品',
  '水电费或公共费用分摊不均',
  '作息差异导致互相影响',
  '宿舍冷战或误会修复',
]

export const defaultSimulationRequest: SimulationRequest = {
  scenario: '舍友晚上打游戏太吵',
  user_message: '你晚上能不能小声点？',
  risk_level: 'pressure',
  context: '当前场景：夜间噪音冲突',
}

export const sampleAnalyzeRequest: AnalyzeRequest = {
  event_type: 'noise_conflict',
  severity: 4,
  frequency: 'weekly',
  emotion: 'irritated',
  has_communicated: false,
  has_conflict: true,
  description: '舍友晚上打游戏声音比较大，最近一周影响了睡眠，也不知道怎么开口说。',
}

export const mockAnalyzeResult: AnalyzeResult = {
  pressure_score: 76,
  risk_level: 'high',
  risk_label: '冲突风险较高',
  main_reasons: ['作息冲突', '噪音问题'],
  main_sources: ['作息冲突', '噪音问题'],
  emotion_keywords: ['无奈', '压抑', '烦躁'],
  suggestion:
    '先表达感受，再提出具体可执行的请求；如果沟通后未改善，可联系辅导员或宿舍管理人员协助。',
  trend_message:
    '该问题发生频率较高，且尚未进行有效沟通。建议先进行沟通演练，再选择舍友情绪较平稳的时间进行现实沟通。',
  recommend_simulation: true,
  disclaimer: '本结果为演示数据，未经过接口返回。',
  is_demo: true,
  demo_notice: '演示数据',
  suggestions: [
    '先表达感受，再提出具体可执行请求。',
    '表达自己的睡眠受影响，再提出 12 点后戴耳机的具体请求。',
    '如果沟通后仍持续影响生活，可联系辅导员或宿舍管理人员协助。',
  ],
  safety_notice: '本结果仅用于宿舍关系压力趋势提示，不作为医学或心理诊断依据。',
  trend_notice:
    '该问题发生频率较高，且尚未进行有效沟通。建议先进行沟通演练，再选择舍友情绪较平稳的时间进行现实沟通。',
}

export function optionLabel(options: Array<{ value: string; label: string }>, value: string) {
  return options.find((option) => option.value === value)?.label ?? value
}

function normalizeEmotionKeywordLabel(keyword: string) {
  if (keyword === '无助') {
    return '无奈'
  }
  if (keyword === '低落') {
    return '压抑'
  }

  return keyword
}

export function normalizeAnalyzeResponse(
  payload: AnalyzeApiResponse,
  demoNotice = '',
  isDemo = false,
): AnalyzeResult {
  return {
    pressure_score: payload.pressure_score,
    risk_level: payload.risk_level,
    risk_label: payload.risk_label,
    main_reasons: payload.main_sources,
    main_sources: payload.main_sources,
    emotion_keywords: payload.emotion_keywords.map(normalizeEmotionKeywordLabel),
    suggestion: payload.suggestion,
    trend_message: payload.trend_message,
    recommend_simulation: payload.recommend_simulation,
    disclaimer: payload.disclaimer,
    is_demo: isDemo,
    demo_notice: demoNotice,
    suggestions: [payload.suggestion],
    safety_notice: payload.disclaimer,
    trend_notice: payload.trend_message,
  }
}

function buildDemoAnalyzeResult(reason: string): AnalyzeResult {
  return normalizeAnalyzeResponse(
    {
      pressure_score: 68,
      risk_level: 'pressure',
      risk_label: '中等压力',
      main_sources: ['未检测到可直接映射来源，暂显示兜底说明'],
      emotion_keywords: ['烦躁', '无力'],
      trend_message: '未接入真实分析服务时，以下结果为演示兜底。',
      suggestion: '建议先记录更多细节，再尝试再次提交分析。',
      recommend_simulation: true,
      disclaimer: `演示兜底结果：${reason}`,
    },
    reason,
    true,
  )
}

export function buildDemoSimulationResponse(reason: string): SimulationResponse {
  return {
    conversation_id: `demo-${Date.now()}`,
    replies: [
      {
        roommate_id: 'roommate_a',
        roommate: '舍友 A',
        personality: '直接型',
        message: '我也没多大声吧，你是不是太敏感了？',
      },
      {
        roommate_id: 'roommate_b',
        roommate: '舍友 B',
        personality: '回避型',
        message: '这个事情之后再说吧。',
      },
      {
        roommate_id: 'roommate_c',
        roommate: '舍友 C',
        personality: '调和型',
        message: '要不我们一起定一个晚上安静时间？',
      },
    ],
    archive_context_used: false,
    safety_note: `当前为演示兜底回复：${reason}`,
    is_demo: true,
    demo_notice: reason,
  }
}

const reviewSuggestionBypass: ReviewRewriteSuggestion = {
  message_index: 0,
  original_message: '你晚上能不能小声点？',
  issue: '请求比较笼统，容易被理解成单纯指责。',
  suggested_message:
    '我最近睡眠状态不太好，晚上声音比较容易影响我。我们能不能约定 11 点后戴耳机或调低音量？',
  reason: '先说明影响，再提出具体可执行的调整。',
}

const demoReviewStrengths = [
  '你在表达中点出了自己受影响的结果，给对方理解的入口。',
  '你没有直接上纲上线，而是先给出可沟通的时间维度。',
  '你提供了与对方协商的语气，降低了对抗感。',
]

const demoReviewRisks = [
  '建议避免使用“你总是”“每次都”这类绝对化表述。',
  '把请求限定在可执行行动和固定时段，便于对方回应。',
  '先给对方表达空间，再决定下一步沟通安排。',
]

const demoReviewPerformanceScores: ReviewPerformanceScores = {
  clarity: 84,
  empathy: 78,
  resolution: 82,
}

const demoReviewSteps = [
  '选择对方情绪较平稳时再复盘一次该话题。',
  '提前商量一个双方都能接受的休息时间规则。',
  '复盘后若持续无效，可联系辅导员或宿管老师协助。',
]

const demoCommunicationPlan: CommunicationPlan = {
  opening: '我想和你聊一下最近晚上休息被影响的事情，我不是想指责你，只是想一起找个办法。',
  specific_request: '我们能不能约定 11 点后戴耳机或把游戏音量调低，尽量不影响彼此休息？',
  fallback_plan:
    '如果今天不方便马上定下来，我们可以明天再聊；如果还是协调不了，再请辅导员或宿管老师帮忙。',
}

export function buildDemoReviewResponse(reason: string, request: ReviewRequest): ReviewResponse {
  const scene = request.scenario || '近期沟通场景'
  return {
    summary: `你在“${scene}”中的沟通总体方向较平和，已经包含了表达影响与协商意愿，建议继续围绕具体执行细节收敛。`,
    strengths: [...demoReviewStrengths],
    risks: [...demoReviewRisks],
    performance_scores: { ...demoReviewPerformanceScores },
    rewrite_suggestions: [{ ...reviewSuggestionBypass }],
    rewritten_message: reviewSuggestionBypass.suggested_message,
    next_steps: [...demoReviewSteps],
    communication_plan: { ...demoCommunicationPlan },
    safety_note: '本复盘仅用于沟通训练建议，不进行医学、心理诊断或人格评价。',
    is_demo: true,
    demo_notice: reason,
  }
}

function mapAnalyzeRequest(form: AnalyzeRequest): AnalyzeRequestPayload {
  const mappedEventType = EVENT_TYPE_MAP[form.event_type as LegacyEventType] ?? 'emotion'
  const mappedFrequency = FREQUENCY_MAP[form.frequency as LegacyFrequency] ?? 'occasional'
  const mappedPrimaryEmotion =
    EMOTION_MAP[(form.primary_emotion || form.emotion) as LegacyEmotion] ?? 'helpless'
  const mappedEmotions = Array.from(
    new Set(
      (form.emotions && form.emotions.length > 0 ? form.emotions : [form.emotion])
        .map((emotion) => EMOTION_MAP[emotion as LegacyEmotion])
        .filter((emotion): emotion is AnalyzeRequestPayload['emotion'] => Boolean(emotion)),
    ),
  )

  return {
    event_type: mappedEventType,
    severity: Number(form.severity) || 1,
    frequency: mappedFrequency,
    emotion: mappedPrimaryEmotion,
    emotions: mappedEmotions.includes(mappedPrimaryEmotion)
      ? mappedEmotions
      : [mappedPrimaryEmotion, ...mappedEmotions],
    primary_emotion: mappedPrimaryEmotion,
    has_communicated: form.has_communicated === true,
    has_conflict: form.has_conflict === true,
    description: form.description ?? '',
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string')
}

function isSimulationReply(value: unknown): value is SimulationReply {
  return (
    isRecord(value) &&
    typeof value.roommate_id === 'string' &&
    value.roommate_id.length > 0 &&
    typeof value.roommate === 'string' &&
    value.roommate.length > 0 &&
    typeof value.personality === 'string' &&
    value.personality.length > 0 &&
    typeof value.message === 'string' &&
    value.message.length > 0
  )
}

function isSimulationResponsePayload(value: unknown): value is SimulationResponsePayload {
  if (!isRecord(value)) {
    return false
  }

  const replies = (value as { replies?: unknown }).replies
  const conversationId = (value as { conversation_id?: unknown }).conversation_id
  const safetyNote = (value as { safety_note?: unknown }).safety_note
  const archiveContextUsed = (value as { archive_context_used?: unknown }).archive_context_used
  const archiveContextSummary = (value as { archive_context_summary?: unknown })
    .archive_context_summary
  const isDemo = (value as { is_demo?: unknown }).is_demo
  const demoNotice = (value as { demo_notice?: unknown }).demo_notice
  const hasCompatibleSourceFields =
    (typeof isDemo === 'undefined' || typeof isDemo === 'boolean') &&
    (typeof demoNotice === 'undefined' || typeof demoNotice === 'string')
  const hasCompatibleArchiveFields =
    (typeof archiveContextUsed === 'undefined' || typeof archiveContextUsed === 'boolean') &&
    (typeof archiveContextSummary === 'undefined' ||
      typeof archiveContextSummary === 'string' ||
      archiveContextSummary === null)

  return (
    Array.isArray(replies) &&
    replies.every(isSimulationReply) &&
    (typeof conversationId === 'undefined' || typeof conversationId === 'string') &&
    typeof safetyNote === 'string' &&
    hasCompatibleArchiveFields &&
    hasCompatibleSourceFields
  )
}

function isSimulationStreamEvent(value: unknown): value is SimulationStreamEvent {
  if (!isRecord(value) || typeof value.type !== 'string') {
    return false
  }

  if (value.type === 'start') {
    return (
      typeof (value as { conversation_id?: unknown }).conversation_id === 'undefined' ||
      typeof (value as { conversation_id?: unknown }).conversation_id === 'string'
    )
  }

  if (value.type === 'reply') {
    return isSimulationReply((value as { reply?: unknown }).reply)
  }

  if (value.type === 'final') {
    return isSimulationResponsePayload((value as { response?: unknown }).response)
  }

  return false
}

function isReviewRewriteSuggestion(value: unknown): value is ReviewRewriteSuggestion {
  if (!isRecord(value)) {
    return false
  }

  return (
    typeof value.message_index === 'number' &&
    Number.isFinite(value.message_index) &&
    typeof value.original_message === 'string' &&
    typeof value.issue === 'string' &&
    typeof value.suggested_message === 'string' &&
    typeof value.reason === 'string'
  )
}

function isReviewPerformanceScores(value: unknown): value is ReviewPerformanceScores {
  if (!isRecord(value)) {
    return false
  }

  return (
    typeof value.clarity === 'number' &&
    Number.isFinite(value.clarity) &&
    typeof value.empathy === 'number' &&
    Number.isFinite(value.empathy) &&
    typeof value.resolution === 'number' &&
    Number.isFinite(value.resolution)
  )
}

function isCommunicationPlan(value: unknown): value is CommunicationPlan {
  if (!isRecord(value)) {
    return false
  }

  return (
    typeof value.opening === 'string' &&
    typeof value.specific_request === 'string' &&
    typeof value.fallback_plan === 'string'
  )
}

export function isReviewResponsePayload(value: unknown): value is ReviewResponsePayload {
  if (!isRecord(value)) {
    return false
  }

  const summary = (value as { summary?: unknown }).summary
  const strengths = (value as { strengths?: unknown }).strengths
  const risks = (value as { risks?: unknown }).risks
  const performanceScores = (value as { performance_scores?: unknown }).performance_scores
  const rewriteSuggestions = (value as { rewrite_suggestions?: unknown }).rewrite_suggestions
  const rewrittenMessage = (value as { rewritten_message?: unknown }).rewritten_message
  const nextSteps = (value as { next_steps?: unknown }).next_steps
  const communicationPlan = (value as { communication_plan?: unknown }).communication_plan
  const safetyNote = (value as { safety_note?: unknown }).safety_note
  const isDemo = (value as { is_demo?: unknown }).is_demo
  const demoNotice = (value as { demo_notice?: unknown }).demo_notice
  const hasCompatibleSourceFields =
    (typeof isDemo === 'undefined' || typeof isDemo === 'boolean') &&
    (typeof demoNotice === 'undefined' || typeof demoNotice === 'string')

  return (
    typeof summary === 'string' &&
    isStringArray(strengths) &&
    isStringArray(risks) &&
    (typeof performanceScores === 'undefined' || isReviewPerformanceScores(performanceScores)) &&
    (typeof rewriteSuggestions === 'undefined' ||
      (Array.isArray(rewriteSuggestions) && rewriteSuggestions.every(isReviewRewriteSuggestion))) &&
    (typeof rewrittenMessage === 'undefined' || typeof rewrittenMessage === 'string') &&
    isStringArray(nextSteps) &&
    (typeof communicationPlan === 'undefined' || isCommunicationPlan(communicationPlan)) &&
    typeof safetyNote === 'string' &&
    hasCompatibleSourceFields
  )
}

export function isReviewResponse(value: unknown): value is ReviewResponse {
  if (!isReviewResponsePayload(value)) {
    return false
  }

  return (
    typeof (value as { is_demo?: unknown }).is_demo === 'boolean' &&
    typeof (value as { demo_notice?: unknown }).demo_notice === 'string' &&
    isReviewPerformanceScores((value as { performance_scores?: unknown }).performance_scores) &&
    isCommunicationPlan((value as { communication_plan?: unknown }).communication_plan)
  )
}

export function isStoredReviewResult(value: unknown): value is StoredReviewResult {
  if (!isRecord(value)) {
    return false
  }

  const request = (value as { request?: unknown }).request
  const response = (value as { response?: unknown }).response

  if (
    !isRecord(request) ||
    typeof request.scenario !== 'string' ||
    (typeof (request as { conversation_id?: unknown }).conversation_id !== 'undefined' &&
      typeof (request as { conversation_id?: unknown }).conversation_id !== 'string') ||
    (typeof (request as { dialogue?: unknown }).dialogue !== 'undefined' &&
      !Array.isArray((request as { dialogue?: unknown }).dialogue)) ||
    !isReviewResponsePayload(response)
  ) {
    return false
  }

  const storedReview = value as { response: ReviewResponse }
  storedReview.response = normalizeReviewResponse(response)
  return true
}

function normalizeRewrittenMessage(raw: unknown, suggestions: ReviewRewriteSuggestion[]): string {
  if (typeof raw === 'string' && raw.trim().length > 0) {
    return raw
  }

  if (suggestions.length > 0) {
    return suggestions[0]?.suggested_message ?? reviewSuggestionBypass.suggested_message
  }

  return reviewSuggestionBypass.suggested_message
}

function normalizeRewriteSuggestions(
  rawSuggestions: unknown,
  rewrittenMessage: unknown,
): ReviewRewriteSuggestion[] {
  if (
    Array.isArray(rawSuggestions) &&
    rawSuggestions.length > 0 &&
    rawSuggestions.every(isReviewRewriteSuggestion)
  ) {
    return rawSuggestions.map((item) => ({ ...item }))
  }

  if (typeof rewrittenMessage === 'string' && rewrittenMessage.trim().length > 0) {
    return [
      {
        ...reviewSuggestionBypass,
        suggested_message: rewrittenMessage.trim(),
      },
    ]
  }

  return [{ ...reviewSuggestionBypass }]
}

function normalizeCommunicationPlan(raw: unknown, rewrittenMessage: string): CommunicationPlan {
  if (isCommunicationPlan(raw)) {
    return {
      opening: raw.opening.trim() || demoCommunicationPlan.opening,
      specific_request:
        raw.specific_request.trim() || rewrittenMessage || demoCommunicationPlan.specific_request,
      fallback_plan: raw.fallback_plan.trim() || demoCommunicationPlan.fallback_plan,
    }
  }

  return {
    opening: demoCommunicationPlan.opening,
    specific_request: rewrittenMessage || demoCommunicationPlan.specific_request,
    fallback_plan: demoCommunicationPlan.fallback_plan,
  }
}

export function normalizeReviewResponse(raw: {
  summary?: unknown
  strengths?: unknown
  risks?: unknown
  performance_scores?: unknown
  rewrite_suggestions?: unknown
  rewritten_message?: unknown
  next_steps?: unknown
  communication_plan?: unknown
  safety_note?: unknown
  is_demo?: unknown
  demo_notice?: unknown
}): ReviewResponse {
  const rewriteSuggestions = normalizeRewriteSuggestions(
    raw.rewrite_suggestions,
    raw.rewritten_message,
  )
  const rewrittenMessage = normalizeRewrittenMessage(raw.rewritten_message, rewriteSuggestions)

  return {
    summary: typeof raw.summary === 'string' ? raw.summary : '后端返回结构异常，已用本地兜底展示。',
    strengths:
      isStringArray(raw.strengths) && raw.strengths.length > 0
        ? raw.strengths
        : [...demoReviewStrengths],
    risks: isStringArray(raw.risks) && raw.risks.length > 0 ? raw.risks : [...demoReviewRisks],
    performance_scores: isReviewPerformanceScores(raw.performance_scores)
      ? raw.performance_scores
      : { ...demoReviewPerformanceScores },
    rewrite_suggestions: rewriteSuggestions,
    rewritten_message: rewrittenMessage,
    next_steps:
      isStringArray(raw.next_steps) && raw.next_steps.length > 0
        ? raw.next_steps
        : [...demoReviewSteps],
    communication_plan: normalizeCommunicationPlan(raw.communication_plan, rewrittenMessage),
    safety_note:
      typeof raw.safety_note === 'string' ? raw.safety_note : '本复盘仅用于沟通训练建议。',
    is_demo: typeof raw.is_demo === 'boolean' ? raw.is_demo : false,
    demo_notice:
      typeof raw.demo_notice === 'string'
        ? raw.demo_notice
        : '后端返回字段不匹配，已展示复盘兜底内容',
  }
}

function normalizeSimulationResponse(raw: SimulationResponsePayload): SimulationResponse {
  return {
    conversation_id:
      typeof raw.conversation_id === 'string' && raw.conversation_id.trim()
        ? raw.conversation_id
        : `local-${Date.now()}`,
    replies: raw.replies,
    archive_context_used: raw.archive_context_used === true,
    archive_context_summary:
      typeof raw.archive_context_summary === 'string' ? raw.archive_context_summary : undefined,
    safety_note: raw.safety_note,
    is_demo: typeof raw.is_demo === 'boolean' ? raw.is_demo : false,
    demo_notice:
      typeof raw.demo_notice === 'string'
        ? raw.demo_notice
        : raw.is_demo
          ? '演示模拟'
          : '后端返回模拟',
  }
}

export function isAnalyzeApiResponse(value: unknown): value is AnalyzeApiResponse {
  if (!isRecord(value)) {
    return false
  }

  return (
    typeof value.pressure_score === 'number' &&
    Number.isFinite(value.pressure_score) &&
    (value.risk_level === 'stable' ||
      value.risk_level === 'pressure' ||
      value.risk_level === 'high' ||
      value.risk_level === 'severe') &&
    typeof value.risk_label === 'string' &&
    isStringArray(value.main_sources) &&
    isStringArray(value.emotion_keywords) &&
    typeof value.trend_message === 'string' &&
    typeof value.suggestion === 'string' &&
    typeof value.recommend_simulation === 'boolean' &&
    typeof value.disclaimer === 'string'
  )
}

export function isAnalyzeResult(value: unknown): value is AnalyzeResult {
  if (!isRecord(value) || !isAnalyzeApiResponse(value)) {
    return false
  }

  return (
    isStringArray(value.main_reasons) &&
    isStringArray(value.main_sources) &&
    isStringArray(value.suggestions) &&
    typeof value.safety_notice === 'string' &&
    typeof value.trend_notice === 'string' &&
    typeof value.is_demo === 'boolean' &&
    typeof value.demo_notice === 'string'
  )
}

export async function submitAnalyzeRequest(form: AnalyzeRequest): Promise<AnalyzeResult> {
  const fallback = buildDemoAnalyzeResult('后端服务未就绪')

  try {
    const response = await fetch('/api/analyze', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(mapAnalyzeRequest(form)),
    })

    if (!response.ok) {
      return buildDemoAnalyzeResult(`接口返回 ${response.status}`)
    }

    const raw = (await response.json()) as unknown

    if (!isAnalyzeApiResponse(raw)) {
      return buildDemoAnalyzeResult('接口返回字段不匹配')
    }

    return normalizeAnalyzeResponse(raw)
  } catch (error) {
    if (error instanceof Error) {
      return buildDemoAnalyzeResult(`请求失败：${error.message}`)
    }

    return fallback
  }
}

export async function submitSimulationRequest(
  payload: SimulationRequest,
  signal?: AbortSignal,
): Promise<SimulationResponse> {
  const fallback = buildDemoSimulationResponse('后端服务未就绪')

  try {
    const response = await fetch('/api/simulate', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
      signal,
    })

    if (!response.ok) {
      if (response.status === 400 || response.status === 422) {
        let detail = ''
        try {
          const raw = (await response.json()) as unknown
          if (isRecord(raw) && typeof raw.detail === 'string') {
            detail = raw.detail
          }
        } catch {
          // Keep status fallback below.
        }
        throw new SimulationRequestError(
          detail || `模拟请求被后端拒绝（接口返回 ${response.status}）`,
        )
      }

      return buildDemoSimulationResponse(`接口返回 ${response.status}`)
    }

    const raw = (await response.json()) as unknown

    if (!isSimulationResponsePayload(raw)) {
      return buildDemoSimulationResponse('接口返回字段不匹配')
    }

    return normalizeSimulationResponse(raw)
  } catch (error) {
    if (
      error instanceof SimulationRequestError ||
      (error instanceof Error && error.name === 'AbortError')
    ) {
      throw error
    }

    if (error instanceof Error) {
      return buildDemoSimulationResponse(`请求失败：${error.message}`)
    }

    return fallback
  }
}

export async function submitSimulationStreamRequest(
  payload: SimulationRequest,
  handlers: SimulationStreamHandlers = {},
  signal?: AbortSignal,
): Promise<SimulationResponse> {
  const response = await fetch('/api/simulate/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
    signal,
  })

  if (!response.ok) {
    let detail = ''
    try {
      const raw = (await response.json()) as unknown
      if (isRecord(raw) && typeof raw.detail === 'string') {
        detail = raw.detail
      } else if (isRecord(raw) && typeof raw.detail !== 'undefined') {
        detail = JSON.stringify(raw.detail)
      }
    } catch {
      // Ignore malformed error bodies; the status code is still enough context.
    }
    const message = detail || `实时回复请求失败（接口返回 ${response.status}）`
    throw new SimulationStreamRequestError(
      message,
      response.status >= 500 || response.status === 429,
      response.status,
      detail || message,
    )
  }

  if (!response.body) {
    throw new SimulationStreamRequestError('stream response body missing', false)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let finalResponse: SimulationResponse | null = null
  let completedStream = false

  try {
    while (true) {
      const { value, done } = await reader.read()
      buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed) {
          continue
        }

        const event = JSON.parse(trimmed) as unknown
        if (!isSimulationStreamEvent(event)) {
          throw new Error('stream event shape mismatch')
        }

        if (event.type === 'reply') {
          handlers.onReply?.(event.reply)
        }

        if (event.type === 'start') {
          handlers.onStart?.(event.conversation_id)
        }

        if (event.type === 'final') {
          finalResponse = normalizeSimulationResponse(event.response)
        }
      }

      if (done) {
        break
      }
    }

    const tail = buffer.trim()
    if (tail) {
      const event = JSON.parse(tail) as unknown
      if (!isSimulationStreamEvent(event)) {
        throw new Error('stream event shape mismatch')
      }

      if (event.type === 'reply') {
        handlers.onReply?.(event.reply)
      }

      if (event.type === 'start') {
        handlers.onStart?.(event.conversation_id)
      }

      if (event.type === 'final') {
        finalResponse = normalizeSimulationResponse(event.response)
      }
    }
    completedStream = true
  } finally {
    if (signal?.aborted || !completedStream) {
      try {
        await reader.cancel()
      } catch {
        // Preserve the original stream read/parse/abort error.
      }
    }
  }

  if (!finalResponse) {
    throw new SimulationStreamRequestError('stream final response missing', false)
  }

  return finalResponse
}

export async function submitReviewRequest(payload: ReviewRequest): Promise<ReviewResponse> {
  const fallback = buildDemoReviewResponse('后端服务未就绪', payload)

  try {
    const response = await fetch('/api/review', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    })

    if (!response.ok && response.status === 400) {
      let detail = ''
      try {
        const raw = (await response.json()) as unknown
        if (isRecord(raw) && typeof raw.detail === 'string') {
          detail = raw.detail
        }
      } catch {
        // malformed error bodies still map to a recoverable memory-missing message.
      }
      throw new Error(detail || '未找到后端对话记忆，请回到模拟页重新演练。')
    }

    if (!response.ok) {
      return buildDemoReviewResponse(`接口返回 ${response.status}`, payload)
    }

    const raw = (await response.json()) as unknown

    if (!isReviewResponsePayload(raw)) {
      return buildDemoReviewResponse('接口返回字段不匹配', payload)
    }

    return normalizeReviewResponse(raw)
  } catch (error) {
    if (error instanceof Error) {
      if (error.message.includes('后端对话记忆') || error.message.includes('重新演练')) {
        throw error
      }

      return buildDemoReviewResponse(`请求失败：${error.message}`, payload)
    }

    return fallback
  }
}
