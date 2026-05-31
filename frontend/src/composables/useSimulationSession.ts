import { computed, onUnmounted, ref } from 'vue'

import {
  SIMULATION_RESULT_STORAGE_KEY,
  SimulationStreamRequestError,
  mapRoommateToReviewSpeaker,
  normalizeRoommates,
  submitSimulationStreamRequest,
  type AnalyzeRiskLevel,
  type RehearsalSourceMeta,
  type ReviewDialogueLine,
  type RoommateProfile,
  type RoommateTraits,
  type SimulationReply,
  type SimulationRequest,
  type SimulationResponse,
  type StoredSimulationResult,
} from '@/data/week1'

type RecordLike = Record<string, unknown>

export type SimulationSessionErrorState = '' | 'expired'

export interface ReplyChainTargetRange {
  min: number
  max: number
}

export interface UseSimulationSessionOptions {
  getScenario: () => string
  getRoommates: () => RoommateProfile[]
  getRiskLevel: () => AnalyzeRiskLevel | undefined
  getContext: () => string
  getUseEventArchive: () => boolean
  getSourceMeta?: () => RehearsalSourceMeta | undefined
  getReplyChainTargetRange?: () => ReplyChainTargetRange
}

export interface ResetConversationOptions {
  preserveUserMessage?: boolean
}

export interface SimulationCacheHydration {
  scenario?: string
  userMessage?: string
  sourceMeta?: RehearsalSourceMeta
}

const defaultReplyChainMin = 3
const defaultReplyChainMax = 7
const maxReplyChainLength = 15
const simulationContextMaxLength = 500
const contextTruncationSuffix = '…'
const contextSeparator = '；'
const interjectionWindowMs = 900

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

function hasStringFields(value: RecordLike, fields: string[]) {
  return fields.every((field) => typeof value[field] === 'string')
}

function isRehearsalSourceMeta(value: unknown): value is RehearsalSourceMeta {
  if (!isRecord(value) || typeof value.mode !== 'string') {
    return false
  }

  if (value.mode === 'scenario_training') {
    return (
      hasStringFields(value, [
        'category_id',
        'category_label',
        'scenario_id',
        'scenario_title',
        'target_id',
        'target_label',
        'difficulty_id',
        'difficulty_label',
      ]) &&
      (typeof value.difficulty_description === 'undefined' ||
        typeof value.difficulty_description === 'string')
    )
  }

  if (value.mode === 'custom_rehearsal') {
    return (
      typeof value.scenario === 'string' &&
      (typeof value.roommate_summary === 'undefined' || typeof value.roommate_summary === 'string')
    )
  }

  return false
}

function isStoredSimulationResult(value: unknown): value is StoredSimulationResult {
  if (!isRecord(value)) {
    return false
  }

  const request = value.request
  const response = value.response
  const dialogue = value.dialogue

  const hasValidSimulationShape =
    isRecord(request) &&
    typeof request.scenario === 'string' &&
    (typeof request.user_message === 'undefined' || typeof request.user_message === 'string') &&
    isRecord(response) &&
    Array.isArray(response.replies) &&
    typeof response.safety_note === 'string' &&
    (typeof dialogue === 'undefined' ||
      (Array.isArray(dialogue) && dialogue.every(isReviewDialogueLine)))

  if (!hasValidSimulationShape) {
    return false
  }

  if (typeof value.source_meta !== 'undefined' && !isRehearsalSourceMeta(value.source_meta)) {
    delete value.source_meta
  }

  return true
}

function cloneTraits(traits: RoommateTraits): RoommateTraits {
  return { ...traits }
}

function cloneRoommate(roommate: RoommateProfile): RoommateProfile {
  return {
    ...roommate,
    traits: cloneTraits(roommate.traits),
  }
}

