<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import RepositoryCards from '../components/RepositoryCards.vue'
import { queryDepartmentRepositories } from '../api/repositories'
import type { RepositoryItem } from '../domain/types'

const props = defineProps<{
  departmentCode: string
  departmentName: string
  description: string
}>()
const router = useRouter()
const authStore = useAuthStore()
const loading = ref(false)
const keyword = ref('')
const items = ref<RepositoryItem[]>([])
const filteredItems = computed(() => {
  const value = keyword.value.trim().toLowerCase()
  if (!value) return items.value
  return items.value.filter((item) => [
    item.customer_order_no,
    item.customer_name,
    item.factory_code,
    item.product_name,
    item.part_name,
    item.part_no,
    item.procedure_name,
  ].some((field) => field.toLowerCase().includes(value)))
})
async function loadItems() {
  loading.value = true
  try { items.value = await queryDepartmentRepositories(props.departmentCode) }
  catch { ElMessage.error('部门生产资料加载失败') }
  finally { loading.value = false }
}

async function logout() {
  await authStore.logout()
  router.replace('/login')
}

onMounted(loadItems)
</script>

<template>
  <main class="page-shell">
    <header class="page-header">
      <div><span>{{ departmentName }}</span><h1>{{ departmentName }}工作台</h1><p>{{ description }}</p></div>
      <div><ElButton @click="loadItems">刷新</ElButton><ElButton @click="logout">退出登录</ElButton></div>
    </header>
    <section class="workspace-grid">
      <div class="content-card">
        <div class="toolbar"><ElInput v-model="keyword" clearable placeholder="搜索订单、产品或配件" /></div>
        <RepositoryCards :items="filteredItems" :loading="loading" />
      </div>
      <div class="content-card work-orders">
        <h2>工单</h2>
        <ElEmpty description="工单系统暂未启用" :image-size="64" />
      </div>
    </section>
  </main>
</template>

<style scoped>
.page-shell { min-height: 100vh; padding: 24px; background: var(--erp-bg); }
.page-header, .content-card { border: 1px solid var(--erp-border); border-radius: 10px; background: #fff; box-shadow: var(--erp-shadow-sm); }
.page-header { display: flex; justify-content: space-between; gap: 20px; align-items: center; margin-bottom: 18px; padding: 20px 24px; }
.page-header span { color: var(--erp-primary); font-size: 12px; font-weight: 700; }
.page-header h1 { margin: 5px 0; font-size: 24px; }
.page-header p { margin: 0; color: var(--el-text-color-secondary); }
.content-card { margin-bottom: 18px; padding: 20px; }
.content-card h2 { margin: 0; font-size: 17px; }
.toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.toolbar .el-input { width: 360px; }
.workspace-grid { display: grid; grid-template-columns: minmax(280px, 360px) minmax(0, 1fr); gap: 18px; align-items: start; }
.work-orders { min-height: 260px; }
@media (max-width: 900px) { .workspace-grid { grid-template-columns: 1fr; } .page-header { align-items: flex-start; flex-direction: column; } }
</style>
