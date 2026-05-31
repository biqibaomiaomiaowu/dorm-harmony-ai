<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { useGsapMotion } from '@/composables/useGsapMotion'
import { useSimulationSession } from '@/composables/useSimulationSession'
import {
  buildScenarioDifficultyContext,
  buildScenarioTrainingRoommates,
  getScenarioDifficultyPressureProfile,
  getScenarioReplyPolicy,
  summarizeScenarioRoommates,
} from '@/data/scenarioDifficultyPolicy'
import {
  buildOpeningSuggestion,
  buildScenarioTrainingSourceMeta,
  getTrainingCategory,
  getTrainingDifficulty,
  getTrainingScenario,
  getTrainingTarget,
  trainingCategories,
  trainingDifficulties,
  trainingScenarios,
  trainingTargets,
  type TrainingCategoryId,
  type TrainingDifficultyId,
  type TrainingScenarioId,
  type TrainingSelection,
  type TrainingTargetId,
} from '@/data/trainingCatalog'
import {
  getTrainingScenarioUiMeta,
  type TrainingScenarioUiMeta,
} from '@/data/trainingScenarioMeta'
import {
  roommateAvatarOptions,
  type ReviewDialogueLine,
  type RoommateAvatarKey,
} from '@/data/week1'

type TrainingStep = 'category' | 'scenario' | 'target' | 'difficulty' | 'opening' | 'chat'
type FilterValue<T extends string> = 'all' | T

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
const trainingOpeningContextMaxLength = 120
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
const categoryFilter = ref<FilterValue<TrainingCategoryId>>('all')
const targetFilter = ref<FilterValue<TrainingTargetId>>('all')
const difficultyFilter = ref<FilterValue<TrainingDifficultyId>>('all')
const scenarioPageRef = ref<HTMLElement | null>(null)
const taskStationRef = ref<HTMLElement | null>(null)
const taskGridRef = ref<HTMLElement | null>(null)
const previewPanelRef = ref<HTMLElement | null>(null)
const { withContext, animatePageIn, animateListEnter, prefersReducedMotion } = useGsapMotion(
  () => scenarioPageRef.value,
)
let stationAnimationRun = 0

const selectedCategory = computed(() => getTrainingCategory(categoryId.value))
const selectedScenario = computed(() => {
  const scenario = getTrainingScenario(scenarioId.value)
  return scenario && scenario.category_id === categoryId.value ? scenario : undefined
})
const selectedTarget = computed(() => getTrainingTarget(targetId.value))
const selectedDifficulty = computed(() => getTrainingDifficulty(difficultyId.value))
const trainingRoommates = computed(() =>
  buildScenarioTrainingRoommates(selectedDifficulty.value?.id),
)
const replyPolicy = computed(() => getScenarioReplyPolicy(selectedDifficulty.value?.id))
const difficultyPressureProfile = computed(() =>
  getScenarioDifficultyPressureProfile(selectedDifficulty.value?.id),
)
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
const selectedScenarioMeta = computed(() =>
  selectedScenario.value ? getTrainingScenarioUiMeta(selectedScenario.value.id) : undefined,
)
const sourceMeta = computed(() => buildScenarioTrainingSourceMeta(trainingSelection.value))
const canEnterChat = computed(() => Boolean(completeSelection.value))
const hasUserMessage = computed(() => userMessage.value.trim().length > 0)
const shouldShowRealitySupport = computed(() =>
  ['analysis', 'high', 'severe', 'high-pressure', 'severe-pressure'].includes(sourceFrom.value) ||
  selectedDifficulty.value?.id === 'advanced' ||
  selectedDifficulty.value?.id === 'challenge',
)
const replyChainRangeLabel = computed(() => `${replyPolicy.value.min}-${replyPolicy.value.max} 条`)
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
  {
    label: '虚拟舍友数',
    value: selectedDifficulty.value ? `${trainingRoommates.value.length} 位` : '待选择',
  },
  {
    label: '回复强度',
    value: selectedDifficulty.value ? replyChainRangeLabel.value : '待选择',
  },
])
const filterSummary = computed(() => [
  {
    label: '冲突类型',
    value:
      categoryFilter.value === 'all'
        ? '全部'
        : getTrainingCategory(categoryFilter.value)?.label ?? '全部',
  },
  {
    label: '训练目标',
    value:
      targetFilter.value === 'all' ? '全部' : getTrainingTarget(targetFilter.value)?.label ?? '全部',
  },
  {
    label: '训练难度',
    value:
      difficultyFilter.value === 'all'
        ? '全部'
        : getTrainingDifficulty(difficultyFilter.value)?.label ?? '全部',
  },
])

