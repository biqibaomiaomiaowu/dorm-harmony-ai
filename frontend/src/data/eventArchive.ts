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
  has_communicated: boolean
  has_conflict: boolean
  description: string
}

export interface EventRecordForm extends AnalyzeRequest {
  event_date: string
}

export interface EventRecord extends EventRecordCreate {
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

export interface ArchiveAnalysisResponse extends AnalyzeApiResponse {
  event_count: number
  active_30d_count: number
  source_breakdown: SourceBreakdown[]
}

export interface ArchiveAnalysisResult extends AnalyzeResult {
  event_count: number
  active_30d_count: number
  source_breakdown: SourceBreakdown[]
}

export interface ArchiveInsightResponse {
  insight: string
  care_suggestion: string
  communication_focus: string[]
  safety_note: string
}

export const ARCHIVE_INSIGHT_CACHE_KEY = 'dorm-harmony:archive-insight-cache:v1'

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

export function formatLocalDate(date = new Date()) {
  const year = date.getFullYear()
  const month = `${date.getMonth() + 1}`.padStart(2, '0')
  const day = `${date.getDate()}`.padStart(2, '0')

  return `${year}-${month}-${day}`
}

export function buildEventRecordCreate(form: EventRecordForm): EventRecordCreate {
  return {
    event_date: form.event_date,
    event_type: EVENT_TYPE_MAP[form.event_type] ?? 'emotion',
    severity: Number(form.severity) || 1,
    frequency: FREQUENCY_MAP[form.frequency] ?? 'occasional',
    emotion: EMOTION_MAP[form.emotion] ?? 'helpless',
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
    candidate.source_breakdown.every(isSourceBreakdown)
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

export async function fetchArchiveAnalysis(): Promise<ArchiveAnalysisResponse> {
  const response = await fetch('/api/events/analysis')

  await assertOk(response, '总压力分析加载失败')
  const raw = (await response.json()) as unknown

  if (!isArchiveAnalysisResponse(raw)) {
    throw new Error('总压力分析加载失败（接口返回字段不匹配）')
  }

  return raw
}

export async function fetchArchiveInsight(): Promise<ArchiveInsightResponse> {
  const response = await fetch('/api/events/insight', {
    method: 'POST',
  })

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
