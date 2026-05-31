<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { useSimulationSession } from '@/composables/useSimulationSession'
import {
  buildOpeningSuggestion,
  buildScenarioTrainingSourceMeta,
  getTrainingCategory,
  getTrainingDifficulty,
  getTrainingScenario,
  getTrainingTarget,
  scenariosForCategory,
  trainingCategories,
  trainingDifficulties,
  trainingTargets,
  type TrainingCategoryId,
  type TrainingDifficultyId,
  type TrainingScenarioId,
  type TrainingSelection,
  type TrainingTargetId,
} from '@/data/trainingCatalog'
import {
  createDefaultRoommates,
  roommateAvatarOptions,
  type ReviewDialogueLine,
  type RoommateAvatarKey,
} from '@/data/week1'

type TrainingStep = 'category' | 'scenario' | 'target' | 'difficulty' | 'opening' | 'chat'

interface RecordLike {
  [key: string]: unknown
}

interface ScenarioTrainingDraft {
  step?: TrainingStep
  category_id?: TrainingCategoryId
  scenario_id?: TrainingScenarioId
  target_id?: TrainingTargetId
  difficulty_id?: TrainingDifficultyId
  opening_message?: string
  opening_touched?: boolean
  from?: string
}

const scenarioTrainingDraftKey = 'dorm-harmony:scenario-training-draft:v1'
const trainingSteps: Array<{ id: TrainingStep; label: string }> = [
  { id: 'category', label: '分类' },
  { id: 'scenario', label: '场景' },
  { id: 'target', label: '目标' },
  { id: 'difficulty', label: '难度' },
  { id: 'opening', label: '开场白' },
  { id: 'chat', label: '聊天' },
]
const defaultStep: TrainingStep = 'category'
const rehearsalSafetyCopy =
  '场景演练只用于练习表达，不代表真实舍友想法；如果冲突升级或压力明显影响生活，请及时联系辅导员、宿管、心理老师等现实支持。'
const analysisSafetyCopy =
  '从压力分析进入时，建议把演练当作话术准备；高压力或持续冲突不应只依赖 AI，请同步寻求辅导员、宿管、心理老师等线下支持。'

const route = useRoute()
const currentStep = ref<TrainingStep>(defaultStep)
const categoryId = ref<TrainingCategoryId | undefined>()
const scenarioId = ref<TrainingScenarioId | undefined>()
const targetId = ref<TrainingTargetId | undefined>()
const difficultyId = ref<TrainingDifficultyId | undefined>()
const openingMessage = ref('')
const openingTouched = ref(false)
const sourceFrom = ref('')
const hasMounted = ref(false)
const trainingRoommates = createDefaultRoommates()

const selectedCategory = computed(() => getTrainingCategory(categoryId.value))
const selectedScenario = computed(() => {
  const scenario = getTrainingScenario(scenarioId.value)
  return scenario && scenario.category_id === categoryId.value ? scenario : undefined
})
const selectedTarget = computed(() => getTrainingTarget(targetId.value))
const selectedDifficulty = computed(() => getTrainingDifficulty(difficultyId.value))
const scenarioOptions = computed(() => scenariosForCategory(categoryId.value))
const trainingSelection = computed<Partial<TrainingSelection>>(() => ({
  category_id: selectedCategory.value?.id,
  scenario_id: selectedScenario.value?.id,
  target_id: selectedTarget.value?.id,
  difficulty_id: selectedDifficulty.value?.id,
}))
const completeSelection = computed<TrainingSelection | undefined>(() => {
  if (
    !selectedCategory.value ||
    !selectedScenario.value ||
    !selectedTarget.value ||
    !selectedDifficulty.value
  ) {
    return undefined
  }

  return {
    category_id: selectedCategory.value.id,
    scenario_id: selectedScenario.value.id,
    target_id: selectedTarget.value.id,
    difficulty_id: selectedDifficulty.value.id,
  }
})
const openingSuggestion = computed(() => buildOpeningSuggestion(trainingSelection.value))
const sourceMeta = computed(() => buildScenarioTrainingSourceMeta(trainingSelection.value))
const canEnterChat = computed(() => Boolean(completeSelection.value))
const hasUserMessage = computed(() => userMessage.value.trim().length > 0)
const shouldShowRealitySupport = computed(() =>
  ['analysis', 'high', 'severe', 'high-pressure', 'severe-pressure'].includes(sourceFrom.value),
)
const trainingSummary = computed(() => [
  { label: '当前模式', value: '场景训练' },
  { label: '场景分类', value: selectedCategory.value?.label ?? '未选择' },
  { label: '具体场景', value: selectedScenario.value?.title ?? '未选择' },
  { label: '训练目标', value: selectedTarget.value?.label ?? '未选择' },
  {
    label: '训练难度',
    value: selectedDifficulty.value
      ? `${selectedDifficulty.value.label}：${selectedDifficulty.value.description}`
      : '未选择',
  },
])