const taskCards = computed(() =>
  trainingScenarios.map((scenario) => ({
    scenario,
    category: getTrainingCategory(scenario.category_id),
    meta: getTrainingScenarioUiMeta(scenario.id),
  })),
)
const filteredTaskCards = computed(() =>
  taskCards.value.filter(({ scenario, meta }) => {
    const matchesCategory =
      categoryFilter.value === 'all' || scenario.category_id === categoryFilter.value
    const matchesTarget =
      targetFilter.value === 'all' || meta.suggested_target_ids.includes(targetFilter.value)
    const matchesDifficulty =
      difficultyFilter.value === 'all' ||
      meta.suggested_difficulty_ids.includes(difficultyFilter.value)

    return matchesCategory && matchesTarget && matchesDifficulty
  }),
)
const recommendationRows = computed(() => {
  if (sourceFrom.value !== 'analysis') {
    return []
  }

  return [
    { label: '推荐场景', value: selectedScenario.value?.title ?? '待选择' },
    { label: '推荐目标', value: selectedTarget.value?.label ?? '待选择' },
    { label: '推荐难度', value: selectedDifficulty.value?.label ?? '待选择' },
  ]
})
const difficultyTrackStyle = computed(() => {
  const activeIndex = trainingDifficulties.findIndex((item) => item.id === selectedDifficulty.value?.id)
  const safeIndex = activeIndex >= 0 ? activeIndex : 0
  const width = 100 / trainingDifficulties.length

  return {
    width: `${width}%`,
    transform: `translateX(${safeIndex * 100}%)`,
  }
})

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
  getRoommates: () => trainingRoommates.value,
  getRiskLevel: () => undefined,
  getUseEventArchive: () => false,
  getContext: () => buildTrainingContext(),
  getSourceMeta: () => sourceMeta.value,
  getReplyChainTargetRange: () => getScenarioReplyPolicy(selectedDifficulty.value?.id),
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

function summarizeTrainingContextValue(value: string, maxLength: number) {
  const normalizedValue = value.replace(/\s+/g, ' ').trim()

  if (normalizedValue.length <= maxLength) {
    return normalizedValue
  }

  return `${normalizedValue.slice(0, Math.max(0, maxLength - 1))}…`
}

function buildTrainingContext() {
  const parts = [
    '当前模式：场景训练',
    `场景分类：${selectedCategory.value?.label ?? '未选择'}`,
    `具体场景：${selectedScenario.value?.title ?? '未选择'}`,
    `训练目标：${selectedTarget.value?.label ?? '未选择'}`,
    `训练难度：${selectedDifficulty.value?.label ?? '未选择'}`,
    `回复链范围：${replyChainRangeLabel.value}`,
    `本轮 AI 舍友阵容：${summarizeScenarioRoommates(trainingRoommates.value) || '待选择'}`,
    `难度压力画像：${difficultyPressureProfile.value}`,
  ]

  if (selectedDifficulty.value?.description) {
    parts.push(`难度说明：${selectedDifficulty.value.description}`)
    parts.push(buildScenarioDifficultyContext(selectedDifficulty.value.id))
  }

  if (selectedDifficulty.value?.id === 'challenge') {
    parts.push(
      '挑战难度行为要求：本轮训练应更难协商，可出现多人反问、站队、推诿、冷处理和转移责任；不要过早缓和或同意；但不得辱骂、威胁、羞辱、歧视、操控或人格评价。',
    )
  }

  parts.push(
    `开场白摘要：${summarizeTrainingContextValue(
      openingMessage.value.trim() || '用户尚未填写',
      trainingOpeningContextMaxLength,
    )}`,
  )

  return parts.join('；')
}

function targetLabel(targetIdValue: TrainingTargetId) {
  return getTrainingTarget(targetIdValue)?.label ?? targetIdValue
}

function difficultyLabel(difficultyIdValue: TrainingDifficultyId) {
  return getTrainingDifficulty(difficultyIdValue)?.label ?? difficultyIdValue
}

function complexityDots(meta: TrainingScenarioUiMeta) {
  return Array.from({ length: 5 }, (_, index) => index < meta.complexity)
}

function isTaskSelected(id: TrainingScenarioId) {
  return selectedScenario.value?.id === id
}

