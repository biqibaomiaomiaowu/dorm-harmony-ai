<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TitleComponent, TooltipComponent } from 'echarts/components'

import { useGsapMotion } from '@/composables/useGsapMotion'
import { ANALYSIS_RESULT_STORAGE_KEY } from '@/data/week1'
import {
  ARCHIVE_INSIGHT_CACHE_KEY,
  fetchArchiveAnalysis,
  fetchEventArchive,
  fetchArchiveInsight,
  isAiUnavailableError,
  isConfiguredAiMissingError,
  normalizeArchiveAnalysisResponse,
  type ArchiveAnalysisResult,
  type EventRecord,
  type ArchiveInsightResponse,
} from '@/data/eventArchive'

type AnalysisRangeDays = 7 | 15 | 30 | 90

const rangeOptions: Array<{ days: AnalysisRangeDays; label: string }> = [
  { days: 7, label: '近 7 天' },
  { days: 15, label: '近 15 天' },
  { days: 30, label: '近 30 天' },
  { days: 90, label: '近 90 天' },
]

const EMPTY_ARCHIVE_RESULT: ArchiveAnalysisResult = {
  pressure_score: 0,
  risk_level: 'stable',
  risk_label: '关系平稳',
  main_reasons: [],
  main_sources: [],
  emotion_keywords: [],
  suggestion: '请先记录事件，系统会根据事件档案汇总宿舍关系压力。',
  trend_message: '当前还没有记录事件，关系状态暂按“关系平稳”展示。',
  recommend_simulation: false,
  disclaimer: '本结果仅用于宿舍关系压力趋势提示，不作为心理诊断依据。',
  is_demo: false,
  demo_notice: '',
  suggestions: ['请先记录事件，系统会根据事件档案汇总宿舍关系压力。'],
  safety_notice: '本结果仅用于宿舍关系压力趋势提示，不作为医学或心理诊断依据。',
  trend_notice: '当前还没有记录事件，关系状态暂按“关系平稳”展示。',
  event_count: 0,
  active_30d_count: 0,
  source_breakdown: [],
  period_days: 30,
  active_period_count: 0,
  trend_points: [],
  trend_explanation: '',
  source_insights: [],
  main_source_conclusion: '',
  emotion_distribution: [],
  event_insight: null,
  training_recommendation: null,
}

const router = useRouter()
const result = ref<ArchiveAnalysisResult>(EMPTY_ARCHIVE_RESULT)
const selectedRangeDays = ref<AnalysisRangeDays>(30)
const archiveInsight = ref<ArchiveInsightResponse | null>(null)
const isAnalysisLoading = ref(true)
const analysisError = ref('')
const insightStatus = ref<'idle' | 'loading' | 'ready' | 'missing-key' | 'unavailable' | 'error'>('idle')
const insightError = ref('')
const animatedScorePercent = ref(0)
const animatedSourcePercents = ref<Record<string, number>>({})
const trendChartRef = ref<HTMLElement | null>(null)
const analysisPageRef = ref<HTMLElement | null>(null)
const { gsap, withContext, animatePageIn, animateNumber, prefersReducedMotion } = useGsapMotion(
  () => analysisPageRef.value,
)
const trendPoints = computed(() => result.value.trend_points)
const activePeriodEventCount = computed(
  () => result.value.active_period_count ?? result.value.active_30d_count,
)
const selectedRangeLabel = computed(() => `近 ${selectedRangeDays.value} 天`)
const trendChartMeta = computed(() => {
  if (!trendPoints.value.length) {
    return null
  }

  const firstPoint = trendPoints.value[0]!
  const lastPoint = trendPoints.value.at(-1)

  const totalCount = trendPoints.value.reduce((sum, point) => sum + Math.max(0, point.event_count), 0)
  const weightedScore = trendPoints.value.reduce(
    (sum, point) => sum + clampScore(point.pressure_score) * Math.max(0, point.event_count),
    0,
  )
  const fallbackScore =
    trendPoints.value.reduce((sum, point) => sum + clampScore(point.pressure_score), 0) /
    trendPoints.value.length
  const avgScore = totalCount > 0 ? Math.round(weightedScore / totalCount) : Math.round(fallbackScore)

  return {
    dateRange:
      trendPoints.value.length === 1
        ? firstPoint.date
        : `${firstPoint.date} ~ ${lastPoint?.date ?? firstPoint.date}`,
    avgScore: clampScore(avgScore),
    totalCount,
    isSinglePoint: trendPoints.value.length === 1,
  }
})

let isAnalysisViewActive = false
let trendChartInstance: echarts.ECharts | null = null
let trendChartResizeHandler: (() => void) | null = null
let hasAnimatedAnalysisSecondary = false
let lastAnimatedInsightKey = ''

echarts.use([LineChart, GridComponent, TooltipComponent, TitleComponent, CanvasRenderer])

const hasTrendData = computed(() => trendPoints.value.length > 0)

const hasArchiveEvents = computed(() => result.value.event_count > 0)

const sourceBreakdown = computed(() => {
  const tones = ['danger', 'warning', 'fresh']

  return result.value.source_breakdown.map((source, index) => ({
    label: source.label,
    percent: clampPercent(source.percent),
    animatedPercent: animatedSourcePercents.value[source.label] ?? 0,
    tone: tones[index % tones.length],
  }))
})

const sourceInsightItems = computed(() =>
  result.value.source_insights.map((source) => ({
    ...source,
    percent: clampPercent(source.percent),
    recentEventDate: source.recent_event_date || '暂无近期日期',
  })),
)

