import { readonly, ref } from 'vue'
import { queryWorkshopRoutes } from '@/api/organization'

const workshopDepartmentCodes = ref<Record<number, string>>({})
let loadingPromise: Promise<void> | null = null

async function loadWorkshopDepartmentCodes() {
  if (Object.keys(workshopDepartmentCodes.value).length) return
  if (!loadingPromise) {
    loadingPromise = queryWorkshopRoutes()
      .then((workshops) => {
        const codes: Record<number, string> = {}
        workshops.forEach((workshop) => {
          codes[workshop.id] = workshop.department_code
        })
        workshopDepartmentCodes.value = codes
      })
      .catch(() => {
        workshopDepartmentCodes.value = {}
      })
      .finally(() => {
        loadingPromise = null
      })
  }
  await loadingPromise
}

export function useWorkshopDepartmentCodes() {
  void loadWorkshopDepartmentCodes()
  return {
    workshopDepartmentCodes: readonly(workshopDepartmentCodes),
  }
}
