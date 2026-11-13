<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { getApiErrorDetail } from '@/api/request'
import LoadErrorAlert from '@/shared/feedback/LoadErrorAlert.vue'
import { queryDepartmentLedger, type DepartmentLedgerMovement } from '../api/plans'

const props = defineProps<{ departmentCode?: string }>()
const rows = ref<DepartmentLedgerMovement[]>([])
const total = ref(0), page = ref(1), loading = ref(false), error = ref('')
let active = true, revision = 0
async function load() {
  const current = ++revision
  loading.value = true; error.value = ''; rows.value = []
  try {
    const result = await queryDepartmentLedger(page.value, props.departmentCode)
    if (!active || current !== revision) return
    if (!result.data.length && page.value > 1 && result.total <= (page.value-1)*50) {
      page.value = Math.max(1,Math.ceil(result.total/50)); await load(); return
    }
    rows.value = result.data; total.value = result.total
  } catch (cause) {
    if (active && current === revision) error.value = getApiErrorDetail(cause)?.message || '部门流水加载失败'
  } finally { if (active && current === revision) loading.value = false }
}
onMounted(load)
onBeforeUnmount(() => { active = false; revision += 1 })
</script>
<template>
  <section>
    <ElButton :loading="loading" @click="load">刷新</ElButton>
    <p>当前部门范围内所有工单的到料、出料记录，按时间精确到秒从早到晚排列。</p>
    <LoadErrorAlert :message="error" :loading="loading" @retry="load" />
    <ElTable v-if="!error" v-loading="loading" :data="rows" border empty-text="暂无部门流水">
      <ElTableColumn prop="order_no" label="订单号" min-width="160" />
      <ElTableColumn prop="department_name" label="部门" min-width="100" />
      <ElTableColumn label="产品" min-width="190"><template #default="{ row }">{{ row.factory_code }} · {{ row.product_name }}</template></ElTableColumn>
      <ElTableColumn prop="material_name" label="实际物料" min-width="170" />
      <ElTableColumn label="类型" width="80"><template #default="{ row }">{{ row.direction === 'receipt' ? '到料' : '出料' }}</template></ElTableColumn>
      <ElTableColumn prop="quantity" label="数量" min-width="120" align="right" />
      <ElTableColumn prop="ticket_no" label="交接票" min-width="140" />
      <ElTableColumn prop="actor_username" label="操作人" min-width="100" />
      <ElTableColumn prop="created_at" label="时间" min-width="180" />
      <ElTableColumn prop="note" label="备注" min-width="190" />
    </ElTable>
    <ElPagination v-if="!error" v-model:current-page="page" :total="total" :page-size="50" layout="prev, pager, next, total" @current-change="load" />
  </section>
</template>
<style scoped>
p { color: var(--erp-text-secondary); font-size: 13px; }
.el-pagination { margin-top: 16px; justify-content: flex-end; }
</style>
