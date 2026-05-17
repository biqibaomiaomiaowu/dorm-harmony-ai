<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import {
  ARCHIVE_INSIGHT_CACHE_KEY,
  deleteEventRecord,
  emotionLabels,
  eventTypeLabels,
  fetchEventArchive,
  frequencyLabels,
  type EventRecord,
} from '@/data/eventArchive'

const events = ref<EventRecord[]>([])
const isLoading = ref(false)
const loadError = ref('')
const currentPage = ref(1)
const confirmingDeleteId = ref('')
const deletingEventIds = ref<Set<string>>(new Set())
const removingEventIds = ref<Set<string>>(new Set())
const deleteError = ref('')
const archiveGridRef = ref<HTMLElement | null>(null)
const pageSize = 6
const archiveStickerStyles = [
  { tone: 'sticker-pink', rotate: '-2.4deg', tapeRotate: '-7deg' },
  { tone: 'sticker-yellow', rotate: '2deg', tapeRotate: '5deg' },
  { tone: 'sticker-purple', rotate: '-1deg', tapeRotate: '3deg' },
  { tone: 'sticker-green', rotate: '1.8deg', tapeRotate: '-5deg' },
  { tone: 'sticker-blue', rotate: '-1.6deg', tapeRotate: '6deg' },
  { tone: 'sticker-cream', rotate: '2.8deg', tapeRotate: '-2deg' },
] as const
let archiveReflowAnimations: Animation[] = []

const latestEventDate = computed(() => events.value[0]?.event_date ?? '暂无记录')
const pageCount = computed(() => Math.max(1, Math.ceil(events.value.length / pageSize)))
const pageStartIndex = computed(() => (currentPage.value - 1) * pageSize)
const pagedEvents = computed(() =>
  events.value.slice(pageStartIndex.value, pageStartIndex.value + pageSize),
)
const hasPendingArchiveMutation = computed(
  () => deletingEventIds.value.size > 0 || removingEventIds.value.size > 0,
)
const recentEventCount = computed(() => {
  const today = new Date()
  const thirtyDaysMs = 30 * 24 * 60 * 60 * 1000

  return events.value.filter((event) => {
    const eventDate = new Date(`${event.event_date}T00:00:00`)
    return Number.isFinite(eventDate.getTime()) && today.getTime() - eventDate.getTime() <= thirtyDaysMs
  }).length
})

function eventTitle(event: EventRecord) {
  return eventTypeLabels[event.event_type] ?? event.event_type
}

function eventFrequency(event: EventRecord) {
  return frequencyLabels[event.frequency] ?? event.frequency
}

function eventEmotion(event: EventRecord) {
  return emotionLabels[event.emotion] ?? event.emotion
}

function booleanLabel(value: boolean) {
  return value ? '是' : '否'
}

function communicationLabel(value: boolean) {
  return value ? '已沟通' : '未沟通'
}

function hashStickerId(eventId: string) {
  let hash = 0

  for (let index = 0; index < eventId.length; index += 1) {
    hash = (hash * 31 + eventId.charCodeAt(index)) >>> 0
  }

  return hash
}

function archiveStickerPresentation(eventId: string) {
  const styleIndex = hashStickerId(eventId) % archiveStickerStyles.length
  return archiveStickerStyles[styleIndex] ?? archiveStickerStyles[0]
}

function isDeleting(eventId: string) {
  return deletingEventIds.value.has(eventId)
}

function isRemoving(eventId: string) {
  return removingEventIds.value.has(eventId)
}

function cloneIdSet(source: Set<string>, eventId: string, action: 'add' | 'delete') {
  const next = new Set(source)
  next[action](eventId)
  return next
}

function clearArchiveInsightCache() {
  try {
    localStorage.removeItem(ARCHIVE_INSIGHT_CACHE_KEY)
  } catch {
    // Restricted browser sessions may block localStorage; analysis still reloads live data.
  }
}

function prefersReducedMotion() {
  return (
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  )
}

function collectArchiveSlotRects() {
  const rects = new Map<string, DOMRect>()
  const slots = archiveGridRef.value?.querySelectorAll<HTMLElement>('[data-event-id]') ?? []

  for (const slot of slots) {
    const eventId = slot.dataset.eventId

    if (eventId) {
      rects.set(eventId, slot.getBoundingClientRect())
    }
  }

  return rects
}

function cancelArchiveReflowAnimations() {
  for (const animation of archiveReflowAnimations) {
    animation.cancel()
  }

  archiveReflowAnimations = []
}

