<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { gsap } from 'gsap'

const finePointerQuery = '(hover: hover) and (pointer: fine)'
const reducedMotionQuery = '(prefers-reduced-motion: reduce)'
const editableSelector = 'input, textarea, select'
const disabledSelector = ':disabled, [disabled], [aria-disabled="true"]'
const interactiveSelector =
  'a[href], button, summary, label, [role="button"], [role="link"], [tabindex]:not([tabindex="-1"])'

const cursorRef = ref<HTMLElement | null>(null)
const isEnabled = ref(false)
const isVisible = ref(false)
const isInteractive = ref(false)

let finePointerMedia: MediaQueryList | null = null
let reducedMotionMedia: MediaQueryList | null = null
let quickX: gsap.QuickToFunc | null = null
let quickY: gsap.QuickToFunc | null = null
let isTracking = false
let isUnmounted = false

watch(
  isEnabled,
  async (enabled) => {
    if (!enabled) {
      stopTracking()
      return
    }

    await nextTick()

    if (!isUnmounted && isEnabled.value) {
      startTracking()
    }
  },
  { flush: 'post' },
)

onMounted(() => {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return
  }

  finePointerMedia = window.matchMedia(finePointerQuery)
  reducedMotionMedia = window.matchMedia(reducedMotionQuery)
  finePointerMedia.addEventListener('change', syncCursorAvailability)
  reducedMotionMedia.addEventListener('change', syncCursorAvailability)
  syncCursorAvailability()
})

onBeforeUnmount(() => {
  isUnmounted = true
  finePointerMedia?.removeEventListener('change', syncCursorAvailability)
  reducedMotionMedia?.removeEventListener('change', syncCursorAvailability)
  stopTracking()
})

function syncCursorAvailability() {
  isEnabled.value = Boolean(finePointerMedia?.matches && !reducedMotionMedia?.matches)
}

function startTracking() {
  if (isTracking || !cursorRef.value) {
    return
  }

  const cursor = cursorRef.value
  gsap.set(cursor, {
    x: window.innerWidth / 2,
    y: window.innerHeight / 2,
    xPercent: -50,
    yPercent: -50,
  })

  quickX = gsap.quickTo(cursor, 'x', { duration: 0.22, ease: 'power3.out' })
  quickY = gsap.quickTo(cursor, 'y', { duration: 0.22, ease: 'power3.out' })

  window.addEventListener('pointermove', handlePointerMove, { passive: true })
  window.addEventListener('pointerover', handlePointerMove, { passive: true })
  window.addEventListener('blur', hideCursor)
  document.addEventListener('mouseleave', hideCursor)
  document.documentElement.classList.add('custom-cursor-ready')
  isTracking = true
}

function stopTracking() {
  if (isTracking) {
    window.removeEventListener('pointermove', handlePointerMove)
    window.removeEventListener('pointerover', handlePointerMove)
    window.removeEventListener('blur', hideCursor)
    document.removeEventListener('mouseleave', hideCursor)
  }

  quickX?.tween.kill()
  quickY?.tween.kill()
  quickX = null
  quickY = null
  isTracking = false
  isVisible.value = false
  isInteractive.value = false
  document.documentElement.classList.remove('custom-cursor-ready')
}

function handlePointerMove(event: PointerEvent) {
  if (event.pointerType === 'touch' || shouldHideForTarget(event.target)) {
    hideCursor()
    return
  }

  quickX?.(event.clientX)
  quickY?.(event.clientY)
  isVisible.value = true
  isInteractive.value = isInteractiveTarget(event.target)
}

function hideCursor() {
  isVisible.value = false
  isInteractive.value = false
}

function shouldHideForTarget(target: EventTarget | null) {
  const element = target instanceof Element ? target : null
  if (!element) {
    return false
  }

  const editable = element.closest(editableSelector)
  const contentEditable = element.closest('[contenteditable]')
  const isContentEditable =
    contentEditable !== null && contentEditable.getAttribute('contenteditable') !== 'false'

  return Boolean(editable || isContentEditable || element.closest(disabledSelector))
}

function isInteractiveTarget(target: EventTarget | null) {
  const element = target instanceof Element ? target : null
  return Boolean(element?.closest(interactiveSelector))
}
</script>

<template>
  <div
    v-if="isEnabled"
    ref="cursorRef"
    class="custom-cursor"
    :class="{
      'custom-cursor-visible': isVisible,
      'custom-cursor-interactive': isInteractive,
    }"
    style="pointer-events: none"
    aria-hidden="true"
  >
    <span class="custom-cursor-ring" />
    <span class="custom-cursor-dot" />
  </div>
</template>