const {
  userMessage,
  isSubmitting,
  submitError,
  safetyNote,
  conversationMessages,
  cachedConversationRoommates,
  generationStatus,
  systemTurnNotice,
  sessionErrorState,
  hasActiveConversation,
  canEnterReview,
  reviewGateMessage,
  chatHintMessage,
  sendMessage,
  resetConversation,
  retryFromExpiredSession,
  hydrateFromSimulationCache,
} = useSimulationSession({
  getScenario: () => selectedScenario.value?.title ?? '场景训练',
  getRoommates: () => trainingRoommates,
  getRiskLevel: () => undefined,
  getUseEventArchive: () => false,
  getContext: () => buildTrainingContext(),
  getSourceMeta: () => sourceMeta.value,
})

function isRecord(value: unknown): value is RecordLike {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function firstQueryValue(value: unknown) {
  if (Array.isArray(value)) {
    return typeof value[0] === 'string' ? value[0] : ''
  }

  return typeof value === 'string' ? value : ''
}

function isTrainingStep(value: unknown): value is TrainingStep {
  return typeof value === 'string' && trainingSteps.some((step) => step.id === value)
}

function normalizeSourceFrom(value: string) {
  return value.trim().slice(0, 32)
}

function buildTrainingContext() {
  const parts = [
    '当前模式：场景训练',
    `场景分类：${selectedCategory.value?.label ?? '未选择'}`,
    `具体场景：${selectedScenario.value?.title ?? '未选择'}`,
    `训练目标：${selectedTarget.value?.label ?? '未选择'}`,
    `训练难度：${selectedDifficulty.value?.label ?? '未选择'}`,
  ]

  if (selectedDifficulty.value?.description) {
    parts.push(`难度说明：${selectedDifficulty.value.description}`)
  }

  parts.push(`开场白：${openingMessage.value.trim() || '用户尚未填写'}`)

  return parts.join('；')
}

function getDeepestAvailableStep(): TrainingStep {
  if (!selectedCategory.value) {
    return 'category'
  }
  if (!selectedScenario.value) {
    return 'scenario'
  }
  if (!selectedTarget.value) {
    return 'target'
  }
  if (!selectedDifficulty.value) {
    return 'difficulty'
  }

  return 'opening'
}

function isStepUnlocked(step: TrainingStep) {
  if (step === 'category') {
    return true
  }
  if (step === 'scenario') {
    return Boolean(selectedCategory.value)
  }
  if (step === 'target') {
    return Boolean(selectedScenario.value)
  }
  if (step === 'difficulty') {
    return Boolean(selectedTarget.value)
  }

  return Boolean(completeSelection.value)
}

function stepState(step: TrainingStep) {
  const activeIndex = trainingSteps.findIndex((item) => item.id === currentStep.value)
  const stepIndex = trainingSteps.findIndex((item) => item.id === step)

  return {
    active: step === currentStep.value,
    done: stepIndex < activeIndex && isStepUnlocked(step),
    disabled: !isStepUnlocked(step),
  }
}

function goToStep(step: TrainingStep) {
  if (!isStepUnlocked(step)) {
    return
  }

  currentStep.value = step
  if (step === 'chat') {
    prefillChatInputFromOpening()
  }
}

function normalizeCurrentStep() {
  if (!isStepUnlocked(currentStep.value)) {
    currentStep.value = getDeepestAvailableStep()
  }
}

function resetConversationForSelectionChange() {
  resetConversation()
}

function selectCategory(id: TrainingCategoryId) {
  if (categoryId.value !== id) {
    resetConversationForSelectionChange()
  }

  categoryId.value = id
  const scenario = getTrainingScenario(scenarioId.value)
  if (!scenario || scenario.category_id !== id) {
    scenarioId.value = undefined
  }
  currentStep.value = 'scenario'
}

function selectScenario(id: TrainingScenarioId) {
  const scenario = getTrainingScenario(id)
  if (!scenario || scenario.category_id !== categoryId.value) {
    return
  }

  if (scenarioId.value !== id) {
    resetConversationForSelectionChange()
  }
  scenarioId.value = id
  currentStep.value = 'target'
}

function selectTarget(id: TrainingTargetId) {
  if (targetId.value !== id) {
    resetConversationForSelectionChange()
  }
  targetId.value = id
  currentStep.value = 'difficulty'
}

function selectDifficulty(id: TrainingDifficultyId) {
  if (difficultyId.value !== id) {
    resetConversationForSelectionChange()
  }
  difficultyId.value = id
  currentStep.value = 'opening'
  applyOpeningSuggestionIfAllowed()
}

function markOpeningTouched() {
  openingTouched.value = true
}

function applyOpeningSuggestionIfAllowed() {
  const suggestion = openingSuggestion.value
  if (!suggestion || openingTouched.value) {
    return
  }

  openingMessage.value = suggestion
}

function useCurrentSuggestion() {
  const suggestion = openingSuggestion.value
  if (!suggestion) {
    return
  }

  openingTouched.value = false
  openingMessage.value = suggestion
}

function prefillChatInputFromOpening() {
  if (hasActiveConversation.value || userMessage.value.trim()) {
    return
  }

  userMessage.value = openingMessage.value
}

function enterChat() {
  if (!canEnterChat.value) {
    return
  }

  currentStep.value = 'chat'
  prefillChatInputFromOpening()
}

function clearDraftStorage() {
  try {
    localStorage.removeItem(scenarioTrainingDraftKey)
  } catch {
    // ignore restricted storage
  }
}

function persistDraft() {
  if (!hasMounted.value) {
    return
  }

  if (
    currentStep.value === defaultStep &&
    !selectedCategory.value &&
    !selectedScenario.value &&
    !selectedTarget.value &&
    !selectedDifficulty.value &&
    !openingMessage.value &&
    !sourceFrom.value
  ) {
    clearDraftStorage()
    return
  }

  const draft: ScenarioTrainingDraft = {
    step: currentStep.value,
    category_id: selectedCategory.value?.id,
    scenario_id: selectedScenario.value?.id,
    target_id: selectedTarget.value?.id,
    difficulty_id: selectedDifficulty.value?.id,
    opening_message: openingMessage.value,
    opening_touched: openingTouched.value,
    from: sourceFrom.value || undefined,
  }

  try {
    localStorage.setItem(scenarioTrainingDraftKey, JSON.stringify(draft))
  } catch {
    // ignore restricted storage
  }
}

function hydrateDraft() {
  try {
    const raw = localStorage.getItem(scenarioTrainingDraftKey)
    const parsed = raw ? (JSON.parse(raw) as unknown) : null
    if (!isRecord(parsed)) {
      return
    }

    const category = getTrainingCategory(
      typeof parsed.category_id === 'string' ? parsed.category_id : undefined,
    )
    const scenario = getTrainingScenario(
      typeof parsed.scenario_id === 'string' ? parsed.scenario_id : undefined,
    )
    const target = getTrainingTarget(
      typeof parsed.target_id === 'string' ? parsed.target_id : undefined,
    )
    const difficulty = getTrainingDifficulty(
      typeof parsed.difficulty_id === 'string' ? parsed.difficulty_id : undefined,
    )

    categoryId.value = scenario?.category_id ?? category?.id
    scenarioId.value =
      scenario && (!categoryId.value || scenario.category_id === categoryId.value)
        ? scenario.id
        : undefined
    targetId.value = target?.id
    difficultyId.value = difficulty?.id
    openingMessage.value = typeof parsed.opening_message === 'string' ? parsed.opening_message : ''
    openingTouched.value =
      typeof parsed.opening_touched === 'boolean' ? parsed.opening_touched : false
    sourceFrom.value = typeof parsed.from === 'string' ? normalizeSourceFrom(parsed.from) : ''
    currentStep.value = isTrainingStep(parsed.step) ? parsed.step : getDeepestAvailableStep()
    normalizeCurrentStep()
  } catch {
    // ignore malformed draft
  }
}

function applyQueryPrefill() {
  const category = getTrainingCategory(firstQueryValue(route.query.category).trim())
  const scenario = getTrainingScenario(firstQueryValue(route.query.scenario).trim())
  const target = getTrainingTarget(firstQueryValue(route.query.target).trim())
  const difficulty = getTrainingDifficulty(firstQueryValue(route.query.difficulty).trim())
  const practice = firstQueryValue(route.query.practice).trim()
  const from = normalizeSourceFrom(firstQueryValue(route.query.from))
  const hadSelectionQuery = Boolean(category || scenario || target || difficulty)

  if (category) {
    categoryId.value = category.id
  }
  if (scenario) {
    categoryId.value = scenario.category_id
    scenarioId.value = scenario.id
  } else if (category && selectedScenario.value?.category_id !== category.id) {
    scenarioId.value = undefined
  }
  if (target) {
    targetId.value = target.id
  }
  if (difficulty) {
    difficultyId.value = difficulty.id
  }
  if (from) {
    sourceFrom.value = from
  }
  if (practice) {
    resetConversation()
    openingMessage.value = practice
    openingTouched.value = true
  }

  normalizeCurrentStep()

  if (practice && completeSelection.value) {
    currentStep.value = 'chat'
    prefillChatInputFromOpening()
    return
  }

  if (hadSelectionQuery && completeSelection.value && currentStep.value !== 'chat') {
    currentStep.value = 'opening'
  }
}

function doesHydratedSourceMetaMatchCurrentTraining(
  sourceMeta: ReturnType<typeof buildScenarioTrainingSourceMeta>,
) {
  return (
    sourceMeta?.mode === 'scenario_training' &&
    completeSelection.value !== undefined &&
    sourceMeta.category_id === completeSelection.value.category_id &&
    sourceMeta.scenario_id === completeSelection.value.scenario_id &&
    sourceMeta.target_id === completeSelection.value.target_id &&
    sourceMeta.difficulty_id === completeSelection.value.difficulty_id
  )
}

function resetTraining() {
  resetConversation()
  categoryId.value = undefined
  scenarioId.value = undefined
  targetId.value = undefined
  difficultyId.value = undefined
  openingMessage.value = ''
  openingTouched.value = false
  sourceFrom.value = ''
  currentStep.value = defaultStep
  clearDraftStorage()
}

function avatarShortLabel(key: RoommateAvatarKey) {
  return roommateAvatarOptions.find((option) => option.key === key)?.shortLabel ?? key.slice(0, 1)
}

function speakerLabel(speaker: ReviewDialogueLine['speaker']) {
  if (speaker === 'user') {
    return '你'
  }
  if (speaker === 'system') {
    return '系统'
  }

  const roommate =
    cachedConversationRoommates.value.find((item) => item.id === speaker) ??
    trainingRoommates.find((item) => item.id === speaker)
  return roommate?.name ?? speaker.replace('roommate_', '舍友 ')
}

function roommateForSpeaker(speaker: ReviewDialogueLine['speaker']) {
  return speaker.startsWith('roommate_')
    ? (cachedConversationRoommates.value.find((item) => item.id === speaker) ??
        trainingRoommates.find((item) => item.id === speaker))
    : undefined
}

function speakerAvatarKey(speaker: ReviewDialogueLine['speaker']) {
  return roommateForSpeaker(speaker)?.avatar
}

function speakerAvatarShortLabel(speaker: ReviewDialogueLine['speaker']) {
  const key = speakerAvatarKey(speaker)
  return key ? avatarShortLabel(key) : ''
}

function messageClass(speaker: ReviewDialogueLine['speaker']) {
  if (speaker === 'user') {
    return 'conversation-message-user'
  }
  if (speaker === 'system') {
    return 'conversation-message-system'
  }

  return 'conversation-message-roommate'
}

onMounted(() => {
  hydrateDraft()
  applyQueryPrefill()
  applyOpeningSuggestionIfAllowed()

  if (currentStep.value === 'chat') {
    const hydrated = firstQueryValue(route.query.practice).trim()
      ? {}
      : hydrateFromSimulationCache()
    const scenarioMatches =
      !hydrated.scenario ||
      !selectedScenario.value ||
      hydrated.scenario === selectedScenario.value.title
    const sourceMetaMatches = doesHydratedSourceMetaMatchCurrentTraining(hydrated.sourceMeta)

    if (!scenarioMatches || !sourceMetaMatches) {
      resetConversation()
    }
    prefillChatInputFromOpening()
  }

  hasMounted.value = true
  persistDraft()
})

watch(
  [currentStep, categoryId, scenarioId, targetId, difficultyId, openingMessage, openingTouched],
  () => {
    normalizeCurrentStep()
    applyOpeningSuggestionIfAllowed()
    persistDraft()
  },
)
</script>

<template>
  <main class="page scenario-training-page simulation-page bg-diagonal-stripes">
    <section class="simulation-header-card card-border pop-card pop-shadow">
      <div class="simulation-title-block">
        <h1>场景训练</h1>
        <div class="simulation-subtitle-chip card-border">六步沟通演练</div>
      </div>
      <p>先选固定训练目录，再把开场白带入 AI 对话；复盘会基于本轮模拟记录生成。</p>
      <div class="scenario-header-actions">
        <RouterLink class="secondary-action pop-shadow" :to="{ name: 'rehearsal' }">
          返回演练首页
        </RouterLink>
        <button class="primary-action pop-shadow" type="button" @click="resetTraining">
          <span class="material-symbol" aria-hidden="true">refresh</span>
          重置训练
        </button>
      </div>
    </section>

    <nav class="scenario-stepper card-border pop-card" aria-label="场景训练步骤">
      <button
        v-for="(step, index) in trainingSteps"
        :key="step.id"
        type="button"
        class="scenario-stepper-item"
        :class="stepState(step.id)"
        :disabled="stepState(step.id).disabled"
        @click="goToStep(step.id)"
      >
        <span>{{ index + 1 }}</span>
        {{ step.label }}
      </button>
    </nav>

    <p class="scenario-safety-note card-border pop-card">
      <span class="material-symbol" aria-hidden="true">health_and_safety</span>
      {{ shouldShowRealitySupport ? analysisSafetyCopy : rehearsalSafetyCopy }}
    </p>

    <section v-if="currentStep !== 'chat'" class="scenario-training-workspace">
      <section class="scenario-step-card card-border pop-card pop-shadow">
        <template v-if="currentStep === 'category'">
          <p class="eyebrow pill-label">Step 1</p>
          <h2>选择场景分类</h2>
          <div class="scenario-option-grid">
            <button
              v-for="category in trainingCategories"
              :key="category.id"
              type="button"
              class="scenario-option-btn pop-shadow"
              :class="{ active: selectedCategory?.id === category.id }"
              @click="selectCategory(category.id)"
            >
              <span class="material-symbol" aria-hidden="true">category</span>
              {{ category.label }}
            </button>
          </div>
        </template>

        <template v-else-if="currentStep === 'scenario'">
          <p class="eyebrow pill-label">Step 2</p>
          <h2>选择具体场景</h2>
          <p class="scenario-step-copy">
            当前分类：{{ selectedCategory?.label ?? '请先选择分类' }}
          </p>
          <div class="scenario-option-grid">
            <button
              v-for="scenario in scenarioOptions"
              :key="scenario.id"
              type="button"
              class="scenario-option-btn pop-shadow"
              :class="{ active: selectedScenario?.id === scenario.id }"
              @click="selectScenario(scenario.id)"
            >
              <span class="material-symbol" aria-hidden="true">sms</span>
              {{ scenario.title }}
            </button>
          </div>
        </template>

        <template v-else-if="currentStep === 'target'">
          <p class="eyebrow pill-label">Step 3</p>
          <h2>选择训练目标</h2>
          <div class="scenario-option-grid">
            <button
              v-for="target in trainingTargets"
              :key="target.id"
              type="button"
              class="scenario-option-btn pop-shadow"
              :class="{ active: selectedTarget?.id === target.id }"
              @click="selectTarget(target.id)"
            >
              <span class="material-symbol" aria-hidden="true">flag</span>
              {{ target.label }}
            </button>
          </div>
        </template>

        <template v-else-if="currentStep === 'difficulty'">
          <p class="eyebrow pill-label">Step 4</p>
          <h2>选择训练难度</h2>
          <div class="scenario-difficulty-list">
            <button
              v-for="difficulty in trainingDifficulties"
              :key="difficulty.id"
              type="button"
              class="scenario-difficulty-btn pop-shadow"
              :class="{ active: selectedDifficulty?.id === difficulty.id }"
              @click="selectDifficulty(difficulty.id)"
            >
              <strong>{{ difficulty.label }}</strong>
              <span>{{ difficulty.description }}</span>
            </button>
          </div>
        </template>

        <template v-else>
          <p class="eyebrow pill-label">Step 5</p>
          <h2>准备开场白</h2>
          <p class="scenario-step-copy">这里的内容会预填到聊天输入框，进入对话后仍可修改。</p>
          <label class="scenario-opening-field">
            <span>开场白</span>
            <textarea
              v-model="openingMessage"
              rows="5"
              maxlength="280"
              placeholder="写下你准备先说出口的一句话"
              @input="markOpeningTouched"
            ></textarea>
          </label>
          <article v-if="openingSuggestion" class="scenario-suggestion card-border">
            <span class="material-symbol" aria-hidden="true">tips_and_updates</span>
            <p>{{ openingSuggestion }}</p>
            <button class="secondary-action pop-shadow" type="button" @click="useCurrentSuggestion">
              套用建议
            </button>
          </article>
          <div class="scenario-step-actions">
            <button
              class="secondary-action pop-shadow"
              type="button"
              @click="goToStep('difficulty')"
            >
              返回难度
            </button>
            <button
              class="primary-action pop-shadow"
              type="button"
              :disabled="!canEnterChat"
              @click="enterChat"
            >
              进入聊天
              <span class="material-symbol" aria-hidden="true">arrow_forward</span>
            </button>
          </div>
        </template>
      </section>

      <aside class="scenario-summary-panel card-border pop-card">
        <h2>当前训练</h2>
        <dl>
          <div v-for="item in trainingSummary" :key="item.label">
            <dt>{{ item.label }}</dt>
            <dd>{{ item.value }}</dd>
          </div>
        </dl>
      </aside>
    </section>

    <section v-else class="scenario-chat-stage">
      <section class="scenario-chat-summary card-border pop-card pop-shadow">
        <div v-for="item in trainingSummary" :key="item.label" class="scenario-chat-summary-item">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </div>
      </section>

      <section class="chat-panel card-border pop-card">
        <header class="chat-header card-border">
          <div class="chat-title chat-title-row">
            <span class="material-symbol" aria-hidden="true">chat</span>
            <h2>场景训练对话</h2>
          </div>
          <button class="primary-action pop-shadow" type="button" @click="resetTraining">
            <span class="material-symbol" aria-hidden="true">refresh</span>
            重置
          </button>
        </header>

        <div class="chat-content">
          <p class="chat-system card-border">
            当前场景：{{ selectedScenario?.title ?? '场景训练' }}。先发送或修改你的开场白。
          </p>

          <Transition name="chat-state">
            <section
              v-if="sessionErrorState === 'expired'"
              class="simulation-session-error pop-card pop-shadow"
            >
              <span class="material-symbol" aria-hidden="true">sync_problem</span>
              <h2>会话已失效</h2>
              <p>当前会话无法继续，请重新开始后再发送。</p>
              <button
                class="primary-action pop-shadow"
                type="button"
                @click="retryFromExpiredSession(userMessage)"
              >
                重新开始
              </button>
            </section>
          </Transition>

          <Transition name="chat-state" mode="out-in">
            <TransitionGroup
              v-if="conversationMessages.length > 0"
              key="thread"
              name="chat-message"
              tag="div"
              class="conversation-thread"
            >
              <article
                v-for="(line, index) in conversationMessages"
                :key="`${line.speaker}-${index}-${line.message}`"
                :class="['conversation-message', messageClass(line.speaker)]"
              >
                <div class="conversation-message-heading">
                  <span
                    v-if="speakerAvatarKey(line.speaker)"
                    :class="[
                      'conversation-message-avatar',
                      `roommate-avatar-${speakerAvatarKey(line.speaker)}`,
                    ]"
                    aria-hidden="true"
                  >
                    {{ speakerAvatarShortLabel(line.speaker) }}
                  </span>
                  <span>{{ speakerLabel(line.speaker) }}</span>
                </div>
                <p>{{ line.message }}</p>
              </article>
              <article
                v-if="systemTurnNotice"
                key="system-turn-notice"
                class="conversation-message conversation-message-system"
              >
                <span>系统</span>
                <p>{{ systemTurnNotice }}</p>
              </article>
              <article
                v-if="isSubmitting"
                key="typing"
                class="conversation-message conversation-message-roommate"
              >
                <span>{{ generationStatus || '正在生成舍友回复...' }}</span>
                <p class="typing-indicator" aria-live="polite">
                  <i></i>
                  <i></i>
                  <i></i>
                </p>
              </article>
            </TransitionGroup>

            <div v-else key="preview" class="chat-preview-state">
              <article class="chat-user" :class="{ 'chat-user-empty': !hasUserMessage }">
                <div class="chat-avatar roommate-avatar-letter" aria-hidden="true">你</div>
                <p class="chat-bubble chat-bubble-user pop-shadow">
                  {{ userMessage || openingMessage || '进入聊天后，先写一句你准备说出口的话' }}
                </p>
              </article>
            </div>
          </Transition>

          <div class="chat-hint card-border pop-card">
            <p class="chat-hint-label">
              <span class="material-symbol" aria-hidden="true">tips_and_updates</span>
              建议先表达感受，再提出具体请求。
            </p>
            <p>{{ chatHintMessage }}</p>
          </div>

          <div class="chat-footer-note card-border pop-card">
            <p>{{ safetyNote || rehearsalSafetyCopy }}</p>
          </div>
        </div>

        <form class="simulation-input-bar card-border" @submit.prevent="sendMessage">
          <div class="comm-input-wrap">
            <input
              v-model="userMessage"
              type="text"
              placeholder="输入或调整你的开场白"
              aria-label="输入你的回复"
            />
            <button class="microphone-btn" type="button" aria-label="麦克风">
              <span class="material-symbol" aria-hidden="true">mic</span>
            </button>
          </div>
          <button class="primary-action pop-shadow" type="submit" :disabled="!hasUserMessage">
            <span v-if="isSubmitting">排队发送</span>
            <span v-else>发送</span>
            <span class="material-symbol" aria-hidden="true">send</span>
          </button>
        </form>

        <p v-if="submitError" class="error-text">{{ submitError }}</p>
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
    </section>
  </main>
