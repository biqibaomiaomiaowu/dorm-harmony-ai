import { readFileSync, existsSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDir = dirname(fileURLToPath(import.meta.url))
const root = dirname(scriptDir)

function read(path) {
  return readFileSync(join(root, path), 'utf8')
}

function assert(condition, message) {
  if (!condition) {
    throw new Error(message)
  }
}

const packageJson = JSON.parse(read('package.json'))
const requiredFiles = [
  'src/composables/useGsapMotion.ts',
  'src/components/CustomCursor.vue',
]

for (const path of requiredFiles) {
  assert(existsSync(join(root, path)), `Missing required motion file: ${path}`)
}

assert(packageJson.dependencies?.gsap, 'package.json must include gsap dependency')
assert(
  packageJson.scripts?.['verify:motion'] === 'node scripts/verify-gsap-motion.mjs',
  'package.json verify:motion must run node scripts/verify-gsap-motion.mjs',
)

const motion = read('src/composables/useGsapMotion.ts')
assert(motion.includes("from 'gsap'") || motion.includes('from "gsap"'), 'useGsapMotion must import gsap')
assert(motion.includes('gsap.context'), 'useGsapMotion must use gsap.context for scoped cleanup')
assert(motion.includes('prefers-reduced-motion'), 'useGsapMotion must handle prefers-reduced-motion')
assert(motion.includes('ScrollTrigger'), 'useGsapMotion must register or expose ScrollTrigger')
assert(motion.includes('quickTo'), 'useGsapMotion must expose quickTo support for cursor motion')

const app = read('src/App.vue')
assert(app.includes('CustomCursor'), 'App.vue must mount CustomCursor')
assert(app.includes('useGsapMotion'), 'App.vue must use shared GSAP motion helpers')

const home = read('src/views/HomeView.vue')
assert(!home.includes('homeMeterAnimationFrame'), 'HomeView should not use manual home meter animation frames')
assert(home.includes('animateNumber'), 'HomeView should use GSAP number tween helper')

const analysis = read('src/views/AnalysisView.vue')
assert(!analysis.includes('analysisAnimationFrame'), 'AnalysisView should not use manual analysis animation frames')
assert(analysis.includes('animateNumber'), 'AnalysisView should use GSAP number tween helper')

const review = read('src/views/ReviewView.vue')
assert(!review.includes('reviewScoresAnimationFrame'), 'ReviewView should not use manual review score animation frames')
assert(review.includes('animateNumber'), 'ReviewView should use GSAP number tween helper')

const archive = read('src/views/EventArchiveView.vue')
assert(!archive.includes(': Animation[]'), 'EventArchiveView should not track Web Animations API Animation[]')
assert(archive.includes('animateFlipReflow'), 'EventArchiveView should use GSAP FLIP-style reflow helper')

const simulation = read('src/views/SimulationView.vue')
assert(simulation.includes('animateListEnter'), 'SimulationView should use shared list/message enter animation')

const cursor = read('src/components/CustomCursor.vue')
assert(cursor.includes('quickTo'), 'CustomCursor must use gsap quickTo for pointer following')
assert(cursor.includes('(hover: hover) and (pointer: fine)'), 'CustomCursor must only enable on fine pointer hover devices')
assert(cursor.includes('prefers-reduced-motion'), 'CustomCursor must disable itself for reduced motion')
assert(cursor.includes('pointer-events: none'), 'CustomCursor must not intercept clicks')

console.log('GSAP motion verification passed')
