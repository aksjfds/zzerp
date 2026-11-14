<script setup lang="ts">
import { useSessionNavigation } from '@/features/identity'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { queryProductionDepartments, type ProductionDepartment } from '@/features/production-departments'
import { useRequest } from '@/shared/query/useRequest'
import LoadErrorAlert from '@/shared/feedback/LoadErrorAlert.vue'
import PageHeader from '@/shared/layout/PageHeader.vue'
import { useAuthStore } from '@/features/identity'
import DepartmentWorkOrdersPanel from '../components/DepartmentWorkOrdersPanel.vue'
import DepartmentLedgerPanel from '../components/DepartmentLedgerPanel.vue'
import ProductionProgressPanel from '../components/ProductionProgressPanel.vue'

const router = useRouter()
const authStore = useAuthStore()
const route = useRoute()
const departmentRequest = useRequest<ProductionDepartment[]>('部门加载失败')
const departments = computed(() => departmentRequest.data.value ?? [])
const loading = departmentRequest.loading
const error = departmentRequest.error
const ledgerOpen = ref(false)
const code = computed(() => String(route.params.departmentCode || ''))
const selected = computed(() => departments.value.find(item => item.code === code.value))
watch(code, () => { ledgerOpen.value = false })
const { logout } = useSessionNavigation()
function load() { return departmentRequest.run(queryProductionDepartments) }
onMounted(load)
</script>

<template>
  <main class="department-page">
    <PageHeader section-name="生产部门" :page-title="code ? (selected ? selected.name + '工单' : '部门工单') : '生产进度查看'"><template #actions><ElButton :disabled="loading || !!error || (!!code && !selected)" @click="ledgerOpen = true">部门流水</ElButton><ElButton v-if="!authStore.user?.department_code" @click="router.push('/production-plans')">返回生产计划</ElButton><ElButton @click="logout">退出登录</ElButton></template></PageHeader>
    <section class="department-card" v-loading="loading">
      <LoadErrorAlert :message="error" :loading="loading" @retry="load" />
      
      <ElAlert v-if="code && !selected && !loading && !error" type="error" title="生产部门不存在" :closable="false" />
      <ProductionProgressPanel v-if="!code" />
      <DepartmentWorkOrdersPanel v-else-if="selected" :key="code" :department-code="code" :can-receive="selected.can_receive" />
    </section>
    <ElDialog v-model="ledgerOpen" :title="`${selected?.name || '全部部门'}流水`" width="min(1440px, 98vw)" destroy-on-close>
      <DepartmentLedgerPanel v-if="ledgerOpen" :key="code" :department-code="code || undefined" />
    </ElDialog>
  </main>
</template>

<style scoped>
.department-page { min-height: 100vh; padding: var(--erp-page-gutter); background: var(--erp-bg); }
.department-card { padding: 20px; border: 1px solid var(--erp-border); border-radius: var(--erp-radius-lg); background: var(--erp-surface); }
.department-links { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 20px; }
.department-links :deep(.el-button + .el-button) { margin-left: 0; }
@media (max-width: 600px) {
  .department-card { min-width: 0; padding: 12px; }
  .department-links { flex-wrap: nowrap; overflow-x: auto; padding-bottom: 8px; }
  .department-links :deep(.el-button) { flex-shrink: 0; }
}
</style>
