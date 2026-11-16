<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { queryProductionDepartments, type ProductionDepartment } from '@/features/production-departments'
import { getApiErrorDetail } from '@/api/request'
import LoadErrorAlert from '@/shared/feedback/LoadErrorAlert.vue'
import PageHeader from '@/shared/layout/PageHeader.vue'
import DepartmentWorkOrdersPanel from '../components/DepartmentWorkOrdersPanel.vue'
import DepartmentLedgerPanel from '../components/DepartmentLedgerPanel.vue'
import ProductionProgressPanel from '../components/ProductionProgressPanel.vue'

const route = useRoute()
const departments = ref<ProductionDepartment[]>([])
const loading = ref(false)
const error = ref('')
const activeTab = ref('orders')
let active = true
let revision = 0
const code = computed(() => String(route.params.departmentCode || ''))
const selected = computed(() => departments.value.find(item => item.code === code.value))
watch(code, () => { activeTab.value = 'orders' })
async function load() {
  const current = ++revision
  loading.value = true
  error.value = ''
  try {
    const result = await queryProductionDepartments()
    if (active && current === revision) departments.value = result
  } catch (cause) {
    if (active && current === revision) error.value = getApiErrorDetail(cause)?.message || '部门加载失败'
  } finally { if (active && current === revision) loading.value = false }
}
onMounted(load)
onBeforeUnmount(() => { active = false; revision += 1 })
</script>

<template>
  <main class="department-page">
    <PageHeader :section-name="code ? '生产执行' : '生产协同'" :page-title="code ? (selected ? selected.name + '工作台' : '部门工作台') : '生产进度'">
      <template #actions><ElButton :loading="loading" @click="load">刷新部门资料</ElButton></template>
    </PageHeader>
    <LoadErrorAlert :message="error" :loading="loading" @retry="load" />
    <section class="department-card" :class="{ 'department-execution': !!code }" v-loading="loading">
      <ElAlert v-if="code && !selected && !loading && !error" type="error" title="生产部门不存在" :closable="false" show-icon />
      <ElTabs v-model="activeTab" class="workspace-tabs">
        <ElTabPane :label="code ? '部门工单与交接' : '订单生产进度'" name="orders">
          <ProductionProgressPanel v-if="!code" />
          <DepartmentWorkOrdersPanel v-else-if="selected" :key="code" :department-code="code" :can-receive="selected.can_receive" />
        </ElTabPane>
        <ElTabPane label="部门流水" name="ledger" lazy :disabled="loading || !!error || (!!code && !selected)">
          <DepartmentLedgerPanel v-if="!error && (!code || selected)" :key="code" :department-code="code || undefined" />
        </ElTabPane>
      </ElTabs>
    </section>
  </main>
</template>

<style scoped>
.department-page { padding: 32px; }
.department-card { min-width: 0; border: 1px solid var(--erp-border); border-radius: 12px; padding: 8px 24px 24px; background: var(--erp-surface); box-shadow: var(--erp-shadow-sm); }
.workspace-tabs :deep(.el-tabs__item) { height: 56px; }
@media (max-width: 760px) { .department-page { padding: 24px 16px; }.department-card { padding: 4px 16px 16px; } }
.department-execution { padding: 0; border: 0; background: transparent; box-shadow: none; }
.department-execution :deep(.el-tabs__header) { padding: 0 16px; border: 1px solid var(--erp-border); border-radius: 12px; background: var(--erp-surface); }
.department-execution :deep(.el-tabs__nav-wrap::after) { display: none; }
</style>
