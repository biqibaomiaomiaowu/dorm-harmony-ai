import {
  isReviewResponse,
  isReviewResponsePayload,
  mapEventTypeToAnalyzeApi,
  normalizeReviewResponse,
  type RehearsalSourceMeta,
  type ReviewDialogueLine,
  type ReviewRequest,
  type ReviewResponse,
} from '@/data/week1'

type RecordLike = Record<string, unknown>
type ScenarioReplyChainRange = NonNullable<
  Extract<RehearsalSourceMeta, { mode: 'scenario_training' }>['reply_chain_range']
>

export interface ReviewReportSummary {
  id: string
  created_at: string
  conversation_id?: string | null
  scenario: string
  summary: string
  score_clarity: number
  score_empathy: number
  score_resolution: number
  source_meta?: RehearsalSourceMeta | null
}

export interface ReviewReportDetail extends ReviewReportSummary {
  request: ReviewRequest
  response: ReviewResponse
  dialogue: ReviewDialogueLine[]
}

export interface ReviewHistoryResponse {
  reports: ReviewReportSummary[]
}

function isRecord(value: unknown): value is RecordLike {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function assertString(value: unknown, field: string): string {
  if (typeof value !== 'string') {
    throw new Error(`复盘历史字段异常：${field}`)
  }

  return value
}

function assertOptionalString(value: unknown, field: string): string | undefined {
  if (typeof value === 'undefined' || value === null) {
    return undefined
  }

  return assertString(value, field)
}

function normalizeReviewHistoryEventType(
  value: unknown,
): NonNullable<ReviewRequest['original_event']>['event_type'] | undefined {
  const eventType = assertOptionalString(value, 'request.original_event.event_type')
  if (!eventType) {
    return undefined
  }

  return mapEventTypeToAnalyzeApi(eventType)
}

function assertFiniteNumber(value: unknown, field: string): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    throw new Error(`复盘历史字段异常：${field}`)
  }

  return value
}

function assertScore(value: unknown, field: string): number {
  const score = assertFiniteNumber(value, field)
  if (score < 0 || score > 100) {
    throw new Error(`复盘历史字段异常：${field}`)
  }

  return score
}

function assertOptionalReplyChainRange(
  value: unknown,
  field: string,
): ScenarioReplyChainRange | undefined {
  if (typeof value === 'undefined' || value === null) {
    return undefined
  }
  if (!isRecord(value)) {
    throw new Error(`复盘历史字段异常：${field}`)
  }

  const min = assertFiniteNumber(value.min, `${field}.min`)
  const max = assertFiniteNumber(value.max, `${field}.max`)
  if (min > max) {
    throw new Error(`复盘历史字段异常：${field}`)
  }

  return { min, max }
}

function assertDateString(value: unknown, field: string): string {
  const dateString = assertString(value, field)
  if (Number.isNaN(new Date(dateString).getTime())) {
    throw new Error(`复盘历史字段异常：${field}`)
  }

  return dateString
}

function assertReviewDialogueLine(value: unknown, field: string): ReviewDialogueLine {
  if (!isRecord(value)) {
    throw new Error(`复盘历史字段异常：${field}`)
  }

  const speaker = assertString(value.speaker, `${field}.speaker`)
  if (speaker !== 'user' && speaker !== 'system' && !speaker.startsWith('roommate_')) {
    throw new Error(`复盘历史字段异常：${field}.speaker`)
  }

  return {
    speaker: speaker as ReviewDialogueLine['speaker'],
    message: assertString(value.message, `${field}.message`),
  }
}

function assertReviewDialogue(value: unknown, field: string): ReviewDialogueLine[] {
  if (!Array.isArray(value)) {
    throw new Error(`复盘历史字段异常：${field}`)
  }

  return value.map((item, index) => assertReviewDialogueLine(item, `${field}.${index}`))
}

function assertRoommateNames(
  value: unknown,
): Partial<Record<ReviewDialogueLine['speaker'], string>> {
  if (typeof value === 'undefined' || value === null) {
    return {}
  }
  if (!isRecord(value)) {
    throw new Error('复盘历史字段异常：request.roommate_names')
  }

  return Object.entries(value).reduce<Partial<Record<ReviewDialogueLine['speaker'], string>>>(
    (roommateNames, [speaker, name]) => {
      if (!speaker.startsWith('roommate_') || typeof name !== 'string') {
        throw new Error('复盘历史字段异常：request.roommate_names')
      }

      const trimmedName = name.trim()
      if (trimmedName) {
        roommateNames[speaker as ReviewDialogueLine['speaker']] = trimmedName
      }
      return roommateNames
    },
    {},
  )
}