function createTurnId() {
  return `turn-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

function normalizeReplyChainTargetRange(
  range: ReplyChainTargetRange | undefined,
): ReplyChainTargetRange {
  const rawMin = Number(range?.min ?? defaultReplyChainMin)
  const rawMax = Number(range?.max ?? defaultReplyChainMax)
  const min = Number.isFinite(rawMin)
    ? Math.max(1, Math.min(maxReplyChainLength, Math.round(rawMin)))
    : defaultReplyChainMin
  const max = Number.isFinite(rawMax)
    ? Math.max(min, Math.min(maxReplyChainLength, Math.round(rawMax)))
    : Math.max(min, defaultReplyChainMax)

  return { min, max }
}

function createReplyChainTarget(range?: ReplyChainTargetRange) {
  const { min, max } = normalizeReplyChainTargetRange(range)
  const span = max - min + 1
  return min + Math.floor(Math.random() * span)
}

function normalizeContextText(value: string) {
  return value.replace(/\s+/g, ' ').replace(/；\s*/g, '；').trim()
}

function truncatePreservingEdges(value: string, maxLength: number) {
  if (value.length <= maxLength) {
    return value
  }
  if (maxLength <= 0) {
    return ''
  }
  if (maxLength <= contextTruncationSuffix.length) {
    return contextTruncationSuffix.slice(0, maxLength)
  }
  if (maxLength <= 24) {
    return `${value.slice(0, maxLength - contextTruncationSuffix.length)}${contextTruncationSuffix}`
  }

  const availableLength = maxLength - contextTruncationSuffix.length
  const headLength = Math.ceil(availableLength * 0.6)
  const tailLength = availableLength - headLength

  return `${value.slice(0, headLength)}${contextTruncationSuffix}${value.slice(-tailLength)}`
}

function joinContextParts(parts: string[]) {
  return parts.map(normalizeContextText).filter(Boolean).join(contextSeparator)
}

function compactSimulationContext(baseContext: string, maxLength: number) {
  return truncatePreservingEdges(normalizeContextText(baseContext), maxLength)
}

function buildBoundedSingleReplyContext(
  baseContext: string,
  isContinuation: boolean,
  replyCount: number,
) {
  const replyLimitHint = '本次只生成1条虚拟舍友回复；前端会按需继续请求。'
  const continuationHint = isContinuation
    ? `同一会话续答；基于记忆选择下一位舍友；已连续返回${replyCount}条。`
    : '用户刚发送新表达；重新规划下一位需要回应的舍友。'
  const requiredHints = joinContextParts([replyLimitHint, continuationHint])
  const baseMaxLength = Math.max(
    0,
    simulationContextMaxLength - requiredHints.length - contextSeparator.length,
  )
  const context = joinContextParts([
    compactSimulationContext(baseContext, baseMaxLength),
    requiredHints,
  ])

  if (context.length <= simulationContextMaxLength) {
    return context
  }

  return truncatePreservingEdges(context, simulationContextMaxLength)
}

function isExpiredSessionError(error: unknown) {
  if (!(error instanceof SimulationStreamRequestError) || error.status !== 400) {
    return false
  }

  const detail = `${error.detail} ${error.message}`.toLowerCase()
  return (
    detail.includes('未找到对应的模拟对话') ||
    detail.includes('missing-memory') ||
    detail.includes('missing memory') ||
    detail.includes('session lost') ||
    detail.includes('conversation memory')
  )
}

export function useSimulationSession(options: UseSimulationSessionOptions) {
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
  const storedSimulationMeta = ref('')
  const hasUserTurn = ref(false)
  const hasCompleteSimulationTurn = ref(false)
  const conversationId = ref('')
  const currentTurnId = ref('')
  const systemTurnNotice = ref('')
  const sessionErrorState = ref<SimulationSessionErrorState>('')
  const expiredRetryMessage = ref('')

  const hasActiveConversation = computed(() =>
    Boolean(conversationId.value || conversationMessages.value.length > 0 || isSubmitting.value),
  )

  const canEnterReview = computed(() =>
    Boolean(
      conversationId.value &&
      hasUserTurn.value &&
      hasCompleteSimulationTurn.value &&
      !isDemoResult.value &&
      !isSubmitting.value &&
      queuedUserMessages.value.length === 0 &&
      sessionErrorState.value !== 'expired',
    ),
  )

  const reviewGateMessage = computed(() => {
    if (sessionErrorState.value === 'expired') {
      return '当前会话已失效，请重新开始后再生成复盘。'
    }
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
    if (sessionErrorState.value === 'expired') {
      return '当前会话无法继续，请重新开始后再发送。'
    }
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

  function clearSimulationCache() {
    try {
      localStorage.removeItem(SIMULATION_RESULT_STORAGE_KEY)
    } catch {
      // ignore restricted storage
    }
  }

  function setDefaultSimulationState(resetOptions: ResetConversationOptions = {}) {
    const nextUserMessage = resetOptions.preserveUserMessage ? userMessage.value : ''
    userMessage.value = nextUserMessage
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
    sessionErrorState.value = ''
    expiredRetryMessage.value = ''
    isContinuationRequestActive.value = false
  }

  function resetConversation(resetOptions: ResetConversationOptions = {}) {
    generationRunId.value += 1
    activeSimulationAbortController.value?.abort()
    activeSimulationAbortController.value = null
    isSubmitting.value = false
    setDefaultSimulationState(resetOptions)
    clearSimulationCache()
  }

  function hydrateFromSimulationCache(): SimulationCacheHydration {
    try {
      const raw = localStorage.getItem(SIMULATION_RESULT_STORAGE_KEY)

      if (!raw) {
        return {}
      }

      const parsed = JSON.parse(raw) as unknown

      if (!isStoredSimulationResult(parsed)) {
        return {}
      }

      if (parsed.response.is_demo) {
        clearSimulationCache()
        return {}
      }

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
      safetyNote.value = parsed.response.safety_note || ''
      storedSimulationMeta.value = parsed.response.is_demo ? '演示数据' : '已返回'
      conversationId.value = parsed.response.conversation_id || parsed.request.conversation_id || ''
      currentTurnId.value = parsed.request.turn_id || ''
      hasUserTurn.value = conversationMessages.value.some((line) => line.speaker === 'user')
      hasCompleteSimulationTurn.value = Boolean(conversationId.value && hasUserTurn.value)
      systemTurnNotice.value =
        parsed.response.replies.length === 0 && hasUserTurn.value
          ? '这轮舍友暂时没有回应，可以继续补充你的表达。'
          : ''

      return {
        scenario: parsed.request.scenario || undefined,
        userMessage: userMessage.value,
        sourceMeta: parsed.source_meta,
      }
    } catch {
      return {}
    }
  }

  function clearSimulationCacheForScenario(scene: string) {
    try {
      const raw = localStorage.getItem(SIMULATION_RESULT_STORAGE_KEY)
      const parsed = raw ? (JSON.parse(raw) as unknown) : null
      if (isStoredSimulationResult(parsed) && parsed.request.scenario === scene) {
        clearSimulationCache()
      }
    } catch {
      // ignore malformed local cache
    }
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

  function appendRoommateReply(reply: SimulationReply, runId: number) {
    if (runId !== generationRunId.value) {
      return false
    }

    generationStatus.value = `正在生成${reply.roommate.replace(/\s+/g, ' ')} 的回复`
    conversationMessages.value = [
      ...conversationMessages.value,
      {
        speaker: mapRoommateToReviewSpeaker(reply.roommate, reply.roommate_id),
        message: reply.message,
      },
    ]
    return true
  }

  function buildSingleReplyContext(isContinuation: boolean, replyCount: number) {
    const baseContext = options.getContext()
    return buildBoundedSingleReplyContext(baseContext, isContinuation, replyCount)
  }

  function buildSimulationRequest(message: string, isContinuation: boolean, replyCount: number) {
    const request: SimulationRequest = {
      conversation_id: conversationId.value || undefined,
      turn_id: currentTurnId.value || undefined,
      scenario: options.getScenario(),
      risk_level: options.getRiskLevel(),
      context: buildSingleReplyContext(isContinuation, replyCount),
      roommates: options.getRoommates().map(cloneRoommate),
      use_event_archive: options.getUseEventArchive(),
      max_replies: 1,
      is_continuation: isContinuation,
    }

    if (!isContinuation) {
      request.user_message = message
    }

    return request
  }

  function applyResultMeta(response: SimulationResponse) {
    isDemoResult.value = response.is_demo
    simulationNotice.value = response.is_demo
      ? response.demo_notice
      : response.archive_context_used && response.archive_context_summary
        ? `已参考事件档案：${response.archive_context_summary}`
        : ''
    safetyNote.value = response.safety_note
    storedSimulationMeta.value = response.is_demo ? '演示数据' : '已返回'
    conversationId.value = response.conversation_id
    hasCompleteSimulationTurn.value = true
    systemTurnNotice.value =
      response.replies.length === 0 ? '这轮舍友暂时没有回应，可以继续补充你的表达。' : ''
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
          source_meta: options.getSourceMeta?.(),
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
    const streamedReplies: SimulationReply[] = []
    generationStatus.value = isContinuation ? '正在判断下一条回应' : '正在规划舍友回应'
    const controller = new AbortController()
    activeSimulationAbortController.value = controller
    isContinuationRequestActive.value = isContinuation

    try {
      const response = await submitSimulationStreamRequest(
        request,
        {
          onStart: (streamConversationId) => {
            if (runId !== generationRunId.value || !streamConversationId) {
              return
            }
            conversationId.value = streamConversationId
          },
          onReply: (reply) => {
            if (appendRoommateReply(reply, runId)) {
              streamedReplies.push(reply)
            }
          },
        },
        controller.signal,
      )

      if (runId !== generationRunId.value) {
        return null
      }

      const oneReplyResponse: SimulationResponse = {
        ...response,
        replies: streamedReplies.length > 0 ? streamedReplies : response.replies,
      }

      applyResultMeta(oneReplyResponse)
      persistSimulationState(request, oneReplyResponse)
      return oneReplyResponse
    } finally {
      if (activeSimulationAbortController.value === controller) {
        activeSimulationAbortController.value = null
        isContinuationRequestActive.value = false
      }
    }
  }

  async function waitForInterjectionWindow(runId: number) {
    generationStatus.value = '可以插入你的下一句，稍后继续判断舍友回应'
    await new Promise((resolve) => window.setTimeout(resolve, interjectionWindowMs))
    return runId === generationRunId.value
  }

  function markExpiredSession(message: string) {
    sessionErrorState.value = 'expired'
    expiredRetryMessage.value = message.trim()
    queuedUserMessages.value = []
    generationStatus.value = ''
    submitError.value = ''
    systemTurnNotice.value = '当前会话已失效，请重新开始后继续。'
    clearSimulationCache()
  }

  async function runAiReplyLoop(firstMessage: string) {
    const runId = generationRunId.value + 1
    generationRunId.value = runId
    currentTurnId.value = createTurnId()
    isSubmitting.value = true
    hasCompleteSimulationTurn.value = false
    sessionErrorState.value = ''
    expiredRetryMessage.value = ''
    let nextMessage = firstMessage
    let activeUserMessage = firstMessage
    let isContinuation = false
    let replyCount = 0
    let targetReplyCount = createReplyChainTarget(options.getReplyChainTargetRange?.())

    try {
      while (runId === generationRunId.value && replyCount < maxReplyChainLength) {
        let response: SimulationResponse | null = null
        try {
          response = await requestSingleAiReply(nextMessage, isContinuation, replyCount, runId)
        } catch (error) {
          if (runId !== generationRunId.value) {
            return
          }
          if (isExpiredSessionError(error)) {
            markExpiredSession(nextMessage || activeUserMessage)
            return
          }
          throw error
        }

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
          activeUserMessage = queuedMessage
          hasCompleteSimulationTurn.value = false
          systemTurnNotice.value =
            queuedUserMessages.value.length > 0
              ? `还有 ${queuedUserMessages.value.length} 条表达在队列中。`
              : ''
          currentTurnId.value = createTurnId()
          nextMessage = queuedMessage
          isContinuation = false
          replyCount = 0
          targetReplyCount = createReplyChainTarget(options.getReplyChainTargetRange?.())
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
          activeUserMessage = queuedMessage
          hasCompleteSimulationTurn.value = false
          systemTurnNotice.value =
            queuedUserMessages.value.length > 0
              ? `还有 ${queuedUserMessages.value.length} 条表达在队列中。`
              : ''
          currentTurnId.value = createTurnId()
          nextMessage = queuedMessage
          isContinuation = false
          replyCount = 0
          targetReplyCount = createReplyChainTarget(options.getReplyChainTargetRange?.())
          continue
        }

        nextMessage = ''
        isContinuation = true
      }
    } catch (error) {
      if (runId !== generationRunId.value) {
        return
      }

      submitError.value =
        error instanceof Error && error.message
          ? error.message
          : '实时回复中断，为避免重复提交，请直接继续输入或重置后重试。'
    } finally {
      if (runId === generationRunId.value) {
        generationStatus.value = ''
        isSubmitting.value = false
      }
    }
  }

  async function retryFromExpiredSession(message = '') {
    const retryMessage = message.trim() || expiredRetryMessage.value.trim()
    resetConversation()

    if (!retryMessage) {
      submitError.value = '请输入你的回复后再发送'
      return
    }

    userMessage.value = ''
    appendUserMessage(retryMessage)
    void runAiReplyLoop(retryMessage)
  }

  async function sendMessage() {
    const message = userMessage.value.trim()

    if (sessionErrorState.value === 'expired') {
      await retryFromExpiredSession(message)
      return
    }

    if (!message) {
      submitError.value = '请输入你的回复后再发送'
      return
    }

    submitError.value = ''
    sessionErrorState.value = ''
    expiredRetryMessage.value = ''
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

  onUnmounted(() => {
    generationRunId.value += 1
    activeSimulationAbortController.value?.abort()
    activeSimulationAbortController.value = null
  })

  return {
    userMessage,
    isSubmitting,
    submitError,
    isDemoResult,
    simulationNotice,
    safetyNote,
    conversationMessages,
    cachedConversationRoommates,
    generationStatus,
    queuedUserMessages,
    storedSimulationMeta,
    hasUserTurn,
    hasCompleteSimulationTurn,
    conversationId,
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
    clearSimulationCacheForScenario,
  }
}