async function animateArchiveReflow(previousRects: Map<string, DOMRect>) {
  await nextTick()

  if (prefersReducedMotion()) {
    return
  }

  const slots = archiveGridRef.value?.querySelectorAll<HTMLElement>('[data-event-id]') ?? []
  let movedSlotIndex = 0

  for (const slot of slots) {
    const eventId = slot.dataset.eventId
    const previousRect = eventId ? previousRects.get(eventId) : undefined

    if (!previousRect || typeof slot.animate !== 'function') {
      continue
    }

    const currentRect = slot.getBoundingClientRect()
    const deltaX = previousRect.left - currentRect.left
    const deltaY = previousRect.top - currentRect.top

    if (Math.abs(deltaX) < 0.5 && Math.abs(deltaY) < 0.5) {
      continue
    }

    const animation = slot.animate(
      [
        { opacity: 0.92, transform: `translate(${deltaX}px, ${deltaY}px)` },
        { opacity: 1, transform: 'translate(0, 0)' },
      ],
      {
        delay: movedSlotIndex * 70,
        duration: 520,
        easing: 'cubic-bezier(0.2, 0, 0, 1)',
        fill: 'both',
      },
    )

    animation.addEventListener('finish', () => {
      archiveReflowAnimations = archiveReflowAnimations.filter((item) => item !== animation)
    })
    archiveReflowAnimations.push(animation)
    movedSlotIndex += 1
  }
}

function removeEventAfterAnimation(eventId: string) {
  cancelArchiveReflowAnimations()
  const previousRects = collectArchiveSlotRects()
  events.value = events.value.filter((event) => event.id !== eventId)
  removingEventIds.value = cloneIdSet(removingEventIds.value, eventId, 'delete')
  confirmingDeleteId.value = ''
  currentPage.value = Math.min(currentPage.value, pageCount.value)
  void animateArchiveReflow(previousRects)
}

async function requestDeleteEvent(event: EventRecord) {
  if (isDeleting(event.id) || isRemoving(event.id)) {
    return
  }

  if (confirmingDeleteId.value !== event.id) {
    confirmingDeleteId.value = event.id
    deleteError.value = ''
    return
  }

  deletingEventIds.value = cloneIdSet(deletingEventIds.value, event.id, 'add')
  deleteError.value = ''

  try {
    await deleteEventRecord(event.id)
    clearArchiveInsightCache()
    removingEventIds.value = cloneIdSet(removingEventIds.value, event.id, 'add')
  } catch (error) {
    deleteError.value = error instanceof Error ? error.message : '事件删除失败，请稍后重试'
  } finally {
    deletingEventIds.value = cloneIdSet(deletingEventIds.value, event.id, 'delete')
  }
}

function handleStickerAnimationEnd(event: AnimationEvent, eventId: string) {
  if (
    event.animationName === 'archive-sticker-wind-away' &&
    event.currentTarget === event.target &&
    isRemoving(eventId)
  ) {
    removeEventAfterAnimation(eventId)
  }
}

function goToPreviousPage() {
  currentPage.value = Math.max(1, currentPage.value - 1)
}

function goToNextPage() {
  currentPage.value = Math.min(pageCount.value, currentPage.value + 1)
}

async function loadArchive() {
  isLoading.value = true
  loadError.value = ''

  try {
    const response = await fetchEventArchive()
    events.value = response.events
    currentPage.value = 1
  } catch (error) {
    loadError.value =
      error instanceof Error ? error.message : '事件档案加载失败，请稍后重试'
  } finally {
    isLoading.value = false
  }
}

onMounted(() => {
  void loadArchive()
})

onBeforeUnmount(() => {
  cancelArchiveReflowAnimations()
})
</script>

