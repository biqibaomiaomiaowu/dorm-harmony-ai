<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

import { fetchArchiveAnalysis, type ArchiveAnalysisResponse } from '@/data/eventArchive'

const featureCards = [
  {
    title: 'AI 深度分析',
    icon: 'psychology_alt',
    text: '识别宿舍事件中的压力来源，生成非诊断性的趋势提示和温和沟通建议。',
    action: '开启分析',
    tone: 'pink',
  },
  {
    title: '沟通模拟器',
    icon: 'forum',
    text: '在安全的沙盒环境中练习对话。模拟不同语气的反馈效果，掌握非暴力沟通技巧。',
    action: '进入沙盒',
    tone: 'purple',
  },
  {
    title: '关系改善趋势',
    icon: 'trending_up',
    text: '追踪长期互动数据，生成可视化的关系健康报告，见证你们的共同成长。',
    action: '查看报告',
    tone: 'yellow',
  },
]

const SAFETY_ACK_STORAGE_KEY = 'dorm-harmony:safety-acknowledged'
const HOME_METER_FALLBACK: ArchiveAnalysisResponse = {
  pressure_score: 0,
  risk_level: 'stable',
  risk_label: '关系平稳',
  main_sources: [],
  emotion_keywords: [],
  trend_message: '当前还没有读取到事件档案汇总，关系状态暂按“关系平稳”展示。',
  suggestion: '记录事件后，首页会从后端同步宿舍压力晴雨表。',
  recommend_simulation: false,
  disclaimer: '本结果仅用于宿舍关系压力趋势提示，不作为医学或心理诊断依据。',
  event_count: 0,
  active_30d_count: 0,
  source_breakdown: [],
}

const showSafetyModal = ref(false)
const safetyModalRef = ref<HTMLElement | null>(null)
const safetyConfirmRef = ref<HTMLButtonElement | null>(null)
const showPrivacyModal = ref(false)
const privacyModalRef = ref<HTMLElement | null>(null)
const privacyConfirmRef = ref<HTMLButtonElement | null>(null)
const restoreFocusTarget = ref<HTMLElement | null>(null)
const shouldRestoreFocusAfterModalLeave = ref(false)
const shouldOpenPrivacyAfterSafetyLeave = ref(false)
const homeMeterAnalysis = ref<ArchiveAnalysisResponse>(HOME_METER_FALLBACK)
const homeMeterError = ref('')
const isHomeMeterLoading = ref(false)
const animatedMeterPercent = ref(0)
let homeMeterAnimationFrame = 0
let isHomeViewActive = false

const homeMeterWeatherIcon = computed(() => {
  const score = animatedMeterPercent.value

  if (score <= 30) {
    return {
      key: 'sunny',
      icon: 'wb_sunny',
      label: '晴天',
      tone: 'sunny',
    }
  }

  if (score <= 60) {
    return {
      key: 'cloudy',
      icon: 'cloud',
      label: '阴天',
      tone: 'cloudy',
    }
  }

  return {
    key: 'rainy',
    icon: 'rainy',
    label: '雨天',
    tone: 'rainy',
  }
})