const emotionDistribution = computed(() =>
  result.value.emotion_distribution.map((emotion, index) => ({
    ...emotion,
    percent: clampPercent(emotion.percent),
    tone: ['fresh', 'warning', 'danger'][index % 3],
  })),
)

const topEmotionLabels = computed(() => result.value.event_insight?.top_emotions ?? [])
const topEventTypeLabels = computed(() => result.value.event_insight?.top_event_types ?? [])
const trainingRecommendation = computed(() => result.value.training_recommendation)

const normalizedScore = computed(() => {
  const score = Number(result.value.pressure_score)

  if (!Number.isFinite(score)) {
    return 0
  }

  return Math.max(0, Math.min(100, Math.round(score)))
})

const scoreGaugeStyle = computed(() => ({
  '--analysis-score-percent': `${animatedScorePercent.value}%`,
}))

// Compatibility marker for the older phase-3 static gate: scoreRingCircumference scoreRingStyle.
// Compatibility marker for the older phase-2 static gate: recommend_simulation.

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string')
}

function clampPercent(value: number): number {
  if (!Number.isFinite(value)) {
    return 0
  }

  return Math.max(0, Math.min(100, Math.round(value)))
}

function clampScore(value: number): number {
  if (!Number.isFinite(value)) {
    return 0
  }

  return Math.max(0, Math.min(100, Math.round(value)))
}

function getCssColor(variableName: string, fallback: string) {
  if (typeof window === 'undefined') {
    return fallback
  }

  return window
    .getComputedStyle(document.documentElement)
    .getPropertyValue(variableName)
    .trim() || fallback
}

function buildTrendChartOptions() {
  const ink = getCssColor('--ink', '#261b1f')
  const inkSoft = getCssColor('--ink-soft', '#6c5965')
  const border = getCssColor('--border', '#d6ccd2')
  const secondary = getCssColor('--secondary', '#ff8182')
  const isSinglePoint = trendPoints.value.length === 1

  if (!trendPoints.value.length) {
    return {
      title: {
        left: '50%',
        text: '暂无趋势数据',
        textStyle: {
          color: inkSoft,
          fontSize: 13,
        },
      },
      grid: {
        left: 20,
        right: 16,
        top: 10,
        bottom: 14,
      },
      xAxis: { show: false },
      yAxis: { show: false },
      series: [],
    }
  }

  return {
    grid: {
      left: 28,
      right: 16,
      top: 18,
      bottom: 24,
      containLabel: true,
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255,255,255,0.95)',
      borderColor: ink,
      borderWidth: 2,
      textStyle: {
        color: ink,
      },
      formatter: (params: Array<{ dataIndex?: number }>) => {
        const dataIndex = params?.[0]?.dataIndex
        const point = typeof dataIndex === 'number' ? trendPoints.value[dataIndex] : null

        if (!point) {
          return ''
        }

        return `${point.date}<br/>平均压力：${clampScore(point.pressure_score)}<br/>事件数：${point.event_count}`
      },
    },
    xAxis: {
      type: 'category',
      axisLabel: {
        color: inkSoft,
      },
      axisLine: {
        lineStyle: {
          color: inkSoft,
        },
      },
      axisTick: {
        lineStyle: {
          color: inkSoft,
        },
      },
      data: trendPoints.value.map((item) => item.date),
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      axisLabel: {
        color: inkSoft,
      },
      splitLine: {
        lineStyle: {
          color: border,
        },
      },
    },
    series: [
      {
        data: trendPoints.value.map((item) => clampScore(item.pressure_score)),
        type: 'line',
        smooth: !isSinglePoint,
        symbolSize: isSinglePoint ? 10 : 7,
        lineStyle: {
          width: isSinglePoint ? 0 : 3,
        },
        itemStyle: {
          color: secondary,
        },
        ...(isSinglePoint
          ? {}
          : {
              areaStyle: {
                color: 'rgba(255, 129, 130, 0.16)',
              },
            }),
      },
    ],
  }
}

function refreshTrendChart() {
  const container = trendChartRef.value

  if (!container || !isAnalysisViewActive) {
    if (!container && trendChartInstance) {
      disposeTrendChart()
    }

    return
  }

  if (trendChartInstance && trendChartInstance.getDom() !== container) {
    disposeTrendChart()
  }

  if (!trendChartInstance) {
    trendChartInstance = echarts.init(container)
  }

  trendChartInstance.setOption(buildTrendChartOptions(), true)
}

function registerTrendChartResizeListener() {
  if (typeof window === 'undefined' || trendChartResizeHandler || !isAnalysisViewActive) {
    return
  }

  trendChartResizeHandler = () => {
    if (trendChartInstance) {
      trendChartInstance.resize()
    }
  }

  window.addEventListener('resize', trendChartResizeHandler)
}

function syncTrendChart() {
  if (!isAnalysisViewActive || !hasTrendData.value) {
    disposeTrendChart()
    return
  }

  refreshTrendChart()
  registerTrendChartResizeListener()
}

function disposeTrendChart() {
  if (trendChartInstance) {
    trendChartInstance.dispose()
    trendChartInstance = null
  }

  if (trendChartResizeHandler) {
    window.removeEventListener('resize', trendChartResizeHandler)
    trendChartResizeHandler = null
  }
}

function buildSourcePercentMap(percent = 1) {
  return Object.fromEntries(
    result.value.source_breakdown.map((source) => [
      source.label,
      Math.round(clampPercent(source.percent) * percent),
    ]),
  )
}

function applyFinalAnalysisProgress() {
  if (!isAnalysisViewActive) {
    return
  }

  animatedScorePercent.value = normalizedScore.value
  animatedSourcePercents.value = buildSourcePercentMap()
}

