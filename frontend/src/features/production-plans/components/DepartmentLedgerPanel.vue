<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { getApiErrorDetail } from '@/api/request'
import LoadErrorAlert from '@/shared/feedback/LoadErrorAlert.vue'
import { queryDepartmentLedger, type DepartmentLedgerMovement } from '../api/plans'
import ProductionDocumentPrintDialog from './ProductionDocumentPrintDialog.vue'
import IssuedDocumentsDialog from './IssuedDocumentsDialog.vue'

const props = defineProps<{ departmentCode?: string }>()
const rows = ref<DepartmentLedgerMovement[]>([])
const printRecord = ref<DepartmentLedgerMovement>()
const documentsVisible = ref(false)
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
<div class="collection-heading"><div><h2>部门物料流水</h2></div><div><ElButton @click="documentsVisible = true">交接单据</ElButton><ElButton :loading="loading" @click="load">刷新记录</ElButton></div></div>
    <LoadErrorAlert :message="error" :loading="loading" @retry="load" />
    <ElTable v-if="!error" v-loading="loading" :data="rows" empty-text="暂无部门流水">
      <ElTableColumn label="类型" width="80">
        <template #default="{ row }">{{ row.direction === 'receipt' ? '到料' : '出料' }}</template>
      </ElTableColumn>
      <ElTableColumn label="来自/到达" min-width="140">
        <template #default="{ row }">{{ row.direction === 'receipt' ? (row.source_department || '无来源到料') : (row.target_department || '终端出料') }}</template>
      </ElTableColumn>
      <ElTableColumn class-name="data-primary" label="产品" min-width="190">
        <template #default="{ row }">{{ row.factory_code }} · {{ row.product_name }}</template>
      </ElTableColumn>
      <ElTableColumn class-name="data-primary" label="配件/装配体" min-width="240">
        <template #default="{ row }">{{ row.material_no }} · {{ row.material_name }}</template>
      </ElTableColumn>
      <ElTableColumn class-name="data-reference" prop="order_no" label="订单号" min-width="160" />
      <ElTableColumn class-name="data-metric" prop="quantity" label="数量" min-width="120" align="right" />
      <ElTableColumn prop="actor_username" label="操作人" min-width="100" />
      <ElTableColumn class-name="data-secondary" prop="created_at" label="时间" min-width="180" />
      <ElTableColumn label="操作" width="90"><template #default="{ row }"><ElButton v-if="row.direction === 'issue' && row.ticket_no" link type="primary" @click="printRecord = row">打印</ElButton></template></ElTableColumn>
      <ElTableColumn class-name="data-secondary" prop="note" label="备注" min-width="190" />
    </ElTable>
    <ElPagination v-if="!error" v-model:current-page="page" :total="total" :page-size="50" layout="prev, pager, next, total" @current-change="load" />
    <ProductionDocumentPrintDialog v-if="printRecord" :document="{ kind: 'issue', record: printRecord }" @close="printRecord = undefined" />
    <IssuedDocumentsDialog v-if="documentsVisible" :department-code="departmentCode" @close="documentsVisible = false" />
  </section>
</template>
<style scoped>
p { color: var(--erp-text-secondary); font-size: 14px; }
.el-pagination { margin-top: 16px; justify-content: flex-end; }
</style>
