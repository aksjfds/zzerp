<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import { saveWorkOrderSchedule, type DepartmentWorkOrder, type WorkOrderSchedule } from '../api/plans'

const props = defineProps<{ order: DepartmentWorkOrder; orders: DepartmentWorkOrder[]; editable: boolean }>()
const emit = defineEmits<{ edit: []; saved: [updates: WorkOrderSchedule[]] }>()
const dayOffset = ref(0), saving = ref(false)
let active = true
let ownRevision: number | undefined
watch(() => props.order.schedule_revision, revision => {
  if (revision !== ownRevision) dayOffset.value = 0
  ownRevision = undefined
})
onBeforeUnmount(() => { active = false })
async function adjustDate(value: number | undefined, previous: number | undefined) {
  const oldOffset = previous ?? 0
  if (saving.value || !props.editable || !props.order.scheduled_date || value === undefined) {
    dayOffset.value = oldOffset
    return
  }
  if (value === oldOffset) return
  const date = new Date(`${props.order.scheduled_date}T00:00:00Z`)
  date.setUTCDate(date.getUTCDate() + value - oldOffset)
  if (!Number.isFinite(date.getTime()) || date.getUTCFullYear() < 1 || date.getUTCFullYear() > 9999) {
    dayOffset.value = oldOffset
    ElMessage.warning('日期超出有效范围')
    return
  }
  saving.value = true
  try {
    const updates = await saveWorkOrderSchedule(props.order, date.toISOString().slice(0, 10), props.orders)
    if (!active) return
    const current = updates.find(item => item.id === props.order.id)
    if (!current) throw new Error('排产响应缺少当前工单')
    ownRevision = current.schedule_revision
    emit('saved', updates)
  } catch (cause) {
    if (active) {
      dayOffset.value = oldOffset
      ElMessage.error(getApiErrorDetail(cause)?.message || '日期调整失败，请刷新后重试')
    }
  } finally { if (active) saving.value = false }
}
</script>
<template>
  <div v-if="editable" class="schedule-cell">
    <ElButton link type="primary" :disabled="saving" @click="emit('edit')">{{ order.scheduled_date || '设置日期' }}</ElButton>
    <ElInputNumber v-model="dayOffset" size="small" :step="1" :precision="0" :min="-36500" :max="36500" :disabled="saving || !order.scheduled_date" aria-label="调整交料日期天数" @change="adjustDate" />
  </div>
  <span v-else>{{ order.scheduled_date || '未安排' }}</span>
</template>
<style scoped>
.schedule-cell { display: inline-flex; align-items: center; gap: 8px; max-width: 100%; }
.schedule-cell :deep(.el-button) { margin: 0; flex-shrink: 0; }
.schedule-cell :deep(.el-input-number) { width: 144px; flex-shrink: 0; }
</style>