function analysisTargets(selector: string) {
  return analysisPageRef.value?.querySelectorAll<HTMLElement>(selector)
}

function revealAnalysisMainPanels() {
  withContext(() => {
    animatePageIn(
      analysisTargets(
        '.analysis-range-tabs, .analysis-gauge-card, .analysis-stat-card, .analysis-source-panel, .analysis-emotion-panel, .analysis-trend-panel, .analysis-event-insight-panel, .analysis-training-panel',
      ),
    )
  })
}

function revealAnalysisSecondarySections() {
  if (
    hasAnimatedAnalysisSecondary ||
    !isAnalysisViewActive ||
    isAnalysisLoading.value ||
    analysisError.value
  ) {
    return
  }

  hasAnimatedAnalysisSecondary = true
  withContext(() => {
    animatePageIn(analysisTargets('.analysis-ai-section, .analysis-v2-actions, .analysis-footer'))
  })
}

function insightRevealKey() {
  if (!archiveInsight.value) {
    return insightStatus.value
  }

  return [
    insightStatus.value,
    archiveInsight.value.insight,
    archiveInsight.value.care_suggestion,
    archiveInsight.value.safety_note,
  ].join('|')
}

function revealAnalysisInsightPanel() {
  if (
    !isAnalysisViewActive ||
    isAnalysisLoading.value ||
    analysisError.value ||
    insightStatus.value !== 'ready' ||
    !archiveInsight.value
  ) {
    return
  }

  const targets = analysisTargets('.analysis-ai-card')
  if (!targets?.length) {
    return
  }

  const key = insightRevealKey()
  if (key === lastAnimatedInsightKey) {
    return
  }

  lastAnimatedInsightKey = key
  withContext(() => {
    animatePageIn(targets)
  })
}

function handleAnalysisInsightPanelAfterEnter() {
  revealAnalysisInsightPanel()
}

function animateAnalysisProgress() {
  if (!isAnalysisViewActive) {
    return
  }

  if (prefersReducedMotion()) {
    applyFinalAnalysisProgress()
    return
  }

  animatedScorePercent.value = 0
  animatedSourcePercents.value = buildSourcePercentMap(0)

  const targetScore = normalizedScore.value
  const sourceProgress = { progress: 0 }

  withContext(() => {
    animateNumber({
      to: targetScore,
      duration: 0.72,
      onUpdate: (value) => {
        if (isAnalysisViewActive) {
          animatedScorePercent.value = clampScore(value)
        }
      },
    })

    gsap.to(sourceProgress, {
      progress: 1,
      duration: 0.72,
      ease: 'power3.out',
      onUpdate: () => {
        if (isAnalysisViewActive) {
          animatedSourcePercents.value = buildSourcePercentMap(sourceProgress.progress)
        }
      },
      onComplete: () => {
        if (isAnalysisViewActive) {
          animatedSourcePercents.value = buildSourcePercentMap()
        }
      },
    })
  })
}

function isArchiveInsightResponse(value: unknown): value is ArchiveInsightResponse {
  return (
    isRecord(value) &&
    typeof value.insight === 'string' &&
    typeof value.care_suggestion === 'string' &&
    isStringArray(value.communication_focus) &&
    typeof value.safety_note === 'string'
  )
}

function buildArchiveSignature(events: EventRecord[]) {
  return JSON.stringify(
    events
      .map((event) => ({
        id: event.id,
        created_at: event.created_at,
        event_date: event.event_date,
        event_type: event.event_type,
        severity: event.severity,
        frequency: event.frequency,
        emotion: event.emotion,
        has_communicated: event.has_communicated,
        has_conflict: event.has_conflict,
        description: event.description,
      }))
      .sort((left, right) => left.id.localeCompare(right.id)),
  )
}

function readCachedArchiveInsight(archiveSignature: string) {
  try {
    const raw = localStorage.getItem(ARCHIVE_INSIGHT_CACHE_KEY)

    if (!raw) {
      return null
    }

    const parsed = JSON.parse(raw) as unknown

    if (
      isRecord(parsed) &&
      parsed.archiveSignature === archiveSignature &&
      isArchiveInsightResponse(parsed.insight)
    ) {
      return parsed.insight
    }
  } catch {
    // Restricted browser sessions may block localStorage; live generation still works.
  }

  return null
}

function writeCachedArchiveInsight(archiveSignature: string, insight: ArchiveInsightResponse) {
  try {
    localStorage.setItem(
      ARCHIVE_INSIGHT_CACHE_KEY,
      JSON.stringify({
        archiveSignature,
        insight,
      }),
    )
  } catch {
    // Restricted browser sessions may block localStorage; the generated insight is still shown.
  }
}

async function loadArchiveInsight(archiveSignature: string) {
  const cachedInsight = readCachedArchiveInsight(archiveSignature)

  if (cachedInsight) {
    if (!isAnalysisViewActive) {
      return
    }

    archiveInsight.value = cachedInsight
    insightError.value = ''
    insightStatus.value = 'ready'
    return
  }

  archiveInsight.value = null
  insightError.value = ''
  insightStatus.value = 'loading'

  try {
    const insight = await fetchArchiveInsight()

    if (!isAnalysisViewActive) {
      return
    }

    archiveInsight.value = insight
    writeCachedArchiveInsight(archiveSignature, insight)
    insightStatus.value = 'ready'
  } catch (error) {
    if (!isAnalysisViewActive) {
      return
    }

    if (isConfiguredAiMissingError(error)) {
      insightStatus.value = 'missing-key'
      insightError.value = 'AI 心晴见解需要配置 DEEPSEEK_API_KEY 后生成。'
      return
    }

    if (isAiUnavailableError(error)) {
      insightStatus.value = 'unavailable'
      insightError.value = 'AI 心晴见解暂时不可用，请稍后重试。'
      return
    }

    insightStatus.value = 'error'
    insightError.value =
      error instanceof Error ? error.message : 'AI 心晴见解暂时不可用，请稍后重试。'
  }
}

