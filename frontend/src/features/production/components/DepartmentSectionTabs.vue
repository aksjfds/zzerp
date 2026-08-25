<script setup lang="ts">
import { computed, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import DepartmentWorkersView from '../views/DepartmentWorkersView.vue'
import DepartmentProductionProgressView from '../views/DepartmentProductionProgressView.vue'
import ProcedurePriceView from '../views/ProcedurePriceView.vue'
import ProductionPositionStorageView from '../views/ProductionPositionStorageView.vue'

const props = defineProps<{
  departmentCode: string
  showInventory?: boolean
  showWorkers?: boolean
  showProgress?: boolean
  showProcedurePrices?: boolean
}>()
const emit = defineEmits<{
  configurationSaved: []
}>()

type DepartmentTab = 'workspace' | 'inventory' | 'workers' | 'progress' | 'tag-prices'

const route = useRoute()
const router = useRouter()
let tabSwitchRevision = 0
const availableTabs = computed<DepartmentTab[]>(() => {
  const tabs: DepartmentTab[] = ['workspace']
  if (props.showInventory) tabs.push('inventory')
  if (props.showProgress) tabs.push('progress')
  if (props.showProcedurePrices) tabs.push('tag-prices')
  if (props.showWorkers) tabs.push('workers')
  return tabs
})
const activeTab = computed<DepartmentTab>({
  get() {
    const requested = String(route.query.tab || 'workspace') as DepartmentTab
    return availableTabs.value.includes(requested) ? requested : 'workspace'
  },
  set(tab) {
    void switchTab(tab)
  },
})

async function switchTab(tab: DepartmentTab) {
  const currentTab = activeTab.value
  if (tab === currentTab) return
  const revision = ++tabSwitchRevision
  const scrollTop = window.scrollY
  const query = { ...route.query }
  if (tab === 'workspace') delete query.tab
  else query.tab = tab
  await router.replace({ path: route.path, query })
  await nextTick()
  window.requestAnimationFrame(() => {
    if (revision !== tabSwitchRevision) return
    window.scrollTo({
      top: scrollTop,
      behavior: 'auto',
    })
  })
}
</script>

<template>
  <ElTabs v-model="activeTab" class="department-section-tabs">
    <ElTabPane label="生产工作台" name="workspace" lazy>
      <slot />
    </ElTabPane>

    <ElTabPane
      v-if="availableTabs.includes('tag-prices')"
      label="工艺与单价配置"
      name="tag-prices"
      lazy
    >
      <ProcedurePriceView
        embedded
        :department-code="departmentCode"
        @saved="emit('configurationSaved')"
      />
    </ElTabPane>
    <ElTabPane
      v-if="availableTabs.includes('workers')"
      label="工人管理"
      name="workers"
      lazy
    >
      <DepartmentWorkersView embedded :department-code="departmentCode" />
    </ElTabPane>
    <ElTabPane
      v-if="availableTabs.includes('progress')"
      label="生产任务"
      name="progress"
      lazy
    >
      <DepartmentProductionProgressView embedded :department-code="departmentCode" />
    </ElTabPane>
    <ElTabPane
      v-if="availableTabs.includes('inventory')"
      label="物料入库"
      name="inventory"
      lazy
    >
      <ProductionPositionStorageView :department-code="departmentCode" />
    </ElTabPane>
  </ElTabs>
</template>

<style scoped>
.department-section-tabs :deep(.el-tabs__header) {
  margin-bottom: 14px;
}
</style>