function assertRehearsalSourceMetaField(value: unknown, field: string): RehearsalSourceMeta {
  if (!isRecord(value)) {
    throw new Error(`复盘历史字段异常：${field}`)
  }

  const mode = assertString(value.mode, `${field}.mode`)
  if (mode === 'scenario_training') {
    const sourceMeta: RehearsalSourceMeta = {
      mode,
      category_id: assertString(value.category_id, `${field}.category_id`),
      category_label: assertString(value.category_label, `${field}.category_label`),
      scenario_id: assertString(value.scenario_id, `${field}.scenario_id`),
      scenario_title: assertString(
        value.scenario_title ?? value.scenario_label,
        `${field}.scenario_title`,
      ),
      target_id: assertString(value.target_id, `${field}.target_id`),
      target_label: assertString(value.target_label, `${field}.target_label`),
      difficulty_id: assertString(value.difficulty_id, `${field}.difficulty_id`),
      difficulty_label: assertString(value.difficulty_label, `${field}.difficulty_label`),
    }

    const difficultyDescription = assertOptionalString(
      value.difficulty_description,
      `${field}.difficulty_description`,
    )
    if (difficultyDescription) {
      sourceMeta.difficulty_description = difficultyDescription
    }
    const roommateSummary = assertOptionalString(value.roommate_summary, `${field}.roommate_summary`)
    if (roommateSummary) {
      sourceMeta.roommate_summary = roommateSummary
    }
    const replyChainRange = assertOptionalReplyChainRange(
      value.reply_chain_range,
      `${field}.reply_chain_range`,
    )
    if (replyChainRange) {
      sourceMeta.reply_chain_range = replyChainRange
    }
    const difficultyPressureProfile = assertOptionalString(
      value.difficulty_pressure_profile,
      `${field}.difficulty_pressure_profile`,
    )
    if (difficultyPressureProfile) {
      sourceMeta.difficulty_pressure_profile = difficultyPressureProfile
    }

    return sourceMeta
  }

  if (mode === 'custom_rehearsal') {
    const sourceMeta: RehearsalSourceMeta = {
      mode,
      scenario: assertString(value.scenario, `${field}.scenario`),
    }
    const roommateSummary = assertOptionalString(
      value.roommate_summary,
      `${field}.roommate_summary`,
    )
    if (roommateSummary) {
      sourceMeta.roommate_summary = roommateSummary
    }

    return sourceMeta
  }

  throw new Error(`复盘历史字段异常：${field}.mode`)
}

export function assertRehearsalSourceMeta(value: unknown): RehearsalSourceMeta {
  return assertRehearsalSourceMetaField(value, 'source_meta')
}

function assertOptionalRehearsalSourceMeta(
  value: unknown,
  field: string,
): RehearsalSourceMeta | null {
  if (typeof value === 'undefined' || value === null) {
    return null
  }

  try {
    return assertRehearsalSourceMetaField(value, field)
  } catch {
    return null
  }
}

function assertReviewRequest(value: unknown): ReviewRequest {
  if (!isRecord(value)) {
    throw new Error('复盘历史字段异常：request')
  }

  const request: ReviewRequest = {
    scenario: assertString(value.scenario, 'request.scenario'),
  }

  const conversationId = assertOptionalString(value.conversation_id, 'request.conversation_id')
  if (conversationId) {
    request.conversation_id = conversationId
  }

  if (typeof value.dialogue !== 'undefined') {
    request.dialogue = assertReviewDialogue(value.dialogue, 'request.dialogue')
  }

  const roommateNames = assertRoommateNames(value.roommate_names)
  if (Object.keys(roommateNames).length > 0) {
    request.roommate_names = roommateNames
  }

  if (typeof value.original_event !== 'undefined' && value.original_event !== null) {
    if (!isRecord(value.original_event)) {
      throw new Error('复盘历史字段异常：request.original_event')
    }

    const originalEvent: NonNullable<ReviewRequest['original_event']> = {}
    const eventType = normalizeReviewHistoryEventType(value.original_event.event_type)
    if (eventType) {
      originalEvent.event_type = eventType
    }

    if (
      typeof value.original_event.risk_level !== 'undefined' &&
      value.original_event.risk_level !== null
    ) {
      const riskLevel = assertString(
        value.original_event.risk_level,
        'request.original_event.risk_level',
      )
      if (
        riskLevel !== 'stable' &&
        riskLevel !== 'pressure' &&
        riskLevel !== 'high' &&
        riskLevel !== 'severe'
      ) {
        throw new Error('复盘历史字段异常：request.original_event.risk_level')
      }
      originalEvent.risk_level = riskLevel as NonNullable<
        ReviewRequest['original_event']
      >['risk_level']
    }

    if (
      typeof value.original_event.pressure_score !== 'undefined' &&
      value.original_event.pressure_score !== null
    ) {
      originalEvent.pressure_score = assertFiniteNumber(
        value.original_event.pressure_score,
        'request.original_event.pressure_score',
      )
    }

    request.original_event = originalEvent
  }

  const sourceMeta = assertOptionalRehearsalSourceMeta(value.source_meta, 'request.source_meta')
  if (sourceMeta) {
    request.source_meta = sourceMeta
  }

  return request
}