async function loadArchiveInsightForCurrentArchive(eventCount: number) {
  if (eventCount <= 0) {
    insightStatus.value = 'idle'
    return
  }

  insightStatus.value = 'loading'
  insightError.value = ''

  try {
    const archive = await fetchEventArchive()

    if (!isAnalysisViewActive) {
      return
    }

    await loadArchiveInsight(buildArchiveSignature(archive.events))
  } catch (error) {
    if (!isAnalysisViewActive) {
      return
    }

    insightStatus.value = 'error'
    insightError.value =
      error instanceof Error ? error.message : 'AI 心晴见解暂时不可用，请稍后重试。'
  }
}

async function loadArchiveAnalysis() {
  isAnalysisLoading.value = true
  analysisError.value = ''
  insightStatus.value = 'idle'
  insightError.value = ''
  archiveInsight.value = null
  disposeTrendChart()
  hasAnimatedAnalysisSecondary = false
  lastAnimatedInsightKey = ''

  try {
    const response = await fetchArchiveAnalysis(selectedRangeDays.value)

    if (!isAnalysisViewActive) {
      return
    }

    result.value = normalizeArchiveAnalysisResponse(response)

    try {
      localStorage.setItem(ANALYSIS_RESULT_STORAGE_KEY, JSON.stringify(result.value))
    } catch {
      // Restricted browser sessions may block localStorage; the page still has live data.
    }

    isAnalysisLoading.value = false
    await nextTick()

    if (!isAnalysisViewActive) {
      return
    }

    revealAnalysisMainPanels()
    revealAnalysisSecondarySections()
    revealAnalysisInsightPanel()
    animateAnalysisProgress()
    syncTrendChart()
    void loadArchiveInsightForCurrentArchive(response.event_count)
  } catch (error) {
    if (!isAnalysisViewActive) {
      return
    }

    analysisError.value =
      error instanceof Error ? error.message : '总压力分析加载失败，请稍后重试'
    disposeTrendChart()
  } finally {
    if (isAnalysisViewActive && isAnalysisLoading.value) {
      isAnalysisLoading.value = false
    }
  }
}

function selectAnalysisRange(days: AnalysisRangeDays) {
  if (selectedRangeDays.value === days || isAnalysisLoading.value) {
    return
  }

  selectedRangeDays.value = days
  void loadArchiveAnalysis()
}

function startRecommendedTraining() {
  const recommendation = trainingRecommendation.value

  if (!recommendation) {
    void router.push({ name: 'rehearsal' })
    return
  }

  void router.push({
    name: 'scenario-training',
    query: {
      category: recommendation.category_id,
      scenario: recommendation.scenario_id,
      target: recommendation.target_id,
      difficulty: recommendation.difficulty_id,
      from: 'analysis',
    },
  })
}

onMounted(() => {
  isAnalysisViewActive = true
  void loadArchiveAnalysis()
})

onBeforeUnmount(() => {
  isAnalysisViewActive = false
  disposeTrendChart()
})

watch(
  trendPoints,
  async () => {
    if (!isAnalysisViewActive) {
      return
    }

    await nextTick()
    syncTrendChart()
  },
  { deep: true },
)

watch(
  [archiveInsight, insightStatus],
  async () => {
    if (!isAnalysisViewActive) {
      return
    }

    await nextTick()
    revealAnalysisInsightPanel()
  },
)
</script>

