import {
  normalizeAnalyzeResponse,
  type AnalyzeApiResponse,
  type AnalyzeRequest,
  type AnalyzeRiskLevel,
  type AnalyzeResult,
} from '@/data/week1'

export type ArchiveEventType = 'noise' | 'schedule' | 'hygiene' | 'cost' | 'privacy' | 'emotion'
export type ArchiveFrequency = 'occasional' | 'weekly_multiple' | 'daily'
export type ArchiveEmotion =
  | 'irritable'
  | 'anxious'
  | 'wronged'
  | 'angry'
  | 'helpless'
  | 'depressed'

export interface EventRecordCreate {
  event_date: string
  event_type: ArchiveEventType
  severity: number
  frequency: ArchiveFrequency
  emotion: ArchiveEmotion
  emotions: ArchiveEmotion[]
  primary_emotion: ArchiveEmotion
  has_communicated: boolean
  has_conflict: boolean
  description: string
}

export interface EventRecordForm extends AnalyzeRequest {
  event_date: string
  emotions: string[]
  primary_emotion: string
}

export interface EventRecord extends Omit<EventRecordCreate, 'emotions' | 'primary_emotion'> {
  emotions?: ArchiveEmotion[]
  primary_emotion?: ArchiveEmotion
  id: string
  created_at: string
  single_analysis: AnalyzeApiResponse
}

export interface EventArchiveResponse {
  events: EventRecord[]
}

export interface SourceBreakdown {
  label: string
  percent: number
  contribution: number
}

export interface ArchiveTrendPoint {
  date: string
  pressure_score: number
  event_count: number
}

export interface EmotionDistributionItem {
  emotion: ArchiveEmotion
  label: string
  count: number
  percent: number
}

export interface SourceInsight {
  rank: number
  label: string
  percent: number
  contribution: number
  event_count: number
  recent_event_date: string | null
  explanation: string
}

export interface EventInsightSummary {
  period_days: number
  period_event_count: number
  top_emotions: string[]
  top_event_types: string[]
  communicated_count: number
  uncommunicated_count: number
  conflict_count: number
  summary: string
}

export interface TrainingRecommendation {
  category_id: string
  category_label: string
  scenario_id: string
  scenario_title: string
  target_id: string
  target_label: string
  difficulty_id: string
  difficulty_label: string
  difficulty_description: string
  reason: string
  opening_suggestion: string
  safety_note: string
}

export interface ArchiveAnalysisResponse extends AnalyzeApiResponse {
  event_count: number
  active_30d_count: number
  source_breakdown: SourceBreakdown[]
  period_days?: number
  active_period_count?: number
  trend_points?: ArchiveTrendPoint[]
  trend_explanation?: string
  source_insights?: SourceInsight[]
  main_source_conclusion?: string
  emotion_distribution?: EmotionDistributionItem[]
  event_insight?: EventInsightSummary | null
  training_recommendation?: TrainingRecommendation | null
}

export interface ArchiveAnalysisResult extends AnalyzeResult {
  event_count: number
  active_30d_count: number
  source_breakdown: SourceBreakdown[]
  period_days: number
  active_period_count: number
  trend_points: ArchiveTrendPoint[]
  trend_explanation: string
  source_insights: SourceInsight[]
  main_source_conclusion: string
  emotion_distribution: EmotionDistributionItem[]
  event_insight: EventInsightSummary | null
  training_recommendation: TrainingRecommendation | null
}

export interface ArchiveInsightResponse {
  insight: string
  care_suggestion: string
  communication_focus: string[]
  safety_note: string
}

export const ARCHIVE_INSIGHT_CACHE_KEY = 'dorm-harmony:archive-insight-cache:v2'

const EVENT_TYPE_MAP: Record<string, ArchiveEventType> = {
  noise_conflict: 'noise',
  schedule_conflict: 'schedule',
  hygiene_conflict: 'hygiene',
  expense_conflict: 'cost',
  privacy_boundary: 'privacy',
  emotional_conflict: 'emotion',
  noise: 'noise',
  schedule: 'schedule',
  hygiene: 'hygiene',
  cost: 'cost',
  privacy: 'privacy',
  emotion: 'emotion',
}

const FREQUENCY_MAP: Record<string, ArchiveFrequency> = {
  occasionally: 'occasional',
  weekly: 'weekly_multiple',
  occasional: 'occasional',
  weekly_multiple: 'weekly_multiple',
  daily: 'daily',
}

