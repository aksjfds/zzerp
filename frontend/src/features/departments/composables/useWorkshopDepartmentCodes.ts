import { readonly, ref } from 'vue'
import { queryWorkshopRoutes } from '@/api/organization'
import { getApiErrorDetail } from '@/api/request'

const workshopDepartmentCodes = ref<Record<number, string>>({})
const loading = ref(false)
const loadError = ref('')
let loaded = false
let loadingPromise: Promise<void> | null = null

async function loadWorkshopDepartmentCodes() {
  if (loaded) return
  if (!loadingPromise) {
    loading.value = true
    loadError.value = ''
    loadingPromise = queryWorkshopRoutes()
      .then((workshops) => {
        const codes: Record<number, string> = {}
        workshops.forEach((workshop) => {
          codes[workshop.id] = workshop.department_code
        })
        workshopDepartmentCodes.value = codes
        loaded = true
      })
      .catch((error) => {
        loadError.value = getApiErrorDetail(error)?.message || '车间信息加载失败'
      })
      .finally(() => {
        loading.value = false
        loadingPromise = null
      })
  }
  await loadingPromise
}

export function useWorkshopDepartmentCodes() {
  void loadWorkshopDepartmentCodes()
  return {
    workshopDepartmentCodes: readonly(workshopDepartmentCodes),
    workshopLoading: readonly(loading),
    workshopError: readonly(loadError),
    reloadWorkshops: loadWorkshopDepartmentCodes,
  }
}
