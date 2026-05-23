<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import {
  deleteReviewReport,
  fetchReviewHistory,
  fetchReviewReport,
  type ReviewReportDetail,
  type ReviewReportSummary,
} from '@/data/reviewHistory'
import {
  ANALYSIS_RESULT_STORAGE_KEY,
  LAST_EVENT_STORAGE_KEY,
  REVIEW_RESULT_STORAGE_KEY,
  SIMULATION_RESULT_STORAGE_KEY,
  buildDemoReviewResponse,
  isAnalyzeResult,
  isStoredReviewResult,
  mapEventTypeToAnalyzeApi,
  mapRoommateToReviewSpeaker,
  submitReviewRequest,
  type AnalyzeRequest,
  type AnalyzeResult,
  type ReviewDialogueLine,
  type ReviewDialogueSpeaker,
  type ReviewRequest,
  type ReviewResponse,
  type ReviewRewriteSuggestion,
  type SimulationRequest,
  type SimulationResponse,
} from '@/data/week1'

interface RecordLike {
  [key: string]: unknown
}

interface ReviewContext {
  scenario: string
  conversationId?: string
  dialogue: ReviewDialogueLine[]
  roommateNames: Partial<Record<ReviewDialogueSpeaker, string>>
  original_event?: ReviewRequest['original_event']
}

interface ReviewSimulationCache {
  request: SimulationRequest
  response: SimulationResponse
  dialogue?: ReviewDialogueLine[]
}

interface StoredReviewCache {
  request: ReviewRequest
  response: ReviewResponse
  dialogue_fingerprint?: string
}

interface ReviewSnapshot {
  request: ReviewRequest
  response: ReviewResponse
  dialogue: ReviewDialogueLine[]
  roommateNames: ReviewContext['roommateNames']
}