</template>

<style scoped>
.scenario-training-page {
  display: grid;
  gap: 16px;
}

.scenario-header-actions,
.scenario-step-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.scenario-stepper {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 8px;
  background: var(--surface-low);
  padding: 10px;
}

.scenario-stepper-item {
  display: inline-flex;
  min-width: 0;
  min-height: 46px;
  align-items: center;
  justify-content: center;
  gap: 7px;
  border: 2px solid var(--ink);
  border-radius: 999px;
  background: var(--surface-container);
  color: var(--ink-soft);
  font-weight: 900;
}

.scenario-stepper-item span {
  display: inline-flex;
  width: 22px;
  height: 22px;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: #ffffff;
  color: var(--ink);
  font-size: 0.78rem;
}

.scenario-stepper-item.active {
  background: var(--primary);
  color: #ffffff;
  box-shadow: 3px 3px 0 0 var(--shadow-dark);
}

.scenario-stepper-item.done {
  background: var(--quaternary);
  color: var(--ink);
}

.scenario-stepper-item:disabled {
  cursor: not-allowed;
  opacity: 0.52;
}

.scenario-safety-note {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin: 0;
  background: var(--secondary-soft);
  padding: 12px 14px;
  color: var(--ink-soft);
  font-weight: 800;
  line-height: 1.55;
}

