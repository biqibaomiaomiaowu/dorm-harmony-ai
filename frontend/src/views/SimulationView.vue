<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { fetchEventArchive } from '@/data/eventArchive'
import {
  ANALYSIS_RESULT_STORAGE_KEY,
  LAST_EVENT_STORAGE_KEY,
  ROOMMATE_PROFILES_STORAGE_KEY,
  SIMULATION_RESULT_STORAGE_KEY,
  buildDemoSimulationResponse,
  createDefaultRoommates,
  defaultSimulationRequest,
  isAnalyzeResult,
  mapRoommateToReviewSpeaker,
  normalizeRoommates,
  roommateAvatarOptions,
  roommatePresetLabels,
  roommatePresetOptions,
  roommatePresetTraits,
  roommateTraitLabels,
  SimulationRequestError,
  simulationScenarios,
  submitSimulationRequest,
  type AnalyzeResult,
  type ReviewDialogueLine,
  type RoommateAvatarKey,
  type RoommatePresetKey,
  type RoommateProfile,
  type RoommateTraits,
  type SimulationReply,
  type SimulationRequest,
  type SimulationResponse,
  type StoredSimulationResult,
} from '@/data/week1'

type RecordLike = Record<string, unknown>
type RoommateDraftMode = RoommatePresetKey | 'custom'

interface RoommateDraft {
  id: string
  name: string
  mode: RoommateDraftMode
  customTag: string
  avatar: RoommateAvatarKey
  traits: RoommateTraits
}

const customScenariosStorageKey = 'dorm-harmony:custom-scenarios:v1'
const defaultScene = defaultSimulationRequest.scenario
const defaultSpeechPlaceholder = `例：${defaultSimulationRequest.user_message}`
const designPreview = buildDemoSimulationResponse('设计稿首屏示例')
const traitKeys: Array<keyof RoommateTraits> = [
  'directness',
  'emotional_reactivity',
  'avoidance',
  'empathy',
  'solution_willingness',
  'boundary_sensitivity',
]

const currentScene = ref(defaultScene)
const customScenarios = ref<string[]>([])
const customSceneDraft = ref('')
const customSceneError = ref('')
const isCustomSceneOpen = ref(false)
const userMessage = ref('')
const isSubmitting = ref(false)
const submitError = ref('')
const isDemoResult = ref(false)
const simulationNotice = ref('')
const safetyNote = ref('')
const conversationMessages = ref<ReviewDialogueLine[]>([])
const cachedConversationRoommates = ref<RoommateProfile[]>([])
const generationStatus = ref('')
const generationRunId = ref(0)
const isContinuationRequestActive = ref(false)
const activeSimulationAbortController = ref<AbortController | null>(null)
const queuedUserMessages = ref<string[]>([])
const savedAnalysisRiskLevel = ref<AnalyzeResult['risk_level'] | undefined>()
const savedAnalysisSources = ref<string[]>([])
const savedAnalysisEmotionKeywords = ref<string[]>([])
const savedAnalysisTrend = ref('')
const savedAnalysisSuggestion = ref('')
const savedAnalysisScore = ref<number | null>(null)
const savedAnalysisContext = ref('')
const storedSimulationMeta = ref('')
const hasUserTurn = ref(false)
const hasCompleteSimulationTurn = ref(false)
const conversationId = ref('')
const currentTurnId = ref('')
const systemTurnNotice = ref('')

const roommates = ref<RoommateProfile[]>(createDefaultRoommates())
const editingIndex = ref<number | null>(null)
const roommateDraft = ref<RoommateDraft | null>(null)
const showRoommateLockedModal = ref(false)
const roommateLockedModalRef = ref<HTMLElement | null>(null)
const roommateLockedConfirmRef = ref<HTMLButtonElement | null>(null)

