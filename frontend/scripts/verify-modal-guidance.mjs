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

function requireMatches(relativePath, checks) {
  const content = read(relativePath)

  for (const { label, pattern } of checks) {
    if (!pattern.test(content)) {
      failures.push(`${relativePath} should match ${label}`)
    }
  }
}

requireIncludes('package.json', ['"verify:modal-guidance": "node scripts/verify-modal-guidance.mjs"'])

requireIncludes('src/views/SimulationView.vue', [
  'showRoommateLockedModal',
  'openRoommateLockedModal',
  'closeRoommateLockedModal',
  'handleRoommateLockedKeydown',
  '对话模拟时不能使用舍友编辑和添加功能，请点击重置按钮后再编辑。',
  '我知道了',
  'roommate-locked-modal',
  'aria-disabled',
])
requireExcludes('src/views/SimulationView.vue', ['关闭添加/编辑提示'])

requireMatches('src/views/SimulationView.vue', [
  {
    label: 'locked add button opens guidance while max roommate limit remains disabled',
    pattern:
      /:disabled="roommates\.length >= 5 && !hasActiveConversation"[\s\S]*@click="openAddRoommate"/,
  },
  {
    label: 'add button exposes active conversation as aria-disabled',
    pattern:
      /class="roommate-add-btn pop-shadow"[\s\S]*:aria-disabled="hasActiveConversation"[\s\S]*@click="openAddRoommate"/,
  },
  {
    label: 'edit buttons stay clickable and expose aria-disabled during active conversation',
    pattern:
      /class="roommate-edit-btn"[\s\S]*:aria-disabled="!canEditRoommates"[\s\S]*@click="openEditRoommate\(index\)"/,
  },
])

requireIncludes('src/views/HomeView.vue', [
  'showFeatureIntroModal',
  'featureIntroSlides',
  'featureIntroPoints',
  'featureIntroIndex',
  'isInitialSafetyModal',
  'currentFeatureIntroSlide',
  'openFeatureIntroModal',
  'closeFeatureIntroModal',
  'showPreviousFeatureIntro',
  'showNextFeatureIntro',
  'handleFeatureIntroKeydown',
  'shouldOpenFeatureIntroAfterSafetyLeave',
  '功能介绍',
  'feature-intro-modal',
  'feature-intro-slide',
  'feature-intro-points',
  'feature-intro-controls',
  'feature-intro-dots',
  '当前情绪可多选',
  '主要情绪只选一个',
  '事件日期、发生频率、严重程度、是否已经沟通和主要情绪会影响压力评分',
  '自动读取事件档案',
  '自定义 AI 舍友',
  '模拟开始后不能编辑或新增 AI 舍友',
  '接入事件档案',
  'AI 舍友回复途中可以插话',
  '不会输出攻击性发言',
  '根据沟通模拟对话总结',
])

requireMatches('src/views/HomeView.vue', [
  {
    label: 'home report card maps to pressure analysis',
    pattern: /if \(action === '查看报告'\)[\s\S]*return 'analysis'/,
  },
  {
    label: 'safety close queues feature intro only for initial safety modal',
    pattern:
      /function closeSafetyModal\(\)[\s\S]*shouldOpenFeatureIntroAfterSafetyLeave\.value = isInitialSafetyModal\.value[\s\S]*isInitialSafetyModal\.value = false/,
  },
  {
    label: 'manual safety modal does not queue feature intro',
    pattern:
      /function openSafetyModal\(event\?: MouseEvent\)[\s\S]*isInitialSafetyModal\.value = false[\s\S]*showSafetyModal\.value = true/,
  },
  {
    label: 'initial safety modal marks feature intro chain eligible',
    pattern:
      /if \(!hasAcknowledgedSafetyModal\(\)\) \{[\s\S]*isInitialSafetyModal\.value = true[\s\S]*showSafetyModal\.value = true/,
  },
  {
    label: 'safety after leave opens feature intro before restoring focus',
    pattern:
      /function handleSafetyModalAfterLeave\(\)[\s\S]*shouldOpenFeatureIntroAfterSafetyLeave\.value[\s\S]*showFeatureIntroModal\.value = true/,
  },
  {
    label: 'home actions include safety and feature intro buttons',
    pattern:
      /<button class="secondary-action" type="button" @click="openSafetyModal">安全说明<\/button>[\s\S]*@click="openFeatureIntroModal"/,
  },
  {
    label: 'feature intro overlay closes on backdrop click',
    pattern:
      /v-if="showFeatureIntroModal"[\s\S]*class="safety-modal-overlay"[\s\S]*@click\.self="closeFeatureIntroModal"/,
  },
  {
    label: 'feature intro carousel controls avoid tab roles',
    pattern:
      /aria-label="上一个功能介绍"[\s\S]*class="feature-intro-dots" aria-label="功能介绍步骤"[\s\S]*:aria-current="index === featureIntroIndex \? 'step' : undefined"[\s\S]*aria-label="下一个功能介绍"/,
  },
])

requireExcludes('src/views/HomeView.vue', ['role="tablist"', 'role="tab"'])

requireIncludes('src/styles/main.css', [
  'feature-intro-modal',
  'feature-intro-slide-enter-active',
  'feature-intro-slide-leave-active',
  'feature-intro-points',
  'feature-intro-controls',
  'feature-intro-arrow',
  'feature-intro-dots',
  'roommate-locked-modal',
  'roommate-locked-copy',
  ".roommate-add-btn[aria-disabled='true']",
])

if (failures.length > 0) {
  console.error(`Modal guidance verification failed with ${failures.length} issue(s):`)

  for (const failure of failures) {
    console.error(`- ${failure}`)
  }

  process.exit(1)
}

console.log('Modal guidance verification passed.')