function selectTaskScenario(id: TrainingScenarioId) {
  const scenario = getTrainingScenario(id)
  if (!scenario) {
    return
  }

  const meta = getTrainingScenarioUiMeta(id)
  const nextTargetId =
    targetId.value && meta.suggested_target_ids.includes(targetId.value)
      ? targetId.value
      : meta.suggested_target_ids[0]
  const nextDifficultyId =
    difficultyId.value && meta.suggested_difficulty_ids.includes(difficultyId.value)
      ? difficultyId.value
      : meta.suggested_difficulty_ids[0]

  if (
    categoryId.value !== scenario.category_id ||
    scenarioId.value !== scenario.id ||
    targetId.value !== nextTargetId ||
    difficultyId.value !== nextDifficultyId
  ) {
    resetConversationForSelectionChange()
  }

  categoryId.value = scenario.category_id
  scenarioId.value = scenario.id
  targetId.value = nextTargetId
  difficultyId.value = nextDifficultyId
  currentStep.value = 'opening'
  applyOpeningSuggestionIfAllowed()
  animatePreviewUpdate()
}

function roommateBehaviorHint(roommate: {
  personality_tag: string
  traits?: { directness: number; avoidance: number; solution_willingness: number; empathy: number }
}) {
  const traits = roommate.traits
  if (!traits) {
    return '会根据当前难度回应你的表达。'
  }
  if (roommate.personality_tag.includes('阴阳怪气')) {
    return '会用轻微反问和表面轻描淡写增加回应压力。'
  }
  if (roommate.personality_tag.includes('站队')) {
    return '会把多人意见拉进来，制造协商压力。'
  }
  if (traits.avoidance >= 5) {
    return '容易拖延或冷处理，需要你把请求说得更落地。'
  }
  if (traits.directness >= 5 && traits.solution_willingness <= 2) {
    return '会直接反驳，不会很快给出承诺。'
  }
  if (traits.empathy <= 1 && traits.solution_willingness <= 1) {
    return '会倾向推诿，需要你稳定边界。'
  }

  return '会给出一定阻力，适合练习澄清和回应。'
}

function useTaskSuggestion() {
  useCurrentSuggestion()
  animatePreviewUpdate()
}

function animateStationEnter() {
  const runId = stationAnimationRun + 1
  stationAnimationRun = runId
  void nextTick(() => {
    if (runId !== stationAnimationRun || currentStep.value === 'chat') {
      return
    }

    withContext(() => {
      animatePageIn(
        scenarioPageRef.value?.querySelectorAll<HTMLElement>(
          '.scenario-hero, .scenario-filter-panel, .scenario-preview-panel',
        ),
      )
      animateListEnter(taskGridRef.value?.querySelectorAll<HTMLElement>('.scenario-task-card'))
    })
  })
}

function animateTaskCards() {
  void nextTick(() => {
    if (currentStep.value === 'chat') {
      return
    }
    withContext(() => {
      animateListEnter(taskGridRef.value?.querySelectorAll<HTMLElement>('.scenario-task-card'))
    })
  })
}

function animatePreviewUpdate() {
  if (prefersReducedMotion()) {
    return
  }
  void nextTick(() => {
    if (currentStep.value === 'chat') {
      return
    }
    withContext(() => {
      animateListEnter(previewPanelRef.value?.querySelectorAll<HTMLElement>('.roommate-preview'))
    })
  })
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
    categoryFilter.value = category.id
  }
  if (scenario) {
    categoryId.value = scenario.category_id
    scenarioId.value = scenario.id
    categoryFilter.value = scenario.category_id
  } else if (category && selectedScenario.value?.category_id !== category.id) {
    scenarioId.value = undefined
  }
  if (target) {
    targetId.value = target.id
    targetFilter.value = target.id
  }
  if (difficulty) {
    difficultyId.value = difficulty.id
    difficultyFilter.value = difficulty.id
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
  categoryFilter.value = 'all'
  targetFilter.value = 'all'
  difficultyFilter.value = 'all'
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
    trainingRoommates.value.find((item) => item.id === speaker)
  return roommate?.name ?? speaker.replace('roommate_', '舍友 ')
}

function roommateForSpeaker(speaker: ReviewDialogueLine['speaker']) {
  return speaker.startsWith('roommate_')
    ? (cachedConversationRoommates.value.find((item) => item.id === speaker) ??
        trainingRoommates.value.find((item) => item.id === speaker))
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
  animateStationEnter()
})

watch(
  [currentStep, categoryId, scenarioId, targetId, difficultyId, openingMessage, openingTouched],
  () => {
    normalizeCurrentStep()
    applyOpeningSuggestionIfAllowed()
    persistDraft()
  },
)

watch([categoryFilter, targetFilter, difficultyFilter], animateTaskCards)
watch([scenarioId, targetId, difficultyId], animatePreviewUpdate)
</script>