<template>
  <main class="page archive-page">
    <section class="archive-heading page-pop-in">
      <div class="archive-heading-mark material-symbol" aria-hidden="true">folder_special</div>
      <div>
        <p class="archive-kicker">Archive Timeline</p>
        <h1>事件档案</h1>
        <p class="archive-intro card-border pop-shadow">
          按时间查看已记录的宿舍事件，为总压力分析提供依据。
        </p>
      </div>
    </section>

    <section class="archive-summary-grid page-pop-in" aria-label="事件档案概览">
      <article class="archive-summary-card pop-card">
        <span class="material-symbol" aria-hidden="true">library_books</span>
        <p>已记录事件数</p>
        <strong>{{ events.length }}</strong>
      </article>
      <article class="archive-summary-card pop-card">
        <span class="material-symbol" aria-hidden="true">event_upcoming</span>
        <p>近 30 天事件</p>
        <strong>{{ recentEventCount }}</strong>
      </article>
      <article class="archive-summary-card pop-card">
        <span class="material-symbol" aria-hidden="true">calendar_month</span>
        <p>最近记录日期</p>
        <strong class="archive-date-value">{{ latestEventDate }}</strong>
      </article>
    </section>

    <section class="archive-action-bar card-border pop-shadow page-pop-in">
      <p>
        <span class="material-symbol" aria-hidden="true">info</span>
        压力分析将基于档案内所有事件计算，而不是只看单条事件。
      </p>
      <div class="archive-actions">
        <RouterLink class="secondary-action pop-shadow" :to="{ name: 'analysis' }">
          生成压力分析报告
        </RouterLink>
        <RouterLink class="primary-action pop-shadow" :to="{ name: 'record' }">
          <span class="action-icon material-symbol" aria-hidden="true">add</span>
          记录新事件
        </RouterLink>
      </div>
    </section>

    <section class="event-timeline pop-card page-pop-in">
      <div class="timeline-header">
        <div>
          <p>Sticker Wall</p>
          <h2>事件贴纸墙</h2>
          <span>每页展示 6 张贴纸，按后端返回顺序翻页查看。</span>
        </div>
        <div v-if="events.length > 0" class="timeline-pager" aria-label="事件贴纸墙分页">
          <button
            class="timeline-page-btn pop-shadow material-symbol"
            type="button"
            :disabled="currentPage === 1 || hasPendingArchiveMutation"
            aria-label="上一页事件贴纸"
            @click="goToPreviousPage"
          >
            chevron_left
          </button>
          <span class="timeline-page-status">
            第 {{ currentPage }} / {{ pageCount }} 页
          </span>
          <button
            class="timeline-page-btn pop-shadow material-symbol"
            type="button"
            :disabled="currentPage === pageCount || hasPendingArchiveMutation"
            aria-label="下一页事件贴纸"
            @click="goToNextPage"
          >
            chevron_right
          </button>
        </div>
      </div>

      <p v-if="loadError || deleteError" class="error-text archive-error" role="alert">
        {{ loadError || deleteError }}
      </p>

      <div
        v-if="isLoading && events.length === 0"
        class="archive-empty card-border"
        role="status"
        aria-live="polite"
      >
        正在加载事件档案...
      </div>

      <div v-else-if="events.length === 0" class="archive-empty card-border">
        <span class="material-symbol" aria-hidden="true">inventory_2</span>
        <h3>还没有事件记录，请先记录一条宿舍事件。</h3>
        <RouterLink class="primary-action pop-shadow" :to="{ name: 'record' }">
          去记录事件
        </RouterLink>
      </div>

      <div v-else ref="archiveGridRef" class="event-sticker-grid">
        <article
          v-for="(event, index) in pagedEvents"
          :key="event.id"
          class="archive-event-slot"
          :data-event-id="event.id"
          :style="{
            '--archive-reflow-delay': `${index * 70}ms`,
            '--sticker-rotate': archiveStickerPresentation(event.id).rotate,
            '--tape-rotate': archiveStickerPresentation(event.id).tapeRotate,
          }"
        >
          <div
            :class="[
              'archive-event-card',
              'event-sticker-card',
              archiveStickerPresentation(event.id).tone,
              {
                'archive-event-card-confirming': confirmingDeleteId === event.id,
                'archive-event-card-deleting': isDeleting(event.id),
                'archive-event-card-removing': isRemoving(event.id),
              },
            ]"
            @animationend="handleStickerAnimationEnd($event, event.id)"
          >
            <button
              class="archive-delete-corner pop-shadow"
              type="button"
              :disabled="isDeleting(event.id) || isRemoving(event.id)"
              :aria-label="
                confirmingDeleteId === event.id
                  ? `确认删除 ${eventTitle(event)}`
                  : `删除 ${eventTitle(event)}`
              "
              @click="requestDeleteEvent(event)"
            >
              <span class="archive-delete-mark" aria-hidden="true">×</span>
            </button>

            <span class="sticker-date">
              <span class="material-symbol" aria-hidden="true">event</span>
              {{ event.event_date }}
            </span>

            <div class="sticker-title">
              <h3>{{ eventTitle(event) }}</h3>
              <strong class="sticker-pressure">{{ event.single_analysis.pressure_score }}</strong>
            </div>

            <p class="sticker-desc">{{ event.description }}</p>

            <div class="sticker-meta">
              <span>严重程度<b>{{ event.severity }}/5</b></span>
              <span>发生频率<b>{{ eventFrequency(event) }}</b></span>
              <span>当前情绪<b>{{ eventEmotion(event) }}</b></span>
              <span>单次压力<b>{{ event.single_analysis.pressure_score }}/100</b></span>
              <span>风险标签<b>{{ event.single_analysis.risk_label }}</b></span>
              <span>冲突/冷战<b>{{ booleanLabel(event.has_conflict) }}</b></span>
              <span>沟通状态<b>{{ communicationLabel(event.has_communicated) }}</b></span>
            </div>
          </div>
        </article>
      </div>
    </section>
  </main>
</template>