const focusableSelector = [
  'a[href]',
  'button:not([disabled])',
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

function focusInitialModalControl() {
  nextTick(() => {
    safetyConfirmRef.value?.focus()
  })
}

function focusPrivacyModalControl() {
  nextTick(() => {
    privacyConfirmRef.value?.focus()
  })
}

function hasAcknowledgedSafetyModal() {
  try {
    return window.localStorage.getItem(SAFETY_ACK_STORAGE_KEY) === 'true'
  } catch {
    return false
  }
}

function prefersReducedMotion() {
  return (
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  )
}

function cancelHomeMeterAnimation() {
  if (homeMeterAnimationFrame) {
    window.cancelAnimationFrame(homeMeterAnimationFrame)
    homeMeterAnimationFrame = 0
  }
}

function normalizeHomeMeterScore(value: number) {
  if (!Number.isFinite(value)) {
    return 0
  }

  return Math.max(0, Math.min(100, Math.round(value)))
}

function animateHomeMeter() {
  if (!isHomeViewActive) {
    return
  }

  cancelHomeMeterAnimation()

  if (prefersReducedMotion()) {
    animatedMeterPercent.value = normalizeHomeMeterScore(homeMeterAnalysis.value.pressure_score)
    return
  }

  animatedMeterPercent.value = 0

  const targetPercent = normalizeHomeMeterScore(homeMeterAnalysis.value.pressure_score)
  const durationMs = 2200
  const startTime = window.performance.now()

  const step = (currentTime: number) => {
    if (!isHomeViewActive) {
      homeMeterAnimationFrame = 0
      return
    }

    const elapsed = currentTime - startTime
    const progress = Math.min(1, elapsed / durationMs)
    const easedProgress = 1 - (1 - progress) ** 3

    animatedMeterPercent.value = Math.round(targetPercent * easedProgress)

    if (progress < 1) {
      homeMeterAnimationFrame = window.requestAnimationFrame(step)
    } else {
      homeMeterAnimationFrame = 0
    }
  }

  homeMeterAnimationFrame = window.requestAnimationFrame(step)
}

async function loadHomeMeterAnalysis() {
  isHomeMeterLoading.value = true
  homeMeterError.value = ''

  try {
    const response = await fetchArchiveAnalysis()

    if (!isHomeViewActive) {
      return
    }

    homeMeterAnalysis.value = response
    await nextTick()
    animateHomeMeter()
  } catch (error) {
    if (!isHomeViewActive) {
      return
    }

    homeMeterAnalysis.value = HOME_METER_FALLBACK
    homeMeterError.value =
      error instanceof Error ? error.message : '宿舍压力晴雨表暂时无法加载'
    animateHomeMeter()
  } finally {
    if (isHomeViewActive) {
      isHomeMeterLoading.value = false
    }
  }
}

function openSafetyModal(event?: MouseEvent) {
  restoreFocusTarget.value =
    event?.currentTarget instanceof HTMLElement
      ? event.currentTarget
      : document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null
  shouldRestoreFocusAfterModalLeave.value = false
  shouldOpenPrivacyAfterSafetyLeave.value = false
  showSafetyModal.value = true
  focusInitialModalControl()
}

function openPrivacyModal(event?: MouseEvent) {
  restoreFocusTarget.value =
    event?.currentTarget instanceof HTMLElement
      ? event.currentTarget
      : document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null
  shouldRestoreFocusAfterModalLeave.value = false
  shouldOpenPrivacyAfterSafetyLeave.value = showSafetyModal.value
  showSafetyModal.value = false

  if (!shouldOpenPrivacyAfterSafetyLeave.value) {
    showPrivacyModal.value = true
    focusPrivacyModalControl()
  }
}

function restoreFocusAfterModalClose() {
  nextTick(() => {
    const target = restoreFocusTarget.value

    if (target && document.contains(target)) {
      target.focus()
      return
    }

    document.querySelector<HTMLElement>('.primary-action, a, button')?.focus()
  })
}

function featureActionTarget(action: string): 'record' | 'simulate' | 'review' | null {
  if (action === '开启分析') {
    return 'record'
  }

  if (action === '进入沙盒') {
    return 'simulate'
  }

  if (action === '查看报告') {
    return 'review'
  }

  return null
}

function closeSafetyModal() {
  try {
    window.localStorage.setItem(SAFETY_ACK_STORAGE_KEY, 'true')
  } catch {
    // Ignore storage failures so the modal can still be dismissed in restricted browsers.
  }

  showSafetyModal.value = false
  shouldOpenPrivacyAfterSafetyLeave.value = false
  shouldRestoreFocusAfterModalLeave.value = true
}

function closePrivacyModal() {
  showPrivacyModal.value = false
  shouldRestoreFocusAfterModalLeave.value = true
}

function handleSafetyModalAfterLeave() {
  if (shouldOpenPrivacyAfterSafetyLeave.value) {
    shouldOpenPrivacyAfterSafetyLeave.value = false
    showPrivacyModal.value = true
    focusPrivacyModalControl()
    return
  }

  if (shouldRestoreFocusAfterModalLeave.value && !showPrivacyModal.value) {
    shouldRestoreFocusAfterModalLeave.value = false
    restoreFocusAfterModalClose()
  }
}

function handlePrivacyModalAfterLeave() {
  if (shouldRestoreFocusAfterModalLeave.value) {
    shouldRestoreFocusAfterModalLeave.value = false
    restoreFocusAfterModalClose()
  }
}

function handleModalKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    event.preventDefault()
    closeSafetyModal()
    return
  }

  if (event.key !== 'Tab') {
    return
  }

  const focusableElements = getModalFocusableElements(safetyModalRef.value)

  if (focusableElements.length === 0) {
    event.preventDefault()
    safetyModalRef.value?.focus()
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

function handlePrivacyKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    event.preventDefault()
    closePrivacyModal()
    return
  }

  if (event.key !== 'Tab') {
    return
  }

  const focusableElements = getModalFocusableElements(privacyModalRef.value)

  if (focusableElements.length === 0) {
    event.preventDefault()
    privacyModalRef.value?.focus()
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

onMounted(() => {
  isHomeViewActive = true
  restoreFocusTarget.value = document.activeElement instanceof HTMLElement ? document.activeElement : null
  void loadHomeMeterAnalysis()

  if (!hasAcknowledgedSafetyModal()) {
    showSafetyModal.value = true
    focusInitialModalControl()
  }
})

onBeforeUnmount(() => {
  isHomeViewActive = false
  cancelHomeMeterAnimation()
})
</script>

<template>
  <main class="page home-page">
    <Transition name="modal-fade" @after-leave="handleSafetyModalAfterLeave">
      <div v-if="showSafetyModal" class="safety-modal-overlay" role="presentation">
        <section
          ref="safetyModalRef"
          class="safety-modal pop-card pop-shadow"
          role="dialog"
          aria-modal="true"
          aria-labelledby="safety-modal-title"
          tabindex="-1"
          @keydown="handleModalKeydown"
        >
          <button
            class="modal-close material-symbol"
            type="button"
            aria-label="关闭首次使用提示"
            @click="closeSafetyModal"
          >
            close
          </button>
          <p class="eyebrow pill-label">
            <span class="material-symbol" aria-hidden="true">verified_user</span>
            首次使用提示
          </p>
          <h2 id="safety-modal-title">使用前请了解安全边界</h2>
          <p class="safety-intro">
            舍友心晴仅用于宿舍压力趋势提示和沟通练习，不进行心理疾病诊断，也不评价任何舍友的人格或心理状态。
          </p>
          <ul class="safety-modal-list">
            <li>压力值只用于关系压力趋势提示，不作为医学或心理诊断依据。</li>
            <li>
              如果出现高压力、严重冲突、持续失眠、强烈焦虑或暴力风险，请及时联系辅导员、心理老师、家人或可信任同学。
            </li>
            <li>Demo 阶段不采集真实身份信息，演示数据使用虚拟样例。</li>
          </ul>
          <div class="modal-actions">
            <button
              ref="safetyConfirmRef"
              class="primary-action pop-shadow"
              type="button"
              @click="closeSafetyModal"
            >
              我已了解，开始使用
              <span class="action-icon material-symbol" aria-hidden="true">arrow_forward</span>
            </button>
            <button
              class="secondary-action"
              type="button"
              @click="openPrivacyModal"
            >
              查看隐私原则
            </button>
          </div>
        </section>
      </div>
    </Transition>

    <Transition name="modal-fade" @after-leave="handlePrivacyModalAfterLeave">
      <div v-if="showPrivacyModal" class="safety-modal-overlay" role="presentation">
        <section
          ref="privacyModalRef"
          class="safety-modal pop-card pop-shadow"
          role="dialog"
          aria-modal="true"
          aria-labelledby="privacy-modal-title"
          tabindex="-1"
          @keydown="handlePrivacyKeydown"
        >
          <button
            class="modal-close material-symbol"
            type="button"
            aria-label="关闭隐私说明"
            @click="closePrivacyModal"
          >
            close
          </button>
          <p class="eyebrow pill-label">
            <span class="material-symbol" aria-hidden="true">verified_user</span>
            隐私说明
          </p>
          <h2 id="privacy-modal-title">查看隐私原则</h2>
          <ul class="safety-modal-list">
            <li>演示数据使用虚拟样例，不采集真实姓名、学号、电话等真实身份信息。</li>
            <li>仅保留支持关系趋势分析所需的最小字段。</li>
            <li>本建议用于沟通练习，不作为心理诊断或医学判断依据。</li>
          </ul>
          <div class="modal-actions">
            <button
              ref="privacyConfirmRef"
              class="primary-action pop-shadow"
              type="button"
              @click="closePrivacyModal"
            >
              我已了解
            </button>
          </div>
        </section>
      </div>
    </Transition>

    <section class="hero-section page-pop-in">
      <div class="hero-copy">
        <p class="eyebrow pill-label">
          <span class="material-symbol" aria-hidden="true">waving_hand</span>
          Welcome back to harmony
        </p>
        <h1>
          舍友心晴：<br />
          <span class="hero-highlight">
            宿舍压力预警与沟通演练助手
            <svg
              class="hero-squiggle"
              viewBox="0 0 100 20"
              preserveAspectRatio="none"
              aria-hidden="true"
            >
              <path
                d="M0,10 Q25,0 50,10 T100,10"
                fill="none"
                stroke="currentColor"
                stroke-linecap="round"
                stroke-width="4"
              ></path>
            </svg>
          </span>
        </h1>
        <p class="hero-text">
          记录宿舍事件，识别压力来源，通过 AI 多角色沟通演练，在真实沟通前练习更温和、具体、可执行的表达方式。
        </p>
        <div class="action-row">
          <RouterLink class="primary-action pop-shadow" :to="{ name: 'record' }">
            开始记录
            <span class="action-icon material-symbol" aria-hidden="true">arrow_forward</span>
          </RouterLink>
          <button class="secondary-action" type="button" @click="openSafetyModal">安全说明</button>
        </div>
      </div>
    </section>

    <section class="dashboard-card pop-card pop-shadow page-pop-in" aria-label="压力晴雨表示例">
      <div class="dashboard-main">
        <span
          :class="['floating-icon', `floating-icon-${homeMeterWeatherIcon.tone}`]"
          :aria-label="`当前压力天气：${homeMeterWeatherIcon.label}`"
          role="img"
        >
          <Transition name="weather-icon-flip" mode="out-in">
            <span :key="homeMeterWeatherIcon.key" class="material-symbol">
              {{ homeMeterWeatherIcon.icon }}
            </span>
          </Transition>
        </span>
        <div class="meter-header">
          <span>宿舍压力晴雨表</span>
          <strong>{{ isHomeMeterLoading ? '读取中...' : homeMeterAnalysis.risk_label }}</strong>
        </div>
        <div class="meter-score">
          <span>当前环境氛围评估</span>
          <strong>Index: {{ animatedMeterPercent }}/100</strong>
        </div>
        <div class="meter-track">
          <span
            class="meter-fill"
            :style="{ '--home-meter-percent': `${animatedMeterPercent}%` }"
          ></span>
        </div>
        <div class="meter-labels">
          <span>和谐融洽</span>
          <span>需干预</span>
        </div>
      </div>
      <aside class="recent-note card-border">
        <strong>档案汇总</strong>
        <p v-if="homeMeterError">{{ homeMeterError }}</p>
        <p v-else>{{ homeMeterAnalysis.trend_message }}</p>
        <p>
          共 {{ homeMeterAnalysis.event_count }} 条事件，近 30 天
          {{ homeMeterAnalysis.active_30d_count }} 条。
        </p>
        <RouterLink :to="{ name: 'analysis' }">查看分析 →</RouterLink>
      </aside>
    </section>

    <section id="safety-note" class="feature-grid page-pop-in" aria-label="功能重点">
      <article
        v-for="card in featureCards"
        :key="card.title"
        :class="['feature-card', 'feature-card-visual', `feature-card-${card.tone}`, 'pop-card']"
      >
        <span class="field-icon material-symbol" aria-hidden="true">{{ card.icon }}</span>
        <h2>{{ card.title }}</h2>
        <p>{{ card.text }}</p>
        <RouterLink
          v-if="featureActionTarget(card.action)"
          class="feature-action"
          :to="{ name: featureActionTarget(card.action)! }"
        >
          {{ card.action }}
        </RouterLink>
        <button v-else class="feature-action" type="button">{{ card.action }}</button>
      </article>
    </section>

  </main>
</template>