const fallbackDialogueMessage = '请先明确你本次沟通希望对方做出的具体调整。'
const fallbackSystemDialogueMessage = '暂无模拟对话缓存，请先返回模拟页完成一次对话。'
const focusableSelector = [
  `button:not([disabled]):not([aria-disabled="true"])`,
  'a[href]',
  'textarea:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

const router = useRouter()
const reviewError = ref('')
const isLoading = ref(true)
const storedDialogue = ref<ReviewDialogueLine[]>([])
const storedRoommateNames = ref<ReviewContext['roommateNames']>({})
const reviewRequest = ref<ReviewRequest>({ scenario: '沟通复盘场景' })
const reviewResponse = ref<ReviewResponse>(
  buildDemoReviewResponse('复盘页初始化', reviewRequest.value),
)
const currentReviewSnapshot = ref<ReviewSnapshot | null>(null)
const reviewHistory = ref<ReviewReportSummary[]>([])
const reviewHistoryError = ref('')
const isHistoryLoading = ref(false)
const isReportSwitching = ref(false)
const activeReviewId = ref<string | null>(null)
const deletingReviewIds = ref<Set<string>>(new Set())
const pendingDeleteReviewId = ref<string | null>(null)
const isDialogueModalOpen = ref(false)
const dialogueModalRef = ref<HTMLElement | null>(null)
const dialogueTriggerRef = ref<HTMLButtonElement | null>(null)
const reviewExportError = ref('')
const animatedPerformanceScores = ref({ clarity: 0, empathy: 0, resolution: 0 })
let reviewScoresAnimationFrame = 0
let isReviewViewActive = false

function isRecord(value: unknown): value is RecordLike {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function requestFingerprint(value: ReviewRequest): string {
  return JSON.stringify({
    scenario: value.scenario,
    conversation_id: value.conversation_id,
    roommate_names: value.roommate_names,
    original_event: value.original_event,
  })
}

function dialogueFingerprint(dialogue: ReviewDialogueLine[]): string {
  return JSON.stringify(dialogue.slice(-50))
}

function hydrateStoredAnalysis(): AnalyzeResult | undefined {
  try {
    const raw = localStorage.getItem(ANALYSIS_RESULT_STORAGE_KEY)
    if (!raw) {
      return undefined
    }

    const parsed = JSON.parse(raw) as unknown
    if (isAnalyzeResult(parsed)) {
      return parsed
    }

    localStorage.removeItem(ANALYSIS_RESULT_STORAGE_KEY)
  } catch {
    // ignore malformed storage
  }

  return undefined
}

function hydrateStoredLastEvent(): AnalyzeRequest | null {
  try {
    const raw = localStorage.getItem(LAST_EVENT_STORAGE_KEY)
    if (!raw) {
      return null
    }

    const parsed = JSON.parse(raw) as unknown
    if (isRecord(parsed) && typeof parsed.event_type === 'string') {
      return {
        event_type: parsed.event_type,
        severity: Number(parsed.severity) || 1,
        frequency: typeof parsed.frequency === 'string' ? parsed.frequency : '',
        emotion: typeof parsed.emotion === 'string' ? parsed.emotion : '',
        has_communicated: parsed.has_communicated === true,
        has_conflict: parsed.has_conflict === true,
        description:
          typeof parsed.description === 'string' ? parsed.description : fallbackDialogueMessage,
      }
    }
  } catch {
    // ignore malformed storage
  }

  return null
}

function isSimulationReply(value: unknown): value is SimulationResponse['replies'][number] {
  return (
    isRecord(value) &&
    typeof value.roommate === 'string' &&
    typeof value.personality === 'string' &&
    typeof value.message === 'string' &&
    (typeof value.roommate_id === 'undefined' || typeof value.roommate_id === 'string')
  )
}

function isReviewDialogueLine(value: unknown): value is ReviewDialogueLine {
  return (
    isRecord(value) &&
    typeof value.speaker === 'string' &&
    typeof value.message === 'string' &&
    (value.speaker === 'user' ||
      value.speaker === 'system' ||
      value.speaker.startsWith('roommate_'))
  )
}

function isStoredSimulationResult(value: unknown): value is ReviewSimulationCache {
  if (!isRecord(value)) {
    return false
  }

  const request = value.request
  const response = value.response
  const dialogue = value.dialogue

  if (!isRecord(request) || !isRecord(response)) {
    return false
  }

  return (
    typeof request.scenario === 'string' &&
    (typeof request.user_message === 'undefined' || typeof request.user_message === 'string') &&
    Array.isArray(response.replies) &&
    response.replies.every(isSimulationReply) &&
    typeof response.safety_note === 'string' &&
    (typeof dialogue === 'undefined' ||
      (Array.isArray(dialogue) && dialogue.every(isReviewDialogueLine)))
  )
}

function buildOriginalEvent(
  analysis: AnalyzeResult | undefined,
  lastEvent: AnalyzeRequest | null,
): ReviewContext['original_event'] | undefined {
  const originalEvent: ReviewContext['original_event'] = {}

  if (analysis) {
    originalEvent.risk_level = analysis.risk_level
    originalEvent.pressure_score = analysis.pressure_score
  }

  if (lastEvent?.event_type) {
    const mappedEventType = mapEventTypeToAnalyzeApi(lastEvent.event_type)
    if (mappedEventType) {
      originalEvent.event_type = mappedEventType
    }
  }

  return Object.keys(originalEvent).length > 0 ? originalEvent : undefined
}

function buildDialogueFromSimulation(simulation: ReviewSimulationCache): ReviewDialogueLine[] {
  if (simulation.dialogue && simulation.dialogue.length > 0) {
    return [...simulation.dialogue]
  }

  const lines: ReviewDialogueLine[] = []
  const userMessage = simulation.request.user_message?.trim() ?? ''
  if (userMessage) {
    lines.push({ speaker: 'user', message: userMessage })
  }

  for (const reply of simulation.response.replies) {
    lines.push({
      speaker: mapRoommateToReviewSpeaker(reply.roommate, reply.roommate_id),
      message: reply.message,
    })
  }

  return lines
}

function buildRoommateNamesFromSimulation(
  simulation: ReviewSimulationCache,
): ReviewContext['roommateNames'] {
  const roommateNames: ReviewContext['roommateNames'] = {}

  if (Array.isArray(simulation.request.roommates)) {
    for (const roommate of simulation.request.roommates) {
      if (
        isRecord(roommate) &&
        typeof roommate.id === 'string' &&
        typeof roommate.name === 'string'
      ) {
        const roommateId = roommate.id.trim()
        const roommateName = roommate.name.trim()
        if (roommateId && roommateName) {
          roommateNames[roommateId as ReviewDialogueSpeaker] = roommateName
        }
      }
    }
  }

  for (const reply of simulation.response.replies) {
    const speaker = mapRoommateToReviewSpeaker(reply.roommate, reply.roommate_id)
    if (!roommateNames[speaker] && reply.roommate.trim()) {
      roommateNames[speaker] = reply.roommate.trim()
    }
  }

  return roommateNames
}

function hydrateReviewContext(): ReviewContext {
  const analysis = hydrateStoredAnalysis()
  const lastEvent = hydrateStoredLastEvent()
  let scenario = '沟通复盘场景'
  let conversationId: string | undefined
  let dialogue: ReviewDialogueLine[] = []
  let roommateNames: ReviewContext['roommateNames'] = {}

  try {
    const raw = localStorage.getItem(SIMULATION_RESULT_STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw) as unknown
      if (isStoredSimulationResult(parsed)) {
        scenario = parsed.request.scenario || scenario
        conversationId = parsed.response.conversation_id || parsed.request.conversation_id
        dialogue = buildDialogueFromSimulation(parsed)
        roommateNames = buildRoommateNamesFromSimulation(parsed)
      }
    }
  } catch {
    // ignore malformed simulation cache
  }

  if (!dialogue.length) {
    const eventHint =
      typeof lastEvent?.description === 'string' && lastEvent.description.length > 0
        ? lastEvent.description
        : fallbackSystemDialogueMessage
    dialogue = [
      {
        speaker: 'system',
        message: `未找到本轮模拟对话缓存。${eventHint}`,
      },
    ]
    scenario = lastEvent?.event_type ? '舍友沟通场景' : scenario
  }

  return {
    scenario,
    conversationId,
    dialogue,
    roommateNames,
    original_event: buildOriginalEvent(analysis, lastEvent),
  }
}

const reviewDialogue = computed(() => storedDialogue.value)
const dialogueStats = computed(() => {
  const dialogue = reviewDialogue.value
  return {
    userTurns: dialogue.filter((line) => line.speaker === 'user').length,
    roommateReplies: dialogue.filter((line) => line.speaker.startsWith('roommate_')).length,
  }
})
const hasVisibleReviewReport = computed(
  () => !isLoading.value && (currentReviewSnapshot.value !== null || activeReviewId.value !== null),
)
const canShowReviewWorkspace = computed(
  () =>
    !isLoading.value &&
    (hasVisibleReviewReport.value ||
      reviewHistory.value.length > 0 ||
      isHistoryLoading.value ||
      Boolean(reviewHistoryError.value)),
)
const suggestionCards = computed<ReviewRewriteSuggestion[]>(() =>
  reviewResponse.value.rewrite_suggestions.length > 0
    ? reviewResponse.value.rewrite_suggestions
    : buildDemoReviewResponse('本地兜底建议', reviewRequest.value).rewrite_suggestions,
)
const activeReportKey = computed(
  () => activeReviewId.value ?? `current-${requestFingerprint(reviewRequest.value)}`,
)
const currentReportRail = computed(() => ({
  scenario: currentReviewSnapshot.value?.request.scenario || reviewRequest.value.scenario,
  summary: currentReviewSnapshot.value?.response.summary || reviewResponse.value.summary,
}))
const visibleReviewHistory = computed<ReviewReportSummary[]>(() => {
  const duplicateId = findCurrentReportDuplicateId()
  if (!duplicateId) {
    return reviewHistory.value
  }

  return reviewHistory.value.filter((report) => report.id !== duplicateId)
})
const practiceMessage = computed(() => {
  const rewritten = reviewResponse.value.rewritten_message.trim()
  if (rewritten) {
    return rewritten
  }

  return suggestionCards.value[0]?.suggested_message.trim() ?? ''
})
const communicationPlanItems = computed(() => [
  {
    icon: 'waving_hand',
    title: '开场白',
    text: reviewResponse.value.communication_plan.opening,
  },
  {
    icon: 'task_alt',
    title: '具体请求',
    text: reviewResponse.value.communication_plan.specific_request,
  },
  {
    icon: 'support_agent',
    title: '兜底方案',
    text: reviewResponse.value.communication_plan.fallback_plan,
  },
])

function normalizeReviewScore(value: number): number {
  if (!Number.isFinite(value)) {
    return 0
  }

  return Math.max(0, Math.min(100, Math.round(value)))
}

function prefersReducedMotion() {
  return (
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  )
}

function targetPerformanceScores() {
  return {
    clarity: normalizeReviewScore(reviewResponse.value.performance_scores.clarity),
    empathy: normalizeReviewScore(reviewResponse.value.performance_scores.empathy),
    resolution: normalizeReviewScore(reviewResponse.value.performance_scores.resolution),
  }
}

function cancelReviewScoreAnimation() {
  if (reviewScoresAnimationFrame) {
    window.cancelAnimationFrame(reviewScoresAnimationFrame)
    reviewScoresAnimationFrame = 0
  }
}

function applyFinalReviewScores() {
  animatedPerformanceScores.value = targetPerformanceScores()
}

function animateReviewScores() {
  if (!isReviewViewActive) {
    return
  }

  cancelReviewScoreAnimation()

  if (prefersReducedMotion()) {
    applyFinalReviewScores()
    return
  }

  animatedPerformanceScores.value = { clarity: 0, empathy: 0, resolution: 0 }

  const targetScores = targetPerformanceScores()
  const durationMs = 720
  const startTime = window.performance.now()

  const step = (currentTime: number) => {
    if (!isReviewViewActive) {
      reviewScoresAnimationFrame = 0
      return
    }

    const progress = Math.min(1, (currentTime - startTime) / durationMs)
    const easedProgress = 1 - (1 - progress) ** 3
    animatedPerformanceScores.value = {
      clarity: Math.round(targetScores.clarity * easedProgress),
      empathy: Math.round(targetScores.empathy * easedProgress),
      resolution: Math.round(targetScores.resolution * easedProgress),
    }

    if (progress < 1) {
      reviewScoresAnimationFrame = window.requestAnimationFrame(step)
    } else {
      reviewScoresAnimationFrame = 0
    }
  }

  reviewScoresAnimationFrame = window.requestAnimationFrame(step)
}

function hydrateStoredReview(
  payload: ReviewRequest,
  dialogue: ReviewDialogueLine[],
): ReviewResponse | null {
  const clearStoredReview = () => {
    try {
      localStorage.removeItem(REVIEW_RESULT_STORAGE_KEY)
    } catch {
      // ignore restricted storage
    }
  }

  try {
    const raw = localStorage.getItem(REVIEW_RESULT_STORAGE_KEY)
    if (!raw) {
      return null
    }

    const parsed = JSON.parse(raw) as unknown
    if (!isStoredReviewResult(parsed)) {
      clearStoredReview()
      return null
    }
    if (parsed.response.is_demo) {
      clearStoredReview()
      return null
    }

    const storedReview = parsed as StoredReviewCache
    const storedDialogueFingerprint =
      storedReview.dialogue_fingerprint ?? dialogueFingerprint(storedReview.request.dialogue ?? [])

    if (
      requestFingerprint(parsed.request) !== requestFingerprint(payload) ||
      storedDialogueFingerprint !== dialogueFingerprint(dialogue)
    ) {
      clearStoredReview()
      return null
    }

    return parsed.response
  } catch {
    clearStoredReview()
  }

  return null
}

const scoreCards = computed(() => [
  {
    title: 'Clarity',
    value: normalizeReviewScore(reviewResponse.value.performance_scores.clarity),
    animatedValue: animatedPerformanceScores.value.clarity,
    description: '表达清晰度',
    tone: 'clarity',
  },
  {
    title: 'Empathy',
    value: normalizeReviewScore(reviewResponse.value.performance_scores.empathy),
    animatedValue: animatedPerformanceScores.value.empathy,
    description: '共情能力',
    tone: 'empathy',
  },
  {
    title: 'Resolution',
    value: normalizeReviewScore(reviewResponse.value.performance_scores.resolution),
    animatedValue: animatedPerformanceScores.value.resolution,
    description: '问题解决度',
    tone: 'resolution',
  },
])

function toSafeArray(value: string[]): string[] {
  return value.length > 0 ? value : ['暂无数据']
}

function dialogueSpeakerLabel(speaker: ReviewDialogueLine['speaker']) {
  if (speaker === 'user') {
    return '你'
  }

  if (speaker === 'system') {
    return '系统提示'
  }

  return storedRoommateNames.value[speaker] ?? speaker.replace('roommate_', '舍友 ').toUpperCase()
}

function dialogueSpeakerInitial(speaker: ReviewDialogueLine['speaker']) {
  if (speaker === 'user') {
    return '你'
  }

  if (speaker === 'system') {
    return 'S'
  }

  const label = storedRoommateNames.value[speaker] ?? ''
  if (label) {
    const compactLabel = label.replace(/^舍友\s*/, '').trim()
    return (compactLabel || label).slice(-2)
  }

  const suffix = speaker.replace('roommate_', '').trim()
  return (
    suffix
      .replace(/^custom_?/i, '')
      .slice(-2)
      .toUpperCase() || 'AI'
  )
}

function originalMessageLabel(suggestion: ReviewRewriteSuggestion) {
  return suggestion.original_message.trim() || '未定位到原句'
}

function getModalFocusableElements(modalRef: HTMLElement | null) {
  return Array.from(modalRef?.querySelectorAll<HTMLElement>(focusableSelector) ?? []).filter(
    (element) => !element.hasAttribute('disabled') && element.tabIndex !== -1,
  )
}

function createReviewSnapshot(): ReviewSnapshot {
  return {
    request: { ...reviewRequest.value },
    response: {
      ...reviewResponse.value,
      strengths: [...reviewResponse.value.strengths],
      risks: [...reviewResponse.value.risks],
      performance_scores: { ...reviewResponse.value.performance_scores },
      rewrite_suggestions: reviewResponse.value.rewrite_suggestions.map((suggestion) => ({
        ...suggestion,
      })),
      next_steps: [...reviewResponse.value.next_steps],
      communication_plan: { ...reviewResponse.value.communication_plan },
    },
    dialogue: [...storedDialogue.value],
    roommateNames: { ...storedRoommateNames.value },
  }
}

function applyReviewSnapshot(snapshot: ReviewSnapshot, reviewId: string | null) {
  reviewRequest.value = { ...snapshot.request }
  reviewResponse.value = {
    ...snapshot.response,
    strengths: [...snapshot.response.strengths],
    risks: [...snapshot.response.risks],
    performance_scores: { ...snapshot.response.performance_scores },
    rewrite_suggestions: snapshot.response.rewrite_suggestions.map((suggestion) => ({
      ...suggestion,
    })),
    next_steps: [...snapshot.response.next_steps],
    communication_plan: { ...snapshot.response.communication_plan },
  }
  storedDialogue.value = [...snapshot.dialogue]
  storedRoommateNames.value = { ...snapshot.roommateNames }
  activeReviewId.value = reviewId
  reviewExportError.value = ''
}

function dialogueFromReportDetail(detail: ReviewReportDetail): ReviewDialogueLine[] {
  if (detail.dialogue.length > 0) {
    return [...detail.dialogue]
  }

  if (detail.request.dialogue && detail.request.dialogue.length > 0) {
    return [...detail.request.dialogue]
  }

  return [
    {
      speaker: 'system',
      message: '历史记录缺少对话快照。',
    },
  ]
}

function hasReviewableDialogue(dialogue: ReviewDialogueLine[]) {
  return dialogue.some((line) => line.speaker === 'user')
}

function snapshotFromReportDetail(detail: ReviewReportDetail): ReviewSnapshot {
  return {
    request: detail.request,
    response: detail.response,
    dialogue: dialogueFromReportDetail(detail),
    roommateNames: detail.request.roommate_names ?? {},
  }
}

function formatReviewTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return '时间未知'
  }

  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

