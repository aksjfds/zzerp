<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { DEPARTMENT_WORK_ORDER_OPERATE } from '@/permission/constants'
import { queryProductionDepartments, type ProductionDepartment } from '@/features/production-departments'
import { getApiErrorDetail } from '@/api/request'
import LoadErrorAlert from '@/shared/feedback/LoadErrorAlert.vue'
import PageHeader from '@/shared/layout/PageHeader.vue'
import DepartmentWorkOrdersPanel from '../components/DepartmentWorkOrdersPanel.vue'
import DepartmentLedgerPanel from '../components/DepartmentLedgerPanel.vue'
import ProductionProgressPanel from '../components/ProductionProgressPanel.vue'
import QualityPanel from '../components/QualityPanel.vue'
import HandoffTicketsPanel from '../components/HandoffTicketsPanel.vue'
import WarehousePanel from '../components/WarehousePanel.vue'
import WarehousePickHistory from '../components/WarehousePickHistory.vue'

const auth = useAuthStore()
const warehousePanel = ref<InstanceType<typeof WarehousePanel>>()
const warehouseHistory = ref<InstanceType<typeof WarehousePickHistory>>()
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
    <PageHeader :section-name="selected?.is_warehouse ? '仓库管理' : code ? '生产执行' : '生产协同'" :page-title="selected?.is_warehouse ? '仓库工作台' : code ? (selected ? selected.name + '工作台' : '部门工作台') : '生产进度'">
      <template v-if="!selected?.is_warehouse" #actions><ElButton :loading="loading" @click="load">刷新部门资料</ElButton></template>
    </PageHeader>
    <LoadErrorAlert :message="error" :loading="loading" @retry="load" />
    <div v-if="selected?.is_warehouse" class="warehouse-workspace">
      <HandoffTicketsPanel :key="`warehouse-tickets:${code}`" :department-code="code" @changed="warehousePanel?.refresh()" />
      <WarehousePanel ref="warehousePanel" :key="code" :can-dispatch="auth.user?.department_code === code && auth.hasPermission(DEPARTMENT_WORK_ORDER_OPERATE)" @dispatched="warehouseHistory?.refresh()" />
      <WarehousePickHistory ref="warehouseHistory" :key="`warehouse-history:${code}`" title="出料记录" />
    </div>
    <section v-else class="department-card" :class="{ 'department-execution': !!code }" v-loading="loading">
      <ElAlert v-if="code && !selected && !loading && !error" type="error" title="生产部门不存在" :closable="false" show-icon />
      <ElTabs v-if="!code || selected" v-model="activeTab" class="workspace-tabs">
        <ElTabPane :label="code ? '部门工单与交接' : '订单生产进度'" name="orders">
          <ProductionProgressPanel v-if="!code" />
          <template v-else-if="selected">
            <DepartmentWorkOrdersPanel :key="code" :department-code="code" :requires-inspection="selected.requires_inspection" :is-warehouse="selected.is_warehouse" />
          </template>
        </ElTabPane>
        <ElTabPane v-if="!code" label="物料交接" name="handoffs" lazy><HandoffTicketsPanel /></ElTabPane>
        <ElTabPane v-if="!code || selected?.requires_inspection" label="质检记录" name="quality" lazy><QualityPanel :key="code" /></ElTabPane>
        <ElTabPane v-if="!code || selected" label="仓库库存" name="warehouse" lazy><WarehousePanel :key="code" :department-code="code || undefined" /></ElTabPane>
        <ElTabPane label="部门流水" name="ledger" lazy :disabled="loading || !!error || (!!code && !selected)">
          <DepartmentLedgerPanel v-if="!error && (!code || selected)" :key="code" :department-code="code || undefined" />
        </ElTabPane>
      </ElTabs>
    </section>
  </main>
</template>

<style scoped>
.department-page { min-width: 0; max-width: 100%; padding: 32px; box-sizing: border-box; }
.warehouse-workspace { display: grid; grid-template-columns: minmax(0, 1fr); gap: 24px; min-width: 0; width: 100%; }
.warehouse-workspace :deep(.el-pagination) { max-width: 100%; overflow-x: auto; }
.department-card { min-width: 0; border: 1px solid var(--erp-border); border-radius: 12px; padding: 8px 24px 24px; background: var(--erp-surface); box-shadow: var(--erp-shadow-sm); }
.workspace-tabs :deep(.el-tabs__item) { height: 56px; }
@media (max-width: 760px) { .department-page { padding: 24px 16px; }.department-card { padding: 4px 16px 16px; } }
.department-execution { padding: 0; border: 0; background: transparent; box-shadow: none; }
.department-execution :deep(.el-tabs__header) { padding: 0 16px; border: 1px solid var(--erp-border); border-radius: 12px; background: var(--erp-surface); }
.department-execution :deep(.el-tabs__nav-wrap::after) { display: none; }
</style>
