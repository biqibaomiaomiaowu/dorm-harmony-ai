<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { useGsapMotion } from '@/composables/useGsapMotion'
import {
  ARCHIVE_INSIGHT_CACHE_KEY,
  deleteEventRecord,
  emotionLabels,
  eventTypeLabels,
  fetchEventArchive,
  frequencyLabels,
  type ArchiveEmotion,
  type EventRecord,
} from '@/data/eventArchive'

const events = ref<EventRecord[]>([])
const isLoading = ref(true)
const loadError = ref('')
const currentPage = ref(1)
const confirmingDeleteId = ref('')
const deletingEventIds = ref<Set<string>>(new Set())
const removingEventIds = ref<Set<string>>(new Set())
const deleteError = ref('')
const archiveGridRef = ref<HTMLElement | null>(null)
const { animateFlipReflow, gsap, prefersReducedMotion, withContext } = useGsapMotion(
  () => archiveGridRef.value,
)
const pageSize = 6
let isArchiveViewActive = false
const archiveStickerStyles = [
  { tone: 'sticker-pink', rotate: '-2.4deg', tapeRotate: '-7deg' },
  { tone: 'sticker-yellow', rotate: '2deg', tapeRotate: '5deg' },
  { tone: 'sticker-purple', rotate: '-1deg', tapeRotate: '3deg' },
  { tone: 'sticker-green', rotate: '1.8deg', tapeRotate: '-5deg' },
  { tone: 'sticker-blue', rotate: '-1.6deg', tapeRotate: '6deg' },
  { tone: 'sticker-cream', rotate: '2.8deg', tapeRotate: '-2deg' },
] as const

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

function eventPrimaryEmotion(event: EventRecord) {
  return event.primary_emotion ?? event.emotion
}

function eventEmotionList(event: EventRecord): ArchiveEmotion[] {
  const values = event.emotions && event.emotions.length > 0 ? event.emotions : [eventPrimaryEmotion(event)]
  return Array.from(new Set(values))
}

function eventEmotionLabel(emotion: string) {
  return emotionLabels[emotion] ?? emotion
}

function isEventPrimaryEmotion(event: EventRecord, emotion: string) {
  return eventPrimaryEmotion(event) === emotion
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

function findArchiveEventCard(eventId: string) {
  const slots = archiveGridRef.value?.querySelectorAll<HTMLElement>('[data-event-id]') ?? []

  for (const slot of slots) {
    if (slot.dataset.eventId === eventId) {
      return slot.querySelector<HTMLElement>('.archive-event-card')
    }
  }

  return null
}

async function removeEventAfterAnimation(eventId: string) {
  if (!isArchiveViewActive) {
    return
  }

  const previousRects = collectArchiveSlotRects()
  events.value = events.value.filter((event) => event.id !== eventId)
  removingEventIds.value = cloneIdSet(removingEventIds.value, eventId, 'delete')
  confirmingDeleteId.value = ''
  currentPage.value = Math.min(currentPage.value, pageCount.value)
  await nextTick()

  if (!isArchiveViewActive) {
    return
  }

  withContext(() => animateFlipReflow(previousRects, archiveGridRef.value))
}

function animateStickerRemoval(eventId: string) {
  if (!isArchiveViewActive) {
    return
  }

  const card = findArchiveEventCard(eventId)

  if (!card || prefersReducedMotion()) {
    void removeEventAfterAnimation(eventId)
    return
  }

  withContext(() => {
    gsap.to(card, {
      x: 220,
      y: -82,
      rotation: '+=20',
      autoAlpha: 0,
      duration: 0.68,
      ease: 'power3.in',
      onComplete: () => {
        if (!isArchiveViewActive) {
          return
        }

        void removeEventAfterAnimation(eventId)
      },
    })
  })
}

async function requestDeleteEvent(event: EventRecord) {
  if (!isArchiveViewActive || isDeleting(event.id) || isRemoving(event.id)) {
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

    if (!isArchiveViewActive) {
      return
    }

    removingEventIds.value = cloneIdSet(removingEventIds.value, event.id, 'add')
    animateStickerRemoval(event.id)
  } catch (error) {
    if (!isArchiveViewActive) {
      return
    }

    deleteError.value = error instanceof Error ? error.message : '事件删除失败，请稍后重试'
  } finally {
    if (isArchiveViewActive) {
      deletingEventIds.value = cloneIdSet(deletingEventIds.value, event.id, 'delete')
    }
  }
}

function goToPreviousPage() {
  currentPage.value = Math.max(1, currentPage.value - 1)
}

function goToNextPage() {
  currentPage.value = Math.min(pageCount.value, currentPage.value + 1)
}

async function loadArchive() {
  if (!isArchiveViewActive) {
    return
  }

  isLoading.value = true
  loadError.value = ''

  try {
    const response = await fetchEventArchive()

    if (!isArchiveViewActive) {
      return
    }

    events.value = response.events
    currentPage.value = 1
  } catch (error) {
    if (!isArchiveViewActive) {
      return
    }

    loadError.value =
      error instanceof Error ? error.message : '事件档案加载失败，请稍后重试'
  } finally {
    if (isArchiveViewActive) {
      isLoading.value = false
    }
  }
}

onMounted(() => {
  isArchiveViewActive = true
  void loadArchive()
})

onBeforeUnmount(() => {
  isArchiveViewActive = false
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

      <Transition name="archive-content-state" mode="out-in">
        <div
          v-if="isLoading && events.length === 0"
          key="loading"
          class="archive-empty card-border"
          role="status"
          aria-live="polite"
        >
          正在加载事件档案...
        </div>

        <div v-else-if="events.length === 0" key="empty" class="archive-empty card-border">
          <span class="material-symbol" aria-hidden="true">inventory_2</span>
          <h3>还没有事件记录，请先记录一条宿舍事件。</h3>
          <RouterLink class="primary-action pop-shadow" :to="{ name: 'record' }">
            去记录事件
          </RouterLink>
        </div>

        <div v-else key="grid" ref="archiveGridRef" class="event-sticker-grid">
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
                },
              ]"
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
                <span class="archive-delete-mark material-symbol" aria-hidden="true">
                  {{ confirmingDeleteId === event.id ? 'check' : 'close' }}
                </span>
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
                <span class="sticker-emotion-meta">
                  当前情绪
                  <b>
                    <i
                      v-for="emotion in eventEmotionList(event)"
                      :key="emotion"
                      :class="{ primary: isEventPrimaryEmotion(event, emotion) }"
                    >
                      {{ eventEmotionLabel(emotion) }}
                    </i>
                  </b>
                </span>
                <span>单次压力<b>{{ event.single_analysis.pressure_score }}/100</b></span>
                <span>风险标签<b>{{ event.single_analysis.risk_label }}</b></span>
                <span>冲突/冷战<b>{{ booleanLabel(event.has_conflict) }}</b></span>
                <span>沟通状态<b>{{ communicationLabel(event.has_communicated) }}</b></span>
              </div>
            </div>
          </article>
        </div>
      </Transition>
    </section>
  </main>
</template>
