<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getDepartmentModule } from '@/features/departments/registry'
import DepartmentWorkersView from '../views/DepartmentWorkersView.vue'
import DepartmentProductionProgressView from '../views/DepartmentProductionProgressView.vue'
import ProcedureTagPriceView from '../views/ProcedureTagPriceView.vue'
import DepartmentSurplusInventoryView from '../views/DepartmentSurplusInventoryView.vue'

const props = defineProps<{
  departmentCode: string
}>()
const emit = defineEmits<{
  configurationSaved: []
}>()

type DepartmentTab = 'workspace' | 'inventory' | 'workers' | 'progress' | 'tag-prices'

const route = useRoute()
const router = useRouter()
const department = computed(() => getDepartmentModule(props.departmentCode))
const availableTabs = computed<DepartmentTab[]>(() => {
  const tabs: DepartmentTab[] = ['workspace']
  const capabilities = department.value?.capabilities
  if (props.departmentCode === 'qc' || capabilities?.includes('repositories')) {
    tabs.push('inventory')
  }
  if (capabilities?.includes('production_progress')) tabs.push('progress')
  if (capabilities?.includes('standard_execution')) tabs.push('tag-prices')
  if (capabilities?.includes('workers')) tabs.push('workers')
  return tabs
})
const activeTab = computed<DepartmentTab>({
  get() {
    const requested = String(route.query.tab || 'workspace') as DepartmentTab
    return availableTabs.value.includes(requested) ? requested : 'workspace'
  },
  set(tab) {
    const query = { ...route.query }
    if (tab === 'workspace') delete query.tab
    else query.tab = tab
    void router.replace({ path: department.value?.routePath || route.path, query })
  },
})
</script>

<template>
  <ElTabs v-model="activeTab" class="department-section-tabs">
    <ElTabPane label="生产工作台" name="workspace" lazy>
      <slot />
    </ElTabPane>
    <ElTabPane
      v-if="availableTabs.includes('inventory')"
      label="库存"
      name="inventory"
      lazy
    >
      <DepartmentSurplusInventoryView :department-code="departmentCode" />
    </ElTabPane>
    <ElTabPane
      v-if="availableTabs.includes('progress')"
      label="查看生产进度"
      name="progress"
      lazy
    >
      <DepartmentProductionProgressView embedded :department-code="departmentCode" />
    </ElTabPane>
    <ElTabPane
      v-if="availableTabs.includes('tag-prices')"
      label="标记与单价配置"
      name="tag-prices"
      lazy
    >
      <ProcedureTagPriceView
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
  </ElTabs>
</template>

<style scoped>
.department-section-tabs :deep(.el-tabs__header) {
  margin-bottom: 14px;
}
</style>
