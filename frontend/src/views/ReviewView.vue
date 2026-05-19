<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

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

const fallbackDialogueMessage = '请先明确你本次沟通希望对方做出的具体调整。'
const fallbackSystemDialogueMessage = '暂无模拟对话缓存，请先返回模拟页完成一次对话。'

const reviewError = ref('')
const isLoading = ref(true)
const storedDialogue = ref<ReviewDialogueLine[]>([])
const storedRoommateNames = ref<ReviewContext['roommateNames']>({})
const reviewRequest = ref<ReviewRequest>({ scenario: '沟通复盘场景' })
const reviewResponse = ref<ReviewResponse>(buildDemoReviewResponse('复盘页初始化', reviewRequest.value))
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
const hasReviewResult = computed(() => !isLoading.value && !reviewError.value)
const suggestionCards = computed<ReviewRewriteSuggestion[]>(() =>
  reviewResponse.value.rewrite_suggestions.length > 0
    ? reviewResponse.value.rewrite_suggestions
    : buildDemoReviewResponse('本地兜底建议', reviewRequest.value).rewrite_suggestions,
)

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
  return suffix.replace(/^custom_?/i, '').slice(-2).toUpperCase() || 'AI'
}

function originalMessageLabel(suggestion: ReviewRewriteSuggestion) {
  return suggestion.original_message.trim() || '未定位到原句'
}

async function initReview() {
  isLoading.value = true
  reviewError.value = ''

  const context = hydrateReviewContext()
  storedDialogue.value = context.dialogue
  storedRoommateNames.value = context.roommateNames
  reviewRequest.value = {
    scenario: context.scenario,
    conversation_id: context.conversationId,
    dialogue: context.conversationId ? undefined : context.dialogue.slice(-50),
    original_event: context.original_event,
  }

  const cached = hydrateStoredReview(reviewRequest.value, context.dialogue)
  if (cached) {
    reviewResponse.value = cached
    isLoading.value = false
    await nextTick()
    animateReviewScores()
    return
  }

  try {
    const result = await submitReviewRequest(reviewRequest.value)
    reviewResponse.value = result
    isLoading.value = false
    await nextTick()
    animateReviewScores()

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
      error instanceof Error && error.message
        ? error.message
        : '复盘生成失败，请返回模拟页后重试'
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
        <div class="review-dialogue-stats">
          <span>
            <strong>{{ dialogueStats.userTurns }} 轮</strong>
            用户表达
          </span>
          <span>
            <strong>{{ dialogueStats.roommateReplies }} 条</strong>
            舍友反馈
          </span>
        </div>
      </section>

      <Transition name="review-state-transition" mode="out-in">
        <p v-if="isLoading" key="loading" class="review-state-pill pop-shadow">
          正在生成复盘...
        </p>
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
        <div v-if="hasReviewResult" class="review-result-stack">
          <section class="review-v2-section">
            <h2>表现总结</h2>
            <p class="review-summary-inline pop-card pop-shadow">{{ reviewResponse.summary }}</p>
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
            <h2>完整对话摘要</h2>
            <div class="review-dialogue-list">
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
                  <li v-for="item in toSafeArray(reviewResponse.strengths)" :key="`strength-${item}`">
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
            <h2>建议话术</h2>
            <TransitionGroup name="review-suggestion" tag="div" class="review-suggestion-list">
              <article
                v-for="(suggestion, index) in suggestionCards"
                :key="`${suggestion.message_index}-${suggestion.original_message}-${index}`"
                class="review-suggestion-card pop-card pop-shadow"
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
                    <p class="rewrite-label">建议表达</p>
                    <p>“{{ suggestion.suggested_message }}”</p>
                  </article>
                </div>
                <p class="review-suggestion-reason">{{ suggestion.reason }}</p>
              </article>
            </TransitionGroup>
          </section>

          <section class="review-bottom-grid">
            <article class="review-block pop-card pop-shadow">
              <h2>后续行动建议</h2>
              <ul>
                <li v-for="item in toSafeArray(reviewResponse.next_steps)" :key="`next-${item}`">
                  {{ item }}
                </li>
              </ul>
            </article>
          </section>

          <section class="review-actions">
            <RouterLink class="primary-action pop-shadow" :to="{ name: 'simulate' }">
              再次演练
              <span class="action-icon material-symbol">refresh</span>
            </RouterLink>
            <RouterLink class="secondary-action pop-shadow" :to="{ name: 'analysis' }">
              查看压力分析
              <span class="action-icon material-symbol">analytics</span>
            </RouterLink>
            <RouterLink class="secondary-action pop-shadow" :to="{ name: 'archive' }">
              返回事件档案
              <span class="action-icon material-symbol">archive</span>
            </RouterLink>
          </section>

          <p class="review-note">
            {{
              reviewResponse.safety_note ||
              '本建议仅用于沟通练习，不作为心理诊断依据；如存在现实安全风险，请优先寻求线下支持。'
            }}
          </p>
        </div>
      </Transition>
    </div>
  </main>
</template>