function reportAverageScore(report: ReviewReportSummary) {
  return Math.round((report.score_clarity + report.score_empathy + report.score_resolution) / 3)
}

function reportMatchesCurrentSnapshot(report: ReviewReportSummary, snapshot: ReviewSnapshot) {
  return (
    report.conversation_id === (snapshot.request.conversation_id ?? null) &&
    report.scenario === snapshot.request.scenario &&
    report.summary === snapshot.response.summary &&
    report.score_clarity === normalizeReviewScore(snapshot.response.performance_scores.clarity) &&
    report.score_empathy === normalizeReviewScore(snapshot.response.performance_scores.empathy) &&
    report.score_resolution ===
      normalizeReviewScore(snapshot.response.performance_scores.resolution)
  )
}

function findCurrentReportDuplicateId() {
  const snapshot = currentReviewSnapshot.value
  if (!snapshot) {
    return null
  }

  const duplicateReport = reviewHistory.value.find((report) =>
    reportMatchesCurrentSnapshot(report, snapshot),
  )
  return duplicateReport?.id ?? null
}

async function loadReviewHistory() {
  isHistoryLoading.value = true
  reviewHistoryError.value = ''

  try {
    const result = await fetchReviewHistory(20)
    reviewHistory.value = result.reports
    if (
      pendingDeleteReviewId.value &&
      !result.reports.some((report) => report.id === pendingDeleteReviewId.value)
    ) {
      pendingDeleteReviewId.value = null
    }
  } catch (error) {
    reviewHistoryError.value =
      error instanceof Error && error.message ? error.message : '复盘历史加载失败'
  } finally {
    isHistoryLoading.value = false
  }
}