<template>
  <main
    ref="scenarioPageRef"
    class="page scenario-training-page simulation-page bg-diagonal-stripes"
  >
    <section class="scenario-hero card-border pop-card pop-shadow">
      <div class="scenario-hero-copy">
        <div class="scenario-hero-kicker">
          <span class="material-symbol" aria-hidden="true">auto_awesome</span>
          AI practice
        </div>
        <h1>场景训练任务台</h1>
        <p>选择一个宿舍冲突任务，练习表达、回应反驳和协商规则</p>
        <div class="scenario-hero-tags" aria-label="训练能力">
          <span>AI practice</span>
          <span>多 AI 舍友</span>
          <span>难度递进</span>
          <span>可复盘</span>
        </div>
      </div>

      <div class="scenario-hero-side">
        <div v-if="recommendationRows.length > 0" class="scenario-recommendation card-border">
          <strong>根据压力分析推荐</strong>
          <dl>
            <div v-for="item in recommendationRows" :key="item.label">
              <dt>{{ item.label }}</dt>
              <dd>{{ item.value }}</dd>
            </div>
          </dl>
        </div>
        <div class="scenario-hero-actions">
          <RouterLink class="secondary-action pop-shadow" :to="{ name: 'rehearsal' }">
            返回演练首页
          </RouterLink>
          <button class="primary-action pop-shadow" type="button" @click="resetTraining">
            <span class="material-symbol" aria-hidden="true">refresh</span>
            重置训练
          </button>
        </div>
      </div>
      <span class="scenario-hero-dot scenario-hero-dot-a" aria-hidden="true"></span>
      <span class="scenario-hero-dot scenario-hero-dot-b" aria-hidden="true"></span>
    </section>

    <p class="scenario-safety-note card-border pop-card">
      <span class="material-symbol" aria-hidden="true">health_and_safety</span>
      {{ shouldShowRealitySupport ? analysisSafetyCopy : rehearsalSafetyCopy }}
    </p>

    <Transition name="scenario-stage-fade" mode="out-in">
      <section
        v-if="currentStep !== 'chat'"
        key="station"
        class="scenario-task-station"
        aria-label="场景训练任务台"
      >
        <aside ref="taskStationRef" class="scenario-filter-panel card-border pop-card pop-shadow">
          <div class="scenario-panel-heading">
            <span class="material-symbol" aria-hidden="true">tune</span>
            <h2>筛选器</h2>
          </div>

          <div class="scenario-filter-group">
            <h3>冲突类型</h3>
            <div class="scenario-chip-list">
              <button
                type="button"
                class="scenario-filter-chip"
                :class="{ active: categoryFilter === 'all' }"
                @click="categoryFilter = 'all'"
              >
                全部
              </button>
              <button
                v-for="category in trainingCategories"
                :key="category.id"
                type="button"
                class="scenario-filter-chip"
                :class="{ active: categoryFilter === category.id }"
                @click="categoryFilter = category.id"
              >
                {{ category.label }}
              </button>
            </div>
          </div>

          <div class="scenario-filter-group">
            <h3>训练目标</h3>
            <div class="scenario-chip-list">
              <button
                type="button"
                class="scenario-filter-chip"
                :class="{ active: targetFilter === 'all' }"
                @click="targetFilter = 'all'"
              >
                全部
              </button>
              <button
                v-for="target in trainingTargets"
                :key="target.id"
                type="button"
                class="scenario-filter-chip"
                :class="{ active: targetFilter === target.id }"
                @click="targetFilter = target.id"
              >
                {{ target.label }}
              </button>
            </div>
          </div>

          <div class="scenario-filter-group">
            <h3>训练难度</h3>
            <div class="scenario-chip-list">
              <button
                type="button"
                class="scenario-filter-chip"
                :class="{ active: difficultyFilter === 'all' }"
                @click="difficultyFilter = 'all'"
              >
                全部
              </button>
              <button
                v-for="difficulty in trainingDifficulties"
                :key="difficulty.id"
                type="button"
                class="scenario-filter-chip"
                :class="{ active: difficultyFilter === difficulty.id }"
                @click="difficultyFilter = difficulty.id"
              >
                {{ difficulty.label }}
              </button>
            </div>
          </div>

          <dl class="scenario-filter-summary">
            <div v-for="item in filterSummary" :key="item.label">
              <dt>{{ item.label }}</dt>
              <dd>{{ item.value }}</dd>
            </div>
          </dl>
        </aside>

        <section ref="taskGridRef" class="scenario-task-grid-column">
          <div class="scenario-task-grid-header">
            <div>
              <p class="eyebrow pill-label">训练任务</p>
              <h2>选择任务卡片</h2>
            </div>
            <span>{{ filteredTaskCards.length }} / {{ taskCards.length }}</span>
          </div>

          <TransitionGroup
            v-if="filteredTaskCards.length > 0"
            name="scenario-card-list"
            tag="div"
            class="scenario-task-grid"
          >
            <article
              v-for="{ scenario, category, meta } in filteredTaskCards"
              :key="scenario.id"
              class="scenario-task-card card-border pop-card pop-shadow"
              :class="{ selected: isTaskSelected(scenario.id) }"
            >
              <div class="scenario-task-card-head">
                <div>
                  <span class="scenario-card-label">{{ category?.label ?? '训练场景' }}</span>
                  <h3>{{ scenario.title }}</h3>
                </div>
                <span v-if="isTaskSelected(scenario.id)" class="scenario-selected-badge">
                  已选择
                </span>
              </div>

              <p class="scenario-card-headline">{{ meta.headline }}</p>
              <dl class="scenario-card-facts">
                <div>
                  <dt>训练重点</dt>
                  <dd>{{ meta.focus }}</dd>
                </div>
                <div>
                  <dt>常见阻力</dt>
                  <dd>{{ meta.resistance }}</dd>
                </div>
              </dl>

              <div class="scenario-card-tags">
                <span v-for="tag in meta.tags" :key="tag">{{ tag }}</span>
              </div>

              <div class="scenario-card-meta">
                <span>
                  推荐目标：
                  {{ meta.suggested_target_ids.map(targetLabel).join(' / ') }}
                </span>
                <span>
                  推荐难度：
                  {{ meta.suggested_difficulty_ids.map(difficultyLabel).join(' / ') }}
                </span>
              </div>

              <div class="scenario-complexity" aria-label="复杂度">
                <span
                  v-for="(filled, index) in complexityDots(meta)"
                  :key="index"
                  :class="{ filled }"
                ></span>
              </div>

              <button
                class="scenario-task-cta pop-shadow"
                type="button"
                @click="selectTaskScenario(scenario.id)"
              >
                {{ isTaskSelected(scenario.id) ? '已选择' : '选择任务' }}
              </button>
            </article>
          </TransitionGroup>

          <section v-else class="scenario-empty-state card-border pop-card">
            <span class="material-symbol" aria-hidden="true">manage_search</span>
            <p>当前筛选下暂无训练任务，试试放宽目标或难度。</p>
          </section>
        </section>

        <aside ref="previewPanelRef" class="scenario-preview-panel card-border pop-card pop-shadow">
          <div class="scenario-panel-heading">
            <span class="material-symbol" aria-hidden="true">view_sidebar</span>
            <h2>训练预览</h2>
          </div>

          <dl class="scenario-preview-summary">
            <div v-for="item in trainingSummary" :key="item.label">
              <dt>{{ item.label }}</dt>
              <dd>{{ item.value }}</dd>
            </div>
          </dl>

          <section v-if="selectedScenarioMeta" class="scenario-preview-section">
            <h3>任务重点</h3>
            <p class="scenario-pressure-profile">{{ selectedScenarioMeta.focus }}</p>
            <p class="scenario-pressure-profile">常见阻力：{{ selectedScenarioMeta.resistance }}</p>
          </section>

          <section class="scenario-preview-section">
            <h3>训练目标</h3>
            <div class="scenario-chip-list">
              <button
                v-for="target in trainingTargets"
                :key="target.id"
                type="button"
                class="scenario-filter-chip"
                :class="{ active: selectedTarget?.id === target.id }"
                @click="selectTarget(target.id)"
              >
                {{ target.label }}
              </button>
            </div>
          </section>

          <section class="scenario-preview-section">
            <div class="scenario-section-title-row">
              <h3>难度滑轨</h3>
              <span>{{ replyChainRangeLabel }}</span>
            </div>
            <div class="difficulty-rail card-border" aria-label="训练难度">
              <span class="difficulty-rail-active" :style="difficultyTrackStyle"></span>
              <button
                v-for="difficulty in trainingDifficulties"
                :key="difficulty.id"
                type="button"
                :class="{ active: selectedDifficulty?.id === difficulty.id }"
                @click="selectDifficulty(difficulty.id)"
              >
                {{ difficulty.label }}
              </button>
            </div>
            <p class="scenario-pressure-profile">{{ difficultyPressureProfile }}</p>
          </section>

          <section class="scenario-preview-section">
            <div class="scenario-section-title-row">
              <h3>AI 舍友阵容</h3>
              <span>{{ trainingRoommates.length }} 位</span>
            </div>
            <div class="roommate-preview-list">
              <article
                v-for="roommate in trainingRoommates"
                :key="roommate.id"
                class="roommate-preview card-border"
              >
                <span
                  :class="['roommate-preview-avatar', `roommate-avatar-${roommate.avatar}`]"
                  aria-hidden="true"
                >
                  {{ avatarShortLabel(roommate.avatar) }}
                </span>
                <div>
                  <strong>{{ roommate.name }}</strong>
                  <span>{{ roommate.personality_tag }}</span>
                  <p>{{ roommateBehaviorHint(roommate) }}</p>
                </div>
              </article>
            </div>
          </section>

          <section class="scenario-preview-section">
            <div class="scenario-section-title-row">
              <h3>开场白</h3>
              <button
                v-if="openingSuggestion"
                class="scenario-inline-action"
                type="button"
                @click="useTaskSuggestion"
              >
                套用建议
              </button>
            </div>
            <label class="scenario-opening-field">
              <span>准备说出口的第一句</span>
              <textarea
                v-model="openingMessage"
                rows="5"
                maxlength="280"
                placeholder="写下你准备先说出口的一句话"
                @input="markOpeningTouched"
              ></textarea>
            </label>
            <p v-if="openingSuggestion" class="scenario-opening-suggestion">
              {{ openingSuggestion }}
            </p>
          </section>

          <p class="scenario-preview-safety card-border">
            {{ shouldShowRealitySupport ? analysisSafetyCopy : rehearsalSafetyCopy }}
          </p>

          <button
            class="primary-action scenario-start-action pop-shadow"
            type="button"
            :disabled="!canEnterChat"
            @click="enterChat"
          >
            开始训练
            <span class="material-symbol" aria-hidden="true">arrow_forward</span>
          </button>
        </aside>
      </section>

      <section v-else key="chat" class="scenario-chat-stage">
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
    </Transition>
  </main>
