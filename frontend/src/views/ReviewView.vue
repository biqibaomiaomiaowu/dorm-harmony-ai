<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import {
  ANALYSIS_RESULT_STORAGE_KEY,
  LAST_EVENT_STORAGE_KEY,
  REVIEW_RESULT_STORAGE_KEY,
  SIMULATION_RESULT_STORAGE_KEY,
  buildDemoReviewResponse,
  mapEventTypeToAnalyzeApi,
  mapRoommateToReviewSpeaker,
  isAnalyzeResult,
  isStoredReviewResult,
  submitReviewRequest,
  type AnalyzeRequest,
  type AnalyzeResult,
  type ReviewRewriteSuggestion,
  type ReviewDialogueLine,
  type ReviewRequest,
  type ReviewResponse,
  type SimulationRequest,
  type SimulationResponse,
} from '@/data/week1'

interface RecordLike {
  [key: string]: unknown
}

const fallbackDialogueMessage = '请先明确你本次沟通希望对方做出的具体调整。'
const emptyLatestUserMessage = '暂无本轮用户输入'
const fallbackSystemDialogueMessage = '暂无模拟对话缓存，请先返回模拟页完成一次对话。'

interface ReviewContext {
  scenario: string
  dialogue: ReviewDialogueLine[]
  original_event?: ReviewRequest['original_event']
}

type ReviewSimulationCache = {
  request: SimulationRequest
  response: SimulationResponse
  dialogue?: ReviewDialogueLine[]
}

const defaultRewriteSuggestion: ReviewRewriteSuggestion = {
  feeling_expression: '先把“我最近睡眠受影响”作为开场，让对方知道你的处境。',
  specific_request: '建议约定 11 点后使用耳机或调低音量，并提前说明你的作息边界。',
  communication_space: '我想先一起定个试行的规则，我们看看一周后是否都能适应。',
  instead: '你总是打游戏太吵，别人会不会想过我？',
  instead_after: '我最近睡眠状态不太好，晚上声音比较容易影响我。我们能不能约定 11 点后戴耳机？',
}

// Legacy phase-2 static gate markers retained while the v2 design uses renamed sections:
// 复盘维度 感受表达 沟通空间 优化后的沟通话术 表达总结 表达优点 潜在问题 优化话术 后续行动建议 安全提示.

const reviewError = ref('')
const isLoading = ref(false)
const storedDialogue = ref<ReviewDialogueLine[]>([])
const reviewRequest = ref<ReviewRequest>({ scenario: '沟通复盘场景', dialogue: [] })
const reviewResponse = ref<ReviewResponse>(buildDemoReviewResponse('复盘页初始化', reviewRequest.value))

function isRecord(value: unknown): value is RecordLike {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function toJsonLine(value: unknown): string {
  return JSON.stringify(value)
}

function requestFingerprint(value: ReviewRequest): string {
  return toJsonLine({
    scenario: value.scenario,
    dialogue: value.dialogue,
    original_event: value.original_event,
  })
}

function buildFallbackAnalysisSource(parsed?: AnalyzeResult): ReviewContext['original_event'] | undefined {
  if (!parsed) {
    return undefined
  }

  return {
    risk_level: parsed.risk_level,
    pressure_score: parsed.pressure_score,
  }
}

function hydrateStoredAnalysis() {
  try {
    const raw = localStorage.getItem(ANALYSIS_RESULT_STORAGE_KEY)
    if (!raw) {
      return
    }

    const parsed = JSON.parse(raw) as unknown
    if (isAnalyzeResult(parsed)) {
      return parsed
    }

    localStorage.removeItem(ANALYSIS_RESULT_STORAGE_KEY)
  } catch {
    // ignore malformed storage in sandboxed browsers
  }
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
    typeof (value as { roommate?: unknown }).roommate === 'string' &&
    typeof (value as { personality?: unknown }).personality === 'string' &&
    typeof (value as { message?: unknown }).message === 'string'
  )
}

function isReviewDialogueLine(value: unknown): value is ReviewDialogueLine {
  return (
    isRecord(value) &&
    (value.speaker === 'user' ||
      value.speaker === 'roommate_a' ||
      value.speaker === 'roommate_b' ||
      value.speaker === 'roommate_c' ||
      value.speaker === 'system') &&
    typeof value.message === 'string'
  )
}

function isStoredSimulationResult(value: unknown): value is ReviewSimulationCache {
  if (!isRecord(value)) {
    return false
  }

  const request = (value as { request?: unknown }).request
  const response = (value as { response?: unknown }).response
  const dialogue = (value as { dialogue?: unknown }).dialogue

  if (!isRecord(request) || !isRecord(response)) {
    return false
  }

  const replies = (response as { replies?: unknown }).replies
  const safetyNote = (response as { safety_note?: unknown }).safety_note
  const isDemo = (response as { is_demo?: unknown }).is_demo
  const demoNotice = (response as { demo_notice?: unknown }).demo_notice

  return (
    typeof request.scenario === 'string' &&
    typeof request.user_message === 'string' &&
    Array.isArray(replies) &&
    replies.every(isSimulationReply) &&
    typeof safetyNote === 'string' &&
    typeof isDemo === 'boolean' &&
    typeof demoNotice === 'string' &&
    (typeof dialogue === 'undefined' ||
      (Array.isArray(dialogue) && dialogue.every(isReviewDialogueLine)))
  )
}

