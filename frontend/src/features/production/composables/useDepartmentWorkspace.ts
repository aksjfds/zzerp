import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { queryDepartmentRepositories, queryDepartmentWorkers } from '../api/repositories'
import type { RepositoryItem, WorkerItem } from '../domain/types'

export function useDepartmentWorkspace(departmentCode: string, loadWorkers = false) {
  const loading = ref(false)
  const items = ref<RepositoryItem[]>([])
  const workers = ref<WorkerItem[]>([])
  const repositoryPage = ref(1)
  const repositoryTotal = ref(0)
  const selectedRepositoryId = ref<number | null>(null)
  const selectedProductionItemId = ref<number | null>(null)
  const pageSize = 50
  let repositorySequence = 0

  const selectedRepository = computed(() => items.value.find(
    item => item.id === selectedRepositoryId.value,
  ))

  async function loadRepositories() {
    const sequence = ++repositorySequence
    loading.value = true
    try {
      const result = await queryDepartmentRepositories(departmentCode, repositoryPage.value, pageSize)
      if (sequence !== repositorySequence) return
      const lastPage = Math.max(1, Math.ceil(result.total / pageSize))
      if (repositoryPage.value > lastPage) {
        repositoryPage.value = lastPage
        await loadRepositories()
        return
      }
      items.value = result.items
      repositoryTotal.value = result.total
      if (!items.value.some(item => item.id === selectedRepositoryId.value)) {
        selectedRepositoryId.value = null
        selectedProductionItemId.value = null
      }
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

  async function load() {
    await Promise.all([loadRepositories(), loadDepartmentWorkers()])
  }
  async function refresh() {
    selectedRepositoryId.value = null
    selectedProductionItemId.value = null
    repositoryPage.value = 1
    await loadRepositories()
  }
  function selectRepository(item: RepositoryItem) {
    selectedRepositoryId.value = item.id
    selectedProductionItemId.value = item.production_item_id
  }

  return {
    items, load, loadRepositories, loading, pageSize, refresh, repositoryPage,
    repositoryTotal, selectRepository, selectedProductionItemId, selectedRepository,
    selectedRepositoryId, workers,
  }
}