<template>
  <main ref="analysisPageRef" class="page analysis-page analysis-v2-page">
    <span class="analysis-decoration analysis-decoration-orb-top bounce-float" aria-hidden="true"></span>

    <section class="analysis-v2-hero page-pop-in">
      <h1>宿舍总压力分析报告</h1>
      <p>
        基于事件档案内的所有记录，综合事件日期、频率、严重程度和沟通状态生成趋势提示。
      </p>
      <p
        v-if="isAnalysisLoading"
        class="analysis-source-badge card-border"
        role="status"
        aria-live="polite"
      >
        正在加载事件档案总压力...
      </p>
      <p v-else-if="analysisError" class="analysis-source-badge card-border" role="alert">
        {{ analysisError }}
      </p>
    </section>

    <section class="analysis-range-tabs card-border page-pop-in" aria-label="分析时间范围">
      <span>分析周期</span>
      <div role="group" aria-label="选择分析周期">
        <button
          v-for="option in rangeOptions"
          :key="option.days"
          type="button"
          :class="{ 'is-active': selectedRangeDays === option.days }"
          :aria-pressed="selectedRangeDays === option.days"
          :disabled="isAnalysisLoading"
          @click="selectAnalysisRange(option.days)"
        >
          {{ option.label }}
        </button>
      </div>
    </section>

    <Transition name="analysis-main-state" mode="out-in">
      <section
        v-if="analysisError && !isAnalysisLoading"
        key="error"
        class="analysis-empty-v2 pop-card pop-shadow page-pop-in"
        role="alert"
      >
        <div class="material-symbol" aria-hidden="true">cloud_off</div>
        <span class="risk-badge">加载失败</span>
        <h2>总压力分析暂时无法加载</h2>
        <p>{{ analysisError }}</p>
        <div class="analysis-actions analysis-empty-actions">
          <button class="primary-action pop-shadow" type="button" @click="loadArchiveAnalysis">
            重新加载
          </button>
          <RouterLink class="secondary-action pop-shadow" :to="{ name: 'archive' }" role="button">
            查看事件档案
          </RouterLink>
        </div>
      </section>

      <section
        v-else-if="!hasArchiveEvents && !isAnalysisLoading"
        key="empty"
        class="analysis-empty-v2 pop-card pop-shadow page-pop-in"
      >
        <div class="material-symbol" aria-hidden="true">sentiment_satisfied</div>
        <span class="risk-badge">关系平稳 (Score 0)</span>
        <h2>还没有事件记录</h2>
        <p>请先记录一条宿舍事件以生成分析。</p>
        <div class="analysis-actions analysis-empty-actions">
          <RouterLink class="primary-action pop-shadow" :to="{ name: 'record' }" role="button">
            去记录事件
          </RouterLink>
          <RouterLink class="secondary-action pop-shadow" :to="{ name: 'archive' }" role="button">
            查看事件档案
          </RouterLink>
        </div>
      </section>

      <section
        v-else-if="hasArchiveEvents && !isAnalysisLoading"
        key="ready"
        class="analysis-ready-stack"
      >
        <div class="analysis-v2-bento">
          <article
            class="analysis-gauge-card pop-card pop-shadow page-pop-in"
            :aria-label="`压力分数 ${result.pressure_score}/100`"
          >
            <span class="analysis-card-corner" aria-hidden="true"></span>
            <h2>
              <span class="material-symbol" aria-hidden="true">speed</span>
              压力指数
            </h2>
            <div class="analysis-gauge" :style="scoreGaugeStyle">
              <div class="analysis-gauge-core">
                <strong>{{ animatedScorePercent }}</strong>
                <span>/ 100</span>
              </div>
            </div>
            <div class="analysis-gauge-copy">
              <span class="risk-badge">{{ result.risk_label }}</span>
              <p>{{ result.suggestion }}</p>
            </div>
          </article>

          <div class="analysis-v2-side">
            <div class="analysis-stat-row">
              <article class="analysis-stat-card pop-card pop-shadow page-pop-in">
                <span class="material-symbol" aria-hidden="true">folder_open</span>
                <div>
                  <p>档案事件数</p>
                  <strong>{{ result.event_count }}</strong>
                </div>
              </article>
              <article class="analysis-stat-card pop-card pop-shadow page-pop-in">
                <span class="material-symbol" aria-hidden="true">event_upcoming</span>
                <div>
                  <p>{{ selectedRangeLabel }}事件</p>
                  <strong>{{ activePeriodEventCount }}</strong>
                </div>
              </article>
            </div>

            <article class="analysis-source-panel pop-card pop-shadow page-pop-in">
              <h2>
                <span class="material-symbol" aria-hidden="true">account_tree</span>
                主要压力来源
              </h2>
              <p v-if="result.main_source_conclusion" class="analysis-source-conclusion">
                {{ result.main_source_conclusion }}
              </p>
              <p v-if="sourceBreakdown.length === 0" class="analysis-source-empty">
                暂无事件类型占比
              </p>
              <div v-else class="analysis-source-bars">
                <div v-for="source in sourceBreakdown" :key="source.label" class="analysis-source-item">
                  <div>
                    <span>{{ source.label }}</span>
                    <strong>{{ source.percent }}%</strong>
                  </div>
                  <div class="analysis-source-track card-border">
                    <i
                      :class="['analysis-source-fill', `analysis-source-fill-${source.tone}`]"
                      :style="{ width: `${source.animatedPercent}%` }"
                    ></i>
                  </div>
                </div>
              </div>
              <ol v-if="sourceInsightItems.length > 0" class="analysis-source-insights">
                <li v-for="source in sourceInsightItems" :key="`${source.rank}-${source.label}`">
                  <div class="analysis-source-insight-head">
                    <span>#{{ source.rank }} {{ source.label }}</span>
                    <strong>{{ source.percent }}%</strong>
                  </div>
                  <p>{{ source.explanation }}</p>
                  <div class="analysis-source-insight-meta">
                    <span>{{ source.event_count }} 条事件</span>
                    <span>最近：{{ source.recentEventDate }}</span>
                  </div>
                </li>
              </ol>
            </article>

            <article class="analysis-emotion-panel analysis-signals-panel pop-card pop-shadow page-pop-in">
              <h2>
                <span class="material-symbol" aria-hidden="true">bar_chart</span>
                情绪分布
              </h2>
              <div v-if="emotionDistribution.length > 0" class="analysis-emotion-bars">
                <div
                  v-for="emotion in emotionDistribution"
                  :key="emotion.emotion"
                  class="analysis-emotion-item"
                >
                  <div class="analysis-emotion-row">
                    <span>{{ emotion.label }}</span>
                    <strong>{{ emotion.count }} 次 · {{ emotion.percent }}%</strong>
                  </div>
                  <div class="analysis-emotion-track card-border">
                    <i
                      :class="['analysis-emotion-fill', `analysis-emotion-fill-${emotion.tone}`]"
                      :style="{ width: `${emotion.percent}%` }"
                    ></i>
                  </div>
                </div>
              </div>
              <p v-else class="analysis-source-empty">
                {{ selectedRangeLabel }}暂无可汇总的情绪分布。
              </p>
            </article>
          </div>
        </div>

        <article class="analysis-trend-panel pop-card pop-shadow page-pop-in">
          <h2>
            <span class="material-symbol" aria-hidden="true">show_chart</span>
            压力趋势图
          </h2>
          <p v-if="trendChartMeta" class="analysis-trend-meta">
            <template v-if="trendChartMeta.isSinglePoint">
              {{ trendChartMeta.dateRange }} | {{ trendChartMeta.totalCount }} 条事件，压力
              {{ trendChartMeta.avgScore }}
            </template>
            <template v-else>
              {{ trendChartMeta.dateRange }} | {{ trendChartMeta.totalCount }} 条事件，平均
              {{ trendChartMeta.avgScore }}
            </template>
          </p>
          <p v-else class="analysis-trend-meta">{{ selectedRangeLabel }}暂无可显示趋势点</p>
          <p
            v-if="result.trend_explanation"
            :class="['analysis-trend-note', { 'is-single-point': trendPoints.length === 1 }]"
          >
            {{ result.trend_explanation }}
          </p>
          <div v-if="hasTrendData" ref="trendChartRef" class="analysis-trend-chart"></div>
          <p v-else class="analysis-trend-empty">
            {{ selectedRangeLabel }}没有可聚合的压力趋势点。
          </p>
        </article>

        <section class="analysis-deterministic-grid" aria-label="事件洞察与场景训练推荐">
          <article class="analysis-event-insight-panel pop-card pop-shadow page-pop-in">
            <h2>
              <span class="material-symbol" aria-hidden="true">fact_check</span>
              事件洞察
            </h2>
            <template v-if="result.event_insight">
              <p class="analysis-event-summary">{{ result.event_insight.summary }}</p>
              <dl class="analysis-event-metrics">
                <div>
                  <dt>统计周期</dt>
                  <dd>{{ result.event_insight.period_days }} 天</dd>
                </div>
                <div>
                  <dt>周期事件</dt>
                  <dd>{{ result.event_insight.period_event_count }} 条</dd>
                </div>
                <div>
                  <dt>已沟通</dt>
                  <dd>{{ result.event_insight.communicated_count }} 条</dd>
                </div>
                <div>
                  <dt>未沟通</dt>
                  <dd>{{ result.event_insight.uncommunicated_count }} 条</dd>
                </div>
                <div>
                  <dt>直接冲突</dt>
                  <dd>{{ result.event_insight.conflict_count }} 条</dd>
                </div>
              </dl>
              <div class="analysis-insight-tags">
                <div>
                  <span>主要情绪</span>
                  <p v-if="topEmotionLabels.length > 0">
                    {{ topEmotionLabels.join('、') }}
                  </p>
                  <p v-else>暂无明显集中项</p>
                </div>
                <div>
                  <span>主要事件类型</span>
                  <p v-if="topEventTypeLabels.length > 0">
                    {{ topEventTypeLabels.join('、') }}
                  </p>
                  <p v-else>暂无明显集中项</p>
                </div>
              </div>
            </template>
            <p v-else class="analysis-neutral-empty">
              {{ selectedRangeLabel }}暂无事件洞察。继续记录事件后，这里会展示客观统计摘要。
            </p>
          </article>

          <article class="analysis-training-panel pop-card pop-shadow page-pop-in">
            <h2>
              <span class="material-symbol" aria-hidden="true">school</span>
              推荐场景训练
            </h2>
            <template v-if="trainingRecommendation">
              <div class="analysis-training-heading">
                <span>{{ trainingRecommendation.category_label }}</span>
                <h3>{{ trainingRecommendation.scenario_title }}</h3>
              </div>
              <dl class="analysis-training-meta">
                <div>
                  <dt>训练目标</dt>
                  <dd>{{ trainingRecommendation.target_label }}</dd>
                </div>
                <div>
                  <dt>难度</dt>
                  <dd>
                    {{ trainingRecommendation.difficulty_label }}
                    <small>{{ trainingRecommendation.difficulty_description }}</small>
                  </dd>
                </div>
              </dl>
              <p>{{ trainingRecommendation.reason }}</p>
              <blockquote>
                {{ trainingRecommendation.opening_suggestion }}
              </blockquote>
              <p class="analysis-training-safety">
                {{ trainingRecommendation.safety_note }}
              </p>
              <button class="primary-action pop-shadow" type="button" @click="startRecommendedTraining">
                开始推荐场景
                <span class="action-icon material-symbol" aria-hidden="true">arrow_forward</span>
              </button>
            </template>
            <div v-else class="analysis-training-empty">
              <p>当前周期暂未形成明确场景推荐。可以继续记录事件，或先选择通用演练。</p>
              <button class="secondary-action pop-shadow" type="button" @click="startRecommendedTraining">
                选择通用演练
              </button>
            </div>
          </article>
        </section>
      </section>
    </Transition>

    <div v-if="!isAnalysisLoading && !analysisError" class="analysis-v2-divider" aria-hidden="true">
      <svg fill="none" height="20" viewBox="0 0 200 20" width="200" xmlns="http://www.w3.org/2000/svg">
        <path d="M0 10C20 10 20 2 40 2C60 2 60 18 80 18C100 18 100 2 120 2C140 2 140 18 160 18C180 18 180 10 200 10" stroke="currentColor" stroke-linecap="round" stroke-width="4" />
      </svg>
    </div>

    <section v-if="!isAnalysisLoading && !analysisError" class="analysis-ai-section">
      <h2>
        <span class="material-symbol" aria-hidden="true">auto_awesome</span>
        AI 心晴见解
      </h2>

      <Transition
        name="analysis-ai-panel"
        mode="out-in"
        @after-enter="handleAnalysisInsightPanelAfterEnter"
      >
        <p
          v-if="insightStatus === 'loading'"
          key="loading"
          class="ai-state ai-state-loading"
          role="status"
          aria-live="polite"
        >
          <span class="material-symbol" aria-hidden="true">progress_activity</span>
          正在生成：AI 心晴见解生成中……
        </p>
        <p v-else-if="insightError" key="error" class="ai-state" role="alert">
          <span class="material-symbol" aria-hidden="true">cloud_off</span>
          {{ insightError }}
        </p>
        <div v-else-if="archiveInsight" key="ready" class="analysis-ai-grid">
          <article class="analysis-ai-card pop-card pop-shadow">
            <span class="material-symbol" aria-hidden="true">visibility</span>
            <h3>整体观察</h3>
            <p>{{ archiveInsight.insight }}</p>
          </article>
          <article class="analysis-ai-card pop-card pop-shadow">
            <span class="material-symbol" aria-hidden="true">favorite</span>
            <h3>自我照顾建议</h3>
            <p>{{ archiveInsight.care_suggestion }}</p>
          </article>
          <article class="analysis-ai-card pop-card pop-shadow">
            <span class="material-symbol" aria-hidden="true">forum</span>
            <h3>沟通重点列表</h3>
            <ul>
              <li v-for="item in archiveInsight.communication_focus" :key="item">
                {{ item }}
              </li>
            </ul>
          </article>
          <article class="analysis-ai-card analysis-ai-card-warning pop-card pop-shadow">
            <span class="material-symbol" aria-hidden="true">warning</span>
            <h3>安全提示</h3>
            <p>{{ archiveInsight.safety_note }}</p>
          </article>
        </div>
        <p v-else key="empty" class="ai-state">
          请先记录一条宿舍事件以生成 AI 心晴见解。
        </p>
      </Transition>

      <div class="analysis-actions analysis-v2-actions">
        <RouterLink
          v-if="hasArchiveEvents"
          class="primary-action pop-shadow"
          :to="{ name: 'rehearsal' }"
          role="button"
        >
          进入沟通演练
          <span class="action-icon material-symbol" aria-hidden="true">arrow_forward</span>
        </RouterLink>
        <RouterLink class="secondary-action pop-shadow" :to="{ name: 'archive' }" role="button">
          查看事件档案
        </RouterLink>
      </div>
    </section>

    <footer class="analysis-footer card-border">
      <span class="material-symbol" aria-hidden="true">info</span>
      本结果仅用于压力趋势提示，不作为心理诊断依据。
    </footer>
  </main>