async function selectHistoryReport(report: ReviewReportSummary) {
  if (activeReviewId.value === report.id || isReportSwitching.value) {
    return
  }

  isReportSwitching.value = true
  reviewHistoryError.value = ''

  try {
    const detail = await fetchReviewReport(report.id)
    applyReviewSnapshot(snapshotFromReportDetail(detail), detail.id)
    await nextTick()
    animateReviewScores()
  } catch (error) {
    reviewHistoryError.value =
      error instanceof Error && error.message ? error.message : '复盘报告加载失败'
  } finally {
    isReportSwitching.value = false
  }
}

async function selectFirstHistoryReportIfNeeded() {
  if (currentReviewSnapshot.value || activeReviewId.value || reviewHistory.value.length === 0) {
    return
  }

  const firstReport = reviewHistory.value[0]
  if (firstReport) {
    await selectHistoryReport(firstReport)
  }
}

function setHistoryDeletingState(reportId: string, isDeleting: boolean) {
  const nextIds = new Set(deletingReviewIds.value)
  if (isDeleting) {
    nextIds.add(reportId)
  } else {
    nextIds.delete(reportId)
  }
  deletingReviewIds.value = nextIds
}

function isDeletingHistoryReport(reportId: string) {
  return deletingReviewIds.value.has(reportId)
}

function isPendingDeleteHistoryReport(reportId: string) {
  return pendingDeleteReviewId.value === reportId
}

async function selectFallbackReportAfterDelete(deletedReportId: string) {
  if (activeReviewId.value !== deletedReportId) {
    return
  }

  if (currentReviewSnapshot.value) {
    applyReviewSnapshot(currentReviewSnapshot.value, null)
    await nextTick()
    animateReviewScores()
    return
  }

  activeReviewId.value = null
  const firstReport = reviewHistory.value[0]
  if (firstReport) {
    await selectHistoryReport(firstReport)
  }
}

async function deleteHistoryReport(report: ReviewReportSummary) {
  if (isDeletingHistoryReport(report.id)) {
    return
  }

  if (pendingDeleteReviewId.value !== report.id) {
    pendingDeleteReviewId.value = report.id
    return
  }

  setHistoryDeletingState(report.id, true)
  reviewHistoryError.value = ''

  try {
    await deleteReviewReport(report.id)
    reviewHistory.value = reviewHistory.value.filter(
      (historyReport) => historyReport.id !== report.id,
    )
    pendingDeleteReviewId.value = null
    await selectFallbackReportAfterDelete(report.id)
  } catch (error) {
    pendingDeleteReviewId.value = null
    reviewHistoryError.value =
      error instanceof Error && error.message ? error.message : '复盘历史删除失败'
  } finally {
    setHistoryDeletingState(report.id, false)
  }
}

async function restoreCurrentReport() {
  if (!currentReviewSnapshot.value || activeReviewId.value === null || isReportSwitching.value) {
    return
  }

  isReportSwitching.value = true
  applyReviewSnapshot(currentReviewSnapshot.value, null)
  await nextTick()
  animateReviewScores()
  isReportSwitching.value = false
}

function openDialogueModal() {
  isDialogueModalOpen.value = true
  nextTick(() => {
    const firstFocusable = getModalFocusableElements(dialogueModalRef.value)[0]
    if (firstFocusable) {
      firstFocusable.focus()
      return
    }

    dialogueModalRef.value?.focus()
  })
}

function closeDialogueModal() {
  isDialogueModalOpen.value = false
}

function handleDialogueModalAfterLeave() {
  dialogueTriggerRef.value?.focus()
}

function handleDialogueModalKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    event.preventDefault()
    closeDialogueModal()
    return
  }

  if (event.key !== 'Tab') {
    return
  }

  const focusableElements = getModalFocusableElements(dialogueModalRef.value)
  if (focusableElements.length === 0) {
    event.preventDefault()
    dialogueModalRef.value?.focus()
    return
  }

  const firstElement = focusableElements[0]!
  const lastElement = focusableElements[focusableElements.length - 1]!
  const activeElement = document.activeElement

  if (!focusableElements.includes(activeElement as HTMLElement)) {
    event.preventDefault()
    firstElement.focus()
    return
  }

  if (event.shiftKey && activeElement === firstElement) {
    event.preventDefault()
    lastElement.focus()
    return
  }

  if (!event.shiftKey && activeElement === lastElement) {
    event.preventDefault()
    firstElement.focus()
  }
}