</template>

<style scoped>
.scenario-training-page {
  display: grid;
  gap: 16px;
}

.scenario-hero {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(280px, 0.36fr);
  gap: 20px;
  overflow: hidden;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.92), rgba(255, 242, 204, 0.72)),
    var(--card);
  padding: 28px;
}

.scenario-hero-copy,
.scenario-hero-side,
.scenario-hero-actions,
.scenario-recommendation,
.scenario-filter-panel,
.scenario-task-grid-column,
.scenario-preview-panel {
  min-width: 0;
}

.scenario-hero-kicker,
.scenario-hero-tags,
.scenario-hero-actions,
.scenario-panel-heading,
.scenario-section-title-row,
.scenario-card-tags,
.scenario-card-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.scenario-hero-kicker {
  width: fit-content;
  border: 2px solid var(--ink);
  border-radius: 999px;
  background: var(--tertiary);
  padding: 6px 10px;
  color: var(--ink);
  font-size: 0.78rem;
  font-weight: 1000;
}

.scenario-hero h1,
.scenario-hero p,
.scenario-panel-heading h2,
.scenario-task-grid-header h2,
.scenario-preview-section h3,
.scenario-filter-group h3 {
  margin: 0;
}

.scenario-hero h1 {
  margin-top: 12px;
  font-size: clamp(2.2rem, 6vw, 4.2rem);
  letter-spacing: 0;
  line-height: 0.98;
}