const EMOTION_MAP: Record<string, ArchiveEmotion> = {
  irritated: 'irritable',
  repressed: 'depressed',
  irritable: 'irritable',
  anxious: 'anxious',
  wronged: 'wronged',
  angry: 'angry',
  helpless: 'helpless',
  depressed: 'depressed',
  无奈: 'helpless',
  压抑: 'depressed',
}

export const eventTypeLabels: Record<ArchiveEventType | string, string> = {
  noise: '噪音冲突',
  schedule: '作息冲突',
  hygiene: '卫生冲突',
  cost: '费用冲突',
  privacy: '隐私边界',
  emotion: '情绪冲突',
  noise_conflict: '噪音冲突',
  schedule_conflict: '作息冲突',
  hygiene_conflict: '卫生冲突',
  expense_conflict: '费用冲突',
  privacy_boundary: '隐私边界',
  emotional_conflict: '情绪冲突',
}

export const frequencyLabels: Record<ArchiveFrequency | string, string> = {
  occasional: '偶尔',
  weekly_multiple: '每周多次',
  daily: '几乎每天',
  occasionally: '偶尔',
  weekly: '每周多次',
}

export const emotionLabels: Record<ArchiveEmotion | string, string> = {
  irritable: '烦躁',
  anxious: '焦虑',
  wronged: '委屈',
  angry: '愤怒',
  helpless: '无奈',
  depressed: '压抑',
  irritated: '烦躁',
  repressed: '压抑',
}

function mapEmotion(value: string | undefined): ArchiveEmotion | undefined {
  const normalized = value?.trim()
  return normalized ? EMOTION_MAP[normalized] : undefined
}

function normalizeEmotionSelection(form: EventRecordForm) {
  const selected = form.emotions.length > 0 ? form.emotions : [form.primary_emotion || form.emotion]
  const emotions = Array.from(
    new Set(selected.map(mapEmotion).filter((emotion): emotion is ArchiveEmotion => Boolean(emotion))),
  )
  const primaryEmotion = mapEmotion(form.primary_emotion) ?? emotions[0] ?? mapEmotion(form.emotion) ?? 'helpless'

  return {
    primaryEmotion,
    emotions: emotions.includes(primaryEmotion) ? emotions : [primaryEmotion, ...emotions],
  }
}

export function formatLocalDate(date = new Date()) {
  const year = date.getFullYear()
  const month = `${date.getMonth() + 1}`.padStart(2, '0')
  const day = `${date.getDate()}`.padStart(2, '0')

  return `${year}-${month}-${day}`
}

export function buildEventRecordCreate(form: EventRecordForm): EventRecordCreate {
  const { primaryEmotion, emotions } = normalizeEmotionSelection(form)

  return {
    event_date: form.event_date,
    event_type: EVENT_TYPE_MAP[form.event_type] ?? 'emotion',
    severity: Number(form.severity) || 1,
    frequency: FREQUENCY_MAP[form.frequency] ?? 'occasional',
    emotion: primaryEmotion,
    emotions,
    primary_emotion: primaryEmotion,
    has_communicated: form.has_communicated === true,
    has_conflict: form.has_conflict === true,
    description: form.description.trim(),
  }
}