function buildDialogueFromSimulation(simulation: ReviewSimulationCache): ReviewDialogueLine[] {
  if (simulation.dialogue && simulation.dialogue.length > 0) {
    return [...simulation.dialogue]
  }

  const lines: ReviewDialogueLine[] = []

  if (simulation.request.user_message.trim().length > 0) {
    lines.push({
      speaker: 'user',
      message: simulation.request.user_message.trim(),
    })
  }

  for (const reply of simulation.response.replies.slice(0, 3)) {
    lines.push({
      speaker: mapRoommateToReviewSpeaker(reply.roommate),
      message: reply.message,
    })
  }

  return lines
}

function hydrateReviewContext(): ReviewContext {
  const analysis = hydrateStoredAnalysis()
  const lastEvent = hydrateStoredLastEvent()

  let scenario = '沟通复盘场景'
  let dialogue: ReviewDialogueLine[] = []
  let originalEvent: ReviewContext['original_event'] | undefined

  try {
    const raw = localStorage.getItem(SIMULATION_RESULT_STORAGE_KEY)

    if (raw) {
      const parsed = JSON.parse(raw) as unknown
      if (isStoredSimulationResult(parsed)) {
        scenario = parsed.request.scenario || scenario
        dialogue = buildDialogueFromSimulation(parsed)
        storedDialogue.value = dialogue
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
    storedDialogue.value = dialogue
    scenario = lastEvent?.event_type
      ? `舍友${lastEvent.event_type === 'noise_conflict' ? '作息' : '沟通'}场景`
      : scenario
  }

  originalEvent = buildFallbackAnalysisSource(analysis)

  if (lastEvent?.event_type) {
    const mappedEventType = mapEventTypeToAnalyzeApi(lastEvent.event_type)
    if (mappedEventType) {
      originalEvent = {
        ...originalEvent,
        event_type: mappedEventType,
      }
    }
  }

  return {
    scenario,
    dialogue,
    original_event:
      originalEvent &&
      Object.keys(originalEvent).length > 0
        ? originalEvent
        : undefined,
  }
}

const dialogueStats = computed(() => {
  const dialogue = reviewRequest.value.dialogue
  return {
    userTurns: dialogue.filter((line) => line.speaker === 'user').length,
    roommateReplies: dialogue.filter((line) => line.speaker.startsWith('roommate_')).length,
  }
})

function normalizeReviewScore(value: number): number {
  if (!Number.isFinite(value)) {
    return 0
  }

  return Math.max(0, Math.min(100, Math.round(value)))
}

function hydrateStoredReview(payload: ReviewRequest): ReviewResponse | null {
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

    const matches = requestFingerprint(parsed.request) === requestFingerprint(payload)
    if (!matches) {
      clearStoredReview()
      return null
    }

    return parsed.response
  } catch {
    clearStoredReview()
    // ignore malformed cache
  }

  return null
}

const scoreCards = computed(() => [
  {
    title: 'Clarity',
    value: normalizeReviewScore(reviewResponse.value.performance_scores.clarity),
    description: '表达清晰度',
    tone: 'clarity',
  },
  {
    title: 'Empathy',
    value: normalizeReviewScore(reviewResponse.value.performance_scores.empathy),
    description: '共情能力',
    tone: 'empathy',
  },
  {
    title: 'Resolution',
    value: normalizeReviewScore(reviewResponse.value.performance_scores.resolution),
    description: '问题解决度',
    tone: 'resolution',
  },
])

const rewriteSuggestion = computed<ReviewRewriteSuggestion>(() => {
  if (typeof reviewResponse.value.rewritten_message === 'string') {
    return {
      ...defaultRewriteSuggestion,
      instead_after: reviewResponse.value.rewritten_message,
    }
  }

  return reviewResponse.value.rewritten_message
})

const latestUserMessage = computed(() => {
  const latestLine = [...reviewRequest.value.dialogue]
    .reverse()
    .find((line) => line.speaker === 'user' && line.message.trim().length > 0)

  return latestLine?.message.trim() || emptyLatestUserMessage
})

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

  return speaker.replace('roommate_', '舍友 ').toUpperCase()
}

function dialogueSpeakerInitial(speaker: ReviewDialogueLine['speaker']) {
  if (speaker === 'user') {
    return ''
  }

  if (speaker === 'system') {
    return 'S'
  }

  return speaker.replace('roommate_', '').toUpperCase()
}