.scenario-safety-note .material-symbol {
  color: var(--primary);
}

.scenario-training-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(260px, 0.34fr);
  gap: 16px;
  align-items: start;
}

.scenario-step-card,
.scenario-summary-panel {
  display: grid;
  gap: 16px;
  background: var(--card);
  padding: 22px;
}

.scenario-step-card h2,
.scenario-step-card p,
.scenario-summary-panel h2 {
  margin: 0;
}

.scenario-step-copy {
  color: var(--ink-soft);
  font-weight: 800;
}

.scenario-option-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.scenario-option-btn,
.scenario-difficulty-btn {
  min-height: 64px;
  border: 2px solid var(--ink);
  border-radius: 14px;
  background: var(--surface-container);
  color: var(--ink);
  font-weight: 900;
  transition:
    transform 160ms ease,
    box-shadow 160ms ease,
    background-color 160ms ease;
}

.scenario-option-btn {
  display: inline-flex;
  align-items: center;
  justify-content: flex-start;
  gap: 10px;
  padding: 12px 14px;
  text-align: left;
}

.scenario-option-btn:hover,
.scenario-difficulty-btn:hover {
  box-shadow: 3px 3px 0 0 var(--shadow-dark);
  transform: translate(-1px, -2px);
}

.scenario-option-btn.active,
.scenario-difficulty-btn.active {
  background: var(--primary-container);
  color: #ffffff;
  box-shadow: 4px 4px 0 0 var(--shadow-dark);
}