export function normalizeArchiveAnalysisResponse(
  payload: ArchiveAnalysisResponse,
): ArchiveAnalysisResult {
  return {
    ...normalizeAnalyzeResponse(payload),
    event_count: payload.event_count,
    active_30d_count: payload.active_30d_count,
    source_breakdown: payload.source_breakdown,
    period_days: payload.period_days ?? 30,
    active_period_count: payload.active_period_count ?? payload.active_30d_count,
    trend_points: payload.trend_points ?? [],
    trend_explanation: payload.trend_explanation ?? '',
    source_insights: payload.source_insights ?? [],
    main_source_conclusion: payload.main_source_conclusion ?? '',
    emotion_distribution: payload.emotion_distribution ?? [],
    event_insight: payload.event_insight ?? null,
    training_recommendation: payload.training_recommendation ?? null,
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string')
}

function isAnalyzeApiResponse(value: unknown): value is AnalyzeApiResponse {
  return (
    isRecord(value) &&
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

function isSourceBreakdown(value: unknown): value is SourceBreakdown {
  return (
    isRecord(value) &&
    typeof value.label === 'string' &&
    typeof value.percent === 'number' &&
    Number.isFinite(value.percent) &&
    typeof value.contribution === 'number' &&
    Number.isFinite(value.contribution)
  )
}

function isArchiveTrendPoint(value: unknown): value is ArchiveTrendPoint {
  return (
    isRecord(value) &&
    typeof value.date === 'string' &&
    typeof value.pressure_score === 'number' &&
    Number.isFinite(value.pressure_score) &&
    typeof value.event_count === 'number' &&
    Number.isFinite(value.event_count)
  )
}

function isArchiveEmotion(value: unknown): value is ArchiveEmotion {
  return (
    value === 'irritable' ||
    value === 'anxious' ||
    value === 'wronged' ||
    value === 'angry' ||
    value === 'helpless' ||
    value === 'depressed'
  )
}

function isEmotionDistributionItem(value: unknown): value is EmotionDistributionItem {
  return (
    isRecord(value) &&
    isArchiveEmotion(value.emotion) &&
    typeof value.label === 'string' &&
    typeof value.count === 'number' &&
    Number.isFinite(value.count) &&
    typeof value.percent === 'number' &&
    Number.isFinite(value.percent)
  )
}

function isSourceInsight(value: unknown): value is SourceInsight {
  return (
    isRecord(value) &&
    typeof value.rank === 'number' &&
    Number.isFinite(value.rank) &&
    typeof value.label === 'string' &&
    typeof value.percent === 'number' &&
    Number.isFinite(value.percent) &&
    typeof value.contribution === 'number' &&
    Number.isFinite(value.contribution) &&
    typeof value.event_count === 'number' &&
    Number.isFinite(value.event_count) &&
    (value.recent_event_date === null || typeof value.recent_event_date === 'string') &&
    typeof value.explanation === 'string'
  )
}

function isEventInsightSummary(value: unknown): value is EventInsightSummary {
  return (
    isRecord(value) &&
    typeof value.period_days === 'number' &&
    Number.isFinite(value.period_days) &&
    typeof value.period_event_count === 'number' &&
    Number.isFinite(value.period_event_count) &&
    isStringArray(value.top_emotions) &&
    isStringArray(value.top_event_types) &&
    typeof value.communicated_count === 'number' &&
    Number.isFinite(value.communicated_count) &&
    typeof value.uncommunicated_count === 'number' &&
    Number.isFinite(value.uncommunicated_count) &&
    typeof value.conflict_count === 'number' &&
    Number.isFinite(value.conflict_count) &&
    typeof value.summary === 'string'
  )
}

function isTrainingRecommendation(value: unknown): value is TrainingRecommendation {
  return (
    isRecord(value) &&
    typeof value.category_id === 'string' &&
    typeof value.category_label === 'string' &&
    typeof value.scenario_id === 'string' &&
    typeof value.scenario_title === 'string' &&
    typeof value.target_id === 'string' &&
    typeof value.target_label === 'string' &&
    typeof value.difficulty_id === 'string' &&
    typeof value.difficulty_label === 'string' &&
    typeof value.difficulty_description === 'string' &&
    typeof value.reason === 'string' &&
    typeof value.opening_suggestion === 'string' &&
    typeof value.safety_note === 'string'
  )
}

function isOptionalFiniteNumber(value: unknown): boolean {
  return typeof value === 'undefined' || (typeof value === 'number' && Number.isFinite(value))
}

function isOptionalString(value: unknown): boolean {
  return typeof value === 'undefined' || typeof value === 'string'
}

function isOptionalArray<T>(
  value: unknown,
  guard: (item: unknown) => item is T,
): boolean {
  return typeof value === 'undefined' || (Array.isArray(value) && value.every(guard))
}

function isOptionalNullable<T>(
  value: unknown,
  guard: (item: unknown) => item is T,
): boolean {
  return typeof value === 'undefined' || value === null || guard(value)
}

function isEventRecord(value: unknown): value is EventRecord {
  return (
    isRecord(value) &&
    typeof value.id === 'string' &&
    typeof value.created_at === 'string' &&
    typeof value.event_date === 'string' &&
    typeof value.event_type === 'string' &&
    typeof value.severity === 'number' &&
    typeof value.frequency === 'string' &&
    typeof value.emotion === 'string' &&
    (typeof value.primary_emotion === 'undefined' || typeof value.primary_emotion === 'string') &&
    (typeof value.emotions === 'undefined' || isStringArray(value.emotions)) &&
    typeof value.has_communicated === 'boolean' &&
    typeof value.has_conflict === 'boolean' &&
    typeof value.description === 'string' &&
    isAnalyzeApiResponse(value.single_analysis)
  )
}

function isEventArchiveResponse(value: unknown): value is EventArchiveResponse {
  return isRecord(value) && Array.isArray(value.events) && value.events.every(isEventRecord)
}

function isArchiveAnalysisResponse(value: unknown): value is ArchiveAnalysisResponse {
  if (!isAnalyzeApiResponse(value)) {
    return false
  }

  const candidate = value as unknown as Record<string, unknown>

  return (
    typeof candidate.event_count === 'number' &&
    Number.isFinite(candidate.event_count) &&
    typeof candidate.active_30d_count === 'number' &&
    Number.isFinite(candidate.active_30d_count) &&
    Array.isArray(candidate.source_breakdown) &&
    candidate.source_breakdown.every(isSourceBreakdown) &&
    isOptionalFiniteNumber(candidate.period_days) &&
    isOptionalFiniteNumber(candidate.active_period_count) &&
    isOptionalArray(candidate.trend_points, isArchiveTrendPoint) &&
    isOptionalString(candidate.trend_explanation) &&
    isOptionalArray(candidate.source_insights, isSourceInsight) &&
    isOptionalString(candidate.main_source_conclusion) &&
    isOptionalArray(candidate.emotion_distribution, isEmotionDistributionItem) &&
    isOptionalNullable(candidate.event_insight, isEventInsightSummary) &&
    isOptionalNullable(candidate.training_recommendation, isTrainingRecommendation)
  )
}

function isArchiveInsightResponse(value: unknown): value is ArchiveInsightResponse {
  return (
    isRecord(value) &&
    typeof value.insight === 'string' &&
    typeof value.care_suggestion === 'string' &&
    isStringArray(value.communication_focus) &&
    typeof value.safety_note === 'string'
  )
}

async function readErrorDetail(response: Response) {
  try {
    const raw = (await response.json()) as unknown
    if (isRecord(raw) && typeof raw.detail === 'string') {
      return raw.detail
    }
  } catch {
    // Ignore malformed error bodies; the status code is still surfaced.
  }

  return ''
}

async function assertOk(response: Response, fallbackMessage: string) {
  if (response.ok) {
    return
  }

  const detail = await readErrorDetail(response)
  const suffix = detail ? `：${detail}` : ''
  throw new Error(`${fallbackMessage}（接口返回 ${response.status}${suffix}）`)
}

export async function createEventRecord(payload: EventRecordCreate): Promise<EventRecord> {
  const response = await fetch('/api/events', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  await assertOk(response, '事件保存失败')
  const raw = (await response.json()) as unknown

  if (!isEventRecord(raw)) {
    throw new Error('事件保存失败（接口返回字段不匹配）')
  }

  return raw
}

export async function fetchEventArchive(): Promise<EventArchiveResponse> {
  const response = await fetch('/api/events')

  await assertOk(response, '事件档案加载失败')
  const raw = (await response.json()) as unknown

  if (!isEventArchiveResponse(raw)) {
    throw new Error('事件档案加载失败（接口返回字段不匹配）')
  }

  return raw
}

export async function deleteEventRecord(id: string): Promise<void> {
  const response = await fetch(`/api/events/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  })

  await assertOk(response, '事件删除失败')
}

export async function fetchArchiveAnalysis(rangeDays = 30): Promise<ArchiveAnalysisResponse> {
  const response = await fetch(`/api/events/analysis?range_days=${rangeDays}`)

  await assertOk(response, '总压力分析加载失败')
  const raw = (await response.json()) as unknown

  if (!isArchiveAnalysisResponse(raw)) {
    throw new Error('总压力分析加载失败（接口返回字段不匹配）')
  }

  return raw
}

export async function fetchArchiveInsight(rangeDays = 30): Promise<ArchiveInsightResponse> {
  const response = await fetch(
    `/api/events/insight?range_days=${encodeURIComponent(String(rangeDays))}`,
    {
      method: 'POST',
    },
  )

  await assertOk(response, 'AI 心晴见解加载失败')
  const raw = (await response.json()) as unknown

  if (!isArchiveInsightResponse(raw)) {
    throw new Error('AI 心晴见解加载失败（接口返回字段不匹配）')
  }

  return raw
}

export function isConfiguredAiMissingError(error: unknown) {
  return error instanceof Error && error.message.includes('接口返回 503')
}

export function isAiUnavailableError(error: unknown) {
  return error instanceof Error && error.message.includes('接口返回 502')
}

export function riskLevelStorageEventType(riskLevel: AnalyzeRiskLevel) {
  return `risk-${riskLevel}`
}