const focusableSelector = [
  `button:not([disabled]):not([aria-disabled="true"])`,
  'a[href]',
  'textarea:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

function getModalFocusableElements(modalRef: HTMLElement | null) {
  return Array.from(modalRef?.querySelectorAll<HTMLElement>(focusableSelector) ?? []).filter(
    (element) => !element.hasAttribute('disabled') && element.tabIndex !== -1,
  )
}

const archiveEventCount = ref(0)
const archiveLoadError = ref('')
const useEventArchive = ref(false)
const defaultReplyChainMin = 3
const defaultReplyChainMax = 7
const maxReplyChainLength = 15
const interjectionWindowMs = 900
const hasActiveConversation = computed(() =>
  Boolean(conversationId.value || conversationMessages.value.length > 0 || isSubmitting.value),
)
const scenarioButtons = computed(() => [...simulationScenarios, ...customScenarios.value])

function isRecord(value: unknown): value is RecordLike {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
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

function isStoredSimulationResult(value: unknown): value is StoredSimulationResult {
  if (!isRecord(value)) {
    return false
  }

  const request = value.request
  const response = value.response
  const dialogue = value.dialogue

  return (
    isRecord(request) &&
    typeof request.scenario === 'string' &&
    (typeof request.user_message === 'undefined' || typeof request.user_message === 'string') &&
    isRecord(response) &&
    Array.isArray(response.replies) &&
    typeof response.safety_note === 'string' &&
    (typeof dialogue === 'undefined' ||
      (Array.isArray(dialogue) && dialogue.every(isReviewDialogueLine)))
  )
}

function cloneRoommate(roommate: RoommateProfile): RoommateProfile {
  return {
    ...roommate,
    traits: { ...roommate.traits },
  }
}

function saveCustomScenarios() {
  try {
    localStorage.setItem(customScenariosStorageKey, JSON.stringify(customScenarios.value))
  } catch {
    // ignore restricted storage
  }
}

function loadCustomScenarios() {
  try {
    const raw = localStorage.getItem(customScenariosStorageKey)
    const parsed = raw ? (JSON.parse(raw) as unknown) : []
    const defaultScenarioSet = new Set(simulationScenarios)
    customScenarios.value = Array.isArray(parsed)
      ? parsed
          .filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
          .map((item) => item.trim())
          .filter((item) => !defaultScenarioSet.has(item))
          .filter((item, index, source) => source.indexOf(item) === index)
          .slice(0, 8)
      : []
    saveCustomScenarios()
  } catch {
    customScenarios.value = []
  }
}

function saveRoommates() {
  try {
    localStorage.setItem(ROOMMATE_PROFILES_STORAGE_KEY, JSON.stringify(roommates.value))
  } catch {
    // ignore restricted storage
  }
}

function loadRoommates() {
  try {
    const raw = localStorage.getItem(ROOMMATE_PROFILES_STORAGE_KEY)
    roommates.value = normalizeRoommates(raw ? JSON.parse(raw) : undefined)
  } catch {
    roommates.value = createDefaultRoommates()
  }
}

function nextRoommateId() {
  const ids = new Set(roommates.value.map((roommate) => roommate.id))
  let index = roommates.value.length + 1
  let candidate = `roommate_custom_${index}`

  while (ids.has(candidate)) {
    index += 1
    candidate = `roommate_custom_${index}`
  }

  return candidate
}

function usedAvatarKeys(excludedIndex: number | null = null) {
  return new Set(
    roommates.value
      .filter((_, index) => index !== excludedIndex)
      .map((roommate) => roommate.avatar),
  )
}

function nextAvailableAvatar(excludedIndex: number | null = null) {
  const used = usedAvatarKeys(excludedIndex)
  return roommateAvatarOptions.find((option) => !used.has(option.key))?.key ?? 'nailong'
}

function createDraft(roommate?: RoommateProfile): RoommateDraft {
  const presetKey = roommate?.tag_mode === 'preset' ? roommate.preset_key ?? 'direct' : 'direct'
  const isCustom = roommate?.tag_mode === 'custom'
  const excludedIndex =
    roommate === undefined ? null : roommates.value.findIndex((item) => item.id === roommate.id)

  return {
    id: roommate?.id ?? nextRoommateId(),
    name: roommate?.name ?? `舍友 ${roommates.value.length + 1}`,
    mode: isCustom ? 'custom' : presetKey,
    customTag: isCustom ? roommate.personality_tag : '自定义',
    avatar: roommate?.avatar ?? nextAvailableAvatar(excludedIndex),
    traits: {
      ...(isCustom && roommate ? roommate.traits : roommatePresetTraits[presetKey]),
    },
  }
}

function openAddRoommate() {
  if (roommates.value.length >= 5 && !hasActiveConversation.value) {
    return
  }

  if (hasActiveConversation.value) {
    openRoommateLockedModal()
    return
  }

  editingIndex.value = null
  roommateDraft.value = createDraft()
}

function openEditRoommate(index: number) {
  if (hasActiveConversation.value) {
    openRoommateLockedModal()
    return
  }

  editingIndex.value = index
  roommateDraft.value = createDraft(roommates.value[index])
}

function closeRoommateEditor() {
  editingIndex.value = null
  roommateDraft.value = null
}

function setDraftMode(mode: RoommateDraftMode) {
  if (!roommateDraft.value) {
    return
  }

  roommateDraft.value.mode = mode
  if (mode !== 'custom') {
    roommateDraft.value.traits = { ...roommatePresetTraits[mode] }
  }
}

function saveDraft() {
  const draft = roommateDraft.value
  if (!draft) {
    return
  }

  const name = draft.name.trim() || '未命名舍友'
  const profile: RoommateProfile =
    draft.mode === 'custom'
      ? {
          id: draft.id,
          name,
          personality_tag: draft.customTag.trim() || '自定义',
          tag_mode: 'custom',
          avatar: draft.avatar,
          traits: { ...draft.traits },
        }
      : {
          id: draft.id,
          name,
          personality_tag: roommatePresetLabels[draft.mode],
          tag_mode: 'preset',
          preset_key: draft.mode,
          avatar: draft.avatar,
          traits: { ...roommatePresetTraits[draft.mode] },
        }

  if (editingIndex.value === null) {
    roommates.value = [...roommates.value, profile].slice(0, 5)
  } else {
    roommates.value = roommates.value.map((roommate, index) =>
      index === editingIndex.value ? profile : roommate,
    )
  }

  saveRoommates()
  closeRoommateEditor()
}

function openRoommateLockedModal() {
  showRoommateLockedModal.value = true
  nextTick(() => {
    roommateLockedConfirmRef.value?.focus()
  })
}

function closeRoommateLockedModal() {
  showRoommateLockedModal.value = false
}

function handleRoommateLockedKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    event.preventDefault()
    closeRoommateLockedModal()
    return
  }

  if (event.key !== 'Tab') {
    return
  }

  const focusableElements = getModalFocusableElements(roommateLockedModalRef.value)

  if (focusableElements.length === 0) {
    event.preventDefault()
    roommateLockedModalRef.value?.focus()
    return
  }

  const firstElement = focusableElements[0]!
  const lastElement = focusableElements[focusableElements.length - 1]!

  if (event.shiftKey && document.activeElement === firstElement) {
    event.preventDefault()
    lastElement.focus()
    return
  }

  if (!event.shiftKey && document.activeElement === lastElement) {
    event.preventDefault()
    firstElement.focus()
  }
}

