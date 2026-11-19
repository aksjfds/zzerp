<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { getApiErrorDetail } from '@/api/request'
import LoadErrorAlert from '@/shared/feedback/LoadErrorAlert.vue'
import { queryHandoffTickets, type HandoffTicket } from '../api/plans'
import ProductionDocumentPrintDialog from './ProductionDocumentPrintDialog.vue'

const props = defineProps<{ departmentCode?: string }>()
const emit = defineEmits<{ close: [] }>()
const rows = ref<HandoffTicket[]>([]), total = ref(0), page = ref(1)
const loading = ref(false), error = ref(''), selected = ref<HandoffTicket>()
let active = true, revision = 0
function rowKey(row: HandoffTicket) { return `${row.kind}:${row.id}` }
async function load() {
  const current = ++revision
  loading.value = true; error.value = ''; rows.value = []
  try {
    const result = await queryHandoffTickets({ page: page.value, direction: 'outgoing', unreceived: false, department_code: props.departmentCode })
    if (!active || current !== revision) return
    if (!result.data.length && page.value > 1 && result.total <= (page.value - 1) * 50) {
      page.value = Math.max(1, Math.ceil(result.total / 50)); await load(); return
    }
    rows.value = result.data; total.value = result.total
  } catch (cause) { if (active && current === revision) error.value = getApiErrorDetail(cause)?.message || '交接单据加载失败' }
  finally { if (active && current === revision) loading.value = false }
}
onMounted(load)
onBeforeUnmount(() => { active = false; revision += 1 })
</script>
<template>
  <ElDialog :model-value="true" title="交接单据" width="min(1000px, 96vw)" @close="emit('close')">
    <LoadErrorAlert :message="error" :loading="loading" @retry="load" />
    <ElTable v-if="!error" v-loading="loading" :data="rows" :row-key="rowKey" empty-text="暂无已出料交接单据">
      <ElTableColumn prop="ticket_no" label="单据编号" min-width="150" />
      <ElTableColumn class-name="data-primary" label="产品" min-width="180"><template #default="{ row }">{{ row.factory_code }} · {{ row.product_name }}</template></ElTableColumn>
      <ElTableColumn class-name="data-primary" label="配件/装配体" min-width="200"><template #default="{ row }">{{ row.material_no }} · {{ row.material_name }}</template></ElTableColumn>
      <ElTableColumn label="交接" min-width="220"><template #default="{ row }">{{ row.source_department }} -&gt; {{ row.target_department }}，{{ row.quantity }}</template></ElTableColumn>
      <ElTableColumn class-name="data-secondary" prop="created_at" label="时间" min-width="180" />
      <ElTableColumn label="操作" width="80"><template #default="{ row }"><ElButton link type="primary" @click="selected = row">打印</ElButton></template></ElTableColumn>
    </ElTable>
    <ElPagination v-model:current-page="page" :total="total" :page-size="50" layout="prev, pager, next, total" @current-change="load" />
  </ElDialog>
  <ProductionDocumentPrintDialog v-if="selected" :document="{ kind: 'handoff', record: selected }" @close="selected = undefined" />
</template>