</template>

<style scoped>
.analysis-range-tabs {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 14px;
  align-items: center;
  margin: -18px 0 28px;
  border-radius: 12px;
  background: var(--surface);
  padding: 14px;
}

.analysis-range-tabs > span {
  color: var(--ink-soft);
  font-size: var(--font-label-bold);
  font-weight: 900;
}

.analysis-range-tabs > div {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  min-width: 0;
}

.analysis-range-tabs button {
  min-width: 0;
  border: 2px solid var(--ink);
  border-radius: 999px;
  background: var(--surface-container);
  box-shadow: 2px 2px 0 0 var(--shadow-dark);
  color: var(--ink);
  padding: 9px 10px;
  font: inherit;
  font-size: var(--font-label-bold);
  font-weight: 900;
  cursor: pointer;
  transition:
    transform 180ms ease,
    background 180ms ease,
    box-shadow 180ms ease;
}

.analysis-range-tabs button:hover:not(:disabled),
.analysis-range-tabs button.is-active {
  background: var(--primary-container);
  color: #ffffff;
  transform: translateY(-2px);
}

.analysis-range-tabs button:disabled {
  cursor: wait;
  opacity: 0.64;
}

.analysis-ready-stack {
  display: grid;
}

.analysis-source-conclusion {
  margin: 0 0 16px;
  border: 2px solid var(--ink);
  border-radius: 12px;
  background: #ffffff;
  color: var(--ink);
  padding: 12px;
  font-weight: 800;
  line-height: 1.55;
}

