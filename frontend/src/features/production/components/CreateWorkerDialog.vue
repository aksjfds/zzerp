<script setup lang="ts">
import { reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { WorkerWorkshop } from '@/features/workers'

const props = defineProps<{
  modelValue: boolean
  workshops: WorkerWorkshop[]
  submitting: boolean
}>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  submit: [payload: { workerName: string; workshopId: number | null }]
}>()
const form = reactive({
  workerName: '',
  workshopId: null as number | null,
})

watch(() => props.modelValue, (visible) => {
  if (!visible) return
  form.workerName = ''
  form.workshopId = props.workshops.length === 1
    ? (props.workshops[0]?.id ?? null)
    : null
})

function submit() {
  const workerName = form.workerName.trim()
  if (!workerName) {
    ElMessage.warning('请输入工人姓名')
    return
  }
  if (props.workshops.length && !form.workshopId) {
    ElMessage.warning('请选择工人所属车间')
    return
  }
  emit('submit', { workerName, workshopId: form.workshopId })
}
</script>

<template>
  <ElDialog
    :model-value="modelValue"
    title="录入工人"
    width="440px"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <ElForm label-position="top">
      <ElFormItem label="工人姓名" required>
        <ElInput v-model="form.workerName" maxlength="100" placeholder="请输入工人姓名" />
      </ElFormItem>
      <ElFormItem v-if="workshops.length" label="所属车间" required>
        <ElSelect
          v-model="form.workshopId"
          placement="top-start"
          :fallback-placements="['top-start', 'top-end']"
          placeholder="请选择所属车间"
          style="width: 100%"
        >
          <ElOption
            v-for="workshop in workshops"
            :key="workshop.id"
            :label="workshop.workshop_name"
            :value="workshop.id"
          />
        </ElSelect>
      </ElFormItem>
      <ElAlert v-else type="info" :closable="false" title="该部门没有车间，工人将录入为部门直属。" />
    </ElForm>
    <template #footer>
      <ElButton @click="emit('update:modelValue', false)">取消</ElButton>
      <ElButton type="primary" :loading="submitting" @click="submit">确认录入</ElButton>
    </template>
  </ElDialog>
</template>
