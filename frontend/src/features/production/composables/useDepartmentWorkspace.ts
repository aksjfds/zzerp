import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  queryDepartmentRepositories,
  queryDepartmentRepositoryWorkshops,
  queryDepartmentWorkers,
} from '../api/departmentRepositories'
import type { RepositoryWorkshop } from '../domain/repositories'
import type { RepositoryFilters, RepositoryItem, WorkerItem } from '../domain/types'

const EMPTY_FILTERS = (): RepositoryFilters => ({
  keyword: '', workshop_name: null, work_status: 'all',
})

export function useDepartmentWorkspace(
  departmentCode: string,
  loadWorkers = false,
  groupSourcesByProductionItem = false,
) {
  const loading = ref(false)
  const items = ref<RepositoryItem[]>([])
  const workers = ref<WorkerItem[]>([])
  const workshops = ref<RepositoryWorkshop[]>([])
  const filters = ref<RepositoryFilters>(EMPTY_FILTERS())
  const repositoryPage = ref(1)
  const repositoryTotal = ref(0)
  const selectedCardKey = ref<string | null>(null)
  const selectedProductionItemId = ref<number | null>(null)
  const pageSize = 50
  let repositorySequence = 0
  let repositoryController: AbortController | undefined

  const selectedRepository = computed(() => items.value.find(
    item => item.card_key === selectedCardKey.value,
  ))

  async function loadRepositories() {
    const sequence = ++repositorySequence
    const selectedBeforeLoad = items.value.find(
      item => item.card_key === selectedCardKey.value,
    )
    repositoryController?.abort()
    const controller = new AbortController()
    repositoryController = controller
    loading.value = true
    try {
      const query = (page: number) => queryDepartmentRepositories(departmentCode, {
        page,
        page_size: pageSize,
        ...filters.value,
      }, controller.signal)
      const requestedPage = repositoryPage.value
      let result = await query(requestedPage)
      if (sequence !== repositorySequence) return
      const lastPage = Math.max(1, Math.ceil(result.total / pageSize))
      if (requestedPage > lastPage) {
        result = await query(lastPage)
        if (sequence !== repositorySequence) return
        repositoryPage.value = lastPage
      }
      items.value = result.items
      repositoryTotal.value = result.total
      const selectedAfterLoad = items.value.find(
        item => item.card_key === selectedCardKey.value,
      ) || (selectedBeforeLoad && items.value.find(item => (
        item.production_item_id === selectedBeforeLoad.production_item_id
        && item.flow_node_id === selectedBeforeLoad.flow_node_id
        && (
          groupSourcesByProductionItem
          || item.source_flow_node_id === selectedBeforeLoad.source_flow_node_id
        )
      )))
      if (selectedAfterLoad) {
        selectedCardKey.value = selectedAfterLoad.card_key
        selectedProductionItemId.value = selectedAfterLoad.production_item_id
      } else if (selectedCardKey.value) {
        clearSelection()
      }
    } catch {
      if (sequence === repositorySequence && !controller.signal.aborted) {
        clearSelection()
        ElMessage.error('部门配件加载失败')
      }
    } finally {
      if (sequence === repositorySequence) {
        loading.value = false
        repositoryController = undefined
      }
    }
  }

  async function loadDepartmentWorkers() {
    if (!loadWorkers) return
    try { workers.value = await queryDepartmentWorkers(departmentCode) }
    catch { ElMessage.warning('工人列表加载失败') }
  }
  async function loadDepartmentWorkshops() {
    try {
      workshops.value = await queryDepartmentRepositoryWorkshops(departmentCode)
    } catch {
      workshops.value = []
      ElMessage.warning('车间列表加载失败')
    }
  }
  async function load() {
    await Promise.all([
      loadRepositories(),
      loadDepartmentWorkers(),
      loadDepartmentWorkshops(),
    ])
  }
  function clearSelection() {
    selectedCardKey.value = null
    selectedProductionItemId.value = null
  }
  function selectRepository(item: RepositoryItem) {
    selectedCardKey.value = item.card_key
    selectedProductionItemId.value = item.production_item_id
  }
  async function search(nextFilters: RepositoryFilters) {
    filters.value = { ...nextFilters }
    repositoryPage.value = 1
    clearSelection()
    await loadRepositories()
  }
  async function changePage(page: number) {
    repositoryPage.value = page
    clearSelection()
    await loadRepositories()
  }
  async function refresh() {
    repositoryPage.value = 1
    clearSelection()
    await loadRepositories()
  }

  return {
    changePage, filters, items, load, loadRepositories, loading, pageSize, refresh, repositoryPage,
    repositoryTotal, search, selectRepository, selectedCardKey, selectedProductionItemId,
    selectedRepository, workers, workshops,
  }
}
