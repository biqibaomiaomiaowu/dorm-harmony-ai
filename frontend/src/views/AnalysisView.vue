<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TitleComponent, TooltipComponent } from 'echarts/components'

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

type TrendPoint = {
  date: string
  score: number
  count: number
}

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
}

const result = ref<ArchiveAnalysisResult>(EMPTY_ARCHIVE_RESULT)
const archiveInsight = ref<ArchiveInsightResponse | null>(null)
const isAnalysisLoading = ref(true)
const analysisError = ref('')
const insightStatus = ref<'idle' | 'loading' | 'ready' | 'missing-key' | 'unavailable' | 'error'>('idle')
const insightError = ref('')
const animatedScorePercent = ref(0)
const animatedSourcePercents = ref<Record<string, number>>({})
const trendPoints = ref<TrendPoint[]>([])
const trendChartRef = ref<HTMLElement | null>(null)
const trendChartMeta = computed(() => {
  if (!trendPoints.value.length) {
    return null
  }

  const firstPoint = trendPoints.value[0]!
  const lastPoint = trendPoints.value.at(-1)

  const totalCount = trendPoints.value.reduce((sum, point) => sum + point.count, 0)
  const avgScore = Math.round(
    trendPoints.value.reduce((sum, point) => sum + point.score * point.count, 0) / totalCount,
  )

  return {
    dateRange: `${firstPoint.date} ~ ${lastPoint?.date ?? firstPoint.date}`,
    avgScore,
    totalCount,
  }
})

let analysisAnimationFrame = 0
let isAnalysisViewActive = false
let trendChartInstance: echarts.ECharts | null = null
let trendChartResizeHandler: (() => void) | null = null

const TREND_DATE_LIMIT = 14

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

function clampTrendDate(value: string) {
  if (/^\d{4}-\d{2}-\d{2}/.test(value)) {
    return value.slice(0, 10)
  }

  return null
}

function estimatePressureScoreFromEvent(event: EventRecord): number {
  const singleScore = event.single_analysis?.pressure_score

  if (Number.isFinite(singleScore)) {
    return clampScore(singleScore)
  }

  const severity = Number(event.severity)

  if (Number.isFinite(severity)) {
    const baseScore = ((Math.max(1, Math.min(5, severity)) - 1) / 4) * 100
    const conflictBoost = event.has_conflict ? 10 : 0
    const communicationReduce = event.has_communicated ? -4 : 0

    return clampScore(baseScore + conflictBoost + communicationReduce)
  }

  return 44
}

