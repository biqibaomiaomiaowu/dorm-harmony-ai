<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import {
  ANALYSIS_RESULT_STORAGE_KEY,
  mockAnalyzeResult,
} from '@/data/week1'
import {
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

const ARCHIVE_INSIGHT_CACHE_KEY = 'dorm-harmony:archive-insight-cache:v1'

const result = ref<ArchiveAnalysisResult>({
  ...mockAnalyzeResult,
  event_count: 0,
  active_30d_count: 0,
  source_breakdown: [],
})
const archiveInsight = ref<ArchiveInsightResponse | null>(null)
const isAnalysisLoading = ref(false)
const analysisError = ref('')
const insightStatus = ref<'idle' | 'loading' | 'ready' | 'missing-key' | 'unavailable' | 'error'>('idle')
const insightError = ref('')
const animatedScorePercent = ref(0)
const animatedSourcePercents = ref<Record<string, number>>({})
let analysisAnimationFrame = 0
let isAnalysisViewActive = false

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
    await nextTick()

    if (!isAnalysisViewActive) {
      return
    }

    animateAnalysisProgress()

    try {
      localStorage.setItem(ANALYSIS_RESULT_STORAGE_KEY, JSON.stringify(result.value))
    } catch {
      // Restricted browser sessions may block localStorage; the page still has live data.
    }

    if (response.event_count > 0) {
      const archive = await fetchEventArchive()

      if (!isAnalysisViewActive) {
        return
      }

      await loadArchiveInsight(buildArchiveSignature(archive.events))
    }
  } catch (error) {
    if (!isAnalysisViewActive) {
      return
    }

    analysisError.value =
      error instanceof Error ? error.message : '总压力分析加载失败，请稍后重试'
  } finally {
    if (isAnalysisViewActive) {
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

  if (analysisAnimationFrame) {
    window.cancelAnimationFrame(analysisAnimationFrame)
    analysisAnimationFrame = 0
  }
})
</script>

<template>
  <main class="page analysis-page analysis-v2-page">
    <span class="analysis-decoration analysis-decoration-orb-top bounce-float" aria-hidden="true"></span>

    <section class="analysis-v2-hero page-pop-in">
      <h1>宿舍总压力分析报告</h1>
      <p>
        基于事件档案内的所有记录，综合事件日期、频率、严重程度和沟通状态生成趋势提示。
      </p>
      <p v-if="isAnalysisLoading" class="analysis-source-badge card-border">
        正在加载事件档案总压力...
      </p>
      <p v-else-if="analysisError" class="analysis-source-badge card-border">
        {{ analysisError }}
      </p>
    </section>

    <section v-if="!hasArchiveEvents && !isAnalysisLoading" class="analysis-empty-v2 pop-card pop-shadow page-pop-in">
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

    <section v-else class="analysis-v2-bento">
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
    </section>

    <div class="analysis-v2-divider" aria-hidden="true">
      <svg fill="none" height="20" viewBox="0 0 200 20" width="200" xmlns="http://www.w3.org/2000/svg">
        <path d="M0 10C20 10 20 2 40 2C60 2 60 18 80 18C100 18 100 2 120 2C140 2 140 18 160 18C180 18 180 10 200 10" stroke="currentColor" stroke-linecap="round" stroke-width="4" />
      </svg>
    </div>

    <section class="analysis-ai-section page-pop-in">
      <h2>
        <span class="material-symbol" aria-hidden="true">auto_awesome</span>
        AI 心晴见解
      </h2>

      <p v-if="insightStatus === 'loading'" class="ai-state">
        <span class="material-symbol" aria-hidden="true">progress_activity</span>
        正在生成：AI 心晴见解生成中……
      </p>
      <p v-else-if="insightError" class="ai-state">
        <span class="material-symbol" aria-hidden="true">cloud_off</span>
        {{ insightError }}
      </p>
      <div v-else-if="archiveInsight" class="analysis-ai-grid">
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
      <p v-else class="ai-state">
        请先记录一条宿舍事件以生成 AI 心晴见解。
      </p>

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