function deleteDraftRoommate() {
  if (editingIndex.value === null || roommates.value.length <= 1) {
    return
  }

  roommates.value = roommates.value.filter((_, index) => index !== editingIndex.value)
  saveRoommates()
  closeRoommateEditor()
}

function traitFillStyle(value: number) {
  return { '--trait-fill': `${Math.max(0, Math.min(5, value)) * 20}%` }
}

const availableAvatarOptions = computed(() => {
  const excludedIndex = editingIndex.value
  const used = usedAvatarKeys(excludedIndex)
  return roommateAvatarOptions.filter(
    (option) => option.key === roommateDraft.value?.avatar || !used.has(option.key),
  )
})

function avatarShortLabel(key: RoommateAvatarKey) {
  return roommateAvatarOptions.find((option) => option.key === key)?.shortLabel ?? key.slice(0, 1)
}

function selectDraftAvatar(key: RoommateAvatarKey) {
  if (roommateDraft.value) {
    roommateDraft.value.avatar = key
  }
}

function toggleCustomSceneEditor() {
  isCustomSceneOpen.value = !isCustomSceneOpen.value
  customSceneError.value = ''
  if (isCustomSceneOpen.value) {
    customSceneDraft.value = ''
  }
}

function saveCustomScene() {
  const scene = customSceneDraft.value.trim()
  if (!scene) {
    customSceneError.value = '请输入自定义演练场景'
    return
  }
  if (scene.length > 40) {
    customSceneError.value = '场景最多 40 个字'
    return
  }
  if (scenarioButtons.value.includes(scene)) {
    customSceneError.value = '这个场景已经存在'
    currentScene.value = scene
    return
  }

  customScenarios.value = [...customScenarios.value, scene].slice(-8)
  saveCustomScenarios()
  currentScene.value = scene
  customSceneDraft.value = ''
  customSceneError.value = ''
  isCustomSceneOpen.value = false
}

function buildRequestContext() {
  const parts = [`当前场景：${currentScene.value}`]
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

  return parts.join('；')
}

function setDefaultSimulationState() {
  currentScene.value = defaultScene
  userMessage.value = ''
  conversationMessages.value = []
  cachedConversationRoommates.value = []
  generationStatus.value = ''
  submitError.value = ''
  isDemoResult.value = false
  simulationNotice.value = ''
  safetyNote.value = ''
  storedSimulationMeta.value = ''
  hasUserTurn.value = false
  hasCompleteSimulationTurn.value = false
  conversationId.value = ''
  currentTurnId.value = ''
  systemTurnNotice.value = ''
  queuedUserMessages.value = []
}