.scenario-hero p {
  margin-top: 12px;
  max-width: 620px;
  color: var(--ink-soft);
  font-weight: 900;
  line-height: 1.55;
}

.scenario-hero-tags {
  margin-top: 18px;
}

.scenario-hero-tags span,
.scenario-card-tags span,
.scenario-selected-badge,
.scenario-card-label {
  border: 2px solid var(--ink);
  border-radius: 999px;
  background: #ffffff;
  padding: 5px 9px;
  color: var(--ink);
  font-size: 0.75rem;
  font-weight: 1000;
  box-shadow: 2px 2px 0 0 var(--shadow-dark);
}

.scenario-hero-side {
  display: grid;
  align-content: space-between;
  gap: 16px;
  position: relative;
  z-index: 1;
}

.scenario-recommendation {
  background: var(--surface-low);
  padding: 14px;
}

.scenario-recommendation strong {
  display: block;
  margin-bottom: 10px;
}

.scenario-recommendation dl,
.scenario-preview-summary,
.scenario-filter-summary,
.scenario-card-facts {
  display: grid;
  gap: 10px;
  margin: 0;
}

.scenario-recommendation div,
.scenario-preview-summary div,
.scenario-filter-summary div,
.scenario-card-facts div {
  display: grid;
  gap: 3px;
}

.scenario-recommendation dt,
.scenario-preview-summary dt,
.scenario-filter-summary dt,
.scenario-card-facts dt {
  color: var(--ink-soft);
  font-size: 0.74rem;
  font-weight: 1000;
}

.scenario-recommendation dd,
.scenario-preview-summary dd,
.scenario-filter-summary dd,
.scenario-card-facts dd {
  min-width: 0;
  margin: 0;
  color: var(--ink);
  font-weight: 900;
  line-height: 1.4;
}

