import { onScopeDispose, ref } from 'vue'

export function useCompactViewport() {
  const query = window.matchMedia('(max-width: 600px)')
  const compact = ref(query.matches)
  const update = () => { compact.value = query.matches }
  query.addEventListener('change', update)
  onScopeDispose(() => query.removeEventListener('change', update))
  return compact
}