const currentScenePrompt = computed(() => {
  return `当前场景：${currentScene.value}。请先输入一句你准备现实沟通时使用的话。`
})
const hasUserMessage = computed(() => userMessage.value.trim().length > 0)
const canAddRoommate = computed(() => roommates.value.length < 5 && !hasActiveConversation.value)
const canEditRoommates = computed(() => !hasActiveConversation.value)
const canDeleteDraft = computed(() => editingIndex.value !== null && roommates.value.length > 1)
const archiveSwitchLabel = computed(() => {
  if (archiveEventCount.value === 0) {
    return '请先记录事件档案'
  }

  return useEventArchive.value ? '已接入事件档案' : '接入事件档案'
})
const canEnterReview = computed(() =>
  Boolean(
    conversationId.value &&
      hasUserTurn.value &&
      hasCompleteSimulationTurn.value &&
      !isDemoResult.value &&
      !isSubmitting.value &&
      queuedUserMessages.value.length === 0,
  ),
)
const reviewGateMessage = computed(() => {
  if (canEnterReview.value) {
    return '已有本轮模拟记录，可生成复盘报告。'
  }
  if (queuedUserMessages.value.length > 0) {
    return `还有 ${queuedUserMessages.value.length} 条待发送表达，请等待当前回复完成。`
  }
  if (isSubmitting.value) {
    return 'AI 仍在逐条回应，请稍候再生成复盘。'
  }

  return '请先完成一次模拟对话，再进入复盘。'
})
const chatHintMessage = computed(() => {
  if (queuedUserMessages.value.length > 0) {
    return `已排队 ${queuedUserMessages.value.length} 条表达，当前 AI 回复完成后会继续发送。`
  }
  if (isSubmitting.value) {
    return generationStatus.value || 'AI 正在逐条生成舍友回复。'
  }
  if (isDemoResult.value && simulationNotice.value) {
    return `${storedSimulationMeta.value || '演示数据'}：${simulationNotice.value}`
  }
  if (simulationNotice.value) {
    return simulationNotice.value
  }
  if (!storedSimulationMeta.value) {
    return '演示建议：先从“我感受到了……”开始表达，并给出可执行边界。'
  }

  return '可以继续输入你的下一句，AI 会基于当前对话继续回应。'
})

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
      savedAnalysisContext.value = `${savedAnalysisContext.value}${savedAnalysisContext.value ? '；' : ''}事件描述：${description}`
    }
  } catch {
    // ignore malformed local cache
  }
}

async function loadArchiveState() {
  try {
    const archive = await fetchEventArchive()
    archiveEventCount.value = archive.events.length
    archiveLoadError.value = ''
    if (archive.events.length === 0) {
      useEventArchive.value = false
    }
  } catch {
    archiveEventCount.value = 0
    useEventArchive.value = false
    archiveLoadError.value = '事件档案状态暂时不可用'
  }
}

function hydrateFromSimulationCache() {
  try {
    const raw = localStorage.getItem(SIMULATION_RESULT_STORAGE_KEY)

    if (!raw) {
      return
    }

    const parsed = JSON.parse(raw) as unknown

    if (!isStoredSimulationResult(parsed)) {
      return
    }

    if (parsed.response.is_demo) {
      localStorage.removeItem(SIMULATION_RESULT_STORAGE_KEY)
      return
    }

    const cachedScene = parsed.request.scenario || defaultScene
    currentScene.value = scenarioButtons.value.includes(cachedScene) ? cachedScene : defaultScene
    userMessage.value = parsed.request.user_message || ''
    conversationMessages.value = parsed.dialogue ? [...parsed.dialogue] : []
    cachedConversationRoommates.value = Array.isArray(parsed.request.roommates)
      ? normalizeRoommates(parsed.request.roommates)
      : []
    isDemoResult.value = parsed.response.is_demo
    simulationNotice.value = parsed.response.is_demo
      ? parsed.response.demo_notice
      : parsed.response.archive_context_used && parsed.response.archive_context_summary
        ? `已参考事件档案：${parsed.response.archive_context_summary}`
        : ''
    safetyNote.value = parsed.response.is_demo ? parsed.response.safety_note : ''
    storedSimulationMeta.value = parsed.response.is_demo ? '演示数据' : '已返回'
    conversationId.value = parsed.response.conversation_id || parsed.request.conversation_id || ''
    currentTurnId.value = parsed.request.turn_id || ''
    hasUserTurn.value = conversationMessages.value.some((line) => line.speaker === 'user')
    hasCompleteSimulationTurn.value = Boolean(conversationId.value && hasUserTurn.value)
    systemTurnNotice.value =
      parsed.response.replies.length === 0 && hasUserTurn.value
        ? '这轮舍友暂时没有回应，可以继续补充你的表达。'
        : ''
  } catch {
    // ignore malformed simulation cache
  }
}

onMounted(() => {
  loadRoommates()
  loadCustomScenarios()
  loadAnalysisContext()
  loadLastEventHint()
  hydrateFromSimulationCache()
  void loadArchiveState()
})

function speakerLabel(speaker: ReviewDialogueLine['speaker']) {
  if (speaker === 'user') {
    return '你'
  }
  if (speaker === 'system') {
    return '系统'
  }

  const roommate =
    cachedConversationRoommates.value.find((item) => item.id === speaker) ??
    roommates.value.find((item) => item.id === speaker)
  return roommate?.name ?? speaker.replace('roommate_', '舍友 ')
}