.scenario-hero-dot {
  position: absolute;
  border: 2px solid var(--ink);
  border-radius: 999px;
  box-shadow: 4px 4px 0 0 var(--shadow-dark);
}

.scenario-hero-dot-a {
  right: 24%;
  bottom: 24px;
  width: 34px;
  height: 34px;
  background: var(--secondary);
}

.scenario-hero-dot-b {
  top: 28px;
  right: 22px;
  width: 54px;
  height: 54px;
  background: var(--primary);
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

.scenario-task-station {
  display: grid;
  grid-template-columns: minmax(220px, 0.26fr) minmax(0, 1fr) minmax(320px, 0.36fr);
  gap: 16px;
  align-items: start;
  min-width: 0;
}

.scenario-filter-panel,
.scenario-preview-panel {
  display: grid;
  gap: 18px;
  background: var(--card);
  padding: 18px;
}

.scenario-filter-panel,
.scenario-preview-panel {
  position: sticky;
  top: 24px;
}

.scenario-panel-heading {
  justify-content: flex-start;
}

.scenario-panel-heading .material-symbol {
  display: inline-flex;
  width: 36px;
  height: 36px;
  align-items: center;
  justify-content: center;
  border: 2px solid var(--ink);
  border-radius: 999px;
  background: var(--secondary-soft);
  color: var(--primary);
  box-shadow: 2px 2px 0 0 var(--shadow-dark);
}

.scenario-filter-group {
  display: grid;
  gap: 10px;
  min-width: 0;
}

.scenario-chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  min-width: 0;
}

.scenario-filter-chip {
  border: 2px solid var(--ink);
  border-radius: 999px;
  background: var(--surface-low);
  padding: 8px 11px;
  color: var(--ink-soft);
  font-size: 0.82rem;
  font-weight: 1000;
  transition:
    transform 160ms ease,
    background-color 160ms ease,
    box-shadow 160ms ease;
}

.scenario-filter-chip:hover {
  transform: translateY(-1px);
  box-shadow: 2px 2px 0 0 var(--shadow-dark);
}

.scenario-filter-chip.active {
  background: var(--primary);
  color: #ffffff;
  box-shadow: 3px 3px 0 0 var(--shadow-dark);
}

.scenario-filter-summary {
  border-top: 2px dashed var(--border);
  padding-top: 12px;
}

.scenario-task-grid-column {
  display: grid;
  gap: 14px;
}

.scenario-task-grid-header {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 12px;
  min-width: 0;
}

.scenario-task-grid-header > span {
  border: 2px solid var(--ink);
  border-radius: 999px;
  background: var(--surface-low);
  padding: 7px 11px;
  font-weight: 1000;
  white-space: nowrap;
}

.scenario-task-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  min-width: 0;
}

.scenario-task-card {
  display: grid;
  gap: 12px;
  background: var(--card);
  padding: 16px;
  transition:
    transform 180ms ease,
    box-shadow 180ms ease,
    border-color 180ms ease,
    background-color 180ms ease;
}

.scenario-task-card:hover {
  transform: translate(-2px, -3px);
  box-shadow: 6px 6px 0 0 var(--shadow-dark);
}

.scenario-task-card.selected {
  background: var(--primary-soft);
  box-shadow: 7px 7px 0 0 var(--shadow-dark);
}

.scenario-task-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  min-width: 0;
}

.scenario-task-card h3 {
  margin: 8px 0 0;
  color: var(--ink);
  font-size: 1.15rem;
  line-height: 1.22;
}

.scenario-card-headline {
  margin: 0;
  color: var(--primary);
  font-weight: 1000;
}

.scenario-card-tags span {
  box-shadow: none;
}

.scenario-card-meta {
  align-items: flex-start;
  color: var(--ink-soft);
  font-size: 0.82rem;
  font-weight: 900;
  line-height: 1.45;
}

.scenario-complexity {
  display: flex;
  gap: 6px;
  align-items: center;
}

.scenario-complexity span {
  width: 12px;
  height: 12px;
  border: 2px solid var(--ink);
  border-radius: 999px;
  background: #ffffff;
}

.scenario-complexity span.filled {
  background: var(--primary);
}

.scenario-task-cta,
.scenario-inline-action {
  border: 2px solid var(--ink);
  border-radius: 999px;
  background: #ffffff;
  color: var(--ink);
  padding: 9px 12px;
  font-weight: 1000;
}

.scenario-task-cta {
  justify-self: start;
}

.scenario-empty-state {
  display: grid;
  justify-items: center;
  gap: 10px;
  background: var(--surface-low);
  padding: 28px;
  text-align: center;
}

.scenario-empty-state .material-symbol {
  font-size: 2rem;
  color: var(--primary);
}

