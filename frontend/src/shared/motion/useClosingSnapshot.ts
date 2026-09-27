import { computed, ref, shallowRef, toValue, watch, type MaybeRefOrGetter } from 'vue'

/** Preserve the last visible content only while the native overlay is leaving. */
export function useClosingSnapshot<T>(
  visible: MaybeRefOrGetter<boolean>,
  source: () => T,
  requestClose: () => void,
) {
  const closing = ref(false)
  const snapshot = shallowRef<T>()

  watch(() => toValue(visible), open => {
    if (open) {
      closing.value = false
      snapshot.value = source()
    }
  }, { immediate: true, flush: 'sync' })

  watch(source, value => {
    if (toValue(visible) && !closing.value) snapshot.value = value
  }, { immediate: true, flush: 'sync' })

  const display = computed(() => (
    (closing.value || !toValue(visible)) && snapshot.value !== undefined
      ? snapshot.value
      : source()
  ))

  function beginClose() {
    if (toValue(visible) && !closing.value) snapshot.value = source()
    closing.value = true
    // Element Plus normally updates v-model after `closed`; invalidate reads now.
    requestClose()
  }

  function finishClose() {
    if (toValue(visible)) return
    closing.value = false
    snapshot.value = undefined
  }

  return { display, closing, beginClose, finishClose }
}
