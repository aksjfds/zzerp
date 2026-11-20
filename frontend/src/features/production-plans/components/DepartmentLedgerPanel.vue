<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { DEPARTMENT_WORK_ORDER_OPERATE } from '@/permission/constants'
import { getApiErrorDetail } from '@/api/request'
import LoadErrorAlert from '@/shared/feedback/LoadErrorAlert.vue'
import { queryDepartmentLedger, type DepartmentLedgerMovement, type DepartmentLedgerRecord } from '../api/plans'
import ProductionDocumentPrintDialog from './ProductionDocumentPrintDialog.vue'
import IssuedDocumentsDialog from './IssuedDocumentsDialog.vue'
import { revokeOperation } from '../api/operations'

const props = defineProps<{ departmentCode?: string; active?: boolean }>()
const emit = defineEmits<{ changed: [] }>()
const auth = useAuthStore()
const canOperate = computed(() => !!auth.user?.department_code && auth.hasPermission(DEPARTMENT_WORK_ORDER_OPERATE))
const rows = ref<DepartmentLedgerRecord[]>([])
const printRecord = ref<DepartmentLedgerMovement>()
const documentsVisible = ref(false)
const total = ref(0), page = ref(1), loading = ref(false), error = ref('')
const selected = ref<DepartmentLedgerRecord>(), reason = ref(''), saving = ref(false), saveError = ref('')
let active = true, revision = 0
defineExpose({ refresh: () => load() })
function print(row: DepartmentLedgerRecord) { if (row.movement && !row.revoked_at) printRecord.value = row.movement }
function rowKey(row: DepartmentLedgerRecord) { return `${row.kind}:${row.id}` }
function openRevoke(row: DepartmentLedgerRecord) {
  if (!row.can_revoke || saving.value) return
  selected.value = row; reason.value = ''; saveError.value = ''
}
function closeRevoke() { if (!saving.value) selected.value = undefined }
function visibilityChanged(value: boolean) { if (!value) closeRevoke() }
async function saveRevoke() {
  if (!selected.value || !selected.value.can_revoke || saving.value) return
  if (!reason.value.trim()) { saveError.value = '请填写撤回原因'; return }
  saving.value = true; saveError.value = ''
  try {
    await revokeOperation(selected.value, reason.value.trim())
    if (!active) return
    selected.value = undefined; emit('changed'); await load()
  } catch (cause) {
    if (active) {
      const detail = getApiErrorDetail(cause)
      saveError.value = detail?.message || '撤回失败'
      if (selected.value && ['operation_has_followup', 'revoke_plan_closed', 'revoke_department_denied', 'revoke_operator_required'].includes(detail?.code || '')) {
        selected.value.can_revoke = false; selected.value.revoke_blocker = saveError.value
        await load()
      }
    }
  }
  finally { if (active) saving.value = false }
}
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
watch(() => props.active, value => { if (value) void load() })
onBeforeUnmount(() => { active = false; revision += 1 })
</script>
<template>
  <section>
<div class="collection-heading"><div><h2>部门物料流水</h2></div><div><ElButton @click="documentsVisible = true">交接单据</ElButton><ElButton :loading="loading" @click="load">刷新记录</ElButton></div></div>
    <LoadErrorAlert :message="error" :loading="loading" @retry="load" />
    <ElTable v-if="!error" v-loading="loading" :data="rows" :row-key="rowKey" empty-text="暂无部门流水">
      <ElTableColumn label="类型" min-width="110">
        <template #default="{ row }"><span>{{ row.label }}</span><ElTag v-if="row.revoked_at" class="revoked-tag" type="info" size="small">已撤回</ElTag></template>
      </ElTableColumn>
      <ElTableColumn label="来自/到达" min-width="140">
        <template #default="{ row }">{{ row.counterpart }}</template>
      </ElTableColumn>
      <ElTableColumn class-name="data-primary" label="产品" min-width="190">
        <template #default="{ row }">{{ row.product }}</template>
      </ElTableColumn>
      <ElTableColumn class-name="data-primary" label="配件/装配体" min-width="240">
        <template #default="{ row }">{{ row.material }}</template>
      </ElTableColumn>
      <ElTableColumn class-name="data-reference" prop="order_no" label="订单号" min-width="160" />
      <ElTableColumn class-name="data-metric" prop="quantity" label="数量" min-width="120" align="right" />
      <ElTableColumn prop="actor_username" label="操作人" min-width="100" />
      <ElTableColumn class-name="data-secondary" prop="created_at" label="时间" min-width="180" />
      <ElTableColumn label="操作" min-width="130"><template #default="{ row }">
        <ElButton v-if="!row.revoked_at && row.movement?.direction === 'issue' && row.movement.ticket_no" link type="primary" @click="print(row)">打印</ElButton>
        <span v-if="canOperate" :title="row.revoke_blocker || ''"><ElButton link type="danger" :disabled="saving || !row.can_revoke" @click="openRevoke(row)">撤回</ElButton></span>
      </template></ElTableColumn>
      <ElTableColumn class-name="data-secondary" label="备注" min-width="240"><template #default="{ row }">{{ row.note }}<div v-if="row.revoked_at" class="revocation-meta"><strong>撤回：{{ row.revoke_reason }}</strong><div>{{ row.revoked_by }} · {{ row.revoked_at }}</div></div></template></ElTableColumn>
    </ElTable>
    <ElPagination v-if="!error" v-model:current-page="page" :total="total" :page-size="50" layout="prev, pager, next, total" @current-change="load" />
    <ProductionDocumentPrintDialog v-if="printRecord" :document="{ kind: 'issue', record: printRecord }" @close="printRecord = undefined" />
    <IssuedDocumentsDialog v-if="documentsVisible" :department-code="departmentCode" @close="documentsVisible = false" />
    <ElDialog :model-value="!!selected" title="撤回操作" width="min(480px, 94vw)" align-center :show-close="!saving" :close-on-click-modal="false" :close-on-press-escape="!saving" @update:model-value="visibilityChanged">
      <template v-if="selected"><div class="revoke-context"><strong>{{ selected.label }} · {{ selected.quantity }}</strong><div>{{ selected.product }}</div><div>{{ selected.material }} · {{ selected.order_no }}</div></div>
        <ElForm label-position="top" :disabled="saving" @submit.prevent="saveRevoke"><ElFormItem label="撤回原因" required><ElInput v-model="reason" type="textarea" :rows="3" maxlength="1000" /></ElFormItem></ElForm>
        <ElAlert v-if="saveError" :title="saveError" type="error" :closable="false" show-icon />
      </template>
      <template #footer><ElButton :disabled="saving" @click="closeRevoke">取消</ElButton><ElButton type="danger" :loading="saving" :disabled="!selected?.can_revoke" @click="saveRevoke">确认撤回</ElButton></template>
    </ElDialog>
  </section>
</template>
<style scoped>
p { color: var(--erp-text-secondary); font-size: 14px; }
.el-pagination { margin-top: 16px; justify-content: flex-end; }
.revoked-tag { margin-left: 6px; }
.revocation-meta { color: var(--erp-text-secondary); font-size: 12px; margin-top: 6px; }
.revoke-context { display: grid; gap: 8px; margin-bottom: 20px; }
</style>