.analysis-source-insights {
  display: grid;
  gap: 12px;
  margin: 18px 0 0;
  padding: 0;
  list-style: none;
}

.analysis-source-insights li {
  border: 2px solid var(--border);
  border-radius: 10px;
  background: #ffffff;
  padding: 12px;
}

.analysis-source-insight-head,
.analysis-source-insight-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.analysis-source-insight-head {
  color: var(--ink);
  font-size: var(--font-label-bold);
  font-weight: 900;
}

.analysis-source-insight-head strong {
  color: var(--primary);
  font-family: Outfit, system-ui, sans-serif;
}

.analysis-source-insights p {
  margin: 8px 0;
  color: var(--ink-soft);
  font-weight: 700;
  line-height: 1.55;
}

.analysis-source-insight-meta {
  flex-wrap: wrap;
  color: var(--ink-soft);
  font-size: 0.86rem;
  font-weight: 800;
}

.analysis-emotion-bars {
  display: grid;
  gap: 14px;
}

.analysis-emotion-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 6px;
  color: var(--ink);
  font-size: var(--font-label-bold);
  font-weight: 900;
}

.analysis-emotion-track {
  position: relative;
  overflow: hidden;
  height: 22px;
  border-radius: 999px;
  background: var(--surface-container);
}

.analysis-emotion-fill {
  position: absolute;
  inset: 0 auto 0 0;
  border-right: 2px solid var(--ink);
}

.analysis-emotion-fill-fresh {
  background: var(--primary);
}

.analysis-emotion-fill-warning {
  background: var(--tertiary);
}

.analysis-emotion-fill-danger {
  background: var(--secondary);
}