function roommateForSpeaker(speaker: ReviewDialogueLine['speaker']) {
  return speaker.startsWith('roommate_')
    ? (cachedConversationRoommates.value.find((item) => item.id === speaker) ??
        roommates.value.find((item) => item.id === speaker))
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

function resetGeneratingState() {
  generationStatus.value = ''
}

function createReplyChainTarget() {
  const span = defaultReplyChainMax - defaultReplyChainMin + 1
  return defaultReplyChainMin + Math.floor(Math.random() * span)
}

function appendUserMessage(message: string) {
  conversationMessages.value = [
    ...conversationMessages.value,
    {
      speaker: 'user',
      message,
    },
  ]
  hasUserTurn.value = true
}

function createTurnId() {
  return `turn-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

async function appendReplyWithDelay(reply: SimulationReply, index: number, runId: number) {
  generationStatus.value = `正在生成${reply.roommate.replace(/\s+/g, ' ')} 的回复`

  await new Promise((resolve) => window.setTimeout(resolve, 520 * index))

  if (runId !== generationRunId.value) {
    return
  }

  conversationMessages.value = [
    ...conversationMessages.value,
    {
      speaker: mapRoommateToReviewSpeaker(reply.roommate, reply.roommate_id),
      message: reply.message,
    },
  ]
}

function buildSingleReplyContext(isContinuation: boolean, replyCount: number) {
  const baseContext = buildRequestContext()
  const replyLimitHint =
    '本次只生成 1 条虚拟舍友回复；不要一次性输出完整一轮，前端会在需要时继续请求下一条。'
  const continuationHint = isContinuation
    ? `这是同一 conversation_id 的 continuation 请求，请基于已有短期记忆判断下一位需要回应的舍友；当前已连续返回 ${replyCount} 条。`
    : '这是用户刚发送的新表达，请重新规划下一位需要回应的舍友。'

  return `${baseContext}；${replyLimitHint}；${continuationHint}`
}

function selectScenario(scene: string) {
  currentScene.value = scene
}

function isCustomScenario(scene: string) {
  return customScenarios.value.includes(scene)
}

function deleteCustomScenario(scene: string) {
  const wasCurrentScene = currentScene.value === scene
  customScenarios.value = customScenarios.value.filter((item) => item !== scene)
  saveCustomScenarios()
  if (customSceneDraft.value.trim() === scene) {
    customSceneDraft.value = ''
  }
  customSceneError.value = ''

  try {
    const raw = localStorage.getItem(SIMULATION_RESULT_STORAGE_KEY)
    const parsed = raw ? (JSON.parse(raw) as unknown) : null
    if (isStoredSimulationResult(parsed) && parsed.request.scenario === scene) {
      localStorage.removeItem(SIMULATION_RESULT_STORAGE_KEY)
    }
  } catch {
    // ignore malformed local cache
  }

  if (wasCurrentScene) {
    resetConversation()
  }
}

function applyResultMeta(response: SimulationResponse) {
  isDemoResult.value = response.is_demo
  simulationNotice.value = response.is_demo
    ? response.demo_notice
    : response.archive_context_used && response.archive_context_summary
      ? `已参考事件档案：${response.archive_context_summary}`
      : ''
  safetyNote.value = response.is_demo ? response.safety_note : ''
  storedSimulationMeta.value = response.is_demo ? '演示数据' : '已返回'
  conversationId.value = response.conversation_id
  hasCompleteSimulationTurn.value = true
  systemTurnNotice.value =
    response.replies.length === 0 ? '这轮舍友暂时没有回应，可以继续补充你的表达。' : ''
}

function buildSimulationRequest(message: string, isContinuation: boolean, replyCount: number) {
  const request: SimulationRequest = {
    conversation_id: conversationId.value || undefined,
    turn_id: currentTurnId.value || undefined,
    scenario: currentScene.value,
    risk_level: savedAnalysisRiskLevel.value,
    context: buildSingleReplyContext(isContinuation, replyCount),
    roommates: roommates.value.map(cloneRoommate),
    use_event_archive: useEventArchive.value && archiveEventCount.value > 0,
    max_replies: 1,
    is_continuation: isContinuation,
  }

  if (!isContinuation) {
    request.user_message = message
  }

  return request
}

function persistSimulationState(request: SimulationRequest, response: SimulationResponse) {
  try {
    localStorage.setItem(
      SIMULATION_RESULT_STORAGE_KEY,
      JSON.stringify({
        request: {
          ...request,
          conversation_id: response.conversation_id,
        },
        response,
        dialogue: conversationMessages.value,
      }),
    )
  } catch {
    // ignore write failures
  }
}

async function requestSingleAiReply(
  message: string,
  isContinuation: boolean,
  replyCount: number,
  runId: number,
) {
  const request = buildSimulationRequest(message, isContinuation, replyCount)
  generationStatus.value = isContinuation ? '正在判断下一条回应' : '正在规划舍友回应'
  const controller = new AbortController()
  activeSimulationAbortController.value = controller
  isContinuationRequestActive.value = isContinuation

  let response: SimulationResponse
  try {
    response = await submitSimulationRequest(request, controller.signal)
  } catch (error) {
    if (
      error instanceof SimulationRequestError &&
      !isContinuation &&
      Boolean(request.conversation_id) &&
      error.message.includes('未找到对应的模拟对话')
    ) {
      conversationId.value = ''
      currentTurnId.value = createTurnId()
      const retryRequest = buildSimulationRequest(message, false, 0)
      response = await submitSimulationRequest(retryRequest, controller.signal)
      request.conversation_id = retryRequest.conversation_id
      request.turn_id = retryRequest.turn_id
    } else {
      throw error
    }
  } finally {
    if (activeSimulationAbortController.value === controller) {
      activeSimulationAbortController.value = null
      isContinuationRequestActive.value = false
    }
  }

  if (runId !== generationRunId.value) {
    return null
  }

  const reply = response.replies[0]
  const oneReplyResponse: SimulationResponse = {
    ...response,
    replies: reply ? [reply] : [],
  }

  if (reply) {
    await appendReplyWithDelay(reply, 0, runId)
  }

  applyResultMeta(oneReplyResponse)
  persistSimulationState(request, oneReplyResponse)
  return oneReplyResponse
}

async function waitForInterjectionWindow(runId: number) {
  generationStatus.value = '可以插入你的下一句，稍后继续判断舍友回应'
  await new Promise((resolve) => window.setTimeout(resolve, interjectionWindowMs))
  return runId === generationRunId.value
}

async function runAiReplyLoop(firstMessage: string) {
  const runId = generationRunId.value + 1
  generationRunId.value = runId
  currentTurnId.value = createTurnId()
  isSubmitting.value = true
  hasCompleteSimulationTurn.value = false
  let nextMessage = firstMessage
  let isContinuation = false
  let replyCount = 0
  let targetReplyCount = createReplyChainTarget()

  try {
    while (runId === generationRunId.value && replyCount < maxReplyChainLength) {
      const response = await requestSingleAiReply(nextMessage, isContinuation, replyCount, runId)
      if (!response) {
        return
      }

      const hasReply = response.replies.length > 0
      if (hasReply) {
        replyCount += response.replies.length
      }

      let queuedMessage = queuedUserMessages.value.shift()
      if (queuedMessage) {
        appendUserMessage(queuedMessage)
        hasCompleteSimulationTurn.value = false
        systemTurnNotice.value =
          queuedUserMessages.value.length > 0
            ? `还有 ${queuedUserMessages.value.length} 条表达在队列中。`
            : ''
        currentTurnId.value = createTurnId()
        nextMessage = queuedMessage
        isContinuation = false
        replyCount = 0
        targetReplyCount = createReplyChainTarget()
        continue
      }

      if (response.is_demo) {
        return
      }

      if (!hasReply) {
        systemTurnNotice.value = '这轮舍友暂时没有回应，可以继续补充你的表达。'
        return
      }

      if (replyCount >= targetReplyCount) {
        systemTurnNotice.value = ''
        return
      }

      if (!(await waitForInterjectionWindow(runId))) {
        return
      }

      queuedMessage = queuedUserMessages.value.shift()
      if (queuedMessage) {
        appendUserMessage(queuedMessage)
        hasCompleteSimulationTurn.value = false
        systemTurnNotice.value =
          queuedUserMessages.value.length > 0
            ? `还有 ${queuedUserMessages.value.length} 条表达在队列中。`
            : ''
        currentTurnId.value = createTurnId()
        nextMessage = queuedMessage
        isContinuation = false
        replyCount = 0
        targetReplyCount = createReplyChainTarget()
        continue
      }

      nextMessage = ''
      isContinuation = true
    }
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError' && runId !== generationRunId.value) {
      return
    }

    submitError.value =
      error instanceof Error && error.message
        ? error.message
        : '实时回复中断，为避免重复提交，请直接继续输入或重置后重试。'
  } finally {
    if (runId === generationRunId.value) {
      resetGeneratingState()
      isSubmitting.value = false
    }
  }
}

async function sendMessage() {
  const message = userMessage.value.trim()

  if (!message) {
    submitError.value = '请输入你的回复后再发送'
    return
  }

  submitError.value = ''
  userMessage.value = ''

  if (isSubmitting.value) {
    if (isContinuationRequestActive.value) {
      activeSimulationAbortController.value?.abort()
      generationRunId.value += 1
      isContinuationRequestActive.value = false
      activeSimulationAbortController.value = null
      appendUserMessage(message)
      systemTurnNotice.value = ''
      void runAiReplyLoop(message)
      return
    }

    queuedUserMessages.value = [...queuedUserMessages.value, message]
    systemTurnNotice.value = `已加入待发送队列（${queuedUserMessages.value.length} 条）。`
    return
  }

  systemTurnNotice.value = ''
  appendUserMessage(message)
  void runAiReplyLoop(message)
}

function resetConversation() {
  generationRunId.value += 1
  isSubmitting.value = false
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
      <div class="simulation-section-heading simulation-section-heading-actions">
        <span>
          <span class="material-symbol" aria-hidden="true">rule</span>
          <h2>选择演练场景</h2>
        </span>
        <button class="roommate-add-btn pop-shadow" type="button" @click="toggleCustomSceneEditor">
          <span class="material-symbol" aria-hidden="true">
            {{ isCustomSceneOpen ? 'close' : 'add' }}
          </span>
          自定义
        </button>
      </div>
      <Transition name="custom-scene">
        <form
          v-if="isCustomSceneOpen"
          class="custom-scene-panel card-border"
          @submit.prevent="saveCustomScene"
        >
          <input
            v-model="customSceneDraft"
            maxlength="40"
            type="text"
            placeholder="例：舍友总在早八前开外放"
            aria-label="自定义演练场景"
          />
          <button class="primary-action pop-shadow" type="submit">保存</button>
          <p v-if="customSceneError" class="custom-scene-error">{{ customSceneError }}</p>
        </form>
      </Transition>
      <p class="simulation-subtitle chip-text">场景选择</p>
      <TransitionGroup name="scene-list" tag="div" class="simulation-scenes">
        <div
          v-for="scene in scenarioButtons"
          :key="scene"
          class="scene-item"
          :class="{ 'scene-item-custom': isCustomScenario(scene) }"
        >
          <button
            class="scene-btn pop-shadow"
            :class="{ active: scene === currentScene }"
            type="button"
            :aria-pressed="scene === currentScene"
            @click="selectScenario(scene)"
          >
            {{ scene }}
          </button>
          <button
            v-if="isCustomScenario(scene)"
            class="scene-delete-btn"
            type="button"
            :aria-label="`删除自定义场景：${scene}`"
            @click.stop="deleteCustomScenario(scene)"
          >
            <span class="material-symbol" aria-hidden="true">close</span>
          </button>
        </div>
      </TransitionGroup>
    </section>

    <section class="simulation-layout page-pop-in">
      <aside class="simulation-left-column">
        <div class="panel-title panel-title-actions">
          <span>
            <span class="material-symbol" aria-hidden="true">groups</span>
            AI 舍友库
          </span>
          <button
            class="roommate-add-btn pop-shadow"
            type="button"
            :disabled="roommates.length >= 5 && !hasActiveConversation"
            :aria-disabled="hasActiveConversation"
            @click="openAddRoommate"
          >
            <span class="material-symbol" aria-hidden="true">add</span>
            新增
          </button>
        </div>

        <TransitionGroup name="roommate-list" tag="div" class="roommate-grid">
          <article
            v-for="(roommate, index) in roommates"
            :key="roommate.id"
            class="roommate-card card-border pop-card"
          >
            <button
              class="roommate-edit-btn"
              type="button"
              :aria-disabled="!canEditRoommates"
              :aria-label="`编辑${roommate.name}`"
              @click="openEditRoommate(index)"
            >
              <span class="material-symbol" aria-hidden="true">edit</span>
            </button>
            <div :class="['roommate-badge', `roommate-badge-${roommate.preset_key ?? 'custom'}`]">
              <span class="material-symbol" aria-hidden="true">
                {{ roommate.tag_mode === 'custom' ? 'tune' : 'person' }}
              </span>
            </div>
            <div class="roommate-card-head">
              <div
                :class="['roommate-avatar', 'roommate-avatar-character', `roommate-avatar-${roommate.avatar}`]"
                aria-hidden="true"
              >
                {{ avatarShortLabel(roommate.avatar) }}
              </div>
              <div>
                <h3>{{ roommate.name }}</h3>
                <p class="roommate-tag card-border">{{ roommate.personality_tag }}</p>
              </div>
            </div>
            <div class="roommate-trait-summary">
              <span v-for="key in traitKeys.slice(0, 3)" :key="key">
                {{ roommateTraitLabels[key] }} {{ roommate.traits[key] }}
              </span>
            </div>
          </article>
        </TransitionGroup>
      </aside>

      <section class="chat-panel card-border pop-card">
        <header class="chat-header card-border">
          <div class="chat-title chat-title-row">
            <span class="material-symbol" aria-hidden="true">chat</span>
            <h2>对话模拟器</h2>
            <button
              class="archive-switch"
              :class="{ 'archive-switch-on': useEventArchive }"
              type="button"
              :disabled="archiveEventCount === 0"
              :aria-pressed="useEventArchive"
              @click="useEventArchive = !useEventArchive"
            >
              <span aria-hidden="true"></span>
              {{ archiveSwitchLabel }}
            </button>
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
          <p v-if="archiveLoadError" class="chat-system archive-system-note card-border">
            {{ archiveLoadError }}
          </p>

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
                  {{ userMessage || '先写一句你准备说出口的话' }}
                </p>
              </article>

              <div class="chat-message-list">
                <article
                  v-for="reply in designPreview.replies"
                  :key="reply.roommate_id"
                  class="chat-bubble card-border pop-card"
                >
                  <p class="chat-role">{{ reply.roommate }}（{{ reply.personality }}）</p>
                  <p>{{ reply.message }}</p>
                </article>
              </div>
            </div>
          </Transition>

          <div class="chat-hint card-border pop-card">
            <p class="chat-hint-label">
              <span class="material-symbol" aria-hidden="true">tips_and_updates</span>
              建议先表达感受，再提出具体请求。
            </p>
            <p>{{ chatHintMessage }}</p>
          </div>

          <div v-if="safetyNote || !storedSimulationMeta" class="chat-footer-note card-border pop-card">
            <p>{{ safetyNote || '请基于对方反馈继续补充你的下一句。' }}</p>
          </div>
        </div>

        <form class="simulation-input-bar card-border" @submit.prevent="sendMessage">
          <div class="comm-input-wrap">
            <input
              v-model="userMessage"
              :placeholder="defaultSpeechPlaceholder"
              type="text"
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

    <Transition name="roommate-editor">
      <div v-if="roommateDraft" class="roommate-editor-backdrop" @click.self="closeRoommateEditor">
        <form class="roommate-editor-panel pop-card pop-shadow" @submit.prevent="saveDraft">
          <header>
            <h2>{{ editingIndex === null ? '新增 AI 舍友' : '编辑 AI 舍友' }}</h2>
            <button type="button" class="roommate-editor-close" @click="closeRoommateEditor">
              <span class="material-symbol" aria-hidden="true">close</span>
            </button>
          </header>

          <label class="roommate-field">
            名称
            <input v-model="roommateDraft.name" maxlength="20" />
          </label>

          <section class="roommate-avatar-picker" aria-label="选择舍友头像">
            <p>头像</p>
            <div>
              <button
                v-for="option in availableAvatarOptions"
                :key="option.key"
                type="button"
                :class="['roommate-avatar-choice', { active: roommateDraft.avatar === option.key }]"
                @click="selectDraftAvatar(option.key)"
              >
                <span :class="`roommate-avatar-${option.key}`" aria-hidden="true">
                  {{ option.shortLabel }}
                </span>
                {{ option.label }}
              </button>
            </div>
          </section>

          <div class="roommate-segmented" :data-mode="roommateDraft.mode">
            <span class="roommate-segmented-thumb" aria-hidden="true"></span>
            <button
              v-for="option in roommatePresetOptions"
              :key="option.key"
              type="button"
              :class="{ active: roommateDraft.mode === option.key }"
              @click="setDraftMode(option.key)"
            >
              {{ option.label }}
            </button>
            <button
              type="button"
              :class="{ active: roommateDraft.mode === 'custom' }"
              @click="setDraftMode('custom')"
            >
              自定义
            </button>
          </div>

          <Transition name="roommate-editor-section" mode="out-in">
            <div v-if="roommateDraft.mode === 'custom'" key="custom" class="roommate-custom-block">
              <label class="roommate-field">
                自定义标签
                <input v-model="roommateDraft.customTag" maxlength="20" />
              </label>
              <label v-for="key in traitKeys" :key="key" class="roommate-slider-row">
                <span>{{ roommateTraitLabels[key] }}</span>
                <input
                  v-model.number="roommateDraft.traits[key]"
                  type="range"
                  min="0"
                  max="5"
                  step="1"
                  :style="traitFillStyle(roommateDraft.traits[key])"
                />
                <strong>{{ roommateDraft.traits[key] }}</strong>
              </label>
            </div>
            <div v-else key="preset" class="roommate-preset-summary">
              <p>预设属性会自动应用到这位舍友。</p>
              <div>
                <span v-for="key in traitKeys" :key="key">
                  {{ roommateTraitLabels[key] }} {{ roommateDraft.traits[key] }}
                </span>
              </div>
            </div>
          </Transition>

          <footer class="roommate-editor-actions">
            <button
              class="danger-action"
              type="button"
              :disabled="!canDeleteDraft"
              @click="deleteDraftRoommate"
            >
              删除
            </button>
            <button class="secondary-action pop-shadow" type="button" @click="closeRoommateEditor">
              取消
            </button>
            <button class="primary-action pop-shadow" type="submit">保存</button>
          </footer>
        </form>
      </div>
    </Transition>

    <Transition name="modal-fade">
      <div
        v-if="showRoommateLockedModal"
        class="safety-modal-overlay"
        role="presentation"
        @click.self="closeRoommateLockedModal"
      >
        <section
          ref="roommateLockedModalRef"
          class="roommate-locked-modal safety-modal pop-card pop-shadow"
          role="dialog"
          aria-modal="true"
          aria-labelledby="roommate-locked-modal-title"
          tabindex="-1"
          @keydown="handleRoommateLockedKeydown"
        >
          <h2 id="roommate-locked-modal-title">功能限制提示</h2>
          <p class="roommate-locked-copy">
            对话模拟时不能使用舍友编辑和添加功能，请点击重置按钮后再编辑。
          </p>
          <div class="modal-actions">
            <button
              ref="roommateLockedConfirmRef"
              class="primary-action pop-shadow"
              type="button"
              @click="closeRoommateLockedModal"
            >
              我知道了
            </button>
          </div>
        </section>
      </div>
    </Transition>
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