function markdownList(items: string[]) {
  return toSafeArray(items)
    .map((item) => `- ${item}`)
    .join('\n')
}

function markdownDialogue() {
  if (!reviewDialogue.value.length) {
    return '- 暂无对话记录'
  }

  return reviewDialogue.value
    .map((line, index) => `${index + 1}. ${dialogueSpeakerLabel(line.speaker)}：${line.message}`)
    .join('\n')
}

function buildReviewMarkdown() {
  const scores = reviewResponse.value.performance_scores
  const suggestionText = suggestionCards.value
    .map(
      (suggestion, index) =>
        `${index + 1}. 原话：${originalMessageLabel(suggestion)}\n   推荐话术：${suggestion.suggested_message}\n   原因：${suggestion.reason}`,
    )
    .join('\n')
  const communicationPlan = reviewResponse.value.communication_plan

  return [
    `# 沟通复盘报告`,
    ``,
    `## Scenario`,
    reviewRequest.value.scenario || '沟通复盘场景',
    ``,
    `## Dialogue`,
    markdownDialogue(),
    ``,
    `## 评分`,
    `- Clarity：${normalizeReviewScore(scores.clarity)}%`,
    `- Empathy：${normalizeReviewScore(scores.empathy)}%`,
    `- Resolution：${normalizeReviewScore(scores.resolution)}%`,
    ``,
    `## Summary`,
    reviewResponse.value.summary,
    ``,
    `## Strengths`,
    markdownList(reviewResponse.value.strengths),
    ``,
    `## Risks`,
    markdownList(reviewResponse.value.risks),
    ``,
    `## 原话 vs 推荐话术`,
    suggestionText,
    ``,
    `## Communication Plan`,
    `- 开场白：${communicationPlan.opening}`,
    `- 具体请求：${communicationPlan.specific_request}`,
    `- 兜底方案：${communicationPlan.fallback_plan}`,
    ``,
    `## Next Steps`,
    markdownList(reviewResponse.value.next_steps),
    ``,
    `## Safety Note`,
    reviewResponse.value.safety_note,
    ``,
  ].join('\n')
}