.scenario-empty-state p {
  margin: 0;
  color: var(--ink-soft);
  font-weight: 900;
}

.scenario-preview-panel {
  max-height: calc(100vh - 48px);
  overflow: auto;
}

.scenario-preview-section {
  display: grid;
  gap: 10px;
  min-width: 0;
  border-top: 2px dashed var(--border);
  padding-top: 14px;
}

.scenario-section-title-row {
  justify-content: space-between;
}

.scenario-section-title-row > span {
  color: var(--primary);
  font-size: 0.82rem;
  font-weight: 1000;
}

.difficulty-rail {
  position: relative;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  overflow: hidden;
  background: var(--surface-low);
  padding: 4px;
}

.difficulty-rail-active {
  position: absolute;
  top: 4px;
  bottom: 4px;
  left: 4px;
  z-index: 0;
  border: 2px solid var(--ink);
  border-radius: 999px;
  background: var(--primary);
  transition: transform 220ms ease;
}

.difficulty-rail button {
  position: relative;
  z-index: 1;
  min-width: 0;
  border: 0;
  border-radius: 999px;
  background: transparent;
  padding: 9px 6px;
  color: var(--ink-soft);
  font-weight: 1000;
}

.difficulty-rail button.active {
  color: #ffffff;
}

.scenario-pressure-profile,
.scenario-opening-suggestion,
.scenario-preview-safety {
  margin: 0;
  color: var(--ink-soft);
  font-weight: 850;
  line-height: 1.55;
}

.roommate-preview-list {
  display: grid;
  gap: 10px;
}

.roommate-preview {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 10px;
  align-items: start;
  background: var(--surface-low);
  padding: 10px;
}

.roommate-preview-avatar {
  display: inline-flex;
  width: 38px;
  height: 38px;
  align-items: center;
  justify-content: center;
  border: 2px solid var(--ink);
  border-radius: 999px;
  box-shadow: 2px 2px 0 0 var(--shadow-dark);
  color: var(--ink);
  font-weight: 1000;
}

.roommate-preview strong,
.roommate-preview span,
.roommate-preview p {
  display: block;
}

.roommate-preview span {
  margin-top: 2px;
  color: var(--primary);
  font-size: 0.82rem;
  font-weight: 1000;
}

.roommate-preview p {
  margin: 5px 0 0;
  color: var(--ink-soft);
  font-size: 0.84rem;
  font-weight: 800;
  line-height: 1.45;
}

.scenario-preview-safety {
  background: var(--secondary-soft);
  padding: 10px 12px;
}

.scenario-start-action {
  width: 100%;
  justify-content: center;
}

.scenario-card-list-enter-active,
.scenario-card-list-leave-active {
  transition:
    opacity 200ms ease,
    transform 200ms ease;
}

.scenario-card-list-enter-from,
.scenario-card-list-leave-to {
  opacity: 0;
  transform: translateY(10px) scale(0.985);
}

.scenario-training-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(260px, 0.34fr);
  gap: 16px;
  align-items: start;
  min-width: 0;
}

.scenario-step-card,
.scenario-summary-panel {
  display: grid;
  gap: 16px;
  background: var(--card);
  padding: 22px;
  min-width: 0;
}

.scenario-step-slide-enter-active,
.scenario-step-slide-leave-active {
  transition:
    opacity 220ms ease,
    transform 220ms ease;
  transform-origin: top center;
}

.scenario-step-slide-enter-from {
  opacity: 0;
  transform: translateY(12px) scale(0.985);
}

.scenario-step-slide-leave-to {
  opacity: 0;
  transform: translateY(-8px) scale(0.99);
}

.scenario-stage-fade-enter-active,
.scenario-stage-fade-leave-active {
  transition:
    opacity 240ms ease,
    transform 240ms ease;
  transform-origin: top center;
}

.scenario-stage-fade-enter-from,
.scenario-stage-fade-leave-to {
  opacity: 0;
  transform: translateY(10px) scale(0.99);
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
  min-width: 0;
}

.scenario-chat-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
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
  .scenario-hero,
  .scenario-task-station {
    grid-template-columns: 1fr;
  }

  .scenario-filter-panel,
  .scenario-preview-panel {
    position: static;
    max-height: none;
  }

  .scenario-stepper,
  .scenario-chat-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .scenario-training-workspace {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 560px) {
  .scenario-hero,
  .scenario-filter-panel,
  .scenario-preview-panel,
  .scenario-task-card {
    padding: 16px;
  }

  .scenario-stepper,
  .scenario-option-grid,
  .scenario-task-grid,
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
  .scenario-hero-actions,
  .scenario-step-actions,
  .scenario-hero-actions a,
  .scenario-hero-actions button,
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
