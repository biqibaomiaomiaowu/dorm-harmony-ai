<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import {
  ANALYSIS_RESULT_STORAGE_KEY,
  LAST_EVENT_STORAGE_KEY,
  SIMULATION_RESULT_STORAGE_KEY,
  buildDemoSimulationResponse,
  defaultSimulationRequest,
  isAnalyzeResult,
  mapRoommateToReviewSpeaker,
  simulationScenarios,
  submitSimulationRequest,
  submitSimulationStreamRequest,
  type AnalyzeResult,
  type ReviewDialogueLine,
  type SimulationReply,
  type SimulationRequest,
  type SimulationResponse,
  type StoredSimulationResult,
} from '@/data/week1'

const scenarioButtons = simulationScenarios
const defaultScene = defaultSimulationRequest.scenario
const defaultSpeechPlaceholder = `例：${defaultSimulationRequest.user_message}`
const designPreview = buildDemoSimulationResponse('设计稿首屏示例')

const currentScene = ref(defaultScene)
const userMessage = ref('')
const isSubmitting = ref(false)
const submitError = ref('')
const isDemoResult = ref(false)
const simulationNotice = ref('')
const safetyNote = ref('')
const replies = ref<SimulationReply[]>([...designPreview.replies])
const conversationMessages = ref<ReviewDialogueLine[]>([])
const replyDelayMs = 750
const generationStatus = ref('')
const generationRunId = ref(0)
const savedAnalysisRiskLevel = ref<AnalyzeResult['risk_level'] | undefined>()
const savedAnalysisSources = ref<string[]>([])
const savedAnalysisEmotionKeywords = ref<string[]>([])
const savedAnalysisTrend = ref('')
const savedAnalysisSuggestion = ref('')
const savedAnalysisScore = ref<number | null>(null)
const savedAnalysisContext = ref('')
const storedSimulationMeta = ref('')
const hasUsableSimulation = ref(false)

type RecordLike = Record<string, unknown>