function reviewFileStamp() {
  return new Date().toISOString().replace(/[:.]/g, '-')
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

function exportReviewMarkdown() {
  reviewExportError.value = ''
  const blob = new Blob([buildReviewMarkdown()], { type: 'text/markdown;charset=utf-8' })
  downloadBlob(blob, `review-report-${reviewFileStamp()}.md`)
}

function practiceAgain() {
  void router.push({
    name: 'simulate',
    query: {
      scenario: reviewRequest.value.scenario,
      practice: practiceMessage.value,
    },
  })
}

async function initReview() {
  isLoading.value = true
  reviewError.value = ''
  reviewHistoryError.value = ''
  activeReviewId.value = null

  const context = hydrateReviewContext()
  storedDialogue.value = context.dialogue
  storedRoommateNames.value = context.roommateNames
  reviewRequest.value = {
    scenario: context.scenario,
    conversation_id: context.conversationId,
    dialogue: context.conversationId ? undefined : context.dialogue.slice(-50),
    roommate_names: context.roommateNames,
    original_event: context.original_event,
  }

  await loadReviewHistory()

  if (!hasReviewableDialogue(context.dialogue)) {
    reviewError.value = '本轮没有可复盘的模拟对话，未生成新的复盘报告。'
    currentReviewSnapshot.value = null
    isLoading.value = false
    await selectFirstHistoryReportIfNeeded()
    return
  }

  const cached = hydrateStoredReview(reviewRequest.value, context.dialogue)
  if (cached) {
    reviewResponse.value = cached
    currentReviewSnapshot.value = createReviewSnapshot()
    isLoading.value = false
    await nextTick()
    animateReviewScores()
    return
  }

  try {
    const result = await submitReviewRequest(reviewRequest.value)
    reviewResponse.value = result
    currentReviewSnapshot.value = createReviewSnapshot()
    isLoading.value = false
    await nextTick()
    animateReviewScores()
    await loadReviewHistory()

    if (result.is_demo) {
      return
    }

    try {
      localStorage.setItem(
        REVIEW_RESULT_STORAGE_KEY,
        JSON.stringify({
          request: reviewRequest.value,
          response: result,
          dialogue_fingerprint: dialogueFingerprint(context.dialogue),
        }),
      )
    } catch {
      // restricted browser sessions may block storage writes
    }
  } catch (error) {
    reviewError.value =
      error instanceof Error && error.message ? error.message : '复盘生成失败，请返回模拟页后重试'
    await selectFirstHistoryReportIfNeeded()
  } finally {
    if (isLoading.value) {
      isLoading.value = false
    }
  }
}

onMounted(() => {
  isReviewViewActive = true
  void initReview()
})

onBeforeUnmount(() => {
  isReviewViewActive = false
  cancelReviewScoreAnimation()
})
</script>

<template>
  <main class="page review-page review-v2-page">
    <span class="review-bg-ball review-bg-ball-yellow bounce-float" aria-hidden="true"></span>

    <div class="review-v2-shell">
      <header class="review-v2-header page-pop-in">
        <h1>沟通复盘报告</h1>
        <span aria-hidden="true"></span>
      </header>

      <section class="review-dialogue-context pop-card pop-shadow page-pop-in">
        <div>
          <h2>本次复盘基于完整模拟对话</h2>
          <p>场景：{{ reviewRequest.scenario || '沟通复盘场景' }}</p>
          <p>
            {{
              reviewRequest.conversation_id
                ? '已连接本轮模拟记录。'
                : '未找到本轮模拟记录，请返回模拟页重新演练。'
            }}
          </p>
        </div>
      </section>

      <article class="review-dialogue-entry-card pop-card pop-shadow page-pop-in">
        <span class="material-symbol" aria-hidden="true">forum</span>
        <div>
          <h2>完整对话记录</h2>
          <p>
            {{ dialogueStats.userTurns }} 轮用户表达 ·
            {{ dialogueStats.roommateReplies }} 条舍友反馈
          </p>
        </div>
        <button
          ref="dialogueTriggerRef"
          class="secondary-action pop-shadow"
          type="button"
          @click="openDialogueModal"
        >
          查看完整对话
        </button>
      </article>

      <Transition name="review-state-transition" mode="out-in">
        <p v-if="isLoading" key="loading" class="review-state-pill pop-shadow">正在生成复盘...</p>
        <p
          v-else-if="reviewError"
          key="error"
          class="review-state-pill review-state-error pop-shadow"
        >
          {{ reviewError }}
        </p>
        <p v-else-if="reviewResponse.is_demo" key="demo" class="review-state-pill pop-shadow">
          {{ reviewResponse.demo_notice || '演示复盘（未接入后端）' }}
        </p>
      </Transition>

      <Transition name="review-result-transition" mode="out-in">
        <div v-if="canShowReviewWorkspace" class="review-workspace">
          <section class="review-history-strip pop-card pop-shadow" aria-label="复盘历史">
            <header>
              <span class="material-symbol" aria-hidden="true">history</span>
              <div>
                <h2>历史复盘</h2>
                <p>
                  {{ isHistoryLoading ? '正在同步...' : `最近 ${visibleReviewHistory.length} 条` }}
                </p>
              </div>
            </header>

            <TransitionGroup name="review-history-card" tag="div" class="review-history-list">
              <article
                v-if="currentReviewSnapshot"
                key="current-report"
                class="review-history-card"
              >
                <button
                  class="review-history-item"
                  :class="{ active: activeReviewId === null }"
                  type="button"
                  :disabled="isReportSwitching"
                  @click="restoreCurrentReport"
                >
                  <span class="review-history-score">当前</span>
                  <span>
                    <strong>{{ currentReportRail.scenario || '当前复盘报告' }}</strong>
                    <small>{{ currentReportRail.summary }}</small>
                  </span>
                </button>
              </article>

              <article
                v-for="report in visibleReviewHistory"
                :key="report.id"
                class="review-history-card"
              >
                <button
                  class="review-history-item"
                  :class="{ active: activeReviewId === report.id }"
                  type="button"
                  :disabled="isReportSwitching || isDeletingHistoryReport(report.id)"
                  @click="selectHistoryReport(report)"
                >
                  <span class="review-history-score">{{ reportAverageScore(report) }}</span>
                  <span>
                    <strong>{{ report.scenario }}</strong>
                    <small>{{ formatReviewTime(report.created_at) }} · {{ report.summary }}</small>
                  </span>
                </button>
                <button
                  class="review-history-delete"
                  :class="{ pending: isPendingDeleteHistoryReport(report.id) }"
                  type="button"
                  :aria-label="
                    isPendingDeleteHistoryReport(report.id)
                      ? `再次点击删除历史复盘：${report.scenario}`
                      : `删除历史复盘：${report.scenario}`
                  "
                  :title="isPendingDeleteHistoryReport(report.id) ? '再次点击删除' : '删除'"
                  :disabled="isReportSwitching || isDeletingHistoryReport(report.id)"
                  @click="deleteHistoryReport(report)"
                >
                  <span class="material-symbol" aria-hidden="true">
                    {{
                      isDeletingHistoryReport(report.id)
                        ? 'hourglass_top'
                        : isPendingDeleteHistoryReport(report.id)
                          ? 'delete_forever'
                          : 'delete'
                    }}
                  </span>
                </button>
              </article>
            </TransitionGroup>

            <p v-if="reviewHistoryError" class="review-history-error">
              {{ reviewHistoryError }}
            </p>
          </section>

          <Transition name="review-report-switch" mode="out-in">
            <div
              v-if="hasVisibleReviewReport"
              :key="activeReportKey"
              class="review-result-stack review-report-export-surface"
            >
              <section class="review-v2-section">
                <h2>表现总结</h2>
                <p class="review-summary-inline pop-card pop-shadow">
                  {{ reviewResponse.summary }}
                </p>
                <div class="review-score-grid">
                  <article
                    v-for="(card, index) in scoreCards"
                    :key="card.title"
                    :class="[
                      'review-score-card',
                      'review-card-reveal-item',
                      `review-score-card-${card.tone}`,
                    ]"
                    :style="{ '--review-card-delay': `${index * 80}ms` }"
                  >
                    <span aria-hidden="true"></span>
                    <div class="review-score-ring">
                      <strong>{{ card.animatedValue }}%</strong>
                    </div>
                    <h3>{{ card.title }}</h3>
                    <p>{{ card.description }}</p>
                  </article>
                </div>
              </section>

              <div class="review-squiggle" aria-hidden="true"></div>

              <section class="review-v2-section">
                <h2>闪光点与注意点</h2>
                <div class="review-highlight-grid">
                  <article
                    class="review-sticker-card review-sticker-good review-card-reveal-item pop-card pop-shadow"
                    style="--review-card-delay: 180ms"
                  >
                    <div class="review-sticker-badge">
                      <span class="material-symbol" aria-hidden="true">thumb_up</span>
                    </div>
                    <h3>本次表达的优点</h3>
                    <ul>
                      <li
                        v-for="item in toSafeArray(reviewResponse.strengths)"
                        :key="`strength-${item}`"
                      >
                        {{ item }}
                      </li>
                    </ul>
                  </article>

                  <article
                    class="review-sticker-card review-sticker-risk review-card-reveal-item pop-card pop-shadow"
                    style="--review-card-delay: 260ms"
                  >
                    <div class="review-sticker-badge">
                      <span class="material-symbol" aria-hidden="true">priority_high</span>
                    </div>
                    <h3>可能引发防御心理的表述</h3>
                    <ul>
                      <li v-for="item in toSafeArray(reviewResponse.risks)" :key="`risk-${item}`">
                        {{ item }}
                      </li>
                    </ul>
                  </article>
                </div>
              </section>

              <div class="review-squiggle" aria-hidden="true"></div>

              <section class="review-v2-section review-script-section">
                <h2>原话 vs 推荐话术</h2>
                <TransitionGroup name="review-suggestion" tag="div" class="review-suggestion-list">
                  <article
                    v-for="(suggestion, index) in suggestionCards"
                    :key="`${suggestion.message_index}-${suggestion.original_message}-${index}`"
                    class="review-suggestion-card review-script-card pop-card pop-shadow"
                    :style="{ '--review-card-delay': `${index * 90}ms` }"
                  >
                    <header>
                      <span>第 {{ suggestion.message_index + 1 }} 条用户表达</span>
                      <strong>{{ suggestion.issue }}</strong>
                    </header>
                    <div class="speech-rewrite-row">
                      <article class="speech-before">
                        <p class="rewrite-label">原表达</p>
                        <p>“{{ originalMessageLabel(suggestion) }}”</p>
                      </article>
                      <div class="speech-arrow" aria-hidden="true">
                        <span class="material-symbol">arrow_forward</span>
                      </div>
                      <article class="speech-after">
                        <p class="rewrite-label">推荐话术</p>
                        <p>“{{ suggestion.suggested_message }}”</p>
                      </article>
                    </div>
                    <p class="review-suggestion-reason">{{ suggestion.reason }}</p>
                  </article>
                </TransitionGroup>
              </section>

              <section class="review-v2-section review-plan-section">
                <h2>沟通计划</h2>
                <div class="review-plan-grid">
                  <article
                    v-for="item in communicationPlanItems"
                    :key="item.title"
                    class="review-plan-card pop-card pop-shadow"
                  >
                    <span class="material-symbol" aria-hidden="true">{{ item.icon }}</span>
                    <h3>{{ item.title }}</h3>
                    <p>{{ item.text }}</p>
                  </article>
                </div>
              </section>

              <section class="review-bottom-grid">
                <article class="review-block pop-card pop-shadow">
                  <h2>后续行动建议</h2>
                  <ul>
                    <li
                      v-for="item in toSafeArray(reviewResponse.next_steps)"
                      :key="`next-${item}`"
                    >
                      {{ item }}
                    </li>
                  </ul>
                </article>
              </section>

              <p class="review-note">
                {{
                  reviewResponse.safety_note ||
                  '本建议仅用于沟通练习，不作为心理诊断依据；如存在现实安全风险，请优先寻求线下支持。'
                }}
              </p>
            </div>
            <section v-else key="empty-history-selection" class="review-block pop-card pop-shadow">
              <h2>选择历史复盘</h2>
              <p>本轮未生成新的复盘报告，可以从上方历史列表打开已保存的报告。</p>
            </section>
          </Transition>

          <section class="review-actions">
            <button
              v-if="hasVisibleReviewReport"
              class="primary-action pop-shadow"
              type="button"
              @click="practiceAgain"
            >
              再次演练
              <span class="action-icon material-symbol">refresh</span>
            </button>
            <button
              v-if="hasVisibleReviewReport"
              class="secondary-action pop-shadow"
              type="button"
              @click="exportReviewMarkdown"
            >
              导出 Markdown
              <span class="action-icon material-symbol">download</span>
            </button>
            <RouterLink class="secondary-action pop-shadow" :to="{ name: 'analysis' }">
              查看压力分析
              <span class="action-icon material-symbol">analytics</span>
            </RouterLink>
            <RouterLink class="secondary-action pop-shadow" :to="{ name: 'archive' }">
              返回事件档案
              <span class="action-icon material-symbol">archive</span>
            </RouterLink>
          </section>
          <p v-if="reviewExportError" class="review-export-error">{{ reviewExportError }}</p>
        </div>
      </Transition>
    </div>

    <Transition name="review-dialogue-modal" @after-leave="handleDialogueModalAfterLeave">
      <div
        v-if="isDialogueModalOpen"
        class="safety-modal-overlay review-dialogue-modal-overlay"
        role="presentation"
        @click.self="closeDialogueModal"
      >
        <section
          ref="dialogueModalRef"
          class="safety-modal review-dialogue-modal pop-card pop-shadow"
          role="dialog"
          aria-modal="true"
          aria-labelledby="review-dialogue-modal-title"
          tabindex="-1"
          @keydown="handleDialogueModalKeydown"
        >
          <button
            class="modal-close material-symbol"
            type="button"
            aria-label="关闭完整对话记录"
            @click="closeDialogueModal"
          >
            close
          </button>
          <h2 id="review-dialogue-modal-title">完整对话记录</h2>
          <p class="review-dialogue-modal-subtitle">
            {{ dialogueStats.userTurns }} 轮用户表达 ·
            {{ dialogueStats.roommateReplies }} 条舍友反馈
          </p>
          <div class="review-dialogue-list review-dialogue-modal-list">
            <article
              v-for="(line, index) in reviewDialogue"
              :key="`${line.speaker}-${index}-${line.message}`"
              :class="['review-dialogue-row', { 'review-dialogue-user': line.speaker === 'user' }]"
            >
              <div
                v-if="line.speaker !== 'user'"
                :class="[
                  'review-dialogue-avatar',
                  `review-dialogue-avatar-${dialogueSpeakerInitial(line.speaker).toLowerCase()}`,
                ]"
                aria-hidden="true"
              >
                {{ dialogueSpeakerInitial(line.speaker) }}
              </div>
              <p>
                <span>{{ dialogueSpeakerLabel(line.speaker) }}</span>
                “{{ line.message }}”
              </p>
            </article>
          </div>
        </section>
      </div>
    </Transition>
  </main>