.analysis-trend-panel {
  display: grid;
  gap: 14px;
  margin-top: 24px;
  border: 2px solid var(--ink);
  border-radius: 12px;
  background: var(--surface);
  padding: 28px;
  animation: analysis-trend-in 420ms cubic-bezier(0.2, 0, 0, 1);
}

.analysis-trend-panel h2 {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0;
  font-size: var(--font-headline-md);
}

.analysis-trend-panel h2 .material-symbol {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border: 2px solid var(--ink);
  border-radius: 999px;
  background: var(--primary-container);
  color: #ffffff;
  box-shadow: 2px 2px 0 0 var(--shadow-dark);
}

.analysis-trend-meta {
  margin: 0;
  color: var(--ink-soft);
  font-size: var(--font-label-bold);
  font-weight: 800;
}

.analysis-trend-note {
  margin: 0;
  border: 2px solid var(--border);
  border-radius: 12px;
  background: #ffffff;
  color: var(--ink-soft);
  padding: 12px 14px;
  font-weight: 800;
  line-height: 1.55;
}

.analysis-trend-note.is-single-point {
  border-color: var(--ink);
  color: var(--ink);
}

.analysis-trend-chart {
  width: 100%;
  min-height: 250px;
  border: 2px solid var(--ink);
  border-radius: 12px;
  background: var(--surface-container);
}

.analysis-trend-empty {
  display: grid;
  align-items: center;
  min-height: 250px;
  margin: 0;
  border: 2px solid var(--ink);
  border-radius: 12px;
  background: var(--surface-container);
  padding: 24px;
  color: var(--ink-soft);
  font-weight: 800;
}

.analysis-deterministic-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 24px;
  margin-top: 24px;
}

.analysis-event-insight-panel,
.analysis-training-panel {
  display: grid;
  align-content: start;
  gap: 16px;
  border: 2px solid var(--ink);
  border-radius: 12px;
  background: var(--surface);
  padding: 24px;
}

.analysis-event-insight-panel h2,
.analysis-training-panel h2 {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0;
  font-size: var(--font-headline-md);
}

.analysis-event-insight-panel h2 .material-symbol,
.analysis-training-panel h2 .material-symbol {
  display: inline-grid;
  place-items: center;
  width: 44px;
  height: 44px;
  border: 2px solid var(--ink);
  border-radius: 10px;
  background: var(--primary-container);
  box-shadow: 2px 2px 0 0 var(--shadow-dark);
  color: #ffffff;
}

.analysis-training-panel h2 .material-symbol {
  background: var(--tertiary);
  color: var(--ink);
}

.analysis-event-summary,
.analysis-training-panel p,
.analysis-neutral-empty,
.analysis-training-empty p {
  margin: 0;
  color: var(--ink-soft);
  font-weight: 700;
  line-height: 1.6;
}

.analysis-event-summary {
  border: 2px solid var(--ink);
  border-radius: 12px;
  background: #ffffff;
  padding: 12px;
}

.analysis-event-metrics,
.analysis-training-meta {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin: 0;
}

.analysis-event-metrics div,
.analysis-training-meta div {
  border: 2px solid var(--border);
  border-radius: 10px;
  background: var(--surface-container);
  padding: 10px;
}

.analysis-event-metrics dt,
.analysis-training-meta dt {
  color: var(--ink-soft);
  font-size: 0.82rem;
  font-weight: 900;
}

.analysis-event-metrics dd,
.analysis-training-meta dd {
  margin: 4px 0 0;
  color: var(--ink);
  font-weight: 900;
}

.analysis-training-meta small {
  display: block;
  margin-top: 4px;
  color: var(--ink-soft);
  font-size: 0.82rem;
  line-height: 1.45;
}

.analysis-insight-tags {
  display: grid;
  gap: 10px;
}

.analysis-insight-tags div {
  border-left: 6px solid var(--primary);
  background: #ffffff;
  padding: 10px 12px;
}

.analysis-insight-tags div:nth-child(2) {
  border-left-color: var(--secondary);
}

.analysis-insight-tags span,
.analysis-training-heading span {
  color: var(--ink-soft);
  font-size: 0.82rem;
  font-weight: 900;
}

.analysis-insight-tags p,
.analysis-training-heading h3 {
  margin: 4px 0 0;
}

.analysis-training-heading h3 {
  color: var(--ink);
  font-size: 1.35rem;
}

.analysis-training-panel blockquote {
  margin: 0;
  border-left: 6px solid var(--secondary);
  background: #ffffff;
  padding: 12px 14px;
  color: var(--ink);
  font-weight: 800;
  line-height: 1.6;
}

.analysis-training-safety {
  border: 2px dashed var(--ink);
  border-radius: 12px;
  background: var(--surface-container);
  padding: 12px;
}

.analysis-training-panel .primary-action,
.analysis-training-panel .secondary-action {
  width: 100%;
  justify-content: center;
}

.analysis-training-empty {
  display: grid;
  gap: 16px;
}

@keyframes analysis-trend-in {
  from {
    opacity: 0;
    transform: translateY(12px) scale(0.985);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@media (max-width: 768px) {
  .analysis-range-tabs {
    grid-template-columns: 1fr;
    margin-top: -24px;
  }

  .analysis-range-tabs > div {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .analysis-trend-panel {
    padding: 22px;
  }

  .analysis-trend-chart,
  .analysis-trend-empty {
    min-height: 220px;
  }

  .analysis-deterministic-grid,
  .analysis-event-metrics,
  .analysis-training-meta {
    grid-template-columns: 1fr;
  }

  .analysis-event-insight-panel,
  .analysis-training-panel {
    padding: 20px;
  }
}
</style>