function assertReviewResponse(value: unknown): ReviewResponse {
  if (isReviewResponse(value)) {
    return value
  }

  if (!isReviewResponsePayload(value)) {
    throw new Error('复盘历史字段异常：response')
  }

  return normalizeReviewResponse(value)
}

function assertReviewReportSummary(value: unknown): ReviewReportSummary {
  if (!isRecord(value)) {
    throw new Error('复盘历史字段异常：report')
  }

  const conversationId = assertOptionalString(value.conversation_id, 'report.conversation_id')
  const sourceMeta = assertOptionalRehearsalSourceMeta(value.source_meta, 'report.source_meta')

  return {
    id: assertString(value.id, 'report.id'),
    created_at: assertDateString(value.created_at, 'report.created_at'),
    conversation_id: conversationId ?? null,
    scenario: assertString(value.scenario, 'report.scenario'),
    summary: assertString(value.summary, 'report.summary'),
    score_clarity: assertScore(value.score_clarity, 'report.score_clarity'),
    score_empathy: assertScore(value.score_empathy, 'report.score_empathy'),
    score_resolution: assertScore(value.score_resolution, 'report.score_resolution'),
    source_meta: sourceMeta,
  }
}

function assertReviewReportDetail(value: unknown): ReviewReportDetail {
  if (!isRecord(value)) {
    throw new Error('复盘历史字段异常：detail')
  }

  const summary = assertReviewReportSummary(value)
  const request = assertReviewRequest(value.request)

  return {
    ...summary,
    source_meta: summary.source_meta ?? request.source_meta ?? null,
    request,
    response: assertReviewResponse(value.response),
    dialogue: assertReviewDialogue(value.dialogue, 'detail.dialogue'),
  }
}

function assertReviewHistoryResponse(value: unknown): ReviewHistoryResponse {
  if (!isRecord(value) || !Array.isArray(value.reports)) {
    throw new Error('复盘历史字段异常：reports')
  }

  return {
    reports: value.reports.map(assertReviewReportSummary),
  }
}

async function readJsonResponse(response: Response, fallbackMessage: string): Promise<unknown> {
  if (!response.ok) {
    throw new Error(`${fallbackMessage}（接口返回 ${response.status}）`)
  }

  return (await response.json()) as unknown
}

async function readEmptyResponse(response: Response, fallbackMessage: string): Promise<void> {
  if (!response.ok) {
    throw new Error(`${fallbackMessage}（接口返回 ${response.status}）`)
  }
}

export async function fetchReviewHistory(limit = 20): Promise<ReviewHistoryResponse> {
  const params = new URLSearchParams()
  params.set('limit', String(limit))

  const response = await fetch(`/api/reviews?${params.toString()}`)
  const raw = await readJsonResponse(response, '复盘历史加载失败')
  return assertReviewHistoryResponse(raw)
}

export async function fetchReviewReport(id: string): Promise<ReviewReportDetail> {
  const response = await fetch(`/api/reviews/${encodeURIComponent(id)}`)
  const raw = await readJsonResponse(response, '复盘报告加载失败')
  return assertReviewReportDetail(raw)
}

export async function deleteReviewReport(id: string): Promise<void> {
  const response = await fetch(`/api/reviews/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  })
  await readEmptyResponse(response, '复盘报告删除失败')
}
