import { existsSync, readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = dirname(dirname(fileURLToPath(import.meta.url)))
const failures = []

function read(relativePath) {
  const absolutePath = join(root, relativePath)
  if (!existsSync(absolutePath)) {
    failures.push(`Missing file: ${relativePath}`)
    return ''
  }

  return readFileSync(absolutePath, 'utf8')
}

function requireIncludes(relativePath, phrases) {
  const content = read(relativePath)

  for (const phrase of phrases) {
    if (!content.includes(phrase)) {
      failures.push(`${relativePath} is missing "${phrase}"`)
    }
  }
}

function requireExcludes(relativePath, phrases) {
  const content = read(relativePath)

  for (const phrase of phrases) {
    if (content.includes(phrase)) {
      failures.push(`${relativePath} should not include "${phrase}"`)
    }
  }
}

function requireNoMatches(relativePath, checks) {
  const content = read(relativePath)

  for (const { label, pattern } of checks) {
    if (pattern.test(content)) {
      failures.push(`${relativePath} should not match ${label}`)
    }
  }
}

function requireMatches(relativePath, checks) {
  const content = read(relativePath)

  for (const { label, pattern } of checks) {
    if (!pattern.test(content)) {
      failures.push(`${relativePath} should match ${label}`)
    }
  }
}

function requireReviewDialogueListModalContract() {
  const relativePath = 'src/views/ReviewView.vue'
  const content = read(relativePath)
  const modalStart = content.indexOf('<Transition name="review-dialogue-modal"')

  if (modalStart < 0) {
    failures.push(`${relativePath} is missing the review dialogue modal transition`)
    return
  }

  const beforeModal = content.slice(0, modalStart)
  if (/\breview-dialogue-list\b/.test(beforeModal)) {
    failures.push(`${relativePath} should not render the full dialogue list before the modal`)
  }

  const modalEnd = content.indexOf('</Transition>', modalStart)
  if (modalEnd < 0) {
    failures.push(`${relativePath} is missing the review dialogue modal closing transition`)
    return
  }

  const modalBlock = content.slice(modalStart, modalEnd)
  const classAttributePattern = /class\s*=\s*["']([^"']*)["']/g
  const hasModalDialogueList = Array.from(modalBlock.matchAll(classAttributePattern)).some(
    ([, classValue]) => {
      const classes = new Set(classValue.split(/\s+/).filter(Boolean))
      return classes.has('review-dialogue-list') && classes.has('review-dialogue-modal-list')
    },
  )

  if (!hasModalDialogueList) {
    failures.push(`${relativePath} should render the full dialogue list inside the modal`)
  }
}

requireIncludes('package.json', ['"verify:v2": "node scripts/verify-v2.mjs"'])

requireIncludes('src/router/index.ts', [
  '/archive',
  "name: 'archive'",
  'EventArchiveView.vue',
])

requireIncludes('src/views/HomeView.vue', [
  'fetchArchiveAnalysis',
  'animatedMeterPercent',
  'homeMeterWeatherIcon',
  'animateHomeMeter',
  'loadHomeMeterAnalysis',
  'requestAnimationFrame',
  'onBeforeUnmount',
  '--home-meter-percent',
  'homeMeterAnalysis.risk_label',
  'homeMeterAnalysis.value.pressure_score',
  'homeMeterAnalysis.trend_message',
  '<Transition name="weather-icon-flip" mode="out-in">',
  'const durationMs = 2200',
])
requireExcludes('src/styles/main.css', ['width: 68%;'])
requireMatches('src/views/HomeView.vue', [
  {
    label: 'home meter starts at zero before animating to target',
    pattern:
      /animatedMeterPercent\.value\s*=\s*0[\s\S]*?const targetPercent = normalizeHomeMeterScore[\s\S]*?requestAnimationFrame/,
  },
  {
    label: 'home meter fill uses animated CSS variable',
    pattern: /class="meter-fill"[\s\S]*--home-meter-percent[\s\S]*animatedMeterPercent/,
  },
  {
    label: 'home meter index displays animated value',
    pattern: /Index:\s*\{\{\s*animatedMeterPercent\s*\}\}\/100/,
  },
  {
    label: 'home meter loads archive analysis from backend before animating',
    pattern: /async function loadHomeMeterAnalysis[\s\S]*?await fetchArchiveAnalysis\(\)[\s\S]*?animateHomeMeter\(\)/,
  },
  {
    label: 'home weather icon is driven by animated pressure thresholds',
    pattern:
      /const homeMeterWeatherIcon = computed[\s\S]*?animatedMeterPercent\.value[\s\S]*?<= 30[\s\S]*?<= 60[\s\S]*?rainy/,
  },
])
requireIncludes('src/styles/main.css', [
  'weather-icon-flip-enter-active',
  'weather-icon-flip-leave-active',
  'rotateY',
])

requireIncludes('src/App.vue', ['事件档案', "name: 'archive'"])

requireIncludes('src/views/RecordView.vue', [
  'event_date',
  '事件日期',
  'createEventRecord',
  "description: ''",
  'const descriptionPlaceholder =',
  '例：',
  ':placeholder="descriptionPlaceholder"',
])
requireExcludes('src/views/RecordView.vue', ['placeholder="写下当时的具体情况..."'])

requireIncludes('src/views/EventArchiveView.vue', [
  '事件档案',
  'fetchEventArchive',
  '生成压力分析报告',
  "name: 'analysis'",
  'archiveGridRef',
  'data-event-id',
  'archiveStickerPresentation',
  'animateArchiveReflow',
  'onBeforeUnmount',
])
requireExcludes('src/views/EventArchiveView.vue', ['stickerTone(pageStartIndex + index)'])
requireMatches('src/views/EventArchiveView.vue', [
  {
    label: 'archive reflow animation uses before/after slot measurements',
    pattern:
      /collectArchiveSlotRects[\s\S]*?getBoundingClientRect[\s\S]*?animateArchiveReflow[\s\S]*?slot\.animate/,
  },
  {
    label: 'archive sticker presentation is keyed by event id rather than current index',
    pattern:
      /--sticker-rotate[\s\S]*?archiveStickerPresentation\(event\.id\)\.rotate[\s\S]*?--tape-rotate[\s\S]*?archiveStickerPresentation\(event\.id\)\.tapeRotate[\s\S]*?archiveStickerPresentation\(event\.id\)\.tone/,
  },
])

requireIncludes('src/data/eventArchive.ts', [
  '/api/events',
  '/api/events/analysis',
  '/api/events/insight',
  'ArchiveAnalysisResponse',
  'ArchiveInsightResponse',
  'source_breakdown',
  'communication_focus',
])

requireIncludes('src/styles/main.css', [
  'archive-page',
  'event-timeline',
  'archive-event-card',
  'page-pop-in',
  'sticker-paste-in',
  'bounce-float',
  'typing-bounce',
  'prefers-reduced-motion',
])

requireIncludes('src/views/AnalysisView.vue', [
  'fetchArchiveAnalysis',
  'fetchArchiveInsight',
  'source_breakdown',
  'animatedScorePercent',
  'animatedSourcePercents',
  'requestAnimationFrame',
  'isAnalysisViewActive',
  'typeof window.matchMedia !== \'function\'',
  "matchMedia('(prefers-reduced-motion: reduce)')",
  'AI 心晴见解',
  '事件档案',
])
requireExcludes('src/views/AnalysisView.vue', [
  'Math.floor(100 / labels.length)',
  '暂无来源',
  '<strong>{{ normalizedScore }}</strong>',
])
requireMatches('src/views/AnalysisView.vue', [
  {
    label: 'score core displays animatedScorePercent',
    pattern: /<strong>\s*\{\{\s*animatedScorePercent\s*\}\}\s*<\/strong>/,
  },
  {
    label: 'loadArchiveAnalysis exits before animating after unmount',
    pattern:
      /isAnalysisLoading\.value = false[\s\S]*?await nextTick\(\)[\s\S]*?if \(!isAnalysisViewActive\) \{[\s\S]*?return[\s\S]*?\}[\s\S]*?animateAnalysisProgress\(\)/,
  },
  {
    label: 'archive insight loads after analysis animation is started',
    pattern:
      /animateAnalysisProgress\(\)[\s\S]*?void loadArchiveInsightForCurrentArchive\(response\.event_count\)/,
  },
  {
    label: 'animation step stops when view is inactive',
    pattern:
      /const step = \(currentTime: number\) => \{[\s\S]*?if \(!isAnalysisViewActive\) \{[\s\S]*?return[\s\S]*?\}/,
  },
  {
    label: 'unmount cancels animation and marks inactive',
    pattern:
      /onBeforeUnmount\(\(\) => \{[\s\S]*?isAnalysisViewActive = false[\s\S]*?cancelAnimationFrame\(analysisAnimationFrame\)/,
  },
])
requireIncludes('src/views/AnalysisView.vue', [
  '<Transition name="analysis-ai-panel" mode="out-in">',
  'analysis-ai-grid-reveal',
  '--analysis-ai-delay',
  'ai-state-loading',
])
requireIncludes('src/styles/main.css', [
  'analysis-ai-panel-enter-active',
  'analysis-ai-panel-leave-active',
  'analysis-ai-card-reveal',
])

requireIncludes('src/views/SimulationView.vue', [
  'useSimulationSession',
  'conversationMessages',
  'const defaultSpeechPlaceholder =',
  ':placeholder="defaultSpeechPlaceholder"',
  '正在生成',
  'sessionErrorState',
  'retryFromExpiredSession',
  'resetConversation',
])
requireExcludes('src/views/SimulationView.vue', [
  'replies.value = result.replies',
  'const userMessage = ref(defaultSpeech)',
  'userMessage.value = defaultSpeech',
  'parsed.request.user_message || defaultSpeech',
  'submitSimulationRequest',
])
requireIncludes('src/composables/useSimulationSession.ts', [
  'submitSimulationStreamRequest',
  'SimulationStreamRequestError',
  "SimulationSessionErrorState = '' | 'expired'",
  'retryFromExpiredSession',
  'activeSimulationAbortController',
  'generationRunId',
])
requireMatches('src/composables/useSimulationSession.ts', [
  {
    label: 'simulation session submits through stream API helper',
    pattern: /await submitSimulationStreamRequest\(/,
  },
  {
    label: 'expired simulation sessions enter fixed error state',
    pattern:
      /function markExpiredSession[\s\S]*?sessionErrorState\.value = 'expired'[\s\S]*?if \(isExpiredSessionError\(error\)\) \{[\s\S]*?markExpiredSession\(/,
  },
])
requireNoMatches('src/views/SimulationView.vue', [
  {
    label: 'simulation view directly importing non-stream request helper',
    pattern: /import\s*\{[\s\S]*?submitSimulationRequest[\s\S]*?\}\s*from ['"]@\/data\/week1['"]/,
  },
])

requireIncludes('src/views/ReviewView.vue', [
  'fetchReviewHistory',
  'fetchReviewReport',
  'storedDialogue',
  'review-dialogue-entry-card',
  'dialogueTriggerRef',
  'openDialogueModal',
  'isDialogueModalOpen',
  'review-dialogue-modal',
  '查看完整对话',
  'performance_scores',
  'communicationPlanItems',
  '原话 vs 推荐话术',
  '沟通计划',
  'exportReviewMarkdown',
  'practiceAgain',
  'canShowReviewWorkspace',
  '<Transition name="review-result-transition" mode="out-in">',
  'review-result-stack',
  'review-card-reveal-item',
  '--review-card-delay',
  'animatedPerformanceScores',
  'animateReviewScores',
  'requestAnimationFrame',
  'onBeforeUnmount',
  'reviewResponse.value.performance_scores.clarity',
  'reviewResponse.value.performance_scores.empathy',
  'reviewResponse.value.performance_scores.resolution',
])
requireIncludes('src/styles/main.css', [
  'review-state-transition-enter-active',
  'review-result-transition-enter-active',
  'review-card-reveal',
])
requireMatches('src/views/ReviewView.vue', [
  {
    label: 'review score cards display animated values',
    pattern: /<strong>\s*\{\{\s*card\.animatedValue\s*\}\}%\s*<\/strong>/,
  },
  {
    label: 'review score animation starts from zero after response is available',
    pattern:
      /animatedPerformanceScores\.value\s*=\s*\{ clarity: 0, empathy: 0, resolution: 0 \}[\s\S]*?requestAnimationFrame/,
  },
  {
    label: 'live review response mounts result before score animation',
    pattern:
      /reviewResponse\.value = result[\s\S]*?isLoading\.value = false[\s\S]*?await nextTick\(\)[\s\S]*?animateReviewScores\(\)/,
  },
])
requireExcludes('src/views/ReviewView.vue', [
  'const scoreFallback',
  'rewriteSuggestion.instead }}',
  'reviewResponse.value.risks.length',
  'reviewResponse.value.strengths.length',
])
requireNoMatches('src/views/ReviewView.vue', [
  {
    label: 'latestUserMessage falling back to defaultRewriteSuggestion.instead',
    pattern:
      /const latestUserMessage = computed\(\(\) => \{[\s\S]*?defaultRewriteSuggestion\.instead[\s\S]*?\}\)/,
  },
  {
    label: 'fallback dialogue assigning speaker user without simulation cache',
    pattern: /if \(!dialogue\.length\) \{[\s\S]*?speaker:\s*['"]user['"]/,
  },
])
requireReviewDialogueListModalContract()

requireIncludes('src/data/week1.ts', [
  'ReviewPerformanceScores',
  'CommunicationPlan',
  'ReviewRequestError',
  'isReviewPerformanceScores',
  'isCommunicationPlan',
  'performance_scores:',
  'communication_plan:',
  'clarity',
  'empathy',
  'resolution',
])
requireMatches('src/data/week1.ts', [
  {
    label: 'ReviewResponsePayload keeps V3 optional fields compatible for legacy review responses',
    pattern:
      /Omit<[\s\S]*?ReviewResponse,[\s\S]*?'performance_scores'\s*\|\s*'communication_plan'\s*\|\s*'is_demo'\s*\|\s*'demo_notice'[\s\S]*?>[\s\S]*?Partial<[\s\S]*?Pick<ReviewResponse,\s*'performance_scores'\s*\|\s*'communication_plan'\s*\|\s*'is_demo'\s*\|\s*'demo_notice'>[\s\S]*?>/,
  },
  {
    label: 'isReviewResponsePayload allows missing V3 fields but validates present values',
    pattern:
      /typeof performanceScores === 'undefined'\s*\|\|\s*isReviewPerformanceScores\(performanceScores\)[\s\S]*?typeof communicationPlan === 'undefined'\s*\|\|\s*isCommunicationPlan\(communicationPlan\)/,
  },
  {
    label: 'stored review hydration normalizes legacy responses',
    pattern: /function isStoredReviewResult[\s\S]*?normalizeReviewResponse\(response/,
  },
  {
    label: 'normalizeReviewResponse preserves backend summary text',
    pattern:
      /function normalizeReviewResponse[\s\S]*?summary:\s*typeof raw\.summary === 'string'\s*\?\s*raw\.summary\s*:/,
  },
  {
    label: 'normalizeReviewResponse preserves backend strengths',
    pattern:
      /function normalizeReviewResponse[\s\S]*?strengths:\s*[\s\S]*?isStringArray\(raw\.strengths\)[\s\S]*?\?\s*raw\.strengths\s*:/,
  },
  {
    label: 'normalizeReviewResponse preserves backend risks',
    pattern:
      /function normalizeReviewResponse[\s\S]*?risks:\s*[\s\S]*?isStringArray\(raw\.risks\)[\s\S]*?\?\s*raw\.risks\s*:/,
  },
  {
    label: 'normalizeReviewResponse only falls back scores to demoReviewPerformanceScores',
    pattern:
      /function normalizeReviewResponse[\s\S]*?performance_scores:\s*isReviewPerformanceScores\(raw\.performance_scores\)\s*\?\s*raw\.performance_scores\s*:\s*\{\s*\.\.\.demoReviewPerformanceScores\s*\}/,
  },
  {
    label: 'normalizeReviewResponse normalizes missing communication_plan',
    pattern:
      /function normalizeReviewResponse[\s\S]*?communication_plan:\s*normalizeCommunicationPlan\(raw\.communication_plan,\s*rewrittenMessage\)/,
  },
  {
    label: 'normalizeReviewResponse preserves backend rewritten_message',
    pattern:
      /function normalizeReviewResponse[\s\S]*?const rewrittenMessage = normalizeRewrittenMessage\(raw\.rewritten_message[\s\S]*?rewritten_message:\s*rewrittenMessage/,
  },
  {
    label: 'normalizeReviewResponse preserves backend next_steps',
    pattern:
      /function normalizeReviewResponse[\s\S]*?next_steps:\s*[\s\S]*?isStringArray\(raw\.next_steps\)[\s\S]*?\?\s*raw\.next_steps\s*:/,
  },
  {
    label: 'normalizeReviewResponse preserves backend safety_note',
    pattern:
      /function normalizeReviewResponse[\s\S]*?safety_note:\s*[\s\S]*?typeof raw\.safety_note === 'string'\s*\?\s*raw\.safety_note\s*:/,
  },
  {
    label: 'submitReviewRequest rethrows client-state 400 errors instead of demo fallback',
    pattern:
      /if \(!response\.ok && response\.status === 400\) \{[\s\S]*?throw new ReviewRequestError[\s\S]*?if \(error instanceof ReviewRequestError\) \{[\s\S]*?throw error/,
  },
])

requireMatches('src/data/reviewHistory.ts', [
  {
    label: 'review history normalizes legacy original_event event_type aliases',
    pattern:
      /mapEventTypeToAnalyzeApi[\s\S]*?function normalizeReviewHistoryEventType[\s\S]*?mapEventTypeToAnalyzeApi/,
  },
])

requireIncludes('src/data/reviewHistory.ts', [
  '/api/reviews',
  'fetchReviewHistory',
  'fetchReviewReport',
  'deleteReviewReport',
  'ReviewReportSummary',
  'ReviewReportDetail',
  'normalizeReviewResponse',
])

requireMatches('src/views/ReviewView.vue', [
  {
    label: 'review page skips current report generation when there is no user dialogue',
    pattern:
      /function hasReviewableDialogue[\s\S]*?speaker === 'user'[\s\S]*?if \(!hasReviewableDialogue\(context\.dialogue\)\)/,
  },
  {
    label: 'review page can show history workspace without a current report',
    pattern:
      /const canShowReviewWorkspace = computed[\s\S]*?reviewHistory\.value\.length > 0[\s\S]*?v-if="canShowReviewWorkspace"/,
  },
  {
    label: 'review page uses Markdown export instead of PDF export',
    pattern:
      /function exportReviewMarkdown\(\)[\s\S]*?new Blob\(\[buildReviewMarkdown\(\)\],[\s\S]*?text\/markdown[\s\S]*?review-report-\$\{reviewFileStamp\(\)\}\.md/,
  },
  {
    label: 'review page restores roommate names from history detail',
    pattern:
      /function snapshotFromReportDetail[\s\S]*?roommateNames: detail\.request\.roommate_names/,
  },
  {
    label: 'review history is rendered as a horizontal strip',
    pattern:
      /class="review-history-strip[\s\S]*?\.review-workspace\s*\{[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1fr\)[\s\S]*?\.review-history-list\s*\{[\s\S]*?grid-auto-flow:\s*column[\s\S]*?overflow-x:\s*auto/,
  },
  {
    label: 'review history hides the persisted duplicate of the current report',
    pattern:
      /const visibleReviewHistory = computed<ReviewReportSummary\[\]>\(\(\) =>[\s\S]*?findCurrentReportDuplicateId[\s\S]*?reviewHistory\.value\.filter\(\(report\) => report\.id !== duplicateId\)[\s\S]*?v-for="report in visibleReviewHistory"/,
  },
  {
    label: 'review page deletes history through API and removes it from local state',
    pattern:
      /deleteReviewReport[\s\S]*?const deletingReviewIds = ref<Set<string>>[\s\S]*?const pendingDeleteReviewId = ref<string \| null>\(null\)[\s\S]*?async function deleteHistoryReport[\s\S]*?pendingDeleteReviewId\.value !== report\.id[\s\S]*?await deleteReviewReport\(report\.id\)[\s\S]*?reviewHistory\.value = reviewHistory\.value\.filter/,
  },
  {
    label: 'review page resets pending delete state after failed delete',
    pattern:
      /catch \(error\) \{\s*pendingDeleteReviewId\.value = null[\s\S]{0,240}?复盘历史删除失败/,
  },
  {
    label: 'review history deletion animates card removal and moves',
    pattern:
      /<TransitionGroup[\s\S]*?name="review-history-card"[\s\S]*?class="review-history-list"[\s\S]*?\.review-history-card-enter-active,[\s\S]*?\.review-history-card-leave-active,[\s\S]*?\.review-history-card-move[\s\S]*?transition:/,
  },
])
requireExcludes('src/views/ReviewView.vue', [
  'window.confirm',
  'exportReviewImage',
  '导出图片',
  'exportReviewPdf',
  '导出 PDF',
  'isExportingPdf',
  'application/pdf',
  'buildPdfWithJpeg',
])

requireIncludes('src/styles/main.css', [
  'analysis-source-fill',
  'transition: width',
])

if (failures.length > 0) {
  console.error('v2 verification failed:')
  for (const failure of failures) {
    console.error(`- ${failure}`)
  }
  process.exit(1)
}

console.log('v2 verification passed')
