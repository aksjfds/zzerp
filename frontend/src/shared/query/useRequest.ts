import { onScopeDispose, ref, shallowRef } from 'vue'
import { getApiErrorDetail } from '@/api/request'

/** Owns cancellation and stale responses, while the feature owns the request inputs. */
export function useRequest<T>(failureMessage: string) {
  const data = shallowRef<T>()
  const loading = ref(false)
  const error = ref('')
  let controller: AbortController | undefined
  let revision = 0
  let disposed = false

  function cancel() {
    revision += 1
    controller?.abort()
    controller = undefined
    loading.value = false
  }

  async function run(fetch: (signal: AbortSignal) => Promise<T>): Promise<T | undefined> {
    if (disposed) return undefined
    cancel()
    const current = revision
    const request = new AbortController()
    controller = request
    data.value = undefined
    loading.value = true
    error.value = ''
    try {
      const result = await fetch(request.signal)
      if (disposed || request.signal.aborted || current !== revision) return undefined
      data.value = result
      return result
    } catch (cause) {
      if (!disposed && !request.signal.aborted && current === revision) {
        error.value = getApiErrorDetail(cause)?.message || failureMessage
      }
      return undefined
    } finally {
      if (current === revision) {
        loading.value = false
        controller = undefined
      }
    }
  }

  onScopeDispose(() => { disposed = true; cancel() })
  return { data, loading, error, run, cancel }
}
