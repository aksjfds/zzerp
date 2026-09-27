import { onMounted, onScopeDispose, ref } from 'vue'
import { erpMotion } from './tokens'

/** Decorative animations never own content visibility or business timing. */
export function useMotion() {
  const preference = window.matchMedia('(prefers-reduced-motion: reduce)')
  const reducedMotion = ref(preference.matches)
  const animations = new Map<HTMLElement, Animation>()

  function cancelAll() {
    animations.forEach(animation => animation.cancel())
    animations.clear()
  }

  function finishAll() {
    // Every reveal ends at the element's ordinary, fully readable CSS state.
    animations.forEach(animation => {
      animation.finish()
      animation.cancel()
    })
    animations.clear()
  }

  function play(
    element: HTMLElement,
    keyframes: Keyframe[],
    options: KeyframeAnimationOptions = {},
  ): Animation | undefined {
    animations.get(element)?.cancel()
    animations.delete(element)
    if (
      reducedMotion.value
      || document.hidden
      || !element.isConnected
      || !element.getClientRects().length
    ) return

    const animation = element.animate(keyframes, {
      duration: erpMotion.duration.content,
      easing: erpMotion.easing.enter,
      fill: 'both',
      ...options,
    })
    animations.set(element, animation)
    void animation.finished.then(() => {
      if (animations.get(element) !== animation) return
      animations.delete(element)
      animation.cancel()
    }).catch(() => {
      // Cancellation is expected when new data or user input interrupts a reveal.
      if (animations.get(element) === animation) animations.delete(element)
    })
    return animation
  }

  function updatePreference() {
    reducedMotion.value = preference.matches
    if (reducedMotion.value) finishAll()
  }

  function finishWhenHidden() {
    if (document.hidden) finishAll()
  }

  onMounted(() => {
    preference.addEventListener('change', updatePreference)
    document.addEventListener('visibilitychange', finishWhenHidden)
  })
  onScopeDispose(() => {
    cancelAll()
    preference.removeEventListener('change', updatePreference)
    document.removeEventListener('visibilitychange', finishWhenHidden)
  })

  return { play, finishAll, cancelAll, reducedMotion }
}
