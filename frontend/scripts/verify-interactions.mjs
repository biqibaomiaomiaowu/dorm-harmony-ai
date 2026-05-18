import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const root = resolve(__dirname, '..')

function read(path) {
  return readFileSync(resolve(root, path), 'utf8')
}

const files = {
  app: read('src/App.vue'),
  styles: read('src/styles/main.css'),
  home: read('src/views/HomeView.vue'),
  analysis: read('src/views/AnalysisView.vue'),
  archive: read('src/views/EventArchiveView.vue'),
  record: read('src/views/RecordView.vue'),
  simulation: read('src/views/SimulationView.vue'),
}

const checks = [
  ['home safety modal uses modal transition', files.home.includes('name="modal-fade"')],
  ['analysis main states use transition', files.analysis.includes('name="analysis-main-state"')],
  ['analysis page starts in loading state', files.analysis.includes('const isAnalysisLoading = ref(true)')],
  ['app keeps default router view without route transition', !files.app.includes('route-view')],
  ['archive content states use transition', files.archive.includes('name="archive-content-state"')],
  ['archive page starts in loading state', files.archive.includes('const isLoading = ref(true)')],
  ['modal focus restore waits for leave', files.home.includes('@after-leave="handleSafetyModalAfterLeave"')],
  ['simulation chat state uses transition', files.simulation.includes('name="chat-state"')],
  [
    'simulation messages use TransitionGroup',
    /<TransitionGroup[\s\S]*?name="chat-message"/.test(files.simulation),
  ],
  ['scenario buttons expose pressed state', files.simulation.includes(':aria-pressed="scene === currentScene"')],
  ['record submit shows spinner while submitting', files.record.includes('action-spinner')],
  ['archive delete button changes confirming icon', files.archive.includes("confirmingDeleteId === event.id ? 'check' : 'close'")],
  [
    'global actions define focus-visible styles',
    /\.primary-action:focus-visible,\s*\.secondary-action:focus-visible,\s*\.dark-action:focus-visible/s.test(
      files.styles,
    ),
  ],
  [
    'global actions define disabled styles',
    /\.primary-action:disabled,\s*\.secondary-action:disabled,\s*\.dark-action:disabled/s.test(
      files.styles,
    ),
  ],
  ['modal fade transition styles exist', files.styles.includes('.modal-fade-enter-active')],
  ['analysis main transition styles exist', files.styles.includes('.analysis-main-state-enter-active')],
  ['archive content transition styles exist', files.styles.includes('.archive-content-state-enter-active')],
  ['chat state transition styles exist', files.styles.includes('.chat-state-enter-active')],
  ['chat message transition styles exist', files.styles.includes('.chat-message-enter-active')],
  ['mobile badges have focus-visible styles', files.styles.includes('.mobile-badge:focus-visible')],
  ['feature CTA has focus-visible styles', files.styles.includes('.feature-action:focus-visible')],
  ['home feature cards have interactive motion', files.styles.includes('.feature-card-visual:hover')],
  [
    'review risk cards have interactive motion',
    files.styles.includes('.review-sticker-card.review-sticker-risk:hover'),
  ],
  ['review risk cards do not expose unreachable focus-within motion', !files.styles.includes('.review-sticker-risk:focus-within')],
  ['roommate cards have interactive motion', files.styles.includes('.roommate-card:hover')],
  ['roommate cards use consistent container styling', !files.simulation.includes('roommate-active')],
  ['scene buttons have focus-visible styles', files.styles.includes('.scene-btn:focus-visible')],
]

const failures = checks.filter(([, passed]) => !passed)

if (failures.length > 0) {
  console.error('Interaction verification failed:')
  for (const [label] of failures) {
    console.error(`- ${label}`)
  }
  process.exit(1)
}

console.log(`Interaction verification passed: ${checks.length}/${checks.length} checks`)
