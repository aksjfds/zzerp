<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { queryProductionDepartments, type ProductionDepartment } from '@/features/production-departments'
import { getApiErrorDetail } from '@/api/request'
import LoadErrorAlert from '@/shared/feedback/LoadErrorAlert.vue'
import PageHeader from '@/shared/layout/PageHeader.vue'
import { useAuthStore } from '@/stores/auth'
import DepartmentWorkOrdersPanel from '../components/DepartmentWorkOrdersPanel.vue'

const router = useRouter()
const authStore = useAuthStore()
const route = useRoute()
const departments = ref<ProductionDepartment[]>([])
const loading = ref(false)
const error = ref('')
let active = true
let revision = 0
const code = computed(() => String(route.params.departmentCode || ''))
const selected = computed(() => departments.value.find(item => item.code === code.value))
async function logout() {
  await authStore.logout()
  await router.replace('/login')
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
    <PageHeader section-name="生产部门" :page-title="selected ? selected.name + '工单' : '部门生产安排'"><template #actions><ElButton v-if="!authStore.user?.department_code" @click="router.push('/production-plans')">返回生产计划</ElButton><ElButton @click="logout">退出登录</ElButton></template></PageHeader>
    <section class="department-card" v-loading="loading">
      <LoadErrorAlert :message="error" :loading="loading" @retry="load" />
      <nav v-if="!authStore.user?.department_code" aria-label="生产部门" class="department-links">
        <ElButton :type="!code ? 'primary' : 'default'" @click="router.push('/department-work-orders')">全部部门</ElButton>
        <ElButton v-for="department in departments" :key="department.code" :type="code === department.code ? 'primary' : 'default'" @click="router.push({ name: 'department-production', params: { departmentCode: department.code } })">{{ department.name }}</ElButton>
      </nav>
      <ElAlert v-if="code && !selected && !loading && !error" type="error" title="生产部门不存在" :closable="false" />
      <DepartmentWorkOrdersPanel v-if="!code || selected" :key="code" :department-code="code || undefined" />
    </section>
  </main>
</template>

<style scoped>
.department-page { min-height: 100vh; padding: var(--erp-page-gutter); background: var(--erp-bg); }
.department-card { padding: 20px; border: 1px solid var(--erp-border); border-radius: var(--erp-radius-lg); background: var(--erp-surface); }
.department-links { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 20px; }
.department-links :deep(.el-button + .el-button) { margin-left: 0; }
</style>
