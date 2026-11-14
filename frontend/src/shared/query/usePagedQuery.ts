import { computed, onMounted, ref } from 'vue'
import { useRequest } from './useRequest'
import type { Page, PageRequest } from './types'

export function usePagedQuery<T>(
  fetch: (request: PageRequest) => Promise<Page<T>>,
  failureMessage: string,
  options: { pageSize?: number; immediate?: boolean } = {},
) {
  const pageSize = options.pageSize ?? 50
  const page = ref(1)
  const request = useRequest<Page<T>>(failureMessage)
  const data = computed(() => request.data.value?.data ?? [])
  const total = computed(() => request.data.value?.total ?? 0)

  function load() {
    return request.run(async signal => {
      const requestedPage = page.value
      let result = await fetch({ page: requestedPage, pageSize, signal })
      if (signal.aborted) return result
      const lastPage = Math.max(1, Math.ceil(result.total / pageSize))
      if (!result.data.length && requestedPage > lastPage) {
        page.value = lastPage
        result = await fetch({ page: lastPage, pageSize, signal })
      }
      return result
    })
  }

  function search() {
    page.value = 1
    return load()
  }

  onMounted(() => { if (options.immediate !== false) void load() })
  return { data, total, page, pageSize, loading: request.loading, error: request.error, load, search }
}