.scenario-difficulty-list {
  display: grid;
  gap: 12px;
}

.scenario-difficulty-btn {
  display: grid;
  gap: 4px;
  padding: 14px;
  text-align: left;
}

.scenario-difficulty-btn span {
  color: inherit;
  line-height: 1.45;
  opacity: 0.84;
}

.scenario-opening-field {
  display: grid;
  gap: 8px;
  color: var(--ink);
  font-weight: 900;
}

.scenario-opening-field textarea {
  width: 100%;
  resize: vertical;
  border: 2px solid var(--ink);
  border-radius: 14px;
  background: var(--surface-low);
  padding: 12px 14px;
  color: var(--ink);
  font: inherit;
  line-height: 1.55;
}

.scenario-opening-field textarea:focus {
  outline: 3px solid var(--tertiary);
  outline-offset: 2px;
}

.scenario-suggestion {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  background: var(--surface-container-low);
  padding: 12px;
}

.scenario-suggestion p {
  color: var(--ink-soft);
  font-weight: 800;
  line-height: 1.55;
}

.scenario-summary-panel dl {
  display: grid;
  gap: 12px;
  margin: 0;
}

.scenario-summary-panel div {
  display: grid;
  gap: 4px;
  border-bottom: 2px dashed var(--border);
  padding-bottom: 10px;
}

