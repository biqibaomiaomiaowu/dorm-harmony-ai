import { existsSync, readFileSync, statSync } from 'node:fs'
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

function requireRegex(relativePath, pattern, description) {
  const content = read(relativePath)

  if (!pattern.test(content)) {
    failures.push(`${relativePath} is missing ${description}`)
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

function requireCssRuleIncludes(relativePath, selector, declarations) {
  const content = read(relativePath)
  const rule = content.match(new RegExp(`${selector.replaceAll('.', '\\.')}\\s*\\{([^}]*)\\}`))

  if (!rule) {
    failures.push(`${relativePath} is missing ${selector} rule`)
    return
  }

  const ruleDeclarations = rule[1]
    .split(';')
    .map((declaration) => declaration.trim())
    .filter(Boolean)

  for (const declaration of declarations) {
    if (!ruleDeclarations.includes(declaration)) {
      failures.push(`${relativePath} ${selector} rule is missing "${declaration}"`)
    }
  }
}

function requireCssRuleExcludes(relativePath, selector, declarations) {
  const content = read(relativePath)
  const rule = content.match(new RegExp(`${selector.replaceAll('.', '\\.')}\\s*\\{([^}]*)\\}`))

  if (!rule) {
    failures.push(`${relativePath} is missing ${selector} rule`)
    return
  }

  const ruleDeclarations = rule[1]
    .split(';')
    .map((declaration) => declaration.trim())
    .filter(Boolean)

  for (const declaration of declarations) {
    if (ruleDeclarations.includes(declaration)) {
      failures.push(`${relativePath} ${selector} rule should not include "${declaration}"`)
    }
  }
}

function requireNonEmptyFile(relativePath) {
  const absolutePath = join(root, relativePath)

  if (!existsSync(absolutePath)) {
    failures.push(`Missing file: ${relativePath}`)
    return
  }

  if (statSync(absolutePath).size <= 0) {
    failures.push(`${relativePath} is empty`)
  }
}

function requireNoMarkdownFormatArtifacts(relativePath) {
  const content = read(relativePath)

  if (content.includes('\\n')) {
    failures.push(`${relativePath} should not include literal escaped newline markers`)
  }

  if (content.includes('\r')) {
    failures.push(`${relativePath} should use LF line endings`)
  }
}

requireIncludes('package.json', ['"verify:phase3": "node scripts/verify-phase3.mjs"'])

requireIncludes('vite.config.ts', [
  'server:',
  'proxy:',
  "'/api'",
  'http://127.0.0.1:8000',
  'changeOrigin: true',
])

requireIncludes('src/data/week1.ts', [
  '/api/analyze',
  '/api/simulate',
  '/api/simulate/stream',
  '/api/review',
  'submitSimulationStreamRequest',
  'SimulationStreamEvent',
])

requireIncludes('src/router/index.ts', [
  '/',
  '/record',
  '/analysis',
  '/simulate',
  '/review',
  "name: 'home'",
  "name: 'record'",
  "name: 'analysis'",
  "name: 'simulate'",
  "name: 'review'",
  'HomeView',
  'RecordView',
  'AnalysisView',
  'SimulationView',
  'ReviewView',
])

// A3 flow hardening markers
requireRegex(
  'src/App.vue',
  /const navItems = \[[\s\S]*name:\s*'home'[\s\S]*name:\s*'record'[\s\S]*name:\s*'analysis'[\s\S]*name:\s*'simulate'[\s\S]*name:\s*'review'/,
  'Navigation order: home -> record -> analysis -> simulate -> review',
)
requireRegex(
  'src/App.vue',
  /<nav class="mobile-nav[^"]*"[\s\S]*v-for="item in navItems"[\s\S]*<\/nav>/,
  'Mobile nav uses navItems for five-core flow',
)
requireIncludes('src/App.vue', ['首页', '事件记录', '压力分析', '沟通模拟', '沟通复盘'])
requireExcludes('src/App.vue', ['futureItems', 'AI 沙盒'])

requireRegex(
  'src/views/RecordView.vue',
  /const description = form\.description\.trim\(\)[\s\S]*if\s*\(\s*!description\s*\)\s*{[\s\S]*submitError\.value/,
  'Record empty description guard before submission',
)

requireRegex(
  'src/views/RecordView.vue',
  /submitError\.value\s*=\s*['"][^'"]*(简要描述|描述)[^'"]*['"]/,
  'Record empty description user message',
)

requireRegex(
  'src/views/HomeView.vue',
  /if \(action === '开启分析'\)[\s\S]*return 'record'/,
  'Home action "开启分析" maps to record',
)
requireRegex(
  'src/views/HomeView.vue',
  /if \(action === '进入沙盒'\)[\s\S]*return 'simulate'/,
  'Home action "进入沙盒" maps to simulate',
)
requireRegex(
  'src/views/HomeView.vue',
  /if \(action === '查看报告'\)[\s\S]*return 'analysis'/,
  'Home action "查看报告" maps to analysis',
)

requireRegex(
  'src/views/AnalysisView.vue',
  /RouterLink[\s\S]*name:\s*'simulate'[\s\S]*进入沟通演练/,
  'Analysis action linking to simulation',
)
requireIncludes('src/views/AnalysisView.vue', ['scoreRingCircumference', 'scoreRingStyle'])
requireIncludes('src/styles/main.css', ['--score-ring-dashoffset'])
requireRegex('src/styles/main.css', /score-ring-fill[\s\S]*--score-ring-dashoffset/, 'Score ring style uses dynamic CSS variable')

requireIncludes('src/views/SimulationView.vue', [
  'SIMULATION_RESULT_STORAGE_KEY',
  'localStorage.setItem',
  'submitSimulationStreamRequest',
  'chat-message-list',
  'const hasUserMessage = computed',
  'chat-user-empty',
])
requireRegex(
  'src/views/SimulationView.vue',
  /<article\s+class="chat-user"\s+:class="\{ 'chat-user-empty': !hasUserMessage \}">/,
  'user chat row stays a layout row instead of nesting a white chat bubble around the purple bubble',
)
requireIncludes('src/views/SimulationView.vue', [
  'savedAnalysisSources',
  'savedAnalysisEmotionKeywords',
  'savedAnalysisTrend',
  'savedAnalysisSuggestion',
  'savedAnalysisScore',
  '压力分数：',
  '压力来源：',
  '情绪关键词：',
  '趋势提示：',
  '建议：',
])
requireRegex(
  'src/views/SimulationView.vue',
  /if\s*\(\s*!message\s*\)\s*{[\s\S]*submitError\.value\s*=\s*['"][^'"]*输入[^'"]*['"]/,
  'Simulation empty input prompt before submit',
)
requireRegex(
  'src/views/SimulationView.vue',
  /submitSimulationStreamRequest\(request/,
  'Simulation streaming-first request path',
)
requireIncludes('src/views/SimulationView.vue', ['const canEnterReview = computed', 'v-if="canEnterReview"', 'reviewGateMessage'])
requireRegex(
  'src/views/SimulationView.vue',
  /const canEnterReview = computed\(\(\) => hasUsableSimulation\.value && replies\.value\.length > 0\)/,
  'Simulation review gating computed state',
)

requireIncludes('src/views/ReviewView.vue', [
  'ANALYSIS_RESULT_STORAGE_KEY',
  'SIMULATION_RESULT_STORAGE_KEY',
  'REVIEW_RESULT_STORAGE_KEY',
  'localStorage.getItem',
  'localStorage.setItem',
])
requireRegex(
  'src/views/ReviewView.vue',
  /localStorage\.getItem\(ANALYSIS_RESULT_STORAGE_KEY\)[\s\S]*localStorage\.getItem\(SIMULATION_RESULT_STORAGE_KEY\)/,
  'Review using analysis + simulation cache before request',
)
requireRegex(
  'src/views/ReviewView.vue',
  /localStorage\.setItem\(\s*REVIEW_RESULT_STORAGE_KEY/,
  'Review persists generated result cache',
)

// Responsive markers
requireRegex('src/styles/main.css', /@media \(max-width: 1024px\)/, '1024px responsive media query')
requireRegex('src/styles/main.css', /@media \(max-width: 720px\)/, '720px responsive media query')

requireCssRuleIncludes('src/styles/main.css', '.mobile-nav', ['position: fixed'])
requireRegex(
  'src/styles/main.css',
  /@media \(max-width: 1024px\)[\s\S]*\.mobile-nav[\s\S]*display:\s*grid/,
  'mobile nav using grid in responsive breakpoint',
)

requireRegex(
  'src/styles/main.css',
  /@media \(max-width: 720px\)[\s\S]*\.simulation-layout[\s\S]*grid-template-columns:\s*1fr/,
  'simulation grid collapses in compact layout',
)
requireRegex(
  'src/styles/main.css',
  /@media \(max-width: 720px\)[\s\S]*\.review-score-grid[\s\S]*grid-template-columns:\s*1fr/,
  'review score grid collapses in compact layout',
)
requireRegex(
  'src/styles/main.css',
  /@media \(max-width: 720px\)[\s\S]*\.review-section-grid[\s\S]*grid-template-columns:\s*1fr/,
  'review section grid collapses in compact layout',
)
requireRegex(
  'src/styles/main.css',
  /@media \(max-width: 720px\)[\s\S]*\.speech-rewrite-row[\s\S]*grid-template-columns:\s*1fr/,
  'review rewrite row collapses in compact layout',
)
requireRegex(
  'src/styles/main.css',
  /@media \(max-width: 720px\)[\s\S]*\.simulation-input-bar[\s\S]*align-items:\s*stretch/,
  'simulation input bar keeps compact layout at mobile width',
)

// Chat bubble containment markers
requireCssRuleIncludes('src/styles/main.css', '.chat-hint', ['padding: 12px 16px'])
requireCssRuleIncludes('src/styles/main.css', '.chat-footer-note', ['padding: 12px 16px'])
requireCssRuleIncludes('src/styles/main.css', '.chat-user', [
  'display: flex',
  'align-items: flex-start',
  'gap: 10px',
  'width: min(80%, 760px)',
  'max-width: 100%',
  'min-width: 0',
])
requireCssRuleExcludes('src/styles/main.css', '.chat-user', [
  'padding: 10px 16px 18px 58px',
])
requireCssRuleIncludes('src/styles/main.css', '.chat-user-empty', [
  'width: fit-content',
])
requireCssRuleExcludes('src/styles/main.css', '.chat-bubble-user', ['margin-top: -12px'])
requireCssRuleIncludes('src/styles/main.css', '.chat-bubble-user', [
  'flex: 1 1 auto',
  'min-width: 0',
  'max-width: 100%',
  'overflow-wrap: anywhere',
  'word-break: break-word',
  'white-space: normal',
])
requireCssRuleIncludes('src/styles/main.css', '.chat-user-empty .chat-bubble-user', [
  'flex: 0 1 auto',
  'min-width: 3em',
])

// Final gate: phase-3 demo documentation
const requiredFiles = [
  {
    path: 'docs/demo/phase3-frontend-fix-log.md',
    phrases: [
      'A3-1',
      'A3-2',
      '导航顺序',
      '首页入口',
      '记录页空描述',
      '动态压力环',
      '模拟复盘门禁',
      '后端不可用演示兜底',
    ],
  },
  {
    path: 'docs/demo/phase3-responsive-check.md',
    phrases: ['A3-3', '移动底部导航', '表单选项', '聊天气泡', '复盘报告', '无横向溢出'],
  },
  {
    path: 'docs/demo/phase3-screenshot-materials.md',
    phrases: [
      'A3-4',
      '截图素材',
      'home.png',
      'record.png',
      'analysis.png',
      'simulate.png',
      'review.png',
      '首页',
      '事件记录',
      '压力分析',
      '沟通模拟',
      '沟通复盘',
    ],
  },
  {
    path: 'docs/demo/phase3-demo-runbook.md',
    phrases: [
      'A3-5',
      '夜间噪音冲突',
      'home -> record -> analysis -> simulate -> review',
      '可无后端兜底',
      '录制视频',
    ],
  },
]

for (const file of requiredFiles) {
  requireIncludes(file.path, file.phrases)
}

for (const screenshot of [
  'docs/demo/screenshots/home.png',
  'docs/demo/screenshots/record.png',
  'docs/demo/screenshots/analysis.png',
  'docs/demo/screenshots/simulate.png',
  'docs/demo/screenshots/review.png',
]) {
  requireNonEmptyFile(screenshot)
}

for (const markdownFile of [
  'docs/demo/phase3-frontend-fix-log.md',
  'docs/demo/phase3-responsive-check.md',
  'docs/demo/phase3-screenshot-materials.md',
  'docs/demo/phase3-demo-runbook.md',
]) {
  requireNoMarkdownFormatArtifacts(markdownFile)
}

if (failures.length > 0) {
  console.error('Phase 3 verification failed:')
  for (const failure of failures) {
    console.error(`- ${failure}`)
  }
  process.exit(1)
}

console.log('Phase 3 verification passed.')