</template>

<style scoped>
.review-v2-shell {
  width: min(1180px, 100%);
}

.review-dialogue-entry-card {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 14px;
  min-width: min(100%, 420px);
  margin: -24px 0 36px;
  border: 4px solid var(--ink);
  background: var(--surface-container-low);
  padding: 16px;
}

.review-dialogue-entry-card > .material-symbol {
  display: inline-grid;
  width: 44px;
  height: 44px;
  place-items: center;
  border: 3px solid var(--ink);
  border-radius: 999px;
  background: var(--secondary-soft);
  box-shadow: 2px 2px 0 0 var(--shadow-dark);
}

.review-dialogue-entry-card h2,
.review-dialogue-entry-card p {
  margin: 0;
}

.review-dialogue-entry-card h2 {
  font-size: var(--font-body-lg);
}

.review-dialogue-entry-card p {
  color: var(--ink-soft);
  font-size: 0.88rem;
  font-weight: 800;
}

.review-dialogue-entry-card .secondary-action {
  min-height: 42px;
  white-space: nowrap;
}

.review-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  align-items: start;
  gap: 24px;
}

.review-history-strip {
  display: grid;
  gap: 14px;
  min-width: 0;
  border: 4px solid var(--ink);
  background: var(--card);
  padding: 16px;
  overflow: hidden;
}

.review-history-strip.pop-shadow:hover {
  box-shadow: 4px 4px 0 0 var(--shadow-dark);
  transform: none;
}

.review-history-strip header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.review-history-strip header > .material-symbol {
  display: inline-grid;
  width: 38px;
  height: 38px;
  place-items: center;
  border: 3px solid var(--ink);
  border-radius: 10px;
  background: var(--tertiary);
  box-shadow: 2px 2px 0 0 var(--shadow-dark);
}

.review-history-strip h2,
.review-history-strip p {
  margin: 0;
}

.review-history-strip h2 {
  font-size: 1.1rem;
}

.review-history-strip header p {
  color: var(--ink-soft);
  font-size: 0.78rem;
  font-weight: 800;
}

.review-history-list {
  position: relative;
  display: grid;
  grid-auto-flow: column;
  grid-auto-columns: minmax(220px, 280px);
  gap: 12px;
  overflow-x: auto;
  overflow-y: hidden;
  padding: 2px 4px 8px 2px;
  scroll-snap-type: x proximity;
}

.review-history-card {
  position: relative;
  min-width: 0;
  scroll-snap-align: start;
}

