import { onBeforeUnmount } from 'vue'
import { gsap } from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'

gsap.registerPlugin(ScrollTrigger)

type MaybeElement = Element | null | undefined

type MotionTarget = MaybeElement | MaybeElement[] | NodeListOf<Element> | Element[]
type MotionContext = gsap.Context & { data?: unknown[] }

interface NumberTweenOptions {
  from?: number
  to: number
  duration?: number
  onUpdate: (value: number) => void
  round?: boolean
}

function isReducedMotion() {
  return (
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  )
}

function toElements(targets: MotionTarget) {
  if (!targets) {
    return []
  }

  if (targets instanceof Element) {
    return [targets]
  }

  return Array.from(targets).filter((target): target is Element => target instanceof Element)
}

export function prefersReducedMotion() {
  return isReducedMotion()
}

export function useGsapMotion(scope?: () => MaybeElement) {
  const contexts = new Set<MotionContext>()
  let isDisposed = false

  function withContext(callback: () => void) {
    if (isDisposed) {
      return null
    }

    pruneCompletedContexts()

    const root = scope?.() ?? undefined
    const context = gsap.context(callback, root ?? undefined) as MotionContext
    if (isDisposed) {
      context.revert()
      return null
    }

    contexts.add(context)
    trackContextForPruning(context)
    pruneCompletedContexts()

    return context
  }

  function contextAnimations(context: MotionContext) {
    return (context.data ?? []).filter(
      (item): item is gsap.core.Animation => item instanceof gsap.core.Animation,
    )
  }

  function isAnimationComplete(animation: gsap.core.Animation) {
    return !animation.isActive() && animation.totalProgress() >= 1
  }

  function pruneCompletedContexts() {
    contexts.forEach((context) => {
      if (context.isReverted) {
        contexts.delete(context)
        return
      }

      const animations = contextAnimations(context)
      if (animations.length > 0 && !animations.every(isAnimationComplete)) {
        return
      }

      context.clear()
      contexts.delete(context)
    })
  }

  function scheduleContextPrune() {
    globalThis.setTimeout(() => {
      if (!isDisposed) {
        pruneCompletedContexts()
      }
    }, 0)
  }

  function trackContextForPruning(context: MotionContext) {
    const animations = contextAnimations(context)
    if (!animations.length) {
      scheduleContextPrune()
      return
    }

    animations.forEach((animation) => {
      const onComplete = animation.eventCallback('onComplete')
      const onInterrupt = animation.eventCallback('onInterrupt')

      animation.eventCallback('onComplete', function (this: gsap.core.Animation) {
        onComplete?.call(this)
        scheduleContextPrune()
      })
      animation.eventCallback('onInterrupt', function (this: gsap.core.Animation) {
        onInterrupt?.call(this)
        scheduleContextPrune()
      })
    })
  }

  function animatePageIn(targets: MotionTarget) {
    const elements = toElements(targets)
    if (!elements.length) {
      return
    }

    if (isReducedMotion()) {
      gsap.set(elements, {
        autoAlpha: 1,
        y: 0,
        scale: 1,
        clearProps: 'transform,opacity,visibility',
      })
      return
    }

    gsap.fromTo(
      elements,
      { autoAlpha: 0, y: 18, scale: 0.985 },
      {
        autoAlpha: 1,
        y: 0,
        scale: 1,
        duration: 0.48,
        ease: 'power3.out',
        stagger: 0.07,
        clearProps: 'transform,opacity,visibility',
      },
    )
  }

  function animateListEnter(targets: MotionTarget) {
    const elements = toElements(targets)
    if (!elements.length) {
      return
    }

    if (isReducedMotion()) {
      gsap.set(elements, {
        autoAlpha: 1,
        x: 0,
        y: 0,
        scale: 1,
        clearProps: 'transform,opacity,visibility',
      })
      return
    }

    gsap.fromTo(
      elements,
      { autoAlpha: 0, y: 14, scale: 0.98 },
      {
        autoAlpha: 1,
        y: 0,
        scale: 1,
        duration: 0.38,
        ease: 'power3.out',
        stagger: 0.055,
        clearProps: 'transform,opacity,visibility',
      },
    )
  }

  function animateNumber(options: NumberTweenOptions) {
    const start = options.from ?? 0
    const state = { value: start }

    if (isReducedMotion()) {
      options.onUpdate(options.round === false ? options.to : Math.round(options.to))
      return gsap.set(state, { value: options.to })
    }

    return gsap.to(state, {
      value: options.to,
      duration: options.duration ?? 0.72,
      ease: 'power3.out',
      onUpdate: () => {
        options.onUpdate(options.round === false ? state.value : Math.round(state.value))
      },
    })
  }

  function animateFlipReflow(previousRects: Map<string, DOMRect>, container: MaybeElement) {
    if (!container || isReducedMotion()) {
      return
    }

    const slots = container.querySelectorAll<HTMLElement>('[data-event-id]')
    const moved: Array<{ slot: HTMLElement; x: number; y: number }> = []

    slots.forEach((slot) => {
      const eventId = slot.dataset.eventId
      const previous = eventId ? previousRects.get(eventId) : undefined
      if (!previous) {
        return
      }

      const current = slot.getBoundingClientRect()
      const x = previous.left - current.left
      const y = previous.top - current.top
      if (Math.abs(x) < 0.5 && Math.abs(y) < 0.5) {
        return
      }

      moved.push({ slot, x, y })
    })

    if (!moved.length) {
      return
    }

    moved.forEach(({ slot, x, y }) => {
      gsap.set(slot, { x, y, autoAlpha: 0.92 })
    })

    gsap.to(
      moved.map(({ slot }) => slot),
      {
        x: 0,
        y: 0,
        autoAlpha: 1,
        duration: 0.52,
        ease: 'power3.out',
        stagger: 0.06,
        clearProps: 'transform,opacity,visibility',
      },
    )
  }

  function makeQuickTo(target: Element, property: 'x' | 'y', duration = 0.26) {
    return gsap.quickTo(target, property, { duration, ease: 'power3.out' })
  }

  onBeforeUnmount(() => {
    isDisposed = true
    contexts.forEach((context) => context.revert())
    contexts.clear()
  })

  return {
    gsap,
    ScrollTrigger,
    withContext,
    animatePageIn,
    animateListEnter,
    animateNumber,
    animateFlipReflow,
    makeQuickTo,
    prefersReducedMotion,
  }
}
