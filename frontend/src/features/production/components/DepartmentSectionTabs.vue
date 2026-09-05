<script setup lang="ts">
import { computed, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import DepartmentWorkersView from '../views/DepartmentWorkersView.vue'
import ProcedurePriceView from '../views/ProcedurePriceView.vue'
import ProductionPositionStorageView from '../views/ProductionPositionStorageView.vue'

const props = defineProps<{
  departmentCode: string
  workspaceLabel?: string
  additionalTabs?: ReadonlyArray<{ name: string; label: string }>
  showInventory?: boolean
  showWorkers?: boolean
  showProcedurePrices?: boolean
}>()
const emit = defineEmits<{
  configurationSaved: []
}>()

type DepartmentTab = string

const route = useRoute()
const router = useRouter()
let tabSwitchRevision = 0
const availableTabs = computed<DepartmentTab[]>(() => {
  const tabs: DepartmentTab[] = ['workspace']
  for (const tab of props.additionalTabs || []) tabs.push(tab.name)
  if (props.showInventory) tabs.push('inventory')
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
    <ElTabPane :label="workspaceLabel || '工作台'" name="workspace" lazy>
      <slot />
    </ElTabPane>

    <ElTabPane
      v-for="tab in additionalTabs || []"
      :key="tab.name"
      :label="tab.label"
      :name="tab.name"
      lazy
    >
      <slot :name="tab.name" />
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
      v-if="availableTabs.includes('inventory')"
      label="物料"
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
