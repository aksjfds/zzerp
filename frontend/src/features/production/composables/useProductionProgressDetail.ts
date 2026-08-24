import { ref, toValue, watch, type MaybeRefOrGetter } from 'vue'
import { ElMessage } from 'element-plus'
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
  const detail = ref<ProductionProgressItemDetail | null>(null)
  let requestRevision = 0

  async function load() {
    const currentItem = toValue(item)
    const currentDepartmentCode = toValue(departmentCode)
    if (!currentItem || !currentDepartmentCode) return
    const revision = ++requestRevision
    loading.value = true
    detail.value = null
    try {
      const result = await queryProductionProgressItemDetail(
        currentDepartmentCode,
        currentItem.production_plan_item_id,
        currentItem.processing_workshop,
        currentItem.flow_node_id,
      )
      if (revision === requestRevision) detail.value = result
    } catch (error) {
      if (revision === requestRevision) {
        ElMessage.error(getApiErrorDetail(error)?.message || '生产情况加载失败')
      }
    } finally {
      if (revision === requestRevision) loading.value = false
    }
  }

  watch(
    () => [
      toValue(visible),
      toValue(item)?.production_plan_item_id,
      toValue(item)?.processing_workshop,
      toValue(item)?.flow_node_id,
    ] as const,
    ([open]) => {
      if (open) void load()
      else {
        requestRevision += 1
        loading.value = false
        detail.value = null
      }
    },
  )

  return { detail, loading, reload: load }
}