.scenario-summary-panel dt {
  color: var(--ink-soft);
  font-size: 0.82rem;
  font-weight: 900;
}

.scenario-summary-panel dd {
  margin: 0;
  color: var(--ink);
  font-weight: 900;
  line-height: 1.45;
}

.scenario-chat-stage {
  display: grid;
  gap: 16px;
}

.scenario-chat-summary {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
  background: var(--surface-low);
  padding: 14px;
}

.scenario-chat-summary-item {
  display: grid;
  gap: 4px;
  min-width: 0;
  border: 2px solid var(--border);
  border-radius: 12px;
  background: #ffffff;
  padding: 10px;
}

.scenario-chat-summary-item span {
  color: var(--ink-soft);
  font-size: 0.76rem;
  font-weight: 900;
}

.scenario-chat-summary-item strong {
  color: var(--ink);
  font-size: 0.9rem;
  line-height: 1.35;
}

.chat-title h2 {
  margin: 0;
  font-size: 1.2rem;
}

.error-text {
  margin: 12px 16px 16px;
  color: var(--error);
  font-weight: 700;
}

.simulation-meta {
  margin: 0;
  color: var(--ink-soft);
  font-size: 14px;
}

.simulation-session-error {
  display: grid;
  justify-items: center;
  gap: 10px;
  border: 2px solid var(--ink);
  border-radius: 16px;
  padding: 18px;
  background: var(--surface);
  text-align: center;
}

.simulation-session-error > .material-symbol {
  display: inline-flex;
  width: 42px;
  height: 42px;
  align-items: center;
  justify-content: center;
  border: 2px solid var(--ink);
  border-radius: 999px;
  background: var(--secondary-soft);
  color: var(--primary);
  box-shadow: 2px 2px 0 0 var(--shadow-dark);
  font-size: 1.35rem;
}

.simulation-session-error h2,
.simulation-session-error p {
  margin: 0;
}

@media (max-width: 920px) {
  .scenario-stepper,
  .scenario-chat-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .scenario-training-workspace {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 560px) {
  .scenario-stepper,
  .scenario-option-grid,
  .scenario-chat-summary {
    grid-template-columns: 1fr;
  }

  .simulation-header-card,
  .scenario-step-card,
  .scenario-summary-panel {
    padding: 18px;
  }

  .scenario-suggestion {
    grid-template-columns: 1fr;
  }

  .scenario-header-actions,
  .scenario-step-actions,
  .scenario-header-actions a,
  .scenario-header-actions button,
  .scenario-step-actions button {
    width: 100%;
  }

  .simulation-input-bar {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
