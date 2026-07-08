import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { queryDepartmentRepositories, queryDepartmentWorkers } from '../api/repositories'
import type { RepositoryFilters, RepositoryItem, WorkerItem } from '../domain/types'

const EMPTY_FILTERS = (): RepositoryFilters => ({
  keyword: '', arrived_from: null, arrived_to: null, work_status: 'all',
})

function matches(item: RepositoryItem, filters: RepositoryFilters) {
  if (filters.work_status !== 'all' && item.work_status !== filters.work_status) return false
  const arrivedDate = item.arrived_at?.slice(0, 10)
  if (filters.arrived_from && (!arrivedDate || arrivedDate < filters.arrived_from)) return false
  if (filters.arrived_to && (!arrivedDate || arrivedDate > filters.arrived_to)) return false
  const value = filters.keyword.trim().toLowerCase()
  if (!value) return true
  const text = `${item.product_name} ${item.factory_code} ${item.part_name} ${item.part_no}`.toLowerCase()
  const tokens = value.replace(/装配体$/, '').replaceAll('-', ' ').split(/\s+/).filter(Boolean)
  return text.includes(value) || tokens.every(token => text.includes(token))
}

function filterAssemblyGroups(items: RepositoryItem[], filters: RepositoryFilters) {
  const groups = new Map<string, RepositoryItem[]>()
  items.forEach((item) => {
    const key = `${item.customer_order_item_id}:${item.flow_node_id}`
    groups.set(key, [...(groups.get(key) || []), item])
  })
  return [...groups.values()].filter((group) => {
    const status = group.some(item => item.work_status === 'processing')
      ? 'processing'
      : group.every(item => item.work_status === 'completed') ? 'completed' : 'unprocessed'
    const arrivedAt = group.map(item => item.arrived_at).filter(Boolean).sort().at(-1) || null
    const representative = {
      ...group[0],
      work_status: status,
      arrived_at: arrivedAt,
      part_name: group.map(item => item.part_name).join('-'),
      part_no: group.map(item => item.part_no).join(' '),
    } as RepositoryItem
    return matches(representative, filters)
  })
}

export function useDepartmentWorkspace(departmentCode: string, loadWorkers = false) {
  const loading = ref(false)
  const allItems = ref<RepositoryItem[]>([])
  const workers = ref<WorkerItem[]>([])
  const filters = ref<RepositoryFilters>(EMPTY_FILTERS())
  const repositoryPage = ref(1)
  const selectedCardKey = ref<string | null>(null)
  const selectedProductionItemId = ref<number | null>(null)
  const pageSize = 50
  let repositorySequence = 0

  const filteredGroups = computed(() => departmentCode === 'assembly'
    ? filterAssemblyGroups(allItems.value, filters.value)
    : [])
  const filteredItems = computed(() => departmentCode === 'assembly'
    ? filteredGroups.value.flat()
    : allItems.value.filter(item => matches(item, filters.value)))
  const repositoryTotal = computed(() => departmentCode === 'assembly'
    ? filteredGroups.value.length
    : filteredItems.value.length)
  const items = computed(() => {
    const start = (repositoryPage.value - 1) * pageSize
    return departmentCode === 'assembly'
      ? filteredGroups.value.slice(start, start + pageSize).flat()
      : filteredItems.value.slice(start, start + pageSize)
  })
  const selectedRepository = computed(() => allItems.value.find(
    item => item.card_key === selectedCardKey.value,
  ))

  async function loadRepositories() {
    const sequence = ++repositorySequence
    loading.value = true
    try {
      const result = await queryDepartmentRepositories(departmentCode)
      if (sequence !== repositorySequence) return
      allItems.value = result.items
      const lastPage = Math.max(1, Math.ceil(repositoryTotal.value / pageSize))
      repositoryPage.value = Math.min(repositoryPage.value, lastPage)
      if (!allItems.value.some(item => item.card_key === selectedCardKey.value)) clearSelection()
    } catch {
      if (sequence === repositorySequence) ElMessage.error('部门配件加载失败')
    } finally {
      if (sequence === repositorySequence) loading.value = false
    }
  }

  async function loadDepartmentWorkers() {
    if (!loadWorkers) return
    try { workers.value = await queryDepartmentWorkers(departmentCode) }
    catch { ElMessage.warning('工人列表加载失败') }
  }
  async function load() { await Promise.all([loadRepositories(), loadDepartmentWorkers()]) }
  function clearSelection() {
    selectedCardKey.value = null
    selectedProductionItemId.value = null
  }
  function selectRepository(item: RepositoryItem) {
    selectedCardKey.value = item.card_key
    selectedProductionItemId.value = item.production_item_id
  }
  function search(nextFilters: RepositoryFilters) {
    filters.value = { ...nextFilters }
    repositoryPage.value = 1
    clearSelection()
  }
  async function refresh() {
    repositoryPage.value = 1
    clearSelection()
    await loadRepositories()
  }

  return {
    filters, items, load, loadRepositories, loading, pageSize, refresh, repositoryPage,
    repositoryTotal, search, selectRepository, selectedCardKey, selectedProductionItemId,
    selectedRepository, workers,
  }
}