function isRecord(value: unknown): value is RecordLike {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isSimulationResult(value: unknown): value is SimulationResponse {
  if (!isRecord(value)) {
    return false
  }

  const replies = (value as { replies?: unknown }).replies

  if (!Array.isArray(replies)) {
    return false
  }

  const hasValidReplies = replies.every((item: unknown) => {
    const row = item as RecordLike
    return (
      isRecord(row) &&
      typeof row.roommate === 'string' &&
      typeof row.personality === 'string' &&
      typeof row.message === 'string'
    )
  })

  return (
    hasValidReplies &&
    typeof (value as { safety_note?: unknown }).safety_note === 'string' &&
    typeof (value as { is_demo?: unknown }).is_demo === 'boolean' &&
    typeof (value as { demo_notice?: unknown }).demo_notice === 'string'
  )
}

function isReviewDialogueLine(value: unknown): value is ReviewDialogueLine {
  if (!isRecord(value)) {
    return false
  }

  return (
    (value.speaker === 'user' ||
      value.speaker === 'roommate_a' ||
      value.speaker === 'roommate_b' ||
      value.speaker === 'roommate_c' ||
      value.speaker === 'system') &&
    typeof value.message === 'string'
  )
}

function isStoredSimulationResult(value: unknown): value is StoredSimulationResult {
  if (!isRecord(value)) {
    return false
  }

  const request = (value as { request?: unknown }).request
  const response = (value as { response?: unknown }).response
  const dialogue = (value as { dialogue?: unknown }).dialogue

  return (
    isRecord(request) &&
    typeof request.scenario === 'string' &&
    typeof request.user_message === 'string' &&
    isSimulationResult(response) &&
    (typeof dialogue === 'undefined' ||
      (Array.isArray(dialogue) && dialogue.every(isReviewDialogueLine)))
  )
}

function buildRequestContext() {
  const parts = ['当前场景：', currentScene.value]
  const analysisPart = savedAnalysisContext.value.trim()

  if (analysisPart) {
    parts.push(analysisPart)
  }

  if (savedAnalysisScore.value !== null) {
    parts.push(`压力分数：${savedAnalysisScore.value}`)
  }

  if (savedAnalysisRiskLevel.value) {
    parts.push(`风险等级：${savedAnalysisRiskLevel.value}`)
  }

  if (savedAnalysisSources.value.length > 0) {
    parts.push(`压力来源：${savedAnalysisSources.value.join('、')}`)
  }

  if (savedAnalysisEmotionKeywords.value.length > 0) {
    parts.push(`情绪关键词：${savedAnalysisEmotionKeywords.value.join('、')}`)
  }

  if (savedAnalysisTrend.value) {
    parts.push(`趋势提示：${savedAnalysisTrend.value}`)
  }

  if (savedAnalysisSuggestion.value) {
    parts.push(`建议：${savedAnalysisSuggestion.value}`)
  }

  return parts.join(' ')
}

function setDefaultSimulationState() {
  currentScene.value = defaultScene
  userMessage.value = ''
  replies.value = [...designPreview.replies]
  conversationMessages.value = []
  generationStatus.value = ''
  submitError.value = ''
  isDemoResult.value = false
  simulationNotice.value = ''
  safetyNote.value = designPreview.safety_note
  storedSimulationMeta.value = ''
  hasUsableSimulation.value = false
}

const currentScenePrompt = computed(() => {
  return `当前场景：${currentScene.value}。请先输入一句你准备现实沟通时使用的话。`
})
const hasUserMessage = computed(() => userMessage.value.trim().length > 0)

function loadAnalysisContext() {
  try {
    const rawAnalysis = localStorage.getItem(ANALYSIS_RESULT_STORAGE_KEY)
    if (!rawAnalysis) {
      return
    }

    const parsed = JSON.parse(rawAnalysis) as unknown

    if (!isAnalyzeResult(parsed)) {
      return
    }

    savedAnalysisContext.value = parsed.disclaimer ?? ''
    savedAnalysisRiskLevel.value = parsed.risk_level
    savedAnalysisScore.value = parsed.pressure_score
    savedAnalysisSources.value = Array.isArray(parsed.main_sources) ? [...parsed.main_sources] : []
    savedAnalysisEmotionKeywords.value = Array.isArray(parsed.emotion_keywords)
      ? [...parsed.emotion_keywords]
      : []
    savedAnalysisTrend.value = parsed.trend_message
    savedAnalysisSuggestion.value = parsed.suggestion
  } catch {
    // ignore malformed analysis cache
  }
}

function loadLastEventHint() {
  try {
    const rawEvent = localStorage.getItem(LAST_EVENT_STORAGE_KEY)

    if (!rawEvent) {
      return
    }

    const parsed = JSON.parse(rawEvent) as unknown

    if (!isRecord(parsed)) {
      return
    }

    const description = typeof parsed.description === 'string' ? parsed.description.trim() : ''

    if (description.length > 0) {
      const descriptionHint = `事件描述：${description}`
      savedAnalysisContext.value = `${savedAnalysisContext.value}${savedAnalysisContext.value ? '；' : ''}${descriptionHint}`
    }

    const emotionHint =
      typeof parsed.emotion === 'string' ? `情绪线索：${parsed.emotion}` : ''

    if (emotionHint) {
      savedAnalysisContext.value = `${savedAnalysisContext.value}${savedAnalysisContext.value ? '；' : ''}${emotionHint}`
    }
  } catch {
    // ignore malformed local cache
  }
}

function hydrateFromSimulationCache() {
  try {
    const raw = localStorage.getItem(SIMULATION_RESULT_STORAGE_KEY)

    if (!raw) {
      return
    }

    const parsed = JSON.parse(raw) as unknown

    if (isStoredSimulationResult(parsed)) {
      currentScene.value = parsed.request.scenario || defaultScene
      userMessage.value = parsed.request.user_message || ''
      replies.value = [...parsed.response.replies]
      conversationMessages.value = parsed.dialogue ? [...parsed.dialogue] : []
      isDemoResult.value = parsed.response.is_demo
      simulationNotice.value = parsed.response.demo_notice
      safetyNote.value = parsed.response.safety_note
      storedSimulationMeta.value = parsed.response.is_demo ? '演示数据' : '后端返回'
      hasUsableSimulation.value = parsed.response.replies.length > 0
      return
    }

    if (isSimulationResult(parsed)) {
      replies.value = [...parsed.replies]
      conversationMessages.value = []
      isDemoResult.value = parsed.is_demo
      simulationNotice.value = parsed.demo_notice
      safetyNote.value = parsed.safety_note
      storedSimulationMeta.value = parsed.is_demo ? '演示数据' : '后端返回'
      hasUsableSimulation.value = parsed.replies.length > 0
    }
  } catch {
    // ignore malformed simulation cache
  }
}

onMounted(() => {
  loadAnalysisContext()
  loadLastEventHint()
  hydrateFromSimulationCache()
})

const canEnterReview = computed(() => hasUsableSimulation.value && replies.value.length > 0)

const reviewGateMessage = computed(() =>
  canEnterReview.value ? '已有本次演练结果，可生成复盘报告。' : '请先发送一次模拟对话，再进入复盘。',
)

function speakerLabel(speaker: ReviewDialogueLine['speaker']) {
  if (speaker === 'user') {
    return '你'
  }
  if (speaker === 'roommate_a') {
    return '舍友 A'
  }
  if (speaker === 'roommate_b') {
    return '舍友 B'
  }
  if (speaker === 'roommate_c') {
    return '舍友 C'
  }

  return '系统'
}

function messageClass(speaker: ReviewDialogueLine['speaker']) {
  return speaker === 'user' ? 'conversation-message-user' : 'conversation-message-roommate'
}

function resetGeneratingState() {
  generationStatus.value = ''
}

async function appendReplyWithDelay(reply: SimulationReply, index: number, runId: number) {
  const nextRoommate = reply.roommate.replace(/\s+/g, ' ')
  generationStatus.value = `正在生成${nextRoommate} 的回复`

  await new Promise((resolve) => window.setTimeout(resolve, replyDelayMs * index))

  if (runId !== generationRunId.value) {
    return
  }

  replies.value = [...replies.value, reply]
  conversationMessages.value = [
    ...conversationMessages.value,
    {
      speaker: mapRoommateToReviewSpeaker(reply.roommate),
      message: reply.message,
    },
  ]
}

function selectScenario(scene: string) {
  currentScene.value = scene
}

async function sendMessage() {
  const message = userMessage.value.trim()

  if (!message) {
    submitError.value = '请输入你的回复后再发送'
    return
  }

  isSubmitting.value = true
  submitError.value = ''
  resetGeneratingState()

  try {
    const priorDialogue = [...conversationMessages.value]
    const currentTurnDialogue: ReviewDialogueLine[] = [
      ...priorDialogue,
      {
        speaker: 'user',
        message,
      },
    ]
    conversationMessages.value = [...currentTurnDialogue]

    const request: SimulationRequest = {
      scenario: currentScene.value,
      user_message: message,
      risk_level: savedAnalysisRiskLevel.value,
      context: buildRequestContext(),
      dialogue: priorDialogue,
    }
    const applyResultMeta = (response: SimulationResponse) => {
      isDemoResult.value = response.is_demo
      simulationNotice.value = response.demo_notice
      safetyNote.value = response.safety_note
      storedSimulationMeta.value = response.is_demo ? '演示数据' : '后端返回'
      hasUsableSimulation.value = response.replies.length > 0
    }

    let result: SimulationResponse
    try {
      const streamRunId = generationRunId.value + 1
      generationRunId.value = streamRunId
      const appendTasks: Array<Promise<void>> = []
      result = await submitSimulationStreamRequest(request, {
        onStart: () => {
          replies.value = []
          isDemoResult.value = false
          simulationNotice.value = 'AI 正在按顺序生成舍友回复'
          generationStatus.value = '正在生成舍友 A 的回复'
          safetyNote.value = ''
          storedSimulationMeta.value = '后端顺序返回'
          hasUsableSimulation.value = false
        },
        onReply: (reply) => {
          appendTasks.push(appendReplyWithDelay(reply, appendTasks.length, streamRunId))
        },
      })
      if (appendTasks.length === 0) {
        appendTasks.push(
          ...result.replies.map((reply, index) =>
            appendReplyWithDelay(reply, index, streamRunId),
          ),
        )
      }
      await Promise.all(appendTasks)
      applyResultMeta(result)
    } catch {
      const fallbackRunId = generationRunId.value + 1
      generationRunId.value = fallbackRunId
      replies.value = []
      conversationMessages.value = [...currentTurnDialogue]
      generationStatus.value = '正在生成舍友回复...'
      result = await submitSimulationRequest(request)
      await Promise.all(
        result.replies.map((reply, index) => appendReplyWithDelay(reply, index, fallbackRunId)),
      )
      applyResultMeta(result)
    }

    try {
      localStorage.setItem(
        SIMULATION_RESULT_STORAGE_KEY,
        JSON.stringify({
          request,
          response: result,
          dialogue: conversationMessages.value,
        }),
      )
    } catch {
      // ignore write failures
    }
  } catch {
    submitError.value = '发送失败，请检查网络后重试'
  } finally {
    resetGeneratingState()
    isSubmitting.value = false
  }
}

function resetConversation() {
  setDefaultSimulationState()

  try {
    localStorage.removeItem(SIMULATION_RESULT_STORAGE_KEY)
  } catch {
    // ignore write failures
  }
}
</script>

<template>
  <main class="page simulation-page bg-diagonal-stripes">
    <span class="simulation-decoration simulation-decoration-squiggle" aria-hidden="true"></span>

    <section class="simulation-header-card card-border pop-card pop-shadow page-pop-in">
      <div class="simulation-title-block">
        <h1>夜间噪音冲突</h1>
        <div class="simulation-subtitle-chip card-border">场景演练</div>
      </div>
      <p>AI 沟通模拟演练，先选场景，再在下方输入你的沟通话术。</p>
    </section>

    <section class="simulation-scene-card card-border pop-card pop-shadow page-pop-in">
      <div class="simulation-section-heading">
        <span class="material-symbol" aria-hidden="true">rule</span>
        <h2>选择演练场景</h2>
      </div>
      <p class="simulation-subtitle chip-text">场景选择</p>
      <div class="simulation-scenes">
        <button
          v-for="scene in scenarioButtons"
          :key="scene"
          class="scene-btn pop-shadow"
          :class="{ active: scene === currentScene }"
          type="button"
          @click="selectScenario(scene)"
        >
          {{ scene }}
        </button>
      </div>
    </section>

    <section class="simulation-layout page-pop-in">
      <aside class="simulation-left-column">
        <h2 class="panel-title">
          <span class="material-symbol" aria-hidden="true">groups</span>
          AI 舍友库
        </h2>
        <div class="roommate-grid">
          <article class="roommate-card card-border pop-card">
            <div class="roommate-badge roommate-badge-direct">
              <span class="material-symbol" aria-hidden="true">bolt</span>
            </div>
            <div class="roommate-card-head">
              <img
                class="roommate-avatar"
                alt="直接型舍友"
                src="https://lh3.googleusercontent.com/aida-public/AB6AXuCQxC7cUISzoMSERUNm8YYvexl7ftRw_7mVgL8WYbAB4k9Vw2xcvxR3OFQaWxEYKk6sBsKbDszLLXpatSBO-Fznk-eonjG4oI7n_T_jNi348WqrWSV9JLlg8hVQsQxTeJCuk8YPMIbV7vIbRMnCUWhF48e_4Hk3QrtiErviy6Mgskn7v106Vz2ZfE81pzxuGYsn9iDSdqrQP7awuhQgYt5S5kiKA6GJLWWgVjiL_D25x7-Ie45Yvc3Ttz71QduXuwvl789DeZKXMaI"
              />
              <div>
                <h3>舍友 A（直接型）</h3>
                <p class="roommate-tag card-border">直接型</p>
              </div>
            </div>
            <p class="roommate-says">“我明早有早课，你键盘声能不能小点？真的很吵！”</p>
          </article>
          <article class="roommate-card card-border pop-card">
            <div class="roommate-badge roommate-badge-avoidant">
              <span class="material-symbol" aria-hidden="true">water_drop</span>
            </div>
            <div class="roommate-card-head">
              <img
                class="roommate-avatar"
                alt="回避型舍友"
                src="https://lh3.googleusercontent.com/aida-public/AB6AXuDVkCv9H9iWL84iWgT-aX9iaTkF9XbiekpJt3Ib4xhIzztu-ixOqqjNCP13qrNtQ8aEWAECETCkYv5sUIGdo630Uxcc3Oz5G_HpCEid2grb5mlydpuEe893SzoEVSDcVt0WAi4HKlW8Y5L-lgvPbuirPyuAvBjnzW3GCUNXGQqkA2YtvnmVElMShQo41zZD_75Z8iWWLzivLO5o9l0MTwP0O8H22sZrA_HsRPk1T3uU86VoVgMAR13C-7qynmOzX0-zIPqXU80KnBE"
              />
              <div>
                <h3>舍友 B（回避型）</h3>
                <p class="roommate-tag roommate-tag-soft card-border">回避型</p>
              </div>
            </div>
            <p class="roommate-says">（戴上耳机，翻个身背对你，不说话）</p>
          </article>
          <article class="roommate-card card-border pop-card roommate-active">
            <div class="roommate-badge roommate-badge-harmony">
              <span class="material-symbol" aria-hidden="true">favorite</span>
            </div>
            <div class="roommate-card-head">
              <img
                class="roommate-avatar"
                alt="调和型舍友"
                src="https://lh3.googleusercontent.com/aida-public/AB6AXuAooVlMNOD_UP6HD9TfVio7c0BXo81Y938kgFj-EZUjSoyy7Ah3YRiJ5qKtUqoQJwQm5jCRbfOmqCfcXlM57JxE60-PoNrWG4NtGkc16Jp4jk8a7s762h1b7PlZ3RvXHUtgPyIo72IJRl_a3G702xO_rNj_TrZGwp5dR3twh_eEYDdoMOLJ7p-DUUOgtLrcN9LPmOn0Jjbwt5pT9B6JjVNNnR0kH6zx7yKoEAHjN4B4oiu2ydu-8anarvfm4rs3aE8uV6VUQKfmPFk"
              />
              <div>
                <h3>舍友 C（调和型）</h3>
                <p class="roommate-tag roommate-tag-harmony card-border">调和型</p>
              </div>
            </div>
            <p class="roommate-says">“兄弟，还在忙呢？注意身体啊。不过键盘声有点大，能稍微轻点吗？”</p>
          </article>
        </div>
      </aside>

      <section class="chat-panel card-border pop-card">
        <header class="chat-header card-border">
          <div class="chat-title">
            <span class="material-symbol" aria-hidden="true">chat</span>
            <h2>对话模拟器</h2>
          </div>
          <button class="primary-action pop-shadow" type="button" @click="resetConversation">
            <span class="material-symbol" aria-hidden="true">refresh</span>
            重置
          </button>
        </header>

        <div class="chat-content">
          <p class="chat-system card-border">
            {{ currentScenePrompt }}
          </p>

          <div v-if="conversationMessages.length > 0" class="conversation-thread">
            <article
              v-for="(line, index) in conversationMessages"
              :key="`${line.speaker}-${index}-${line.message}`"
              :class="['conversation-message', messageClass(line.speaker)]"
            >
              <span>{{ speakerLabel(line.speaker) }}</span>
              <p>{{ line.message }}</p>
            </article>
            <article v-if="isSubmitting" class="conversation-message conversation-message-roommate">
              <span>{{ generationStatus || '正在生成舍友回复...' }}</span>
              <p class="typing-indicator" aria-live="polite">
                <i></i>
                <i></i>
                <i></i>
              </p>
            </article>
          </div>

          <article v-else class="chat-user" :class="{ 'chat-user-empty': !hasUserMessage }">
            <img
              class="chat-avatar"
              alt=""
              aria-hidden="true"
              :src="
                'https://lh3.googleusercontent.com/aida-public/AB6AXuBJCY4H0EjAxeuZ78DN3JrYsAy42cqUaZQaWt1Wq2JWHTPOoyn4mlZrybfWe_rmUsx13ULRLgZNsUN7mZoSEXX0vqtHQTW_qx_gFtLF91ylQl_nIedDSmJxr9g6dqPnhlTz5XrTKmVmZnB6RT586DEXb122JBJ9QF-rjTrL-ptfWXnlooad8kRFSMnfgLJJfY0xHIuyCz8-ielL8ZiobKlyFYkQT35aoKSOLs63e8WoBtT5UlpQiO5MJ2HpuLQs7GODYSqaqBxtgyc'
              "
            />
            <p class="chat-bubble chat-bubble-user pop-shadow">
              {{ userMessage }}
            </p>
          </article>

          <div v-if="conversationMessages.length === 0" class="chat-message-list">
            <article
              v-for="reply in replies"
              :key="`${reply.roommate}-${reply.personality}`"
              class="chat-bubble card-border pop-card"
            >
              <p class="chat-role">{{ reply.roommate }}（{{ reply.personality }}）</p>
              <p>{{ reply.message }}</p>
            </article>
          </div>

          <div class="chat-hint card-border pop-card">
            <p class="chat-hint-label">
              <span class="material-symbol" aria-hidden="true">tips_and_updates</span>
              建议先表达感受，再提出具体请求。
            </p>
            <p>
              {{
                storedSimulationMeta
                  ? `${storedSimulationMeta}：${simulationNotice || '已返回模拟建议。'}`
                  : '演示建议：先从“我感受到了……”开始表达，并给出可执行边界。'
              }}
            </p>
          </div>

          <div class="chat-footer-note card-border pop-card">
            <p>{{ safetyNote || '请基于对方反馈继续补充你的下一句。' }}</p>
          </div>
        </div>

        <form class="simulation-input-bar card-border" @submit.prevent="sendMessage">
          <div class="comm-input-wrap">
            <input
              v-model="userMessage"
              :placeholder="defaultSpeechPlaceholder"
              type="text"
              :disabled="isSubmitting"
              aria-label="输入你的回复"
            />
            <button class="microphone-btn" type="button" :disabled="isSubmitting" aria-label="麦克风">
              <span class="material-symbol" aria-hidden="true">mic</span>
            </button>
          </div>
          <button class="primary-action pop-shadow" type="submit" :disabled="isSubmitting">
            <span v-if="isSubmitting">{{ generationStatus || '正在生成' }}</span>
            <span v-else>发送</span>
            <span class="material-symbol" aria-hidden="true">send</span>
          </button>
        </form>

        <p v-if="submitError" class="error-text">{{ submitError }}</p>
      </section>
    </section>

    <section class="simulation-end-bar">
      <RouterLink
        v-if="canEnterReview"
        class="secondary-action pop-shadow"
        :to="{ name: 'review' }"
      >
        生成复盘报告
      </RouterLink>
      <button v-else class="secondary-action pop-shadow" type="button" disabled>
        生成复盘报告
      </button>
      <p class="simulation-meta">{{ reviewGateMessage }}</p>
    </section>
  </main>
</template>

<style scoped>
.error-text {
  margin: 12px 0 0;
  color: var(--error);
  font-weight: 700;
}

.simulation-meta {
  margin: 0;
  color: var(--ink-soft);
  font-size: 14px;
}

.chip-text {
  margin: 0 0 10px;
  color: var(--ink-soft);
  font-size: 13px;
  font-weight: 700;
}
</style>
