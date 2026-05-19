# 弹窗引导增强 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add clearer modal guidance for locked AI roommate editing during simulations and add a reusable home feature-introduction carousel.

**Architecture:** Keep behavior local to the existing Vue views and reuse the global modal/button style language in `main.css`. Add one static verification script that checks the new UI markers and transitions because the frontend currently uses source verification scripts rather than a component test suite.

**Tech Stack:** Vue 3 `<script setup>`, Vite, TypeScript, existing CSS utilities and Material Symbols.

---

## File Structure

- Create `frontend/scripts/verify-modal-guidance.mjs`: source-level verification for the new modal states, text, controls, and CSS transitions.
- Modify `frontend/package.json`: add `verify:modal-guidance`.
- Modify `frontend/src/views/SimulationView.vue`: add roommate locked modal state, handlers, template, and keyboard handling.
- Modify `frontend/src/views/HomeView.vue`: add feature intro carousel data/state, modal lifecycle, focus handling, trigger button, and carousel controls.
- Modify `frontend/src/styles/main.css`: add reusable modal details for feature intro and simulation locked prompt, including transitions and responsive behavior.

## Task 1: Add Failing Verification

**Files:**
- Create: `frontend/scripts/verify-modal-guidance.mjs`
- Modify: `frontend/package.json`

- [ ] **Step 1: Write the failing verification script**

Create `frontend/scripts/verify-modal-guidance.mjs`:

```js
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

requireMatches('src/views/SimulationView.vue', [
  {
    label: 'locked add button opens guidance while max roommate limit remains disabled',
    pattern:
      /:disabled="roommates\.length >= 5 && !hasActiveConversation"[\s\S]*@click="openAddRoommate"/,
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
  'featureIntroIndex',
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
  'feature-intro-controls',
  'feature-intro-dots',
])

requireMatches('src/views/HomeView.vue', [
  {
    label: 'safety close queues feature intro after modal leave',
    pattern:
      /function closeSafetyModal\(\)[\s\S]*shouldOpenFeatureIntroAfterSafetyLeave\.value = true/,
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
])

requireIncludes('src/styles/main.css', [
  'feature-intro-modal',
  'feature-intro-slide-enter-active',
  'feature-intro-slide-leave-active',
  'feature-intro-controls',
  'feature-intro-arrow',
  'feature-intro-dots',
  'roommate-locked-modal',
  'roommate-locked-copy',
])

if (failures.length > 0) {
  console.error(`Modal guidance verification failed with ${failures.length} issue(s):`)

  for (const failure of failures) {
    console.error(`- ${failure}`)
  }

  process.exit(1)
}

console.log('Modal guidance verification passed.')
```

- [ ] **Step 2: Add the package script**

Add this entry to `frontend/package.json` scripts:

```json
"verify:modal-guidance": "node scripts/verify-modal-guidance.mjs"
```

- [ ] **Step 3: Run verification to confirm RED**

Run:

```bash
cd frontend && npm run verify:modal-guidance
```

Expected: FAIL with missing modal guidance markers.

## Task 2: Implement Simulation and Home Modals

**Files:**
- Modify: `frontend/src/views/SimulationView.vue`
- Modify: `frontend/src/views/HomeView.vue`
- Modify: `frontend/src/styles/main.css`

- [ ] **Step 1: Add simulation locked modal behavior**

In `SimulationView.vue`, add `showRoommateLockedModal`, open/close functions, and a keydown handler. Update `openAddRoommate()` and `openEditRoommate()` so active conversations open the modal instead of returning silently. Keep the max-roommate case disabled.

- [ ] **Step 2: Add simulation locked modal template**

Add a `Transition` near the existing roommate editor modal with the fixed message and only one primary button labeled `我知道了`.

- [ ] **Step 3: Add home feature intro carousel behavior**

In `HomeView.vue`, add `featureIntroSlides` with detailed point lists, modal refs/state, an initial-safety flag, computed current slide/points, open/close functions, previous/next carousel functions, focus handling, and a dedicated keydown handler.

- [ ] **Step 4: Chain the home intro after safety close**

Set `shouldOpenFeatureIntroAfterSafetyLeave.value = isInitialSafetyModal.value` in `closeSafetyModal()`, then clear `isInitialSafetyModal`. Manual `openSafetyModal()` must set `isInitialSafetyModal.value = false`. In `handleSafetyModalAfterLeave()`, keep the privacy branch first; then open feature intro if queued; only restore focus if no modal is opening.

- [ ] **Step 5: Add home feature intro trigger and modal template**

Add a `功能介绍` button next to `安全说明`. Add a modal with slide icon/title/text, point list, left/right arrow buttons, dots/page status, and a primary `我知道了` close button.

- [ ] **Step 6: Add CSS for the new UI**

Add styles near existing modal styles for feature intro and simulation locked prompt. Include hover, active, focus-visible, enter/leave transition, stable arrow dimensions, and mobile adjustments.

- [ ] **Step 7: Run verification to confirm GREEN**

Run:

```bash
cd frontend && npm run verify:modal-guidance
```

Expected: PASS.

- [ ] **Step 8: Run build**

Run:

```bash
cd frontend && npm run build
```

Expected: Type check and Vite build complete successfully.
