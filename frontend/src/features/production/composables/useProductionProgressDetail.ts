import { onScopeDispose, ref, toValue, watch, type MaybeRefOrGetter } from 'vue'
import { getApiErrorDetail } from '@/api/request'
import { queryProductionProgressItemDetail } from '../api/productionProgress'
import type {
  DepartmentProductionProgressItem,
  ProductionProgressItemDetail,
} from '../domain/productionProgress'

export function useProductionProgressDetail(
  visible: MaybeRefOrGetter<boolean>,
  departmentCode: MaybeRefOrGetter<string>,
  item: MaybeRefOrGetter<DepartmentProductionProgressItem | null>,
) {
  const loading = ref(false)
  const loadError = ref('')
  const detail = ref<ProductionProgressItemDetail | null>(null)
  let requestRevision = 0

  async function load() {
    const revision = ++requestRevision
    const currentItem = toValue(item)
    const currentDepartmentCode = toValue(departmentCode)
    loadError.value = ''
    detail.value = null
    if (!toValue(visible) || !currentItem || !currentDepartmentCode) {
      loading.value = false
      return
    }
    loading.value = true
    try {
      const result = await queryProductionProgressItemDetail(
        currentDepartmentCode,
        currentItem.production_plan_item_id,
        currentItem.processing_workshop_id,
        currentItem.flow_node_id,
      )
      if (revision === requestRevision) detail.value = result
    } catch (error) {
      if (revision === requestRevision) {
        loadError.value = getApiErrorDetail(error)?.message || '生产情况加载失败'
      }
    } finally {
      if (revision === requestRevision) loading.value = false
    }
  }

  watch(
    () => [
      toValue(visible),
      toValue(departmentCode),
      toValue(item)?.production_plan_item_id,
      toValue(item)?.processing_workshop_id,
      toValue(item)?.flow_node_id,
    ] as const,
    ([open]) => {
      if (open) void load()
      else {
        requestRevision += 1
        loading.value = false
        loadError.value = ''
        detail.value = null
      }
    },
    { immediate: true },
  )

  onScopeDispose(() => { requestRevision += 1 })

  return { detail, loading, loadError, reload: load }
}
