<script setup lang="ts">
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import LoadErrorAlert from '@/shared/feedback/LoadErrorAlert.vue'
import { queryRepairTargets, queryQualityOrigin, saveInspection, type QualityOrigin, type InspectionBatch, type RepairTarget } from '../api/quality'

const props = defineProps<{ batch: InspectionBatch }>()
const emit = defineEmits<{ close: []; saved: [] }>()
const form = reactive({ good: 0, scrap: 0, rework: 0, target: undefined as string | undefined, note: '' })
const targets = ref<RepairTarget[]>([])
const origin = ref<QualityOrigin>()
const repairKind = ref<'original' | 'cross'>('original')
const loading = ref(false), saving = ref(false), error = ref('')
const requestId = crypto.randomUUID()
let active = true
async function load() {
  loading.value = true
  error.value = ''
  try { const [result, source] = await Promise.all([queryRepairTargets(props.batch.work_order_id), queryQualityOrigin(props.batch)]); if (active) { targets.value = result; origin.value = source; if (source.department_code === 'qc') repairKind.value = 'cross' } }
  catch (cause) { if (active) error.value = getApiErrorDetail(cause)?.message || '返修部门加载失败' }
  finally { if (active) loading.value = false }
}
async function save() {
  if (saving.value || loading.value || error.value) return
  const counts = [form.good, form.scrap, form.rework]
  if (counts.some(value => !Number.isSafeInteger(value) || value < 0)
    || counts.reduce((sum, value) => sum + BigInt(value), 0n) !== BigInt(props.batch.quantity)) {
    ElMessage.warning('合格、报废和返修数量之和必须等于来料数量')
    return
  }
  if ((form.scrap > 0 || form.rework > 0) && !form.note.trim()) { ElMessage.warning('有报废或返修时必须填写备注'); return }
  const repairDepartment = repairKind.value === 'original' ? origin.value?.department_code : form.target
  if (form.rework > 0 && !repairDepartment) { ElMessage.warning('请选择返修部门'); return }
  if (!props.batch.source_kind) return
  saving.value = true
  try {
    await saveInspection({ source_kind: props.batch.source_kind, source_id: props.batch.id,
      good_quantity: form.good, scrap_quantity: form.scrap, rework_quantity: form.rework,
      repair_department_code: form.rework > 0 ? repairDepartment! : null, repair_kind: form.rework > 0 ? repairKind.value : null, request_id: requestId, note: form.note.trim() })
    if (active) { ElMessage.success('质检已登记'); emit('saved') }
  } catch (cause) { if (active) ElMessage.error(getApiErrorDetail(cause)?.message || '质检保存失败') }
  finally { if (active) saving.value = false }
}
onMounted(load)
onBeforeUnmount(() => { active = false })
</script>
<template>
  <ElDialog :model-value="true" title="来料质检" width="min(560px, 94vw)" :close-on-click-modal="!saving" :close-on-press-escape="!saving" :show-close="!saving" @close="emit('close')">
    <p>{{ batch.order_no }} · {{ batch.product }}</p>
    <p>{{ batch.material }} · 来料数量 {{ batch.quantity }}</p>
    <p v-if="origin?.worker_name">计件工人：{{ origin.worker_name }}</p>
    <LoadErrorAlert :message="error" :loading="loading" @retry="load" />
    <ElForm label-position="top" :disabled="saving" @submit.prevent="save">
      <div class="qc-counts">
        <ElFormItem label="合格数" required><ElInputNumber v-model="form.good" :min="0" :max="Number(batch.quantity)" :precision="0" /></ElFormItem>
        <ElFormItem label="报废数" required><ElInputNumber v-model="form.scrap" :min="0" :max="Number(batch.quantity)" :precision="0" /></ElFormItem>
        <ElFormItem label="返修数" required><ElInputNumber v-model="form.rework" :min="0" :max="Number(batch.quantity)" :precision="0" /></ElFormItem>
      </div>
      <ElFormItem v-if="form.rework > 0" label="返修部门" required>
        <ElRadioGroup v-model="repairKind"><ElRadioButton value="original" :disabled="origin?.department_code === 'qc'">原部门原工人</ElRadioButton><ElRadioButton value="cross">跨部门返修</ElRadioButton></ElRadioGroup>
        <p v-if="repairKind === 'original'">{{ targets.find(item => item.code === origin?.department_code)?.label }} {{ origin?.worker_name }}</p>
        <ElSelect v-else v-model="form.target" filterable :loading="loading" placeholder="选择其他部门"><ElOption v-for="item in targets.filter(item => item.code !== origin?.department_code)" :key="item.code" :value="item.code" :label="item.label" /></ElSelect>
      </ElFormItem>
      <ElFormItem label="备注" :required="form.scrap > 0 || form.rework > 0"><ElInput v-model="form.note" type="textarea" maxlength="2000" /></ElFormItem>
      <ElButton type="primary" native-type="submit" :loading="saving" :disabled="loading || !!error">保存质检</ElButton>
    </ElForm>
  </ElDialog>
</template>
<style scoped>
.qc-counts { display: flex; flex-wrap: wrap; gap: 16px; }
</style>