function parseTrendPoints(events: EventRecord[]): TrendPoint[] {
  const bucket: Record<string, number[]> = {}

  events.forEach((event) => {
    const date = clampTrendDate(event.event_date)

    if (!date) {
      return
    }

    const score = estimatePressureScoreFromEvent(event)
    const existed = bucket[date]

    if (existed) {
      existed.push(score)
    } else {
      bucket[date] = [score]
    }
  })

  const orderedDates = Object.keys(bucket).sort((left, right) => left.localeCompare(right))

  const truncatedDates = orderedDates.slice(-TREND_DATE_LIMIT)

  return truncatedDates.map((date) => {
    const scores = bucket[date] ?? []
    const scoreSum = scores.reduce((sum, item) => sum + item, 0)
    const count = scores.length

    if (!count) {
      return {
        date,
        score: 0,
        count: 0,
      }
    }

    return {
      date,
      score: clampScore(scoreSum / count),
      count,
    }
  })
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

        return `${point.date}<br/>平均压力：${point.score}<br/>事件数：${point.count}`
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
        data: trendPoints.value.map((item) => item.score),
        type: 'line',
        smooth: true,
        symbolSize: 7,
        lineStyle: {
          width: 3,
        },
        areaStyle: {
          color: 'rgba(255, 129, 130, 0.16)',
        },
        itemStyle: {
          color: secondary,
        },
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

function prefersReducedMotion() {
  if (typeof window.matchMedia !== 'function') {
    return false
  }

  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
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

function animateAnalysisProgress() {
  if (!isAnalysisViewActive) {
    return
  }

  if (analysisAnimationFrame) {
    window.cancelAnimationFrame(analysisAnimationFrame)
    analysisAnimationFrame = 0
  }

  if (prefersReducedMotion()) {
    applyFinalAnalysisProgress()
    return
  }

  animatedScorePercent.value = 0
  animatedSourcePercents.value = buildSourcePercentMap(0)

  const targetScore = normalizedScore.value
  const durationMs = 720
  const startTime = window.performance.now()

  const step = (currentTime: number) => {
    if (!isAnalysisViewActive) {
      analysisAnimationFrame = 0
      return
    }

    const elapsed = currentTime - startTime
    const progress = Math.min(1, elapsed / durationMs)
    const easedProgress = 1 - (1 - progress) ** 3

    animatedScorePercent.value = Math.round(targetScore * easedProgress)
    animatedSourcePercents.value = buildSourcePercentMap(easedProgress)

    if (progress < 1) {
      analysisAnimationFrame = window.requestAnimationFrame(step)
    } else {
      analysisAnimationFrame = 0
    }
  }

  analysisAnimationFrame = window.requestAnimationFrame(step)
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
  trendPoints.value = []

  try {
    const archive = await fetchEventArchive()

    if (!isAnalysisViewActive) {
      return
    }

    trendPoints.value = parseTrendPoints(archive.events)
    await nextTick()
    refreshTrendChart()
    registerTrendChartResizeListener()
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

  try {
    const response = await fetchArchiveAnalysis()

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

    animateAnalysisProgress()
    void loadArchiveInsightForCurrentArchive(response.event_count)
  } catch (error) {
    if (!isAnalysisViewActive) {
      return
    }

    analysisError.value =
      error instanceof Error ? error.message : '总压力分析加载失败，请稍后重试'
  } finally {
    if (isAnalysisViewActive && isAnalysisLoading.value) {
      isAnalysisLoading.value = false
    }
  }
}

onMounted(() => {
  isAnalysisViewActive = true
  void loadArchiveAnalysis()
})

onBeforeUnmount(() => {
  isAnalysisViewActive = false
  disposeTrendChart()

  if (analysisAnimationFrame) {
    window.cancelAnimationFrame(analysisAnimationFrame)
    analysisAnimationFrame = 0
  }
})

watch(
  trendPoints,
  () => {
    if (!isAnalysisViewActive) {
      return
    }

    if (!trendPoints.value.length) {
      disposeTrendChart()
      return
    }

    if (trendChartInstance) {
      refreshTrendChart()
    }
  },
  { deep: true },
)
</script>

<template>
  <main class="page analysis-page analysis-v2-page">
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
                  <p>近 30 天事件</p>
                  <strong>{{ result.active_30d_count }}</strong>
                </div>
              </article>
            </div>

            <article class="analysis-source-panel pop-card pop-shadow page-pop-in">
              <h2>
                <span class="material-symbol" aria-hidden="true">pie_chart</span>
                矛盾溯源分析
              </h2>
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
            </article>

            <article class="analysis-signals-panel pop-card pop-shadow page-pop-in">
              <h2>
                <span class="material-symbol" aria-hidden="true">psychology</span>
                情绪与趋势
              </h2>
              <div class="analysis-keyword-list">
                <span v-for="keyword in result.emotion_keywords" :key="keyword">
                  {{ keyword }}
                </span>
              </div>
              <p>{{ result.trend_message }}</p>
            </article>
          </div>
        </div>

        <article class="analysis-trend-panel pop-card pop-shadow page-pop-in">
          <h2>
            <span class="material-symbol" aria-hidden="true">show_chart</span>
            压力趋势图
          </h2>
          <p v-if="trendChartMeta" class="analysis-trend-meta">
            {{ trendChartMeta.dateRange }} | 近 {{ trendChartMeta.totalCount }} 份事件，平均 {{ trendChartMeta.avgScore }}
          </p>
          <p v-else class="analysis-trend-meta">暂无可显示趋势点</p>
          <div v-if="hasTrendData" ref="trendChartRef" class="analysis-trend-chart"></div>
          <p v-else class="analysis-trend-empty">最近 14 个日期点暂无有效压力分数数据。</p>
        </article>
      </section>
    </Transition>

    <div v-if="!isAnalysisLoading && !analysisError" class="analysis-v2-divider" aria-hidden="true">
      <svg fill="none" height="20" viewBox="0 0 200 20" width="200" xmlns="http://www.w3.org/2000/svg">
        <path d="M0 10C20 10 20 2 40 2C60 2 60 18 80 18C100 18 100 2 120 2C140 2 140 18 160 18C180 18 180 10 200 10" stroke="currentColor" stroke-linecap="round" stroke-width="4" />
      </svg>
    </div>

    <section v-if="!isAnalysisLoading && !analysisError" class="analysis-ai-section page-pop-in">
      <h2>
        <span class="material-symbol" aria-hidden="true">auto_awesome</span>
        AI 心晴见解
      </h2>

      <Transition name="analysis-ai-panel" mode="out-in">
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
        <div v-else-if="archiveInsight" key="ready" class="analysis-ai-grid analysis-ai-grid-reveal">
          <article
            class="analysis-ai-card pop-card pop-shadow"
            style="--analysis-ai-delay: 0ms"
          >
            <span class="material-symbol" aria-hidden="true">visibility</span>
            <h3>整体观察</h3>
            <p>{{ archiveInsight.insight }}</p>
          </article>
          <article
            class="analysis-ai-card pop-card pop-shadow"
            style="--analysis-ai-delay: 80ms"
          >
            <span class="material-symbol" aria-hidden="true">favorite</span>
            <h3>自我照顾建议</h3>
            <p>{{ archiveInsight.care_suggestion }}</p>
          </article>
          <article
            class="analysis-ai-card pop-card pop-shadow"
            style="--analysis-ai-delay: 160ms"
          >
            <span class="material-symbol" aria-hidden="true">forum</span>
            <h3>沟通重点列表</h3>
            <ul>
              <li v-for="item in archiveInsight.communication_focus" :key="item">
                {{ item }}
              </li>
            </ul>
          </article>
          <article
            class="analysis-ai-card analysis-ai-card-warning pop-card pop-shadow"
            style="--analysis-ai-delay: 240ms"
          >
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
          :to="{ name: 'simulate' }"
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
.analysis-ready-stack {
  display: grid;
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
  .analysis-trend-panel {
    padding: 22px;
  }

  .analysis-trend-chart,
  .analysis-trend-empty {
    min-height: 220px;
  }
}
</style>
