export interface AnalyzeRequest {
  event_type: string
  severity: number
  frequency: string
  emotion: string
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

export type ReviewDialogueSpeaker = 'user' | 'roommate_a' | 'roommate_b' | 'roommate_c' | 'system'

export interface ReviewDialogueLine {
  speaker: ReviewDialogueSpeaker
  message: string
}

export interface SimulationRequest {
  scenario: string
  user_message: string
  risk_level?: AnalyzeRiskLevel
  context?: string
  dialogue?: ReviewDialogueLine[]
}

export interface SimulationReply {
  roommate: string
  personality: string
  message: string
}

export interface SimulationResponse {
  replies: SimulationReply[]
  safety_note: string
  is_demo: boolean
  demo_notice: string
}

type SimulationResponsePayload = Omit<SimulationResponse, 'is_demo' | 'demo_notice'> &
  Partial<Pick<SimulationResponse, 'is_demo' | 'demo_notice'>>

export type SimulationStreamEvent =
  | { type: 'start' }
  | { type: 'reply'; reply: SimulationReply }
  | { type: 'final'; response: SimulationResponsePayload }

export interface SimulationStreamHandlers {
  onStart?: () => void
  onReply?: (reply: SimulationReply) => void
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
  feeling_expression: string
  specific_request: string
  communication_space: string
  instead: string
  instead_after: string
}

export interface ReviewPerformanceScores {
  clarity: number
  empathy: number
  resolution: number
}

export interface ReviewResponse {
  summary: string
  strengths: string[]
  risks: string[]
  performance_scores: ReviewPerformanceScores
  rewritten_message: string | ReviewRewriteSuggestion
  next_steps: string[]
  safety_note: string
  is_demo: boolean
  demo_notice: string
}

type ReviewResponsePayload = Omit<ReviewResponse, 'performance_scores' | 'is_demo' | 'demo_notice'> &
  Partial<Pick<ReviewResponse, 'performance_scores' | 'is_demo' | 'demo_notice'>>

export interface ReviewRequest {
  scenario: string
  dialogue: ReviewDialogueLine[]
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
type LegacyEmotion = 'irritated' | 'anxious' | 'wronged' | 'angry' | 'helpless' | 'repressed'

interface AnalyzeRequestPayload {
  event_type: 'noise' | 'schedule' | 'hygiene' | 'cost' | 'privacy' | 'emotion'
  severity: number
  frequency: 'occasional' | 'weekly_multiple' | 'daily'
  emotion: 'irritable' | 'anxious' | 'wronged' | 'angry' | 'helpless' | 'depressed'
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

const EMOTION_MAP: Record<LegacyEmotion, AnalyzeRequestPayload['emotion']> = {
  irritated: 'irritable',
  anxious: 'anxious',
  wronged: 'wronged',
  angry: 'angry',
  helpless: 'helpless',
  repressed: 'depressed',
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

export function mapRoommateToReviewSpeaker(roommate: string): ReviewDialogueSpeaker {
  const normalized = roommate.trim()
  const compact = normalized.replace(/\s+/g, '')

  if (compact === '舍友A' || compact.toLowerCase() === 'roommatea' || compact.toLowerCase() === 'roommate_a') {
    return 'roommate_a'
  }

  if (compact === '舍友B' || compact.toLowerCase() === 'roommateb' || compact.toLowerCase() === 'roommate_b') {
    return 'roommate_b'
  }

  if (compact === '舍友C' || compact.toLowerCase() === 'roommatec' || compact.toLowerCase() === 'roommate_c') {
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
  { value: 'repressed', label: '压抑', icon: 'sentiment_stressed' },
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
    emotion_keywords: payload.emotion_keywords,
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
    replies: [
      {
        roommate: '舍友 A',
        personality: '直接型',
        message: '我也没多大声吧，你是不是太敏感了？',
      },
      {
        roommate: '舍友 B',
        personality: '回避型',
        message: '这个事情之后再说吧。',
      },
      {
        roommate: '舍友 C',
        personality: '调和型',
        message: '要不我们一起定一个晚上安静时间？',
      },
    ],
    safety_note: '当前为演示兜底回复，未接入后端服务。',
    is_demo: true,
    demo_notice: reason,
  }
}

const reviewSuggestionBypass: ReviewRewriteSuggestion = {
  feeling_expression: '先说明自己的睡眠状态和感受，再进入请求。',
  specific_request: '我最近睡眠受影响比较明显，能否让晚上 11 点后把音量调低一点？',
  communication_space: '我们先定个周内临时规则看看效果，我也会尽量配合调节。',
  instead: '你晚上打游戏太吵了，快点闭麦，要不是这样我受不了。',
  instead_after:
    '我最近睡眠状态不太好，晚上声音比较容易影响我。我们能不能约定 11 点后戴耳机或调低音量？',
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

export function buildDemoReviewResponse(reason: string, request: ReviewRequest): ReviewResponse {
  const scene = request.scenario || '近期沟通场景'
  return {
    summary: `你在“${scene}”中的沟通总体方向较平和，已经包含了表达影响与协商意愿，建议继续围绕具体执行细节收敛。`,
    strengths: [...demoReviewStrengths],
    risks: [...demoReviewRisks],
    performance_scores: { ...demoReviewPerformanceScores },
    rewritten_message: { ...reviewSuggestionBypass },
    next_steps: [...demoReviewSteps],
    safety_note: '本复盘仅用于沟通训练建议，不进行医学、心理诊断或人格评价。',
    is_demo: true,
    demo_notice: reason,
  }
}

function mapAnalyzeRequest(form: AnalyzeRequest): AnalyzeRequestPayload {
  const mappedEventType = EVENT_TYPE_MAP[form.event_type as LegacyEventType] ?? 'emotion'
  const mappedFrequency = FREQUENCY_MAP[form.frequency as LegacyFrequency] ?? 'occasional'
  const mappedEmotion = EMOTION_MAP[form.emotion as LegacyEmotion] ?? 'helpless'

  return {
    event_type: mappedEventType,
    severity: Number(form.severity) || 1,
    frequency: mappedFrequency,
    emotion: mappedEmotion,
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
  const safetyNote = (value as { safety_note?: unknown }).safety_note
  const isDemo = (value as { is_demo?: unknown }).is_demo
  const demoNotice = (value as { demo_notice?: unknown }).demo_notice
  const hasCompatibleSourceFields =
    (typeof isDemo === 'undefined' || typeof isDemo === 'boolean') &&
    (typeof demoNotice === 'undefined' || typeof demoNotice === 'string')

  return (
    Array.isArray(replies) &&
    replies.every(isSimulationReply) &&
    typeof safetyNote === 'string' &&
    hasCompatibleSourceFields
  )
}

function isSimulationStreamEvent(value: unknown): value is SimulationStreamEvent {
  if (!isRecord(value) || typeof value.type !== 'string') {
    return false
  }

  if (value.type === 'start') {
    return true
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
    typeof value.feeling_expression === 'string' &&
    typeof value.specific_request === 'string' &&
    typeof value.communication_space === 'string' &&
    typeof value.instead === 'string' &&
    typeof value.instead_after === 'string'
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

function isReviewResponsePayload(value: unknown): value is ReviewResponsePayload {
  if (!isRecord(value)) {
    return false
  }

  const summary = (value as { summary?: unknown }).summary
  const strengths = (value as { strengths?: unknown }).strengths
  const risks = (value as { risks?: unknown }).risks
  const performanceScores = (value as { performance_scores?: unknown }).performance_scores
  const rewrittenMessage = (value as { rewritten_message?: unknown }).rewritten_message
  const nextSteps = (value as { next_steps?: unknown }).next_steps
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
    (typeof rewrittenMessage === 'string' || isReviewRewriteSuggestion(rewrittenMessage)) &&
    isStringArray(nextSteps) &&
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
    isReviewPerformanceScores((value as { performance_scores?: unknown }).performance_scores)
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
    !Array.isArray((request as { dialogue?: unknown }).dialogue) ||
    !isReviewResponsePayload(response)
  ) {
    return false
  }

  const storedReview = value as { response: ReviewResponse }
  storedReview.response = normalizeReviewResponse(response)
  return true
}

function normalizeRewrittenMessage(
  raw: ReviewResponse['rewritten_message'],
): ReviewResponse['rewritten_message'] {
  if (typeof raw === 'string' && raw.trim().length > 0) {
    return raw
  }

  if (isReviewRewriteSuggestion(raw)) {
    return raw
  }

  return { ...reviewSuggestionBypass }
}

function normalizeReviewResponse(raw: {
  summary?: unknown
  strengths?: unknown
  risks?: unknown
  performance_scores?: unknown
  rewritten_message?: unknown
  next_steps?: unknown
  safety_note?: unknown
  is_demo?: unknown
  demo_notice?: unknown
}): ReviewResponse {
  return {
    summary: typeof raw.summary === 'string' ? raw.summary : '后端返回结构异常，已用本地兜底展示。',
    strengths:
      isStringArray(raw.strengths) && raw.strengths.length > 0
        ? raw.strengths
        : [...demoReviewStrengths],
    risks:
      isStringArray(raw.risks) && raw.risks.length > 0
        ? raw.risks
        : [...demoReviewRisks],
    performance_scores: isReviewPerformanceScores(raw.performance_scores)
      ? raw.performance_scores
      : { ...demoReviewPerformanceScores },
    rewritten_message: normalizeRewrittenMessage(raw.rewritten_message as ReviewResponse['rewritten_message']),
    next_steps:
      isStringArray(raw.next_steps) && raw.next_steps.length > 0
        ? raw.next_steps
        : [...demoReviewSteps],
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
    replies: raw.replies,
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
): Promise<SimulationResponse> {
  const fallback = buildDemoSimulationResponse('后端服务未就绪')

  try {
    const response = await fetch('/api/simulate', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    })

    if (!response.ok) {
      return buildDemoSimulationResponse(`接口返回 ${response.status}`)
    }

    const raw = (await response.json()) as unknown

    if (!isSimulationResponsePayload(raw)) {
      return buildDemoSimulationResponse('接口返回字段不匹配')
    }

    return normalizeSimulationResponse(raw)
  } catch (error) {
    if (error instanceof Error) {
      return buildDemoSimulationResponse(`请求失败：${error.message}`)
    }

    return fallback
  }
}

export async function submitSimulationStreamRequest(
  payload: SimulationRequest,
  handlers: SimulationStreamHandlers = {},
): Promise<SimulationResponse> {
  const response = await fetch('/api/simulate/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  if (!response.ok || !response.body) {
    throw new Error(`stream request failed: ${response.status}`)
  }

  handlers.onStart?.()

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let finalResponse: SimulationResponse | null = null

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

    if (event.type === 'final') {
      finalResponse = normalizeSimulationResponse(event.response)
    }
  }

  if (!finalResponse) {
    throw new Error('stream final response missing')
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
      return buildDemoReviewResponse(`请求失败：${error.message}`, payload)
    }

    return fallback
  }
}
