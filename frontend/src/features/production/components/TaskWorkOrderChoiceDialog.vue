<script setup lang="ts">
import { ref, watch } from 'vue'
import type { TaskWorkOrderChoice } from '../domain/workOrderCreation'

const props = defineProps<{
  modelValue: boolean
  choices: TaskWorkOrderChoice[]
}>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  confirm: [choice: TaskWorkOrderChoice]
}>()
const selectedKey = ref('')

watch(() => props.modelValue, visible => {
  if (visible) selectedKey.value = props.choices[0]?.key || ''
})

function confirm() {
  const choice = props.choices.find(item => item.key === selectedKey.value)
  if (choice) emit('confirm', choice)
}
</script>

<template>
  <ElDialog
    :model-value="modelValue"
    title="选择开单来源"
    width="520px"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <ElRadioGroup v-model="selectedKey" class="choice-list">
      <ElRadio
        v-for="choice in choices"
        :key="choice.key"
        :value="choice.key"
        border
      >
        <span class="choice-content">
          <strong>{{ choice.label }}</strong>
          <small>{{ choice.description }}</small>
        </span>
      </ElRadio>
    </ElRadioGroup>
    <template #footer>
      <ElButton @click="emit('update:modelValue', false)">取消</ElButton>
      <ElButton type="primary" :disabled="!selectedKey" @click="confirm">确定</ElButton>
    </template>
  </ElDialog>
</template>

<style scoped>
.choice-list {
  display: grid;
  gap: 10px;
  width: 100%;
}

.choice-list :deep(.el-radio) {
  width: 100%;
  height: auto;
  min-height: 58px;
  margin: 0;
  padding: 10px 14px;
}

.choice-content {
  display: grid;
  gap: 4px;
  white-space: normal;
}

.choice-content small {
  color: var(--el-text-color-secondary);
}
</style>
