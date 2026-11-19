<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import { saveWorkOrderSchedule, type DepartmentWorkOrder, type WorkOrderSchedule } from '../api/plans'

const props = defineProps<{ order: DepartmentWorkOrder; orders: DepartmentWorkOrder[] }>()
const emit = defineEmits<{ close: []; saved: [updates: WorkOrderSchedule[]] }>()
const date = ref(props.order.scheduled_date || '')
const saving = ref(false)
let active = true
onBeforeUnmount(() => { active = false })
async function save() {
  if (saving.value) return
  saving.value = true
  try {
    const updates = await saveWorkOrderSchedule(props.order, date.value || null, props.orders)
    if (!active) return
    ElMessage.success('交料日期已保存')
    emit('saved', updates)
  } catch (cause) {
    if (active) ElMessage.error(getApiErrorDetail(cause)?.message || '排产保存失败，请刷新后重试')
  } finally {
    if (active) saving.value = false
  }
}
</script>

<template>
  <ElDialog :model-value="true" title="设置交料日期" width="min(400px, 94vw)" :close-on-click-modal="!saving" :close-on-press-escape="!saving" :show-close="!saving" @close="emit('close')">
    <p>{{ order.order_no }} · {{ order.factory_code }} · {{ order.product_name }}</p>
    <p>{{ order.part_no }} · {{ order.part_name }} · {{ order.department_name }}</p>
    <ElForm label-position="top" :disabled="saving" @submit.prevent="save">
      <ElFormItem label="交料日期">
        <ElDatePicker v-model="date" type="date" value-format="YYYY-MM-DD" format="YYYY-MM-DD" placeholder="选择日期，清空则取消安排" />
      </ElFormItem>
      <ElButton type="primary" native-type="submit" :loading="saving">保存</ElButton>
    </ElForm>
  </ElDialog>
</template>