.review-history-card-enter-active,
.review-history-card-leave-active,
.review-history-card-move {
  transition:
    opacity 180ms ease,
    transform 220ms cubic-bezier(0.2, 0, 0, 1);
}

.review-history-card-enter-from,
.review-history-card-leave-to {
  opacity: 0;
  transform: translateY(-8px) scale(0.96);
}

.review-history-card-leave-active {
  position: absolute;
  width: min(280px, calc(100vw - 64px));
}

.review-history-item {
  display: grid;
  grid-template-columns: 48px minmax(0, 1fr);
  align-items: center;
  gap: 10px;
  width: 100%;
  border: 3px solid var(--ink);
  border-radius: 12px;
  background: var(--surface-container-low);
  box-shadow: 2px 2px 0 0 var(--shadow-dark);
  color: var(--ink);
  min-height: 86px;
  padding: 10px 46px 10px 10px;
  text-align: left;
  transition:
    background-color 180ms ease,
    box-shadow 180ms ease,
    transform 180ms cubic-bezier(0.34, 1.56, 0.64, 1);
}

.review-history-item:hover:not(:disabled),
.review-history-item.active {
  background: var(--primary-container);
  color: #ffffff;
  box-shadow: 4px 4px 0 0 var(--shadow-dark);
  transform: translate(-2px, -2px);
}

.review-history-item:disabled {
  cursor: wait;
  opacity: 0.7;
}

.review-history-delete {
  position: absolute;
  top: 10px;
  right: 10px;
  display: inline-grid;
  width: 32px;
  height: 32px;
  place-items: center;
  border: 2px solid var(--ink);
  border-radius: 10px;
  background: var(--card);
  box-shadow: 2px 2px 0 0 var(--shadow-dark);
  color: var(--ink);
  transition:
    background-color 180ms ease,
    transform 180ms ease;
}

.review-history-delete:hover:not(:disabled) {
  background: var(--error-soft);
  color: var(--error);
  transform: translate(-1px, -1px);
}

.review-history-delete.pending {
  background: var(--error-soft);
  color: var(--error);
}

.review-history-delete:disabled {
  cursor: wait;
  opacity: 0.68;
}

.review-history-delete .material-symbol {
  font-size: 1.1rem;
}

.review-history-score {
  display: inline-grid;
  min-height: 42px;
  place-items: center;
  border: 2px solid currentColor;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.72);
  color: var(--ink);
  font-size: 0.82rem;
  font-weight: 900;
}

.review-history-item strong,
.review-history-item small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
}

.review-history-item strong {
  white-space: nowrap;
}

.review-history-item small {
  display: -webkit-box;
  margin-top: 4px;
  color: inherit;
  opacity: 0.78;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-height: 1.35;
}

.review-history-error,
.review-export-error {
  margin: 0;
  border: 3px solid var(--ink);
  border-radius: 12px;
  background: var(--error-soft);
  color: var(--error);
  padding: 10px 12px;
  font-weight: 800;
}

.review-report-export-surface {
  min-width: 0;
}

.review-script-card {
  border-color: var(--primary);
  box-shadow: 6px 6px 0 0 var(--primary-container);
}

.review-script-card .speech-rewrite-row {
  border: 4px solid var(--ink);
  border-radius: 16px;
}

.review-script-card .speech-before,
.review-script-card .speech-after {
  min-height: 132px;
}

.review-script-card .speech-after {
  box-shadow: 5px 5px 0 0 rgba(52, 211, 153, 0.36);
}

.review-plan-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18px;
}

.review-plan-card {
  display: grid;
  gap: 10px;
  border: 4px solid var(--ink);
  background: var(--card);
  padding: 18px;
}

.review-plan-card > .material-symbol {
  display: inline-grid;
  width: 44px;
  height: 44px;
  place-items: center;
  border: 3px solid var(--ink);
  border-radius: 12px;
  background: var(--quaternary);
  box-shadow: 2px 2px 0 0 var(--shadow-dark);
}

.review-plan-card:nth-child(2) > .material-symbol {
  background: var(--secondary-soft);
}

.review-plan-card:nth-child(3) > .material-symbol {
  background: var(--tertiary);
}

.review-plan-card h3,
.review-plan-card p {
  margin: 0;
}

.review-plan-card p {
  color: var(--ink-soft);
  font-weight: 800;
  line-height: 1.6;
  overflow-wrap: anywhere;
}

.review-workspace > .review-actions,
.review-workspace > .review-export-error {
  grid-column: 1;
}

.review-workspace > .review-actions {
  justify-content: flex-start;
  margin-top: 0;
}

.review-dialogue-modal {
  width: min(720px, calc(100vw - 32px));
}

.review-dialogue-modal-subtitle {
  margin: 4px 42px 18px 0;
  color: var(--ink-soft);
  font-weight: 800;
}

.review-dialogue-modal-list {
  max-height: min(58vh, 560px);
  overflow-y: auto;
  padding: 4px 8px 8px 4px;
}

.review-report-switch-enter-active,
.review-report-switch-leave-active {
  transition:
    opacity 220ms ease,
    transform 280ms cubic-bezier(0.2, 0, 0, 1);
}

.review-report-switch-enter-from,
.review-report-switch-leave-to {
  opacity: 0;
  transform: translateY(14px) scale(0.985);
}

.review-dialogue-modal-enter-active,
.review-dialogue-modal-leave-active {
  transition: opacity 180ms ease;
}

.review-dialogue-modal-enter-active .review-dialogue-modal,
.review-dialogue-modal-leave-active .review-dialogue-modal {
  transition:
    opacity 220ms ease,
    transform 260ms cubic-bezier(0.2, 0, 0, 1);
}

.review-dialogue-modal-enter-from,
.review-dialogue-modal-leave-to {
  opacity: 0;
}

.review-dialogue-modal-enter-from .review-dialogue-modal,
.review-dialogue-modal-leave-to .review-dialogue-modal {
  opacity: 0;
  transform: translateY(18px) scale(0.96);
}

@media (max-width: 980px) {
  .review-workspace {
    grid-template-columns: 1fr;
  }

  .review-workspace > .review-actions,
  .review-workspace > .review-export-error {
    grid-column: 1;
  }
}

@media (max-width: 720px) {
  .review-dialogue-entry-card,
  .review-plan-grid {
    grid-template-columns: 1fr;
  }

  .review-dialogue-entry-card .secondary-action,
  .review-workspace > .review-actions button,
  .review-workspace > .review-actions a {
    width: 100%;
  }

  .review-history-item {
    grid-template-columns: 42px minmax(0, 1fr);
  }

  .review-history-list {
    grid-auto-columns: minmax(210px, 82vw);
  }
}
</style>
