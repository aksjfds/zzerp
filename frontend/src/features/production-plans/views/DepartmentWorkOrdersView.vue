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
import ProductionBoard from '../components/ProductionBoard.vue'
import QualityPanel from '../components/QualityPanel.vue'
import HandoffTicketsPanel from '../components/HandoffTicketsPanel.vue'
import WarehousePanel from '../components/WarehousePanel.vue'
import WorkerPieceworkPanel from '../components/WorkerPieceworkPanel.vue'
import OutsourcingPanel from '../components/OutsourcingPanel.vue'
import PurchasingPanel from '../components/PurchasingPanel.vue'

const auth = useAuthStore()
const warehousePanel = ref<InstanceType<typeof WarehousePanel>>()
const warehouseTickets = ref<InstanceType<typeof HandoffTicketsPanel>>()
const purchasingPanel = ref<InstanceType<typeof PurchasingPanel>>()
const warehouseLedger = ref<InstanceType<typeof DepartmentLedgerPanel>>()
const ordersPanel = ref<InstanceType<typeof DepartmentWorkOrdersPanel>>()
const route = useRoute()
const departments = ref<ProductionDepartment[]>([])
const loading = ref(false)
const error = ref('')
const activeTab = ref('orders')
const warehouseTab = ref('handoffs')
const operationRevision = ref(0)
let active = true
let revision = 0
const code = computed(() => String(route.params.departmentCode || ''))
const selected = computed(() => departments.value.find(item => item.code === code.value))
const workersView = computed(() => code.value === 'grinding' && route.query.view === 'workers')
watch(code, () => { activeTab.value = 'orders'; warehouseTab.value = 'handoffs' })
function warehouseTabChanged(name: string | number) {
  if (name === 'handoffs') { void warehouseTickets.value?.refresh(); void warehousePanel.value?.refresh() }
  else if (name === 'purchasing') void purchasingPanel.value?.refresh()
  else if (name === 'ledger') void warehouseLedger.value?.refresh()
}
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
    <PageHeader :section-name="selected?.is_warehouse ? '仓库管理' : code ? '生产执行' : '生产协同'" :page-title="workersView ? '工人计件质检' : selected?.is_warehouse ? '仓库工作台' : code ? (selected ? selected.name + '工作台' : '部门工作台') : '生产进度'">
      <template v-if="!selected?.is_warehouse" #actions><ElButton :loading="loading" @click="load">刷新部门资料</ElButton></template>
    </PageHeader>
    <LoadErrorAlert :message="error" :loading="loading" @retry="load" />
    <WorkerPieceworkPanel v-if="workersView && selected" />
    <div v-else-if="selected?.is_warehouse" class="warehouse-workspace">
      <ElTabs v-model="warehouseTab" class="workspace-tabs warehouse-tabs" @tab-change="warehouseTabChanged">
        <ElTabPane label="物料交接" name="handoffs" lazy>
          <div class="warehouse-tab-content">
            <HandoffTicketsPanel ref="warehouseTickets" :key="`warehouse-tickets:${code}:${operationRevision}`" :department-code="code" @changed="warehousePanel?.refresh(); warehouseLedger?.refresh()" />
            <WarehousePanel ref="warehousePanel" :key="`${code}:${operationRevision}`" :can-dispatch="auth.user?.department_code === code && auth.hasPermission(DEPARTMENT_WORK_ORDER_OPERATE)" @dispatched="warehouseLedger?.refresh()" />
          </div>
        </ElTabPane>
        <ElTabPane label="采购" name="purchasing" lazy>
          <PurchasingPanel ref="purchasingPanel" :key="`purchase:${code}:${operationRevision}`" @changed="warehouseLedger?.refresh()" />
        </ElTabPane>
        <ElTabPane label="部门流水" name="ledger" lazy>
          <div class="warehouse-tab-content">
            <div class="department-card"><DepartmentLedgerPanel ref="warehouseLedger" :key="code" :department-code="code" @changed="operationRevision++" /></div>
          </div>
        </ElTabPane>
      </ElTabs>
    </div>
    <section v-else class="department-card" :class="{ 'department-execution': !!code }" v-loading="loading">
      <ElAlert v-if="code && !selected && !loading && !error" type="error" title="生产部门不存在" :closable="false" show-icon />
      <ElTabs v-if="!code || selected" v-model="activeTab" class="workspace-tabs">
        <ElTabPane :label="code ? '部门工单与交接' : '生产进度'" name="orders">
          <ProductionBoard v-if="!code" :key="operationRevision" />
          <template v-else-if="selected">
            <DepartmentWorkOrdersPanel ref="ordersPanel" :key="`${code}:${operationRevision}`" :department-code="code" :requires-inspection="selected.requires_inspection" :is-warehouse="selected.is_warehouse" />
          </template>
        </ElTabPane>
        <ElTabPane v-if="!code" label="物料交接" name="handoffs" lazy><HandoffTicketsPanel :key="operationRevision" /></ElTabPane>
        <ElTabPane v-if="!code || code === 'outsource'" label="委外加工" name="outsourcing" lazy><OutsourcingPanel :key="operationRevision" :active="activeTab === 'outsourcing'" @changed="ordersPanel?.refresh()" /></ElTabPane>
        <ElTabPane v-if="!code || selected?.requires_inspection" label="质检记录" name="quality" lazy><QualityPanel :key="`${code}:${operationRevision}`" /></ElTabPane>
        <ElTabPane v-if="!code || selected" label="仓库库存" name="warehouse" lazy><WarehousePanel :key="`${code}:${operationRevision}`" :department-code="code || undefined" /></ElTabPane>
        <ElTabPane label="部门流水" name="ledger" lazy :disabled="loading || !!error || (!!code && !selected)">
          <DepartmentLedgerPanel v-if="!error && (!code || selected)" :key="code" :department-code="code || undefined" :active="activeTab === 'ledger'" @changed="operationRevision++" />
        </ElTabPane>
      </ElTabs>
    </section>
  </main>
</template>

<style scoped>
.department-page { min-width: 0; max-width: 100%; padding: 32px; box-sizing: border-box; }
.warehouse-workspace { display: grid; grid-template-columns: minmax(0, 1fr); gap: 24px; min-width: 0; width: 100%; }
.warehouse-workspace :deep(.el-pagination) { max-width: 100%; overflow-x: auto; }
.warehouse-tabs { min-width: 0; }.warehouse-tab-content { display: grid; grid-template-columns: minmax(0, 1fr); gap: 24px; min-width: 0; }
.warehouse-tabs :deep(.el-tabs__header) { padding: 0 16px; border: 1px solid var(--erp-border); border-radius: 12px; background: var(--erp-surface); }
.warehouse-tabs :deep(.el-tabs__nav-wrap::after) { display: none; }
.department-card { min-width: 0; border: 1px solid var(--erp-border); border-radius: 12px; padding: 8px 24px 24px; background: var(--erp-surface); box-shadow: var(--erp-shadow-sm); }
.workspace-tabs :deep(.el-tabs__item) { height: 56px; }
@media (max-width: 760px) { .department-page { padding: 24px 16px; }.department-card { padding: 4px 16px 16px; } }
.department-execution { padding: 0; border: 0; background: transparent; box-shadow: none; }
.department-execution :deep(.el-tabs__header) { padding: 0 16px; border: 1px solid var(--erp-border); border-radius: 12px; background: var(--erp-surface); }
.department-execution :deep(.el-tabs__nav-wrap::after) { display: none; }
</style>