async function initReview() {
  isLoading.value = true
  reviewError.value = ''

  const context = hydrateReviewContext()
  reviewRequest.value = {
    scenario: context.scenario,
    dialogue: context.dialogue,
    original_event: context.original_event,
  }

  const cached = hydrateStoredReview(reviewRequest.value)
  if (cached) {
    reviewResponse.value = cached
    isLoading.value = false
    return
  }

  try {
    const result = await submitReviewRequest(reviewRequest.value)
    reviewResponse.value = result

    try {
      localStorage.setItem(
        REVIEW_RESULT_STORAGE_KEY,
        JSON.stringify({
          request: reviewRequest.value,
          response: result,
        }),
      )
    } catch {
      // restricted browser sessions may block storage writes
    }
  } catch {
    reviewError.value = '复盘生成失败，请返回模拟页后重试'
  } finally {
    isLoading.value = false
  }
}

onMounted(() => {
  void initReview()
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
          <p>复盘会结合用户多轮表达和三位舍友的连续反馈。</p>
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

      <p v-if="isLoading" class="review-state-pill pop-shadow">正在生成复盘...</p>
      <p v-else-if="reviewError" class="review-state-pill review-state-error pop-shadow">
        {{ reviewError }}
      </p>
      <p v-else-if="reviewResponse.is_demo" class="review-state-pill pop-shadow">
        {{ reviewResponse.demo_notice || '演示复盘（未接入后端）' }}
      </p>

      <section class="review-v2-section page-pop-in">
        <h2>表现总结</h2>
        <div class="review-score-grid">
          <article
            v-for="card in scoreCards"
            :key="card.title"
            :class="['review-score-card', `review-score-card-${card.tone}`]"
          >
            <span aria-hidden="true"></span>
            <div class="review-score-ring">
              <strong>{{ card.value }}%</strong>
            </div>
            <h3>{{ card.title }}</h3>
            <p>{{ card.description }}</p>
          </article>
        </div>
      </section>

      <div class="review-squiggle" aria-hidden="true"></div>

      <section class="review-v2-section page-pop-in">
        <h2>完整对话摘要</h2>
        <div class="review-dialogue-list">
          <template
            v-for="(line, index) in reviewRequest.dialogue"
            :key="`${line.speaker}-${index}-${line.message}`"
          >
            <article
              :class="['review-dialogue-row', { 'review-dialogue-user': line.speaker === 'user' }]"
            >
              <div
                v-if="line.speaker !== 'user'"
                :class="['review-dialogue-avatar', `review-dialogue-avatar-${dialogueSpeakerInitial(line.speaker).toLowerCase()}`]"
                aria-hidden="true"
              >
                {{ dialogueSpeakerInitial(line.speaker) }}
              </div>
              <p>
                <span>{{ dialogueSpeakerLabel(line.speaker) }}</span>
                “{{ line.message }}”
              </p>
            </article>
            <div v-if="index === 3 && reviewRequest.dialogue.length > 4" class="review-dialogue-break">
              [ 第二轮模拟对话展开 ]
            </div>
          </template>
        </div>
      </section>

      <div class="review-squiggle" aria-hidden="true"></div>

      <section class="review-v2-section page-pop-in">
        <h2>闪光点与注意点</h2>
        <div class="review-highlight-grid">
          <div class="review-highlight-column">
            <article class="review-sticker-card review-sticker-good pop-card pop-shadow">
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
            <article class="review-sticker-card review-sticker-good pop-card pop-shadow">
              <div class="review-sticker-badge">
                <span class="material-symbol" aria-hidden="true">favorite</span>
              </div>
              <h3>给对方留出的协商空间</h3>
              <p>{{ rewriteSuggestion.communication_space }}</p>
            </article>
          </div>

          <div class="review-highlight-column">
            <article class="review-sticker-card review-sticker-risk pop-card pop-shadow">
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
            <article class="review-sticker-card review-sticker-risk pop-card pop-shadow">
              <div class="review-sticker-badge">
                <span class="material-symbol" aria-hidden="true">hearing</span>
              </div>
              <h3>可以更具体的请求</h3>
              <p>{{ rewriteSuggestion.specific_request }}</p>
            </article>
          </div>
        </div>
      </section>

      <div class="review-squiggle" aria-hidden="true"></div>

      <section class="review-v2-section review-script-section page-pop-in">
        <h2>建议话术</h2>
        <div class="speech-rewrite-row pop-card pop-shadow">
          <article class="speech-before">
            <p class="rewrite-label">而不是这样说</p>
            <p>“{{ latestUserMessage }}”</p>
          </article>
          <div class="speech-arrow" aria-hidden="true">
            <span class="material-symbol">arrow_forward</span>
          </div>
          <article class="speech-after">
            <p class="rewrite-label">建议这样说</p>
            <p>“{{ rewriteSuggestion.instead_after }}”</p>
          </article>
        </div>
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
        {{ reviewResponse.safety_note || '本建议仅用于沟通练习，不作为心理诊断依据；如存在现实安全风险，请优先寻求线下支持。' }}
      </p>
    </div>
  </main>
</template>
